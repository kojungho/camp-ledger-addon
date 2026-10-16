const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('android/camp-note/assets/platform-fields.js','utf8');
const anchors=(href,label)=>({innerText:label,getAttribute:k=>k==='href'?href:null});
for(const [host,body,path] of [
 ['camfit.co.kr','캠핑장명: 숲 캠핑장\n캠핑존\nA-14\n주소\n경기 가평군 숲길 15\n입실일\n2026.10.01\n퇴실일\n2026.10.03\n총 금액\n66,000원','/camping/123'],
 ['m.thankqcamping.com','숙소명: 숲 캠핑장\n객실명: A-14\n위치: 경기 가평군 숲길 15\n체크인: 2027년 10월 1일\n체크아웃: 2027년 10월 3일\n합계 금액: 66,000원','/camps/123'],
 ['campingtalk.me','업체명: 숲 캠핑장\n사이트: A-14\n소재지: 경기 가평군 숲길 15\n입실 2026.10.01\n퇴실 2026.10.03\n결제금액 66,000원','/campsites/123'],
 ['m.booking.naver.com','장소명: 숲 캠핑장\n사이트명: A-14\n주소: 경기 가평군 숲길 15\n입실일: 2026.10.01\n퇴실일: 2026.10.03\n총금액: 66,000원','/booking/3/bizes/123']
]){
 const links=[anchors('javascript:alert(1)','캠핑장 보기'),anchors('/my/reservations/secret','예약 상세'),anchors(path+'?utm_source=app&token=secret','캠핑장 보기'),anchors('https://map.naver.com/p/entry/place/123','지도보기')];
 const api=vm.runInNewContext(source,{document:{},location:{href:'https://'+host+'/my/reservations/123'},URL})(),el={innerText:'결제일: 2026.09.01\n'+body+'\n환불 계좌 12345678',querySelectorAll:s=>s==='a[href]'?links:[]};
 const f=api.fields(el);assert.equal(f.name,'숲 캠핑장',host);assert.equal(f.site,'A-14',host);assert.equal(f.location,'경기 가평군 숲길 15');assert.equal(f.price,66000);assert.match(f.checkin,host.includes('thankq')?/2027/:/2026/);assert.match(f.checkout,host.includes('thankq')?/2027/:/2026/);assert.equal(f.booking_url,'https://'+host+path);assert.equal(f.map_url,'https://map.naver.com/p/entry/place/123');assert.doesNotMatch(JSON.stringify(f),/secret|12345678/);
}
let pressed=0;const details={tagName:'DETAILS',innerText:'일정',open:false,getBoundingClientRect:()=>({width:200,height:30}),querySelector:()=>({innerText:'예약 정보'})};
const button={tagName:'BUTTON',innerText:'주소 보기',isConnected:true,state:'false',getBoundingClientRect:()=>({width:200,height:30}),getAttribute(k){return k==='aria-controls'?'address':this.state},click(){this.state=this.state==='false'?'true':'false';pressed++}};
const unsafe={...button,innerText:'예약 취소',click(){throw Error('Never activate destructive actions')}};
const navigation={...button,getAttribute:()=>null,innerText:'예약 정보',click(){throw Error('Never navigate automatically')}};
const api=vm.runInNewContext(source,{document:{querySelectorAll:()=>[details,button,unsafe,navigation],getElementById:id=>id==='address'?{}:null},location:{href:'https://camfit.co.kr/my/bookings'},URL})(),expansion=api.expander();
assert.equal(expansion.expand(),2);assert.equal(details.open,true);assert.equal(button.state,'true');assert.equal(expansion.expand(),0);expansion.restore();assert.equal(details.open,false);assert.equal(button.state,'false');assert.equal(pressed,2);
const empty=api.fields({innerText:'위치선택\n예약자정보\n사이트사진',querySelectorAll:()=>[]});assert.deepEqual(Object.keys(empty),[],'No prefix-only label matches');
console.log('All four platforms: explicit stay labels, public campsite/map links, private/tracking URL exclusion and reversible safe expansion passed.');

const paired=api.fields({innerText:'입실일\n퇴실일\n2027.09.24\n2027.09.26',querySelectorAll:()=>[]});assert.equal(paired.checkin,'2027.09.24');assert.equal(paired.checkout,'2027.09.26');

const merchant=api.enrich({text:'캠핑장명: 숲 캠핑장',media:[]},{innerText:'숲 캠핑장',querySelectorAll:()=>[anchors('https://camp.test/camps/other','다른 추천 캠핑장'),anchors('https://camp.test/camps/123','숲 캠핑장 >')]},true);assert.equal(merchant.fields.booking_url,'https://camp.test/camps/123');
