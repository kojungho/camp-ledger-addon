import unittest
from test_journal import app,connection,DEFAULTS
from journal.reservation_import import parse_reservations,identity
import json
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
