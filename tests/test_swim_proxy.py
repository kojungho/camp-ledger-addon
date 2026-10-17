import hashlib,json,threading,unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from http.client import HTTPConnection
from unittest.mock import patch,Mock
from werkzeug.test import Client
from werkzeug.wrappers import Response
from test_ledger import ledger
from mobile_access import channel_app

class Peer(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  if self.path=='/':body=b'<html><head><title>Reservation helper</title></head><body><script src="app.js"></script></body></html>';mime='text/html'
  elif self.path=='/styles.css':body=b'body{color:green}';mime='text/css'
  elif self.path=='/site-map.png':body=bytes(range(256));mime='image/png'
  elif self.path=='/redirect':self.send_response(302);self.send_header('Location','http://untrusted.invalid/');self.end_headers();return
  else:body=json.dumps({'path':self.path,'headers':dict(self.headers),'body':self.rfile.read(int(self.headers.get('Content-Length','0'))).decode()}).encode();mime='application/json'
  self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Set-Cookie','peer_session=must-not-leak');self.send_header('X-Peer-Secret','hidden');self.end_headers();self.wfile.write(body)
 do_POST=do_GET
 do_PUT=do_GET
 do_DELETE=do_GET

class SwimProxyTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.peer=ThreadingHTTPServer(('127.0.0.1',0),Peer);cls.thread=threading.Thread(target=cls.peer.serve_forever,daemon=True);cls.thread.start()
 @classmethod
 def tearDownClass(cls):cls.peer.shutdown();cls.peer.server_close();cls.thread.join()
 def setUp(self):
  self.client=ledger.app.test_client();self.headers={'X-Camp-Request':'1'};self.destinations=[]
  def connection(host,port,timeout):
   self.destinations.append((host,port));return HTTPConnection('127.0.0.1',self.peer.server_port,timeout=timeout)
  self.patch=patch('swim_proxy.http.client.HTTPConnection',side_effect=connection);self.patch.start();self.addCleanup(self.patch.stop)
 def test_html_assets_binary_queries_and_credential_isolation(self):
  self.client.set_cookie('camp_device','private-device');self.client.set_cookie('ha_cookie','private-ha')
  html=self.client.get('/swim/');self.assertEqual(html.status_code,200);self.assertIn(b'../static/swim-embed.js',html.data);self.assertIn(b'src="app.js"',html.data)
  self.assertNotIn('Set-Cookie',html.headers);self.assertNotIn('X-Peer-Secret',html.headers);self.assertIn("script-src 'self'",html.headers['Content-Security-Policy'])
  self.assertEqual(self.client.get('/swim/styles.css').data,b'body{color:green}');self.assertEqual(self.client.get('/swim/site-map.png').data,bytes(range(256)))
  response=self.client.put('/swim/api/echo?month=2026-10',data='{"value":42}',headers={**self.headers,'Authorization':'Bearer private-ha','Content-Type':'application/json'})
  self.assertEqual(response.status_code,200);data=response.json;self.assertEqual(data['path'],'/api/echo?month=2026-10');self.assertEqual(data['body'],'{"value":42}')
  self.assertFalse(any(k.lower() in ('authorization','cookie','x-camp-request') for k in data['headers']));self.assertEqual(set(self.destinations),{('76980dac-swim-reservation',8099)})
 def test_mutations_require_existing_csrf_header_and_paths_cannot_escape(self):
  self.assertEqual(self.client.post('/swim/api/echo',json={}).status_code,400);self.assertFalse(self.destinations)
  for path in ('/swim/%252e%252e/api/config','/swim/%255c%255cother','/swim/%252fother'):
   self.assertEqual(self.client.get(path).status_code,400)
  self.assertFalse(self.destinations);self.assertEqual(self.client.get('/swim/redirect').status_code,502)
 def test_external_access_requires_existing_enabled_device_key(self):
  with ledger.conn() as c:
   settings=json.loads(json.dumps(ledger.DEFAULT));settings['mobile']={'enabled':True,'external_url':'https://camp.test/camp-ledger/'};c.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(settings),));c.execute('DELETE FROM devices')
  external=Client(channel_app(ledger.app,'external'),Response)
  self.assertEqual(external.get('/swim/').status_code,401);self.assertEqual(external.get('/swim/api/config').status_code,401);self.assertFalse(self.destinations)
  key='A'*43
  with ledger.conn() as c:c.execute('INSERT INTO devices(id,name,token_hash,created,last_used) VALUES(?,?,?,?,?)',('swim-device','test',hashlib.sha256(key.encode()).hexdigest(),1,None))
  external.set_cookie('camp_device',key);self.assertEqual(external.get('/swim/').status_code,200)
  with ledger.conn() as c:c.execute('DELETE FROM devices WHERE id=?',('swim-device',))
  self.assertEqual(external.get('/swim/api/config').status_code,401)
 def test_unavailable_helper_shows_retry_without_exposing_internal_details(self):
  self.patch.stop();peer=Mock();peer.connect.side_effect=OSError('private host details')
  with patch('swim_proxy.http.client.HTTPConnection',return_value=peer):
   html=self.client.get('/swim/');self.assertEqual(html.status_code,503);self.assertIn('다시 시도',html.text);self.assertNotIn('private host',html.text)
   response=self.client.get('/swim/api/config');self.assertEqual(response.status_code,503);self.assertIn('error',response.json)
