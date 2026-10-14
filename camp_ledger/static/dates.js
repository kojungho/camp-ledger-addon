"use strict";
window.dateISO=value=>{const s=String(value||'');if(/^\d{4}-\d{2}-\d{2}$/.test(s))return s;if(/^\d{2}\.\d{2}\.\d{2}$/.test(s))return '20'+s.replaceAll('.','-');return s;};
window.dateLabel=value=>{const s=window.dateISO(value);return /^\d{4}-\d{2}-\d{2}$/.test(s)?s.slice(2).replaceAll('-','.'):s;};
window.dateInputISO=e=>e?.dataset.isoValue&&window.dateLabel(e.dataset.isoValue)===e.value?e.dataset.isoValue:window.dateISO(e?.value);
window.formatDateInputs=root=>root.querySelectorAll('[data-date-picker]').forEach(e=>{if(/^\d{4}-\d{2}-\d{2}$/.test(e.value))e.dataset.isoValue=e.value;e.value=window.dateLabel(e.value);});
