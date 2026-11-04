import test from 'node:test'
import assert from 'node:assert/strict'
async function api(){try{return await import('../src/shipTasks.ts')}catch{assert.fail('Ship task state contract has not been implemented')}}
const context={routeId:'route',nodeId:'S2',actorId:'owner',authorName:'测试署名',activityMode:'individual' as const,material:'straw' as const,layout:'both' as const,currentSide:'right' as const,first:52000,second:0,hadArrows:true,reportText:'看清那排人影！',supportIds:[]}
test('M03 legal object move clears the passage while old layout remains unchanged',async()=>{
 const h=await api();const before=h.newTask('passage','record-1');const moved=h.moveObstacle(before,'right_rack','t1');assert.equal(before.obstacle,'passage');assert.equal(moved.obstacle,'right_rack');assert.equal(h.taskComplete(moved),false)
 const checked=h.verifyPassage(moved,'t2');assert.equal(h.taskComplete(checked),true);assert.equal(h.taskPayload(checked,'complete').blocked_after,false);assert.equal(h.taskPayload(before,'draft').blocked_after,true)
 assert.equal(h.verifyPassage(before,'t1').walked,false);assert.equal(h.moveObstacle(moved,'right_rack','t3').placements.length,1)
})
test('M07 first point survives automatic feedback and a later correction',async()=>{
 const h=await api();const first=h.pointSide(h.newTask('side','record-2'),'right',context,'t1');assert.equal(first.attempts[0].side,'right');assert.equal(first.feedback.length,1);assert.deepEqual(first.attempts[0].feedback_before,[])
 const second=h.pointSide(first,'left',context,'t2');const p=h.taskPayload(second,'complete');assert.equal(p.first_attempt.side,'right');assert.equal(p.attempts[1].side,'left');assert.deepEqual(p.attempts[1].feedback_before,[first.feedback[0].id]);assert.equal(first.attempts.length,1);assert.equal('score' in p,false)
})
test('M07 help before first response is preserved and unprepared side never becomes a prop',async()=>{
 const h=await api();const helped=h.addSideHelp(h.newTask('side','record-3'),'LOOK_EMPTY_SIDE','t1');const answered=h.pointSide(helped,'left',{...context,layout:'one'},'t2');assert.equal(answered.attempts[0].feedback_before.length,1);assert.match(h.sideDescription('left',{...context,layout:'one'}),/没有装置|空栏/);assert.equal(h.taskComplete(answered),true)
})
test('M09 playback facts and repeat counts are separate from original wording',async()=>{
 const h=await api();let s=h.newTask('listening','record-4');s=h.markHeard(s,'arrow_change','local_web_audio','t1');s=h.markHeard(s,'arrow_change','local_web_audio','t2');s=h.markHeard(s,'shore_report','text_equivalent','t3');assert.equal(h.taskComplete(s),false)
 s=h.setTaskResponse(s,'岸上正在查看。我担心退路，想先停鼓。');const p=h.taskPayload(s,'complete');assert.equal(p.replays.arrow_change,2);assert.equal(p.heard[2].mode,'text_equivalent');assert.equal(p.response,'岸上正在查看。我担心退路，想先停鼓。');assert.equal(h.taskComplete(s),true)
 assert.equal(h.taskComplete(h.setTaskResponse(s,'  ')),false)
})
test('M09 never-fired context does not invent an arrow volley or an inspection report',async()=>{
 const h=await api();const quiet={...context,hadArrows:false,reportText:''};assert.doesNotMatch(h.clipCaption('arrow_change',quiet),/箭声停|刚才.*射/);assert.doesNotMatch(h.clipCaption('shore_report',quiet),/已经查明|中了箭/);assert.ok(h.soundPlan('arrow_change',quiet).duration>0);assert.ok(h.soundPlan('arrow_change',quiet).segments.every(x=>x.kind!=='arrow'))
})
test('audio plans are finite and repeatable, with a real quiet interval after arrows',async()=>{
 const h=await api();const p=h.soundPlan('arrow_change',context);assert.deepEqual(p,h.soundPlan('arrow_change',context));assert.ok(p.duration<=4);assert.ok(p.segments.some(x=>x.kind==='arrow'));assert.ok(Math.max(...p.segments.map(x=>x.at+x.duration))<p.duration-.4)
})
test('server initial task payload restores immutable first attempt ahead of local defaults',async()=>{
 const h=await api();assert.equal(typeof h.restoreTask,'function','server task restoration is required')
 let original=h.pointSide(h.newTask('side','server-record'),'right',context,'t1');original=h.pointSide(original,'left',context,'t2')
 const resumed=h.restoreTask('side','client-record',h.taskPayload(original,'draft'));assert.equal(resumed.id,'server-record');assert.equal(resumed.attempts[0].side,'right');assert.equal(resumed.attempts.length,2)
 const added=h.pointSide(resumed,'left',context,'t3');assert.ok(added.attempts[2].sequence>resumed.attempts[1].sequence);assert.equal(added.attempts[0].side,'right')
})
test('a newer unsent sentence survives a compatible server draft refresh',async()=>{
 const h=await api();assert.equal(typeof h.mergeTaskDraft,'function','draft/server reconciliation is required')
 const remote=h.markHeard(h.newTask('listening','r-sync'),'arrow_change','local_web_audio','t1');const local=h.setTaskResponse(h.markHeard(remote,'shore_report','text_equivalent','t2'),'这句刚输入，还没同步。');const result=h.mergeTaskDraft('listening','r-sync',h.taskPayload(remote,'draft'),local)
 assert.equal(result.state.response,'这句刚输入，还没同步。');assert.equal(result.state.heard.length,2);assert.equal(result.conflictText,'')
})
test('completed or divergent server records stay authoritative and retain conflicting local text separately',async()=>{
 const h=await api();const remote=h.setTaskResponse(h.markHeard(h.markHeard(h.newTask('listening','server'),'arrow_change','text_equivalent','t1'),'shore_report','text_equivalent','t2'),'服务器已确认的话。');const local=h.setTaskResponse({...remote},'本机还有一句未存的话。')
 const done=h.mergeTaskDraft('listening','server',h.taskPayload(remote,'complete'),local);assert.equal(done.state.response,remote.response);assert.equal(done.conflictText,local.response)
 const divergent=h.setTaskResponse(h.markHeard(h.newTask('listening','server'),'shore_report','local_web_audio','t9'),'另一端写的话。');const conflict=h.mergeTaskDraft('listening','server',h.taskPayload(divergent,'draft'),local);assert.equal(conflict.state.response,divergent.response);assert.deepEqual(conflict.state.heard,divergent.heard);assert.equal(conflict.conflictText,local.response)
})
