import io,json,unittest
from unittest.mock import patch
from urllib.error import HTTPError
import test_journal
from journal import address_search
class AddressTest(unittest.TestCase):
 def test_auth_and_invalid_queries(self):
  r=test_journal.app.test_client().get('/api/addresses?q=x');self.assertEqual(r.status_code,400)
  r=test_journal.app.test_client().get('/api/addresses?q=분당구',environ_overrides={'journal.entrypoint':'external','SERVER_PORT':'8098'});self.assertEqual(r.status_code,401)
 def test_free_lookup_coordinates_and_persistent_cache(self):
  raw={'features':[{'geometry':{'coordinates':[127.105,37.359]},'properties':{'city':'성남시','street':'불정로','housenumber':'6'}}]}
  with patch('journal.address_search.urlopen',return_value=io.BytesIO(json.dumps(raw).encode())) as call:
   result,status=address_search.search('캐시검증 불정로 6');self.assertEqual(status,200);self.assertEqual(result['results'][0]['lat'],37.359);self.assertEqual(result['results'][0]['lng'],127.105)
   req=call.call_args.args[0];self.assertTrue(req.full_url.startswith('https://photon.komoot.io/'));self.assertIn('CampsiteJournal',req.get_header('User-agent'));self.assertNotIn('X-NCP',str(req.headers))
   again,status=address_search.search('캐시검증 불정로 6');self.assertEqual(again,result);self.assertEqual(call.call_count,1)
 def test_failure_offers_manual_map_selection(self):
  with patch('journal.address_search.urlopen',side_effect=HTTPError('https://photon.komoot.io/',503,'error',{},None)),patch('journal.address_search.time.sleep'):
   result,status=address_search.search('서비스실패 점검주소');self.assertEqual(status,502);self.assertIn('지도에서 직접',result['error'])
 def test_invalid_or_foreign_coordinate_is_not_suggested(self):
  raw={'features':[{'geometry':{'coordinates':[999,37]},'properties':{}},{'geometry':{'coordinates':[-73,40]},'properties':{}}]}
  with patch('journal.address_search.urlopen',return_value=io.BytesIO(json.dumps(raw).encode())),patch('journal.address_search.time.sleep'):
   result,status=address_search.search('잘못된 좌표 점검주소');self.assertEqual(result['results'],[])
