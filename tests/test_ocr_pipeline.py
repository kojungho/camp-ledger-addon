import io,subprocess,unittest
from unittest.mock import patch
from PIL import Image
from werkzeug.datastructures import FileStorage
from journal.reservation_import import image_text,parse_reservations
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
