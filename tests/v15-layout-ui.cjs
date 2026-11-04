// Targeted real-UI regression. API calls establish fleet_order preconditions only.
// Run against the isolated built app: node tests/v15-layout-ui.cjs
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {randomUUID}=require('node:crypto');
const base='http://127.0.0.1:8772';
const phase=process.env.QA_PHASE||'green';
const output=path.resolve(__dirname,'../docs/v15/qa/layout-fix-'+phase+'.json');

(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const context=await browser.newContext({viewport:{width:1440,height:900}});
 const page=await context.newPage();
 const report={scope:'API-created fleet_order preconditions, then targeted real UI; not a full route',checks:[],errors:[]};
 page.on('pageerror',e=>report.errors.push(e.message));
 try{
  const login=await context.request.post(base+'/api/auth/login',{data:{user_id:'S001',password:'DemoStudent123!'}});
  assert.equal(login.ok(),true,'demo login');
  const auth=await login.json(),headers={Authorization:'Bearer '+auth.token};
  const witness=require('../docs/v15/witnesses.json').witnesses[0];
  let response=await context.request.post(base+'/api/v1/runs',{headers,data:{role:witness.role,scenario:witness.scenario,design_version:'V1.5',members:['测试同伴']}});
  assert.equal(response.ok(),true,'create isolated QA run');
  let run=await response.json();
  for(const step of witness.steps){
   if(run.scene.node==='fleet_order')break;
   assert.equal(run.scene.node,step.node,'witness precondition node');
   response=await context.request.post(base+'/api/v1/runs/'+run.id+'/actions',{headers,data:{request_id:randomUUID(),revision:run.revision,action:step.action,payload:step.payload}});
   assert.equal(response.ok(),true,'witness precondition action');run=await response.json();
  }
  assert.equal(run.scene.node,'fleet_order');report.run=run.id;
  const saved=who=>page.evaluate(({id,who})=>JSON.parse(localStorage.getItem(`v12:operation:${id}:fleet_order:${who}`)||'null'),{id:run.id,who});
  const dialog=page.locator('.v12-activity'),actor=page.getByLabel('此刻执掌'),invite=page.locator('.v12-action-invite');
  const finish=page.getByRole('button',{name:'两船已应，查看江面 →',exact:true});
  const close=page.getByRole('button',{name:'返回当前一幕 ×',exact:true});
  const front=page.getByRole('button',{name:'向前船传令',exact:true}),rear=page.getByRole('button',{name:'向后船传令',exact:true});
  const lamp=page.getByRole('button',{name:'拖灯向船传令，回车向下一船传令',exact:true});
  const check=name=>{report.checks.push(name);console.log('PASS '+name)};
  async function dialogue(){for(let i=0;i<12;i++){const next=page.locator('.v1-dialogue .continue');if(!await next.count())break;await next.click()}await invite.waitFor()}
  async function open(){await invite.click();await dialog.waitFor();assert.equal(await close.evaluate(el=>el===document.activeElement),true,'opening focuses the dialog close button');assert.equal(await dialog.getAttribute('aria-modal'),'true')}
  async function command(index,pulses){await page.locator('.command-rail>button').nth(index).click();for(const pulse of pulses)await page.locator('.signal-instruments>button').nth(pulse==='short'?0:1).click()}
  async function acknowledged(ship){await page.locator('.signal-boat').filter({hasText:ship}).filter({hasText:'已收到'}).waitFor()}
  async function storedRelays(who,count){await page.waitForFunction(({id,who,count})=>JSON.parse(localStorage.getItem(`v12:operation:${id}:fleet_order:${who}`)||'null')?.drafts?.nav_signal?.relays.length===count,{id:run.id,who,count})}
  async function assertPartial(who,code,count){const op=await saved(who);assert.equal(op.done,false);assert.deepEqual(op.drafts.nav_signal.code,code);assert.equal(op.drafts.nav_signal.relays.length,count);assert.equal(op.authors.nav_signal,undefined)}
  async function restore(){await page.reload();await page.getByRole('button',{name:'接续未尽的一夜',exact:true}).click();await page.locator('.v1-heading h1').waitFor();await dialogue()}
  await page.goto(base);
  await page.evaluate(({token,id})=>{localStorage.setItem('v1:auth',token);localStorage.setItem('v1:run:S001',id)},{token:auth.token,id:run.id});
  await restore();
  await page.getByRole('button',{name:'人物对白 开',exact:true}).click();
  await page.getByRole('button',{name:'背景音乐 开',exact:true}).click();
  await open();await command(0,['short','short']);await front.click();await acknowledged('前船');


 const layout=[];
 for(const [width,height] of [[1440,900],[1252,724],[1024,600]]){
  await page.setViewportSize({width,height});await page.waitForTimeout(350);
  const measured=await page.evaluate(()=>{
   const rect=e=>{const b=e.getBoundingClientRect();return {x:b.x,y:b.y,right:b.right,bottom:b.bottom,width:b.width,height:b.height}};
   const boxes=Object.fromEntries(Object.entries({rail:'.command-rail',footer:'.nav-signal footer',header:'.nav-signal header',close:'.activity-close',lead:'.lead-seat',lamp:'.hooded-lamp'}).map(([name,selector])=>[name,rect(document.querySelector(selector))]));
   const controls=[...document.querySelectorAll('.command-rail>button,.signal-boat,.hooded-lamp,.signal-channel>button,.signal-instruments>button,.send-finish,.activity-close')].map(el=>{
    const box=rect(el),hits=[];
    for(const xf of [.2,.5,.8])for(const yf of [.2,.5,.8]){const x=box.x+box.width*xf,y=box.y+box.height*yf,top=document.elementFromPoint(x,y);hits.push({x,y,hit:!!top&&el.contains(top),top:top?.tagName+'.'+top?.className})}
    return {name:el.getAttribute('aria-label')||el.textContent.trim(),box,disabled:el.matches(':disabled'),hits,fontSize:getComputedStyle(el).fontSize};
   });
   return {boxes,controls};
  });
  const boxes=measured.boxes;
  layout.push({width,height,...measured,railCovered:boxes.rail.bottom>boxes.footer.y,leadCovered:boxes.lead.bottom>boxes.footer.y,headerOverlapsRail:boxes.header.bottom>boxes.rail.y});
  await page.screenshot({path:path.resolve(__dirname,'../docs/v15/qa/layout-fix-'+phase+'-'+width+'.png')});
 }
 report.layout=layout;
 fs.writeFileSync(output,JSON.stringify(report,null,2));
 for(const item of layout){
  assert.equal(item.railCovered,false,`${item.width}x${item.height}: command rail must clear footer`);
  assert.equal(item.leadCovered,false,`${item.width}x${item.height}: lead lamp and hint must clear footer`);
  assert.equal(item.headerOverlapsRail,false,`${item.width}x${item.height}: header must clear command rail`);
  for(const control of item.controls){assert.ok(control.box.x>=0&&control.box.y>=0&&control.box.right<=item.width&&control.box.bottom<=item.height,`${item.width}: ${control.name} must stay in viewport`);assert.ok(control.hits.every(h=>h.hit),`${item.width}: ${control.name} must be hittable across its rectangle`)}
 }
 check('all three viewports: header, command rail and lead lamp clear footer; every control rectangle stays visible and hittable');
 for(const [width,height] of [[1252,724],[1024,600]]){
  await page.setViewportSize({width,height});
  await command(2,['long','long']);
  assert.equal(await page.locator('.command-rail>button').nth(2).getAttribute('aria-pressed'),'true');
  await lamp.focus();await page.keyboard.press('Enter');await acknowledged('前船');
  const from=await lamp.boundingBox(),to=await rear.boundingBox();assert.ok(from&&to);
  await page.mouse.move(from.x+from.width/2,from.y+from.height/2);await page.mouse.down();await page.mouse.move(to.x+to.width/2,to.y+to.height/2,{steps:14});await page.mouse.up();
  await acknowledged('后船');assert.equal(await finish.isEnabled(),true);await finish.click();
  const proof=await saved(0);assert.equal(proof.done,true);assert.equal(proof.drafts.nav_signal.command,'recall');assert.deepEqual(proof.drafts.nav_signal.code,['long','long']);assert.equal(proof.drafts.nav_signal.relays.length,2);
  check(`${width}x${height}: real recall click, long-long code, Enter front send, lamp drag rear send and finish`);
  await open();
 }
 report.layout=layout;await close.click();await page.waitForTimeout(1300);const before=await page.locator('.scene-backdrop .frame.current').evaluate(e=>getComputedStyle(e).transform);await page.waitForTimeout(1200);const after=await page.locator('.scene-backdrop .frame.current').evaluate(e=>getComputedStyle(e).transform);report.cameraMoves=before!==after;report.checks.push('background transform changes over time');
 await page.emulateMedia({reducedMotion:'reduce'});await page.waitForTimeout(200);report.reducedAnimation=await page.locator('.scene-backdrop .frame.current').evaluate(e=>getComputedStyle(e).animationName);
 assert.equal(report.cameraMoves,true);assert.equal(report.reducedAnimation,'none');assert.deepEqual(report.errors,[]);report.complete=true;
 fs.writeFileSync(output,JSON.stringify(report,null,2));console.log(JSON.stringify({checks:report.checks,errors:report.errors,complete:report.complete}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)})
