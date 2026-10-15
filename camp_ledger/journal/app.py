"""Persistent campsite journal, HA Ingress and isolated paired-device listener."""
import io,json,os,shutil,sqlite3,uuid,zipfile
from pathlib import Path
from datetime import date
from contextlib import contextmanager
from flask import Flask,request,jsonify,abort,send_file,Response,stream_with_context
from PIL import Image,UnidentifiedImageError,ImageOps
from pillow_heif import register_heif_opener
register_heif_opener()
from .mobile_access import install_mobile,channel_app
from .address_search import search as search_address
from .campsite_search import search as search_campsites
from . import live_sync

DATA=Path(os.getenv('JOURNAL_DATA','./.local-data'));DATA.mkdir(parents=True,exist_ok=True)
MEDIA=DATA/'photos';MEDIA.mkdir(exist_ok=True)
FIELDS=['platform','booking_url','name','location','map_url','site','price','checkin','checkout','nights','photos','layout','notes']
LABELS=['예약 플랫폼','캠핑장 링크','캠핑장명','위치','지도 링크','사이트명','가격','입실','퇴실','기간','사진','배치도','메모']
DETAIL_FIELDS=['name','location','platform','booking_url','site','price','stay','map_url','notes','map','photos','layout']
DEFAULT_PLATFORMS=['홈페이지','캠핏','땡큐캠핑','네이버','캠핑톡']
DEFAULTS={'platforms':DEFAULT_PLATFORMS,'order':FIELDS,'visible':{k:k!='notes' for k in FIELDS},'desktop':{'widths':{k:140 for k in FIELDS},'font':14,'padding':10},'mobile':{'widths':{k:100 for k in FIELDS},'font':12,'padding':6},'external':{},'picker':'files'}
# Device config uses mobile key; display settings use display_mobile to keep schemas separate.
DEFAULTS['display_mobile']=DEFAULTS.pop('mobile')
app=Flask(__name__);app.config['MAX_CONTENT_LENGTH']=64*1024*1024
@contextmanager
def connection():
 c=sqlite3.connect(DATA/'journal.sqlite3',timeout=30);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON')
 try:yield c;c.commit()
 except: c.rollback();raise
 finally:c.close()
with connection() as c:
 c.executescript('CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,body TEXT NOT NULL);CREATE TABLE IF NOT EXISTS photos(id TEXT PRIMARY KEY,record_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,kind TEXT NOT NULL,name TEXT NOT NULL);CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY,body TEXT NOT NULL);')
 if 'memo' not in [r['name'] for r in c.execute('PRAGMA table_info(photos)')]:c.execute("ALTER TABLE photos ADD COLUMN memo TEXT NOT NULL DEFAULT ''")
 c.execute('INSERT OR IGNORE INTO settings VALUES(1,?)',(json.dumps(DEFAULTS),))
def upgrade_columns(settings):
 order=settings.get('order',[])
 if isinstance(order,list) and len(order)==len(FIELDS)-1 and all(isinstance(k,str) for k in order) and set(order)==set(FIELDS)-{'nights'}:
  settings['order']=[*order[:order.index('checkout')+1],'nights',*order[order.index('checkout')+1:]]
  settings.setdefault('visible',{}).setdefault('nights',settings['visible'].get('checkout',True))
  for mode in ('desktop','display_mobile'):
   widths=settings.setdefault(mode,{}).setdefault('widths',{});widths.setdefault('nights',widths.get('checkout',100))
 return settings
def get_settings(c):
 s=upgrade_columns(json.loads(c.execute('SELECT body FROM settings WHERE id=1').fetchone()[0]));s.setdefault('platforms',list(DEFAULT_PLATFORMS));s.setdefault('scroll_top','bottom-right');s['scroll_top']={'left-top':'top-left','right-top':'top-right','left-bottom':'bottom-left','right-bottom':'bottom-right','left-middle':'bottom-left','right-middle':'bottom-right'}.get(s['scroll_top'],s['scroll_top']);s.setdefault('add_position','bottom-right');s.setdefault('add_label','캠핑 기록 추가');s.setdefault('kakao_key','');s.setdefault('detail_order',list(DETAIL_FIELDS));s.setdefault('field_labels',{});s.setdefault('selection_enabled',True);s.setdefault('duplicate_enabled',True);s.setdefault('detail_duplicate_enabled',s['duplicate_enabled']);s.setdefault('click_actions',{'list':{'name':{'copy':False,'map':True},'location':{'copy':False,'map':True}},'detail':{'name':{'copy':True,'map':False},'location':{'copy':True,'map':False}}})
 for mode in ('desktop','display_mobile'):
  s[mode].setdefault('link_size',20);s[mode].setdefault('order',list(s['order']) if mode=='desktop' else ['name','site','checkin','checkout','nights','location','price','notes','platform','booking_url','map_url','photos','layout']);s[mode].setdefault('visible',dict(s['visible']));s[mode].setdefault('photo_size',38);s[mode].setdefault('row_height',0);s[mode].setdefault('layout_caption',False);s[mode].setdefault('layout_size',56)
 s.setdefault('empty_text',{})
 return s
mobile=install_mobile(app,connection,get_settings,DATA)
@app.before_request
def guard():
 result=mobile['guard']()
 if result is not None:return result
 if request.method in ('POST','PUT','DELETE') and request.path!='/api/mobile/session' and request.headers.get('X-Camp-Request')!='1':abort(403)
@app.after_request
def headers(r):
 r.headers['X-Content-Type-Options']='nosniff';r.headers['Referrer-Policy']='strict-origin-when-cross-origin';r.headers['Cache-Control']='no-store' if request.path.startswith('/api/') else 'no-cache'
 if request.method in ('POST','PUT','DELETE') and request.path.startswith('/api/') and r.status_code<400 and request.path not in ('/api/import/preview','/api/import/text-preview'):live_sync.publish()
 r.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data: blob: https://tile.openstreetmap.org https://*.kakao.com https://*.daumcdn.net https://*.daum.net https://*.kakaocdn.net; style-src 'self' 'unsafe-inline'; script-src 'self' https://dapi.kakao.com https://*.daumcdn.net https://*.daum.net https://*.kakaocdn.net; connect-src 'self' https://*.kakao.com https://*.daumcdn.net https://*.daum.net; frame-src 'self' kakaonavi-sdk: kakaomap: nmap: tmap: intent: https://kakaonavi.kakao.com https://www.openstreetmap.org https://postcode.map.kakao.com https://postcode.map.daum.net; base-uri 'self'; form-action 'self'"
 return r
@app.errorhandler(ValueError)
def invalid(e):return jsonify(error=str(e)),400
@app.errorhandler(413)
def too_large(e):return jsonify(error='한 번에 64MB 이하로 첨부해주세요.'),413
@app.get('/')
def index():
 html=(Path(app.static_folder)/'index.html').read_text().replace('__APP_VERSION__',os.getenv('JOURNAL_VERSION','1.0.0'))
 return Response(html,mimetype='text/html')
@app.get('/hub')
def hub():return app.send_static_file('hub.html')
@app.get('/api/state')
def state():
 with connection() as c:
  rows=[{**json.loads(r['body']),'id':r['id'],'photos':[dict(p) for p in c.execute('SELECT * FROM photos WHERE record_id=?',(r['id'],))]} for r in c.execute('SELECT * FROM records ORDER BY rowid DESC')]
  return jsonify(records=rows,settings=get_settings(c),admin=mobile['admin'](),version=os.getenv('JOURNAL_VERSION','1.0.0'))
def clean(raw):
 if not isinstance(raw,dict):raise ValueError('기록 형식이 올바르지 않습니다.')
 b={k:raw.get(k,'') for k in FIELDS if k not in ('photos','layout','nights')}
 for k,v in b.items():
  if not isinstance(v,(str,int,float)) or len(str(v))>10000:raise ValueError('입력값이 너무 길거나 올바르지 않습니다.')
  if k!='price':b[k]=str(v).strip()
 if not b['name']:raise ValueError('캠핑장명을 입력해주세요.')
 for k in ('booking_url','map_url'):
  if b[k] and not b[k].startswith(('https://','http://')):raise ValueError('링크는 https:// 또는 http://로 시작해야 합니다.')
 try:b['price']=int(b['price'] or 0)
 except (ValueError,TypeError):raise ValueError('가격은 원 단위 정수로 입력해주세요.')
 if b['price']<0:raise ValueError('가격은 0원 이상이어야 합니다.')
 for k in ('checkin','checkout'):
  if b[k]:
   try:date.fromisoformat(b[k])
   except ValueError:raise ValueError('숙박 날짜를 확인해주세요.')
 if b['checkout'] and not b['checkin']:raise ValueError('입실일을 먼저 입력해주세요.')
 if b['checkin'] and b['checkout'] and b['checkout']<b['checkin']:raise ValueError('퇴실일은 입실일 이후여야 합니다.')
 for k in ('lat','lng'):
  v=raw.get(k)
  if v in ('',None):b[k]=None
  else:
   try:v=float(v)
   except (ValueError,TypeError):raise ValueError('좌표는 숫자로 입력해주세요.')
   if not -(90 if k=='lat' else 180)<=v<=(90 if k=='lat' else 180):raise ValueError('좌표 범위를 확인해주세요.')
   b[k]=v
 if (b['lat'] is None)!=(b['lng'] is None):raise ValueError('위도와 경도를 함께 입력해주세요.')
 return b
@app.get('/api/live/status')
def live_status():
 return jsonify(revision=live_sync.revision,version=os.getenv('JOURNAL_VERSION','1.0.0'))

@app.get('/api/live')
def live():
 return Response(stream_with_context(live_sync.events()),mimetype='text/event-stream',headers={'X-Accel-Buffering':'no','Cache-Control':'no-cache'})

@app.get('/api/campsites')
def campsites():
 body,status=search_campsites(request.args.get('q',''))
 return jsonify(body),status

@app.get('/api/addresses')
def addresses():
 body,status=search_address(request.args.get('q',''))
 return jsonify(body),status

def reject_duplicate(c,body,exclude=None):
 from .reservation_import import identity
 if not body.get('checkin') or not body.get('checkout'):return
 key=identity(body)
 if any(row['id']!=exclude and identity(json.loads(row['body']))==key for row in c.execute('SELECT id,body FROM records')):
  abort(409,description='같은 캠핑장과 입실·퇴실일의 기록이 이미 있습니다. 기존 기록을 수정하거나 기간을 변경해주세요.')

@app.errorhandler(409)
def conflict(e):return jsonify(error=e.description,code='duplicate_record' if e.description.startswith('같은 캠핑장') else 'conflict'),409

@app.post('/api/records')
def create():
 raw=request.get_json();b=clean(raw);ident=str(uuid.uuid4());source=raw.get('clone_from');staged=[]
 if source is not None and (not isinstance(source,str) or len(source)>80):raise ValueError('복제할 원본 기록을 확인해주세요.')
 try:
  with connection() as c:
   c.execute('BEGIN IMMEDIATE')
   reject_duplicate(c,b)
   if source and not c.execute('SELECT 1 FROM records WHERE id=?',(source,)).fetchone():raise ValueError('원본 기록이 삭제되어 복제할 수 없습니다.')
   c.execute('INSERT INTO records VALUES(?,?)',(ident,json.dumps(b,ensure_ascii=False)))
   if source:
    for photo in c.execute('SELECT * FROM photos WHERE record_id=?',(source,)).fetchall():
     pid=str(uuid.uuid4());path=MEDIA/(pid+'.jpg');staged.append(path);shutil.copyfile(MEDIA/(photo['id']+'.jpg'),path)
     c.execute('INSERT INTO photos(id,record_id,kind,name,memo) VALUES(?,?,?,?,?)',(pid,ident,photo['kind'],photo['name'],photo['memo']))
 except Exception:
  for path in staged:path.unlink(missing_ok=True)
  raise
 return jsonify(id=ident),201
@app.post('/api/records/bulk-delete')
def bulk_delete():
 raw=request.get_json();ids=raw.get('ids') if isinstance(raw,dict) else None
 if not isinstance(ids,list) or not 1<=len(ids)<=10000 or any(not isinstance(ident,str) or not ident or len(ident)>80 for ident in ids):raise ValueError('삭제할 기록을 선택해주세요.')
 ids=list(dict.fromkeys(ids));names=[];found=[]
 with connection() as c:
  c.execute('BEGIN IMMEDIATE')
  for start in range(0,len(ids),500):
   chunk=ids[start:start+500];marks=','.join('?' for _ in chunk)
   found.extend(row[0] for row in c.execute('SELECT id FROM records WHERE id IN ('+marks+')',chunk))
   names.extend(row[0] for row in c.execute('SELECT id FROM photos WHERE record_id IN ('+marks+')',chunk))
  c.executemany('DELETE FROM records WHERE id=?',[(ident,) for ident in found])
 for name in names:(MEDIA/(name+'.jpg')).unlink(missing_ok=True)
 return jsonify(ok=True,deleted=len(found))
@app.put('/api/records/<ident>')
def update(ident):
 b=clean(request.get_json())
 with connection() as c:
  c.execute('BEGIN IMMEDIATE')
  if not c.execute('SELECT 1 FROM records WHERE id=?',(ident,)).fetchone():abort(404)
  reject_duplicate(c,b,ident)
  if not c.execute('UPDATE records SET body=? WHERE id=?',(json.dumps(b,ensure_ascii=False),ident)).rowcount:abort(404)
 return jsonify(ok=True)
@app.delete('/api/records/<ident>')
def delete(ident):
 with connection() as c:
  names=[p[0] for p in c.execute('SELECT id FROM photos WHERE record_id=?',(ident,))]
  if not c.execute('DELETE FROM records WHERE id=?',(ident,)).rowcount:abort(404)
 for name in names:(MEDIA/(name+'.jpg')).unlink(missing_ok=True)
 return jsonify(ok=True)
@app.put('/api/records/<ident>/position')
def resolve_position(ident):
 raw=request.get_json()
 if not isinstance(raw,dict) or not isinstance(raw.get('address'),str):raise ValueError('주소를 확인해주세요.')
 checked=clean({'name':'지도 위치','lat':raw.get('lat'),'lng':raw.get('lng')})
 if checked['lat'] is None:raise ValueError('지도 위치를 확인해주세요.')
 with connection() as c:
  c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT body FROM records WHERE id=?',(ident,)).fetchone()
  if row is None:abort(404)
  body=json.loads(row['body'])
  if body.get('location')!=raw['address']:return jsonify(error='주소가 변경되어 위치를 다시 찾아야 합니다.'),409
  if body.get('lat') is None or body.get('lng') is None:
   body.update(lat=checked['lat'],lng=checked['lng']);c.execute('UPDATE records SET body=? WHERE id=?',(json.dumps(body,ensure_ascii=False),ident))
  return jsonify(lat=body['lat'],lng=body['lng'])
def image_content(file):
 try:
  with Image.open(file.stream) as im:
   if im.format not in ('JPEG','PNG','WEBP','GIF','HEIF','HEIC'):raise ValueError('JPG, PNG, WebP, GIF 사진을 선택해주세요.')
   im.load();im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((3200,3200));buf=io.BytesIO();im.save(buf,'JPEG',quality=90);return buf.getvalue()
 except (UnidentifiedImageError,OSError,Image.DecompressionBombError):raise ValueError('사진을 읽을 수 없습니다. HEIC 사진은 JPG로 변환해주세요.')
@app.post('/api/records/save')
def save_with_photos():
 try:raw=json.loads(request.form.get('record','null'))
 except (ValueError,TypeError):raise ValueError('저장할 기록을 확인해주세요.')
 if not isinstance(raw,dict):raise ValueError('저장할 기록을 확인해주세요.')
 body=clean(raw.get('fields'));ident=raw.get('id');source=raw.get('clone_from');keep=raw.get('keep',[]);uploads=raw.get('uploads',[]);remove=raw.get('remove',[])
 if any(v is not None and (not isinstance(v,str) or not v or len(v)>80) for v in (ident,source)) or ident and source:raise ValueError('저장할 기록을 확인해주세요.')
 if not isinstance(keep,list) or not isinstance(uploads,list) or len(keep)+len(uploads)>2000:raise ValueError('사진 목록을 확인해주세요.')
 def memo(item):
  if not isinstance(item,dict) or not isinstance(item.get('memo',''),str) or len(item.get('memo',''))>2000:raise ValueError('사진 메모는 2000자 이하로 입력해주세요.')
  return item.get('memo','')
 if not isinstance(remove,list) or any(not isinstance(pid,str) for pid in remove) or len(remove)>2000:raise ValueError('삭제할 사진 목록을 확인해주세요.')
 keep_values={};memo_changed=set()
 for item in keep:
  text=memo(item);pid=item.get('id')
  if not isinstance(pid,str) or not pid or pid in keep_values:raise ValueError('사진 목록을 확인해주세요.')
  keep_values[pid]=text
  if item.get('changed',True):memo_changed.add(pid)
 staged=[];fields=set()
 for item in uploads:
  text=memo(item);field=item.get('field');kind=item.get('kind')
  if not isinstance(field,str) or field in fields or kind not in ('gallery','layout') or field not in request.files:raise ValueError('첨부 사진을 확인해주세요.')
  fields.add(field);file=request.files[field];staged.append((str(uuid.uuid4()),kind,Path(file.filename or '사진').name,image_content(file),text))
 target=ident or str(uuid.uuid4());written=[];removed=[]
 try:
  with connection() as c:
   c.execute('BEGIN IMMEDIATE');owner=ident or source
   if owner and not c.execute('SELECT 1 FROM records WHERE id=?',(owner,)).fetchone():raise ValueError('기록이 삭제되어 저장할 수 없습니다.')
   reject_duplicate(c,body,ident)
   existing={p['id']:dict(p) for p in c.execute('SELECT * FROM photos WHERE record_id=?',(owner,))} if owner else {}
   if not set(keep_values)<=set(existing) or not set(remove)<=set(existing) or set(remove)&set(keep_values) or remove and not ident:raise ValueError('현재 기록에 속한 사진만 저장할 수 있습니다.')
   if ident:c.execute('UPDATE records SET body=? WHERE id=?',(json.dumps(body,ensure_ascii=False),target))
   else:c.execute('INSERT INTO records VALUES(?,?)',(target,json.dumps(body,ensure_ascii=False)))
   if ident:
    removed=list(set(remove))
    c.executemany('DELETE FROM photos WHERE id=?',[(pid,) for pid in removed])
    c.executemany('UPDATE photos SET memo=? WHERE id=?',[(text,pid) for pid,text in keep_values.items() if pid in memo_changed])
   elif source:
    for pid,text in keep_values.items():
     photo=existing[pid];newid=str(uuid.uuid4());path=MEDIA/(newid+'.jpg');written.append(path);shutil.copyfile(MEDIA/(pid+'.jpg'),path)
     c.execute('INSERT INTO photos(id,record_id,kind,name,memo) VALUES(?,?,?,?,?)',(newid,target,photo['kind'],photo['name'],text))
   for pid,kind,name,content,text in staged:
    path=MEDIA/(pid+'.jpg');written.append(path);path.write_bytes(content)
    c.execute('INSERT INTO photos(id,record_id,kind,name,memo) VALUES(?,?,?,?,?)',(pid,target,kind,name,text))
 except Exception:
  for path in written:path.unlink(missing_ok=True)
  raise
 for pid in removed:(MEDIA/(pid+'.jpg')).unlink(missing_ok=True)
 return jsonify(id=target),200 if ident else 201
@app.post('/api/records/<ident>/photos/<kind>')
def upload(ident,kind):
 if kind not in ('gallery','layout'):abort(400)
 staged=[]
 try:
  files=request.files.getlist('photos')
  if not files:raise ValueError('사진을 선택해주세요.')
  for f in files:
   ident_photo=str(uuid.uuid4())
   content=image_content(f)
   staged.append((ident_photo,Path(f.filename or '사진').name,content))
  with connection() as c:
   if not c.execute('SELECT 1 FROM records WHERE id=?',(ident,)).fetchone():abort(404)
   for pid,name,content in staged:
    (MEDIA/(pid+'.jpg')).write_bytes(content);c.execute('INSERT INTO photos(id,record_id,kind,name) VALUES(?,?,?,?)',(pid,ident,kind,name))
 except Exception:
  for pid,_,_ in staged:(MEDIA/(pid+'.jpg')).unlink(missing_ok=True)
  raise
 return jsonify(ok=True,count=len(staged))
@app.get('/photos/<pid>')
def photo(pid):
 with connection() as c:
  if not c.execute('SELECT 1 FROM photos WHERE id=?',(pid,)).fetchone():abort(404)
 return send_file(MEDIA/(pid+'.jpg'),mimetype='image/jpeg')
@app.put('/api/photos/<pid>')
def photo_memo(pid):
 raw=request.get_json()
 if not isinstance(raw,dict) or not isinstance(raw.get('memo'),str) or len(raw['memo'])>2000:raise ValueError('사진 메모는 2000자 이하로 입력해주세요.')
 with connection() as c:
  if not c.execute('UPDATE photos SET memo=? WHERE id=?',(raw['memo'],pid)).rowcount:abort(404)
 return jsonify(ok=True)
@app.delete('/api/photos/<pid>')
def remove_photo(pid):
 with connection() as c:
  if not c.execute('DELETE FROM photos WHERE id=?',(pid,)).rowcount:abort(404)
 (MEDIA/(pid+'.jpg')).unlink(missing_ok=True)
 return jsonify(ok=True)
@app.post('/api/import/preview')
def import_preview():
 from .reservation_import import image_text,parse_reservations,identity
 file=request.files.get('image')
 text=image_text(file) if file else str((request.get_json(silent=True) or {}).get('text',''))[:50000]
 with connection() as c:existing={identity(json.loads(row['body'])) for row in c.execute('SELECT body FROM records')}
 rows=parse_reservations(text)
 return jsonify(text=text,records=[{**row,'duplicate':identity(row) in existing} for row in rows])
@app.post('/api/import/text-preview')
def import_text_preview():
 from .reservation_import import parse_reservation_text,identity
 raw=request.get_json(silent=True)
 if not isinstance(raw,dict) or not isinstance(raw.get('text'),str) or len(raw['text'])>10000:raise ValueError('예약문자는 10,000자 이하로 붙여넣어주세요.')
 rows=parse_reservation_text(raw['text'])
 with connection() as c:existing={identity(json.loads(row['body'])) for row in c.execute('SELECT body FROM records')}
 return jsonify(records=[{**row,'duplicate':identity(row) in existing} for row in rows])
@app.post('/api/import/commit')
def import_commit():
 from .reservation_import import identity
 raw=request.get_json(silent=True) or {};rows=raw.get('records')
 if not isinstance(rows,list) or not 1<=len(rows)<=100 or any(not isinstance(row,dict) for row in rows):raise ValueError('추가할 예약은 1~100개로 선택해주세요.')
 bodies=[clean(row) for row in rows]
 if any(not b.get('checkin') or not b.get('checkout') for b in bodies):raise ValueError('사진 가져오기는 입실일과 퇴실일이 필요합니다.')
 added=[];skipped=0
 with connection() as c:
  c.execute('BEGIN IMMEDIATE');existing={identity(json.loads(row['body'])) for row in c.execute('SELECT body FROM records')}
  for body in bodies:
   key=identity(body)
   if key in existing:skipped+=1;continue
   ident=uuid.uuid4().hex;c.execute('INSERT INTO records VALUES(?,?)',(ident,json.dumps(body,ensure_ascii=False)));existing.add(key);added.append(ident)
 return jsonify(added=added,skipped=skipped)
@app.put('/api/settings')
def settings():
 raw=request.get_json()
 if not isinstance(raw,dict):raise ValueError('설정 형식이 올바르지 않습니다.')
 raw=upgrade_columns(raw)
 order=raw.get('order',[])
 if len(order)!=len(FIELDS) or set(order)!=set(FIELDS):raise ValueError('항목 순서를 확인해주세요.')
 visible=raw.get('visible',{})
 if set(visible)!=set(FIELDS) or any(type(v)!=bool for v in visible.values()) or not any(visible.values()):raise ValueError('최소 한 항목을 표시해주세요.')
 display={}
 for key in ('desktop','display_mobile'):
  x=raw.get(key,{})
  try:
   font=int(x['font']);padding=int(x['padding']);widths={k:int(x['widths'][k]) for k in FIELDS}
  except (KeyError,ValueError,TypeError):raise ValueError('화면 설정을 확인해주세요.')
  if not 8<=font<=60 or not 2<=padding<=60 or any(not 20<=v<=1200 for v in widths.values()):raise ValueError('열 너비 20px, 글자 8px, 여백 2px 이상으로 설정해주세요.')
  link_size=x.get('link_size',20)
  if type(link_size)!=int or not 8<=link_size<=80:raise ValueError('링크 아이콘 크기는 8~80px로 설정해주세요.')
  mode_order=x.get('order',order);mode_visible=x.get('visible',visible);photo_size=x.get('photo_size',38)
  if not isinstance(mode_order,list) or any(not isinstance(k,str) for k in mode_order) or len(mode_order)!=len(FIELDS) or set(mode_order)!=set(FIELDS):raise ValueError('PC·모바일 항목 순서를 확인해주세요.')
  if not isinstance(mode_visible,dict) or set(mode_visible)!=set(FIELDS) or any(type(v)!=bool for v in mode_visible.values()) or not any(mode_visible.values()):raise ValueError('PC·모바일에 최소 한 항목을 표시해주세요.')
  if type(photo_size)!=int or not 20<=photo_size<=200:raise ValueError('사진 크기는 20~200px입니다.')
  row_height=x.get('row_height',0)
  if type(row_height)!=int or (row_height!=0 and not 20<=row_height<=400):raise ValueError('행 높이는 자동(0) 또는 20~400px입니다.')
  layout_caption=x.get('layout_caption',False)
  if type(layout_caption)!=bool:raise ValueError('배치도 문구 표시 설정을 확인해주세요.')
  layout_size=x.get('layout_size',56)
  if type(layout_size)!=int or not 20<=layout_size<=200:raise ValueError('배치도 사진 크기는 20~200px입니다.')
  display[key]={'layout_size':layout_size,'layout_caption':layout_caption,'row_height':row_height,'font':font,'padding':padding,'widths':widths,'link_size':link_size,'order':mode_order,'visible':mode_visible,'photo_size':photo_size}
 if raw.get('picker') not in ('files','gallery'):raise ValueError('사진 선택 방식을 확인해주세요.')
 with connection() as c:
  c.execute('BEGIN IMMEDIATE');s=get_settings(c);platforms=raw.get('platforms',s['platforms'])
  if not isinstance(platforms,list) or not 0<=len(platforms)<=200 or any(not isinstance(p,str) or not p.strip() or len(p)>80 for p in platforms):raise ValueError('예약 플랫폼은 최대 200개, 이름은 1~80자로 입력해주세요.')
  platforms=[p.strip() for p in platforms]
  if len({p.casefold() for p in platforms})!=len(platforms):raise ValueError('중복된 예약 플랫폼 이름을 확인해주세요.')
  operations={}
  for key in ('platform_remove','platform_add'):
   values=raw.get(key,[])
   if not isinstance(values,list) or len(values)>200 or any(not isinstance(p,str) or not p.strip() or len(p)>80 for p in values):raise ValueError('예약 플랫폼 변경 항목을 확인해주세요.')
   operations[key]={p.strip().casefold() for p in values}
  deleted=set(s.get('platform_deleted',[]));deleted.update(operations['platform_remove']);deleted.difference_update(operations['platform_add'])
  requested_order=raw.get('platform_order')
  if requested_order is not None:
   if not isinstance(requested_order,list) or any(not isinstance(p,str) for p in requested_order) or len(requested_order)!=len(platforms) or {p.casefold() for p in requested_order}!={p.casefold() for p in platforms}:raise ValueError('예약 플랫폼 순서를 확인해주세요.')
   sequence=[*requested_order,*s['platforms']]
  else:sequence=[*s['platforms'],*platforms]
  merged=[];seen=set()
  for p in sequence:
   if p.casefold() not in seen and p.casefold() not in deleted:seen.add(p.casefold());merged.append(p)
  if len(merged)>200:raise ValueError('예약 플랫폼은 최대 200개까지 등록할 수 있습니다.')
  detail_order=raw.get('detail_order',s['detail_order'])
  if not isinstance(detail_order,list) or len(detail_order)!=len(DETAIL_FIELDS) or any(not isinstance(k,str) for k in detail_order) or set(detail_order)!=set(DETAIL_FIELDS):raise ValueError('상세 항목 순서를 확인해주세요.')
  kakao_key=raw.get('kakao_key',s['kakao_key'])
  if kakao_key!=s['kakao_key'] and not mobile['admin']():abort(403)
  if not isinstance(kakao_key,str) or (kakao_key and (len(kakao_key)!=32 or any(ch not in '0123456789abcdefABCDEF' for ch in kakao_key))):raise ValueError('카카오 JavaScript 키를 확인해주세요.')
  scroll_top=raw.get('scroll_top',s['scroll_top'])
  scroll_top={'left-top':'top-left','right-top':'top-right','left-bottom':'bottom-left','right-bottom':'bottom-right','left-middle':'bottom-left','right-middle':'bottom-right'}.get(scroll_top,scroll_top)
  if scroll_top not in ('top-left','top-center','top-right','bottom-left','bottom-center','bottom-right'):raise ValueError('맨 위로 버튼 위치를 확인해주세요.')
  add_label=raw.get('add_label',s['add_label'])
  if not isinstance(add_label,str) or len(add_label)>40:raise ValueError('추가 버튼 문구는 40자 이하로 입력해주세요.')
  add_position=raw.get('add_position',s['add_position'])
  if add_position not in ('top-left','top-center','top-right','bottom-left','bottom-center','bottom-right'):raise ValueError('추가 버튼 위치를 확인해주세요.')
  actions={k:raw.get(k,s[k]) for k in ('selection_enabled','duplicate_enabled','detail_duplicate_enabled')}
  if any(type(value)!=bool for value in actions.values()):raise ValueError('선택·복제 표시 설정을 확인해주세요.')
  click_actions=raw.get('click_actions',s['click_actions'])
  if not isinstance(click_actions,dict) or set(click_actions)!=set(('list','detail')):raise ValueError('클릭 동작 설정을 확인해주세요.')
  for view in click_actions.values():
   if not isinstance(view,dict) or set(view)!=set(('name','location')):raise ValueError('클릭 동작 설정을 확인해주세요.')
   for flags in view.values():
    if not isinstance(flags,dict) or set(flags)!=set(('copy','map')) or any(type(v)!=bool for v in flags.values()):raise ValueError('클릭 동작 설정을 확인해주세요.')
  field_labels=raw.get('field_labels',s['field_labels'])
  if not isinstance(field_labels,dict) or any(k not in FIELDS or not isinstance(v,str) or len(v)>40 for k,v in field_labels.items()):raise ValueError('항목 이름은 공백을 포함해 40자 이하로 입력해주세요.')
  field_labels=dict(field_labels)
  empty_text=raw.get('empty_text',s['empty_text'])
  if not isinstance(empty_text,dict) or any(k not in FIELDS or k in ('photos','layout') or not isinstance(v,str) or len(v)>100 for k,v in empty_text.items()):raise ValueError('빈 내용 표시는 사진을 제외한 항목에 100자 이하로 입력해주세요.')
  s.update(**actions,add_label=add_label,click_actions=click_actions,add_position=add_position,empty_text=empty_text,field_labels=field_labels,platform_deleted=sorted(deleted),detail_order=detail_order,kakao_key=kakao_key,scroll_top=scroll_top,platforms=merged,order=order,visible=visible,picker=raw['picker'],**display);c.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(s,ensure_ascii=False),))
 return jsonify(ok=True)
@app.get('/api/backup')
def backup():
 out=io.BytesIO()
 with connection() as c,zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  # Serialize only journal data; paired device secrets are excluded.
  records=[dict(r) for r in c.execute('SELECT * FROM records')];photos=[dict(r) for r in c.execute('SELECT * FROM photos')]
  s=get_settings(c);s.pop('mobile',None)
  z.writestr('journal.json',json.dumps({'records':records,'photos':photos,'settings':s},ensure_ascii=False))
  for p in photos:z.write(MEDIA/(p['id']+'.jpg'),'photos/'+p['id']+'.jpg')
 out.seek(0);return send_file(out,as_attachment=True,download_name='캠핑장기록-백업.zip')
if __name__=='__main__':
 from waitress import serve
 import threading
 threading.Thread(target=lambda:serve(channel_app(app,'external'),host='0.0.0.0',port=8098,threads=32),daemon=True).start()
 serve(channel_app(app,'ingress'),host=os.getenv('JOURNAL_HOST','0.0.0.0'),port=int(os.getenv('JOURNAL_PORT','8099')),threads=32)
