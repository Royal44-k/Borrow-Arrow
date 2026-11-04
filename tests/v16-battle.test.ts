import test from 'node:test'
import assert from 'node:assert/strict'
import {battleSchedule,arrowPose} from '../src/v16/battle.ts'
test('warning shots finish in the water; volleys build from sparse to dense',()=>{
 const warning=battleSchedule('warning'),first=battleSchedule('first'),second=battleSchedule('second')
 assert(warning.every(a=>a.water));assert(first.some(a=>!a.water));assert(second.length>first.length)
 assert(first.filter(a=>a.start>4&&a.start<8).length>first.filter(a=>a.start<3).length)
})
test('arrow travels continuously from distant bank to foreground and remains finite',()=>{
 for(const a of battleSchedule('second')){
  const p=arrowPose(a,0),end=arrowPose(a,1)
  assert(p.z<-60);assert(end.z>p.z);assert(Number.isFinite(end.y));if(!a.flyby){assert(end.z<3);assert(Math.abs(end.x)>1)}
  for(const t of [0,.25,.5,.75,1])assert(Object.values(arrowPose(a,t)).every(Number.isFinite))
 }
})
test('battle composition is deterministic and source arrays cannot cross-contaminate',()=>{
 const a=battleSchedule('first'),b=battleSchedule('first');assert.deepEqual(a,b);a.pop();assert.notEqual(a.length,b.length)
})
test('each volley lodges in the receiving rail; the second faces the other rail',()=>{
 assert(battleSchedule('first').filter(a=>!a.water&&!a.flyby).every(a=>a.ex<0))
 assert(battleSchedule('second').filter(a=>!a.water&&!a.flyby).every(a=>a.ex>0))
})
test('near-camera flybys pass the eye but never lodge in an unhit rail',()=>{const a=battleSchedule('second').filter(a=>a.flyby);assert(a.length>20&&a.length<150);assert(a.every(x=>x.ez>10&&!x.water))})
