'use strict';
(()=>{
 const defaults={width:220,height:210,font:14};
 const dialog=document.createElement('dialog');dialog.className='calendar-choice-dialog';
 const head=document.createElement('div');head.className='calendar-choice-head';
 const title=document.createElement('strong'),close=document.createElement('button');close.type='button';close.textContent='✕';close.setAttribute('aria-label','연도·월 선택 닫기');head.append(title,close);
 const list=document.createElement('div');list.className='calendar-choice-list';list.setAttribute('role','listbox');dialog.append(head,list);document.body.append(dialog);
 let target=null;
 const dismiss=()=>{dialog.close();target?.focus()};close.onclick=dismiss;
 window.closeCalendarOutside=(box,event)=>{if(event.target!==box)return;const r=box.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)box.close()};
 dialog.addEventListener('click',event=>{if(event.target!==dialog)return;const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dismiss()});
 dialog.addEventListener('cancel',()=>target?.focus());
 function viewport(){if(window.popupViewportGeometry)return window.popupViewportGeometry();const v=window.visualViewport;let top=v?.offsetTop||0,bottom=top+(v?.height||window.innerHeight||800);try{if(window.parent!==window&&window.frameElement){const pv=window.parent.visualViewport,r=window.frameElement.getBoundingClientRect();top=Math.max(top,(pv?.offsetTop||0)-r.top);bottom=Math.min(bottom,(pv?.offsetTop||0)+(pv?.height||window.parent.innerHeight)-r.top)}}catch{}return {offsetTop:Math.max(0,top),height:Math.max(100,bottom-top)}}
 function position(){if(!dialog.open)return;const v=viewport();dialog.style.setProperty('--calendar-choice-view-height',v.height+'px');dialog.style.top=(v.offsetTop+Math.max(12,(v.height-dialog.getBoundingClientRect().height)/2))+'px'}
 window.visualViewport?.addEventListener('resize',position);window.visualViewport?.addEventListener('scroll',position);window.addEventListener?.('resize',position);
 function open(select,kind){
  if(dialog.open)return;target=select;
  const settings=window.calendarChoiceSettings||{},ranges={width:[160,480],height:[120,480],font:[10,24]};
  for(const key of Object.keys(defaults)){const raw=Number(settings[key]),value=Number.isFinite(raw)&&raw>0?raw:defaults[key];dialog.style.setProperty('--calendar-choice-'+key,Math.min(ranges[key][1],Math.max(ranges[key][0],value))+'px')}
  title.textContent=kind==='year'?'연도 선택':'월 선택';dialog.setAttribute('aria-label',title.textContent);list.setAttribute('aria-label',title.textContent);list.replaceChildren();
  const now=new Date(),current=String(kind==='year'?now.getFullYear():now.getMonth());let centered=null;
  for(const option of select.options){const button=document.createElement('button');button.type='button';button.textContent=option.textContent;button.dataset.value=option.value;button.setAttribute('role','option');button.setAttribute('aria-selected',String(option.value===select.value));if(option.value===select.value)button.classList.add('selected');if(option.value===current){button.classList.add('current');button.setAttribute('aria-current','date');centered=button}button.onclick=()=>{select.value=option.value;select.dispatchEvent(new Event('change',{bubbles:true}));dismiss()};list.append(button)}
  const view=viewport();dialog.style.setProperty('--calendar-choice-view-height',view.height+'px');dialog.showModal();position();requestAnimationFrame(()=>{if(!dialog.open||target!==select)return;const button=centered||[...list.children].find(el=>el.dataset.value===select.value)||list.firstElementChild;if(button){list.scrollTop=button.offsetTop-list.offsetTop-(list.clientHeight-button.offsetHeight)/2;button.focus({preventScroll:true})}})
 }
 window.bindCalendarChoice=(select,kind)=>{if(!select||select.dataset.calendarChoice)return;select.dataset.calendarChoice=kind;select.setAttribute('aria-haspopup','dialog');select.addEventListener('pointerdown',event=>{if(event.button!=null&&event.button!==0)return;event.preventDefault();open(select,kind)});select.addEventListener('click',event=>{event.preventDefault();open(select,kind)});select.addEventListener('keydown',event=>{if(['Enter',' ','ArrowDown','ArrowUp'].includes(event.key)){event.preventDefault();open(select,kind)}})};
})();
