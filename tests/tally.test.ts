import test from 'node:test'
import assert from 'node:assert/strict'
import { parseTallyTotal, tallySubmission, tallyInitial } from '../src/tally.ts'

test('tally accepts integer counts and thousands separators without inventing decimal digits',()=>{
 assert.equal(parseTallyTotal('44,000'),44000)
 assert.equal(parseTallyTotal(' ０ '),null)
 assert.equal(parseTallyTotal('0'),0)
 for(const value of ['440.00','44,00','-1','NaN','', '1e4','1,000,00'])assert.equal(parseTallyTotal(value),null)
})
test('unsubmitted local tally survives closing; authoritative server identity wins',()=>{
 const empty={record_id:null,status:'not_started' as const,attempts:[]}
 assert.deepEqual(tallyInitial(empty,{record_id:'local',total:'100000',side:'right'},()=> 'new'),{id:'local',total:'100000',side:'right',locked:false})
 assert.equal(tallyInitial({...empty,record_id:'server'}, {record_id:'local',total:'100000'},()=> 'new').total,'')
})
test('completed or ten-attempt tally restores the recorded answer instead of an unconfirmable edit',()=>{
 const a={sequence:1,answer_total:44000}
 for(const p of [{record_id:'r',status:'complete' as const,attempts:[a]},{record_id:'r',status:'draft' as const,attempts:Array(10).fill(a)}]){
  const s=tallyInitial(p,{record_id:'r',total:'100000'},()=> 'new');assert.equal(s.locked,true);assert.equal(s.total,'44000')
 }
})
test('side comparison is required only on a sides task; answer contains no claimed correctness',()=>{
 assert.equal(tallySubmission('r','sides','103000',''),null)
 assert.deepEqual(tallySubmission('r','sides','103000','right'),{record_id:'r',answer_total:103000,answer_side:'right'})
 assert.deepEqual(tallySubmission('r','balance','44,000',''),{record_id:'r',answer_total:44000})
})
