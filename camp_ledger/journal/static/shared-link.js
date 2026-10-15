'use strict';
(()=>{
 const bound=new WeakSet();
 window.extractSharedUrl=text=>{
  const source=String(text||'').replace(/[\u200b-\u200f\u2060\ufeff]/g,'');
  for(const match of source.matchAll(/https?:\/\/[^\s<>"'`“”‘’「」『』]+/gi)){
   let value=match[0].replace(/[.,;!。，；！、]+$/u,'');
   for(const [open,close] of [['(',')'],['[',']'],['{','}'],['（','）'],['【','】']]){
    while(value.endsWith(close)&&value.split(close).length>value.split(open).length)value=value.slice(0,-1);
   }
   try{const url=new URL(value);if(['https:','http:'].includes(url.protocol)&&url.hostname)return value}catch{}
  }
  return null;
 };
 window.bindSharedLinkInput=input=>{
  if(bound.has(input))return;bound.add(input);
  input.addEventListener('paste',event=>{
   const text=event.clipboardData?.getData('text/plain'),url=window.extractSharedUrl(text);
   if(!url)return;
   event.preventDefault();input.value=url;input.dispatchEvent(new Event('input',{bubbles:true}));
  });
  // Some mobile keyboards insert clipboard text through input rather than paste.
  // Leave a plain URL alone while typing so dots and query punctuation remain editable.
  input.addEventListener('input',()=>{
   const text=input.value;if(/^https?:\/\/\S+$/i.test(text))return;
   const url=window.extractSharedUrl(text);if(url)input.value=url;
  });
 };
})();
