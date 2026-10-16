'use strict';
(()=>{
 window.campPlatformSyncReady=true;
 const providers={camfit:'캠핏',thankq:'땡큐캠핑',campingtalk:'캠핑톡',naver:'네이버'},dialog=document.createElement('dialog');dialog.id='platformConnections';
 dialog.innerHTML='<div class="dialog-head"><h2>예약 플랫폼 동기화</h2><button type="button" data-close-platform aria-label="닫기">✕</button></div><p>플랫폼별 두 계정은 로그인 상태가 서로 분리됩니다. 이름을 저장한 뒤 사용할 계정으로 로그인하고 예약 목록 또는 상세 화면을 여세요.</p><div id="platformProviders"></div><p id="platformSyncStatus" class="hint" role="status"></p><p class="hint">동기화 버튼을 눌렀을 때만 현재 페이지 아래쪽까지 자동 스크롤합니다. 다음 페이지·다른 예약 탭·기간 검색은 직접 열어 다시 동기화하세요. 한 번에 최대 100건이며 읽은 범위를 결과에 표시합니다. 배치도는 예약 화면에서 확인되는 경우만 가져옵니다.</p>';document.body.append(dialog);
 const status=dialog.querySelector('#platformSyncStatus');let busy=false,accountState={};
 const supported=()=>Number(window.CampsiteJournalNative?.getPlatformSyncVersion?.()||0)>=7;
 function paint(){
  const list=dialog.querySelector('#platformProviders');list.replaceChildren();
  for(const [id,name] of Object.entries(providers))for(const account of [1,2]){
   const fallback='계정 '+account,current=accountState[id]?.accounts?.[account]||{},box=document.createElement('div'),row=document.createElement('div'),input=document.createElement('input'),save=document.createElement('button'),button=document.createElement('button');
   box.className='platform-account';row.className='platform-account-name';input.type='text';input.maxLength=30;input.placeholder=fallback;input.value=current.label&&current.label!==fallback?current.label:'';input.setAttribute('aria-label',name+' '+fallback+' 이름');save.type='button';save.textContent='이름 저장';button.type='button';button.className='platform-provider';const label=()=>input.value.trim()||fallback;const update=()=>button.textContent=name+' · '+label()+' 로그인 · 예약 열기';update();
   save.onclick=async()=>{save.disabled=true;button.disabled=true;try{const result=await api('api/platforms/accounts/label','POST',{provider:id,account,label:input.value});input.value=result.label===fallback?'':result.label;accountState[id]??={accounts:{}};accountState[id].accounts??={};accountState[id].accounts[account]={...(accountState[id].accounts[account]||{}),label:result.label};update();status.textContent=name+' '+result.label+' 이름을 저장했습니다. 로그인 상태와 동기화 이력은 유지됩니다.';}catch(error){status.textContent=error.message}finally{save.disabled=false;button.disabled=false}};
   button.onclick=async()=>{if(!supported()){status.textContent='Android 캠핑 노트 앱 1.0.17 이상에서 사용할 수 있습니다. 앱을 업데이트한 뒤 열어주세요. 아이폰·일반 브라우저에서는 예약 사진·문자 입력을 사용해주세요.';return;}button.disabled=true;try{const history=await api('api/platforms/state');accountState=history;window.CampsiteJournalNative.openPlatformAccount(id,account,JSON.stringify(history[id]?.accounts?.[account]||{}));dialog.close();}catch(error){status.textContent=error.message}finally{button.disabled=false}};
   row.append(input,save);box.append(row,button);list.append(box);
  }
 }
 document.querySelector('#platformSync').onclick=async()=>{dialog.querySelector('#platformProviders').replaceChildren();status.textContent='계정 정보를 불러오고 있습니다…';dialog.showModal();try{accountState=await api('api/platforms/state');paint();status.textContent=supported()?'최신순 목록에서 이전에 동기화한 예약을 만나면 읽기를 멈춥니다. 새 예약은 기본으로 모두 선택됩니다. 취소된 예약은 표시되지만 선택할 수 없습니다.':'전용 Android 앱 1.0.17 업데이트가 필요합니다. 앱 실행 시 업데이트하거나 앱 설치·연결에서 설치 파일을 받으세요.';}catch(error){status.textContent=error.message}};
 dialog.querySelector('[data-close-platform]').onclick=()=>dialog.close();
 window.addEventListener('message',event=>{
  if(event.origin!==location.origin||(event.source!==window&&event.source!==window.parent)||event.data?.type!=='camp-platform-capture')return;
  const payload=event.data.payload;if(!payload||!providers[payload.provider]||busy)return;
  if(document.querySelector('#editor').open){toast('작성 중인 기록을 먼저 저장하거나 닫고 다시 동기화해주세요.');return;}
  busy=true;window.journalUploading=true;
  (async()=>{try{
   const result=await api('api/platforms/preview','POST',payload);
   if(!result.records.length){paint();status.textContent=(result.already_synced?'새로 가져올 예약이 없습니다. 이미 반영한 예약 '+result.already_synced+'건을 제외했습니다.':result.ignored_non_lodging?'식당·체험 등 숙박이 아닌 예약은 제외했습니다. 숙박 마크가 있는 예약 목록이나 숙박 상세 화면에서 동기화해주세요.':'입력할 예약을 읽지 못했습니다. 예약 상세를 연 뒤 다시 동기화하거나 예약 사진으로 입력해주세요.')+(result.scan_truncated?' 읽기 제한에 도달해 아직 읽지 않은 예약이 있을 수 있습니다.':'');dialog.showModal();return;}
   edit(null);document.querySelector('#editorTitle').textContent='동기화 예약 확인';window.showPlatformReservationReview(result.records);
   const notice=document.createElement('p');notice.className='hint';notice.textContent=(result.scan_truncated?'읽기 제한에 도달했습니다. 아직 읽지 않은 아래쪽 예약이 있을 수 있습니다.':result.stopped_at_synced?'이전에 동기화한 예약을 만나 읽기를 멈췄습니다. 그 앞의 새 예약만 표시합니다.':'현재 페이지의 아래쪽까지 읽었습니다.')+' 다음 페이지·다른 탭·기간 검색 내역은 별도로 동기화하세요.';document.querySelector('#reservationScanResults').prepend(notice);
   const cancelled=result.records.filter(row=>row.cancelled===true).length;
   toast(cancelled===result.records.length?(cancelled===1?'등록 불가: 취소된 예약입니다.':'등록 불가: 인식된 예약 '+cancelled+'건이 모두 취소된 예약입니다.'):'예약 '+result.records.length+'건을 확인하고 선택한 건만 반영하세요.'+(cancelled?' 취소 예약 '+cancelled+'건은 등록할 수 없습니다.':'')+(result.already_synced?' 기존 '+result.already_synced+'건 제외.':''));
  }catch(error){toast(error.message)}finally{busy=false;window.journalUploading=false;window.dispatchEvent(new Event('journal-idle'))}})();
 });
})();
