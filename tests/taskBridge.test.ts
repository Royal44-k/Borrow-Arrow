import test from 'node:test'
import assert from 'node:assert/strict'
import {taskBeforeAction,taskIdentity} from '../src/taskBridge.ts'
test('leaving with partial arrows never forces the turn task',()=>{
 assert.equal(taskBeforeAction({node_id:'A0',role:'L'},{id:'A0.withdraw',label:'退'}),null)
 assert.equal(taskBeforeAction({node_id:'A0',role:'L'},{id:'A0.turn',label:'转',kind:'turn'}),'side')
})
test('task is tied to actual station and actor, not all successful routes',()=>{
 assert.equal(taskBeforeAction({node_id:'S2',role:'L'},{id:'S2.both',label:'系牢'}),'passage')
 assert.equal(taskBeforeAction({node_id:'S12',role:'Z'},{id:'S12.retreat',label:'退'}),null)
 assert.equal(taskBeforeAction({node_id:'C2',role:'C'},{id:'C2.stop',label:'停'}),null)
 assert.notEqual(taskIdentity('r','S12','a','listening'),taskIdentity('r','S12','b','listening'))
})
test('观察属于剧情，五个静默节点所有行动均不被听辨作文拦住',()=>{
 for(const node of ['S11','S12','S15','S16','S17'])for(const role of ['L','Z'] as const){
  for(const suffix of ['go','wait','hear','bluff','near'])assert.equal(taskBeforeAction({node_id:node,role},{id:node+'.'+suffix,label:suffix}),null)
 }
})
