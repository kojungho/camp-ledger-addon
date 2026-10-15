import json,unittest
from test_journal import app as journal,connection,DEFAULTS
from test_ledger import ledger
class ListPreferencesTest(unittest.TestCase):
 def setUp(self):
  with connection() as c:c.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(DEFAULTS),))
  with ledger.conn() as c:c.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(ledger.DEFAULT),))
  self.h={'X-Camp-Request':'1'}
 def test_journal_independent_views_blank_labels_placeholders_and_photo_size(self):
  client=journal.test_client();s=client.get('/api/state').json['settings'];s['desktop']['visible']['site']=False;s['display_mobile']['visible']['site']=True;s['display_mobile']['order']=s['display_mobile']['order'][::-1];s['field_labels']={'site':'','notes':'  '};s['empty_text']={'notes':'미기재','site':''};s['desktop']['photo_size']=120
  self.assertEqual(client.put('/api/settings',json=s,headers=self.h).status_code,200)
  saved=client.get('/api/state').json['settings'];self.assertFalse(saved['desktop']['visible']['site']);self.assertTrue(saved['display_mobile']['visible']['site']);self.assertNotEqual(saved['desktop']['order'],saved['display_mobile']['order']);self.assertEqual(saved['field_labels']['notes'],'  ');self.assertEqual(saved['field_labels']['site'],'');self.assertEqual(saved['empty_text']['site'],'');self.assertEqual(saved['desktop']['photo_size'],120)
  s['desktop']['photo_size']=201;self.assertEqual(client.put('/api/settings',json=s,headers=self.h).status_code,400)
  s['desktop']['photo_size']=120;s['empty_text']['photos']='x';self.assertEqual(client.put('/api/settings',json=s,headers=self.h).status_code,400)
 def test_journal_pc_row_height(self):
  client=journal.test_client();s=client.get('/api/state').json['settings'];self.assertEqual(s['desktop']['row_height'],0)
  s['desktop']['row_height']=86
  self.assertEqual(client.put('/api/settings',json=s,headers=self.h).status_code,200)
  self.assertEqual(client.get('/api/state').json['settings']['desktop']['row_height'],86)
  for invalid in [19,401,-1,True,'60']:
   s['desktop']['row_height']=invalid;self.assertEqual(client.put('/api/settings',json=s,headers=self.h).status_code,400)
  s['desktop']['row_height']=0;self.assertEqual(client.put('/api/settings',json=s,headers=self.h).status_code,200)
 def test_journal_scroll_positions_match_ledger(self):
  client=journal.test_client();s=client.get('/api/state').json['settings']
  for position in ('top-left','top-center','top-right','bottom-left','bottom-center','bottom-right'):
   s['scroll_top']=position;self.assertEqual(client.put('/api/settings',json=s,headers=self.h).status_code,200)
   self.assertEqual(client.get('/api/state').json['settings']['scroll_top'],position)
  for old,new in [('left-top','top-left'),('right-bottom','bottom-right'),('left-middle','bottom-left')]:
   s['scroll_top']=old;self.assertEqual(client.put('/api/settings',json=s,headers=self.h).status_code,200)
   self.assertEqual(client.get('/api/state').json['settings']['scroll_top'],new)
  s['scroll_top']='invalid';self.assertEqual(client.put('/api/settings',json=s,headers=self.h).status_code,400)
 def test_floating_add_positions(self):
  for module,key in [(journal,'add_position'),(ledger.app,'addButtonPosition')]:
   client=module.test_client();s=client.get('/api/state').json['settings'];target=s if key=='add_position' else s['display']
   self.assertEqual(target[key],'bottom-right')
   for position in ('top-left','top-center','top-right','bottom-left','bottom-center','bottom-right'):
    target[key]=position;self.assertEqual(client.put('/api/settings',json=s,headers=self.h).status_code,200)
    saved=client.get('/api/state').json['settings'];self.assertEqual((saved if key=='add_position' else saved['display'])[key],position)
   target[key]='invalid';self.assertEqual(client.put('/api/settings',json=s,headers=self.h).status_code,400)
 def test_ledger_selection_pc_mobile_independent(self):
  client=ledger.app.test_client();settings=client.get('/api/state').json['settings'];d=settings['display'];d['selectionPcEnabled']=True;d['selectionMobileEnabled']=False
  self.assertEqual(client.put('/api/settings',json=settings,headers=self.h).status_code,200)
  saved=client.get('/api/state').json['settings']['display'];self.assertTrue(saved['selectionPcEnabled']);self.assertFalse(saved['selectionMobileEnabled'])
  d['selectionPcEnabled']=False;d['selectionMobileEnabled']=True;self.assertEqual(client.put('/api/settings',json=settings,headers=self.h).status_code,200)
  saved=client.get('/api/state').json['settings']['display'];self.assertFalse(saved['selectionPcEnabled']);self.assertTrue(saved['selectionMobileEnabled'])
  d['selectionMobileEnabled']='false';self.assertEqual(client.put('/api/settings',json=settings,headers=self.h).status_code,400)
 def test_ledger_blank_labels_empty_text_selection_and_photo_size(self):
  client=ledger.app.test_client();s=client.get('/api/state').json['settings'];d=s['display'];d.update(fieldLabels={'name':'','buyer':'  '},emptyText={'notes':'없음','buyer':''},photoSize=100,selectionEnabled=False)
  self.assertEqual(client.put('/api/settings',json=s,headers=self.h).status_code,200)
  saved=client.get('/api/state').json['settings']['display'];self.assertEqual(saved['fieldLabels']['buyer'],'  ');self.assertEqual(saved['fieldLabels']['name'],'');self.assertEqual(saved['emptyText']['buyer'],'');self.assertFalse(saved['selectionEnabled']);self.assertEqual(saved['photoSize'],100)
  d['selectionEnabled']='false';self.assertEqual(client.put('/api/settings',json=s,headers=self.h).status_code,400)
  d['selectionEnabled']=False;d['emptyText']['photos']='x';self.assertEqual(client.put('/api/settings',json=s,headers=self.h).status_code,400)
