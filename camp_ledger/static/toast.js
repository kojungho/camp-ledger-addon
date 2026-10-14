"use strict";
(()=>{const stack=[];let timer;const dialogs=()=>Array.from(document.querySelectorAll('dialog[open]'));document.querySelectorAll('dialog').forEach(dialog=>dialog.addEventListener('toggle',()=>{const at=stack.indexOf(dialog);if(at>=0)stack.splice(at,1);if(dialog.open)stack.push(dialog);}));
window.showToast=message=>{const box=document.getElementById('toast'),focused=document.activeElement?.closest('dialog[open]'),top=focused||stack.filter(d=>d.open).at(-1)||dialogs().at(-1);(top||document.body).append(box);box.textContent=String(message||'');box.classList.add('show');clearTimeout(timer);timer=setTimeout(()=>box.classList.remove('show'),8000);};
})();
