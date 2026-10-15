"""Local screenshot OCR and conservative reservation extraction; no external service."""
import io,re,subprocess,tempfile,unicodedata
from pathlib import Path
from PIL import Image,ImageOps,UnidentifiedImageError

def identity(record):
 return (re.sub(r'[\W_]+','',unicodedata.normalize('NFKC',str(record.get('name','')))).casefold(),record.get('checkin',''),record.get('checkout',''))

def parse_reservations(text):
 text=re.sub(r'\b(2[0-9])([01][0-9])\.(\d{1,2})',r'\1.\2.\3',text)
 lines=[re.sub(r'\s+',' ',line).strip() for line in text.splitlines() if line.strip()]
 pattern=re.compile(r'(\d{2,4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})\s*\(?[월화수목금토일]?\)?\s*[~–—-]\s*(\d{2,4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})')
 from datetime import date
 result=[];seen=set()
 for i,line in enumerate(lines):
  match=pattern.search(line)
  if not match:continue
  values=list(map(int,match.groups()))
  try:
   start=date(values[0]+2000 if values[0]<100 else values[0],*values[1:3]).isoformat();end=date(values[3]+2000 if values[3]<100 else values[3],*values[4:6]).isoformat()
  except ValueError:continue
  if end<start:continue
  candidates=[(n,lines[n]) for n in range(max(0,i-5),i) if re.search('캠핑|야영장',lines[n]) and not re.search(r'로그|예약번호|결제|이용완료|사이트|선착순|[ㆍ·]\s*\d+\s*명',lines[n])]
  if not candidates:continue
  n,name=candidates[-1];name=re.sub(r'^[△▶•\s]+','',name).strip()
  site=' · '.join(lines[n+1:i]);site=re.sub(r'\s*[·ㆍ]\s*\d+\s*명.*$','',site).strip()
  record={'name':name,'site':site,'checkin':start,'checkout':end}
  key=identity(record)
  if key not in seen:seen.add(key);result.append(record)
 return result

def image_text(file):
 # Decode and normalize into a bounded local image before invoking OCR.
 try:original=Image.open(file.stream)
 except (UnidentifiedImageError,OSError,Image.DecompressionBombError):raise ValueError('읽을 수 있는 이미지 파일을 선택해주세요.')
 with original:
  if original.width*original.height>25000000:raise ValueError('사진은 2,500만 화소 이하로 선택해주세요.')
  image=ImageOps.exif_transpose(original).convert('RGB');image.thumbnail((2600,5000))
  if image.width<1200:image=image.resize((image.width*2,image.height*2))
  with tempfile.TemporaryDirectory(prefix='camp-ocr-') as directory:
   def recognize(picture,name):
    path=Path(directory)/(name+'.png');picture.save(path)
    try:result=subprocess.run(['tesseract',str(path),'stdout','-l','kor+eng','--psm','6'],capture_output=True,text=True,timeout=20)
    except FileNotFoundError:raise ValueError('사진 인식 구성요소가 없습니다. 인식할 글자를 직접 붙여넣어주세요.')
    except subprocess.TimeoutExpired:raise ValueError('사진 인식 시간이 초과됐습니다. 사진을 잘라 다시 선택해주세요.')
    if result.returncode:raise ValueError('사진에서 글자를 읽지 못했습니다. 다른 사진이나 직접 입력을 사용해주세요.')
    return result.stdout[:50000]
   full=recognize(image,'full');rows=parse_reservations(full)
   # Thumbnails beside text can become stray Latin words in the recognized name.
   # Compare a text-side pass; the user still reviews every result before saving.
   side=recognize(image.crop((int(image.width*.30),0,image.width,image.height)),'text-side');side_rows=parse_reservations(side)
   if len(side_rows)>len(rows) or (side_rows and len(side_rows)==len(rows) and any(re.match(r'^[A-Za-z]',r['name']) for r in rows)):return side
   return full

def parse_reservation_text(text):
 """Extract only booking fields; recipient names and the original clipboard are not stored."""
 from datetime import date,timedelta
 text=unicodedata.normalize('NFKC',text).replace('\r','')[:10000]
 if re.search(r'예약\s*취소|취소\s*완료|취소되었',text):return []
 rows=parse_reservations(text)
 if rows:return rows
 pattern=r'(20\d{2})[./-](\d{1,2})[./-](\d{1,2})'
 dates=list(re.finditer(pattern,text));duration=re.search(r'(\d{1,3})\s*박',text)
 start_match=re.search(r'(?:입실(?:일)?|체크인|이용시작)\s*[:：]?\s*'+pattern,text)
 end_match=re.search(r'(?:퇴실(?:일)?|체크아웃|이용종료)\s*[:：]?\s*'+pattern,text)
 if not dates:return []
 def as_date(match):return date(*map(int,match.groups()[-3:]))
 try:
  start=as_date(start_match or dates[0])
  if end_match:end=as_date(end_match)
  elif duration:
   nights=int(duration.group(1))
   if not 1<=nights<=366:return []
   end=start+timedelta(days=nights)
  elif len(dates)>1:end=as_date(dates[1])
  else:return []
 except ValueError:return []
 if not 0<=(end-start).days<=366:return []
 named=re.search(r'(?:캠핑장명|캠핑장|업체명|숙소명)\s*[:：]\s*([^\n,]+)',text)
 tail=re.search(r'(?:완료|확정)\s*[!！:：~\s]*([^,\n]+)\s*$',text)
 if named:name=named.group(1).strip()
 elif tail and re.search(r'캠프|캠핑|야영장|목장|휴양림|글램핑|카라반',tail.group(1)):name=tail.group(1).strip()
 else:
  candidates=[line.strip() for line in text.splitlines() if re.search(r'캠프|캠핑장|야영장|글램핑|카라반',line) and not re.search(pattern,line) and not re.search(r'예약번호|http|고객센터|취소|입실|퇴실',line)]
  name=candidates[0] if len(candidates)==1 else ''
 if not name or len(name)>200:return []
 site=re.search(r'(?:사이트명|사이트|자리|구역)\s*[:：]\s*([^,\n]+)',text)
 if site:site=site.group(1).strip()
 elif ',' in text[:dates[0].start()]:site=text[:dates[0].start()].rstrip(' ,').split(',')[-1].strip()
 else:site=''
 row={'name':name,'site':site,'checkin':start.isoformat(),'checkout':end.isoformat()}
 amount=re.search(r'(?:결제금액|이용금액|총금액|금액|요금)\s*[:：]?\s*([\d,]+)\s*원',text)
 if amount:row['price']=int(amount.group(1).replace(',',''))
 for platform in ('캠핏','땡큐캠핑','네이버','캠핑톡'):
  if platform in text:row['platform']=platform;break
 return [row]
