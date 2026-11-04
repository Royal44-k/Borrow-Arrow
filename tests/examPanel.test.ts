import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { runInNewContext } from 'node:vm'
import { webcrypto } from 'node:crypto'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'
import ts from 'typescript'
import * as Vue from 'vue'

type Element = { type:string; props:Record<string,any>; children:Element[]; parent?:Element; text?:string }
function element(type:string):Element { return {type,props:{},children:[]} }
function descendants(root:Element):Element[] { return [root,...root.children.flatMap(descendants)] }
function textOf(node:Element):string { return (node.text??'')+node.children.map(textOf).join('') }
const options=[{id:'a',text:'选项甲'},{id:'b',text:'选项乙'}]
const exam={id:'test-paper',title:'课题测试',max_score:100,instructions:'完成全部题目。',items:[
  {id:'q1',type:'single',prompt:'选择',points:10,goal_id:'g1',options},
  {id:'q2',type:'multi',prompt:'多选',points:10,goal_id:'g1',options},
  {id:'q3',type:'order',prompt:'排序',points:10,goal_id:'g1',options},
  {id:'q4',type:'match',prompt:'配对',points:10,goal_id:'g1',left:options,right:options},
  {id:'q5',type:'short',prompt:'表达',points:60,goal_id:'g1'},
  {id:'q6',type:'fill',prompt:'填空内容',points:3,goal_id:'g1'},
  {id:'q7',type:'essay',prompt:'展开论述',points:14,goal_id:'g1'},
  {id:'q8',type:'reflection',prompt:'写下个人感悟',points:10,goal_id:'g1'},
  {id:'q10',type:'multi',prompt:'新的第十题',points:4,goal_id:'g1',options},
]}
const initialAnswers={q1:'a',q2:['a'],q3:['a','b'],q4:{a:'a',b:'b'},q5:'原先写下的回答',q6:'三日',q7:'我认为应重新判断当前情境。',q8:'我曾经选择继续等，后来改变了安排。',q10:['a']}
async function flush(){await Promise.resolve();await Vue.nextTick();await Promise.resolve();await Vue.nextTick()}

async function mountPanel(active=4){
  const storage=new Map<string,string>()
  const key='caocuan:exam:student-1:test-paper'
  storage.set(key,JSON.stringify({answers:initialAnswers,active,identity:null}))
  const localStorage={getItem:(k:string)=>storage.get(k)??null,setItem:(k:string,v:string)=>storage.set(k,v),removeItem:(k:string)=>storage.delete(k)}
  const assessmentSource=readFileSync(new URL('../src/assessment.ts',import.meta.url),'utf8')
  const evaluate=(source:string,requires:Record<string,unknown>)=>{
    const exports:Record<string,any>={}
    const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
    runInNewContext(code,{exports,require:(id:string)=>{if(!(id in requires))throw new Error(`Unexpected import: ${id}`);return requires[id]},localStorage,crypto:webcrypto,console},{filename:'ExamPanel.test-harness.cjs'})
    return exports
  }
  const assessment=evaluate(assessmentSource,{})
  const {descriptor}=parse(readFileSync(new URL('../src/components/ExamPanel.vue',import.meta.url),'utf8'))
  const script=compileScript(descriptor,{id:'exam-behavior-test'})
  const template=compileTemplate({source:descriptor.template!.content,filename:'ExamPanel.vue',id:'exam-behavior-test',compilerOptions:{bindingMetadata:script.bindings}})
  assert.equal(template.errors.length,0)
  const component=evaluate(script.content,{vue:Vue,'../assessment':assessment}).default
  component.render=evaluate(template.code,{vue:Vue}).render
  const renderer=Vue.createRenderer<Element,Element>({
    createElement:element,createText:t=>({...element('#text'),text:t}),createComment:t=>({...element('#comment'),text:t}),
    setText:(n,t)=>{n.text=t},setElementText:(n,t)=>{n.children=[];n.text=t},
    patchProp:(n,k,_old,v)=>{n.props[k]=v},parentNode:n=>n.parent??null,
    nextSibling:n=>n.parent?.children[n.parent.children.indexOf(n)+1]??null,
    insert:(n,p,anchor)=>{if(n.parent){const old=n.parent.children.indexOf(n);if(old>=0)n.parent.children.splice(old,1)};n.parent=p;const i=anchor?p.children.indexOf(anchor):-1;p.children.splice(i<0?p.children.length:i,0,n)},
    remove:n=>{if(n.parent){const i=n.parent.children.indexOf(n);if(i>=0)n.parent.children.splice(i,1)}},
  })
  let resolvePost!:(value:unknown)=>void,rejectPost!:(error:Error)=>void
  const pending=new Promise((resolve,reject)=>{resolvePost=resolve;rejectPost=reject})
  const posts:any[]=[];let closed=0
  const app=renderer.createApp(component,{userId:'student-1',onClose:()=>closed++,request:async(path:string,method='GET',body?:unknown)=>{
    if(method==='POST'){posts.push(body);return pending}
    return path==='/api/exam'?exam:{attempts:[]}
  }})
  const root=element('root');app.mount(root);await flush()
  // The real SFC setup bindings and compiled render run against Vue's renderer.
  const state=(app as any)._instance.setupState
  return {app,root,state,storage,key,posts,resolvePost,rejectPost,get closed(){return closed}}
}

test('pending submission freezes answers, navigation, return and the request payload',async()=>{
  const h=await mountPanel()
  try{
    const pending=h.state.submit();await flush()
    assert.equal(h.posts.length,1)
    assert.equal(h.posts[0].exam_id,'test-paper')
    const snapshot=JSON.stringify(h.posts[0].answers)
    const textarea=descendants(h.root).find(n=>n.type==='textarea')!
    // Deliberately dispatch a stale input event too; disabled DOM alone is insufficient.
    textarea.props.onInput({target:{value:'提交期间晚改的回答'}})
    h.state.toggle('q2','b');h.state.setMatch('q4','a','b')
    h.state.setAnswer('q3',['b','a'])
    for(const control of descendants(h.root).filter(n=>n.type==='button')){
      assert.equal(control.props.disabled,true,`${textOf(control)} remains enabled`)
      if(/返回课件|上一题/.test(textOf(control)))control.props.onClick?.({})
    }
    assert.equal(textarea.props.disabled,true)
    assert.equal(h.state.active,4)
    assert.equal(h.closed,0)
    assert.equal(JSON.stringify(h.state.answers),JSON.stringify(initialAnswers))
    assert.equal(JSON.stringify(h.posts[0].answers),snapshot)
    // A request owns a detached value, including nested arrays and match maps.
    h.state.answers.q2.push('external-mutation')
    h.state.answers.q4.a='external-mutation'
    assert.equal(JSON.stringify(h.posts[0].answers),snapshot)
    h.resolvePost({id:'attempt-1',status:'pending_review',total:null,created_at:new Date().toISOString(),published_at:null})
    await pending;await flush()
    assert.equal(h.state.busy,false)
    assert.equal(h.storage.has(h.key),false)
  }finally{h.app.unmount()}
})

test('new question ten does not inherit legacy scenario image and new types render their own controls',async()=>{
 for(const [active,label,tag] of [[5,'填空','input'],[6,'论述','textarea'],[7,'个人感悟','textarea'],[8,'多项选择','input']] as const){
  const h=await mountPanel(active)
  try{
   assert.ok(textOf(h.root).includes(label))
   assert.ok(descendants(h.root).some(n=>n.type===tag))
   if(active===8)assert.equal(descendants(h.root).some(n=>n.type==='svg'),false)
  }finally{h.app.unmount()}
 }
})

test('all question types disable their native controls, and failed submission unlocks the preserved draft',async()=>{
  for(let active=0;active<exam.items.length;active++){
    const h=await mountPanel(active)
    try{
      const pending=h.state.submit();await flush()
      const controls=descendants(h.root).filter(n=>['input','select','textarea','button','fieldset'].includes(n.type))
      for(const control of controls)assert.equal(control.props.disabled,true,`${exam.items[active]!.type}: ${control.type} is not disabled`)
      h.rejectPost(new Error('连接中断，请重试'))
      await pending;await flush()
      assert.equal(h.state.busy,false)
      assert.equal(h.state.submitted,null)
      assert.equal(JSON.stringify(h.state.answers),JSON.stringify(initialAnswers))
      assert.equal(h.storage.has(h.key),true)
      const draft=JSON.parse(h.storage.get(h.key)!)
      assert.deepEqual(draft.answers,initialAnswers)
      const requestId=h.posts[0].request_id
      h.state.submit();await flush()
      assert.equal(h.posts[1].request_id,requestId,'unchanged failed request keeps idempotency identity')
    }finally{h.app.unmount()}
  }
})
