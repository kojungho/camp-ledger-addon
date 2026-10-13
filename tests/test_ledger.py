import importlib.util, io, json, os, tempfile, unittest, zipfile
from pathlib import Path
from PIL import Image
from openpyxl import load_workbook

sandbox=tempfile.TemporaryDirectory()
os.environ['CAMP_DATA']=sandbox.name
os.environ.pop('HA_INGRESS',None)
spec=importlib.util.spec_from_file_location('ledger',Path(__file__).resolve().parents[1]/'camp_ledger/app.py')
ledger=importlib.util.module_from_spec(spec);spec.loader.exec_module(ledger)

class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.client=ledger.app.test_client()
        self.headers={'X-Camp-Request':'1'}
        with ledger.conn() as c:
            c.execute('DELETE FROM items')
            c.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(ledger.DEFAULT),))
    def image(self):
        b=io.BytesIO();Image.new('RGB',(32,24),'green').save(b,'PNG');b.seek(0);return b
    def item(self,**extra):
        return dict(category='텐트',name='캠핑 텐트',purchase_date='2026-10-01',method='온라인',buyer='나',purchase_price=300000,sale_price=150000,status='owned',sale_date='',disposal_date='',notes='영수증 보관',**extra)
    def save(self,item,ident=None,photos=0,deletes=None):
        data={'item':json.dumps(item),'delete_attachments':json.dumps(deletes or [])}
        if photos:data['photo_kinds']=json.dumps(['product' if n%2==0 else 'receipt' for n in range(photos)])
        if photos:data['photos']=[(self.image(),f'사진{n}.png') for n in range(photos)]
        return self.client.open('/api/items'+('/'+ident if ident else ''),method='PUT' if ident else 'POST',data=data,headers=self.headers)
    def state(self):return self.client.get('/api/state').get_json()
    def test_full_lifecycle_and_export(self):
        r=self.save(self.item(),photos=12);self.assertEqual(r.status_code,200)
        first=self.state()['items'][0];self.assertEqual(len(first['attachments']),12);self.assertEqual(sum(a['kind']=='receipt' for a in first['attachments']),6)
        changed={**first,'status':'sold','sale_date':'2026-10-13','sale_price':180000,'name':'=SUM(1,2)'}
        r=self.save(changed,first['id'],photos=1,deletes=[first['attachments'][0]['id']]);self.assertEqual(r.status_code,200)
        sold=self.state()['items'][0];self.assertEqual(len(sold['attachments']),12);self.assertEqual(len(sold['history']),2)
        self.assertEqual(self.client.get('/api/photos/'+first['attachments'][0]['id']).status_code,404)
        x=self.client.get('/api/export');self.assertEqual(x.status_code,200)
        wb=load_workbook(io.BytesIO(x.data));self.assertEqual(wb.sheetnames,['전체 상품','변경 이력','첨부 사진','설정','금액 집계'])
        self.assertEqual(wb['전체 상품']['C2'].value,"'=SUM(1,2)")
        self.assertEqual(len(wb['첨부 사진']._images),12)
        self.assertEqual(wb['금액 집계']['D3'].value,180000)
        self.assertEqual(wb['금액 집계']['E5'].value,120000)
        disposed={**sold,'status':'disposed','disposal_date':'2026-10-13'}
        self.assertEqual(self.save(disposed,sold['id']).status_code,200)
        wb=load_workbook(io.BytesIO(self.client.get('/api/export').data));self.assertEqual(wb['금액 집계']['D5'].value,0)
        backup=self.client.get('/api/backup').data
        r=self.client.post('/api/delete',json={'ids':[first['id']]},headers=self.headers);self.assertEqual(r.status_code,200);self.assertEqual(self.state()['items'],[])
        with ledger.conn() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM attachments').fetchone()[0],0)
        r=self.client.post('/api/restore',data={'backup':(io.BytesIO(backup),'backup.zip')},headers=self.headers)
        self.assertEqual(r.status_code,200);restored=self.state()['items'][0];self.assertEqual(restored['status'],'disposed');self.assertEqual(len(restored['attachments']),12)
        self.assertEqual(self.client.get('/api/photos/'+restored['attachments'][0]['id']).status_code,200)
    def test_validation_conflict_and_atomic_restore(self):
        bad={**self.item(),'purchase_price':-1};self.assertEqual(self.save(bad).status_code,400)
        r=self.save(self.item());self.assertEqual(r.status_code,200);first=self.state()['items'][0]
        self.assertEqual(self.save({**first,'notes':'수정'},first['id']).status_code,200)
        self.assertEqual(self.save(first,first['id']).status_code,409)
        r=self.client.post('/api/items',data={'item':json.dumps(self.item()),'photos':(io.BytesIO(b'fake'),'fake.png')},headers=self.headers);self.assertEqual(r.status_code,400)
        self.assertEqual(len(self.state()['items']),1)
        z=io.BytesIO()
        with zipfile.ZipFile(z,'w') as archive:archive.writestr('ledger.json',json.dumps({'version':1,'settings':ledger.DEFAULT,'items':[{'bad':1}]}))
        z.seek(0);self.assertEqual(self.client.post('/api/restore',data={'backup':(z,'bad.zip')},headers=self.headers).status_code,400)
        self.assertEqual(len(self.state()['items']),1)
    def test_settings_persistence_and_ingress(self):
        s=self.state()['settings'];s['categories'].remove('텐트');s['buyers'].append('캠퍼');s['display']['columns']['name']['font']=22
        self.save(self.item());r=self.client.put('/api/settings',json=s,headers=self.headers);self.assertEqual(r.status_code,200)
        self.assertEqual(self.state()['settings']['display']['columns']['name']['font'],22)
        self.assertEqual(self.state()['items'][0]['category'],'텐트')
        self.assertEqual(self.client.post('/api/delete',json={'ids':[]}).status_code,400)
        os.environ['HA_INGRESS']='1'
        try:
            self.assertEqual(self.client.get('/api/state').status_code,403)
            self.assertEqual(self.client.get('/api/state',environ_base={'REMOTE_ADDR':'172.30.32.2'}).status_code,200)
        finally:os.environ.pop('HA_INGRESS',None)

if __name__=='__main__':unittest.main()
