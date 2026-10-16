import io,subprocess,unittest
from unittest.mock import patch
from PIL import Image,ImageDraw
from werkzeug.datastructures import FileStorage
from journal.reservation_import import image_text,parse_reservations,thumbnail_boxes,current_year,review_records
TEXT='테스트 캠핑장\nA존-A01 · 2명\n일정 26.10.01(목)-26.10.03(토)'
class OcrPipelineTest(unittest.TestCase):
 def photo(self):
  stream=io.BytesIO();Image.new('RGB',(800,1000),'white').save(stream,'PNG');stream.seek(0);return FileStorage(stream=stream,filename='booking.png')
 def success(self,text=TEXT):return subprocess.CompletedProcess([],0,stdout=text,stderr='')
 @patch('journal.reservation_import.subprocess.run')
 def test_successful_text_column_skips_slow_whole_image_pass(self,run):
  run.return_value=self.success();self.assertEqual(parse_reservations(image_text(self.photo()))[0]['site'],'A존-A01');self.assertEqual(run.call_count,1);self.assertEqual(run.call_args.kwargs['env']['OMP_THREAD_LIMIT'],'1');self.assertLessEqual(run.call_args.kwargs['timeout'],40)
 @patch('journal.reservation_import.subprocess.run')
 def test_timeout_can_fall_back_and_releases_capacity(self,run):
  run.side_effect=[subprocess.TimeoutExpired('tesseract',40),self.success()];self.assertEqual(len(parse_reservations(image_text(self.photo()))),1)
  run.side_effect=[subprocess.TimeoutExpired('tesseract',40),subprocess.TimeoutExpired('tesseract',40)]
  with self.assertRaisesRegex(ValueError,'시간이 초과'):image_text(self.photo())
  run.side_effect=None;run.return_value=self.success();self.assertEqual(len(parse_reservations(image_text(self.photo()))),1)
 @patch('journal.reservation_import.subprocess.run')
 def test_full_image_fallback_for_other_layouts(self,run):
  run.side_effect=[self.success('글자 영역에 예약 없음'),self.success(TEXT)];self.assertEqual(len(parse_reservations(image_text(self.photo()))),1);self.assertEqual(run.call_count,2)
 @patch('journal.reservation_import.subprocess.run')
 def test_partial_results_survive_fallback_timeout(self,run):
  run.side_effect=[self.success(TEXT+'\n일정 26.11.01-26.11.03'),subprocess.TimeoutExpired('tesseract',40)];self.assertEqual(len(parse_reservations(image_text(self.photo()))),1);self.assertEqual(run.call_count,2)
 def test_name_noise_cleanup_preserves_numeric_names(self):
  self.assertEqual(parse_reservations('= '+TEXT)[0]['name'],'테스트 캠핑장')
  self.assertEqual(parse_reservations('365 '+TEXT)[0]['name'],'365 테스트 캠핑장')

 @patch('journal.reservation_import.subprocess.run')
 def test_card_crops_keep_correct_photos_and_skip_whole_screen(self,run):
  image=Image.new('RGB',(1000,2400),'white');draw=ImageDraw.Draw(image);draw.rectangle((0,0,999,90),fill='gray');draw.rectangle((0,2300,999,2399),fill='gray')
  for y,color in ((400,'blue'),(1000,'red'),(1600,'green')):draw.rectangle((60,y,260,y+200),fill=color)
  boxes=thumbnail_boxes(image);self.assertEqual(len(boxes),3)
  stream=io.BytesIO();image.save(stream,'PNG');stream.seek(0)
  run.side_effect=[self.success('캠핑장'+str(i)+'\n예약일 : 2026.10.0'+str(i+1)+' (2박3일)\n예약정보 : A'+str(i)) for i in range(3)]
  result=image_text(FileStorage(stream=stream,filename='cards.png'),with_records=True);self.assertEqual(run.call_count,3);self.assertEqual(len(result['records']),3);self.assertTrue(all(r['thumbnail'].startswith('data:image/jpeg;base64,') for r in result['records']))

 @patch('journal.reservation_import.subprocess.run')
 def test_visit_receipt_recovers_bad_date_from_focused_crop(self,run):
  from pathlib import Path
  receipt='산너미목장 > ee\n관광농원,팜스테이 · 강원 평창군 미탄면\n481025\n오전 12:00 · 1번째 방문\nAD\n살반 캠핑 에어텐트 펌프\n내역\n산너미 차박\n총 금액 110,000원'
  def recognize(args,**kwargs):
   if args[2]!='stdout':
    Path(args[2]+'.txt').write_text(receipt)
    Path(args[2]+'.tsv').write_text('level\tblock_num\tpar_num\tline_num\tleft\ttop\twidth\theight\ttext\n5\t1\t1\t1\t40\t870\t140\t25\t1 번 째 방 문\n')
    return self.success('')
   self.assertEqual(args[args.index('--psm')+1],'7');self.assertEqual(args[args.index('-l')+1],'kor')
   return self.success('4월 10일 금')
  run.side_effect=recognize
  stream=io.BytesIO();Image.new('RGB',(600,1280),'white').save(stream,'PNG');stream.seek(0)
  result=image_text(FileStorage(stream=stream,filename='visit.png'),with_records=True)
  self.assertEqual(run.call_count,2);row=result['records'][0]
  self.assertEqual((row['name'],row['site'],row['checkin'],row['checkout']),('산너미목장','산너미 차박',f'{current_year()}-04-10',''))
  self.assertEqual(row['location'],'강원 평창군 미탄면');self.assertEqual(row['price'],110000);self.assertNotIn('thumbnail',row)
  self.assertIn('방문일 재인식',result['text'])

 @patch('journal.reservation_import.subprocess.run')
 def test_visit_receipt_keeps_read_date_when_focused_pass_times_out(self,run):
  from pathlib import Path
  receipt='산너미목장 >\n강원 평창군 미탄면\n4월 10일 금\n오전 12:00 · 1번째 방문\n내역\n산너미 차박\n총 금액 110,000원'
  def recognize(args,**kwargs):
   if args[2]=='stdout':raise subprocess.TimeoutExpired('tesseract',8)
   Path(args[2]+'.txt').write_text(receipt)
   Path(args[2]+'.tsv').write_text('level\tblock_num\tpar_num\tline_num\tleft\ttop\twidth\theight\ttext\n5\t1\t1\t1\t40\t870\t140\t25\t1 번 째 방 문\n')
   return self.success('')
  run.side_effect=recognize
  stream=io.BytesIO();Image.new('RGB',(600,1280),'white').save(stream,'PNG');stream.seek(0)
  result=image_text(FileStorage(stream=stream,filename='visit.png'),with_records=True)
  self.assertEqual(run.call_count,2);self.assertEqual(result['records'][0]['checkin'],f'{current_year()}-04-10')
