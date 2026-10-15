'use strict';
const key=new URLSearchParams(location.hash.slice(1)).get('key');if(key){document.querySelector('#key').value=key;history.replaceState(null,'',location.pathname)}
async function connect(e){e?.preventDefault();const status=document.querySelector('#connectStatus');try{const r=await fetch('api/mobile/session',{method:'POST',headers:{'Content-Type':'application/json','X-Camp-Request':'1'},body:JSON.stringify({key:document.querySelector('#key').value.trim()})});if(!r.ok)throw Error('연결키를 확인해주세요. 홈어시스턴트에서 새 연결키를 만들 수 있습니다.');location.reload()}catch(err){status.textContent=err.message}}
document.querySelector('#connectForm').onsubmit=connect;if(key)connect();
