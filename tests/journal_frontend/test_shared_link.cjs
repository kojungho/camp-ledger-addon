const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const window={},c={window,URL,WeakSet,Event:class{constructor(type,options){this.type=type;this.bubbles=options?.bubbles}}};vm.runInNewContext(fs.readFileSync('camp_ledger/journal/static/shared-link.js','utf8'),c);
const extract=window.extractSharedUrl;
const naver='[네이버지도]\n하늘구니\n대구 군위군 삼국유사면 화산길 712\nhttps://naver.me/5ajvJix3';
assert.equal(extract(naver),'https://naver.me/5ajvJix3');assert.equal(extract('캠핏 별 캠핑장\n예약하기 https://camfit.co.kr/camp/123?site=A1&from=share'),'https://camfit.co.kr/camp/123?site=A1&from=share');assert.equal(extract('안내: (https://example.test/camp).'),'https://example.test/camp');assert.equal(extract('링크: https://example.test/camp_(A)'), 'https://example.test/camp_(A)');assert.equal(extract('[https://example.test/path?q=%EA%B0%80%EB%82%98&x=1]'),'https://example.test/path?q=%EA%B0%80%EB%82%98&x=1');assert.equal(extract('https://naver.me/5ajvJix3\n참고 https://other.test'),'https://naver.me/5ajvJix3');assert.equal(extract('https://[::1]/camp'),'https://[::1]/camp');assert.equal(extract('“https://example.test/공유”'),'https://example.test/공유');assert.equal(extract('링크 https://example.test/path\u200b'),'https://example.test/path');assert.equal(extract('javascript:alert(1)'),null);assert.equal(extract('캠핑장 안내만 있습니다'),null);
function input(){return {value:'',listeners:{},addEventListener(type,fn){(this.listeners[type]??=[]).push(fn)},dispatchEvent(event){for(const fn of this.listeners[event.type]||[])fn(event)}}}
for(const name of ['booking_url','map_url']){
 const el=input();window.bindSharedLinkInput(el);window.bindSharedLinkInput(el);assert.equal(el.listeners.paste.length,1);let prevented=false,updates=0;el.addEventListener('input',()=>updates++);
 el.dispatchEvent({type:'paste',clipboardData:{getData:()=>naver},preventDefault(){prevented=true}});assert.equal(prevented,true);assert.equal(el.value,'https://naver.me/5ajvJix3');assert.equal(updates,1);
 el.value='[네이버지도]하늘구니https://naver.me/5ajvJix3';el.dispatchEvent({type:'input'});assert.equal(el.value,'https://naver.me/5ajvJix3');
 el.value='https://example.';el.dispatchEvent({type:'input'});assert.equal(el.value,'https://example.','Typing a domain dot must not be interrupted');
 prevented=false;el.dispatchEvent({type:'paste',clipboardData:{getData:()=> '아직 링크 없음'},preventDefault(){prevented=true}});assert.equal(prevented,false);assert.equal(el.value,'https://example.');
}
console.log('Shared map/platform text becomes only its first valid web URL on paste, with mobile fallback and normal typing preserved.');
