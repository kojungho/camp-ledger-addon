"""Keyless campsite search using attributed, publicly licensed datasets."""
import json,re
from pathlib import Path
CATALOG=json.loads((Path(__file__).parent/'static/data/campsites.json').read_text())
def norm(text):return re.sub(r'[^가-힣a-z0-9]','',text.lower())
def search(query):
 query=query.strip()
 if not query or len(query)>200:return {'error':'캠핑장명 또는 지역과 캠핑장명을 입력해주세요.'},400
 tokens=[norm(t) for t in query.split() if norm(t)]
 if not tokens:return {'error':'캠핑장명을 입력해주세요.'},400
 matches=[];nq=norm(query)
 for r in CATALOG['records']:
  name=norm(r['name']);full=name+norm(r['address'])
  if all(t in full for t in tokens):
   score=0 if name==nq else 1 if nq in name else 2
   matches.append((score,r['lat'] is None,r['name'],r))
 matches.sort(key=lambda x:x[:3])
 return {'results':[r for *_,r in matches[:30]],'total':len(matches),'sources':CATALOG['sources']},200
