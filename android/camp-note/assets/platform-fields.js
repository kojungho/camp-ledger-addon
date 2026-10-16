(function(){
 'use strict';
 const text=el=>(el?.innerText||'').trim(),allowed=/^(?:예약\s*(?:정보|내역|상세(?:\s*정보)?)|숙소\s*정보|상품\s*정보|캠핑장\s*정보|이용\s*정보|일정|숙박\s*일정|주소|위치|배치도)(?:\s*(?:보기|더보기|펼치기|접기))?$/;
 const forbidden=/취소|환불|결제|예약자|계좌|개인정보|약관|동의|예약하기|구매|삭제/;
 function expander(){
  const opened=[],seen=new WeakSet();let count=0;
  function expand(){let changed=0;for(const el of document.querySelectorAll('details:not([open]),button[aria-expanded="false"],[role="button"][aria-expanded="false"]')){
   if(seen.has(el)||count>=24)continue;const label=text(el.tagName==='DETAILS'?el.querySelector('summary'):el).replace(/[+−▼▲▾▴⌄⌃]/g,'').trim();
   if(!allowed.test(label)||forbidden.test(label))continue;const rect=el.getBoundingClientRect();if(!rect.width||!rect.height)continue;
   if(el.tagName==='DETAILS'){el.open=true;opened.push(()=>{el.open=false})}
   else{const id=el.getAttribute('aria-controls'),panel=id?document.getElementById(id):null;if(!panel||!el.click)continue;el.click();opened.push(()=>{if(el.isConnected!==false&&el.getAttribute('aria-expanded')==='true')el.click()})}
   seen.add(el);count++;changed++;
  }return changed}
  function restore(){for(const undo of opened.reverse())try{undo()}catch(ignored){}opened.length=0}
  function pending(){return [...document.querySelectorAll('details:not([open]),button[aria-expanded="false"],[role="button"][aria-expanded="false"]')].some(el=>{const label=text(el.tagName==='DETAILS'?el.querySelector('summary'):el).replace(/[+−▼▲▾▴⌄⌃]/g,'').trim(),r=el.getBoundingClientRect();return allowed.test(label)&&!forbidden.test(label)&&r.width>0&&r.height>0})}
  return {expand,restore,pending};
 }
 const dateValue=value=>{const match=value.match(/(?<!\d)(?:(\d{4}|\d{2})\s*[./년-]\s*)?(\d{1,2})\s*[./월-]\s*(\d{1,2})(?:일)?(?!\d)/);if(!match)return '';const month=Number(match[2]),day=Number(match[3]);return month>=1&&month<=12&&day>=1&&day<=31?(match[1]?match[1]+'.':'')+match[2]+'.'+match[3]:''};
 function fields(el,detail=false,knownName=''){
  const result={},lines=text(el).split(/\n+/).map(v=>v.trim()).filter(Boolean);
  const labels={name:'캠핑장명|숙소명|업체명|장소명',site:'사이트명|사이트|캠핑존|구역|객실명|객실|예약정보',location:'주소|소재지|위치',checkin:'입실일|입실|체크인|이용시작일',checkout:'퇴실일|퇴실|체크아웃|이용종료일',price:'총 결제금액|총결제금액|총 금액|총금액|결제금액|합계 금액'};
  // Some two-column layouts put both date labels before both values in DOM order.
  const startLabel=/^(?:입실일|입실|체크인|이용시작일)$/,endLabel=/^(?:퇴실일|퇴실|체크아웃|이용종료일)$/;
  for(let i=0;i<lines.length-3;i++)if(startLabel.test(lines[i])&&endLabel.test(lines[i+1])||endLabel.test(lines[i])&&startLabel.test(lines[i+1])){const a=dateValue(lines[i+2]),b=dateValue(lines[i+3]);if(a&&b){result[startLabel.test(lines[i])?'checkin':'checkout']=a;result[startLabel.test(lines[i])?'checkout':'checkin']=b;break}}
  // Match a label and its own value: dates in payment notices or policy prose never override stay dates.
  for(const [key,names] of Object.entries(labels))for(let i=0;result[key]===undefined&&i<lines.length;i++){
   const m=lines[i].match(new RegExp('^(?:'+names+')(?:\\s*[:：]\\s*|\\s+|(?=\\d)|$)(.*)$'));if(!m)continue;
   const value=(m[1]||lines[i+1]||'').trim();if(!value||value.length>300||forbidden.test(value))continue;
   if(key==='checkin'||key==='checkout'){const date=dateValue(value);if(date)result[key]=date}
   else if(key==='price'){const amount=value.match(/^([\d,]+)\s*원?$/);if(amount)result.price=Number(amount[1].replace(/,/g,''))}
   else if(!Object.values(labels).some(names=>new RegExp('^(?:'+names+')$').test(value)))result[key]=value;
   if(result[key]!==undefined)break;
  }
  const anchors=[...(el.matches?.('a[href],[data-url],[data-href]')?[el]:[]),...el.querySelectorAll('a[href]'),...el.querySelectorAll('[data-url],[data-href]')];let reservation='';
  for(const anchor of anchors){
   const label=text(anchor),raw=anchor.getAttribute('href')||anchor.getAttribute('data-url')||anchor.getAttribute('data-href')||'';let url;try{url=new URL(raw,location.href)}catch(ignored){continue}
   const privateBooking=/(^|\.)naver\.com$/.test(url.hostname)&&/\/(?:my\/)?(?:bookings?|reservations?)\/\d+(?:\/|$)|\/my\/bookings?(?:\/|$)/i.test(url.pathname)&&/상세\s*보기|예약\s*(?:상세|내역|정보)/.test(label)&&!url.username&&!url.password&&/^https?:$/.test(url.protocol);
   if(privateBooking){for(const key of [...url.searchParams.keys()])if(!/^(?:bookingId|bookingNo|reservationId|reservationNo|businessId|bizId)$/i.test(key))url.searchParams.delete(key);url.hash='';if(!reservation)reservation=url.href;continue}
   if(!/^https?:$/.test(url.protocol)||url.username||url.password||/취소|환불|결제|리뷰|후기|예약\s*(?:상세|내역)|로그인|플랫폼\s*홈/.test(label))continue;
   if(/\/my(?:\/|$)|\/member(?:\/|$)|\/reservations?(?:\/|$)|\/orders?(?:\/|$)|\/pay(?:ment)?(?:\/|$)|login|logout/i.test(url.pathname))continue;
   const map=/(^|\.)(?:map\.naver\.com|naver\.me|kko\.to|map\.kakao\.com)$/.test(url.hostname);
   const place=/\/(?:campgrounds?|campsites?|camps?|camping|places?|accommodations?|business(?:es)?|bizes)\/[\w-]+/i.test(url.pathname)||/\/booking\/\d+\/bizes\/\d+/.test(url.pathname);
   const merchant=result.name||knownName;const named=!!merchant&&label.replace(/\s*[>›»❯]\s*$/,'')===merchant||/캠핑장\s*(?:보기|홈|정보|예약)|숙소\s*(?:보기|홈|정보)|홈페이지|공식\s*(?:사이트|홈)|장소\s*(?:보기|정보)/.test(label);
   if(!map&&!place&&!named)continue;
   if(detail&&!map&&!named)continue;
   // Drop tracking/session parameters; retain only known public place routing parameters.
   for(const key of [...url.searchParams.keys()])if(!/^(?:id|seq|bizId|businessId|placeId|campsiteId|campsiteSeq|campId|campSeq|campingId|campingSeq|camp_seq|camping_seq|campingCode|campCode)$/i.test(key))url.searchParams.delete(key);
   url.hash='';if(map&&!result.map_url)result.map_url=url.href;else if(!map&&!result.booking_url)result.booking_url=url.href;
  }
  if(!result.booking_url&&reservation){result.booking_url=reservation;result.booking_link_private=true}
  return result;
 }
 function enrich(card,el,detail=false){const name=card.text.match(/^캠핑장명:\s*(.+)$/m)?.[1]||'';card.fields={...fields(el,detail,name),...card.fields};return card}
 return {expander,fields,enrich};
})
