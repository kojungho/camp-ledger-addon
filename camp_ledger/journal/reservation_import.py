"""Local screenshot OCR and conservative reservation extraction; no external service."""
import io,re,subprocess,tempfile,unicodedata,os,time,threading,base64,binascii
from pathlib import Path
from PIL import Image,ImageOps,UnidentifiedImageError

def identity(record):
 return (re.sub(r'[\W_]+','',unicodedata.normalize('NFKC',str(record.get('name','')))).casefold(),record.get('checkin',''),record.get('checkout',''))

def parse_timeline(lines):
 """Extract incomplete visit entries without inventing a year or checkout date."""
 result=[];seen=set();date_hint=''
 category=re.compile(r'캠핑\s*[,，.·ㆍ]?\s*야영장')
 for i,line in enumerate(lines):
  month_day=re.fullmatch(r'(\d{1,2})\s*[./]\s*(\d{1,2})\s*([월화수목금토일])?',line)
  if month_day:
   month,day=map(int,month_day.groups()[:2])
   try:
    from datetime import date
    date(2000,month,day)
   except ValueError:continue
   date_hint=f'{month}.{day}'+(' '+month_day.group(3) if month_day.group(3) else '')
  match=category.search(line)
  if not match or i==0:continue
  name=lines[i-1]
  name=re.sub(r'^[^\w가-힣]+','',name)
  name=re.sub(r'^[a-z]{1,3}\s+(?=[가-힣])','',name)
  name=re.sub(r'\s*[★☆*⋮:;]+.*$','',name).strip()
  if not name or re.search(r'방문|예약|리뷰|^\d+[./]\d+',name):continue
  location=line[match.end():].strip(' ·ㆍ.,:：')
  site='';price=None
  for following in lines[i+1:i+6]:
   if category.search(following) or re.fullmatch(r'\d{1,2}[./]\d{1,2}.*',following):break
   amount=re.search(r'([\d,]+)\s*원',following)
   if amount:
    price=int(amount.group(1).replace(',',''));site=following[:amount.start()].strip(' ·ㆍ.,:：')
    site=re.sub(r'^(?:디|티|그|[Ilㅣ])\s+(?=[0-9A-Za-z])','',site);break
  if price is None or not location or not date_hint:continue
  row={'name':name,'location':location,'site':site,'price':price,'checkin':'','checkout':'','date_hint':date_hint,'needs_dates':True}
  key=(name,date_hint,site)
  if key not in seen:seen.add(key);result.append(row)
 return result

def parse_reservations(text):
 text=re.sub(r'\b(2[0-9])([01][0-9])\.(\d{1,2})',r'\1.\2.\3',text)
 lines=[re.sub(r'\s+',' ',line).strip() for line in text.splitlines() if line.strip()]
 pattern=re.compile(r'(\d{2,4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})\s*\(?[월화수목금토일]?\)?\s*[~–—-]\s*(\d{2,4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})')
 from datetime import date,timedelta
 result=[];seen=set();previous_range=-1
 for i,line in enumerate(lines):
  match=pattern.search(line)
  if not match:continue
  lower=max(0,i-5,previous_range+1);previous_range=i
  values=list(map(int,match.groups()))
  try:
   start=date(values[0]+2000 if values[0]<100 else values[0],*values[1:3]).isoformat();end=date(values[3]+2000 if values[3]<100 else values[3],*values[4:6]).isoformat()
  except ValueError:continue
  if end<start:continue
  candidates=[(n,lines[n]) for n in range(lower,i) if re.search('캠핑|야영장',lines[n]) and not re.search(r'로그|예약번호|결제|이용완료|사이트|선착순|[ㆍ·]\s*\d+\s*명',lines[n])]
  if not candidates:continue
  n,name=candidates[-1];name=re.sub(r'^[^\w가-힣]+','',name).strip()
  site=' · '.join(lines[n+1:i]);site=re.sub(r'\s*[·ㆍ]\s*\d+\s*명.*$','',site).strip()
  record={'name':name,'site':site,'checkin':start,'checkout':end}
  key=identity(record)
  if key not in seen:seen.add(key);result.append(record)
 # Some platforms show a start date and number of nights instead of a range.
 previous=-1
 for i,line in enumerate(lines):
  match=re.search(r'(20\d{2})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})\s*\(?\s*(\d{1,3})\s*박',line)
  if not match:continue
  try:
   year,month,day,nights=map(int,match.groups());start=date(year,month,day)
   if not 1<=nights<=366:continue
   end=start+timedelta(days=nights)
  except ValueError:continue
  candidates=[lines[n] for n in range(max(0,i-5,previous+1),i) if re.search('캠핑|캠프|야영장|글램핑|카라반',lines[n]) and not re.search('예약번호|예약정보|후기|재예약|사이트',lines[n])]
  previous=i
  if not candidates:continue
  name=re.sub(r'^[^\w가-힣]+','',candidates[-1]).strip();site=''
  for following in lines[i+1:i+3]:
   m=re.search(r'예약\s*정보\s*[:：]\s*(.*)',following)
   if m:site=m.group(1).strip();break
  row={'name':name,'site':site,'checkin':start.isoformat(),'checkout':end.isoformat()}
  if identity(row) not in seen:seen.add(identity(row));result.append(row)
 # Separate check-in/check-out columns (dates may be on one or two OCR lines).
 date_pattern=re.compile(r'(\d{2,4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})')
 for i,line in enumerate(lines):
  if not re.search('입실|퇴실|체크인|체크아웃',line):continue
  section=' '.join(lines[i:i+4]);dates=date_pattern.findall(section)
  if len(dates)<2:continue
  try:
   values=[list(map(int,v)) for v in dates[:2]]
   start,end=[date(v[0]+2000 if v[0]<100 else v[0],v[1],v[2]) for v in values]
  except ValueError:continue
  if not 0<=(end-start).days<=366:continue
  candidates=[(n,lines[n]) for n in range(max(0,i-7),i) if re.search('캠핑|캠프|야영장|글램핑|카라반',lines[n]) and not re.search('예약번호|예약정보|후기|재예약|사이트|중개|거래',lines[n])]
  if not candidates:continue
  n,name=candidates[-1];name=re.sub(r'^[^\w가-힣]+','',name).strip();site=' · '.join(lines[n+1:i]);site=re.sub(r'^예약\s*정보\s*[:：]\s*','',site).strip()
  row={'name':name,'site':site,'checkin':start.isoformat(),'checkout':end.isoformat()}
  if identity(row) not in seen:seen.add(identity(row));result.append(row)
 return result or parse_timeline(lines)

def thumbnail_boxes(image):
 """Find dense photo blocks in the left column; exclude short badges/text lines."""
 width,height=image.size;small=image.resize((min(width,600),round(height*min(width,600)/width)))
 w,h=small.size;x0,x1=round(w*.035),round(w*.285);pixels=small.load();hits=[]
 for y in range(h):
  count=sum(1 for x in range(x0,x1) if min(pixels[x,y])<210)
  hits.append(count>=(x1-x0)*.42)
 # Close small gaps caused by a light area in a photo, not the white card margins.
 gap=max(2,round(w*.012));runs=[];start=None;last=None
 for y,hit in enumerate(hits+[False]*(gap+1)):
  if hit:
   if start is None:start=y
   last=y
  elif start is not None and y-last>gap:
   if w*.09<=last-start+1<=w*.5:runs.append((start,last+1))
   start=None
 boxes=[];scale=width/w
 for top,bottom in runs:
  columns=[x for x in range(x0,x1) if sum(min(pixels[x,y])<225 for y in range(top,bottom))>(bottom-top)*.4]
  if not columns:continue
  left,right=min(columns),max(columns)+1
  if right-left<w*.08 or not .55<=(right-left)/(bottom-top)<=1.8:continue
  boxes.append(tuple(round(v*scale) for v in (left,top,right,bottom)))
 return boxes[:100]

def thumbnail_data(image,box):
 photo=image.crop(box);photo.thumbnail((480,480));out=io.BytesIO();photo.save(out,'JPEG',quality=88)
 return 'data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode('ascii')

def decode_thumbnail(value):
 if value is None:return None
 if not isinstance(value,str) or not value.startswith('data:image/jpeg;base64,') or len(value)>1000000:raise ValueError('예약 사진을 확인해주세요.')
 try:
  content=base64.b64decode(value.split(',',1)[1],validate=True)
  with Image.open(io.BytesIO(content)) as photo:
   if photo.format!='JPEG' or photo.width*photo.height>1000000:raise ValueError('예약 사진 크기를 확인해주세요.')
   photo.load();photo=ImageOps.exif_transpose(photo).convert('RGB');photo.thumbnail((480,480));out=io.BytesIO();photo.save(out,'JPEG',quality=90);return out.getvalue()
 except (binascii.Error,UnidentifiedImageError,OSError,Image.DecompressionBombError):raise ValueError('예약 사진을 읽을 수 없습니다.')

OCR_SLOT=threading.BoundedSemaphore(1)

def image_text(file,with_records=False):
 try:original=Image.open(file.stream)
 except (UnidentifiedImageError,OSError,Image.DecompressionBombError):raise ValueError('읽을 수 있는 이미지 파일을 선택해주세요.')
 with original:
  if original.width*original.height>25000000:raise ValueError('사진은 2,500만 화소 이하로 선택해주세요.')
  image=ImageOps.exif_transpose(original).convert('RGB');image.thumbnail((1800,7000))
 if not OCR_SLOT.acquire(timeout=3):raise ValueError('다른 사진을 인식 중입니다. 잠시 후 다시 선택해주세요.')
 try:
  with tempfile.TemporaryDirectory(prefix='camp-ocr-') as directory:
   deadline=time.monotonic()+50;timed_out=False;outputs=[]
   def recognize(picture,name,limit=20):
    # Enlarge text, not the photograph-filled whole screenshot. Keep a bounded canvas.
    if picture.width<1100:
     scale=min(1.5,1100/picture.width);picture=picture.resize((round(picture.width*scale),round(picture.height*scale)),Image.Resampling.LANCZOS)
    picture.thumbnail((1500,6500));picture=ImageOps.expand(ImageOps.grayscale(picture),border=12,fill='white')
    path=(Path(directory)/(name+'.png')).resolve();picture.save(path)
    args=['tesseract',str(path),'stdout','-l','kor+eng','--psm','6']
    models=Path(os.getenv('CAMP_OCR_MODELS','/app/ocr-models'))
    if (models/'kor.traineddata').is_file():args.extend(['--tessdata-dir',str(models)])
    try:result=subprocess.run(args,capture_output=True,text=True,timeout=max(1,min(limit,deadline-time.monotonic())),env={**os.environ,'OMP_THREAD_LIMIT':'1','OMP_NUM_THREADS':'1'})
    except FileNotFoundError:raise ValueError('사진 인식 구성요소가 없습니다. 인식할 글자를 직접 붙여넣어주세요.')
    if result.returncode:raise ValueError('사진에서 글자를 읽지 못했습니다. 다른 사진이나 직접 입력을 사용해주세요.')
    return result.stdout[:50000]
   def output(text,rows=None):
    return {'text':text,'records':rows if rows is not None else parse_reservations(text)} if with_records else text
   boxes=thumbnail_boxes(image)
   if boxes:
    parts=[];rows=[]
    for index,box in enumerate(boxes):
     if time.monotonic()>=deadline:break
     left,top,right,bottom=box
     # The title/site are beside the photo; some platforms place dates below it.
     title=image.crop((max(right+4,round(image.width*.28)),max(0,top-round(image.width*.025)),image.width,bottom))
     lower=min(image.height,bottom+round(image.width*.32),boxes[index+1][1]-round(image.width*.11) if index+1<len(boxes) else image.height)
     below=image.crop((round(image.width*.035),bottom,round(image.width*.965),max(bottom,lower)))
     picture=Image.new('RGB',(max(title.width,below.width),title.height+below.height+15),'white');picture.paste(title,(0,0));picture.paste(below,(0,title.height+15))
     try:text=recognize(picture,'card-'+str(index),limit=12)
     except subprocess.TimeoutExpired:timed_out=True;continue
     parts.append(text);found=parse_reservations(text)
     # Only attach a crop when this bounded card contains exactly one reservation.
     if len(found)==1:found[0]['thumbnail']=thumbnail_data(image,box)
     rows.extend(found)
    if rows:return output('\n'.join(parts),rows)
   # Booking cards place photos on the left. Try their text column first; fall back
   # to the whole image for other layouts. A successful pass is never discarded.
   pictures=[(image.crop((int(image.width*.29),0,image.width,image.height)),'text-side'),(image,'full')]
   for picture,name in pictures:
    if time.monotonic()>=deadline:break
    try:text=recognize(picture,name)
    except subprocess.TimeoutExpired:timed_out=True;continue
    outputs.append(text)
    rows=parse_reservations(text)
    dated_lines=sum(bool(re.search(r'\d[./]\s*\d{1,2}.*[~–—-].*\d[./]\s*\d{1,2}',line)) for line in text.splitlines())
    if rows and not any(row.get('needs_dates') for row in rows) and len(rows)>=dated_lines:return output(text)
   if outputs:
    best=max(reversed(outputs),key=lambda text:len(parse_reservations(text)))
    if parse_reservations(best) or not timed_out:return output(best)
   if timed_out:raise ValueError('사진 인식 시간이 초과됐습니다. 예약 내용 부분만 잘라 다시 선택해주세요.')
   return output('')
 finally:OCR_SLOT.release()

def parse_reservation_text(text):
 """Extract only booking fields; recipient names and the original clipboard are not stored."""
 from datetime import date,timedelta
 text=unicodedata.normalize('NFKC',text).replace('\r','')[:10000]
 if re.search(r'예약\s*취소|취소\s*완료|취소되었',text):return []
 rows=parse_reservations(text)
 if rows and not any(row.get('needs_dates') for row in rows) and not re.search(r'(?:캠핑장명|캠핑장|업체명|숙소명)\s*[:：]',text):return rows
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
