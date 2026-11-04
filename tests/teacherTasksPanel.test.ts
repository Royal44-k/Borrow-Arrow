import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {runInNewContext} from 'node:vm'
import {parse,compileScript,compileTemplate} from 'vue/compiler-sfc'
import ts from 'typescript'
import * as Vue from 'vue'
import * as assessment from '../src/assessment.ts'
import * as aiAssessment from '../src/aiAssessment.ts'
type E={type:string;props:Record<string,any>;children:E[];parent?:E;text?:string;addEventListener:()=>void;removeEventListener:()=>void}
function el(type:string):E{return{type,props:{},children:[],addEventListener(){},removeEventListener(){}}}
function text(n:E):string{return(n.text??'')+n.children.map(text).join('')}
const first={sequence:1,side:'right',feedback_before:[],support_ids:[]}
const base={id:'one',record_id:'r',route_id:'route',node_id:'A0',task_id:'M07_SIDE',actor_id:'a',author_name:'本人',account_id:'S1',activity_mode:'group',created_at:'2026-10-28T00:00:00Z',revision:1,payload:{status:'draft',first_attempt:first,attempts:[first],feedback:[],selected_side:'right'}}
const rows=[base,{...base,id:'two',revision:2,feedback_display:[{id:'f',sequence:2,text:'右边已有箭，左边还空着。'}],payload:{...base.payload,status:'complete',attempts:[first,{sequence:3,side:'left',feedback_before:['f'],support_ids:[]}],selected_side:'left'}},{...base,id:'three',record_id:'peer',task_id:'M03_PASSAGE',author_name:'同伴署名',account_id:null,payload:{status:'complete',placements:[{object_id:'loose_bundle'}],blocked_after:false,walked:true}}]
async function flush(){for(let i=0;i<5;i++){await Promise.resolve();await Vue.nextTick()}}
test('teacher task facts show the original side, assisted correction and real group signature',async()=>{
 const {descriptor}=parse(readFileSync(new URL('../src/components/TeacherPanel.vue',import.meta.url),'utf8'));const script=compileScript(descriptor,{id:'teacher-tasks'});const template=compileTemplate({source:descriptor.template!.content,filename:'TeacherPanel.vue',id:'teacher-tasks',compilerOptions:{bindingMetadata:script.bindings}});assert.deepEqual(template.errors,[])
 function evaluate(s:string,deps:Record<string,unknown>){const exports:Record<string,any>={};runInNewContext(ts.transpileModule(s,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{exports,require:(id:string)=>deps[id],console});return exports}
 const component=evaluate(script.content,{vue:Vue,'../assessment':assessment,'../aiAssessment':aiAssessment}).default;component.render=evaluate(template.code,{vue:Vue}).render
 const renderer=Vue.createRenderer<E,E>({insertStaticContent(content,p,a){const n=el('#static');n.text=content;n.parent=p;const i=a?p.children.indexOf(a):-1;p.children.splice(i<0?p.children.length:i,0,n);return[n,n]},createElement:el,createText:t=>({...el('#text'),text:t}),createComment:t=>({...el('#comment'),text:t}),setText(n,t){n.text=t},setElementText(n,t){n.children=[];n.text=t},patchProp(n,k,o,v){n.props[k]=v},parentNode:n=>n.parent??null,nextSibling:n=>n.parent?.children[n.parent.children.indexOf(n)+1]??null,insert(n,p,a){if(n.parent){const i=n.parent.children.indexOf(n);if(i>=0)n.parent.children.splice(i,1)}n.parent=p;const i=a?p.children.indexOf(a):-1;p.children.splice(i<0?p.children.length:i,0,n)},remove(n){if(n.parent){const i=n.parent.children.indexOf(n);if(i>=0)n.parent.children.splice(i,1)}}})
 const student={user_id:'S1',name:'本人',class_id:'A',route_count:1,attempt_count:0,published_total:null,demo:true};const app=renderer.createApp(component,{request:async(path:string)=>path==='/api/teacher/students'?{students:[student]}:path==='/api/teacher/exam'?{items:[]}:{student,routes:[],matrix:[],attempts:[],comment:null,ai_mode:'disabled',limitations:[],s11:{expressions:[],supports:[],events:[],tasks:rows}}});const root=el('root');app.mount(root);await flush()
 try{const visible=text(root);assert.match(visible,/首次指向右舷/);assert.match(visible,/提示后指向左舷/);assert.match(visible,/同伴署名/);assert.match(visible,/共端署名，未绑定账号/);assert.match(visible,/右边已有箭，左边还空着/);assert.equal((app as any)._instance.setupState.processTasks.length,2)}finally{app.unmount()}
})
