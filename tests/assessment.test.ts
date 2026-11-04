import test from 'node:test'
import assert from 'node:assert/strict'
import { isAnswered, moveInOrder, visibleScore, submissionIdentity, canPublishReview, type ExamItem } from '../src/assessment.ts'

const base = { id:'q', prompt:'问题', points:10, goal_id:'g' }
test('single and multi reject unknown choices and duplicated answers', () => {
  const q:ExamItem={...base,type:'single',options:[{id:'a',text:'A'},{id:'b',text:'B'}]}
  assert.equal(isAnswered(q,'a'),true)
  assert.equal(isAnswered(q,'unknown'),false)
  assert.equal(isAnswered({...q,type:'multi'},['a','a']),false)
  assert.equal(isAnswered({...q,type:'multi'},['a','b']),true)
})
test('order requires every id exactly once and changes do not mutate old answers', () => {
  const q:ExamItem={...base,type:'order',options:[{id:'a',text:'A'},{id:'b',text:'B'},{id:'c',text:'C'}]}
  assert.equal(isAnswered(q,['a','b']),false)
  assert.equal(isAnswered(q,['a','b','c']),true)
  const old=['a','b','c']; assert.deepEqual(moveInOrder(old,1,-1),['b','a','c']); assert.deepEqual(old,['a','b','c'])
  assert.deepEqual(moveInOrder(old,0,-1),old)
})
test('matching requires all left entries and known right ids', () => {
  const q:ExamItem={...base,type:'match',left:[{id:'l1',text:'甲'},{id:'l2',text:'乙'}],right:[{id:'r1',text:'A'},{id:'r2',text:'B'}]}
  assert.equal(isAnswered(q,{l1:'r1'}),false)
  assert.equal(isAnswered(q,{l1:'r1',l2:'r2'}),true)
  assert.equal(isAnswered(q,{l1:'bad',l2:'r2'}),false)
  assert.equal(isAnswered(q,{l1:'r1',l2:'r1'}),false)
})
test('student scores never expose an unpublished total, including accidental backend total', () => {
  assert.equal(visibleScore({status:'pending_review',total:70}),'待批阅')
  assert.equal(visibleScore({status:'reviewed',total:88}),'待发布')
  assert.equal(visibleScore({status:'published',total:0}),'0')
  assert.equal(visibleScore({status:'published',total:88}),'88')
  assert.equal(visibleScore({status:'published',total:null}),'待发布')
})
test('same payload retry keeps its id while edited work gets a new id', () => {
  const a=submissionIdentity({q1:'a'},null,()=> 'first')
  const b=submissionIdentity({q1:'a'},a,()=> 'second')
  const c=submissionIdentity({q1:'b'},b,()=> 'third')
  assert.equal(a.requestId,b.requestId);assert.equal(c.requestId,'third')
})
test('empty and whitespace-only short responses remain unanswered', () => {
  const q:ExamItem={...base,type:'short'}
  assert.equal(isAnswered(q,'  '),false)
  assert.equal(isAnswered(q,'我让鲁肃先向船夫说清楚当前安排。'),true)
})
test('publishing requires saved marks and saved review comment', () => {
  const saved={status:'reviewed',item_scores:{q10:12,q11:10},review_comment:'具体说明'}
  assert.equal(canPublishReview(saved,{q10:12,q11:10},'具体说明'),true)
  assert.equal(canPublishReview(saved,{q10:14,q11:10},'具体说明'),false)
  assert.equal(canPublishReview(saved,{q10:12,q11:10},'新说明'),false)
  assert.equal(canPublishReview({...saved,status:'pending_review'},{q10:12,q11:10},'具体说明'),false)
  assert.equal(canPublishReview({...saved,status:'published'},{q10:12,q11:10},'具体说明'),false)
})
test('common case needs all four parts and rejects unknown or boolean values', () => {
  const q:ExamItem={...base,type:'scenario',parts:[{id:'spent',type:'number',prompt:'已支出',points:5},{id:'remaining',type:'number',prompt:'剩余',points:5},{id:'turn',type:'single',prompt:'转舷',points:5,options:[{id:'B',text:'不能保证'}]},{id:'report',type:'single',prompt:'停射',points:5,options:[{id:'A',text:'声音与观察'}]}]}
  assert.equal(isAnswered(q,{spent:'0',remaining:'44000',turn:'B',report:'A'}),true)
  assert.equal(isAnswered(q,{spent:'0',remaining:'44000',turn:'B'}),false)
  assert.equal(isAnswered(q,{spent:'0',remaining:'NaN',turn:'B',report:'A'}),false)
  assert.equal(isAnswered(q,{spent:false,remaining:'44000',turn:'B',report:'A'}),false)
})
test('publishing cannot omit an expression score',()=>{
  assert.equal(canPublishReview({status:'reviewed',item_scores:{q10:12,q11:13},review_comment:'已核'},{q10:12},'已核'),false)
})
