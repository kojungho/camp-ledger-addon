"use strict";
(()=>{
 const form=document.querySelector('#recordForm'),contexts=new WeakMap();
 const normal=value=>String(value||'').normalize('NFKC').trim().replace(/\s+/g,' ');
 // Registration order, rather than visit date, determines the latest source.
 window.latestMatchingCampsite=(records,fields)=>{
  const keys=['name','location','platform'];
  if(keys.some(key=>!normal(fields[key])))return null;
  return records.find(record=>keys.every(key=>normal(record[key])===normal(fields[key])))||null;
 };
 window.setupRecordInheritance=(enabled,target=form,onInherit=window.inheritLayoutDraft)=>{
  let context=contexts.get(target);
  if(!context){
   context={watched:new WeakSet()};contexts.set(target,context);
   context.apply=()=>{
    if(!context.active||!context.searched)return;
    const fields=Object.fromEntries(['name','location','platform'].map(key=>[key,target.elements[key].value]));
    const record=window.latestMatchingCampsite(state.records,fields);
    if(context.applied===(record?.id||null))return;
    context.applied=record?.id||null;
    if(!context.linkTouched){target.elements.booking_url.value=record?.booking_url||'';target.elements.booking_url.dispatchEvent(new Event('input'));}
    context.onInherit?.(record);
    if(record)toast('최근 등록한 기록의 캠핑장 링크·배치도·대표 사진을 가져왔습니다.');
   };
   target.addEventListener('campsite-selected',()=>{context.searched=true;context.apply()});
  }
  Object.assign(context,{active:enabled,searched:false,applied:null,linkTouched:false,onInherit});
  const link=target.elements.booking_url;
  if(!context.watched.has(link)){context.watched.add(link);link.addEventListener('input',event=>{if(event.isTrusted)context.linkTouched=true});}
  for(const key of ['name','location','platform']){
   const input=target.elements[key];if(context.watched.has(input))continue;context.watched.add(input);
   input.addEventListener('input',context.apply);input.addEventListener('change',context.apply);
  }
 };
})();
