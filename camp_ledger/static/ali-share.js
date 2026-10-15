'use strict';
(()=>{
 const aliases=[['브리즈문','브리즈문'],['BREEZEMOON','브리즈문'],['네이처하이크','네이처하이크'],['Naturehike','네이처하이크'],['스노우라인','스노우라인'],['Snowline','스노우라인'],['Blackdeer','블랙디어'],['블랙디어','블랙디어'],['Fire Maple','파이어메이플'],['Fire-Maple','파이어메이플'],['Flextail','플렉스테일'],['Widesea','위드씨'],['Boundless Voyage','바운드리스보야지'],['3F UL GEAR','3F UL GEAR'],['BRS','BRS']];
 const clean=text=>String(text||'').normalize('NFKC').replace(/\s+/g,' ').trim();
 function concise(title){
  let text=clean(title).replace(/^(?:상품명|제품명|상품|제품)\s*[:：]\s*/,'');
  const material=/스테인리스|스테인레스/i.test(text)?'스테인리스':/알루미늄/.test(text)?'알루미늄':'';
  const count=text.match(/(?:^|\s)(\d{1,3})\s*(?:개|pcs?)(?=\s|$|[,.])/i)?.[1];
  if(/필드\s*[랙렉]/.test(text))return [material,/멀티/.test(text)?'멀티':'','필드랙'].filter(Boolean).join(' ');
  if(/제어\s*손잡이|조절\s*손잡이|컨트롤\s*노브/.test(text))return (/스토브/.test(text)&&/오븐/.test(text)?'스토브·오븐 ':'')+'제어 손잡이'+(/세트|set/i.test(text)?' 세트':'')+(count?' ('+count+'개)':'');
  if(/그릴/.test(text))return [/접이식|접는/.test(text)?'접이식':'',material,/숯불/.test(text)?'숯불':'','그릴'].filter(Boolean).join(' ');
  text=text.split(/[,，;；]/)[0].replace(/(?:무료\s*배송|인기\s*상품|최신형|최고의|뜨거운\s*판매|신제품)/g,'').trim();
  const words=text.split(/\s+/),seen=new Set();text=words.filter(word=>{if(seen.has(word))return false;seen.add(word);return true}).join(' ');
  if(text.length>40){const prefix=text.slice(0,40),space=prefix.lastIndexOf(' ');text=prefix.slice(0,space>=20?space:40).trim()+'…';}
  return text;
 }
 window.parseAliShare=(text,knownBrands=[])=>{
  const rows=[],seen=new Set();let pending=[];
  for(const raw of String(text||'').replace(/[\u200b-\u200f\u2060\ufeff]/g,'').slice(0,20000).split(/\r?\n/)){
   const url=window.extractSharedUrl(raw);
   const line=(url?raw.slice(0,raw.indexOf(url)):raw).trim();
   if(line)pending.push(line);
   if(!url)continue;
   const host=new URL(url).hostname.toLowerCase();
   if(!['aliexpress.com','aliexpress.us','aliexpress.ru'].some(domain=>host===domain||host.endsWith('.'+domain))){pending=[];continue;}
   let lines=pending.map(line=>line.replace(/^.*?(?:AliExpress에서\s*찾은\s*상품(?:이에요|입니다)?|I\s+just\s+found\s+this\s+on\s+AliExpress)\s*[:：]?/i,'').trim()).filter(line=>line&&!/^(?:[₩$]|US\s*\$|가격\s*[:：]|\d[\d,.]*\s*원)/i.test(line));
   const explicit=lines.find(line=>/^(?:브랜드|brand)\s*[:：]/i.test(line));
   let brand=explicit?clean(explicit.replace(/^(?:브랜드|brand)\s*[:：]\s*/i,'')):'';
   if(/^(?:no\s*brand|unbranded|generic|OEM|없음|미상|브랜드\s*없음)$/i.test(brand))brand='';
   lines=lines.filter(line=>line!==explicit);const fullTitle=clean(lines.join(' '));let title=fullTitle.replace(/^(?:상품명|제품명)\s*[:：]\s*/,'');
   const candidates=[...aliases,...knownBrands.filter(value=>typeof value==='string'&&value.trim().length>=2&&!/^(?:휴대용|접이식|스테인리스|알루미늄|캠핑|브랜드|상품|기타|없음|generic)$/i.test(value.trim())).map(value=>[value.trim(),value.trim()])].sort((a,b)=>b[0].length-a[0].length);
   for(const [alias,label] of candidates){const prefix=title.slice(0,alias.length);if(prefix.toLocaleLowerCase()!==alias.toLocaleLowerCase()||!/^\s|^[·:：-]|^$/.test(title.slice(alias.length)))continue;const rest=title.slice(alias.length).replace(/^[\s·:：-]+/,'');if(/^(?:호환|용\s|스타일|compatible|for\s)/i.test(rest))break;if(!brand)brand=label;title=rest;break;}
   if(!seen.has(url)){seen.add(url);rows.push({name:concise(title),brand:brand.slice(0,80),purchase_url:url,original_name:fullTitle});}
   pending=[];if(rows.length>=20)break;
  }
  return rows;
 };
 window.summarizeAliProduct=concise;
 const form=document.getElementById('item-form');if(!form)return;
 const source=document.getElementById('ali-share-text'),results=document.getElementById('ali-share-results'),status=document.getElementById('ali-share-status');let fingerprint='';
 window.bindSharedLinkInput(form.elements.purchase_url);
 window.resetAliShare=()=>{fingerprint='';source.value='';status.textContent='';results.replaceChildren()};
 function apply(row){
  for(const key of ['name','brand','purchase_url']){const input=form.elements[key];if(['name','brand'].includes(key)&&!row.name)continue;input.value=row[key]||'';input.dispatchEvent(new Event('input',{bubbles:true}));}
 }
 function recognize(){
  const known=typeof state!=='undefined'?(state.items||[]).map(item=>item.brand).filter(Boolean):[],rows=window.parseAliShare(source.value,known);results.replaceChildren();
  if(!rows.length){fingerprint='';status.textContent=source.value.trim()?'알리 상품 링크가 포함된 공유 문구를 붙여넣어주세요.':'';return;}
  const key=JSON.stringify(rows);if(key!==fingerprint){apply(rows[0]);fingerprint=key;}
  status.textContent=rows.length>1?rows.length+'개 상품 인식 · 첫 번째 상품을 입력했습니다. 다른 상품을 선택할 수 있습니다.':rows[0].name?'상품명·링크를 입력했습니다.'+(rows[0].brand?'':' 브랜드는 확인되지 않아 비워두었습니다.'):'링크를 입력했습니다. 공유 문구에 상품명이 없어 직접 입력이 필요합니다.';
  for(const row of rows){const card=document.createElement('div'),button=document.createElement('button'),details=document.createElement('details'),summary=document.createElement('summary'),original=document.createElement('p');card.className='ali-share-result';button.type='button';button.textContent=(row.brand?row.brand+' · ':'')+(row.name||'상품명 직접 입력')+' · 입력';button.onclick=()=>{apply(row);status.textContent='선택한 상품을 입력했습니다.'+(row.brand?'':' 브랜드는 확인되지 않아 비워두었습니다.')};summary.textContent='원래 상품명';original.textContent=row.original_name||'공유 문구에 상품명이 없습니다.';details.append(summary,original);card.append(button,details);results.append(card);}
 }
 source.addEventListener('input',recognize);document.getElementById('ali-share-parse').onclick=()=>{fingerprint='';recognize()};
 document.getElementById('item-dialog').addEventListener('close',window.resetAliShare);
})();
