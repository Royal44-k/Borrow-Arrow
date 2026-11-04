import test from 'node:test'
import assert from 'node:assert/strict'
import { isAnswered, criteriaFor, reviewComplete, canPublishReview, isWriting, type ExamItem } from '../src/assessment.ts'

const item=(id:string,type:ExamItem['type'],points=6):ExamItem=>({id,type,points,prompt:'本题',goal_id:'G3'})
test('fill, essay and reflection require an actual bounded answer',()=>{
 for(const kind of ['fill','essay','reflection'] as const){
  assert.equal(isAnswered(item('x',kind),'  '),false)
  assert.equal(isAnswered(item('x',kind),false),false)
  assert.equal(isAnswered(item('x',kind),'我保留了另一个合理判断。'),true)
 }
 assert.equal(isAnswered(item('x','fill'),'字'.repeat(201)),false)
 assert.equal(isWriting(item('x','fill')),false)
 assert.equal(isWriting(item('x','reflection')),true)
})
test('new and saved legacy papers retain their own rubric sizes and maxima',()=>{
 const old=item('q10','short',15)
 assert.deepEqual(criteriaFor(old).map(c=>c.max_points),[5,5,5])
 const q={...item('q21','essay',14),rubric_criteria:[{id:'a',title:'观点',max_points:4,description:'明确'},{id:'b',title:'讨论',max_points:6,description:'具体'},{id:'c',title:'结构',max_points:4,description:'连贯'}]}
 assert.equal(reviewComplete([q],{q21:[4,6,4]}),true)
 assert.equal(reviewComplete([q],{q21:[5,5,4]}),false)
 assert.equal(reviewComplete([q],{q21:[4,null,4]}),false)
 assert.equal(reviewComplete([q],{q21:[4,6]}),false)
})
test('publication compares all actual writing items, not hardcoded old q10 q11',()=>{
 const items=[item('q17','short'),item('q22','reflection',10)]
 const saved={status:'reviewed',item_scores:{q1:3,q17:5,q22:9},review_comment:'已逐项核读'}
 assert.equal(canPublishReview(saved,{q17:5,q22:9},'已逐项核读',items),true)
 assert.equal(canPublishReview(saved,{q17:5},'已逐项核读',items),false)
 assert.equal(canPublishReview(saved,{q17:5,q22:10},'已逐项核读',items),false)
 assert.equal(canPublishReview(saved,{q17:5,q22:9,q10:2},'已逐项核读',items),false)
})
