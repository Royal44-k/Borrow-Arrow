import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import test from 'node:test'
import {runInNewContext} from 'node:vm'
import {webcrypto} from 'node:crypto'
import {parse,compileScript,compileTemplate} from 'vue/compiler-sfc'
import ts from 'typescript'
import * as Vue from 'vue'
import * as taskHelpers from '../src/shipTasks.ts'
type E={type:string;props:Record<string,any>;children:E[];parent?:E;text?:string;addEventListener:()=>void;removeEventListener:()=>void}
function el(type:string):E{return{type,props:{},children:[],addEventListener(){},removeEventListener(){}}}
const context={routeId:'r',nodeId:'S2',actorId:'a',authorName:'署名',activityMode:'individual',material:'straw',layout:'both',currentSide:'right',first:52000,second:0,hadArrows:true,reportText:'看清那排人影！',supportIds:[],reducedMotion:true}
async function flush(){await Promise.resolve();await Vue.nextTick();await Promise.resolve();await Vue.nextTick()}
async function mount(task:string,options:{server?:Record<string,unknown>;cached?:unknown;error?:string}={}){
 let source='';try{source=readFileSync(new URL('../src/components/ShipTasks.vue',import.meta.url),'utf8')}catch{assert.fail('ShipTasks.vue has not been implemented')}
 const {descriptor}=parse(source);const script=compileScript(descriptor,{id:'ship-tasks-test'});const template=compileTemplate({source:descriptor.template!.content,filename:'ShipTasks.vue',id:'ship-tasks-test',compilerOptions:{bindingMetadata:script.bindings}});assert.deepEqual(template.errors,[])
 const store=new Map();if(options.cached)store.set(`caocuan:s11:ship-task:v1:${task}:r:S2:a`,JSON.stringify(options.cached));const evaluate=(s:string,deps:Record<string,unknown>)=>{const exports:Record<string,any>={};runInNewContext(ts.transpileModule(s,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{exports,require:(id:string)=>{if(!(id in deps))throw Error('Unexpected import '+id);return deps[id]},console,crypto:webcrypto,window:{setTimeout:(fn:()=>void)=>{fn();return 1}},clearTimeout(){},localStorage:{getItem:(k:string)=>store.get(k)??null,setItem:(k:string,v:string)=>store.set(k,v)}});return exports}
 const component=evaluate(script.content,{vue:Vue,'../shipTasks':taskHelpers,'../assets/cast-support-s11.png':{default:'test-atlas'},'../assets/deck-passage-s13.png':{default:'test-deck'},'../assets/loose-straw-s13.png':{default:'test-straw'}}).default;component.render=evaluate(template.code,{vue:Vue}).render
 const renderer=Vue.createRenderer<E,E>({insertStaticContent(content,p,a){const n=el('#static');n.text=content;n.parent=p;const i=a?p.children.indexOf(a):-1;p.children.splice(i<0?p.children.length:i,0,n);return[n,n]},createElement:el,createText:t=>({...el('#text'),text:t}),createComment:t=>({...el('#comment'),text:t}),setText(n,t){n.text=t},setElementText(n,t){n.children=[];n.text=t},patchProp(n,k,o,v){n.props[k]=v},parentNode:n=>n.parent??null,nextSibling:n=>n.parent?.children[n.parent.children.indexOf(n)+1]??null,insert(n,p,a){if(n.parent){const i=n.parent.children.indexOf(n);if(i>=0)n.parent.children.splice(i,1)}n.parent=p;const i=a?p.children.indexOf(a):-1;p.children.splice(i<0?p.children.length:i,0,n)},remove(n){if(n.parent){const i=n.parent.children.indexOf(n);if(i>=0)n.parent.children.splice(i,1)}}})
 const completed:any[]=[],progress:any[]=[],closed:any[]=[];const app=renderer.createApp(component,{task,context:{...context,initialPayload:options.server},error:options.error,onComplete:(p:any)=>completed.push(p),onProgress:(p:any)=>progress.push(p),onClose:(p:any)=>closed.push(p)});app.mount(el('root'));await flush();return{app,state:(app as any)._instance.setupState,completed,progress,closed}
}
test('M03 compiled widget moves an actual blocker and verifies the visible passage before completion',async()=>{const h=await mount('passage');try{h.state.finish();assert.equal(h.completed.length,0);h.state.move();await flush();assert.equal(h.state.state.obstacle,'right_rack');await h.state.walk();await flush();h.state.finish();assert.equal(h.completed[0].blocked_after,false);assert.equal(h.completed[0].walked,true)}finally{h.app.unmount()}})
test('M07 compiled widget emits cumulative original/feedback/corrected facts and preserves close draft',async()=>{const h=await mount('side');try{h.state.point('right');h.state.point('left');h.state.leave();assert.equal(h.closed[0].first_attempt.side,'right');assert.equal(h.progress.at(-1).attempts.length,2);assert.equal(h.progress.at(-1).attempts[1].feedback_before.length,1);h.state.finish();assert.equal(h.completed[0].selected_side,'left')}finally{h.app.unmount()}})
test('M09 no-audio alternative is stored as text, never falsely as heard audio',async()=>{const h=await mount('listening');try{h.state.readClip('arrow_change');h.state.readClip('shore_report');h.state.editResponse({target:{value:'我担心哨艇靠近，先告诉韩伯留好退路。'}});h.state.finish();assert.equal(h.completed.length,1);assert.ok(h.completed[0].heard.every((x:any)=>x.mode==='text_equivalent'));assert.equal(h.completed[0].response,'我担心哨艇靠近，先告诉韩伯留好退路。')}finally{h.app.unmount()}})
test('M03 pointer capture delivers release over the rack without native HTML drag',async()=>{
 const h=await mount('passage');try{assert.equal(typeof h.state.pointerStart,'function','the moving pointer must be captured');let captures=0,releases=0;const target={setPointerCapture(){captures++},releasePointerCapture(){releases++}};h.state.storageZone={getBoundingClientRect:()=>({left:700,right:800,top:200,bottom:300})};h.state.pointerStart({pointerId:1,button:0,clientX:574,clientY:352,currentTarget:target});h.state.pointerUp({pointerId:1,clientX:753,clientY:253});h.state.pointerUp({pointerId:1,clientX:753,clientY:253});assert.equal(captures,1);assert.equal(releases,1);assert.equal(h.state.state.obstacle,'right_rack');assert.equal(h.state.state.placements.length,1)}finally{h.app.unmount()}
})

test('M03 dragged grass follows the pointer and a cancelled drag leaves the passage blocked',async()=>{
 const h=await mount('passage');try{
  assert.equal(typeof h.state.pointerMove,'function')
  const target={setPointerCapture(){},releasePointerCapture(){}}
  h.state.pointerStart({pointerId:7,button:0,clientX:300,clientY:310,currentTarget:target})
  h.state.pointerMove({pointerId:7,clientX:420,clientY:250})
  assert.equal(h.state.dragOffset.x,120);assert.equal(h.state.dragOffset.y,-60)
  h.state.cancelPointer()
  assert.equal(h.state.dragOffset.x,0);assert.equal(h.state.dragOffset.y,0)
  assert.equal(h.state.state.obstacle,'passage');assert.equal(h.completed.length,0)
 }finally{h.app.unmount()}
})

test('compiled task reopens an unsent sentence against the same server draft without erasing it',async()=>{
 const remote=taskHelpers.markHeard(taskHelpers.newTask('listening','same-server'),'arrow_change','local_web_audio','t1');const cached=taskHelpers.setTaskResponse(remote,'尚未失焦的原句仍须保留。');const h=await mount('listening',{server:taskHelpers.taskPayload(remote,'draft'),cached,error:'保存中断'});try{assert.equal(h.state.state.response,cached.response);assert.equal(h.state.state.heard.length,1);assert.equal(h.state.state.id,'same-server')}finally{h.app.unmount()}
})
test('compiled task keeps completed server wording and offers conflicting local text separately',async()=>{
 let remote=taskHelpers.markHeard(taskHelpers.markHeard(taskHelpers.newTask('listening','same-server'),'arrow_change','text_equivalent','t1'),'shore_report','text_equivalent','t2');remote=taskHelpers.setTaskResponse(remote,'已保存的原句。');const cached=taskHelpers.setTaskResponse(remote,'尚未同步的另一句。');const h=await mount('listening',{server:taskHelpers.taskPayload(remote,'complete'),cached});try{assert.equal(h.state.state.response,'已保存的原句。');assert.equal(h.state.conflictText,'尚未同步的另一句。');h.state.recoverText();assert.equal(h.state.state.response,'已保存的原句。')}finally{h.app.unmount()}
})
