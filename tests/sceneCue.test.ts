import test from 'node:test'
import assert from 'node:assert/strict'
import * as scene from '../src/sceneCue.ts'
test('未开弓不说箭停；新哨艇不能复用静默说明',()=>{
 const v={node_id:'S12',role:'L',visual:{}} as const
 assert.doesNotMatch(scene.sceneCue(v)!.line.text,/箭停|起疑|看穿/)
 const boat=scene.sceneCue({...v,visual:{scout_approaching:true}})!
 assert.equal(boat.id,'approaching-oars');assert.match(boat.line.text,/桨声/)
})
test('已停箭仍不替曹军断定意图；无雾不宣称雾散',()=>{
 assert.match(scene.sceneCue({node_id:'S15',role:'Z',visual:{}})!.line.text,/还是/)
 assert.doesNotMatch(scene.sceneCue({node_id:'S17',role:'Z',visual:{weather:'clear'}})!.line.text,/雾/)
 assert.equal(scene.sceneCue({node_id:'S15',role:'C',visual:{}}),null)
})
