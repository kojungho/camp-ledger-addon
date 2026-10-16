"""Explicit platform imports. Only supplied page text/images are read; no login crawl."""
import base64,binascii,hashlib,io,json,re,uuid
from datetime import datetime,timezone
from PIL import Image,ImageOps,UnidentifiedImageError
from .reservation_import import review_records,identity
MAX_BOOKINGS=100
CANCELLED=re.compile(r'취소\s*완료|예약(?:이|가)\s*취소|취소된\s*예약|예약\s*취소됨')
PROVIDERS={'camfit':'캠핏','thankq':'땡큐캠핑','campingtalk':'캠핑톡','naver':'네이버'}
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
 account=raw.get('account',1)
 if type(account) is not int or account not in (1,2):raise ValueError('계정 1 또는 계정 2를 선택해주세요.')
 ref={'provider':raw['provider'],'booking_id':ident,'account':account}
 for key in ('source_key','text_hash'):
  value=raw.get(key,'')
  if not isinstance(value,str) or value and not re.fullmatch(r'[a-f0-9]{64}',value):raise ValueError('동기화 이력을 확인해주세요.')
  ref[key]=value
 return ref

def source_key(fields,ref):
 value=('id',ref['booking_id']) if ref['booking_id'] else ('stay',identity(fields))
 return hashlib.sha256(json.dumps([ref['provider'],value] if ref.get('account',1)==1 else [ref['provider'],2,value],ensure_ascii=False).encode()).hexdigest()

def sync_state(c):
 states={provider:{str(account):{'booking_ids':set(),'text_hashes':set(),'last_synced':None} for account in (1,2)} for provider in PROVIDERS}
 for row in c.execute('SELECT provider,booking_id,text_hash,synced_at,account FROM platform_sync_history'):
  if row['provider'] not in states:continue
  state=states[row['provider']][str(row['account'])]
  if row['booking_id']:state['booking_ids'].add(row['booking_id'])
  if row['text_hash']:state['text_hashes'].add(row['text_hash'])
  state['last_synced']=max(state['last_synced'] or '',row['synced_at'])
 for row in c.execute('SELECT body FROM records'):
  ref=json.loads(row['body']).get('platform_ref',{});provider=ref.get('provider');account=str(ref.get('account',1))
  if provider in states and account in states[provider] and ref.get('booking_id'):states[provider][account]['booking_ids'].add(ref['booking_id'])
 for row in c.execute('SELECT provider,account,label FROM platform_accounts'):
  if row['provider'] in states and str(row['account']) in states[row['provider']]:states[row['provider']][str(row['account'])]['label']=row['label']
 result={}
 for provider,accounts in states.items():
  for account,state in accounts.items():
   state['label']=state.get('label') or '계정 '+account
   for key in ('booking_ids','text_hashes'):state[key]=sorted(state[key])
  result[provider]={**accounts['1'],'accounts':accounts}
 return result

def match_record(records,fields,ref):
 if ref['booking_id']:
  matches=[r for r in records if r.get('platform_ref',{}).get('provider')==ref['provider'] and r.get('platform_ref',{}).get('booking_id')==ref['booking_id']]
  if len(matches)>1:raise ValueError('같은 예약 번호가 여러 기록에 있습니다. 기존 기록을 확인해주세요.')
  if matches:return matches[0]
 matches=[r for r in records if fields.get('checkin') and fields.get('checkout') and identity(r)==identity(fields)]
 if len(matches)>1:raise ValueError('같은 캠핑장·기간의 기록이 여러 개입니다. 기존 기록을 확인해주세요.')
 return matches[0] if matches else None

def preview(raw,records,history=()):
 if not isinstance(raw,dict) or raw.get('provider') not in PROVIDERS:raise ValueError('지원하는 플랫폼을 선택해주세요.')
 cards=raw.get('cards',[])
 if not isinstance(cards,list) or not 0<=len(cards)<=MAX_BOOKINGS:raise ValueError('예약 화면에서 동기화를 눌러주세요. 한 번에 100건까지 읽습니다.')
 account=raw.get('account',1)
 if type(account) is not int or account not in (1,2):raise ValueError('계정 1 또는 계정 2를 선택해주세요.')
 result=[];seen=set();already=raw.get('already_synced',0)
 if type(already) is not int or not 0<=already<=MAX_BOOKINGS:raise ValueError('동기화 제외 개수를 확인해주세요.')
 known={(r['provider'],r['sync_key']) for r in history}
 for card in cards:
  if not isinstance(card,dict) or not isinstance(card.get('text'),str) or len(card['text'])>8000:raise ValueError('예약 화면 내용을 확인해주세요.')
  text=card['text']
  cancelled=card.get('cancelled') is True or bool(CANCELLED.search(text))
  rows=review_records(text)
  if not rows:
   if not cancelled:continue
   rows=[{'name':'취소된 예약','notes':text,'checkin':'','checkout':''}]
  # Photos can only be associated with a card that resolves to one booking.
  photos=media_list(card.get('media',[])) if len(rows)==1 and not cancelled else []
  for row in rows:
   ref={'provider':raw['provider'],'account':account,'booking_id':booking_id(text) if len(rows)==1 else ''}
   row['platform']=PROVIDERS[ref['provider']]
   key=ref['booking_id'] or str(identity(row))
   if key in seen:continue
   seen.add(key);existing=match_record(records,row,ref) if not cancelled else None
   complete=bool(row.get('name') and row.get('checkin') and row.get('checkout'))
   ref['source_key']=source_key(row,ref) if complete or ref['booking_id'] else ''
   ref['text_hash']=hashlib.sha256(text.encode()).hexdigest() if len(rows)==1 and (complete or ref['booking_id']) else ''
   if not cancelled and (existing or (ref['provider'],ref['source_key']) in known):already+=1;continue
   merged={**row,'cancelled':cancelled}
   merged['platform_sync']=ref;merged['sync_existing']=None;merged['replace_cover']=False
   merged['sync_media']=[{'kind':p['kind'],'data':p['data']} for p in photos]
   gallery=next((p for p in photos if p['kind']=='gallery'),None)
   if gallery:merged['thumbnail']=gallery['data']
   merged['duplicate']=False;result.append(merged)
 limited=len(result)>MAX_BOOKINGS;result=result[:MAX_BOOKINGS]
 return {'records':result,'cancelled_count':sum(r['cancelled'] for r in result),'already_synced':already,'scan_truncated':limited or raw.get('scan_truncated') is True,'stopped_at_synced':raw.get('stopped_at_synced') is True,'scan_reason':'limit' if limited else raw.get('scan_reason','') if raw.get('scan_reason') in ('limit','time','checkpoint') else ''}

def commit(raw,connection,clean,reject_duplicate,media_root):
 rows=raw.get('records') if isinstance(raw,dict) else None
 if not isinstance(rows,list) or not 1<=len(rows)<=MAX_BOOKINGS:raise ValueError('동기화할 예약을 1~100건 선택해주세요.')
 prepared=[]
 for row in rows:
  if not isinstance(row,dict):raise ValueError('예약 내용을 확인해주세요.')
  if row.get('cancelled') is True:raise ValueError('취소된 예약은 등록할 수 없습니다.')
  ref=validate_ref(row.get('platform_sync'));fields=clean({k:v for k,v in row.items() if k!='rating'})
  if fields.get('platform')!=PROVIDERS[ref['provider']]:raise ValueError('연결한 플랫폼과 예약 플랫폼이 다릅니다.')
  if not fields.get('checkin') or not fields.get('checkout'):raise ValueError('동기화할 예약의 입실일·퇴실일을 선택해주세요.')
  if type(row.get('replace_cover',False)) is not bool:raise ValueError('대표 사진 선택을 확인해주세요.')
  prepared.append((fields,ref,media_list(row.get('sync_media',[])),row.get('replace_cover',False)))
 written=[];added=[];updated=[];photos_added=0;skipped=0
 try:
  with connection() as c:
   c.execute('BEGIN IMMEDIATE')
   for fields,ref,photos,replace in prepared:
    records=[{**json.loads(r['body']),'id':r['id']} for r in c.execute('SELECT * FROM records')]
    old=match_record(records,fields,ref);key=ref['source_key'] or source_key(fields,ref)
    if old or c.execute('SELECT 1 FROM platform_sync_history WHERE provider=? AND sync_key=?',(ref['provider'],key)).fetchone():skipped+=1;continue
    ident=uuid.uuid4().hex
    reject_duplicate(c,fields,None)
    body={**fields,'platform_ref':ref}
    c.execute('INSERT INTO records VALUES(?,?)',(ident,json.dumps(body,ensure_ascii=False)));added.append(ident)
    c.execute('INSERT INTO platform_sync_history(provider,sync_key,booking_id,text_hash,synced_at,account) VALUES(?,?,?,?,?,?)',(ref['provider'],key,ref['booking_id'],ref['text_hash'],datetime.now(timezone.utc).isoformat(),ref['account']))
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
 return {'added':added,'updated':updated,'photos_added':photos_added,'skipped':skipped}
