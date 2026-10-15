'use strict';
(()=>{
 window.campMapTentSvg='<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M20 3 3 35h34L20 3Z" fill="#edf5e8" stroke="#234e43" stroke-width="2.4" stroke-linejoin="round"/><path d="m20 15-8 20h16z" fill="#234e43"/><path d="M20 15v20" stroke="#a9c6a4" stroke-width="1.5"/></svg>';
 window.currentCampMapDisplay=()=>{const mode=matchMedia('(max-width:700px)').matches?'display_mobile':'desktop',view=state.settings[mode]||{};return {marker:view.map_marker_size||32,label:view.map_label_size||12,button:view.map_button_size||11,gap:view.map_label_gap??3}};
 window.createCampMapMarker=(record,open)=>{const root=document.createElement('div');root.className='camp-map-point';const marker=document.createElement('button');marker.type='button';marker.className='camp-map-marker';marker.innerHTML=window.campMapTentSvg;marker.setAttribute('aria-label',record.name+' 상세정보');marker.title=record.name;const name=document.createElement('button');name.type='button';name.className='camp-map-name';name.textContent=record.name;name.title=record.name;marker.onclick=name.onclick=open;root.append(marker,name);return root};
})();
