"use strict";
(()=>{
 const root=document.querySelector('#detailRating');
 window.renderRecordRating=record=>{
  let rating=Math.max(0,Math.min(5,Number(record.rating)||0));
  const blocked=()=>Boolean(window.campStayStatus?.(record));
  const unavailable=value=>blocked()&&value!==rating;
  root.innerHTML=Array.from({length:5},(_,i)=>'<button type="button" role="radio" class="rating-star" data-rating="'+(i+1)+'" aria-label="'+(i+1)+'점'+(rating===i+1?', 다시 누르면 평가 삭제':'')+'" aria-checked="'+(rating===i+1)+'"'+(unavailable(i+1)?' disabled title="이용 완료 후 평가할 수 있습니다."':(rating===i+1?' title="평가 삭제"':''))+'><span aria-hidden="true">'+(i<rating?'⭐️':'☆')+'</span></button>').join('');
  root.querySelectorAll('[data-rating]').forEach(button=>button.onclick=run(async()=>{
   const value=Number(button.dataset.rating),next=value===rating?0:value;
   if(next&&blocked())return;
   root.querySelectorAll('button').forEach(b=>b.disabled=true);
   try{await api('api/records/'+record.id+'/rating','PUT',{rating:next});record.rating=rating=next;await reload();}
   finally{root.querySelectorAll('button').forEach(b=>b.disabled=unavailable(Number(b.dataset.rating)));}
  }));
 };
})();
