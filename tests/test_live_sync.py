import unittest
import test_journal
from journal import live_sync
class LiveSyncTest(unittest.TestCase):
 def test_two_clients_receive_same_record_change(self):
  a=live_sync.events();b=live_sync.events();self.assertIn('event: ready',next(a));self.assertIn('event: ready',next(b))
  client=test_journal.app.test_client();r=client.post('/api/records',json={'name':'동기화 검증'},headers={'X-Camp-Request':'1'});self.assertEqual(r.status_code,201)
  first=next(a);second=next(b);self.assertEqual(first,second);self.assertIn('event: change',first);a.close();b.close()
  client.delete('/api/records/'+r.json['id'],headers={'X-Camp-Request':'1'})
 def test_stream_auth_and_proxy_headers(self):
  client=test_journal.app.test_client();outside={'journal.entrypoint':'external','SERVER_PORT':'8098'}
  self.assertEqual(client.get('/api/live',environ_overrides=outside).status_code,401)
  response=client.get('/api/live',buffered=False);self.assertEqual(response.mimetype,'text/event-stream');self.assertEqual(response.headers['X-Accel-Buffering'],'no');self.assertIn(b'event: ready',next(iter(response.response)));response.close()
 def test_failed_mutation_does_not_publish(self):
  before=live_sync.revision;client=test_journal.app.test_client();client.post('/api/records',json={'name':''},headers={'X-Camp-Request':'1'});self.assertEqual(live_sync.revision,before)
