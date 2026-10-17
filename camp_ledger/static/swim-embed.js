'use strict';
(()=>{
 const original=window.fetch.bind(window),prefix=new URL('./',location.href).pathname;
 window.fetch=async(input,options)=>{
  const url=new URL(input instanceof Request?input.url:String(input),document.baseURI),method=String(options?.method||(input instanceof Request?input.method:'GET')).toUpperCase();
  if(url.origin===location.origin&&url.pathname.startsWith(prefix)&&['POST','PUT','DELETE'].includes(method)){
   const headers=new Headers(options?.headers||(input instanceof Request?input.headers:undefined));headers.set('X-Camp-Request','1');options={...options,headers};
  }
  const response=await original(input,options);
  if(response.status===401&&url.origin===location.origin&&url.pathname.startsWith(prefix)&&window.parent!==window)window.parent.postMessage({type:'camp-auth-lost'},location.origin);
  return response;
 };
 document.addEventListener('DOMContentLoaded',()=>{const retry=document.getElementById('swimRetry');if(retry)retry.onclick=()=>location.reload()},{once:true});
})();
