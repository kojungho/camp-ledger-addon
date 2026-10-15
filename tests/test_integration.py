import os,tempfile,unittest,io,zipfile,hashlib,json,sqlite3,sys
from pathlib import Path
from werkzeug.test import Client
from werkzeug.wrappers import Response
from test_ledger import ledger
sandbox_journal=tempfile.TemporaryDirectory();os.environ['JOURNAL_DATA']=sandbox_journal.name
from journal.app import app as journal,connection,DATA,MEDIA,DEFAULTS
from integrated import combined_app
class IntegrationTest(unittest.TestCase):
 def setUp(self):
  with connection() as c:
   c.execute('DELETE FROM records');c.execute('DELETE FROM devices');c.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(DEFAULTS),))
  self.client=ledger.app.test_client();self.headers={'X-Camp-Request':'1'}
 def archive(self):
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'journal.sqlite3'
   with connection() as source:
    source.execute('INSERT INTO records VALUES(?,?)',('visit',json.dumps({'name':'캠핑장','checkin':'2025-01-01','checkout':'2025-01-02'})))
    source.execute('INSERT INTO photos(id,record_id,kind,name,memo) VALUES(?,?,?,?,?)',('photo','visit','gallery','사진','메모'))
    source.execute('INSERT INTO devices VALUES(?,?,?,?,?)',('device','휴대폰','hash',1,None))
   with connection() as source:
    target=sqlite3.connect(path);source.backup(target);target.execute('ALTER TABLE photos DROP COLUMN is_cover');target.commit();target.close()
   values={'journal.sqlite3':path.read_bytes(),'photos/photo.jpg':b'image-bytes'}
   manifest={'counts':{'records':1,'photos':1,'devices':1},'sha256':{k:hashlib.sha256(v).hexdigest() for k,v in values.items()}}
   data=io.BytesIO()
   with zipfile.ZipFile(data,'w') as archive:
    for k,v in values.items():archive.writestr(k,v)
    archive.writestr('manifest.json',json.dumps(manifest))
   with connection() as c:c.execute('DELETE FROM records');c.execute('DELETE FROM devices')
   return data.getvalue()
 def test_migration_preserves_photos_memos_devices_and_refuses_overwrite(self):
  payload=self.archive();result=self.client.post('/api/integration/import-journal',data={'archive':(io.BytesIO(payload),'journal.zip')},headers=self.headers);self.assertEqual(result.status_code,200,result.json);self.assertEqual(result.json['counts'],{'records':1,'photos':1,'devices':1})
  with connection() as c:self.assertEqual(c.execute('SELECT memo FROM photos').fetchone()[0],'메모');self.assertEqual(c.execute('SELECT is_cover FROM photos').fetchone()[0],0);self.assertEqual(c.execute('SELECT token_hash FROM devices').fetchone()[0],'hash')
  self.assertEqual((MEDIA/'photo.jpg').read_bytes(),b'image-bytes')
  self.assertEqual(self.client.post('/api/integration/import-journal',data={'archive':(io.BytesIO(payload),'journal.zip')},headers=self.headers).status_code,400)
 def test_dispatch_hub_and_admin_isolation(self):
  client=Client(combined_app(ledger.app,'ingress'),Response)
  self.assertEqual(client.get('/journal/api/state').status_code,200)
  with client.get('/') as response:self.assertIn(b'journalFrame',response.data)
  with client.get('/?camp_hub=1') as response:self.assertNotIn(b'journalFrame',response.data)
  external=Client(combined_app(ledger.app,'external'),Response)
  self.assertEqual(external.get('/journal/api/state').status_code,401)
  self.assertEqual(external.post('/api/integration/import-journal',headers=self.headers).status_code,401)
 def test_bad_archive_does_not_change_data(self):
  result=self.client.post('/api/integration/import-journal',data={'archive':(io.BytesIO(b'not-a-zip'),'journal.zip')},headers=self.headers);self.assertEqual(result.status_code,400)
  with connection() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM records').fetchone()[0],0)
 def test_slow_ocr_does_not_block_other_devices_state_reads(self):
  import threading
  from unittest.mock import patch
  entered=threading.Event();release=threading.Event();finished=threading.Event();statuses=[]
  application=combined_app(ledger.app,'ingress')
  def recognize(_,**kwargs):
   entered.set();release.wait(5);text='캠핑장\n일정 26.10.01-26.10.03'
   from journal.reservation_import import parse_reservations
   return {'text':text,'records':parse_reservations(text)} if kwargs.get('with_records') else text
  def preview():statuses.append(Client(application,Response).post('/journal/api/import/preview',data={'image':(io.BytesIO(b'photo'),'image.png')},headers=self.headers).status_code)
  def state():statuses.append(Client(application,Response).get('/journal/api/state').status_code);finished.set()
  with patch('journal.reservation_import.image_text',side_effect=recognize):
   reader=threading.Thread(target=preview);reader.start();self.assertTrue(entered.wait(2));viewer=threading.Thread(target=state);viewer.start()
   try:self.assertTrue(finished.wait(2),'OCR must not hold the shared journal request lock')
   finally:release.set();reader.join(5);viewer.join(5)
  self.assertEqual(statuses,[200,200])
