import test from 'node:test'
import assert from 'node:assert/strict'
import {signalCode,verifySignal,restoreSignal} from '../src/v15/signal.ts'
test('each real command has distinct code and proof',()=>{
 for(const command of ['advance','spread','recall'] as const){
  const code=signalCode(command),p={command,channel:'light',code,relays:['前船','后船'].map(ship=>({ship,code,ack:true}))}
  assert.equal(verifySignal(p),true)
  assert.equal(verifySignal({...p,relays:p.relays.slice(0,1)}),false)
  assert.equal(verifySignal({...p,code:['long','short']}),false)
 }
})
test('reload preserves completed acknowledgements but cannot manufacture a send',()=>{
 const p={command:'advance',channel:'sound',code:['short','short'],relays:[{ship:'前船',code:['short','short'],ack:true}]}
 assert.equal(restoreSignal(p).relays.length,1)
 assert.equal(restoreSignal({...p,relays:[{ship:'前船',code:['long'],ack:true}]}).relays.length,0)
 assert.equal(restoreSignal(null).command,null)
 assert.equal(verifySignal({...p,relays:[...p.relays,...p.relays]}),false)
})
