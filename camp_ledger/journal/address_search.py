"""Small, cached, rate-limited lookup for campsite location suggestions."""
import json,os,sqlite3,time,threading
from pathlib import Path
from contextlib import closing
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
LOCK=threading.Lock();last_request=0.0

def search(query):
 global last_request
 query=' '.join(query.split())
 if not 2<=len(query)<=200:return {'error':'검색할 주소를 2~200자로 입력해주세요.'},400
 path=Path(os.getenv('JOURNAL_DATA','./.local-data'));path.mkdir(parents=True,exist_ok=True)
 with LOCK,closing(sqlite3.connect(path/'geocode-cache.sqlite3')) as c,c:
  c.execute('CREATE TABLE IF NOT EXISTS cache(query TEXT PRIMARY KEY,body TEXT,created REAL)')
  cached=c.execute('SELECT body FROM cache WHERE query=? AND created>?',(query,time.time()-30*86400)).fetchone()
  if cached:return json.loads(cached[0]),200
  wait=1.1-(time.monotonic()-last_request)
  if wait>0:time.sleep(wait)
  last_request=time.monotonic()
  url='https://photon.komoot.io/api/?'+urlencode({'q':query,'limit':5,'bbox':'124,33,132,39'})
  req=Request(url,headers={'User-Agent':'CampsiteJournal/1.0.5 (+https://github.com/kojungho/campsite-journal-addon)','Accept':'application/json'})
  try:
   with urlopen(req,timeout=10) as r:raw=json.load(r)
  except (HTTPError,URLError,TimeoutError,OSError,ValueError):return {'error':'무료 지도 위치 조회를 사용할 수 없습니다. 지도에서 직접 위치를 눌러 선택하거나 주소만 저장할 수 있습니다.'},502
  results=[]
  for f in raw.get('features',[])[:5]:
   try:lng,lat=map(float,f['geometry']['coordinates'][:2])
   except (KeyError,ValueError,TypeError):continue
   if not 33<=lat<=39 or not 124<=lng<=132:continue
   p=f.get('properties',{});text=' '.join(str(p[k]) for k in ['state','city','district','street','housenumber','name'] if p.get(k))
   results.append({'address':text or query,'lat':lat,'lng':lng})
  result={'results':results,'provider':'Photon / OpenStreetMap'}
  c.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)',(query,json.dumps(result,ensure_ascii=False),time.time()))
 return result,200
