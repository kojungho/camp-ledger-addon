import unittest,json
from werkzeug.test import Client
from werkzeug.wrappers import Response
from test_ledger import ledger
from test_journal import app as journal,connection,DEFAULTS
from integrated import combined_app
class UnifiedAccessTest(unittest.TestCase):
 def setUp(self):
  for connect,defaults in [(connection,DEFAULTS),(ledger.conn,ledger.DEFAULT)]:
   with connect() as c:c.execute('DELETE FROM devices');c.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(defaults),))
  self.admin=Client(combined_app(ledger.app,'ingress'),Response);self.external=Client(combined_app(ledger.app,'external'),Response,use_cookies=False);self.h={'X-Camp-Request':'1'}
  self.assertEqual(self.admin.put('/journal/api/mobile/config',json={'enabled':True,'external_url':'https://ha.test/campsite-journal/'},headers=self.h).status_code,200)
 def key(self,path='/journal'):
  response=self.admin.post(path+'/api/mobile/devices',json={'name':'테스트 기기','platform':'android'},headers=self.h);self.assertEqual(response.status_code,200);return response.json
 def test_one_key_opens_both_stores_without_admin_rights(self):
  key=self.key()['token'];h={'Authorization':'Bearer '+key}
  for path in ['/journal/api/state','/api/state']:self.assertEqual(self.external.get(path,headers=h).status_code,200)
  self.assertEqual(self.external.put('/api/mobile/config',json={'enabled':False,'external_url':''},headers={**h,**self.h}).status_code,403)
  response=self.external.post('/journal/api/mobile/session',json={},headers={**self.h,'Cookie':'campsite_device='+key});self.assertEqual(response.status_code,200)
  cookies=response.headers.getlist('Set-Cookie');self.assertTrue(any('camp_device=' in c and 'Path=/camp-ledger/' in c for c in cookies));self.assertEqual(len(cookies),1);own=self.external.post('/journal/api/mobile/session',json={'key':key},headers=self.h);self.assertTrue(any('campsite_device=' in c and 'Path=/campsite-journal/' in c for c in own.headers.getlist('Set-Cookie')));self.assertTrue(all('Secure' in c and 'HttpOnly' in c and 'SameSite=Strict' in c for c in cookies))
 def test_legacy_ledger_key_can_bootstrap_and_be_revoked_centrally(self):
  old=self.key('');key=old['token'];response=self.external.post('/journal/api/mobile/session',json={},headers={**self.h,'Cookie':'campsite_device='+key});self.assertEqual(response.status_code,200)
  devices=self.admin.get('/journal/api/mobile/status').json['devices'];ident=next(d['id'] for d in devices if d['id'].endswith(old['id']));self.assertTrue(ident.startswith('peer:'))
  self.assertEqual(self.admin.post('/journal/api/mobile/devices/'+ident+'/revoke',json={},headers=self.h).status_code,200)
  for path in ['/journal/api/state','/api/state']:self.assertEqual(self.external.get(path,headers={'Authorization':'Bearer '+key}).status_code,401)
 def test_disabled_access_and_bad_keys_cannot_bootstrap(self):
  key=self.key()['token'];self.assertEqual(self.external.post('/journal/api/mobile/session',json={'key':'x'*43},headers=self.h).status_code,401)
  self.assertEqual(self.admin.put('/journal/api/mobile/config',json={'enabled':False,'external_url':'https://ha.test/campsite-journal/'},headers=self.h).status_code,200)
  for path in ['/journal/api/state','/api/state']:self.assertEqual(self.external.get(path,headers={'Authorization':'Bearer '+key}).status_code,401)
