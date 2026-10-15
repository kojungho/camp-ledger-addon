import unittest
import test_journal
from journal.campsite_search import search,CATALOG
class CampsiteSearchTest(unittest.TestCase):
 def test_exact_name_with_known_coordinates(self):
  sample=next(r for r in CATALOG['records'] if r['lat'] is not None)
  result,status=search(sample['name']);self.assertEqual(status,200);self.assertTrue(any(r['name']==sample['name'] and r['address']==sample['address'] and r['lat']==sample['lat'] for r in result['results']))
 def test_keyword_spaces_region_and_no_results(self):
  result,status=search('자라섬');self.assertEqual(status,200);self.assertTrue(result['results']);self.assertTrue(all('자라섬' in r['name'] or '자라섬' in r['address'] for r in result['results']))
  result,status=search('없는장소_설치검증_xyz');self.assertEqual(result['results'],[])
  result,status=search('');self.assertEqual(status,400)
 def test_addresses_and_coordinates_are_valid(self):
  for r in CATALOG['records']:
   self.assertTrue(r['name']);self.assertTrue(r['address'])
   if r['lat'] is not None:self.assertTrue(33<=r['lat']<=39 and 124<=r['lng']<=132)
 def test_private_endpoint(self):
  client=test_journal.app.test_client();self.assertEqual(client.get('/api/campsites?q=자라섬').status_code,200)
  self.assertEqual(client.get('/api/campsites?q=자라섬',environ_overrides={'journal.entrypoint':'external','SERVER_PORT':'8098'}).status_code,401)
