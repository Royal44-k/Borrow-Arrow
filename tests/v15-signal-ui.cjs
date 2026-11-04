// Targeted real-UI regression. API calls establish fleet_order preconditions only.
// Run against the isolated built app: node tests/v15-signal-ui.cjs
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {randomUUID}=require('node:crypto');
const base='http://127.0.0.1:8772';
const output=path.resolve(__dirname,'../docs/v15/qa/task2-fix-'+(process.env.QA_PHASE||'green')+'.json');

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

  // The original exploit escapes from the front-ship button to the actor select.
  await front.focus();
  for(let i=0;i<24;i++){
   await page.keyboard.press('Tab');
   assert.equal(await dialog.evaluate(el=>el.contains(document.activeElement)),true,`Tab ${i+1} must stay inside the activity dialog`);
  }
  for(let i=0;i<24;i++){
   await page.keyboard.press('Shift+Tab');
   assert.equal(await dialog.evaluate(el=>el.contains(document.activeElement)),true,`Shift+Tab ${i+1} must stay inside the activity dialog`);
  }
  assert.equal(await actor.isDisabled(),true,'background actor select must be disabled');
  assert.equal(await actor.inputValue(),'0');check('Tab and Shift+Tab stay in modal; background actor cannot change');
  await assertPartial(0,['short','short'],1);
  await close.click();assert.equal(await actor.isEnabled(),true);assert.equal(await invite.evaluate(el=>el===document.activeElement),true);
  check('closing restores focus and enables actor switching');

  await actor.selectOption('1');await open();
  assert.equal(await page.locator('.code-strip').innerText(),'·　·');
  assert.equal(await page.locator('.signal-boat.answered').count(),0);assert.equal(await finish.isDisabled(),true);
  await rear.click();assert.equal(await page.locator('.signal-boat.answering').count(),0);assert.equal(await saved(1),null);
  await command(1,['short','long']);await front.click();await acknowledged('前船');await page.keyboard.press('Escape');assert.equal(await dialog.count(),0);
  await assertPartial(1,['short','long'],1);await assertPartial(0,['short','short'],1);
  check('A and B keep independent unfinished command codes and front acknowledgements');

  await actor.selectOption('0');await open();
  assert.match(await page.locator('.code-strip').innerText(),/●\s+●/);assert.equal(await page.locator('.signal-boat.answered').count(),1);assert.equal(await finish.isDisabled(),true);
  await restore();await open();
  assert.equal(await page.locator('.signal-boat.answered').count(),1);assert.equal(await finish.isDisabled(),true);await assertPartial(0,['short','short'],1);
  await close.click();await actor.selectOption('1');await open();
  assert.match(await page.locator('.code-strip').innerText(),/●\s+━━/);assert.equal(await page.locator('.signal-boat.answered').count(),1);
  check('close/reopen and browser refresh preserve each partial draft without completing rear ship');

  // Closing while rear acknowledgement is pending must cancel its old timer.
  await rear.click();await page.locator('.signal-boat.answering').waitFor();await close.click();
  await actor.selectOption('0');await open();await page.waitForTimeout(1800);
  await assertPartial(1,['short','long'],1);await assertPartial(0,['short','short'],1);
  assert.equal(await page.locator('.signal-boat.answered').count(),1);
  await close.click();await actor.selectOption('1');await open();assert.equal(await page.locator('.signal-boat.answered').count(),1);
  check('close during pending reply cancels timer and cannot credit either actor');

  await command(1,['long','short']);await front.click();await rear.click();
  assert.equal(await page.locator('.signal-boat.answering').count(),0);assert.equal(await page.locator('.signal-boat.answered').count(),0);assert.equal(await finish.isDisabled(),true);
  await assertPartial(1,['long','short'],0);check('wrong short/long code cannot send or complete');
  await command(1,['short','long']);await lamp.focus();await page.keyboard.press('Enter');await acknowledged('前船');
  const from=await lamp.boundingBox(),to=await rear.boundingBox();assert.ok(from&&to);
  await page.mouse.move(from.x+from.width/2,from.y+from.height/2);await page.mouse.down();await page.mouse.move(to.x+to.width/2,to.y+to.height/2,{steps:14});await page.mouse.up();
  await acknowledged('后船');assert.equal(await finish.isEnabled(),true);await finish.click();
  const b=await saved(1);assert.equal(b.done,true);assert.equal(b.authors.nav_signal,1);assert.deepEqual(b.drafts.nav_signal,{command:'spread',channel:'light',code:['short','long'],relays:[{ship:'前船',code:['short','long'],ack:true},{ship:'后船',code:['short','long'],ack:true}]});
  await assertPartial(0,['short','short'],1);check('Enter front send and real lamp drag rear send complete only B with B proof');

  await actor.selectOption('0');await open();assert.equal(await finish.isDisabled(),true);await lamp.focus();await page.keyboard.press('Enter');await acknowledged('后船');await finish.click();
  const a=await saved(0);assert.equal(a.done,true);assert.equal(a.authors.nav_signal,0);assert.equal(a.drafts.nav_signal.command,'advance');assert.deepEqual(await saved(1),b);
  check('A resumes its own draft and completes without overwriting B');
  await actor.selectOption('1');
  const posted=page.waitForRequest(r=>r.url().endsWith(`/api/v1/runs/${run.id}/actions`)&&r.method()==='POST');
  const accepted=page.waitForResponse(r=>r.url().endsWith(`/api/v1/runs/${run.id}/actions`)&&r.request().method()==='POST');
  await page.locator('[data-action="spread"]').click();
  const body=(await posted).postDataJSON();assert.equal(body.actor,1);assert.equal(body.payload.operation_authors.nav_signal,1);assert.deepEqual(body.payload.nav_signal,b.drafts.nav_signal);
  const next=await accepted;assert.equal(next.ok(),true);assert.equal((await next.json()).scene.node,'spread_channel');
  check('actual action request submits B actor, author and B-only proof');
  assert.deepEqual(report.errors,[]);report.complete=true;
 }catch(error){report.failure=error.stack;throw error}
 finally{fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(report,null,2));await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
