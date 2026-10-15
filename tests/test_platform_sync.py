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
  with connection() as c:c.execute('DELETE FROM records');c.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(DEFAULTS),))
 def capture(self,provider='camfit',text=TEXT,media=None):return {'provider':provider,'cards':[{'text':text,'media':media or []}]}
 def post(self,path,data):return self.client.post('/api/platforms/'+path,json=data,headers=self.headers)
 def test_preview_is_read_only_preserves_source_cards_and_skips_only_cancelled_states(self):
  for provider in PROVIDERS:
   result=self.post('preview',self.capture(provider));self.assertEqual(result.status_code,200);row=result.json['records'][0];self.assertEqual(row['name'],'강촌 스칼라 캠프');self.assertEqual(row['platform'],PROVIDERS[provider]);self.assertEqual(row['platform_sync']['booking_id'],'9744403');self.assertEqual(row['checkout'],'2026-10-11')
  self.assertEqual(self.client.get('/api/state').json['records'],[])
  self.assertEqual(self.post('preview',self.capture(text=TEXT+'\n취소 완료')).json['cancelled_skipped'],1)
  self.assertEqual(self.post('preview',self.capture(provider='unknown')).status_code,400)
  self.assertEqual(self.client.post('/api/platforms/commit',json={'records':[]}).status_code,403)
 def test_explicit_commit_updates_by_booking_number_and_deduplicates_photos(self):
  capture=self.capture(media=[{'kind':'gallery','data':photo('blue')},{'kind':'layout','data':photo('green')}])
  rows=self.post('preview',capture).json['records'];self.assertEqual(len(rows[0]['sync_media']),2)
  result=self.post('commit',{'records':rows});self.assertEqual(result.status_code,200);self.assertEqual(len(result.json['added']),1);self.assertEqual(result.json['photos_added'],2)
  before=self.client.get('/api/state').json['records'][0];ident=before['id'];self.assertEqual(sum(p['is_cover'] for p in before['photos']),1)
  self.assertEqual(self.post('commit',{'records':rows}).json['photos_added'],0)
  with connection() as c:
   body=json.loads(c.execute('SELECT body FROM records WHERE id=?',(ident,)).fetchone()[0]);body['notes']='개인 메모';body['rating']=4;c.execute('UPDATE records SET body=? WHERE id=?',(json.dumps(body),ident))
  moved=self.post('preview',self.capture(text=TEXT.replace('2026.10.09','2026.10.16'))).json['records'];self.assertEqual(moved[0]['sync_existing'],ident)
  result=self.post('commit',{'records':moved});self.assertEqual(result.status_code,200);self.assertEqual(result.json['added'],[]);self.assertEqual(result.json['updated'],[ident])
  after=self.client.get('/api/state').json['records'][0];self.assertEqual(after['checkin'],'2026-10-16');self.assertEqual(after['notes'],'개인 메모');self.assertEqual(after['rating'],4);self.assertEqual(len(after['photos']),2)
  # Normal editing and photo-form editing preserve the source reference too.
  self.client.put('/api/records/'+ident,json={'name':after['name'],'checkin':after['checkin'],'checkout':after['checkout']},headers=self.headers)
  self.assertEqual(self.client.get('/api/state').json['records'][0]['platform_ref']['booking_id'],'9744403')
 def test_existing_cover_is_kept_unless_explicitly_replaced(self):
  rows=self.post('preview',self.capture(media=[{'kind':'gallery','data':photo('blue')}])).json['records'];self.post('commit',{'records':rows});first=self.client.get('/api/state').json['records'][0];cover=first['photos'][0]['id']
  rows=self.post('preview',self.capture(media=[{'kind':'gallery','data':photo('red')}])).json['records'];self.post('commit',{'records':rows});after=self.client.get('/api/state').json['records'][0];self.assertEqual(next(p['id'] for p in after['photos'] if p['is_cover']),cover)
  rows[0]['replace_cover']=True;result=self.post('commit',{'records':rows});self.assertEqual(result.json['photos_added'],0);self.assertNotEqual(next(p['id'] for p in self.client.get('/api/state').json['records'][0]['photos'] if p['is_cover']),cover)
 def test_legacy_first_photo_remains_representative_without_cover_flag(self):
  rows=self.post('preview',self.capture(media=[{'kind':'gallery','data':photo('blue')}])).json['records'];self.post('commit',{'records':rows})
  with connection() as c:c.execute('UPDATE photos SET is_cover=0')
  rows=self.post('preview',self.capture(media=[{'kind':'gallery','data':photo('red')}])).json['records'];self.post('commit',{'records':rows})
  after=self.client.get('/api/state').json['records'][0];self.assertEqual(len(after['photos']),2);self.assertFalse(any(p['is_cover'] for p in after['photos']))
 def test_media_failures_and_duplicate_conflicts_roll_back_everything(self):
  rows=self.post('preview',self.capture(media=[{'kind':'gallery','data':photo('blue')}])).json['records'];files=set(MEDIA.iterdir())
  with patch('pathlib.Path.write_bytes',side_effect=OSError('disk failure')),self.assertLogs(app.logger,level='ERROR'):
   self.assertEqual(self.post('commit',{'records':rows}).status_code,500)
  self.assertEqual(self.client.get('/api/state').json['records'],[]);self.assertEqual(set(MEDIA.iterdir()),files)
  rows[0]['sync_media'][0]['data']='data:image/jpeg;base64,garbage';self.assertEqual(self.post('commit',{'records':rows}).status_code,400)
  self.assertEqual(self.post('preview',self.capture(media=[{'kind':'layout','data':'https://private/image'}])).status_code,400)
 def test_ambiguous_combined_page_never_assigns_a_photo_to_multiple_bookings(self):
  text='별 캠핑장\nA-1\n26.10.01-26.10.03\n달 캠핑장\nB-1\n26.10.04-26.10.05'
  rows=self.post('preview',self.capture(text=text,media=[{'kind':'gallery','data':photo('blue')}])).json['records'];self.assertEqual(len(rows),2);self.assertTrue(all(not r['sync_media'] for r in rows))
