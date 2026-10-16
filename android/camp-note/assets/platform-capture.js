(function(){
 'use strict';
 if(document.querySelector('input[type="password"]'))return JSON.stringify({error:'로그인한 뒤 예약 내역 화면에서 동기화를 눌러주세요.'});
 const visible=el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0};
 const text=el=>(el.innerText||'').trim();
 const dated=value=>/(?:20\d{2}|\d{2})\s*[.\/-]\s*\d{1,2}\s*[.\/-]\s*\d{1,2}|\d{1,2}월\s*\d{1,2}일|(?:^|\n)\s*\d{1,2}[./]\d{1,2}\s*\(?[월화수목금토일]\)?/.test(value);
 const named=el=>/캠핑장|캠프|야영장|글램핑/.test(text(el))||[...el.querySelectorAll('h1,h2,h3,h4,strong')].some(title=>{const value=text(title);return value.length>=2&&value.length<=80&&!/입실|퇴실|예약|일정|금액|완료|취소|로그인/.test(value)});
 // Detail pages split the date, title and cancellation banner into unrelated sections.
 // Read one booking as a whole, but send only booking fields (never refund/bank/customer sections).
 const bodyText=text(document.body),lines=bodyText.split(/\n+/).map(v=>v.trim()).filter(Boolean);
 const detailSections=(bodyText.match(/예약자\s*정보|결제\s*정보|환불\s*(?:예정\s*)?정보|환불\s*계좌\s*정보/g)||[]).length;
 const bookingIds=[...bodyText.matchAll(/예약\s*(?:번호|코드)\s*[:：#]?\s*([A-Za-z0-9][A-Za-z0-9_-]{4,79})/g)];
 const detailDates=[...bodyText.matchAll(/(?<![\d.])(?:(\d{4}|\d{2})\s*[./-]\s*)?(\d{1,2})\s*[./-]\s*(\d{1,2})\s*\([월화수목금토일]\)/g)];
 const detailCancelled=/예약(?:이|가)\s*취소(?:되었습니다|됐습니다|되었어요|됐어요|됨)|취소\s*완료|취소된\s*예약/.test(bodyText);
 let detail=null;
 if(detailSections>=2&&bookingIds.length===1&&(detailDates.length>=2||dated(bodyText))){
  const field=labels=>{for(let i=0;i<lines.length;i++){const m=lines[i].match(new RegExp('^(?:'+labels+')\\s*[:：]?\\s*(.*)$'));if(m)return m[1]||lines[i+1]||''}return ''};
  const names=lines.filter(v=>/캠핑장|캠프|야영장|글램핑|카라반|목장|휴양림/.test(v)&&v.length<=100&&!/예약|결제|환불|취소|이용|약관|플랫폼|중개|고객|주의/.test(v));
  const headings=[...document.body.querySelectorAll('h1,h2,h3,h4,strong')].map(text).filter(v=>v.length>=2&&v.length<=80&&!/예약|결제|환불|취소|계좌|정보|안내|금액|약관|고객|주의/.test(v));
  const name=field('캠핑장명|업체명|숙소명')||names[0]||headings[0]||'';
  const normalized=[];if(name)normalized.push('캠핑장명: '+name);
  normalized.push('예약번호: '+bookingIds[0][1]);
  if(detailDates.length>=2){normalized.push('입실일: '+detailDates[0][0]);normalized.push('퇴실일: '+detailDates[1][0])}
  else for(const line of lines)if(/입실|퇴실|체크인|체크아웃/.test(line)&&dated(line))normalized.push(line);
  for(const [label,keys] of [['사이트명','사이트명|사이트|캠핑존|구역|객실명'],['주소','주소|위치|소재지'],['총금액','총 결제금액|총결제금액|총 금액|총금액|합계 금액|합계금액']]){const v=field(keys);if(v)normalized.push(label+': '+v)}
  if(detailCancelled)normalized.push('예약이 취소되었습니다');
  detail={text:normalized.join('\n'),cancelled:detailCancelled};
 }
 const candidates=[...document.querySelectorAll('article,li,section,[class*="reservation" i],[class*="booking" i]')].filter(el=>{if(!visible(el))return false;const value=text(el);return value.length>=15&&value.length<=8000&&dated(value)&&named(el)&&(/예약\s*(?:번호|정보|상세|내역|일|확정)|입실|퇴실|일정|이용완료|방문완료|다시\s*예약/.test(value))});
 const leaves=candidates.filter(el=>!candidates.some(child=>child!==el&&el.contains(child)&&named(child)));
 const cards=[],seen=new Set();
 for(const el of detail?[document.body]:leaves){
  const value=detail?detail.text:text(el);if(seen.has(value))continue;seen.add(value);
  const media=[];let gallery=false,layouts=0;
  for(const img of el.querySelectorAll('img')){
   const rect=img.getBoundingClientRect(),src=img.currentSrc||img.src||'';
   if(!/^https:\/\//i.test(src)||Math.max(rect.width,img.naturalWidth||0)<80||Math.max(rect.height,img.naturalHeight||0)<60)continue;
   if(/logo|icon|avatar|banner|로고|아이콘|프로필/i.test((img.alt||'')+' '+img.className))continue;
   const parent=img.closest('figure')||img.parentElement,near=parent&&parent.querySelectorAll('img').length===1&&text(parent).length<100?text(parent):'';
   const layout=/배치도|사이트\s*맵|구역도|안내도/.test((img.alt||'')+' '+near);
   if(layout&&layouts<3){media.push({kind:'layout',url:src});layouts++;}
   else if(!layout&&!gallery){media.push({kind:'gallery',url:src});gallery=true;}
  }
  const cancelled=!!detail?.cancelled||/취소\s*완료|예약(?:이|가)\s*취소|취소된\s*예약|예약\s*취소됨/.test(value)||[...el.querySelectorAll('[class*="status" i],[class*="badge" i],[class*="state" i]')].some(node=>!node.closest('button,a,[role="button"]')&&/^(?:예약\s*)?취소$/.test(text(node)));
  cards.push({text:value,media,single_card:true,cancelled});if(cards.length>=100)break;
 }
 if(!cards.length){
  const value=text(document.body).slice(0,8000);
  if((/my|member|reserv|booking|resv/i.test(location.pathname)||location.hostname==='my.naver.com')&&dated(value)&&/예약\s*번호|입실|퇴실|체크인|체크아웃|일정|예약정보/.test(value))cards.push({text:value,media:[],single_card:[...value.matchAll(/예약\s*(?:번호|코드)\s*[:：#]?\s*([A-Za-z0-9][A-Za-z0-9_-]{4,79})/g)].length===1,cancelled:detailCancelled});
 }
 return JSON.stringify(cards.length?{cards}:{error:'예약을 읽지 못했습니다. 로그인 후 예약 내역 또는 예약 상세 화면을 열어주세요.'});
})();
