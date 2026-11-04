import test from 'node:test'
import assert from 'node:assert/strict'
import * as film from '../src/cinematic.ts'
import { stageMode, publicStage, visibleActions, playableLines, operationAction, replayMemories, helpPrompts } from '../src/cinematic.ts'
test('完整发言不因句号成为两次开口，兼容旧拆句存档',()=>{
 assert.deepEqual(playableLines({speaker:'韩伯',lines:['前头就是曹营。','还往近处走吗？']} as any),[{speaker:'韩伯',text:'前头就是曹营。还往近处走吗？'}])
})
test('动作回应与开场去掉同一整句，保留人物之间的不同回应',()=>{
 const compose=(film as any).sceneLines
 assert.equal(typeof compose,'function','缺少有归属的对白合成器')
 const view={speaker:'韩伯',lines:['前头就是曹营。','还往近处走吗？'],transition:[{speaker:'鲁肃',text:'就在这里停吧。'},{speaker:'韩伯',text:'前头就是曹营。还往近处走吗？'}]} as any
 assert.deepEqual(compose(view),[{speaker:'鲁肃',text:'就在这里停吧。'},{speaker:'韩伯',text:'前头就是曹营。还往近处走吗？'}])
 assert.deepEqual(compose(view,false),[{speaker:'韩伯',text:'前头就是曹营。还往近处走吗？'}])
})
test('曹方不知道的装置和箭数不会补成船方实数',()=>{
 const p=publicStage({role:'C',visual:{weather:'fog',material:'unknown',layout:'unknown'}} as any)
 assert.equal(p.first,0);assert.equal(p.material,'none');assert.equal(p.layout,'none')
})
test('转镜头不执行命令，操舵确认才映射转舷',()=>{
 const v={node_id:'A0',actions:[{id:'A0.turn',label:'转舷'}]} as any
 assert.equal(operationAction(v,{kind:'helm-preview',side:'left'}),null)
 assert.equal(operationAction(v,{kind:'helm-confirm',side:'left'}),'A0.turn')
 assert.equal(operationAction(v,{kind:'helm-confirm',side:'right'}),null)
})
test('鼓面试敲不推进，完成拔箭才能送箭',()=>{
 const v={node_id:'S10',actions:[{id:'S10.drum'}]} as any
 assert.equal(operationAction(v,{kind:'drum',action:'sound'}),null)
 assert.equal(operationAction(v,{kind:'drum',action:'command'}),'S10.drum')
 const c={node_id:'COUNT1',actions:[{id:'COUNT1.done'}]} as any
 assert.equal(operationAction(c,{kind:'collect',complete:false}),null)
 assert.equal(operationAction(c,{kind:'collect',complete:true}),'COUNT1.done')
})
test('一场最多三项决定；末场不用制作占位文字',()=>{
 assert.equal(visibleActions({actions:[1,2,3,4]} as any).length,3)
 assert.deepEqual(playableLines({node_id:'X1',speaker:'末场',lines:['采用02中当前角色专属三镜头'],ending:{lines:[{speaker:'周瑜',text:'箭都送来了？'}]}} as any),[{speaker:'周瑜',text:'箭都送来了？'}])
 assert.equal(stageMode({node_id:'COUNT1'} as any),'river')
})
test('备船前不凭默认值摆满道具，箭束按现存而非曾取得数量显示',()=>{
 assert.equal(publicStage({node_id:'S0',visual:{material:'straw',layout:'both'}} as any).material,'none')
 assert.equal(publicStage({node_id:'S2',visual:{material:'armor',layout:'both'}} as any).layout,'none')
 const p=publicStage({node_id:'COUNT1',visual:{first:52000,second:51000,arrows:{right:44000,left:51000}}} as any)
 assert.equal(p.first,44000);assert.equal(p.second,51000)
})
test('返航有独立号令，不能把转舷预览当作返航',()=>{
 const v={node_id:'R0',actions:[{id:'R0.return'}]} as any
 assert.equal(operationAction(v,{kind:'helm-confirm',side:'right'}),null)
 assert.equal(operationAction(v,{kind:'return-confirm'}),'R0.return')
 assert.equal(stageMode(v),'river')
})
test('末场回看仍保留亲自提问的雾中节点，帮助问题对应眼前事物',()=>{
 const memories=[{id:'s1',node_id:'S8',can_fork:true},{id:'s2',node_id:'A0'},{id:'s3',node_id:'R0'},{id:'s4',node_id:'COUNT1'},{id:'s5',node_id:'X1'}]
 assert.equal(replayMemories(memories).some(s=>s.node_id==='S8'),true)
 assert.match(helpPrompts('A0','L')[0].label,/哪边/)
 assert.match(helpPrompts('C2','C')[0].label,/人影/)
})
