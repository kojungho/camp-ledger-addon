(function(){
 'use strict';
 if(!/(^|\.)naver\.com$/i.test(location.hostname))return null;
 const text=el=>(el?.innerText||'').trim(),visible=el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>0};
 const datePattern=/(?<![\d.])(?:(\d{4}|\d{2})\s*[.\/-]\s*)?(\d{1,2})\s*[.\/]\s*(\d{1,2})(?:\s*\(?[월화수목금토일]\)?)?/g;
 const dates=value=>[...value.matchAll(datePattern)].filter(m=>Number(m[2])>=1&&Number(m[2])<=12&&Number(m[3])>=1&&Number(m[3])<=31);
 const idPattern=/예약\s*(?:번호|코드)\s*[:：#]?\s*([A-Za-z0-9][A-Za-z0-9_-]{4,79})/g;
 const cancelled=value=>/취소\s*완료|예약(?:이|가)\s*취소(?:되었습니다|됐습니다|됨)|취소된\s*예약|예약\s*취소됨/.test(value)||value.split(/\n/).some(line=>/^(?:예약\s*)?취소$/.test(line.trim()));
 const body=text(document.body),lodging=[...document.querySelectorAll('[aria-selected="true"],[aria-current="page"],[class*="active" i]')].some(el=>/^(숙박|캠핑|숙소)$/.test(text(el)));
 function linesOf(el){return text(el).split(/\n+/).map(v=>v.trim()).filter(Boolean)}
 function field(lines,labels){for(let i=0;i<lines.length;i++){const match=lines[i].match(new RegExp('^(?:'+labels+')\\s*[:：]?\\s*(.*)$'));if(match)return match[1]||lines[i+1]||''}return ''}
 const titleOK=value=>value.length>=2&&value.length<=120&&!/[\n\r]/.test(value)&&!dates(value).length&&!/예약|입실|퇴실|체크인|체크아웃|일정|결제|환불|취소|이용완료|사용완료|익명|신분증|전자문서|멤버십|리뷰|후기|상세보기|로그인|적립|멤버십|주변|예약자|에서 드리는 글/.test(value)&&!/^(?:이용(?:전|중|예정)|방문완료|사용예정)$/.test(value)&&!/^\d+사이트|^[A-Z]\d+(?:\s|$|\()|^(?:상품|객실|사이트명|숙박|예약 정보|AD)$/.test(value);
 function nameOf(el,lines,detail=false){
  const explicit=field(lines,'캠핑장명|숙소명|업체명|장소명');if(titleOK(explicit))return explicit;
  const titles=[...el.querySelectorAll('h1,h2,h3,h4,strong,[class*="title" i],[class*="name" i],a')].map(text).filter(titleOK);
  const valid=value=>{const i=lines.indexOf(value);return i<1||!/^(상품|상품명|이용상품|객실|사이트명)$/.test(lines[i-1])};
  const names=[...titles,...lines.filter(titleOK)].filter(valid);
  return names.find(v=>/캠핑장|캠프|야영장|글램핑|카라반|휴양림|목장/.test(v))||titles.find(valid)||((detail||categoryOf(el)==='stay')?names[0]:'')||'';
 }
 function photos(el,name,detail){const result=[];for(const img of el.querySelectorAll('img')){const r=img.getBoundingClientRect(),url=img.currentSrc||img.src||'',alt=img.alt||'';if(!/^https:\/\//.test(url)||Math.max(r.width,img.naturalWidth||0)<80||Math.max(r.height,img.naturalHeight||0)<60||/logo|icon|avatar|banner|advert|로고|아이콘|프로필|광고/i.test(alt+' '+img.className)||img.closest('[class*="advert" i],[class*="banner" i],[id^="ad-"],[aria-label="광고"]'))continue;const layout=/배치도|구역도|안내도|사이트\s*맵/.test(alt);if(detail&&!layout&&!alt.includes(name))continue;if(layout&&result.filter(p=>p.kind==='layout').length<3)result.push({kind:'layout',url});else if(!layout&&!result.some(p=>p.kind==='gallery'))result.push({kind:'gallery',url})}return result}
 function categoryOf(el){
  const marks=[...el.querySelectorAll('img,svg,use,[aria-label],[title],[data-category],[data-type],[data-icon],[data-booking-type],[data-business-type],[class*="icon" i],[class*="badge" i],[class*="category" i]')];
  for(const mark of marks){const value=['alt','aria-label','title','data-category','data-type','data-icon','href','xlink:href','src','class','data-booking-type','data-business-type'].map(key=>mark.getAttribute?.(key)||'').join(' ');if(/숙박|캠핑|(?:^|[\s_/#.-])(?:accommodations?|lodging|hotel|stay|bed|camping)(?:$|[\s_/#.?#-])/i.test(value))return 'stay';if(/음식점|식당|체험|공연|(?:^|[\s_/#.-])(?:restaurant|dining|ticket|activity)(?:$|[\s_/#.?#-])/i.test(value))return 'other'}return ''
 }
 function parse(el,detail=false){
  const raw=text(el);if(raw.length<12||raw.length>16000||!dates(raw).length)return null;
  let lines=linesOf(el);if(detail){const end=lines.findIndex(v=>/에서\s*드리는\s*글|^예약자\s*정보|^취소.*규정|^환불.*규정/.test(v));if(end>=0)lines=lines.slice(0,end)}
  const source=lines.join('\n'),name=nameOf(el,lines,detail);if(!name)return null;
  const category=categoryOf(el);if(category==='other'&&(!detail||!/캠핑장|캠프|숙박|입실|퇴실/.test(name+' '+source)))return null;
  const camping=category==='stay'||/캠핑장|캠프|야영장|글램핑|카라반|휴양림|목장/.test(name)||lodging||/숙박|객실|입실|퇴실|체크인|체크아웃|\d+\s*박/.test(source);
  if(!camping)return null;
  const ids=[...source.matchAll(idPattern)];if(ids.length>1)return null;
  let values=[];const labelled=field(lines,'일정|이용기간|숙박기간|예약일');if(labelled)values=dates(labelled);if(!values.length)values=dates(source);if(values.length>2&&!detail)return null;
  if(!values.length)return null;
  let site=field(lines,'사이트명|사이트|객실명|객실|상품명|이용상품|상품').replace(/\(\d+\)\s*$/,'').trim();
  if(!site){const index=lines.indexOf(name);const candidate=lines.slice(index+1).find(v=>!dates(v).length&&!/예약|상세|후기|리뷰|입실|퇴실|이용완료|^\d[\d,]*원$/.test(v)&&/^(?:[A-Z]\s*\d+|[A-Z]구역|[A-Z]존|\d+사이트|성인|오토캠핑|데크|파쇄석)|사이트|호수뷰|차박/.test(v));if(candidate)site=candidate.replace(/\s*[·ㆍ]\s*[\d,]+원.*$/,'').trim()}
  const normalized=['캠핑장명: '+name];if(ids[0])normalized.push('예약번호: '+ids[0][1]);if(site)normalized.push('사이트명: '+site);normalized.push('입실일: '+values[0][0]);if(values[1])normalized.push('퇴실일: '+values[1][0]);else{const nights=source.match(/(\d{1,3})\s*박/);if(nights)normalized.push(nights[1]+'박')}
  const address=field(lines,'주소|위치|소재지');if(address)normalized.push('주소: '+address);
  const price=source.match(/(?:[·ㆍ]|가격\s*[:：]?|금액\s*[:：]?)\s*([\d,]+)\s*원/);if(price)normalized.push('금액: '+price[1]+'원');
  if(cancelled(source))normalized.push('예약이 취소되었습니다');
  return {text:normalized.join('\n'),media:photos(el,name,detail),single_card:true,cancelled:cancelled(source)};
 }
 const modals=[...document.querySelectorAll('[role="dialog"],[aria-modal="true"],dialog[open],[class*="popup" i],[class*="modal" i],[class*="layer" i]')].filter(visible);
 for(const root of [...modals,document.body]){const value=text(root);if([...value.matchAll(idPattern)].length===1&&/예약\s*번호/.test(value)&&/일정|입실|퇴실|예약\s*정보/.test(value)){const row=parse(root,true);if(row)return {cards:[row]}}}
 const nodes=[...document.querySelectorAll('article,li,section,[role="listitem"],[class*="reservation" i],[class*="booking" i],div,a')].slice(0,6000),found=[];
 for(const el of nodes){if(!visible(el)||text(el).length>6000||!/예약|입실|퇴실|숙박|체크인|체크아웃/.test(text(el)))continue;const row=parse(el);if(row)found.push({el,row})}
 const leaves=found.filter(parent=>!found.some(child=>child!==parent&&parent.el.contains(child.el))),seen=new Set(),cards=[];
 for(const {row} of leaves){if(seen.has(row.text))continue;seen.add(row.text);cards.push(row);if(cards.length>=100)break}
 const recent=/예약\s*[·ㆍ・]\s*(?:주문|장소)/.test(body);
 const ignored=nodes.some(el=>visible(el)&&dates(text(el)).length>0&&categoryOf(el)==='other');
 if(cards.length||ignored||lodging||recent)return {cards,handled:true,ignored_non_lodging:ignored||recent};
 return null;
})
