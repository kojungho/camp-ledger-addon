import json,unittest
from test_journal import app,connection,MEDIA
class DuplicateTest(unittest.TestCase):
 def setUp(self):
  self.client=app.test_client();self.headers={'X-Camp-Request':'1'}
  with connection() as c:c.execute('DELETE FROM records')
  self.body={'name':'한강 캠핑장','checkin':'2026-11-01','checkout':'2026-11-03','site':'A1'}
  self.ident=self.client.post('/api/records',json=self.body,headers=self.headers).json['id']
 def test_create_clone_and_multipart_block_same_name_dates(self):
  duplicate={**self.body,'name':' 한강-캠핑장 ','site':'B2','platform':'다른 플랫폼'}
  self.assertEqual(self.client.post('/api/records',json=duplicate,headers=self.headers).status_code,409)
  self.assertEqual(self.client.post('/api/records',json={**duplicate,'clone_from':self.ident},headers=self.headers).status_code,409)
  files=set(MEDIA.iterdir());self.assertEqual(self.client.post('/api/records/save',data={'record':json.dumps({'fields':duplicate,'uploads':[],'keep':[]})},headers=self.headers).status_code,409);self.assertEqual(set(MEDIA.iterdir()),files)
  self.assertEqual(len(self.client.get('/api/state').json['records']),1)
  self.assertEqual(self.client.post('/api/records',json={**duplicate,'checkout':'2026-11-04'},headers=self.headers).status_code,201)
 def test_edit_keeps_self_and_rejects_conflicting_other(self):
  self.assertEqual(self.client.put('/api/records/'+self.ident,json=self.body,headers=self.headers).status_code,200)
  other=self.client.post('/api/records',json={**self.body,'name':'다른 캠핑장'},headers=self.headers).json['id']
  self.assertEqual(self.client.put('/api/records/'+other,json=self.body,headers=self.headers).status_code,409)
  self.assertEqual(self.client.post('/api/records/save',data={'record':json.dumps({'id':other,'fields':self.body})},headers=self.headers).status_code,409)
  self.assertEqual(self.client.post('/api/records/save',data={'record':json.dumps({'id':self.ident,'fields':self.body})},headers=self.headers).status_code,200)
 def test_bulk_excludes_existing_and_in_batch_duplicates(self):
  rows=[self.body,{**self.body,'name':'한강-캠핑장'},{**self.body,'name':'새 캠핑장'},{**self.body,'name':'새캠핑장'},{**self.body,'checkout':'2026-11-05'}]
  result=self.client.post('/api/import/commit',json={'records':rows},headers=self.headers);self.assertEqual(result.status_code,200);self.assertEqual(len(result.json['added']),2);self.assertEqual(result.json['skipped'],3)
