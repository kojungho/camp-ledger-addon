import unittest
from test_journal import app,connection,DEFAULTS
from journal.reservation_import import parse_reservations,identity
import json,io,base64
from PIL import Image
from journal.reservation_import import thumbnail_data,decode_thumbnail,thumbnail_boxes
from unittest.mock import patch
from journal.app import MEDIA
TEXT='''25.07.03 결제
예약번호 C20250703002378
이용완료
시즌온관광농원 캠핑장
B존-B02 · 2명
일정 25.07.05(토)-25.07.06(일)
로그 작성완료
25.05.07 결제
연천 평화강변 수목캠핑장
오토캠핑 사이트-48 선착순 · 2명
일정 25.06.06(금)-25.06.08(일)
포천 한탄강둘레길캠핑장
성인 2인-여우비 · 2명
일정 24.10.26(토)-24.10.28(월)'''
class ReservationTest(unittest.TestCase):
 def setUp(self):
  self.client=app.test_client();self.headers={'X-Camp-Request':'1'}
  with connection() as c:c.execute('DELETE FROM records');c.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(DEFAULTS),))
 def test_parse_dates_excludes_payment_and_deduplicates(self):
  rows=parse_reservations(TEXT+'\n'+TEXT);self.assertEqual(len(rows),3);self.assertEqual(rows[1]['name'],'연천 평화강변 수목캠핑장');self.assertEqual(rows[0]['checkin'],'2025-07-05');self.assertEqual(rows[0]['site'],'B존-B02');self.assertEqual(rows[2]['checkout'],'2024-10-28');self.assertEqual(parse_reservations('포천 한탄강둘레길캠핑장\n일정 2410.26(토)-2410.28(월)')[0]['checkout'],'2024-10-28');self.assertEqual(parse_reservations('캠핑장\n일정 25.02.30-25.03.01'),[])
  self.assertEqual(identity({'name':'연천 평화강변 수목캠핑장'}),identity({'name':'연천평화강변수목캠핑장'}))
 def test_review_and_atomic_duplicate_safe_commit(self):
  preview=self.client.post('/api/import/preview',json={'text':TEXT},headers=self.headers);self.assertEqual(preview.status_code,200);self.assertTrue(all(not r['duplicate'] for r in preview.json['records']))
  rows=preview.json['records'];result=self.client.post('/api/import/commit',json={'records':rows},headers=self.headers);self.assertEqual(len(result.json['added']),3)
  result=self.client.post('/api/import/commit',json={'records':rows},headers=self.headers);self.assertEqual(result.json['skipped'],3)
  self.assertTrue(all(r['duplicate'] for r in self.client.post('/api/import/preview',json={'text':TEXT},headers=self.headers).json['records']))
  response=self.client.post('/api/import/commit',json={'records':[{'name':'새 기록','checkin':'2027-01-01','checkout':'2027-01-02'},{'name':''}]},headers=self.headers);self.assertEqual(response.status_code,400);self.assertEqual(len(self.client.get('/api/state').json['records']),3)
 def test_custom_labels_validation_and_legacy_save(self):
  settings=self.client.get('/api/state').json['settings'];settings['field_labels']={'site':'자리','nights':'여행 기간'}
  self.assertEqual(self.client.put('/api/settings',json=settings,headers=self.headers).status_code,200);self.assertEqual(self.client.get('/api/state').json['settings']['field_labels']['site'],'자리')
  settings.pop('field_labels');self.client.put('/api/settings',json=settings,headers=self.headers);self.assertEqual(self.client.get('/api/state').json['settings']['field_labels']['site'],'자리')
  settings['field_labels']={'id':'잘못된항목'};self.assertEqual(self.client.put('/api/settings',json=settings,headers=self.headers).status_code,400)

 def test_start_date_nights_platform_format(self):
  text='강촌 스칼라 캠프\n예약번호 : 9744403\n예약일 : 2026.10.09 (2박3일)\n예약정보 : G 존 / G 3\n재예약\n강촌 스칼라 캠프\n예약번호 : 8499602\n예약일 : 2025.05.02 (2박3일)\n예약정보 : D2 존 / D 2-2\n엘모르캠핑파크\n예약일 : 2025.04.26 (1박2일)\n예약정보 : F 패밀리존(1~11) / 3'
  rows=parse_reservations(text);self.assertEqual(len(rows),3);self.assertEqual(rows[0]['checkout'],'2026-10-11');self.assertEqual(rows[1]['checkout'],'2025-05-04');self.assertEqual(rows[2]['checkout'],'2025-04-27');self.assertEqual(rows[0]['site'],'G 존 / G 3')
 def test_thumbnail_commit_duplicate_skip_and_failure_rollback(self):
  thumb=thumbnail_data(Image.new('RGB',(200,200),'blue'),(0,0,200,200));row={'name':'사진 캠핑장','checkin':'2026-12-01','checkout':'2026-12-03','thumbnail':thumb}
  response=self.client.post('/api/import/commit',json={'records':[row,row]},headers=self.headers);self.assertEqual(response.status_code,200);self.assertEqual(response.json['skipped'],1)
  record=self.client.get('/api/state').json['records'][0];self.assertEqual(len(record['photos']),1);self.assertEqual(record['photos'][0]['is_cover'],1)
  with Image.open(MEDIA/(record['photos'][0]['id']+'.jpg')) as photo:self.assertEqual(photo.size,(200,200));self.assertGreater(photo.getpixel((80,80))[2],200)
  files=set(MEDIA.iterdir());self.assertEqual(self.client.post('/api/import/commit',json={'records':[row]},headers=self.headers).json['skipped'],1);self.assertEqual(set(MEDIA.iterdir()),files)
  bad={**row,'name':'실패 캠핑장'}
  with patch('pathlib.Path.write_bytes',side_effect=OSError('disk failure')),self.assertLogs(app.logger,level='ERROR'):
   self.assertEqual(self.client.post('/api/import/commit',json={'records':[bad]},headers=self.headers).status_code,500)
  self.assertEqual(len(self.client.get('/api/state').json['records']),1);self.assertEqual(set(MEDIA.iterdir()),files)
  self.assertEqual(self.client.post('/api/import/commit',json={'records':[{**bad,'thumbnail':'data:image/jpeg;base64,invalid'}]},headers=self.headers).status_code,400)
 def test_rating_columns_upgrade_independent_visibility_size_order(self):
  settings=self.client.get('/api/state').json['settings']
  for mode in ('desktop','display_mobile'):
   settings[mode]['order'].remove('rating');settings[mode]['order'].insert(0,'rating')
  settings['desktop']['visible']['rating']=False;settings['display_mobile']['visible']['rating']=True;settings['desktop']['rating_size']=12;settings['display_mobile']['rating_size']=24;settings['display_mobile']['rating_spacing']=0
  self.assertEqual(self.client.put('/api/settings',json=settings,headers=self.headers).status_code,200);result=self.client.get('/api/state').json['settings'];self.assertEqual(result['desktop']['order'][0],'rating');self.assertFalse(result['desktop']['visible']['rating']);self.assertEqual(result['display_mobile']['rating_size'],24);self.assertEqual(result['display_mobile']['rating_spacing'],0)
  settings['desktop']['rating_size']=60;self.assertEqual(self.client.put('/api/settings',json=settings,headers=self.headers).status_code,400)
 def test_separate_arrival_departure_columns(self):
  text='평창 가야지캠핑장\n*D구역/호수뷰 15*강자갈/차박O/애견O\n입실일        퇴실일\n26. 09. 24 (목)        26. 09. 26 (토)\n다시 예약하기'
  rows=parse_reservations(text);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['name'],'평창 가야지캠핑장');self.assertEqual(rows[0]['checkin'],'2026-09-24');self.assertEqual(rows[0]['checkout'],'2026-09-26');self.assertIn('호수뷰 15',rows[0]['site'])
  self.assertEqual(parse_reservations(text.replace('26. 09. 26','26. 09. 23')),[])
