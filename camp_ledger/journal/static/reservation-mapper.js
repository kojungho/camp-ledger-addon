'use strict';
(()=>{
 const fields=[['name','캠핑장명'],['location','주소'],['site','사이트명'],['platform','예약 플랫폼'],['price','가격'],['checkin','입실일'],['checkout','퇴실일'],['booking_url','캠핑장 링크'],['map_url','지도 링크'],['notes','메모']];
 const normalize=value=>String(value??'').normalize('NFKC').toLowerCase().replace(/[\s\p{P}\p{S}_]/gu,'');
 function unassigned(text,records){
  const known=[];
  for(const record of records)for(const [key] of fields){const value=record[key];if(value==null||value==='')continue;known.push(normalize(value));if(['checkin','checkout'].includes(key)&&/^\d{4}-\d{2}-\d{2}$/.test(value)){const [y,m,d]=value.split('-');known.push(normalize(y.slice(2)+m+d),normalize(Number(m)+'.'+Number(d)),normalize(m+d))}}
  for(const record of records)if(record.date_hint)known.push(normalize(record.date_hint));known.sort((a,b)=>b.length-a.length);
  const labels=['캠핑장명','캠핑장링크','예약플랫폼','사이트명','예약정보','입실일','퇴실일','예약일','결제금액','이용금액','사이트','주소','위치','가격','금액','요금','일정','메모'];
  return String(text||'').split(/\r?\n/).map(line=>line.trim()).filter(line=>{
   if(!line)return false;let rest=normalize(line);
   for(const token of known)if(token&&(token.length>=3||rest===token))rest=rest.split(token).join('');
   for(const label of labels)rest=rest.split(normalize(label)).join('');
   rest=rest.replace(/원$/,'');
   if(!rest||/^[월화수목금토일]+$/.test(rest))return false;
   if(['다시예약','다시예약하기','예약내역','예약상세','리뷰쓰기','후기작성','로그작성완료','이용완료','방문완료','재예약'].includes(rest))return false;
   return true;
  });
 }
 function mappedValue(field,text,year=Number(new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Seoul',year:'numeric'}).format(new Date()))){
  if(!fields.some(([key])=>key===field))throw Error('넣을 항목을 선택해주세요.');
  let value=String(text||'').trim();if(!value)throw Error('적용할 문구를 입력해주세요.');
  const label={name:'캠핑장명|업체명|숙소명',location:'주소|위치|소재지',site:'사이트명|사이트|구역|자리',platform:'예약 플랫폼|예약플랫폼|플랫폼',price:'결제금액|이용금액|가격|금액|요금',checkin:'입실일|입실|체크인',checkout:'퇴실일|퇴실|체크아웃',booking_url:'캠핑장 링크|예약 링크|링크',map_url:'지도 링크|링크',notes:'메모'}[field];
  value=value.replace(new RegExp('^(?:'+label+')\\s*[:：]\\s*'),'');
  if(field==='price'){if(!/^[₩\s]*\d[\d,\s]*(?:원)?$/.test(value))throw Error('가격에 넣을 숫자만 남겨주세요. 예: 140,000원');const number=Number(value.replace(/[^\d]/g,''));if(!Number.isSafeInteger(number))throw Error('가격을 확인해주세요.');return String(number)}
  if(['checkin','checkout'].includes(field)){
   let matches=[...value.matchAll(/(?<!\d)(\d{4}|\d{2})\s*[.\/년-]\s*(\d{1,2})\s*[.\/월-]\s*(\d{1,2})(?:일)?(?!\d)/g)],short=false;
   if(!matches.length){matches=[...value.matchAll(/(?<![\d.\/-])(\d{1,2})\s*[.\/월]\s*(\d{1,2})(?:일)?(?![\d.\/-])/g)];short=true}
   const match=field==='checkout'?matches.at(-1):matches[0];if(!match)throw Error('날짜를 확인해주세요. 예: 2026-05-23 또는 5.23');
   let [y,m,d]=short?[year,Number(match[1]),Number(match[2])]:match.slice(1,4).map(Number);if(y<100)y+=2000;const date=new Date(Date.UTC(y,m-1,d));if(date.getUTCFullYear()!==y||date.getUTCMonth()!==m-1||date.getUTCDate()!==d)throw Error('존재하는 날짜인지 확인해주세요.');return [y,String(m).padStart(2,'0'),String(d).padStart(2,'0')].join('-');
  }
  if(['booking_url','map_url'].includes(field)){const match=value.match(/https?:\/\/[^\s]+/);if(!match)throw Error('http:// 또는 https:// 링크를 입력해주세요.');const url=new URL(match[0]);if(!['http:','https:'].includes(url.protocol))throw Error('웹 링크를 확인해주세요.');return url.href}
  return value;
 }
 window.unassignedReservationLines=unassigned;window.reservationMappedValue=mappedValue;
 window.mountReservationMapper=({container,text,cards})=>{
  const lines=unassigned(text,cards.map(card=>card.read()));container.replaceChildren();container.className='reservation-unassigned';container.hidden=!lines.length||!cards.length;if(container.hidden)return;
  const title=document.createElement('h3');title.textContent='항목을 선택할 문구';const hint=document.createElement('p');hint.className='hint';hint.textContent='문구와 넣을 기록·항목을 선택하세요. 적용 전 현재 값과 비교할 수 있습니다.';const list=document.createElement('div'),more=document.createElement('button');more.type='button';container.append(title,hint,list,more);let offset=0;
  function lineEditor(line){
   const row=document.createElement('div');row.className='reservation-map-row';const phrase=document.createElement('input');phrase.type='text';phrase.value=line;phrase.setAttribute('aria-label','분류할 문구');
   const record=document.createElement('select');record.setAttribute('aria-label','넣을 기록');const field=document.createElement('select');field.setAttribute('aria-label','넣을 항목');
   const blank=document.createElement('option');blank.value='';blank.textContent='넣을 항목 선택';field.append(blank);for(const [key,label] of fields){const option=document.createElement('option');option.value=key;option.textContent=label;field.append(option)}
   const mode=document.createElement('select');mode.setAttribute('aria-label','기존 값 처리');for(const [key,label] of [['replace','값 바꾸기'],['append','뒤에 추가']]){const option=document.createElement('option');option.value=key;option.textContent=label;mode.append(option)}
   const before=document.createElement('p'),after=document.createElement('p'),notice=document.createElement('p'),apply=document.createElement('button'),skip=document.createElement('button');before.className=after.className='reservation-map-compare';notice.className='hint';notice.setAttribute('role','status');apply.type=skip.type='button';skip.textContent='제외';let applied='';
   const signature=()=>JSON.stringify([phrase.value,record.value,field.value,mode.value]);
   function targets(){const previous=record.value;record.replaceChildren();cards.forEach((card,i)=>{const option=document.createElement('option');option.value=String(i);option.textContent=(i+1)+'. '+(card.read().name||'이름 미입력');record.append(option)});record.value=previous&&Number(previous)<cards.length?previous:'0'}
   function candidate(){const current=String(cards[Number(record.value)].read()[field.value]??''),value=mappedValue(field.value,phrase.value);return {current,value:mode.value==='append'&&current?current+' · '+value:value}}
   function update(){
    const fixed=['price','checkin','checkout','booking_url','map_url'].includes(field.value);mode.hidden=fixed||!field.value;if(fixed)mode.value='replace';
    try{const {current,value}=candidate();before.textContent='현재: '+(current||'(빈 값)');after.textContent='적용 후: '+value;apply.textContent=mode.value==='append'?'뒤에 추가':'적용';apply.disabled=signature()===applied||value===current;notice.textContent=signature()===applied?'적용했습니다.':''}catch(error){before.textContent=field.value?'현재: '+(cards[Number(record.value)].read()[field.value]||'(빈 값)'):'';after.textContent='';apply.disabled=true;apply.textContent='적용';notice.textContent=field.value?error.message:''}
   }
   targets();record.onfocus=targets;phrase.oninput=record.onchange=mode.onchange=update;field.onchange=()=>{mode.value=field.value==='notes'?'append':'replace';update()};
   apply.onclick=()=>{try{const {value}=candidate();cards[Number(record.value)].write(field.value,value);applied=signature();targets();update()}catch(error){notice.textContent=error.message}};skip.onclick=()=>{row.hidden=true};row.append(phrase,record,field,mode,before,after,notice,apply,skip);update();list.append(row);
  }
  function next(){const end=Math.min(offset+20,lines.length);for(;offset<end;offset++)lineEditor(lines[offset]);more.hidden=offset>=lines.length;more.textContent='문구 더보기 ('+(lines.length-offset)+'개)'}more.onclick=next;next();
 };
})();
