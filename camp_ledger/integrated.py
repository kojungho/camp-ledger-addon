"""One add-on, two isolated stores, retained standalone URLs and device keys."""
import os,io,json,sqlite3,zipfile,tempfile,hashlib,re,threading
from pathlib import Path
from flask import request,jsonify,abort
from werkzeug.middleware.dispatcher import DispatcherMiddleware
LOCK=threading.RLock()
def combined_app(ledger,channel):
 from journal.app import app as journal
 dispatched=DispatcherMiddleware(ledger,{'/journal':journal})
 def application(environ,start_response):
  environ['camp.entrypoint']=environ['journal.entrypoint']=channel
  if environ.get('PATH_INFO','').startswith('/journal'):
   with LOCK:return dispatched(environ,start_response)
  return dispatched(environ,start_response)
 return application

def install_integration(ledger,mobile):
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
