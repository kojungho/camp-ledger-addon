 'use strict';
(()=>{const q=s=>document.querySelector(s),key=new URLSearchParams(location.hash.slice(1)).get('key'),android=/Android/i.test(navigator.userAgent);if(key){q('#key').value=key;history.replaceState(null,'',location.pathname+location.search)}
async function connect(e){e?.preventDefault();const status=q('#connectStatus');status.textContent='캠핑 노트에 연결하고 있습니다…';try{const value=q('#key').value.trim();const r=await fetch('api/mobile/session',{method:'POST',headers:{'Content-Type':'application/json','X-Camp-Request':'1'},body:JSON.stringify({key:value})});if(!r.ok)throw Error('연결키를 확인해주세요. 홈어시스턴트에서 새 연결을 만들 수 있습니다.');window.CampsiteJournalNative?.flushCookies?.();if(window.parent!==window){parent.postMessage({type:'camp-connected'},location.origin);location.replace('./?camp_hub=1')}else location.replace('hub')}catch(err){status.textContent=err.message;q('#connectForm').hidden=false}}
q('#connectForm').onsubmit=connect;q('#connectBrowser').onclick=connect;
if(key&&/^[A-Za-z0-9_-]{40,100}$/.test(key)){
 if(android&&!new URLSearchParams(location.search).has('browser')){const base=new URL('./',location.href).href,fallback=base+'connect?browser=1#key='+encodeURIComponent(key),native='intent://connect?url='+encodeURIComponent(base)+'#Intent;scheme=campsite-journal;package=co.kr.badara.campsitejournal;S.key='+key+';S.browser_fallback_url='+encodeURIComponent(fallback)+';end';q('#connectApp').href=native;q('#quickConnectActions').hidden=false;q('#connectForm').hidden=true;q('#connectStatus').textContent='캠핑 노트 앱을 열고 있습니다…';location.href=native}
 else connect();
}
})();
