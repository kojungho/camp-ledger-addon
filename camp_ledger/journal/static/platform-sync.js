'use strict';
(()=>{
 window.campPlatformSyncReady=true;
 const providers={camfit:'캠핏',thankq:'땡큐캠핑',campingtalk:'캠핑톡'},dialog=document.createElement('dialog');dialog.id='platformConnections';
 dialog.innerHTML='<div class="dialog-head"><h2>예약 플랫폼 동기화</h2><button type="button" data-close-platform aria-label="닫기">✕</button></div><p>각 플랫폼에 직접 로그인한 뒤 예약 내역을 여세요. ‘현재 예약 동기화’를 눌렀을 때만 현재 화면에 불러온 예약과 사진을 읽습니다.</p><div id="platformProviders"></div><p id="platformSyncStatus" class="hint" role="status"></p><p class="hint">예약 목록을 스크롤하거나 다음 페이지를 연 뒤 다시 동기화하면 이전 예약도 추가할 수 있습니다. 배치도는 예약 화면의 이미지가 배치도로 확인되는 경우만 가져옵니다. 지원 범위는 실제 로그인 화면에 따라 달라질 수 있습니다.</p>';document.body.append(dialog);
 const status=dialog.querySelector('#platformSyncStatus');let busy=false;
 const supported=()=>Number(window.CampsiteJournalNative?.getPlatformSyncVersion?.()||0)>=1;
 function paint(){const list=dialog.querySelector('#platformProviders');list.replaceChildren();for(const [id,name] of Object.entries(providers)){const button=document.createElement('button');button.type='button';button.className='platform-provider';button.textContent=name+' 로그인 · 예약 열기';button.onclick=()=>{if(!supported()){status.textContent='Android 캠핑 노트 앱 1.0.12 이상에서 사용할 수 있습니다. 앱을 업데이트한 뒤 열어주세요. 아이폰·일반 브라우저에서는 예약 사진·문자 입력을 사용해주세요.';return;}dialog.close();window.CampsiteJournalNative.openPlatform(id)};list.append(button)}}
 document.querySelector('#platformSync').onclick=()=>{paint();status.textContent=supported()?'로그인만으로는 기록이 변경되지 않습니다. 동기화한 내용을 확인하고 반영하세요.':'전용 Android 앱 업데이트가 필요합니다. 앱 실행 시 업데이트하거나 앱 설치·연결에서 설치 파일을 받으세요.';dialog.showModal()};dialog.querySelector('[data-close-platform]').onclick=()=>dialog.close();
 window.addEventListener('message',event=>{
  if(event.origin!==location.origin||(event.source!==window&&event.source!==window.parent)||event.data?.type!=='camp-platform-capture')return;
  const payload=event.data.payload;if(!payload||!providers[payload.provider]||busy)return;
  if(document.querySelector('#editor').open){toast('작성 중인 기록을 먼저 저장하거나 닫고 다시 동기화해주세요.');return;}
  busy=true;window.journalUploading=true;
  (async()=>{try{const result=await api('api/platforms/preview','POST',payload);if(!result.records.length){paint();status.textContent='입력할 예약을 읽지 못했습니다. 예약 상세를 연 뒤 다시 동기화하거나 예약 사진으로 입력해주세요.'+(result.cancelled_skipped?' 취소된 예약 '+result.cancelled_skipped+'건은 제외했습니다.':'');dialog.showModal();return;}edit(null);window.showPlatformReservationReview(result.records);toast('읽은 예약을 확인한 뒤 동기화 반영을 눌러주세요.');}catch(error){toast(error.message)}finally{busy=false;window.journalUploading=false;window.dispatchEvent(new Event('journal-idle'))}})();
 });
})();
