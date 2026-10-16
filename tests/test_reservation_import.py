import unittest
from test_journal import app,connection,DEFAULTS
from journal.reservation_import import parse_reservations,identity
import json,io,base64
from PIL import Image
from journal.reservation_import import thumbnail_data,decode_thumbnail,thumbnail_boxes,current_year,review_records
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
 def test_timeline_defaults_current_year_and_preserves_missing_departure(self):
  text='5.23 토\nmy 풍경소리캠핑장 * :\n캠핑,야영장ㆍ전북 정읍시 산내면\n오전 12:00ㆍ1번째 방문\n디 D4 (호수뷰,차박 불가)ㆍ140,000원\n다시 예약\n5.3 일\n= 하늘구니 더원 * :\n캠핑,야영장ㆍ대구 군위군 삼국유사면\n오전 12:00ㆍ1번째 방문\n티 3사이트 캠핑장ㆍ175,000원'
  rows=parse_reservations(text);self.assertEqual(len(rows),2);self.assertEqual(rows[0]['name'],'풍경소리캠핑장');self.assertEqual(rows[1]['name'],'하늘구니 더원');self.assertEqual(rows[0]['price'],140000);self.assertEqual(rows[1]['price'],175000);self.assertEqual(rows[0]['site'],'D4 (호수뷰,차박 불가)');self.assertEqual(rows[1]['location'],'대구 군위군 삼국유사면');self.assertEqual(rows[0]['date_hint'],'5.23 토');self.assertTrue(all(r['needs_dates'] and r['checkin'].startswith(str(current_year())+'-') and not r['checkout'] for r in rows))
  self.client.post('/api/records',json={'name':'풍경소리캠핑장'},headers=self.headers)
  preview=self.client.post('/api/import/preview',json={'text':text},headers=self.headers);self.assertFalse(preview.json['records'][0]['duplicate']);self.assertEqual(len(preview.json['records']),2)
  partial=self.client.post('/api/import/commit',json={'records':rows},headers=self.headers);self.assertEqual(partial.status_code,200);self.assertEqual(len(partial.json['added']),2)
  self.assertTrue(all(not r['checkout'] for r in self.client.get('/api/state').json['records']))
  repeated=self.client.post('/api/import/commit',json={'records':rows},headers=self.headers);self.assertEqual(repeated.json['skipped'],2)
  for row,dates in zip(rows,[('2026-05-23','2026-05-25'),('2026-05-03','2026-05-05')]):row.update(checkin=dates[0],checkout=dates[1])
  result=self.client.post('/api/import/commit',json={'records':rows},headers=self.headers);self.assertEqual(result.status_code,200);self.assertEqual(len(result.json['added']),2)
 def test_best_effort_fields_and_current_year_month_day(self):
  text='숙소명: 숲속 쉼터\n방문일: 5.23\n사이트: A-1\n위치: 경기 가평군\n금액: 120,000원'
  with patch('journal.reservation_import.current_year',return_value=2031):row=review_records(text)[0]
  self.assertEqual(row['name'],'숲속 쉼터');self.assertEqual(row['checkin'],'2031-05-23');self.assertEqual(row['checkout'],'');self.assertEqual(row['price'],120000);self.assertEqual(row['site'],'A-1');self.assertEqual(row['location'],'경기 가평군');self.assertTrue(row['year_assumed'])
  response=self.client.post('/api/import/preview',json={'text':'요금: 85,000원'},headers=self.headers);self.assertEqual(response.status_code,200);self.assertEqual(response.json['records'][0]['price'],85000);self.assertEqual(response.json['records'][0]['name'],'')
  original='<script>alert(1)</script>\n읽힌 글자 일부'
  response=self.client.post('/api/import/preview',json={'text':original},headers=self.headers);self.assertEqual(response.json['text'],original);self.assertEqual(response.json['records'],[])
 def test_partial_does_not_use_payment_date_as_stay(self):
  row=review_records('금액 100,000원\n결제일 2026-04-01')[0];self.assertEqual(row['checkin'],'');self.assertEqual(row['checkout'],'')
 def test_map_display_sizes_are_separate_and_validated(self):
  settings=self.client.get('/api/state').json['settings'];settings['desktop'].update(map_marker_size=64,map_label_size=18,map_button_size=16,map_label_gap=18);settings['display_mobile'].update(map_marker_size=24,map_label_size=10,map_button_size=9,map_label_gap=0)
  self.assertEqual(self.client.put('/api/settings',json=settings,headers=self.headers).status_code,200);result=self.client.get('/api/state').json['settings'];self.assertEqual(result['desktop']['map_marker_size'],64);self.assertEqual(result['display_mobile']['map_marker_size'],24);self.assertEqual(result['desktop']['map_button_size'],16);self.assertEqual(result['display_mobile']['map_label_size'],10);self.assertEqual(result['desktop']['map_label_gap'],18);self.assertEqual(result['display_mobile']['map_label_gap'],0)
  for key,value in [('map_marker_size',9),('map_label_size',7),('map_button_size',41),('map_label_gap',-1),('map_label_gap',81)]:
   bad=json.loads(json.dumps(settings));bad['desktop'][key]=value;self.assertEqual(self.client.put('/api/settings',json=bad,headers=self.headers).status_code,400)

 def test_noisy_timeline_is_cleaned_without_guessing_site_letters(self):
  text="""5.23 토
iy 풍경소리캠핑장                                 국 ：
캠핑,야영장ㆍ전북 정읍시 산내면
S) 오전 12:00ㆍ1번째 방문
트 04 (호수뷰,차박 불가) ㆍ140,000원
[nu] 다시 예약     Fa 예약 내역     OF 쓰기
5.3 일
니 하늘구니 더원                                  국 ：
캠핑,야영장ㆍ대구 군위군 삼국유사면
S) 오전 12:00ㆍ1번째 방문
EF) 3사이트캠핑장.ㆍ175,000원
[nm] 다시 예약                     ? 리뷰 쓰기
@ 지도보기 he               소"""
  response=self.client.post('/api/import/preview',json={'text':text},headers=self.headers)
  self.assertEqual(response.status_code,200);self.assertEqual(response.json['text'],text)
  a,b=response.json['records'];self.assertEqual(a['name'],'풍경소리캠핑장');self.assertEqual(b['name'],'하늘구니 더원')
  self.assertEqual(a['site'],'04 (호수뷰,차박 불가)');self.assertTrue(a['review_warnings']);self.assertEqual(b['site'],'3사이트캠핑장')
  self.assertEqual((a['price'],b['price']),(140000,175000));self.assertEqual(b['location'],'대구 군위군 삼국유사면')
  self.assertEqual((a['checkin'],b['checkin']),(f'{current_year()}-05-23',f'{current_year()}-05-03'))
  self.assertFalse(a['checkout']);self.assertNotIn('thumbnail',a)
 def test_partial_visit_without_price_is_kept(self):
  rows=review_records('5.23 토\n풍경소리캠핑장\n캠핑,야영장ㆍ전북 정읍시 산내면\n5.3 일\n하늘구니 더원\n캠핑,야영장ㆍ대구 군위군 삼국유사면')
  self.assertEqual(len(rows),2);self.assertNotIn('price',rows[0]);self.assertEqual(rows[1]['name'],'하늘구니 더원')
 def test_repeated_labelled_bookings_do_not_share_values(self):
  rows=review_records('숙소명: 숲속 쉼터\n방문일: 5.23\n사이트: A-1\n위치: 경기 가평군\n금액: 120,000원\n숙소명: 강가 쉼터\n방문일: 6.2\n사이트: B-2\n위치: 강원 홍천군\n금액: 80,000원')
  self.assertEqual(len(rows),2);self.assertEqual(rows[1]['name'],'강가 쉼터');self.assertEqual(rows[1]['price'],80000);self.assertEqual(rows[1]['site'],'B-2');self.assertEqual(rows[1]['location'],'강원 홍천군')
 def test_complete_cards_are_enriched_from_their_own_block(self):
  rows=review_records('별 캠핑장\n사이트 A-1\n일정 26.05.23-26.05.25\n주소: 경기 가평군\n금액: 120,000원\n달 캠핑장\n사이트 B-2\n일정 26.06.02-26.06.03\n주소: 강원 홍천군\n금액: 80,000원')
  self.assertEqual(len(rows),2);self.assertEqual(rows[0]['price'],120000);self.assertEqual(rows[1]['price'],80000);self.assertEqual(rows[1]['location'],'강원 홍천군')

 def test_korean_address_discards_isolated_latin_noise_but_keeps_building_labels(self):
  row=review_records('5.3 일\n하늘구니 더원\n캠핑,야영장ㆍ대구 군위군 ABO AH\n3사이트 캠핑장ㆍ175,000원')[0]
  self.assertEqual(row['location'],'대구 군위군');self.assertIn('주소',row['review_warnings'][0])
  from journal.reservation_import import clean_location
  self.assertEqual(clean_location('경기 가평군 가평읍 캠핑로 123 A동 ABC빌딩'),'경기 가평군 가평읍 캠핑로 123 A동 ABC빌딩')
  self.assertEqual(clean_location('123 Camping Road CA'),'123 Camping Road CA')

 def test_batch_inherits_only_matching_source_media_and_keeps_thumbnail_cover(self):
  source={'name':'같은 캠핑장','location':'경기 가평군','platform':'캠핏','booking_url':'https://camp.test','checkin':'2026-01-01','checkout':'2026-01-02'}
  sid=self.client.post('/api/records',json=source,headers=self.headers).json['id']
  for kind in ('gallery','layout'):
   photo=io.BytesIO();Image.new('RGB',(20,20),'green').save(photo,'PNG');photo.seek(0)
   self.client.post('/api/records/'+sid+'/photos/'+kind,data={'photos':(photo,kind+'.png')},headers=self.headers)
  original=self.client.get('/api/state').json['records'][0];original_files=set(MEDIA.iterdir())
  row={**source,'checkin':'2026-02-01','checkout':'2026-02-02','inherit_from':sid}
  result=self.client.post('/api/import/commit',json={'records':[row]},headers=self.headers);self.assertEqual(result.status_code,200)
  copied=self.client.get('/api/state').json['records'][0];self.assertEqual({p['kind'] for p in copied['photos']},{'layout','gallery'})
  self.assertEqual(sum(p['is_cover'] for p in copied['photos']),1);self.assertFalse({p['id'] for p in copied['photos']}&{p['id'] for p in original['photos']})
  row.update(checkin='2026-03-01',checkout='2026-03-02',thumbnail=thumbnail_data(Image.new('RGB',(20,20),'blue'),(0,0,20,20)))
  self.assertEqual(self.client.post('/api/import/commit',json={'records':[row]},headers=self.headers).status_code,200)
  record=self.client.get('/api/state').json['records'][0];self.assertEqual(len(record['photos']),3);self.assertEqual(sum(p['is_cover'] for p in record['photos']),1)
  self.assertTrue(next(p for p in record['photos'] if p['is_cover'])['name'].endswith('예약 사진.jpg'))
  before=self.client.get('/api/state').json['records'];files=set(MEDIA.iterdir());row.update(checkin='2026-04-01',checkout='2026-04-02',platform='네이버')
  self.assertEqual(self.client.post('/api/import/commit',json={'records':[row]},headers=self.headers).status_code,400)
  self.assertEqual(self.client.get('/api/state').json['records'],before);self.assertEqual(set(MEDIA.iterdir()),files)
  row.update(platform='캠핏',thumbnail=None)
  with patch('shutil.copyfile',side_effect=OSError('disk failure')),self.assertLogs(app.logger,level='ERROR'):
   self.assertEqual(self.client.post('/api/import/commit',json={'records':[row]},headers=self.headers).status_code,500)
  self.assertEqual(self.client.get('/api/state').json['records'],before);self.assertEqual(set(MEDIA.iterdir()),files);self.assertTrue(original_files<=files)

 def test_visit_receipt_fields_survive_unreadable_date_and_ad_noise(self):
  text='닫기 플랫폼 홈 현재 예약 동기화\n산너미목장 > ee\n관광농원,팜스테이 · 강원 평창군 미탄면\n481025\n오전 12:00 · 1번째 방문\n이 날 방문 어땠어요? 리뷰를 남겨보세요\nAD\n살반 캠핑 에어텐트 펌프\n내역\n산너미 차박\n총 금액 110,000원\n예약 내역'
  row=review_records(text)[0]
  self.assertEqual(row['name'],'산너미목장');self.assertEqual(row['site'],'산너미 차박');self.assertEqual(row['price'],110000)
  self.assertEqual(row['location'],'강원 평창군 미탄면');self.assertFalse(row['checkin']);self.assertFalse(row['checkout']);self.assertTrue(row['needs_dates'])
  row=review_records(text.replace('481025','4월 10일 금'))[0]
  self.assertEqual(row['checkin'],f'{current_year()}-04-10');self.assertTrue(row['year_assumed']);self.assertFalse(row['checkout'])

 def test_visit_receipt_special_handling_does_not_merge_two_receipts(self):
  from journal.reservation_import import parse_visit_receipt
  text='산너미목장\n4월 10일 금\n1번째 방문\n내역\n산너미 차박\n총 금액 110,000원'
  self.assertEqual(parse_visit_receipt(text+'\n'+text),[])
  self.assertEqual(parse_visit_receipt('일반 캠핑장\n일정 26.04.10-26.04.12'),[])
