// Run against an isolated local development server. Never point this at production data.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
 const base=process.env.CAMP_SETTINGS_TEST_URL||'http://127.0.0.1:8765/';assert.match(base,/^http:\/\/(127\.0\.0\.1|localhost):\d+\/$/);
 const browser=await chromium.launch({headless:true});try{
 for(const mobile of [false,true])for(const journal of [true,false]){
  const page=await browser.newPage({viewport:mobile?{width:390,height:844}:{width:1280,height:950}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(base+(journal?'journal/':'?camp_hub=1'));
  if(journal){await page.evaluate(async()=>{const state=await(await fetch('api/state')).json();if(!state.records.length)await fetch('api/records',{method:'POST',headers:{'Content-Type':'application/json','X-Camp-Request':'1'},body:JSON.stringify({name:'테스트 캠핑장',checkin:'2026-10-01',checkout:'2026-10-03',location:'강원도'})})});await page.reload()}
  await page.locator(journal?'#settings':'#header-settings').click();
  const tab=key=>page.locator(journal?({common:'#commonPrefs',mobile:'#mobilePrefs',pc:'#desktopPrefs'}[key]):'#display-tab-'+key);
  await assert.doesNotReject(()=>tab('common').waitFor({state:'visible'}));assert.equal(await tab('common').getAttribute('aria-selected'),'true');
  await tab('mobile').click();
  const font=page.locator(journal?'[data-field-style="name"][data-style-prop="font"]':'[data-mobile-column="name"][data-prop="font"]');await font.fill('19');
  await tab('pc').click();assert.equal(await tab('pc').getAttribute('aria-selected'),'true');
  if(journal){const value=page.locator('[data-field-style="name"][data-style-prop="font"]');await value.fill('22');const row=page.locator('.pref-row[data-key="name"]');await row.locator('[data-field-label]').fill('내 캠핑장');await row.locator('[data-empty-text]').fill('빈칸');await row.locator('[data-pref-width]').fill('180')}
  await tab('common').click();await tab('mobile').click();assert.equal(await font.inputValue(),'19');
  if(journal){await page.locator('.pref-row[data-key="layout"] [data-pref-visible]').uncheck();await page.locator('.pref-row[data-key="layout"] #layoutCaptionPref').check();await tab('pc').click();await tab('mobile').click();assert.equal(await page.locator('.pref-row[data-key="layout"] [data-pref-visible]').isChecked(),false);assert.equal(await page.locator('#layoutCaptionPref').isChecked(),true)}
  await page.screenshot({path:'/tmp/camp-settings-'+(journal?'journal':'ledger')+'-'+(mobile?'mobile':'pc')+'.png'});
  const response=page.waitForResponse(r=>r.url().endsWith('/api/settings')&&r.request().method()==='PUT');await page.locator(journal?'#savePrefs':'#settings-form button[type=submit]').click();const saved=await response;assert.equal(saved.status(),200,await saved.text());
  const settings=await page.evaluate(async()=> (await(await fetch('api/state')).json()).settings);assert.equal(journal?settings.display_mobile.field_styles.name.font:settings.display.mobile.columns.name.font,19);
  if(journal){assert.equal(settings.desktop.field_styles.name.font,22);assert.equal(settings.field_labels.name,'내 캠핑장');assert.equal(settings.display_mobile.layout_caption,true);assert.equal(settings.display_mobile.visible.layout,false);assert.equal(settings.desktop.widths.name,180)}
  if(journal){await page.setViewportSize({width:1280,height:950});await page.reload();await page.waitForFunction(()=>document.querySelector('#table td[data-field=name]')?.style.fontSize==='22px');assert.equal(await page.locator('#table td[data-field="name"]').first().evaluate(el=>getComputedStyle(el).fontSize),'22px');await page.setViewportSize({width:390,height:844});await page.reload();await page.waitForFunction(()=>document.querySelector('.camp-card-title')?.style.fontSize==='19px');assert.equal(await page.locator('.camp-card-title').first().evaluate(el=>getComputedStyle(el).fontSize),'19px')}
  assert.deepEqual(errors,[]);await page.close();console.log((journal?'Journal':'Ledger')+' '+(mobile?'mobile':'PC')+' settings: tabs, retained drafts, distinct device values and save passed');
 }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
