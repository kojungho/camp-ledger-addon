'use strict';
(()=>{
 const bound=new WeakSet();
 window.setupJournalReorder=container=>{
  if(bound.has(container))return;bound.add(container);
  const dialog=container.closest('dialog'),scroller=dialog.querySelector?.('#prefsBody')||dialog;let drag=null,frame=0;
  const rows=()=>[...container.children].filter(row=>row!==drag?.row);
  const clearMarks=()=>[...container.children].forEach(row=>row.classList.remove('drop-before','drop-after'));
  function paint(){if(!drag)return;drag.row.style.transform='translateY('+(drag.y-drag.startY+scroller.scrollTop-drag.startScroll)+'px)';clearMarks();const remaining=rows();drag.before=remaining.find(row=>drag.y<row.getBoundingClientRect().top+row.getBoundingClientRect().height/2)||null;if(drag.before)drag.before.classList.add('drop-before');else remaining.at(-1)?.classList.add('drop-after')}
  function tick(){if(!drag)return;const bounds=scroller.getBoundingClientRect();const direction=drag.y<bounds.top+56?-1:drag.y>bounds.bottom-56?1:0;if(direction){const max=Math.max(0,scroller.scrollHeight-scroller.clientHeight);scroller.scrollTop=Math.max(0,Math.min(max,scroller.scrollTop+direction*10));paint()}frame=requestAnimationFrame(tick)}
  function finish(commit){if(!drag)return;const current=drag;drag=null;cancelAnimationFrame(frame);clearMarks();current.row.style.transform='';current.row.classList.remove('dragging');current.handle.setAttribute('aria-grabbed','false');document.body.classList.remove('reordering');if(commit)container.insertBefore(current.row,current.before);try{if(current.handle.hasPointerCapture?.(current.id))current.handle.releasePointerCapture(current.id)}catch{}current.handle.focus({preventScroll:true});document.removeEventListener('pointermove',pointerMove,true);document.removeEventListener('pointerup',pointerEnd,true);document.removeEventListener('pointercancel',pointerCancel,true);document.removeEventListener('mousemove',mouseMove,true);document.removeEventListener('mouseup',mouseEnd,true);document.removeEventListener('touchmove',touchMove,true);document.removeEventListener('touchend',touchEnd,true);document.removeEventListener('touchcancel',touchCancel,true);window.removeEventListener('blur',cancel);dialog.removeEventListener('close',cancel)}
  function cancel(){finish(false)}
  function begin(event,point,id){const handle=event.target.closest('.handle');if(!handle||!container.contains(handle)||drag)return;const row=handle.closest('.pref-row');if(row?.parentElement!==container)return;if(event.cancelable)event.preventDefault();event.stopPropagation();window.getSelection?.()?.removeAllRanges();drag={row,handle,id,startY:point.clientY,y:point.clientY,startScroll:scroller.scrollTop,before:row.nextElementSibling};handle.setAttribute('aria-grabbed','true');row.classList.add('dragging');document.body.classList.add('reordering');window.addEventListener('blur',cancel);dialog.addEventListener('close',cancel);paint();frame=requestAnimationFrame(tick);return handle}
  function move(event,point){if(!drag)return;if(event.cancelable)event.preventDefault();drag.y=point.clientY;paint()}
  function pointerMove(e){if(drag?.id===e.pointerId)move(e,e)}
  function pointerEnd(e){if(drag?.id!==e.pointerId)return;move(e,e);finish(true)}
  function pointerCancel(e){if(drag?.id===e.pointerId)finish(false)}
  function mouseMove(e){move(e,e)}function mouseEnd(e){move(e,e);finish(true)}
  function touchMove(e){const point=[...e.touches].find(t=>t.identifier===drag?.id);if(point)move(e,point)}
  function touchEnd(e){const point=[...e.changedTouches].find(t=>t.identifier===drag?.id);if(point){move(e,point);finish(true)}}
  function touchCancel(){finish(false)}
  if(window.PointerEvent){container.addEventListener('pointerdown',e=>{if(e.button!==0||e.isPrimary===false)return;const handle=begin(e,e,e.pointerId);if(!handle)return;try{handle.setPointerCapture(e.pointerId)}catch{}document.addEventListener('pointermove',pointerMove,{capture:true,passive:false});document.addEventListener('pointerup',pointerEnd,true);document.addEventListener('pointercancel',pointerCancel,true)})}
  else{container.addEventListener('touchstart',e=>{if(e.touches.length!==1)return;const point=e.touches[0];if(!begin(e,point,point.identifier))return;document.addEventListener('touchmove',touchMove,{capture:true,passive:false});document.addEventListener('touchend',touchEnd,{capture:true,passive:false});document.addEventListener('touchcancel',touchCancel,true)},{passive:false});container.addEventListener('mousedown',e=>{if(e.button!==0||!begin(e,e,'mouse'))return;document.addEventListener('mousemove',mouseMove,{capture:true,passive:false});document.addEventListener('mouseup',mouseEnd,true)})}
  container.addEventListener('keydown',e=>{const handle=e.target.closest('.handle');if(!handle)return;if(e.key==='Escape'){cancel();return}const row=handle.closest('.pref-row');if(e.key==='ArrowUp'&&row.previousElementSibling){e.preventDefault();row.previousElementSibling.before(row);handle.focus({preventScroll:true})}if(e.key==='ArrowDown'&&row.nextElementSibling){e.preventDefault();row.nextElementSibling.after(row);handle.focus({preventScroll:true})}});
  for(const name of ['selectstart','dragstart','contextmenu','click'])container.addEventListener(name,e=>{if(e.target.closest('.handle')){e.preventDefault();e.stopPropagation()}});
 };
})();
