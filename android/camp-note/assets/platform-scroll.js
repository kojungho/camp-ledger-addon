(function(capture){
 'use strict';
 const limit=100,start=Date.now(),page=location.href,originals=new Map(),cards=new Map();const expansion=typeof window!=='undefined'?window.__campNoteFields?.expander():null;let rounds=0,stable=0,lastCount=0,finished=false,initialized=false,lastBatch=[],moveNext=false,movedLast=false,ignoredNonLodging=false;
 function roots(){const pageRoot=document.scrollingElement||document.documentElement;const list=pageRoot?[pageRoot]:[];for(const el of [...document.querySelectorAll('main,section,div,ul')].slice(0,2000)){if(el===pageRoot||el===document.body||el.clientHeight<100||el.scrollHeight<=el.clientHeight+40)continue;const style=getComputedStyle(el);if(/auto|scroll/.test(style.overflowY)&&el.getBoundingClientRect().width>0)list.push(el)}for(const el of list)if(!originals.has(el))originals.set(el,el.scrollTop);return [...new Set(list)]}
 function restore(){expansion?.restore();for(const [el,top] of originals)el.scrollTop=top;finished=true}
 function keyOf(card){const ids=[...card.text.matchAll(/예약\s*(?:번호|코드)\s*[:：#]?\s*([A-Za-z0-9][A-Za-z0-9_-]{4,79})/g)];return card.single_card&&ids.length===1?'id:'+ids[0][1]:card.text}
 function snapshot(){lastBatch=[];const data=JSON.parse(capture());if(data.error){if(!cards.size&&/로그인/.test(data.error))return data.error;return null}ignoredNonLodging=ignoredNonLodging||data.ignored_non_lodging===true;lastBatch=data.cards||[];for(const card of lastBatch){const key=keyOf(card),old=cards.get(key);if(old){old.cancelled=old.cancelled||card.cancelled;old.fields={...old.fields,...card.fields};old.media=[...old.media,...card.media].filter((p,i,all)=>all.findIndex(q=>q.url===p.url)===i).slice(0,4)}else if(cards.size<limit)cards.set(key,card)}}
 function stopAtSynced(index){const marker=lastBatch[index];if(!marker)return JSON.stringify({error:'동기화 중단 기준을 확인하지 못했습니다.'});const key=keyOf(marker),fresh=[];for(const [id,card] of cards){if(id===key){if(card.cancelled)fresh.push(card);break}fresh.push(card)}const collapsed=expansion?.pending()||false;restore();return JSON.stringify({collapsed_unread:collapsed,done:true,cards:fresh,batch:[],stopped_at_synced:true,already_synced:1,ignored_non_lodging:ignoredNonLodging,scan_truncated:false,scan_reason:'checkpoint'})}
 function finish(reason){const collapsed=expansion?.pending()||false;restore();return JSON.stringify({collapsed_unread:collapsed,done:true,cards:[...cards.values()],batch:lastBatch,ignored_non_lodging:ignoredNonLodging,scan_truncated:!!reason,scan_reason:reason||''})}
 function step(){
  if(finished)return JSON.stringify({error:'예약 읽기가 취소되었습니다.'});
  if(location.href!==page){restore();return JSON.stringify({error:'읽는 중에 페이지가 변경되었습니다. 예약 화면에서 다시 동기화해주세요.'})}
  if(Date.now()-start>=90000)return finish('time');
  if(!document.body||document.readyState==='loading')return JSON.stringify({done:false,count:cards.size,batch:[]});
  if(!initialized){for(const el of roots())el.scrollTop=0;initialized=true;return JSON.stringify({done:false,count:0,batch:[]})}
  if(moveNext){movedLast=false;for(const el of roots()){const next=Math.min(Math.max(0,el.scrollHeight-el.clientHeight),el.scrollTop+Math.max(120,Math.floor(el.clientHeight*.8)));if(next>el.scrollTop+2){el.scrollTop=next;movedLast=true}}moveNext=false;return JSON.stringify({done:false,count:cards.size,batch:[]})}
  if(expansion?.expand())return JSON.stringify({done:false,count:cards.size,batch:[]});
  moveNext=true;const error=snapshot();if(error){restore();return JSON.stringify({error})}rounds++;
  if(cards.size>=limit)return finish('limit');if(rounds>=140||Date.now()-start>=90000)return finish('time');
  if(!movedLast&&cards.size===lastCount)stable++;else stable=0;lastCount=cards.size;
  const loading=[...document.querySelectorAll('[aria-busy="true"],[role="progressbar"],.loading,.spinner')].some(el=>el.getBoundingClientRect().width>0&&el.getBoundingClientRect().height>0);if(loading||(!cards.size&&Date.now()-start<6000))stable=0;
  if(stable>=6)return finish('');return JSON.stringify({done:false,count:cards.size,batch:lastBatch})
 }
 return {step,stopAtSynced,cancel:restore};
})
