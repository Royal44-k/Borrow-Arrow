import { test } from 'node:test'
import assert from 'node:assert/strict'
import { verifyTally, restoreTallyDraft } from './tally.ts'
const full = { right: 50000, left: 50000, total: 100000 }
test('requires manual sample inspection and all three selections', () => {
 assert.equal(verifyTally({}, full).ok, false)
 assert.equal(verifyTally({sample_checked:false,...full}, full).ok, false)
 assert.equal(verifyTally({sample_checked:true,right:50000,left:50000}, full).ok, false)
})
test('accepts exact student proof including zero route', () => {
 for (const context of [full, {right:50000,left:0,total:50000}, {right:0,left:0,total:0}]) {
  assert.deepEqual(verifyTally({sample_checked:true,...context}, context), {ok:true,proof:{sample_checked:true,...context}})
 }
})
test('rejects coercion, malformed counts, and wrong fleet reports', () => {
 for (const bad of ['50000', null, true, -1, 1.5, NaN, Infinity, 100001]) {
  assert.equal(verifyTally({sample_checked:true,...full,right:bad},full).ok,false)
 }
 assert.equal(verifyTally({sample_checked:true,right:0,left:50000,total:50000},full).ok,false)
 assert.equal(verifyTally({sample_checked:true,...full,total:50000},full).ok,false)
 assert.equal(verifyTally({sample_checked:true,...full}, {...full,total:50000}).ok,false)
})
test('restores explicit zero but never supplies an unselected answer', () => {
 assert.deepEqual(restoreTallyDraft(),{sample_checked:false,samples_taken:0})
 assert.deepEqual(restoreTallyDraft({sample_checked:true,right:0,left:'0',total:100000}),{sample_checked:true,samples_taken:3,right:0,total:100000})
})

 test('partial extraction survives reopen without filling any counts',()=>{
  const d=restoreTallyDraft({sample_checked:false,samples_taken:2});
  assert.equal(d.samples_taken,2);assert.equal(d.sample_checked,false);assert.equal(d.total,undefined);
  assert.equal(restoreTallyDraft({samples_taken:-1}).samples_taken,0);
  assert.equal(restoreTallyDraft({samples_taken:'2'}).samples_taken,0);
 });
