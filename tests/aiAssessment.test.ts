import test from 'node:test'
import assert from 'node:assert/strict'
import {canResolveGrade,modelSucceeded,runLabel,type AIRun} from '../src/aiAssessment.ts'
const run=(status:string,mode='live'):AIRun=>({id:'a',kind:'grade',status,mode,model:'m',error_code:null,created_at:'now',result:{conflict_ids:['q2'],objective_results:[{item_id:'q2',model_score:3,rule_score:0,max_points:3,status:'disagreement',reason:'different'}]}})
test('new paper needs explicit fallback or all real model disagreements resolved',()=>{
 assert.equal(canResolveGrade('caocuan-exam-s1.2',null,false,{}),false)
 assert.equal(canResolveGrade('caocuan-exam-s1.2',null,true,{}),true)
 assert.equal(canResolveGrade('caocuan-exam-s1.1',null,false,{}),true)
 for(const n of [null,-1,4,1.5])assert.equal(canResolveGrade('caocuan-exam-s1.2',run('conflict'),true,{q2:n}),false)
 assert.equal(canResolveGrade('caocuan-exam-s1.2',run('conflict'),false,{q2:2}),true)
})
test('fallback and invalid responses cannot appear as successful model grading',()=>{
 assert.equal(modelSucceeded(run('completed','rule_fallback')),false)
 assert.equal(modelSucceeded(run('invalid_response')),false)
 assert.match(runLabel(run('pending_model','rule_fallback')),/未调用/)
})
