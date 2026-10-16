const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('android/camp-note/assets/platform-scroll.js','utf8');
function run({inner=false,limit=false,checkpoint=false}={}){
 let now=0,lazy=false,rows=limit?100:5,pos=700;
 const scroller={clientHeight:500,get scrollHeight(){return rows*500},get scrollTop(){return pos},set scrollTop(value){pos=Math.max(0,Math.min(value,this.scrollHeight-this.clientHeight));if(!limit&&!lazy&&pos>=this.scrollHeight-this.clientHeight){lazy=true;rows++}},getBoundingClientRect:()=>({width:300})};
 const page=inner?{clientHeight:500,scrollHeight:500,scrollTop:0}:scroller,location={href:'https://camfit.co.kr/reservations'};
 const doc={scrollingElement:page,documentElement:page,body:{},querySelectorAll:()=>inner?[scroller]:[]};
 const factory=vm.runInNewContext(source,{document:doc,location,getComputedStyle:()=>({overflowY:'auto'}),Date:{now:()=>now},Map,Set,JSON,Math});
 const capture=()=>JSON.stringify({cards:limit?Array.from({length:100},(_,i)=>({text:'별 캠핑장\n예약번호 '+(10000+i),single_card:true,media:[]})):[{text:'별 캠핑장\n예약번호 '+(10000+Math.floor(pos/500)),single_card:true,cancelled:Math.floor(pos/500)===2,media:[]}]});
 const controller=factory(capture);let result;
 for(let n=0;n<160;n++){now+=700;result=JSON.parse(controller.step());if(checkpoint&&result.batch?.some(c=>c.text.includes('10002'))){result=JSON.parse(controller.stopAtSynced(result.batch.findIndex(c=>c.text.includes('10002'))));break}if(result.done||result.error)break}
 assert.equal(pos,700,'Restore the original scroll position');
 if(checkpoint){assert.equal(result.stopped_at_synced,true);assert.equal(result.scan_truncated,false);assert.deepEqual(result.cards.map(c=>c.text.match(/1000\d/)[0]),['10000','10001','10002']);assert.equal(lazy,false,'Stop before reaching lazy-loaded older reservations');assert.equal(result.batch.length,0)}else if(limit){assert.equal(result.scan_truncated,true);assert.equal(result.scan_reason,'limit');assert.equal(result.cards.length,100)}else{assert.equal(result.done,true);assert.equal(result.scan_truncated,false);assert.equal(result.cards.length,6,'Collect virtualized rows and an additional lazy-loaded bottom row');assert.equal(result.cards.filter(c=>c.cancelled).length,1)}
 return {factory,capture,scroller,location};
}
run();run({checkpoint:true});run({inner:true,checkpoint:true});run({inner:true});run({limit:true});
const {factory,capture,scroller,location}=run();const c=factory(capture);c.step();c.cancel();assert.equal(scroller.scrollTop,700);assert.match(JSON.parse(c.step()).error,/취소/);
const changed=factory(capture);location.href='https://camfit.co.kr/other';assert.match(JSON.parse(changed.step()).error,/페이지가 변경/);assert.equal(scroller.scrollTop,700);
console.log('Automatic scan collects off-screen, virtualized and lazy-loaded reservations, scrolls inner containers, deduplicates, restores position and reports cancellation/navigation/limits.');

// A lazy-loaded price/photo must enrich the existing booking, never create another row.
{
 let now=0,reads=0;const root={clientHeight:500,scrollHeight:500,scrollTop:0};
 const factory=vm.runInNewContext(source,{document:{scrollingElement:root,body:{},querySelectorAll:()=>[]},location:{href:'https://m.booking.naver.com/reservations'},Date:{now:()=>now},Map,Set,JSON,Math});
 const base='캠핑장명: 풍경소리캠핑장\n사이트명: D4\n입실일: 2026.05.23';
 const scan=factory(()=>JSON.stringify({cards:[{single_card:true,text:base+(reads++?'\n금액: 140,000원':''),media:[{kind:'gallery',url:'https://images.test/'+reads+'.jpg'},...Array.from({length:3},(_,i)=>({kind:'layout',url:'https://images.test/layout'+reads+i+'.jpg'}))]}]}));
 let result;for(let i=0;i<40;i++){now+=700;result=JSON.parse(scan.step());if(result.done)break}
 assert.equal(result.cards.length,1);assert.match(result.cards[0].text,/140,000원/);assert.equal(result.cards[0].media.filter(p=>p.kind==='gallery').length,1);assert.equal(result.cards[0].media.filter(p=>p.kind==='layout').length,3);
}
