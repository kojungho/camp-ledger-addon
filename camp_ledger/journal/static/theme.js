'use strict';
(()=>{
 const key='campNoteTheme',modes=['system','light','dark'],root=document.documentElement,media=window.matchMedia('(prefers-color-scheme: dark)');let mode='system';
 try{const saved=localStorage.getItem(key);if(modes.includes(saved))mode=saved}catch{}
 function systemTheme(){try{const native=window.CampsiteJournalNative||window.CampLedgerNative,value=native?.getSystemTheme?.();if(value==='dark'||value==='light')return value}catch{}return media.matches?'dark':'light'}
 function apply(){const theme=mode==='system'?systemTheme():mode;root.dataset.campTheme=theme;root.dataset.campThemeMode=mode;root.style.colorScheme=theme;document.querySelectorAll('meta[name="theme-color"]').forEach(meta=>meta.content=theme==='dark'?'#101214':'#fafbf7');document.querySelectorAll('[data-camp-theme-select]').forEach(select=>select.value=mode)}
 function forward(exclude){const message={type:'camp-theme-change',mode};if(window.parent!==window&&window.parent!==exclude)window.parent.postMessage(message,location.origin);document.querySelectorAll('iframe').forEach(frame=>{if(frame.contentWindow&&frame.contentWindow!==exclude)frame.contentWindow.postMessage(message,location.origin)})}
 function setMode(value,source){if(!modes.includes(value))return;mode=value;try{localStorage.setItem(key,mode)}catch{}apply();forward(source)}
 window.CampTheme={getMode:()=>mode,setMode:value=>setMode(value),refreshSystemTheme:()=>{if(mode==='system')apply()}};
 window.addEventListener('storage',event=>{if(event.key===key||event.key===null){mode=modes.includes(event.newValue)?event.newValue:'system';apply()}});
 window.addEventListener('message',event=>{if(event.origin!==location.origin||event.data?.type!=='camp-theme-change')return;const trusted=event.source===window.parent&&window.parent!==window||[...document.querySelectorAll('iframe')].some(frame=>frame.contentWindow===event.source);if(trusted)setMode(event.data.mode,event.source)});
 const changed=()=>{if(mode==='system')apply()};if(media.addEventListener)media.addEventListener('change',changed);else media.addListener?.(changed);
 window.addEventListener('focus',changed);document.addEventListener('visibilitychange',changed);
 apply();
 function mount(){apply();const panel=document.querySelector('#commonPrefsPanel,#common-display-settings');if(!panel||panel.querySelector('[data-camp-theme-select]'))return;const section=document.createElement('section');section.className='camp-theme-settings';section.innerHTML='<label><span>화면 모드</span><select data-camp-theme-select aria-label="화면 모드"><option value="system">기기 설정에 맞추기</option><option value="light">라이트</option><option value="dark">다크</option></select></label><p>선택 즉시 기록과 장부에 함께 적용되며, 이 기기에 저장됩니다.</p>';panel.prepend(section);const select=section.querySelector('select');select.value=mode;select.addEventListener('change',()=>setMode(select.value))}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})();
