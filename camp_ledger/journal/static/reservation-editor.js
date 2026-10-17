'use strict';
(()=>{
 let previousLabel=null;
 window.setReservationReviewMode=(handler,count=0,action='등록')=>{
  const manual=document.querySelector('#manualRecordFields'),submit=document.querySelector('#recordSubmit');
  window.submitReservationReview=handler;
  manual.hidden=Boolean(handler);manual.querySelectorAll('[name]').forEach(input=>input.disabled=Boolean(handler));
  if(handler){if(previousLabel===null)previousLabel=submit.textContent;submit.textContent='선택한 '+count+'건 '+action;submit.disabled=count===0;}
  else{if(previousLabel!==null)submit.textContent=previousLabel;previousLabel=null;submit.disabled=false;}
 };
 window.setupReservationEditor=({card,row})=>{
  const elements=Object.fromEntries([...card.querySelectorAll('[data-review-field]')].map(input=>[input.dataset.reviewField,input]));
  const target={elements,get isConnected(){return card.isConnected},dispatchEvent:event=>card.dispatchEvent(event),addEventListener:(...args)=>card.addEventListener(...args)};
  const status=card.querySelector('[data-review-geo]');
  const ci=elements.checkin.closest('label'),co=elements.checkout.closest('label'),stay=document.createElement('div');stay.className='stay-input-row wide';ci.before(stay);stay.append(ci,co);
  window.setupStayPicker(target);window.setupCampsiteFinder(target,status);window.setupRecordInputLinks(target);
  elements.location.placeholder='주소 검색에서 선택하거나 도로명주소를 입력하세요.';
  elements.location.oninput=()=>{elements.lat.value='';elements.lng.value='';status.textContent='주소를 변경했습니다. 주소 검색에서 선택하면 지도 위치도 갱신됩니다.'};
  card.querySelector('[data-review-address]').onclick=run(()=>window.openAddressSearch(target,status));
  card.querySelector('[data-review-position]').onclick=run(()=>window.openMapPosition(target,status));
  window.setupRecordInheritance(true,target,record=>{
   row.inherit_from=record?.id||null;
   const preview=card.querySelector('[data-review-inherited]');preview.replaceChildren();
   if(!record)return;
   const photos=record.photos||[],cover=photos.find(p=>p.kind==='gallery'&&p.is_cover)||photos.find(p=>p.kind==='gallery'),layout=photos.find(p=>p.kind==='layout'&&p.is_cover)||photos.find(p=>p.kind==='layout');
   for(const photo of photos.filter(p=>p===layout||(!row.thumbnail&&p===cover))){
    const figure=document.createElement('figure'),image=document.createElement('img'),caption=document.createElement('figcaption');image.src='photos/'+photo.id;image.alt=photo.kind==='layout'?'배치도':'대표 사진';caption.textContent=image.alt;figure.append(image,caption);preview.append(figure);
   }
  });
  // Reclassification writes must follow the same change/inheritance rules as typing.
  return target;
 };
})();
