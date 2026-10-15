"""Explicit platform imports. Only supplied page text/images are read; no login crawl."""
import base64,binascii,hashlib,io,json,re,uuid
from PIL import Image,ImageOps,UnidentifiedImageError
from .reservation_import import review_records,identity
PROVIDERS={'camfit':'캠핏','thankq':'땡큐캠핑','campingtalk':'캠핑톡'}
def booking_id(text):
 match=re.search(r'예약\s*(?:번호|코드|번호\s*[:：])\s*[:：#]?\s*([A-Za-z0-9][A-Za-z0-9_-]{4,79})',text)
 return match.group(1) if match else ''
def media_bytes(value):
 if not isinstance(value,str) or not value.startswith('data:image/jpeg;base64,') or len(value)>2500000:raise ValueError('동기화 사진 형식을 확인해주세요.')
 try:
  raw=base64.b64decode(value.split(',',1)[1],validate=True)
  with Image.open(io.BytesIO(raw)) as image:
   if image.format!='JPEG' or image.width*image.height>6000000:raise ValueError('동기화 사진 크기를 확인해주세요.')
   image=ImageOps.exif_transpose(image).convert('RGB');image.thumbnail((1800,1800));out=io.BytesIO();image.save(out,'JPEG',quality=88);return out.getvalue()
 except (binascii.Error,UnidentifiedImageError,OSError,Image.DecompressionBombError):raise ValueError('동기화 사진을 읽을 수 없습니다.')
def media_list(raw):
 if not isinstance(raw,list) or len(raw)>4:raise ValueError('예약당 사진은 대표 사진 1장·배치도 3장까지 가져올 수 있습니다.')
 result=[]
 for photo in raw:
  if not isinstance(photo,dict) or photo.get('kind') not in ('gallery','layout'):raise ValueError('사진 종류를 확인해주세요.')
  result.append({'kind':photo['kind'],'data':photo['data'],'bytes':media_bytes(photo['data'])})
 if sum(p['kind']=='gallery' for p in result)>1 or sum(p['kind']=='layout' for p in result)>3:raise ValueError('사진 종류별 개수를 확인해주세요.')
 return result

def validate_ref(raw):
 if not isinstance(raw,dict) or raw.get('provider') not in PROVIDERS:raise ValueError('동기화 플랫폼을 확인해주세요.')
 ident=raw.get('booking_id','')
 if not isinstance(ident,str) or ident and not re.fullmatch(r'[A-Za-z0-9_-]{5,80}',ident):raise ValueError('예약 번호를 확인해주세요.')
 return {'provider':raw['provider'],'booking_id':ident}
def match_record(records,fields,ref):
 if ref['booking_id']:
  matches=[r for r in records if r.get('platform_ref')==ref]
  if len(matches)>1:raise ValueError('같은 예약 번호가 여러 기록에 있습니다. 기존 기록을 확인해주세요.')
  if matches:return matches[0]
 matches=[r for r in records if fields.get('checkin') and fields.get('checkout') and identity(r)==identity(fields)]
 if len(matches)>1:raise ValueError('같은 캠핑장·기간의 기록이 여러 개입니다. 기존 기록을 확인해주세요.')
 return matches[0] if matches else None

def preview(raw,records):
 if not isinstance(raw,dict) or raw.get('provider') not in PROVIDERS:raise ValueError('지원하는 플랫폼을 선택해주세요.')
 cards=raw.get('cards',[])
 if not isinstance(cards,list) or not 1<=len(cards)<=20:raise ValueError('예약 화면에서 동기화를 눌러주세요. 한 번에 20건까지 읽습니다.')
 result=[];seen=set();skipped=0
 for card in cards:
  if not isinstance(card,dict) or not isinstance(card.get('text'),str) or len(card['text'])>8000:raise ValueError('예약 화면 내용을 확인해주세요.')
  text=card['text']
  if re.search(r'취소\s*완료|예약(?:이|가)\s*취소|취소된\s*예약|예약\s*취소됨',text):skipped+=1;continue
  rows=review_records(text)
  if not rows:continue
  # Photos can only be associated with a card that resolves to one booking.
  photos=media_list(card.get('media',[])) if len(rows)==1 else []
  for row in rows:
   ref={'provider':raw['provider'],'booking_id':booking_id(text) if len(rows)==1 else ''}
   row['platform']=PROVIDERS[ref['provider']]
   key=ref['booking_id'] or str(identity(row))
   if key in seen:continue
   seen.add(key);existing=match_record(records,row,ref)
   merged={**(existing or {}),**row};merged.pop('id',None);merged.pop('rating',None);merged.pop('photos',None)
   for field in ('location','site','booking_url','map_url','notes','checkin','checkout'):
    if not row.get(field) and existing and existing.get(field):merged[field]=existing[field]
   if existing and row.get('location') and row['location']!=existing.get('location'):merged['lat']=None;merged['lng']=None
   merged['platform_sync']=ref;merged['sync_existing']=existing['id'] if existing else None;merged['replace_cover']=False
   merged['sync_media']=[{'kind':p['kind'],'data':p['data']} for p in photos]
   gallery=next((p for p in photos if p['kind']=='gallery'),None)
   if gallery:merged['thumbnail']=gallery['data']
   merged['duplicate']=False;result.append(merged)
 return {'records':result,'cancelled_skipped':skipped}

def commit(raw,connection,clean,reject_duplicate,media_root):
 rows=raw.get('records') if isinstance(raw,dict) else None
 if not isinstance(rows,list) or not 1<=len(rows)<=20:raise ValueError('동기화할 예약을 1~20건 선택해주세요.')
 prepared=[]
 for row in rows:
  if not isinstance(row,dict):raise ValueError('예약 내용을 확인해주세요.')
  ref=validate_ref(row.get('platform_sync'));fields=clean({k:v for k,v in row.items() if k!='rating'})
  if fields.get('platform')!=PROVIDERS[ref['provider']]:raise ValueError('연결한 플랫폼과 예약 플랫폼이 다릅니다.')
  if not fields.get('checkin') or not fields.get('checkout'):raise ValueError('동기화할 예약의 입실일·퇴실일을 선택해주세요.')
  if type(row.get('replace_cover',False)) is not bool:raise ValueError('대표 사진 선택을 확인해주세요.')
  prepared.append((fields,ref,media_list(row.get('sync_media',[])),row.get('replace_cover',False)))
 written=[];added=[];updated=[];photos_added=0
 try:
  with connection() as c:
   c.execute('BEGIN IMMEDIATE')
   for fields,ref,photos,replace in prepared:
    records=[{**json.loads(r['body']),'id':r['id']} for r in c.execute('SELECT * FROM records')]
    old=match_record(records,fields,ref);ident=old['id'] if old else uuid.uuid4().hex
    reject_duplicate(c,fields,ident if old else None)
    body={**(old or {}),**fields,'platform_ref':ref};body.pop('id',None)
    if old:c.execute('UPDATE records SET body=? WHERE id=?',(json.dumps(body,ensure_ascii=False),ident));updated.append(ident)
    else:c.execute('INSERT INTO records VALUES(?,?)',(ident,json.dumps(body,ensure_ascii=False)));added.append(ident)
    current=[dict(p) for p in c.execute('SELECT * FROM photos WHERE record_id=?',(ident,))]
    hashes={}
    for p in current:
     path=media_root/(p['id']+'.jpg')
     if path.is_file():hashes[(p['kind'],hashlib.sha256(path.read_bytes()).hexdigest())]=p['id']
    has_cover=any(p['kind']=='gallery' for p in current)
    for photo in photos:
     key=(photo['kind'],hashlib.sha256(photo['bytes']).hexdigest());pid=hashes.get(key)
     if not pid:
      pid=uuid.uuid4().hex;path=media_root/(pid+'.jpg');written.append(path);path.write_bytes(photo['bytes'])
      c.execute('INSERT INTO photos(id,record_id,kind,name,memo,is_cover) VALUES(?,?,?,?,?,0)',(pid,ident,photo['kind'],fields['name']+(' 대표 사진.jpg' if photo['kind']=='gallery' else ' 배치도.jpg'),''));hashes[key]=pid;photos_added+=1
     if photo['kind']=='gallery' and (replace or not has_cover):
      c.execute("UPDATE photos SET is_cover=0 WHERE record_id=? AND kind='gallery'",(ident,));c.execute('UPDATE photos SET is_cover=1 WHERE id=?',(pid,));has_cover=True
 except Exception:
  for path in written:path.unlink(missing_ok=True)
  raise
 return {'added':added,'updated':updated,'photos_added':photos_added}
