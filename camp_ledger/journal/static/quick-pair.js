'use strict';
(()=>{const q=s=>document.querySelector(s),button=q('#quickPairDevice'),status=q('#quickPairStatus'),result=q('#quickPairResult');
const android=/Android/i.test(navigator.userAgent),ios=/iPhone|iPad|iPod/i.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1),phone=android||ios;
button.textContent=phone?(ios?'이 기기 연결':'이 휴대폰 연결'):'새 기기 연결';q('#quickPairHint').textContent=phone?'한 번 누르면 연결을 만들고 캠핑 노트를 엽니다. 기기 이름과 연결키는 자동으로 처리합니다.':'한 번 누르면 QR을 표시합니다. 연결할 휴대폰으로 QR을 읽어주세요.';
button.onclick=run(async()=>{if(button.disabled)return;button.disabled=true;status.textContent='연결을 준비하고 있습니다…';result.replaceChildren();try{
 const info=await api('api/mobile/status');if(!info.admin)throw Error('기기 연결은 홈어시스턴트에서 열어주세요.');
 const url=info.external_url||q('#externalUrl').value||'https://ha.badara.co.kr/campsite-journal/';if(!info.enabled||!info.external_url)await api('api/mobile/config','PUT',{enabled:true,external_url:url});
 const stamp=new Intl.DateTimeFormat('ko-KR',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date());
 const data=await api('api/mobile/devices','POST',{name:(android?'안드로이드':ios?'아이폰·아이패드':'QR 연결')+' · '+stamp,platform:android?'android':ios?'ios':'auto'});
 if(phone){const link=document.createElement('a');link.className='button primary quick-pair-link';link.textContent=android?'캠핑 노트 앱으로 연결':'캠핑 노트 열기';link.href=android?data.native:data.link;link.target='_top';result.append(link);status.textContent=android?'앱을 열고 있습니다. 자동으로 열리지 않으면 아래 버튼을 눌러주세요.':'캠핑 노트를 열고 있습니다. 홈 화면 앱은 Safari에서 홈 화면에 추가하세요.';link.click()}
 else{const qr=document.createElement('img');qr.src=data.qr;qr.alt='캠핑 노트 기기 연결 QR';result.append(qr);status.textContent='휴대폰으로 QR을 읽으면 캠핑 노트에 연결됩니다.'}
 await mobileStatus();
 }catch(error){status.textContent=error.message;throw error}finally{button.disabled=false}});
})();
