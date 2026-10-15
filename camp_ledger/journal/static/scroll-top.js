 'use strict';
(()=>{const button=document.getElementById('scrollTop');const update=()=>button.hidden=window.scrollY<240;window.applyScrollTop=position=>{button.dataset.position=position;update()};window.addEventListener('scroll',update,{passive:true});button.onclick=()=>window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});update()})();
