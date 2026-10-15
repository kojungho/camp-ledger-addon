import json,unittest
from test_journal import app,connection,DEFAULTS
from journal.reservation_import import parse_reservation_text
TEXT='[Web발신]\n고중호님,빛_하늘존,2026-12-11,2박,완료!!쉼오지캠프'
class TextReservationTest(unittest.TestCase):
 def setUp(self):
  self.client=app.test_client();self.headers={'X-Camp-Request':'1'}
  with connection() as c:c.execute('DELETE FROM records');c.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(DEFAULTS),))
 def test_example_and_date_boundaries(self):
  row=parse_reservation_text(TEXT)[0];self.assertEqual(row,{'name':'쉼오지캠프','site':'빛_하늘존','checkin':'2026-12-11','checkout':'2026-12-13'})
  self.assertNotIn('고중호',str(row));self.assertEqual(parse_reservation_text(TEXT.replace('2026-12-11','2026-12-31'))[0]['checkout'],'2027-01-02');self.assertEqual(parse_reservation_text(TEXT.replace('2026-12-11','2028-02-28'))[0]['checkout'],'2028-03-01')
  self.assertEqual(parse_reservation_text(TEXT.replace('2026-12-11','2026-02-30')),[]);self.assertEqual(parse_reservation_text(TEXT.replace('2박','999박')),[]);self.assertEqual(parse_reservation_text('일반 문자 2026-12-11 2박'),[]);self.assertEqual(parse_reservation_text('예약취소 완료\n'+TEXT),[])
 def test_labelled_message_and_preview_no_save(self):
  text='캠핑장명: 별 캠핑장\n사이트: A-3\n입실일: 2026-12-30\n퇴실일: 2027-01-02\n결제금액: 120,000원\n캠핏'
  row=parse_reservation_text(text)[0];self.assertEqual(row['price'],120000);self.assertEqual(row['platform'],'캠핏');self.assertEqual(row['site'],'A-3');self.assertEqual(row['checkout'],'2027-01-02')
  result=self.client.post('/api/import/text-preview',json={'text':TEXT},headers=self.headers);self.assertEqual(result.status_code,200);self.assertFalse(result.json['records'][0]['duplicate']);self.assertEqual(self.client.get('/api/state').json['records'],[])
  self.client.post('/api/records',json=result.json['records'][0],headers=self.headers);self.assertTrue(self.client.post('/api/import/text-preview',json={'text':TEXT},headers=self.headers).json['records'][0]['duplicate']);self.assertEqual(self.client.post('/api/import/text-preview',json={'text':TEXT}).status_code,403);self.assertEqual(self.client.post('/api/import/text-preview',json={'text':'a'*10001},headers=self.headers).status_code,400)
 def test_click_and_duplicate_settings_are_independent(self):
  settings=self.client.get('/api/state').json['settings'];settings['duplicate_enabled']=False;settings['detail_duplicate_enabled']=True
  flags=settings['click_actions'];flags['list']['name']={'copy':True,'map':False};flags['list']['location']={'copy':False,'map':True};flags['detail']['name']={'copy':False,'map':False};flags['detail']['location']={'copy':True,'map':True}
  self.assertEqual(self.client.put('/api/settings',json=settings,headers=self.headers).status_code,200);saved=self.client.get('/api/state').json['settings'];self.assertFalse(saved['duplicate_enabled']);self.assertTrue(saved['detail_duplicate_enabled']);self.assertEqual(saved['click_actions'],flags)
  settings['detail_duplicate_enabled']='yes';self.assertEqual(self.client.put('/api/settings',json=settings,headers=self.headers).status_code,400);settings['detail_duplicate_enabled']=True;flags['list']['name']['copy']='true';self.assertEqual(self.client.put('/api/settings',json=settings,headers=self.headers).status_code,400)
 def test_duplicate_response_identifies_popup_error(self):
  row=parse_reservation_text(TEXT)[0];self.client.post('/api/records',json=row,headers=self.headers);r=self.client.post('/api/records',json=row,headers=self.headers);self.assertEqual(r.status_code,409);self.assertEqual(r.json['code'],'duplicate_record')
