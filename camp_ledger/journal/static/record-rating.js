"use strict";
(()=>{
 const root=document.querySelector('#detailRating');
 window.renderRecordRating=record=>{
  const rating=Math.max(0,Math.min(5,Number(record.rating)||0));
  root.innerHTML=Array.from({length:5},(_,i)=>'<button type="button" role="radio" class="rating-star" data-rating="'+(i+1)+'" aria-label="'+(i+1)+'점" aria-checked="'+(rating===i+1)+'"><span aria-hidden="true">'+(i<rating?'⭐️':'☆')+'</span></button>').join('');
  root.querySelectorAll('[data-rating]').forEach(button=>button.onclick=run(async()=>{
   root.querySelectorAll('button').forEach(b=>b.disabled=true);
   try{await api('api/records/'+record.id+'/rating','PUT',{rating:Number(button.dataset.rating)});await reload();}
   finally{root.querySelectorAll('button').forEach(b=>b.disabled=false);}
  }));
 };
})();
