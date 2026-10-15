"use strict";
(()=>{
 const form=document.querySelector('#recordForm');
 const normal=value=>String(value||'').normalize('NFKC').trim().replace(/\s+/g,' ');
 // state.records is in registration order (newest first), independent of list sorting.
 window.latestMatchingCampsite=(records,fields)=>{
  const keys=['name','location','platform'];
  if(keys.some(key=>!normal(fields[key])))return null;
  return records.find(record=>keys.every(key=>normal(record[key])===normal(fields[key])))||null;
 };
 let active=false,searched=false,applied=null,linkTouched=false;
 function apply(){
  if(!active||!searched)return;
  const fields=Object.fromEntries(['name','location','platform'].map(key=>[key,form.elements[key].value]));
  const record=window.latestMatchingCampsite(state.records,fields);
  if(applied===(record?.id||null))return;
  applied=record?.id||null;
  if(!linkTouched){form.elements.booking_url.value=record?.booking_url||'';form.elements.booking_url.dispatchEvent(new Event('input'));}
  window.inheritLayoutDraft(record);
  if(record)toast('최근 등록한 기록의 캠핑장 링크·배치도를 가져왔습니다.');
 }
 form.addEventListener('campsite-selected',()=>{searched=true;apply()});
 window.setupRecordInheritance=enabled=>{
  active=enabled;searched=false;applied=null;linkTouched=false;
  form.elements.booking_url.addEventListener('input',event=>{if(event.isTrusted)linkTouched=true});
  for(const key of ['name','location','platform']){
   form.elements[key].addEventListener('input',apply);
   form.elements[key].addEventListener('change',apply);
  }
 };
})();
