import io, json, os, sqlite3, uuid, zipfile, time, math
from datetime import date, datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_file, abort
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.drawing.image import Image as XLImage
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.comments import Comment
from openpyxl.utils.exceptions import InvalidFileException
from PIL import Image

app = Flask(__name__, static_folder='static')
app.config.update(MAX_FORM_PARTS=None, MAX_FORM_MEMORY_SIZE=None)
DATA = Path(os.environ.get('CAMP_DATA', '/data/camp-ledger'))
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / 'ledger.sqlite3'
DEFAULT = {'categories':['부품','텐트','의자','테이블','소모품','기타'], 'methods':['온라인','오프라인'], 'buyers':['나','가족'], 'display': {'rowHeight':72,'headerHeight':48,'cellPadding':20,'detailFont':15,'titleFont':32,'columns':{'category':{'font':14,'width':130},'name':{'font':16,'width':360},'purchase_price':{'font':16,'width':165},'sale_price':{'font':16,'width':165}}}}
FIELDS = {'category':'구분','name':'상품명','purchase_date':'구입일자','method':'구매방식','buyer':'구매자','purchase_price':'구입가격','sale_price':'판매가격','status':'상태','sale_date':'판매일자','disposal_date':'폐기일자','notes':'메모'}
STATUSES = {'owned':'보유','sold':'판매','disposed':'폐기'}
DISPLAY_LABELS = {**FIELDS, 'photos':'사진'}
for key in DISPLAY_LABELS:
    DEFAULT['display']['columns'].setdefault(key, {'font':14,'width':320 if key=='notes' else 160})
DEFAULT['display'].update(visibleColumns=['category','name','purchase_price','sale_price'],
                          visibleSummaries=['purchase','sale','net','owned'],showProductThumb=True)

def normalize_settings(s):
    d=s.setdefault('display',{})
    for key in ('visibleColumns','visibleSummaries','showProductThumb'):
        if key not in d: d[key]=list(DEFAULT['display'][key]) if isinstance(DEFAULT['display'][key],list) else DEFAULT['display'][key]
    columns=d.setdefault('columns',{})
    for key,value in DEFAULT['display']['columns'].items():
        if key not in columns: columns[key]=dict(value)
    return s

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
    if 'kind' not in [r[1] for r in c.execute('PRAGMA table_info(attachments)')]:
        c.execute("ALTER TABLE attachments ADD COLUMN kind TEXT NOT NULL DEFAULT 'product'")
    c.execute('INSERT OR IGNORE INTO settings VALUES(1,?)',(json.dumps(DEFAULT,ensure_ascii=False),))
    c.execute('CREATE TABLE IF NOT EXISTS imports(id TEXT PRIMARY KEY, created REAL NOT NULL, payload TEXT NOT NULL, result TEXT)')

def now(): return datetime.now().astimezone().isoformat(timespec='microseconds')
def settings(c): return normalize_settings(json.loads(c.execute('SELECT body FROM settings WHERE id=1').fetchone()[0]))
def get_item(c, ident):
    r=c.execute('SELECT body FROM items WHERE id=?',(ident,)).fetchone()
    if not r: abort(404, description='상품을 찾을 수 없습니다.')
    item=json.loads(r[0])
    item['attachments']=[dict(x) for x in c.execute('SELECT id,name,mime,kind,length(data) AS size FROM attachments WHERE item_id=? ORDER BY rowid',(ident,))]
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
    s=normalize_settings(s)
    for key in ('categories','methods','buyers'):
        if not isinstance(s.get(key),list) or any(not isinstance(x,str) or not x.strip() for x in s[key]) or len(set(s[key]))!=len(s[key]): raise ValueError('목록 값을 확인해주세요.')
    d=s['display']
    limits={'rowHeight':(40,200),'headerHeight':(32,120),'cellPadding':(8,60),'detailFont':(12,30),'titleFont':(20,48)}
    for k,(low,high) in limits.items():
        if type(d.get(k)) is not int or not low<=d[k]<=high: raise ValueError('화면 크기 설정이 범위를 벗어났습니다.')
    for key in DISPLAY_LABELS:
        col=d['columns'][key]
        if type(col['font']) is not int or not 12<=col['font']<=30 or type(col['width']) is not int or not 90<=col['width']<=800: raise ValueError('열 설정을 확인해주세요.')
    for key,allowed in [('visibleColumns',DISPLAY_LABELS),('visibleSummaries',('purchase','sale','net','owned'))]:
        values=d[key]
        if not isinstance(values,list) or any(not isinstance(v,str) or v not in allowed for v in values) or len(set(values))!=len(values): raise ValueError('메인 화면 표시 항목을 확인해주세요.')
    if not d['visibleColumns']: raise ValueError('목록에 표시할 항목을 하나 이상 선택해주세요.')
    if type(d['showProductThumb']) is not bool: raise ValueError('대표 사진 표시 설정을 확인해주세요.')
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
    incoming=request.files.getlist('photos')
    kinds=json.loads(request.form.get('photo_kinds','[]'))
    if not kinds: kinds=['product']*len(incoming)
    if len(kinds)!=len(incoming) or any(k not in ('product','receipt') for k in kinds): raise ValueError('사진 종류를 확인해주세요.')
    for f,kind in zip(incoming,kinds):
        data=f.read()
        try:
            with Image.open(io.BytesIO(data)) as im:
                fmt=im.format
                im.verify()
            mime={'JPEG':'image/jpeg','PNG':'image/png','WEBP':'image/webp','GIF':'image/gif'}[fmt]
        except Exception: raise ValueError('사진은 JPG, PNG, WebP, GIF 형식으로 첨부해주세요.')
        uploads.append((str(uuid.uuid4()),Path(f.filename or '사진').name,mime,data,kind))
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
        for aid,name,mime,data,kind in uploads: c.execute('INSERT INTO attachments(id,item_id,name,mime,data,kind) VALUES(?,?,?,?,?,?)',(aid,ident,name,mime,data,kind))
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
    photos.append(['상품 ID','상품명','첨부 ID','파일명','형식','종류','사진'])
    with conn() as c:
        c.execute('BEGIN')
        items=[get_item(c,r[0]) for r in c.execute('SELECT id FROM items ORDER BY rowid').fetchall()]
        for it in items:
            vals=[STATUSES[it[k]] if k=='status' else it[k] for k in FIELDS]
            ws.append([excel_value(v) for v in [it['id']]+vals+[len(it['attachments']),', '.join(a['name'] for a in it['attachments']),it['created_at'],it['updated_at']]])
            for event in it['history']:
                for ch in event['changes']: hist.append([excel_value(v) for v in [it['id'],it['name'],event['at'],ch['field'],ch['before'],ch['after']]])
            for a in c.execute('SELECT * FROM attachments WHERE item_id=?',(it['id'],)):
                photos.append([excel_value(v) for v in [it['id'],it['name'],a['id'],a['name'],a['mime'],'영수증' if a['kind']=='receipt' else '상품 사진']])
                with Image.open(io.BytesIO(a['data'])) as im:
                    im.thumbnail((180,130)); buf=io.BytesIO(); im.convert('RGB').save(buf,'PNG'); buf.seek(0)
                xl=XLImage(buf); photos.add_image(xl,f'G{photos.max_row}'); photos.row_dimensions[photos.max_row].height=105
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
    photos.column_dimensions['G'].width=28
    buf=io.BytesIO(); wb.save(buf); buf.seek(0)
    return send_file(buf,as_attachment=True,download_name=f'캠핑용품_전체_{date.today()}.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.get('/api/import/template')
def import_template():
    with conn() as c: s=settings(c)
    wb=Workbook(); ws=wb.active; ws.title='용품 입력'
    ws.append(list(FIELDS.values()))
    ws.freeze_panes='C2'; ws.auto_filter.ref='A1:K101'; ws.sheet_view.showGridLines=False
    widths=[16,32,17,16,16,18,18,15,17,17,44]
    for col,width in zip('ABCDEFGHIJK',widths): ws.column_dimensions[col].width=width
    for cell in ws[1]:
        cell.fill=PatternFill('solid',fgColor='285345'); cell.font=Font(color='FFFFFF',bold=True,size=12)
        cell.alignment=Alignment(vertical='center'); cell.comment=Comment('필수 입력' if cell.value=='상품명' else '선택 입력. 날짜: YYYY-MM-DD / 금액: 원 단위 정수','CAMP LEDGER')
    ws.row_dimensions[1].height=32
    for row in ws.iter_rows(min_row=2,max_row=101,max_col=11):
        for cell in row:
            cell.font=Font(color='285345',size=11)
            cell.fill=PatternFill('solid',fgColor='F3F6EE' if cell.row%2==0 else 'FFFFFF')
            cell.alignment=Alignment(vertical='center',wrap_text=True)
            if cell.column in (3,9,10): cell.number_format='yyyy-mm-dd'
            elif cell.column in (6,7): cell.number_format='#,##0'
            else: cell.number_format='@'
        ws.row_dimensions[row[0].row].height=27
    lists=wb.create_sheet('목록'); lists.sheet_state='hidden'
    for col,key,named,target in [('A','categories','CampCategories','A'),('B','methods','CampMethods','D'),('C','buyers','CampBuyers','E'),('D',None,'CampStatus','H')]:
        values=s[key] if key else ['보유','판매','폐기']
        if not values: continue
        lists[f'{col}1']=key or 'status'
        for n,value in enumerate(values,2):
            lists[f'{col}{n}']=value; lists[f'{col}{n}'].data_type='s'
        wb.defined_names.add(DefinedName(named,attr_text=f"'목록'!${col}$2:${col}${len(values)+1}"))
        dv=DataValidation(type='list',formula1='='+named,allow_blank=True)
        dv.showErrorMessage=not bool(key); dv.errorTitle='상태를 확인해주세요'; dv.error='보유, 판매, 폐기 중에서 선택해주세요.'
        ws.add_data_validation(dv); dv.add(f'{target}2:{target}20001')
    for col in ('F','G'):
        dv=DataValidation(type='whole',operator='between',formula1=0,formula2=999999999999,allow_blank=True)
        dv.showErrorMessage=True; dv.error='금액은 0 이상의 원 단위 정수로 입력해주세요.'
        ws.add_data_validation(dv); dv.add(f'{col}2:{col}20001')
    guide=wb.create_sheet('작성 안내',1); guide.sheet_view.showGridLines=False
    guide.column_dimensions['A'].width=23; guide.column_dimensions['B'].width=95
    instructions=[('캠핑용품 엑셀 업로드','작성한 상품은 기존 장부에 새 항목으로 추가됩니다.'),
        ('작성 위치','용품 입력 시트의 2행부터 상품을 한 줄씩 작성하세요. 제목 행은 유지해주세요.'),
        ('필수 입력','상품명만 필수입니다. 빈 행은 건너뛰고, 예시는 업로드하지 않습니다.'),
        ('금액','원 단위 정수. 비워두면 0원으로 추가합니다. 예: 135000'),
        ('날짜','YYYY-MM-DD 또는 Excel 날짜. 예: 2026-10-13'),
        ('상태','보유 / 판매 / 폐기. 비워두면 보유로 추가됩니다.'),
        ('구분·구매방식·구매자','설정에 등록된 목록을 선택할 수 있습니다. 새 값을 직접 입력하면 목록에도 추가됩니다.'),
        ('업로드 순서','엑셀 업로드 → 파일 선택 → 내용 확인 → 추가하기'),
        ('입력 오류','오류가 있는 행을 수정한 후 다시 올려주세요. 오류가 있으면 어떤 상품도 추가하지 않습니다.'),
        ('반복 업로드','같은 파일을 다시 올리면 같은 상품도 새 항목으로 추가됩니다.'),
        ('사진','이 양식은 상품 정보를 입력합니다. 상품 사진·영수증은 업로드 후 상세 화면에서 첨부하세요.'),
        ('파일 형식','xlsx · 파일당 20,000개 상품 / 20MB까지'),
        ('예시','아래 예시는 작성 안내용이며 업로드 대상이 아닙니다.')]
    for row in instructions: guide.append(row)
    guide.append(['구분: 의자','상품명: 헬리녹스 체어원 / 구입일자: 2026-10-13 / 구매방식: 온라인 / 구매자: 나 / 구입가격: 135000 / 상태: 보유'])
    for row in guide:
        guide.row_dimensions[row[0].row].height=36
        for cell in row: cell.alignment=Alignment(vertical='center',wrap_text=True); cell.font=Font(color='52654F',size=11)
        row[0].font=Font(color='285345',bold=True,size=11)
    for cell in guide[1]: cell.fill=PatternFill('solid',fgColor='285345'); cell.font=Font(color='FFFFFF',bold=True,size=12)
    buf=io.BytesIO(); wb.save(buf); buf.seek(0)
    return send_file(buf,as_attachment=True,download_name='캠핑용품_업로드양식.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


def import_cell(cell,key):
    value=cell.value
    if value is None or isinstance(value,str) and not value.strip():
        return 0 if key in ('purchase_price','sale_price') else 'owned' if key=='status' else ''
    if cell.data_type in ('f','e'): raise ValueError('수식이나 Excel 오류 대신 값을 입력해주세요.')
    if key in ('purchase_price','sale_price'):
        if isinstance(value,bool): raise ValueError('금액은 0 이상의 정수로 입력해주세요.')
        if isinstance(value,str): value=value.strip().replace(',','').replace('₩','').removesuffix('원').strip()
        if isinstance(value,float):
            if not math.isfinite(value) or not value.is_integer(): raise ValueError('금액에 소수를 사용할 수 없습니다.')
            value=int(value)
        if not str(value).isdigit() or int(value)>999999999999: raise ValueError('금액은 0~999,999,999,999원의 정수로 입력해주세요.')
        return int(value)
    if key in ('purchase_date','sale_date','disposal_date'):
        if isinstance(value,datetime): return value.date().isoformat()
        if isinstance(value,date): return value.isoformat()
        if isinstance(value,str):
            text=value.strip()
            for fmt in ('%Y-%m-%d','%Y/%m/%d','%Y.%m.%d','%Y%m%d'):
                try: return datetime.strptime(text,fmt).date().isoformat()
                except ValueError: pass
        raise ValueError('날짜는 YYYY-MM-DD 또는 Excel 날짜로 입력해주세요.')
    if key=='status':
        aliases={'보유':'owned','판매':'sold','판매완료':'sold','폐기':'disposed',**{k:k for k in STATUSES}}
        status=aliases.get(str(value).strip().replace(' ',''))
        if not status: raise ValueError('상태는 보유, 판매, 폐기 중에서 입력해주세요.')
        return status
    if isinstance(value,(str,int,float)): return str(value).strip()
    raise ValueError('텍스트로 입력해주세요.')

@app.post('/api/import/preview')
def preview_import():
    f=request.files.get('excel')
    if not f or not (f.filename or '').lower().endswith('.xlsx'): raise ValueError('다운로드한 .xlsx 양식을 선택해주세요.')
    content=f.read(20*1024*1024+1)
    if len(content)>20*1024*1024: raise ValueError('엑셀 파일은 20MB 이하로 올려주세요.')
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            if sum(x.file_size for x in z.infolist())>120*1024*1024: raise ValueError('엑셀 파일이 너무 큽니다. 나눠서 업로드해주세요.')
        wb=load_workbook(io.BytesIO(content),read_only=True,data_only=False,keep_links=False)
    except (zipfile.BadZipFile,InvalidFileException,KeyError): raise ValueError('읽을 수 없는 엑셀 파일입니다. .xlsx 파일을 확인해주세요.')
    try:
        ws=next((wb[name] for name in ('용품 입력','전체 상품') if name in wb.sheetnames),wb.worksheets[0])
        if (ws.max_column or 0)>100 or (ws.max_row or 0)>20001: raise ValueError('파일당 최대 20,000행입니다. 입력 범위를 확인해주세요.')
        first=next(ws.iter_rows(min_row=1,max_row=1),())
        mapping={}; labels={v:k for k,v in FIELDS.items()}
        for n,cell in enumerate(first):
            header=str(cell.value or '').strip().removesuffix('*').strip()
            if header not in labels: continue
            key=labels[header]
            if key in mapping: raise ValueError(f'{header} 열이 중복되었습니다.')
            mapping[key]=n
        if 'name' not in mapping: raise ValueError('첫 행에 상품명 열이 필요합니다. 업로드 양식을 내려받아 작성해주세요.')
        rows=[]; errors=[]
        for number,cells in enumerate(ws.iter_rows(min_row=2),2):
            if not any(cells[n].value is not None and str(cells[n].value).strip() for n in mapping.values()): continue
            obj={key:0 if key in ('purchase_price','sale_price') else 'owned' if key=='status' else '' for key in FIELDS}
            row_errors=[]
            for key,n in mapping.items():
                try: obj[key]=import_cell(cells[n],key)
                except ValueError as exc: row_errors.append({'row':number,'field':FIELDS[key],'message':str(exc)})
            if not obj['name']: row_errors.append({'row':number,'field':'상품명','message':'상품명을 입력해주세요.'})
            errors.extend(row_errors)
            if not row_errors: rows.append({'row':number,'item':valid_item(obj)})
        if not rows and not errors: raise ValueError('추가할 상품이 없습니다. 양식의 2행부터 내용을 작성해주세요.')
        result={'ok':not bool(errors),'count':len(rows),'errors':errors[:100],'error_count':len(errors),'preview':rows[:50],
                'purchase_total':sum(r['item']['purchase_price'] for r in rows),
                'sale_total':sum(r['item']['sale_price'] for r in rows if r['item']['status']=='sold')}
        if not errors:
            token=str(uuid.uuid4())
            with conn() as c:
                c.execute('DELETE FROM imports WHERE created<?',(time.time()-3600,))
                c.execute('INSERT INTO imports VALUES(?,?,?,NULL)',(token,time.time(),json.dumps({'rows':rows,'filename':Path(f.filename).name},ensure_ascii=False)))
            result['token']=token
        return jsonify(result)
    finally: wb.close()

@app.post('/api/import/commit')
def commit_import():
    token=(request.get_json() or {}).get('token')
    if not isinstance(token,str): raise ValueError('업로드 파일을 먼저 확인해주세요.')
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        batch=c.execute('SELECT * FROM imports WHERE id=?',(token,)).fetchone()
        if not batch or batch['created']<time.time()-3600: raise ValueError('미리보기가 만료되었습니다. 엑셀 파일을 다시 선택해주세요.')
        if batch['result']: return jsonify(json.loads(batch['result']))
        payload=json.loads(batch['payload']); ids=[]; stamp=now(); s=settings(c)
        for row in payload['rows']:
            it=valid_item(row['item']); ident=str(uuid.uuid4())
            it.update(id=ident,created_at=stamp,updated_at=stamp,history=[{'at':stamp,'changes':[{'field':'엑셀 등록','before':'','after':f"{payload['filename']} · {row['row']}행"}]}])
            # Always insert under a new ID; existing records and attachments are untouched.
            c.execute('INSERT INTO items VALUES(?,?)',(ident,json.dumps(it,ensure_ascii=False)))
            ids.append(ident)
            for field,key in [('category','categories'),('method','methods'),('buyer','buyers')]:
                if it[field] and it[field] not in s[key]: s[key].append(it[field])
        c.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(s,ensure_ascii=False),))
        result={'ok':True,'count':len(ids),'ids':ids}
        c.execute('UPDATE imports SET result=?,payload=? WHERE id=?',(json.dumps(result),'{}',token))
    return jsonify(result)

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
                kind=a.get('kind','product')
                if kind not in ('product','receipt'): raise ValueError('사진 종류를 확인해주세요.')
                attachments.append((aid,ident,Path(a['name']).name,mime,b,kind))
            rows.append((it,attachments))
    with conn() as c:
        c.execute('DELETE FROM items')
        c.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(s,ensure_ascii=False),))
        for it,attachments in rows:
            c.execute('INSERT INTO items VALUES(?,?)',(it['id'],json.dumps(it,ensure_ascii=False)))
            c.executemany('INSERT INTO attachments(id,item_id,name,mime,data,kind) VALUES(?,?,?,?,?,?)',attachments)
    return jsonify(ok=True)

if __name__=='__main__':
    from waitress import serve
    serve(app,host=os.environ.get('CAMP_HOST','0.0.0.0'),port=int(os.environ.get('PORT','8099')),threads=4,max_request_body_size=2**40)
