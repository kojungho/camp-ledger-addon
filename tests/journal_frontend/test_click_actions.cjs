const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
(async()=>{
 const src=fs.readFileSync('camp_ledger/journal/static/app.js','utf8'),calls=[];
 const nodes={'#duplicateNoticeText':{},'#duplicateNotice':{open:false,showModal(){this.open=true}}};
 const record={id:'r',name:'캠핑장',location:'주소'};
 const actions={list:{name:{copy:true,map:false},location:{copy:false,map:true}},detail:{name:{copy:false,map:false},location:{copy:true,map:true}}};
 const c={state:{settings:{click_actions:actions},records:[record]},$:k=>nodes[k],window:{openAddressApps:(r,source)=>calls.push(['map',source])},copyValue:async value=>calls.push(['copy',value]),toast:msg=>calls.push(['toast',msg])};
 vm.createContext(c);
 vm.runInContext(src.slice(src.indexOf('function showDuplicateNotice('),src.indexOf('function detailOrder(')),c);
 for(const [view,key,expected]of [['list','name',[['copy','캠핑장']]],['list','location',[['map','address']]],['detail','name',[]],['detail','location',[['copy','주소'],['map','address']]]]){calls.length=0;await c.performFieldAction(record,key,view);assert.deepEqual(calls,expected)}
 vm.runInContext(src.slice(src.indexOf('function run('),src.indexOf('async function reload(')),c);
 await c.run(()=>{const error=new Error('이미 등록');error.code='duplicate_record';throw error})();
 assert.equal(nodes['#duplicateNotice'].open,true);assert.equal(nodes['#duplicateNoticeText'].textContent,'이미 등록');
 const edits=[];c.edit=(...args)=>edits.push(args);
 vm.runInContext(src.slice(src.indexOf('function duplicateRecord('),src.indexOf("$('#clearSelected').onclick=")),c);
 c.state.settings.duplicate_enabled=false;c.state.settings.detail_duplicate_enabled=true;c.duplicateRecord('r');c.duplicateRecord('r','detail');assert.equal(edits.length,1);assert.equal(edits[0][0],record);
 c.state.settings.duplicate_enabled=true;c.state.settings.detail_duplicate_enabled=false;c.duplicateRecord('r');c.duplicateRecord('r','detail');assert.equal(edits.length,2);
 console.log('Independent field copy/map actions, detail/list clone switches and visible duplicate notice passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
