"""One add-on, two isolated stores, retained standalone URLs and device keys."""
import os,io,json,sqlite3,zipfile,tempfile,hashlib,re,threading,time
from urllib.parse import urlparse,urlunparse
from pathlib import Path
from flask import request,jsonify,abort
from werkzeug.middleware.dispatcher import DispatcherMiddleware
LOCK=threading.RLock()
def combined_app(ledger,channel):
 from journal.app import app as journal,connection,get_settings
 if not ledger.config.get('CAMP_SHARED_ACCESS'):
  ledger_store=ledger.config['CAMP_STORE'];journal_store=(connection,get_settings,'/campsite-journal/')
  ledger.config['CAMP_SHARED_ACCESS']=SharedAccess(ledger_store,journal_store)
  journal.config['CAMP_SHARED_ACCESS']=SharedAccess(journal_store,ledger_store)
 dispatched=DispatcherMiddleware(ledger,{'/journal':journal})
 def application(environ,start_response):
  environ['camp.unified']=True
  environ['camp.entrypoint']=environ['journal.entrypoint']=channel
  if environ.get('PATH_INFO','').startswith('/journal'):
   with LOCK:return dispatched(environ,start_response)
  return dispatched(environ,start_response)
 return application

def install_integration(ledger,mobile,connection,get_settings):
 ledger.config['CAMP_STORE']=(connection,get_settings,'/camp-ledger/')
 @ledger.get('/hub')
 def hub():return ledger.send_static_file('hub.html')
 @ledger.post('/api/integration/import-journal')
 def import_journal():
  if not mobile['admin']():abort(403)
  from journal.app import DATA,MEDIA,connection
  upload=request.files.get('archive')
  if not upload:raise ValueError('이전할 기록 백업을 선택해주세요.')
  # Staging avoids partial data on bad archives. Only an empty journal is imported.
  with tempfile.TemporaryDirectory(dir=DATA.parent,prefix='.journal-import-') as directory:
   staging=Path(directory)
   try:
    with zipfile.ZipFile(upload.stream) as archive:
     members=archive.infolist()
     if len(members)>100000 or sum(m.file_size for m in members)>4*1024**3:raise ValueError('이전 백업 크기를 확인해주세요.')
     if len({m.filename for m in members})!=len(members):raise ValueError('중복된 백업 경로입니다.')
     for member in members:
      name=member.filename
      if not (name in ('journal.sqlite3','manifest.json','geocode-cache.sqlite3') or re.fullmatch(r'photos/[a-zA-Z0-9_-]+\.jpg',name)):raise ValueError('허용되지 않은 백업 경로입니다.')
      path=staging/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(archive.read(member))
    manifest=json.loads((staging/'manifest.json').read_text())
    if set(manifest['sha256'])!={m.filename for m in members}-{'manifest.json'}:raise ValueError('백업 파일 목록이 일치하지 않습니다.')
    for name,digest in manifest['sha256'].items():
     if name not in {m.filename for m in members} or hashlib.sha256((staging/name).read_bytes()).hexdigest()!=digest:raise ValueError('백업 파일 검증에 실패했습니다.')
    source=sqlite3.connect(staging/'journal.sqlite3')
    try:
     if source.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('기록 데이터베이스 검증에 실패했습니다.')
     if source.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('기록과 사진 연결을 확인해주세요.')
     counts={table:source.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ('records','photos','devices')}
     for ident, in source.execute('SELECT id FROM photos'):
      if not re.fullmatch(r'[a-zA-Z0-9_-]+',ident) or not (staging/'photos'/(ident+'.jpg')).is_file():raise ValueError('사진 파일이 누락됐습니다.')
     if counts!=manifest['counts']:raise ValueError('기록 개수가 백업과 다릅니다.')
    finally:source.close()
    with LOCK:
     with connection() as current:
      if current.execute('SELECT COUNT(*) FROM records').fetchone()[0] or current.execute('SELECT COUNT(*) FROM devices').fetchone()[0]:raise ValueError('이미 기록이나 연결 정보가 있습니다. 덮어쓰지 않습니다.')
     # All checked files remain on the same volume for atomic replacement.
     MEDIA.mkdir(exist_ok=True)
     for photo in (staging/'photos').glob('*.jpg'):os.replace(photo,MEDIA/photo.name)
     os.replace(staging/'journal.sqlite3',DATA/'journal.sqlite3')
     if (staging/'geocode-cache.sqlite3').exists():os.replace(staging/'geocode-cache.sqlite3',DATA/'geocode-cache.sqlite3')
    return jsonify(ok=True,counts=counts,sha256=manifest['sha256'])
   except (zipfile.BadZipFile,KeyError,sqlite3.Error,json.JSONDecodeError) as error:raise ValueError('기록 백업 형식이 올바르지 않습니다.') from error


class SharedAccess:
 """Existing device hashes remain in place; either enabled store grants both views."""
 def __init__(self,own,peer):self.own=own;self.peer=peer
 def valid_peer(self,key):
  if not isinstance(key,str) or not 32<=len(key)<=100:return None
  connection,settings,_=self.peer
  with connection() as c:
   if not settings(c).get('mobile',{}).get('enabled'):return None
   row=c.execute('SELECT id,last_used FROM devices WHERE token_hash=?',(hashlib.sha256(key.encode()).hexdigest(),)).fetchone()
   if row:c.execute('UPDATE devices SET last_used=? WHERE id=?',(time.time(),row['id']))
   return row
 def devices(self):
  rows=[];seen=set()
  for prefix,(connection,_,_) in [('',self.own),('peer:',self.peer)]:
   with connection() as c:
    for row in c.execute('SELECT * FROM devices ORDER BY created DESC'):
     if row['token_hash'] in seen:continue
     seen.add(row['token_hash']);rows.append({k:row[k] for k in ('name','created','last_used')}|{'id':prefix+row['id']})
  return sorted(rows,key=lambda row:row['created'],reverse=True)
 def revoke(self,ident):
  store=self.peer if ident.startswith('peer:') else self.own;ident=ident.removeprefix('peer:')
  with LOCK:
   with store[0]() as c:row=c.execute('SELECT token_hash FROM devices WHERE id=?',(ident,)).fetchone()
   if row:
    for connection,_,_ in (self.own,self.peer):
     with connection() as c:c.execute('DELETE FROM devices WHERE token_hash=?',(row['token_hash'],))
 def sync_config(self,prefs):
  connection,settings,path=self.peer;parsed=urlparse(prefs['external_url'])
  with connection() as c:
   s=settings(c);s['mobile']={'enabled':prefs['enabled'],'external_url':urlunparse((parsed.scheme,parsed.netloc,path,'','','')) if parsed.netloc else ''};c.execute('UPDATE settings SET body=? WHERE id=1',(json.dumps(s,ensure_ascii=False),))
 def cookies(self,response,key):
  for connection,settings,fallback in (self.own,self.peer):
   with connection() as c:path=urlparse(settings(c).get('mobile',{}).get('external_url','')).path or fallback
   response.set_cookie('campsite_device' if fallback=='/campsite-journal/' else 'camp_device',key,max_age=60*60*24*365*5,secure=True,httponly=True,samesite='Strict',path=path)
  return response
 def apk(self):return Path(__file__).parent/'journal/static/downloads/camp-note.apk'
