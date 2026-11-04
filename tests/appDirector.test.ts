// Component behavior tests with a custom Vue renderer. These are NOT GUI visits.
import assert from 'node:assert/strict'
import test from 'node:test'
import {readFileSync} from 'node:fs'
import {runInNewContext} from 'node:vm'
import {webcrypto} from 'node:crypto'
import {parse,compileScript} from 'vue/compiler-sfc'
import ts from 'typescript'
import * as Vue from 'vue'
import * as cinematic from '../src/cinematic.ts'
import * as bridge from '../src/taskBridge.ts'
import * as tasks from '../src/shipTasks.ts'
import * as cues from '../src/sceneCue.ts'
import {Narration} from '../src/narration.ts'
const v=(node='S0',route='route')=>({version:'S1.1',node_id:node,route_id:route,session_id:'session',revision:1,role:'L',speaker:'韩伯',lines:['前头就是曹营。','还往近处走吗？'],transition:[],visual:{first:0,second:0,weather:'fog'},stage:{world:'ship'},status:'active',ending:null,members:[{id:'a',name:'测试学生'}],controller_id:'a',snapshots:[],old_utterances:[],actions:[{id:node+'.go',label:'回去'}]})
async function harness(catalogPending=false){
 const calls:any[]=[],said:string[]=[],timers=new Map<number,()=>void>();let next=v(),id=0
 class Api{async request(path:string,method:string,body:unknown){calls.push({path,method,body});if(catalogPending&&path.startsWith('/api/s11/catalog'))return new Promise(()=>{});return next}}
 class ApiError extends Error{status=0}
 const blank=Vue.defineComponent({render:()=>null})
 const deps:any={vue:Vue,'./api':{Api,ApiError},'./cinematic':cinematic,'./taskBridge':bridge,'./shipTasks':tasks,'./sceneCue':cues,'./narration':{Narration,browserSpeechPort:()=>({cancel(){},speak(text:string,e:any){said.push(text);e.start();e.end()}})},'./cinematic.css':{}}
 for(const component of ['SceneStage','HarborCover','CinematicActor','ExamPanel','TeacherPanel','ShipTasks','TallyTask'])deps[`./components/${component}.vue`]={default:blank}
 for(const name of ['shore-plate-s13','river-night','river-plate-s13','river-clear-plate-s13','river-dawn-plate-s13','camp-night'])deps[`./assets/${name}.png`]={default:name}
 const {descriptor}=parse(readFileSync(new URL('../src/App.vue',import.meta.url),'utf8'))
 const script=compileScript(descriptor,{id:'app-director-test'})
 const exports:any={};const doc={addEventListener(){},removeEventListener(){},querySelector(){return null}}
 runInNewContext(ts.transpileModule(script.content,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{exports,require:(name:string)=>{assert.ok(name in deps,name);return deps[name]},console,crypto:webcrypto,document:doc,localStorage:{getItem(){return null},setItem(){}},matchMedia:()=>({matches:true}),window:{setInterval(fn:()=>void){timers.set(++id,fn);return id},setTimeout(fn:()=>void){timers.set(++id,fn);return id}},clearInterval(n:number){timers.delete(n)},clearTimeout(n:number){timers.delete(n)}})
 const component=exports.default;component.render=()=>null
 const renderer=Vue.createRenderer<any,any>({createElement:()=>({}),createText:()=>({}),createComment:()=>({}),setText(){},setElementText(){},patchProp(){},parentNode:()=>null,nextSibling:()=>null,insert(){},remove(){},insertStaticContent:()=>[{},{}]})
 const app=renderer.createApp(component);app.mount({});await Vue.nextTick()
 const state=(app as any)._instance.setupState
 state.user={user_id:'S-demo',name:'测试学生',role:'student',class_id:'C',class_ids:[],demo:true};state.view=v();state.reduced=true
 return {app,s:state,said,calls,setNext(value:any){next=value}}
}

test('首页进入新故事不会恢复旧路线，也不等待可选情境目录',async()=>{
 const h=await harness(true);try{
  h.s.page='cover';const old=h.s.view
  void h.s.enter();await Vue.nextTick()
  assert.equal(h.s.page,'roles');assert.equal(h.s.view,old)
  assert.equal(h.calls.filter(c=>c.path.endsWith('/sessions')).length,0)
 }finally{h.app.unmount()}
})
test('未登录的新故事意图不会被旧进度接管',async()=>{
 const h=await harness();try{h.s.user=null;h.s.page='cover';await h.s.enter();assert.equal(h.s.page,'login');assert.equal(h.s.entryIntent,'new')}finally{h.app.unmount()}
})
test('曹方寨前节点即使沿用camp分类，也不能把来船画在军帐地板上',async()=>{
 const h=await harness();try{
  h.s.page='story'
  h.s.view={...v('C1'),role:'C',stage:{world:'camp'}}
  assert.equal(h.s.backdrop,'shore-plate-s13')
  h.s.view={...v('C0'),role:'C',stage:{world:'camp'}}
  assert.equal(h.s.backdrop,'camp-night')
 }finally{h.app.unmount()}
})
test('真实App的adopt不重复整句；显全文不重播；换角只adopt一次',async()=>{
 const h=await harness();try{
  await h.s.resumeStory();assert.equal(h.said.length,1)
  h.setNext({...v('S9','fork'),transition:[{speaker:'韩伯',text:'前头就是曹营。还往近处走吗？'}]})
  h.s.selectedSnapshot='old';h.s.drawer='review';h.s.forkRole='Z'
  await h.s.fork();await Vue.nextTick();assert.equal(h.s.lines.length,1);assert.equal(h.said.length,2)
  h.s.nextLine();assert.equal(h.said.length,2)
  assert.equal(h.calls.filter(c=>c.path.endsWith('/forks')).length,1)
 }finally{h.app.unmount()}
})
test('真实App连续静默节点的返航不会开启听辨窗口或请求任务审查',async()=>{
 const h=await harness();try{
  await h.s.resumeStory()
  for(const node of ['S11','S12','S15','S16','S17']){
   await h.s.adopt(v(node),true);h.setNext(v('R0'));await h.s.act({id:node+'.go',label:'回去'})
   assert.equal(h.s.shipTask,null);assert.equal(h.s.view.node_id,'R0')
  }
  assert.equal(h.calls.filter(c=>c.path.endsWith('/review')).length,0)
  assert.equal(h.calls.filter(c=>c.path.endsWith('/actions')).length,5)
 }finally{h.app.unmount()}
})
test('回看切线和提交疑问关窗后，当前新句自动播一次',async()=>{
 const h=await harness();try{
  await h.s.resumeStory();h.s.drawer='review';h.setNext(v('S8','returned'));await h.s.switchRoute('returned');await Vue.nextTick()
  assert.equal(h.said.length,2)
  h.s.drawer='expression';h.s.pending={id:'S8.ask',label:'问孔明'};h.s.text='曹军追来，如何撤？';h.setNext(v('S9','returned'))
  await h.s.express();await Vue.nextTick();assert.equal(h.said.length,3)
 }finally{h.app.unmount()}
})
test('动作对白先于新一阵箭，动画完成才接目标开场；每句一次',async()=>{
 const h=await harness();try{
  await h.s.resumeStory();h.s.reduced=false
  h.s.view={...v('A0'),visual:{first:52000,second:0,side:'right',weather:'fog'}}
  await h.s.adopt({...v('A4'),visual:{first:52000,second:51000,side:'left',weather:'fog'},speaker:'阿成',lines:['另一边也满了！'],transition:[{speaker:'鲁肃',text:'把另一面转过去？'},{speaker:'诸葛亮',text:'转。后船依次跟上。'}]})
  assert.equal(h.s.current.text,'把另一面转过去？');assert.equal(h.s.visual.second,0)
  h.s.nextLine();h.s.nextLine();assert.equal(h.s.current.text,'转。后船依次跟上。');assert.equal(h.s.visual.second,0)
  h.s.nextLine();h.s.onKey({key:'Enter',target:{tagName:'MAIN'},preventDefault(){}});assert.equal(h.s.visual.second,51000);assert.equal(h.s.stageMoving,true)
  h.s.motion(false);assert.equal(h.s.current.text,'另一边也满了！')
  for(const text of ['把另一面转过去？','转。后船依次跟上。','另一边也满了！'])assert.equal(h.said.filter(s=>s===text).length,1)
 }finally{h.app.unmount()}
})
test('箭雨待播时恢复或切线，不能重演原路线命令',async()=>{
 const h=await harness();try{
  await h.s.resumeStory();h.s.reduced=false
  const target={...v('A4'),visual:{first:52000,second:51000,side:'left',weather:'fog'},speaker:'阿成',lines:['另一边也满了！'],transition:[{speaker:'诸葛亮',text:'转。后船依次跟上。'}]}
  await h.s.adopt(target);assert.ok(h.s.beforeMotion)
  await h.s.adopt(target,true);assert.equal(h.s.beforeMotion,null);assert.equal(h.s.visual.second,51000);assert.equal(h.s.current.text,'另一边也满了！')
  h.s.motion(false);assert.equal(h.s.current.text,'另一边也满了！')
  h.s.view=v('A0');await h.s.adopt(target);h.s.drawer='review';h.setNext(v('S8','other'));await h.s.switchRoute('other')
  assert.equal(h.s.beforeMotion,null);assert.equal(h.s.visual.second,0);h.s.motion(false);assert.equal(h.s.current.text,'前头就是曹营。还往近处走吗？')
 }finally{h.app.unmount()}
})
