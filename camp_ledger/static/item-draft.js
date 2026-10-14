"use strict";
(()=>{
const dialog=document.getElementById('item-dialog'),form=document.getElementById('item-form');
const key='camp-ledger-item-draft-v1',fallbackKey=key+'-picker';
let queue=Promise.resolve(),restored=false,restoring=false,pickerTimer=0,lastFiles='',warned=false,intentionalClose=false,returnUntil=0;
function read(storage,k){try{return JSON.parse(storage.getItem(k)||'null')}catch{return null}}
const fallback=read(localStorage,fallbackKey);
let recovery=read(sessionStorage,key)||(fallback&&Date.now()-fallback.at<300000?fallback:null);
const storageId=recovery?.storageId||crypto.randomUUID();let pickerRecovery=!!recovery;
window.itemDraftRestoring=!!recovery;
const db=new Promise((resolve,reject)=>{const request=indexedDB.open('camp-ledger-edit-drafts',1);request.onupgradeneeded=()=>request.result.createObjectStore('photos');request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error)});
db.catch(()=>{});
function photoStore(mode,action){return db.then(database=>new Promise((resolve,reject)=>{const tx=database.transaction('photos',mode);const request=action(tx.objectStore('photos'));let value;request.onsuccess=()=>value=request.result;tx.oncomplete=()=>resolve(value);tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error)}));}
function snapshot(){const values={};for(const input of form.querySelectorAll('[name]:not([type=file])')){values[input.name]=input.matches('[data-date-picker]')?dateInputISO(input):input.type==='checkbox'?input.checked:input.value;}
return{at:Date.now(),storageId,current,values,disposed:document.getElementById('disposed-check').checked,deleted:[...deleted],operations,dirty,picker:!!window.photoPickerActive,scroll:dialog.querySelector('.modal-body').scrollTop,files:files.map(f=>({name:f.file.name,kind:f.kind,size:f.file.size}))};}
function persist(){if(restoring||!dialog.open)return;const draft=snapshot();try{sessionStorage.setItem(key,JSON.stringify(draft));if(pickerRecovery)localStorage.setItem(fallbackKey,JSON.stringify(draft))}catch{}
const signature=files.map(f=>f.url).join('|');if(signature===lastFiles)return;lastFiles=signature;const saved=files.map(f=>({file:f.file,kind:f.kind}));queue=queue.catch(()=>{}).then(()=>photoStore('readwrite',store=>store.put(saved,storageId))).catch(()=>{if(!warned&&saved.length){warned=true;toast('사진 임시 보관이 어려워요. 화면이 다시 열리면 사진을 다시 선택해주세요.')}});}
window.persistItemDraft=persist;window.beginItemDraft=()=>{intentionalClose=false;returnUntil=0;};
window.clearItemDraft=()=>{intentionalClose=true;pickerRecovery=false;window.photoPickerActive=false;clearTimeout(pickerTimer);recovery=null;lastFiles='';try{sessionStorage.removeItem(key);if(read(localStorage,fallbackKey)?.storageId===storageId)localStorage.removeItem(fallbackKey)}catch{}queue=queue.catch(()=>{}).then(()=>photoStore('readwrite',store=>store.delete(storageId))).catch(()=>{});};
function ensurePopup(){if(intentionalClose||(!window.photoPickerActive&&Date.now()>returnUntil&&!(pickerRecovery&&dirty)))return;if(!dialog.open){const body=dialog.querySelector('.modal-body'),position=body.scrollTop;dialog.showModal();document.getElementById('save-item').focus({preventScroll:true});body.scrollTop=position;window.dispatchEvent(new Event('resize'));}persist();}
function pollPhotoResult(){for(const input of form.querySelectorAll('#photos,#receipts'))window.collectPhotoFiles?.(input);}
function finishPicker(){clearTimeout(pickerTimer);pollPhotoResult();returnUntil=Date.now()+2500;ensurePopup();persist();pickerTimer=setTimeout(()=>{pollPhotoResult();window.photoPickerActive=false;ensurePopup();persist();},2500);window.dispatchEvent(new Event('resize'));}
form.addEventListener('click',e=>{if(!e.target.matches('#photos,#receipts')&&!e.target.closest('[data-photo-picker]'))return;clearTimeout(pickerTimer);window.photoPickerActive=true;window.photoPickerReceived=false;pickerRecovery=true;persist();},true);
form.addEventListener('cancel',e=>{if(e.target.matches('#photos,#receipts'))finishPicker();},true);
form.addEventListener('change',e=>{if(e.target.matches('#photos,#receipts'))finishPicker();else persist();});form.addEventListener('input',persist);
form.addEventListener('click',()=>setTimeout(persist,0));
window.addEventListener('focus',()=>{pollPhotoResult();ensurePopup();if(window.photoPickerActive)pickerTimer=setTimeout(finishPicker,1500)});
document.addEventListener('visibilitychange',()=>{clearTimeout(pickerTimer);if(document.hidden)persist();else{pollPhotoResult();ensurePopup();if(window.photoPickerActive)pickerTimer=setTimeout(finishPicker,1500)}});
window.addEventListener('pagehide',persist);
dialog.addEventListener('close',()=>queueMicrotask(ensurePopup));dialog.addEventListener('toggle',()=>{if(!dialog.open)queueMicrotask(ensurePopup);});
async function restore(){if(restored||restoring||!state.settings)return;restored=true;if(!recovery){window.itemDraftRestoring=false;return;}if(Date.now()-recovery.at>86400000){window.clearItemDraft();window.itemDraftRestoring=false;return;}if(dialog.open){window.itemDraftRestoring=false;return;}restoring=true;const draft=recovery;
try{let saved=[];try{saved=await photoStore('readonly',store=>store.get(storageId))||[]}catch{}
openItem(draft.current?.id);current=draft.current||null;
for(const [name,value] of Object.entries(draft.values)){const input=form.querySelector(`[name="${name}"]`);if(!input)continue;if(input.type==='checkbox')input.checked=!!value;else{if(input.tagName==='SELECT'&&value&&!Array.from(input.options).some(o=>o.value===value))input.add(new Option(value,value));input.value=value;if(input.matches('[data-date-picker]'))delete input.dataset.isoValue;}}
window.formatDateInputs?.(form);document.getElementById('disposed-check').checked=draft.disposed;deleted=new Set(draft.deleted);operations=draft.operations||[];files=saved.map(f=>({...f,url:URL.createObjectURL(f.file)}));dirty=draft.dirty||files.length>0;statusUI();renderStock();renderPurchases();renderPhotos();renderHistory();dialog.querySelector('.modal-body').scrollTop=draft.scroll||0;window.refreshLiveNotices?.();
toast((draft.picker||draft.files.length)&&!saved.length?'입력 내용을 복구했습니다. 사진은 다시 선택해주세요.':'저장 전 입력 내용과 사진을 복구했습니다.');
}finally{restoring=false;window.itemDraftRestoring=false;window.photoPickerActive=false;persist();}}
const updated=window.onLedgerStateUpdated;window.onLedgerStateUpdated=remote=>{updated?.(remote);restore().catch(()=>{window.itemDraftRestoring=false;toast('이전 입력 복구에 실패했습니다. 내용을 확인해주세요.');});};
if(state.settings)restore().catch(()=>window.itemDraftRestoring=false);
})();
