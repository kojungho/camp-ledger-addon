import io, json, os, sqlite3, uuid, zipfile
from datetime import date, datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_file, abort
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.drawing.image import Image as XLImage
from PIL import Image

app = Flask(__name__, static_folder='static')
app.config.update(MAX_FORM_PARTS=None, MAX_FORM_MEMORY_SIZE=None)
DATA = Path(os.environ.get('CAMP_DATA', '/data/camp-ledger'))
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / 'ledger.sqlite3'
DEFAULT = {'categories':['부품','텐트','의자','테이블','소모품','기타'], 'methods':['온라인','오프라인'], 'buyers':['나','가족'], 'display': {'rowHeight':72,'headerHeight':48,'cellPadding':20,'detailFont':15,'titleFont':32,'columns':{'category':{'font':14,'width':160},'name':{'font':16,'width':440},'purchase_price':{'font':16,'width':190},'sale_price':{'font':16,'width':190}}}}
FIELDS = {'category':'구분','name':'상품명','purchase_date':'구입일자','method':'구매방식','buyer':'구매자','purchase_price':'구입가격','sale_price':'판매가격','status':'상태','sale_date':'판매일자','disposal_date':'폐기일자','notes':'메모'}
STATUSES = {'owned':'보유','sold':'판매','disposed':'폐기'}

class ManagedConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try: return super().__exit__(*args)
        finally: self.close()

def conn():
    c = sqlite3.connect(DB, timeout=30, factory=ManagedConnection)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c
with conn() as c:
    c.executescript('CREATE TABLE IF NOT EXISTS items(id TEXT PRIMARY KEY, body TEXT NOT NULL); CREATE TABLE IF NOT EXISTS attachments(id TEXT PRIMARY KEY,item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,name TEXT NOT NULL,mime TEXT NOT NULL,data BLOB NOT NULL); CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY,body TEXT NOT NULL);')
    c.execute('INSERT OR IGNORE INTO settings VALUES(1,?)',(json.dumps(DEFAULT,ensure_ascii=False),))

def now(): return datetime.now().astimezone().isoformat(timespec='microseconds')
def settings(c): return json.loads(c.execute('SELECT body FROM settings WHERE id=1').fetchone()[0])
def get_item(c, ident):
    r=c.execute('SELECT body FROM items WHERE id=?',(ident,)).fetchone()
    if not r: abort(404, description='상품을 찾을 수 없습니다.')
    item=json.loads(r[0])
    item['attachments']=[dict(x) for x in c.execute('SELECT id,name,mime,length(data) AS size FROM attachments WHERE item_id=? ORDER BY rowid',(ident,))]
    return item

def valid_item(raw):
    obj={k:raw.get(k,'') for k in FIELDS}
    for k in FIELDS:
        if k not in ('purchase_price','sale_price') and not isinstance(obj[k],str): raise ValueError('입력 형식을 확인해주세요.')
    obj['name']=obj['name'].strip()
    if not obj['name']: raise ValueError('상품명을 입력해주세요.')
    if obj['status'] not in STATUSES: raise ValueError('상태를 확인해주세요.')
    for k in ('purchase_price','sale_price'):
        v=obj[k]
        if isinstance(v,bool) or not str(v).isdigit(): raise ValueError('금액은 0 이상의 정수로 입력해주세요.')
        obj[k]=int(v)
        if obj[k]>999999999999: raise ValueError('금액이 너무 큽니다.')
    for k in ('purchase_date','sale_date','disposal_date'):
        if obj[k]: date.fromisoformat(obj[k])
    return obj

def valid_settings(s):
    for key in ('categories','methods','buyers'):
        if not isinstance(s.get(key),list) or any(not isinstance(x,str) or not x.strip() for x in s[key]) or len(set(s[key]))!=len(s[key]): raise ValueError('목록 값을 확인해주세요.')
    d=s['display']
    limits={'rowHeight':(40,200),'headerHeight':(32,120),'cellPadding':(8,60),'detailFont':(12,30),'titleFont':(20,48)}
    for k,(low,high) in limits.items():
        if type(d.get(k)) is not int or not low<=d[k]<=high: raise ValueError('화면 크기 설정이 범위를 벗어났습니다.')
    for key in ('category','name','purchase_price','sale_price'):
        col=d['columns'][key]
        if type(col['font']) is not int or not 12<=col['font']<=30 or type(col['width']) is not int or not 90<=col['width']<=800: raise ValueError('열 설정을 확인해주세요.')
    return s

@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(413)
def http_error(e): return jsonify(error=e.description),e.code
@app.errorhandler(ValueError)
@app.errorhandler(KeyError)
@app.errorhandler(zipfile.BadZipFile)
def value_error(e): return jsonify(error=str(e) or '파일 또는 입력값을 확인해주세요.'),400

@app.before_request
def protect():
    # Production port is only exposed through the HA ingress network.
    if os.environ.get('HA_INGRESS')=='1' and request.remote_addr != '172.30.32.2': abort(403)
    if request.method in ('POST','PUT','DELETE') and request.headers.get('X-Camp-Request')!='1': abort(400,description='요청을 확인해주세요.')

@app.after_request
def headers(r):
    r.headers['X-Content-Type-Options']='nosniff'
    r.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; connect-src 'self'; object-src 'none'; base-uri 'self'"
    r.headers['Cache-Control']='no-store'
    return r

@app.get('/')
def index(): return app.send_static_file('index.html')
@app.get('/api/state')
def state():
    with conn() as c:
        c.execute('BEGIN')
        return jsonify(settings=settings(c),items=[get_item(c,x[0]) for x in c.execute('SELECT id FROM items ORDER BY rowid DESC').fetchall()])
@app.put('/api/settings')
def update_settings():
    s=valid_settings(request.get_json())
    with conn() as c: c.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(s,ensure_ascii=False),))
    return jsonify(ok=True)
@app.post('/api/items')
@app.put('/api/items/<ident>')
def save(ident=None):
    raw=json.loads(request.form.get('item','{}'))
    obj=valid_item(raw)
    delete_ids=json.loads(request.form.get('delete_attachments','[]'))
    if not isinstance(delete_ids,list) or any(not isinstance(x,str) for x in delete_ids): raise ValueError('첨부 목록을 확인해주세요.')
    uploads=[]
    for f in request.files.getlist('photos'):
        data=f.read()
        try:
            with Image.open(io.BytesIO(data)) as im:
                fmt=im.format
                im.verify()
            mime={'JPEG':'image/jpeg','PNG':'image/png','WEBP':'image/webp','GIF':'image/gif'}[fmt]
        except Exception: raise ValueError('사진은 JPG, PNG, WebP, GIF 형식으로 첨부해주세요.')
        uploads.append((str(uuid.uuid4()),Path(f.filename or '사진').name,mime,data))
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        old=get_item(c,ident) if ident else None
        if old and raw.get('updated_at')!=old['updated_at']: return jsonify(error='다른 화면에서 변경되었습니다. 목록을 새로 불러온 뒤 수정해주세요.'),409
        ident=ident or str(uuid.uuid4())
        history=old.get('history',[]) if old else []
        stamp=now()
        changes=[{'field':FIELDS[k],'before':old.get(k,''),'after':obj[k]} for k in FIELDS if old and old.get(k)!=obj[k]]
        if not old: changes=[{'field':'등록','before':'','after':obj['name']}]
        removed=[a['name'] for a in old['attachments'] if a['id'] in delete_ids] if old else []
        if uploads: changes.append({'field':'사진 추가','before':'','after':', '.join(u[1] for u in uploads)})
        if removed: changes.append({'field':'사진 삭제','before':', '.join(removed),'after':''})
        if changes: history.append({'at':stamp,'changes':changes})
        obj.update(id=ident,created_at=old['created_at'] if old else stamp,updated_at=stamp,history=history)
        c.execute('INSERT INTO items VALUES(?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',(ident,json.dumps(obj,ensure_ascii=False)))
        for aid in delete_ids: c.execute('DELETE FROM attachments WHERE id=? AND item_id=?',(aid,ident))
        for aid,name,mime,data in uploads: c.execute('INSERT INTO attachments VALUES(?,?,?,?,?)',(aid,ident,name,mime,data))
    return jsonify(ok=True,id=ident)
@app.post('/api/delete')
def delete():
    ids=request.get_json().get('ids',[])
    if not isinstance(ids,list) or any(not isinstance(x,str) for x in ids): raise ValueError('선택 항목을 확인해주세요.')
    with conn() as c:
        c.executemany('DELETE FROM items WHERE id=?',[(x,) for x in ids])
    return jsonify(ok=True)
@app.get('/api/photos/<ident>')
def photo(ident):
    with conn() as c: r=c.execute('SELECT name,mime,data FROM attachments WHERE id=?',(ident,)).fetchone()
    if not r: abort(404)
    return send_file(io.BytesIO(r['data']),mimetype=r['mime'],download_name=r['name'])

def excel_value(v):
    if isinstance(v,str) and v.startswith(('=','+','-','@')): return "'"+v
    return v
@app.get('/api/export')
def export():
    wb=Workbook(); ws=wb.active; ws.title='전체 상품'; hist=wb.create_sheet('변경 이력'); photos=wb.create_sheet('첨부 사진'); prefs=wb.create_sheet('설정'); summary=wb.create_sheet('금액 집계')
    ws.append(['ID']+list(FIELDS.values())+['사진 수','사진 파일명','등록 시각','수정 시각'])
    hist.append(['상품 ID','상품명','변경 시각','항목','변경 전','변경 후'])
    photos.append(['상품 ID','상품명','첨부 ID','파일명','형식','사진'])
    with conn() as c:
        c.execute('BEGIN')
        items=[get_item(c,r[0]) for r in c.execute('SELECT id FROM items ORDER BY rowid').fetchall()]
        for it in items:
            vals=[STATUSES[it[k]] if k=='status' else it[k] for k in FIELDS]
            ws.append([excel_value(v) for v in [it['id']]+vals+[len(it['attachments']),', '.join(a['name'] for a in it['attachments']),it['created_at'],it['updated_at']]])
            for event in it['history']:
                for ch in event['changes']: hist.append([excel_value(v) for v in [it['id'],it['name'],event['at'],ch['field'],ch['before'],ch['after']]])
            for a in c.execute('SELECT * FROM attachments WHERE item_id=?',(it['id'],)):
                photos.append([excel_value(v) for v in [it['id'],it['name'],a['id'],a['name'],a['mime']]])
                with Image.open(io.BytesIO(a['data'])) as im:
                    im.thumbnail((180,130)); buf=io.BytesIO(); im.convert('RGB').save(buf,'PNG'); buf.seek(0)
                xl=XLImage(buf); photos.add_image(xl,f'F{photos.max_row}'); photos.row_dimensions[photos.max_row].height=105
        prefs.append(['항목','값']); s=settings(c)
        for k in ('categories','methods','buyers'): prefs.append([{'categories':'구분','methods':'구매방식','buyers':'구매자'}[k],json.dumps(s[k],ensure_ascii=False)])
        prefs.append(['화면 설정',json.dumps(s['display'],ensure_ascii=False)])
    summary.append(['상태','수량','구입 합계','실제 판매 합계','순지출'])
    for status,label in list(STATUSES.items())+[('all','전체')]:
        group=[it for it in items if status=='all' or it['status']==status]
        p=sum(it['purchase_price'] for it in group); sale=sum(it['sale_price'] for it in group if it['status']=='sold')
        summary.append([label,len(group),p,sale,p-sale])
    for sheet in wb:
        sheet.freeze_panes='A2'; sheet.auto_filter.ref=sheet.dimensions
        for cell in sheet[1]: cell.fill=PatternFill('solid',fgColor='214F43'); cell.font=Font(color='FFFFFF',bold=True); cell.alignment=Alignment(vertical='center')
        sheet.row_dimensions[1].height=28
        for col in sheet.columns:
            key=col[0].column_letter; sheet.column_dimensions[key].width=min(55,max(15,max(len(str(cell.value or '')) for cell in col)+3))
        for row in sheet.iter_rows(min_row=2):
            for cell in row: cell.alignment=Alignment(vertical='center',wrap_text=True)
    for n in (6,7):
        for row in ws.iter_rows(min_row=2): row[n].number_format='#,##0"원"'
    photos.column_dimensions['F'].width=28
    buf=io.BytesIO(); wb.save(buf); buf.seek(0)
    return send_file(buf,as_attachment=True,download_name=f'캠핑용품_전체_{date.today()}.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
@app.get('/api/backup')
def backup():
    buf=io.BytesIO()
    with conn() as c, zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        c.execute('BEGIN')
        items=[get_item(c,r[0]) for r in c.execute('SELECT id FROM items').fetchall()]
        z.writestr('ledger.json',json.dumps({'version':1,'settings':settings(c),'items':items},ensure_ascii=False))
        for a in c.execute('SELECT id,data FROM attachments'): z.writestr('photos/'+a['id'],a['data'])
    buf.seek(0)
    return send_file(buf,as_attachment=True,download_name=f'캠핑용품_백업_{date.today()}.zip')
@app.post('/api/restore')
def restore():
    f=request.files.get('backup')
    if not f: raise ValueError('백업 파일을 선택해주세요.')
    rows=[]; ids=set(); aids=set()
    with zipfile.ZipFile(f.stream) as z:
        data=json.loads(z.read('ledger.json'))
        if data.get('version')!=1: raise ValueError('지원하지 않는 백업 버전입니다.')
        s=valid_settings(data['settings'])
        for raw in data['items']:
            it=valid_item(raw)
            ident=str(uuid.UUID(raw['id']))
            if ident in ids: raise ValueError('상품 ID가 중복되었습니다.')
            ids.add(ident)
            for k in ('created_at','updated_at'): datetime.fromisoformat(raw[k]); it[k]=raw[k]
            if not isinstance(raw['history'],list): raise ValueError('이력 형식을 확인해주세요.')
            for h in raw['history']:
                datetime.fromisoformat(h['at'])
                for ch in h['changes']:
                    if not isinstance(ch['field'],str) or not isinstance(ch['before'],(str,int)) or not isinstance(ch['after'],(str,int)): raise ValueError('이력 형식을 확인해주세요.')
            it.update(id=ident,history=raw['history']); attachments=[]
            for a in raw['attachments']:
                aid=str(uuid.UUID(a['id']))
                if aid in aids: raise ValueError('사진 ID가 중복되었습니다.')
                aids.add(aid); b=z.read('photos/'+aid)
                with Image.open(io.BytesIO(b)) as im:
                    mime={'JPEG':'image/jpeg','PNG':'image/png','WEBP':'image/webp','GIF':'image/gif'}.get(im.format); im.verify()
                if not mime: raise ValueError('지원하지 않는 사진 형식입니다.')
                attachments.append((aid,ident,Path(a['name']).name,mime,b))
            rows.append((it,attachments))
    with conn() as c:
        c.execute('DELETE FROM items')
        c.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(s,ensure_ascii=False),))
        for it,attachments in rows:
            c.execute('INSERT INTO items VALUES(?,?)',(it['id'],json.dumps(it,ensure_ascii=False)))
            c.executemany('INSERT INTO attachments VALUES(?,?,?,?,?)',attachments)
    return jsonify(ok=True)

if __name__=='__main__':
    from waitress import serve
    serve(app,host=os.environ.get('CAMP_HOST','0.0.0.0'),port=int(os.environ.get('PORT','8099')),threads=4,max_request_body_size=2**40)
