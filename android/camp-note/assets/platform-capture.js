(function(){
 'use strict';
 if(document.querySelector('input[type="password"]'))return JSON.stringify({error:'로그인한 뒤 예약 내역 화면에서 동기화를 눌러주세요.'});
 const visible=el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0};
 const text=el=>(el.innerText||'').trim();
 const dated=value=>/(?:20\d{2}|\d{2})\s*[.\/-]\s*\d{1,2}\s*[.\/-]\s*\d{1,2}|\d{1,2}월\s*\d{1,2}일|(?:^|\n)\s*\d{1,2}[./]\d{1,2}\s*[월화수목금토일]/.test(value);
 const named=el=>/캠핑장|캠프|야영장|글램핑/.test(text(el))||[...el.querySelectorAll('h1,h2,h3,h4,strong')].some(title=>{const value=text(title);return value.length>=2&&value.length<=80&&!/입실|퇴실|예약|일정|금액|완료|취소|로그인/.test(value)});
 const candidates=[...document.querySelectorAll('article,li,section,[class*="reservation" i],[class*="booking" i]')].filter(el=>{if(!visible(el))return false;const value=text(el);return value.length>=15&&value.length<=8000&&dated(value)&&named(el)&&(/예약\s*(?:번호|정보|상세|내역|일|확정)|입실|퇴실|일정|이용완료|방문완료|다시\s*예약/.test(value))});
 const leaves=candidates.filter(el=>!candidates.some(child=>child!==el&&el.contains(child)&&named(child)));
 const cards=[],seen=new Set();
 for(const el of leaves){
  const value=text(el);if(seen.has(value))continue;seen.add(value);
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
  const cancelled=/취소\s*완료|예약(?:이|가)\s*취소|취소된\s*예약|예약\s*취소됨/.test(value)||[...el.querySelectorAll('[class*="status" i],[class*="badge" i],[class*="state" i]')].some(node=>!node.closest('button,a,[role="button"]')&&/^(?:예약\s*)?취소$/.test(text(node)));
  cards.push({text:value,media,single_card:true,cancelled});if(cards.length>=100)break;
 }
 if(!cards.length){
  const value=text(document.body).slice(0,8000);
  if((/my|member|reserv|booking|resv/i.test(location.pathname)||location.hostname==='my.naver.com')&&dated(value)&&/예약\s*번호|입실|퇴실|일정|예약정보/.test(value))cards.push({text:value,media:[]});
 }
 return JSON.stringify(cards.length?{cards}:{error:'예약을 읽지 못했습니다. 로그인 후 예약 내역 또는 예약 상세 화면을 열어주세요.'});
})();
