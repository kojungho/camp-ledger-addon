'use strict';
(()=>{
 const today=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 window.campStayStatus=(record,day=today())=>{
  if(!/^\d{4}-\d{2}-\d{2}$/.test(record.checkin||''))return '';
  const pending=day<record.checkin,active=!pending&&record.checkout&&day<record.checkout;
  if(!pending&&!active)return '';
  return '<span class="stay-status '+(pending?'stay-pending':'stay-active')+'">'+(pending?'이용전':'이용중')+'</span>';
 };
 let previous=today();
 window.setInterval?.(()=>{const day=today();if(day!==previous){previous=day;window.refreshStayStatuses?.()}},30000);
})();
