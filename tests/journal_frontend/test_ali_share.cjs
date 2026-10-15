const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class E{constructor(){this.value='';this.listeners={};this.children=[];this.textContent=''}addEventListener(type,fn){(this.listeners[type]??=[]).push(fn)}dispatchEvent(event){for(const fn of this.listeners[event.type]||[])fn(event)}append(...nodes){this.children.push(...nodes)}replaceChildren(){this.children=[]}}
const ids={};for(const id of ['ali-share-text','ali-share-results','ali-share-status','ali-share-parse','item-dialog'])ids[id]=new E();const form=ids['item-form']=new E();form.elements=Object.fromEntries(['name','brand','purchase_url'].map(key=>[key,new E()]));
const document={getElementById:id=>ids[id],createElement:()=>new E()},window={},c={document,window,URL,WeakSet,Event:class{constructor(type){this.type=type}},state:{items:[{brand:'사용자브랜드'}]}};vm.createContext(c);for(const path of ['journal/static/shared-link','static/ali-share'])vm.runInContext(fs.readFileSync('camp_ledger/'+path+'.js','utf8'),c);
const text=`방금 AliExpress에서 찾은 상품이에요:
브리즈문 스테인리스 택티컬 멀티 필드랙 테이블 쿨러 난로 팬히터 쉘프 캠핑 선반
https://a.aliexpress.com/_c3wAxSZP

방금 AliExpress에서 찾은 상품이에요:
어댑터가 있는 제어 손잡이 다용도 제어 손잡이 세트 손잡이 및 스토브 및 오븐용 어댑터 12개 제어 손잡이
https://a.aliexpress.com/_c4TfSTa5

방금 AliExpress에서 찾은 상품이에요:
휴대용 접이식 스테인리스 숯불 그릴, 가정용 야외 캠핑 바베큐 그릴, 고기 생선 구이용
https://a.aliexpress.com/_c2RWC8n7`;
const rows=window.parseAliShare(text);assert.equal(rows.length,3);assert.equal(rows[0].brand,'브리즈문');assert.equal(rows[0].name,'스테인리스 멀티 필드랙');assert.equal(rows[1].brand,'');assert.equal(rows[1].name,'스토브·오븐 제어 손잡이 세트 (12개)');assert.equal(rows[2].brand,'');assert.equal(rows[2].name,'접이식 스테인리스 숯불 그릴');assert.equal(rows[2].purchase_url,'https://a.aliexpress.com/_c2RWC8n7');assert.ok(rows.every(row=>row.original_name.length>=row.name.length));
assert.equal(window.parseAliShare('Naturehike 접이식 의자\nhttps://a.aliexpress.com/_other')[0].brand,'네이처하이크');assert.equal(window.parseAliShare('네이처하이크 호환 수납가방\nhttps://a.aliexpress.com/_other')[0].brand,'');assert.equal(window.parseAliShare('브랜드: Other Brand\n접이식 의자\nhttps://a.aliexpress.com/_other')[0].brand,'Other Brand');assert.equal(window.parseAliShare('https://a.aliexpress.com/_other')[0].name,'');assert.equal(window.parseAliShare('휴대용 스테인리스 주전자\nhttps://evil.test/aliexpress.com').length,0);assert.equal(window.parseAliShare('주전자\nhttps://a.aliexpress.com.evil.test/path').length,0);assert.equal(window.parseAliShare(text+'\n'+text).length,3);assert.ok(window.summarizeAliProduct('아주긴상품명 '.repeat(30)).length<=41);
ids['ali-share-text'].value=text;ids['ali-share-text'].dispatchEvent({type:'input'});assert.equal(form.elements.name.value,rows[0].name);assert.equal(form.elements.brand.value,'브리즈문');assert.equal(ids['ali-share-results'].children.length,3);assert.ok(ids['ali-share-status'].textContent.includes('3개'));ids['ali-share-results'].children[1].children[0].onclick();assert.equal(form.elements.name.value,rows[1].name);assert.equal(form.elements.brand.value,'');assert.equal(form.elements.purchase_url.value,rows[1].purchase_url);
let prevented=false;form.elements.purchase_url.dispatchEvent({type:'paste',clipboardData:{getData:()=>text.split('\n\n')[0]},preventDefault(){prevented=true}});assert.equal(prevented,true);assert.equal(form.elements.purchase_url.value,rows[0].purchase_url);
form.elements.name.value='기존 상품';form.elements.brand.value='기존 브랜드';ids['ali-share-text'].value='https://a.aliexpress.com/_urlOnly';ids['ali-share-text'].dispatchEvent({type:'input'});assert.equal(form.elements.name.value,'기존 상품');assert.equal(form.elements.brand.value,'기존 브랜드');assert.equal(form.elements.purchase_url.value,'https://a.aliexpress.com/_urlOnly');
window.resetAliShare();assert.equal(ids['ali-share-text'].value,'');assert.equal(ids['ali-share-results'].children.length,0);assert.equal(form.elements.name.value,'기존 상품','Resetting source must not erase edited item fields');
console.log('Ali share text extracts brands conservatively, concise names and URLs; multi-item choices fill only the draft and ledger URL paste strips surrounding text.');
