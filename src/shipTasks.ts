/** Raw, append-only task facts. These helpers never compute a learner score. */
export type ShipTask = 'passage'|'side'|'listening'
export type TaskSide = 'right'|'left'
export type ClipId = 'arrow_change'|'shore_report'
export interface ShipTaskContext {
 routeId:string;nodeId:string;actorId:string;authorName:string;activityMode:'individual'|'group';
 material:'straw'|'armor'|'none';layout:'both'|'one'|'none';currentSide:TaskSide;first:number;second:number;
 hadArrows:boolean;reportText?:string;supportIds?:string[];recordId?:string;initialPayload?:Record<string,unknown>|null
}
export interface SideAttempt {sequence:number;side:TaskSide;feedback_before:string[];support_ids:string[];client_at:string}
export interface TaskFeedback {id:string;sequence:number;code:'COMPARE_SIDES'|'LOOK_EMPTY_SIDE';source:'authored_task_feedback';client_at:string}
export interface HeardFact {sequence:number;clip_id:ClipId;mode:'local_web_audio'|'text_equivalent';client_at:string}
export interface PlacementFact {sequence:number;object_id:'loose_bundle';from:'passage';to:'right_rack';client_at:string}
export interface ShipTaskState {id:string;task:ShipTask;sequence:number;obstacle:'passage'|'right_rack';placements:PlacementFact[];walked:boolean;attempts:SideAttempt[];feedback:TaskFeedback[];heard:HeardFact[];response:string;responseEdited?:boolean}
export interface SoundSegment {kind:'arrow'|'water'|'call';at:number;duration:number;frequency:number;gain:number}
export interface SoundPlan {duration:number;segments:SoundSegment[]}
export const TASK_IDS={passage:'M03_PASSAGE',side:'M07_SIDE',listening:'M09_LISTEN'} as const
export const FEEDBACK_TEXT={COMPARE_SIDES:'右边已有箭，左边还空着。',LOOK_EMPTY_SIDE:'看看哪边还没落箭。您指给我，我来掌舵。'} as const
export function newTask(task:ShipTask,id:string):ShipTaskState {return{id,task,sequence:0,obstacle:'passage',placements:[],walked:false,attempts:[],feedback:[],heard:[],response:''}}
/** Caller supplies the authenticated server's latest matching task payload. */
export function restoreTask(task:ShipTask,id:string,payload:unknown):ShipTaskState {
 const s=newTask(task,id)
 if(!payload||typeof payload!=='object'||Array.isArray(payload))return s
 const p=payload as Record<string,unknown>
 if(typeof p.record_id!=='string'||!p.record_id)return s
 s.id=p.record_id
 for(const key of ['placements','attempts','feedback','heard'] as const)if(Array.isArray(p[key]))s[key]=JSON.parse(JSON.stringify(p[key]))
 s.sequence=Math.max(0,...[...s.placements,...s.attempts,...s.feedback,...s.heard].map(x=>Number(x.sequence)||0))
 s.obstacle=p.blocked_after===false&&s.placements.length?'right_rack':'passage'
 s.walked=p.walked===true&&s.obstacle==='right_rack'
 s.response=typeof p.response==='string'?p.response.slice(0,2000):''
 s.responseEdited=false
 return s
}
function canonical(value:unknown):string {return JSON.stringify(value,(_key,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b))):v)}
/** A compatible draft may append local facts, but cannot rewrite server facts. */
export function mergeTaskDraft(task:ShipTask,id:string,server:unknown,local:ShipTaskState|null):{state:ShipTaskState;conflictText:string} {
 if(!server||typeof server!=='object'||Array.isArray(server)||typeof (server as Record<string,unknown>).record_id!=='string')return {state:local??newTask(task,id),conflictText:''}
 const p=server as Record<string,unknown>,remote=restoreTask(task,id,server)
 if(!local)return {state:remote,conflictText:''}
 const dirty=local.responseEdited===true||(local.responseEdited===undefined&&!!local.response&&local.response!==remote.response)
 const keys:('placements'|'attempts'|'feedback'|'heard')[]=task==='passage'?['placements']:task==='side'?['attempts','feedback']:['heard']
 const compatible=p.status!=='complete'&&local.id===remote.id&&local.task===task&&keys.every(k=>canonical(local[k].slice(0,remote[k].length))===canonical(remote[k]))
 if(!compatible)return {state:remote,conflictText:dirty&&local.response!==remote.response?local.response:''}
 return {state:{...local,sequence:Math.max(local.sequence,remote.sequence),response:dirty?local.response:remote.response,responseEdited:dirty&&local.response!==remote.response},conflictText:''}
}
export function moveObstacle(state:ShipTaskState,target:string,at:string):ShipTaskState {
 if(state.task!=='passage'||target!=='right_rack'||state.obstacle!=='passage')return state
 const sequence=state.sequence+1
 return {...state,sequence,obstacle:'right_rack',placements:[...state.placements,{sequence,object_id:'loose_bundle',from:'passage',to:'right_rack',client_at:at}]}
}
export function verifyPassage(state:ShipTaskState,_at:string):ShipTaskState {return state.task==='passage'&&state.obstacle==='right_rack'&&!state.walked?{...state,sequence:state.sequence+1,walked:true}:state}
export function addSideHelp(state:ShipTaskState,code:TaskFeedback['code'],at:string):ShipTaskState {
 if(state.task!=='side'||state.feedback.length>=50)return state
 const sequence=state.sequence+1
 return {...state,sequence,feedback:[...state.feedback,{id:`${state.id}:feedback:${sequence}`,sequence,code,source:'authored_task_feedback',client_at:at}]}
}
export function pointSide(state:ShipTaskState,side:TaskSide,context:ShipTaskContext,at:string):ShipTaskState {
 if(state.task!=='side'||!['left','right'].includes(side)||state.attempts.length>=100)return state
 const sequence=state.sequence+1
 let next:ShipTaskState={...state,sequence,attempts:[...state.attempts,{sequence,side,feedback_before:state.feedback.map(f=>f.id),support_ids:[...(context.supportIds??[])].slice(-50),client_at:at}]}
 // The concrete comparison shown after pointing to the already-loaded side is
 // itself assistance; a later correction cannot be called an unassisted first try.
 if(side===context.currentSide&&!state.feedback.some(f=>f.code==='COMPARE_SIDES'))next=addSideHelp(next,'COMPARE_SIDES',at)
 return next
}
export function sideDescription(side:TaskSide,c:ShipTaskContext):string {
 const name=side==='right'?'右舷':'左舷'
 const fitted=c.layout==='both'||(c.layout==='one'&&side==='right')
 if(!fitted||c.material==='none')return `${name}是空栏，没有装置；转向后也不能凭空留住箭。`
 const amount=side==='right'?c.first:c.second
 return amount>0?`${name}的${c.material==='armor'?'木撑和外板':'草束'}已经留着箭。`:`${name}的${c.material==='armor'?'木撑空甲':'草束'}仍没有这一阵的新箭。`
}
export function markHeard(state:ShipTaskState,clip:ClipId,mode:HeardFact['mode'],at:string):ShipTaskState {
 if(state.task!=='listening'||state.heard.length>=200)return state
 const sequence=state.sequence+1
 return {...state,sequence,heard:[...state.heard,{sequence,clip_id:clip,mode,client_at:at}]}
}
export function setTaskResponse(state:ShipTaskState,text:string):ShipTaskState {return {...state,response:text.slice(0,2000),responseEdited:true}}
export function taskComplete(s:ShipTaskState):boolean {
 if(s.task==='passage')return s.obstacle==='right_rack'&&s.walked
 if(s.task==='side')return s.attempts.length>0
 return ['arrow_change','shore_report'].every(id=>s.heard.some(h=>h.clip_id===id))&&s.response.trim().length>0
}
export function taskPayload(s:ShipTaskState,status:'draft'|'complete') {
 const base={record_id:s.id,status:status==='complete'&&taskComplete(s)?'complete' as const:'draft' as const}
 if(s.task==='passage')return {...base,placements:s.placements.map(x=>({...x})),blocked_after:s.obstacle==='passage',walked:s.walked}
 if(s.task==='side')return {...base,attempts:s.attempts.map(a=>({...a,feedback_before:[...a.feedback_before],support_ids:[...a.support_ids]})),first_attempt:s.attempts[0]?{...s.attempts[0],feedback_before:[...s.attempts[0].feedback_before],support_ids:[...s.attempts[0].support_ids]}:null,feedback:s.feedback.map(f=>({...f})),selected_side:s.attempts.at(-1)?.side??null}
 return {...base,heard:s.heard.map(h=>({...h})),replays:{arrow_change:s.heard.filter(h=>h.clip_id==='arrow_change').length,shore_report:s.heard.filter(h=>h.clip_id==='shore_report').length},response:s.response,sound_source:'local_web_audio' as const}
}
export function clipCaption(clip:ClipId,c:ShipTaskContext):string {
 if(clip==='arrow_change')return c.hadArrows?'方才还有箭啸和落水声，随后安静了。':'江上只有水声，还没有听到来箭。'
 return c.reportText?.trim()?`岸上喊：“${c.reportText.trim()}”`:'岸上有脚步和灯下的动静，尚未听清新的查验喊声。'
}
export function soundPlan(clip:ClipId,c:ShipTaskContext):SoundPlan {
 if(clip==='arrow_change')return {duration:2.6,segments:c.hadArrows?[0,.18,.44,.71,.95,1.2].map((at,i)=>({kind:'arrow' as const,at,duration:.3,frequency:1250-i*70,gain:.12})): [{kind:'water',at:0,duration:1.4,frequency:180,gain:.055}]}
 return {duration:2.2,segments:c.reportText?.trim()?[0,.28,.57,.98,1.25].map((at,i)=>({kind:'call' as const,at,duration:.2,frequency:210+(i%3)*35,gain:.13})):[0,.45,.95].map(at=>({kind:'water' as const,at,duration:.25,frequency:150,gain:.04}))}
}
