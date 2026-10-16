import unittest,json,io,base64
from unittest.mock import patch
from PIL import Image
from test_journal import app,connection,DEFAULTS,MEDIA
from journal.platform_sync import preview,booking_id,PROVIDERS
TEXT='''강촌 스칼라 캠프
예약번호: 9744403
예약일: 2026.10.09 (2박3일)
예약정보: G 존 / G 3
예약 취소'''
def photo(color):
 out=io.BytesIO();Image.new('RGB',(120,90),color).save(out,'JPEG');return 'data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode()
class PlatformSyncTest(unittest.TestCase):
 def setUp(self):
  self.client=app.test_client();self.headers={'X-Camp-Request':'1'}
  with connection() as c:c.execute('DELETE FROM platform_sync_history');c.execute('DELETE FROM platform_accounts');c.execute('DELETE FROM records');c.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(DEFAULTS),))
 def capture(self,provider='camfit',text=TEXT,media=None):return {'provider':provider,'cards':[{'text':text,'media':media or []}]}
 def post(self,path,data):return self.client.post('/api/platforms/'+path,json=data,headers=self.headers)
 def test_camfit_cancelled_detail_short_dates_remains_visible_not_registerable(self):
  text='캠핑장명: 숲속 캠핑장\n예약번호: 2407123456\n입실일: 07.27(토)\n퇴실일: 07.28(일)\n사이트명: A-14\n주소: 경기 가평군 숲길 15\n총금액: 66,000원\n예약이 취소되었습니다'
  with patch('journal.reservation_import.current_year',return_value=2026):
   result=self.post('preview',self.capture(text=text)).json
  self.assertEqual(len(result['records']),1);row=result['records'][0]
  self.assertTrue(row['cancelled']);self.assertTrue(row['year_assumed']);self.assertEqual(row['checkin'],'2026-07-27');self.assertEqual(row['checkout'],'2026-07-28');self.assertEqual(row['name'],'숲속 캠핑장');self.assertEqual(row['site'],'A-14');self.assertEqual(row['price'],66000)
  self.assertEqual(self.post('commit',{'records':[row]}).status_code,400)
 def test_checkpoint_preview_reports_completed_boundary(self):
  raw=self.capture();raw.update(stopped_at_synced=True,already_synced=1,scan_reason='checkpoint',scan_truncated=False)
  result=self.post('preview',raw).json
  self.assertTrue(result['stopped_at_synced']);self.assertEqual(result['scan_reason'],'checkpoint');self.assertFalse(result['scan_truncated']);self.assertEqual(result['already_synced'],1);self.assertEqual(len(result['records']),1)
 def test_preview_is_read_only_preserves_source_cards_and_skips_only_cancelled_states(self):
  for provider in PROVIDERS:
   result=self.post('preview',self.capture(provider));self.assertEqual(result.status_code,200);row=result.json['records'][0];self.assertEqual(row['name'],'강촌 스칼라 캠프');self.assertEqual(row['platform'],PROVIDERS[provider]);self.assertEqual(row['platform_sync']['booking_id'],'9744403');self.assertEqual(row['checkout'],'2026-10-11')
  self.assertEqual(self.client.get('/api/state').json['records'],[])
  cancelled=self.post('preview',self.capture(text=TEXT+'\n취소 완료')).json;self.assertEqual(cancelled['cancelled_count'],1);self.assertTrue(cancelled['records'][0]['cancelled']);self.assertEqual(self.post('commit',{'records':cancelled['records']}).status_code,400)
  self.assertEqual(self.post('preview',self.capture(provider='unknown')).status_code,400)
  self.assertEqual(self.client.post('/api/platforms/commit',json={'records':[]}).status_code,403)
 def test_successful_sync_is_incremental_and_keeps_existing_data_untouched(self):
  capture=self.capture(media=[{'kind':'gallery','data':photo('blue')},{'kind':'layout','data':photo('green')}])
  rows=self.post('preview',capture).json['records'];self.assertEqual(len(rows[0]['sync_media']),2)
  self.assertIsNone(self.client.get('/api/platforms/state').json['camfit']['last_synced'])
  result=self.post('commit',{'records':rows});self.assertEqual(result.status_code,200);self.assertEqual(len(result.json['added']),1);self.assertEqual(result.json['photos_added'],2)
  before=self.client.get('/api/state').json['records'];history=self.client.get('/api/platforms/state').json['camfit'];self.assertEqual(history['booking_ids'],['9744403']);self.assertTrue(history['last_synced']);self.assertEqual(len(history['text_hashes']),1)
  again=self.post('preview',capture).json;self.assertEqual(again['records'],[]);self.assertEqual(again['already_synced'],1)
  # A second device's stale review cannot overwrite a saved booking or photos.
  rows[0]['name']='덮어쓰면 안 됨';rows[0]['replace_cover']=True
  result=self.post('commit',{'records':rows});self.assertEqual(result.json['skipped'],1);self.assertEqual(result.json['photos_added'],0);self.assertEqual(self.client.get('/api/state').json['records'],before)
  changed=self.post('preview',self.capture(text=TEXT.replace('2026.10.09','2026.10.16'))).json;self.assertEqual(changed['records'],[])
  # A genuinely new reservation is kept, even if its stay precedes the last sync date.
  fresh=self.post('preview',self.capture(text=TEXT.replace('9744403','1234567').replace('2026.10.09','2025.05.02'))).json['records'];self.assertEqual(len(fresh),1);self.assertEqual(fresh[0]['checkin'],'2025-05-02')
  self.assertEqual(len(self.post('commit',{'records':fresh}).json['added']),1)
 def test_preview_cancel_and_failed_commit_never_mark_booking_as_synced(self):
  rows=self.post('preview',self.capture()).json['records'];self.assertEqual(self.client.get('/api/platforms/state').json['camfit']['booking_ids'],[])
  self.assertEqual(len(self.post('preview',self.capture()).json['records']),1)
  rows[0]['checkout']='';self.assertEqual(self.post('commit',{'records':rows}).status_code,400);self.assertIsNone(self.client.get('/api/platforms/state').json['camfit']['last_synced'])
 def test_no_number_history_survives_manual_edits_and_deletion(self):
  capture=self.capture(text=TEXT.replace('예약번호: 9744403',''))
  rows=self.post('preview',capture).json['records'];rows[0]['name']='사용자가 보완한 캠핑장';ident=self.post('commit',{'records':rows}).json['added'][0]
  result=self.post('preview',capture).json;self.assertEqual(result['records'],[]);self.assertEqual(result['already_synced'],1)
  self.client.delete('/api/records/'+ident,headers=self.headers)
  self.assertEqual(self.post('preview',capture).json['records'],[])
  with connection() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM platform_sync_history').fetchone()[0],1)
 def test_previous_version_source_reference_is_recognized_and_kept_on_edit(self):
  data={'name':'강촌 스칼라 캠프','checkin':'2026-10-09','checkout':'2026-10-11','platform_ref':{'provider':'camfit','booking_id':'9744403'}}
  with connection() as c:c.execute('INSERT INTO records VALUES(?,?)',('legacy',json.dumps(data)))
  self.assertEqual(self.client.get('/api/platforms/state').json['camfit']['booking_ids'],['9744403'])
  self.assertEqual(self.post('preview',self.capture()).json['records'],[])
  self.client.put('/api/records/legacy',json={**data,'name':'수정'},headers=self.headers)
  self.assertEqual(self.client.get('/api/state').json['records'][0]['platform_ref']['booking_id'],'9744403')
 def test_media_failures_and_duplicate_conflicts_roll_back_everything(self):
  rows=self.post('preview',self.capture(media=[{'kind':'gallery','data':photo('blue')}])).json['records'];files=set(MEDIA.iterdir())
  with patch('pathlib.Path.write_bytes',side_effect=OSError('disk failure')),self.assertLogs(app.logger,level='ERROR'):
   self.assertEqual(self.post('commit',{'records':rows}).status_code,500)
  self.assertEqual(self.client.get('/api/state').json['records'],[]);self.assertEqual(set(MEDIA.iterdir()),files)
  self.assertIsNone(self.client.get('/api/platforms/state').json['camfit']['last_synced'])
  rows[0]['sync_media'][0]['data']='data:image/jpeg;base64,garbage';self.assertEqual(self.post('commit',{'records':rows}).status_code,400)
  self.assertEqual(self.post('preview',self.capture(media=[{'kind':'layout','data':'https://private/image'}])).status_code,400)
 def test_ambiguous_combined_page_never_assigns_a_photo_to_multiple_bookings(self):
  text='별 캠핑장\nA-1\n26.10.01-26.10.03\n달 캠핑장\nB-1\n26.10.04-26.10.05'
  rows=self.post('preview',self.capture(text=text,media=[{'kind':'gallery','data':photo('blue')}])).json['records'];self.assertEqual(len(rows),2);self.assertTrue(all(not r['sync_media'] for r in rows))

 def test_mixed_cancelled_bookings_remain_visible_but_cannot_be_committed(self):
  capture={'provider':'camfit','cards':[{'text':TEXT,'media':[]},{'text':TEXT.replace('9744403','9999999')+'\n취소 완료','media':[]}]}
  result=self.post('preview',capture).json;self.assertEqual(len(result['records']),2);self.assertEqual(result['cancelled_count'],1)
  self.assertEqual(self.post('commit',{'records':result['records']}).status_code,400);self.assertEqual(self.client.get('/api/state').json['records'],[])
  self.assertEqual(len(self.post('commit',{'records':[result['records'][0]]}).json['added']),1)
  again=self.post('preview',capture).json;self.assertEqual(len(again['records']),1);self.assertTrue(again['records'][0]['cancelled']);self.assertEqual(again['already_synced'],1)
  flagged=self.capture(text=TEXT.replace('9744403','8888888'));flagged['cards'][0]['cancelled']=True
  self.assertTrue(self.post('preview',flagged).json['records'][0]['cancelled'])
 def test_scan_range_limit_is_reported_and_empty_cancelled_cards_are_visible(self):
  raw=self.capture();raw.update(scan_truncated=True,scan_reason='time');self.assertTrue(self.post('preview',raw).json['scan_truncated'])
  rows=self.post('preview',self.capture(text='취소 완료')).json['records'];self.assertEqual(len(rows),1);self.assertTrue(rows[0]['cancelled']);self.assertEqual(self.post('commit',{'records':rows}).status_code,400)

 def test_two_account_checkpoints_and_naver_are_supported(self):
  for account,number,name in [(1,'1111111','첫 캠핑장'),(2,'2222222','둘 캠핑장')]:
   capture=self.capture(provider='naver',text=TEXT.replace('9744403',number).replace('강촌 스칼라 캠프',name));capture['account']=account
   rows=self.post('preview',capture).json['records'];self.assertEqual(rows[0]['platform_sync']['account'],account);self.assertEqual(rows[0]['platform'],'네이버');self.assertEqual(len(self.post('commit',{'records':rows}).json['added']),1)
  states=self.client.get('/api/platforms/state').json['naver']['accounts'];self.assertEqual(states['1']['booking_ids'],['1111111']);self.assertEqual(states['2']['booking_ids'],['2222222']);self.assertTrue(states['1']['last_synced']);self.assertTrue(states['2']['last_synced'])
  bad=self.capture();bad['account']=3;self.assertEqual(self.post('preview',bad).status_code,400)

 def test_account_names_are_shared_without_changing_checkpoint_or_records(self):
  before=self.client.get('/api/state').json['records'];request={'provider':'naver','account':2,'label':'가족 계정'}
  response=self.client.post('/api/platforms/accounts/label',json=request,headers=self.headers);self.assertEqual(response.status_code,200)
  state=self.client.get('/api/platforms/state').json['naver']['accounts'];self.assertEqual(state['2']['label'],'가족 계정');self.assertEqual(state['1']['label'],'계정 1');self.assertIsNone(state['2']['last_synced']);self.assertEqual(self.client.get('/api/state').json['records'],before)
  request['label']='';self.assertEqual(self.client.post('/api/platforms/accounts/label',json=request,headers=self.headers).json['label'],'계정 2')
  request['label']='x'*31;self.assertEqual(self.client.post('/api/platforms/accounts/label',json=request,headers=self.headers).status_code,400)
