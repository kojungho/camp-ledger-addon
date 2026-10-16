const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('android/camp-note/assets/platform-naver.js','utf8');
function node(value,{titles=[],marks=[],children=[]}={}){return {innerText:value,children,getBoundingClientRect:()=>({width:320,height:300}),contains(child){return children.includes(child)||children.some(c=>c.contains(child))},querySelectorAll(s){if(s==='img')return [];if(s.startsWith('img,svg'))return marks.map(label=>({getAttribute:key=>key==='aria-label'?label:''}));if(s.startsWith('h1'))return titles.map(innerText=>({innerText}));return []}}}
function capture(nodes,{tab='',body,modal}={}){const root=body||node(nodes.map(n=>n.innerText).join('\n'),{children:nodes}),document={body:root,querySelectorAll(s){if(s.includes('aria-selected'))return tab?[{innerText:tab}]:[];if(s.includes('aria-modal'))return modal?[modal]:[];return nodes}};return vm.runInNewContext(source,{document,location:{hostname:'my.naver.com'},JSON})()}
const first=node('이용완료\n하늘구니 더원\nD4 (호수뷰,차박 불가)\n일정 26.05.23(토)-26.05.25(월)\n예약 상세',{titles:['하늘구니 더원'],marks:['숙박']});
const second=node('풍경소리캠핑장\n상품\n3사이트 캠핑장\n입실일 2026.05.03\n퇴실일 2026.05.05\n예약 내역',{titles:['풍경소리캠핑장']});
const combined=node('프로필\n'+first.innerText+'\n'+second.innerText,{titles:['익명'],children:[first,second],marks:['숙박']});
let result=capture([combined,first,second],{tab:'숙박'});assert.equal(result.cards.length,2);assert.match(result.cards[0].text,/캠핑장명: 하늘구니 더원/);assert.match(result.cards[0].text,/사이트명: D4/);assert.match(result.cards[1].text,/캠핑장명: 풍경소리캠핑장/);assert.match(result.cards[1].text,/사이트명: 3사이트 캠핑장/);
const restaurant=node('해돈 텍사스 바베큐 그릴\n8.1 토 오후 7:00 예약\n테이블 예약\n상세보기',{titles:['해돈 텍사스 바베큐 그릴'],marks:['음식점']});const activity=node('횡성루지체험장\n10.4 일 오전 12:00 예약\n19,500원\n상세보기',{titles:['횡성루지체험장'],marks:['체험']});const stay=node('하늘구니\n5.3 일 오전 12:00 예약\n3사이트 캠핑장 · 175,000원\n상세보기',{titles:['하늘구니'],marks:['숙박']});
result=capture([restaurant,activity,stay]);assert.equal(result.cards.length,1);assert.equal(result.ignored_non_lodging,true);assert.match(result.cards[0].text,/캠핑장명: 하늘구니/);assert.match(result.cards[0].text,/사이트명: 3사이트 캠핑장/);assert.doesNotMatch(result.cards[0].text,/퇴실일:/,'Never invent an end date from the main list');
const detail=node('풍경소리캠핑장\n강력한 마그네틱 클립오르 AD\n예약 정보\n주변 가볼만한 곳\n이용완료\n예약번호 1172454330\nD4 (호수뷰,차박 불가)\n일정\n2026. 5. 23(토)~2026. 5. 25(월)\n상품\nD4 (호수뷰,차박 불가)(1)\n풍경소리캠핑장에서 드리는 글\n입실시간 오후 2:00 / 퇴실시간 오전 11:00\n예약자 개인정보',{titles:['풍경소리캠핑장','D4 (호수뷰,차박 불가)']});
result=capture([],{body:detail,modal:detail});assert.equal(result.cards.length,1);assert.match(result.cards[0].text,/예약번호: 1172454330/);assert.match(result.cards[0].text,/사이트명: D4 \(호수뷰,차박 불가\)/);assert.match(result.cards[0].text,/퇴실일: 2026. 5. 25/);assert.doesNotMatch(result.cards[0].text,/마그네틱|개인정보|오후 2/);assert.equal(result.cards[0].cancelled,false);
result=capture([restaurant,activity]);assert.equal(result.cards.length,0);assert.equal(result.handled,true);assert.equal(result.ignored_non_lodging,true);
console.log('Naver lodging and recent mixed lists preserve place/product/date boundaries, prioritize lodging marks and isolate visible detail from policy/ads.');

const statusFirst=node('이용전\n하늘구니 더원\n5.3 일 예약\n상세보기',{titles:['이용전','하늘구니 더원'],marks:['숙박']});assert.match(capture([statusFirst]).cards[0].text,/캠핑장명: 하늘구니 더원/);

const unmarked=node('해돈 텍사스 바베큐 그릴\n8.1 토 오후 7:00 예약\n테이블 예약',{titles:['해돈 텍사스 바베큐 그릴']});assert.equal(capture([unmarked],{body:node('예약·장소\n예약·주문\n'+unmarked.innerText)}).cards.length,0);
