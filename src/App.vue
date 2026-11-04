<script setup lang="ts">
import {computed,nextTick,onBeforeUnmount,onMounted,ref,watch} from 'vue'
import SceneStage from './components/SceneStage.vue'
import HarborCover from './components/HarborCover.vue'
import CinematicActor from './components/CinematicActor.vue'
import ExamPanel from './components/ExamPanel.vue'
import TeacherPanel from './components/TeacherPanel.vue'
import ShipTasks from './components/ShipTasks.vue'
import TallyTask from './components/TallyTask.vue'
import {TASK_IDS,type ShipTask,type ShipTaskContext} from './shipTasks'
import {taskBeforeAction,taskIdentity} from './taskBridge'
import {sceneCue} from './sceneCue'
import {Narration,browserSpeechPort,type VoiceStatus} from './narration'
import {Api,ApiError} from './api'
import {PROLOGUE,ROLE_NAMES,ROLE_PROMISES,publicStage,stageMode,playableLines,sceneLines,visibleActions,operationAction,replayMemories,helpPrompts,screenTitle,type StoryView,type StoryAction,type Line} from './cinematic'
import river from './assets/river-night.png'
import riverPlate from './assets/river-plate-s13.png'
import shorePlate from './assets/shore-plate-s13.png'
import clearRiver from './assets/river-clear-plate-s13.png'
import dawn from './assets/river-dawn-plate-s13.png'
import camp from './assets/camp-night.png'
import './cinematic.css'
type User={user_id:string;name:string;role:'student'|'teacher';class_id:string;class_ids:string[];demo:boolean}
type Page='cover'|'login'|'prologue'|'roles'|'story'
const page=ref<Page>('cover'),user=ref<User|null>(null),auth=ref(''),sessionToken=ref(''),view=ref<StoryView|null>(null)
const entryIntent=ref<'new'|'resume'>('new')
const booting=ref(true),busy=ref(false),error=ref(''),notice=ref(''),loginId=ref(''),password=ref('')
const role=ref<'L'|'Z'|'C'>('L'),mode=ref('individual'),names=ref(''),scenario=ref('standard'),replay=ref(false),scenarios=ref<any[]>([])
const drawer=ref(''),exam=ref(false),teacher=ref(false),review=ref<any>(null),routes=ref<any[]>([]),selectedSnapshot=ref(''),forkRole=ref('Z')
const lineIndex=ref(0),revealed=ref(0),lines=ref<Line[]>([]),transitioning=ref(false),transitionLabel=ref(''),operationMode=ref(''),pending=ref<StoryAction|null>(null)
const text=ref(''),helpText=ref(''),inspectText=ref(''),placed=ref<string[]>([]),stageError=ref(''),sound=ref(false),voice=ref(stored('caocuan:voice')!=='off'),reduced=ref(false),rain=ref(false)
const voiceStatus=ref<VoiceStatus>('idle'),cueText=ref('')
let voiceGesture=false,voiceWarning=false,beatSequence=0
const narrator=new Narration(browserSpeechPort(),status=>{voiceStatus.value=status;if(status==='unavailable'&&!voiceWarning){voiceWarning=true;notify('本机对白暂时无法发声；字幕可继续，声音设置中可重试。')}})
const helpSpeaker=ref('沈砚'),expressionKind=ref('utterance')
const stageMoving=ref(false),stageInstance=ref(0)
const beforeMotion=ref<{opening:Line[];turned:boolean}|null>(null),heldVisual=ref<ReturnType<typeof publicStage>|null>(null)
const shipTask=ref<ShipTask|null>(null),shipContext=ref<ShipTaskContext|null>(null)
const tallyOpen=ref(false),tallyReadyRoute=ref('')
const tallyContext=computed(()=>view.value?.task_context?.M12_TALLY)
const finishedTasks=new Set<string>()
let taskAction:StoryAction|null=null
let taskQueue:Promise<unknown>=Promise.resolve()
let afterMotion:Line[]|null=null,expressionReceipt:{route:string;text:string}|null=null
let soundOptedOut=false
const soundStarting=ref(false)
let typeTimer=0,cutTimer=0,noticeTimer=0,rainTimer=0,ambience:AudioContext|undefined,master:GainNode|undefined,wind:AudioBufferSourceNode|undefined
let identity:{fingerprint:string;id:string}|null=null
const api=new Api(()=>auth.value||null,()=>sessionToken.value||null)
const request=(path:string,method='GET',body?:unknown)=>api.request<any>(path,method,body)
const current=computed(()=>lines.value[lineIndex.value]??{speaker:'',text:''})
const typed=computed(()=>current.value.text.slice(0,revealed.value))
const dialogueDone=computed(()=>lineIndex.value===lines.value.length-1&&revealed.value>=current.value.text.length)
const actions=computed(()=>view.value?visibleActions(view.value).map(a=>a.id==='COUNT1.done'&&(tallyContext.value?.progress.record_id||tallyReadyRoute.value===view.value?.route_id)?{...a,label:tallyContext.value?.progress.status==='complete'?'把箭送入帐中':'继续核对箭簿'}:a):[])
const ended=computed(()=>view.value?.status==='ended')
const visual=computed(()=>heldVisual.value??(view.value?publicStage(view.value):{material:'none' as const,layout:'none' as const,side:'right' as const,weather:'dense' as const,first:0,second:0,fire:'none' as const}))
const world=computed(()=>page.value==='prologue'?'camp':view.value?.stage.world??'shore')
const backdrop=computed(()=>{
 if(page.value==='prologue')return camp
 if(page.value!=='story')return river
 if(ended.value)return camp
 if(view.value?.role==='C')return view.value.node_id==='C0'?camp:shorePlate
 if(world.value==='camp')return camp
 if(['return','count'].includes(world.value))return dawn
 return visual.value.weather==='clear'?clearRiver:riverPlate
})
const effectiveMode=computed(()=>operationMode.value||(view.value?stageMode(view.value):'river'))
const showStage=computed(()=>page.value==='story'&&!ended.value)
const stageLayout=computed(()=>view.value?.node_id==='S2'&&placed.value.length?placed.value.includes('left')?'both':'right':visual.value.layout)
const chapter=computed(()=>{const s=view.value?.scene??'';return view.value?.role==='C'?'北岸 · 守寨':s==='M02'||s==='M03'?'江东 · 备船':s==='M04'?'江边 · 候时':s==='M12'?'南岸 · 清点':s==='M13'||ended.value?'军帐 · 交箭':'江上 · 借箭'})
const speaking=computed(()=>drawer.value==='help'?helpSpeaker.value:current.value.speaker)
const actorVisible=computed(()=>!['旁白','末场',''].includes(speaking.value))
const nearSpeaker=computed(()=>actorVisible.value&&!(view.value?.role!=='C'&&['岸上军士','岸上弓手','哨长'].includes(speaking.value)))
const riverCue=computed(()=>view.value?sceneCue(view.value):null)
const activeActor=computed(()=>view.value?.members.find(m=>m.id===view.value?.controller_id)?.name??user.value?.name??'')
const allSnapshots=computed(()=>replayMemories(review.value?.snapshots??[]))
const latestSnapshots=computed(()=>{const all=allSnapshots.value;const selected=[all.find(s=>s.node_id==='S8'),all.find(s=>['A0','S15','C2'].includes(s.node_id)),all.filter(s=>s.node_id!=='X1').at(-1)].filter(Boolean);return [...new Map(selected.map(s=>[s.id,s])).values()].slice(0,3)})
const availableScenarios=computed(()=>scenarios.value.filter(s=>role.value==='C'||!['counterfire','no_contact'].includes(s.id)))
const helpChoices=computed(()=>helpPrompts(view.value?.node_id??'',view.value?.role??'L'))
const expressionTitle=computed(()=>expressionKind.value==='reflection'?(view.value?.node_id==='COUNT1'?'把数目报清楚':'低声告诉同伴'):view.value?.role==='Z'?'答鲁肃':'问孔明')
const expressionPrompt=computed(()=>expressionKind.value==='reflection'?(view.value?.node_id==='COUNT1'?'这次实际带回多少箭？发出去的、受损的各是多少？报给清点的阿成听。':'箭声忽然停了。你最担心接下来发生什么，打算怎样照应这船人？'):view.value?.role==='Z'?'他就在你面前，等你回应这份担心。':'最担心曹军做什么？向孔明问清楚。')
function stored(key:string){try{return localStorage.getItem(key)}catch{return null}}
function save(key:string,value:string){try{localStorage.setItem(key,value)}catch{notify('本机未能记住入口；请保持当前页面。')}}
function notify(value:string){notice.value=value;clearTimeout(noticeTimer);noticeTimer=window.setTimeout(()=>notice.value='',4500)}
function failure(e:unknown){error.value=e instanceof Error?e.message:'这一步尚未完成，请重试。';if(e instanceof ApiError&&e.status===401){page.value='login';drawer.value='';exam.value=false;teacher.value=false;tallyOpen.value=false;shipTask.value=null}}
function routeKey(){return `caocuan:s11:${user.value?.user_id??''}`}
function saveRoute(){if(view.value&&user.value)save(routeKey(),JSON.stringify({routeId:view.value.route_id,token:sessionToken.value,userId:user.value.user_id}))}
function setLines(value:Line[]){narrator.stop();beatSequence++;cueText.value='';lines.value=value.length?value:[{speaker:'旁白',text:'江面渐渐静了下来。'}];lineIndex.value=0;typeLine()}
function typeLine(){clearInterval(typeTimer);revealed.value=reduced.value?current.value.text.length:0;if(!reduced.value)typeTimer=window.setInterval(()=>{revealed.value=Math.min(current.value.text.length,revealed.value+1);if(revealed.value>=current.value.text.length)clearInterval(typeTimer)},38);readLine(false)}
function nextLine(){if(revealed.value<current.value.text.length){clearInterval(typeTimer);revealed.value=current.value.text.length;return}if(lineIndex.value<lines.value.length-1){lineIndex.value++;typeLine()}else if(beforeMotion.value){beginArrowMotion()}else if(page.value==='prologue'){save('caocuan:s11:prologue','seen');page.value='roles'}}
function beginArrowMotion(){const queued=beforeMotion.value;if(!queued)return;beforeMotion.value=null;afterMotion=queued.opening;heldVisual.value=null;stageMoving.value=true;playEffect('arrow');setLines([{speaker:queued.turned?'韩伯':'阿成',text:queued.turned?'各船跟上，慢些转！':'箭来了，伏低！'}])}
function readLine(repeat=true){if(!voice.value||!voiceGesture||drawer.value||exam.value||teacher.value||!['story','prologue'].includes(page.value))return;narrator.play(`${beatSequence}:${lineIndex.value}`,current.value.text,repeat)}
function toggleVoice(){voiceGesture=true;voice.value=!voice.value}
function observeRiver(){const cue=riverCue.value;if(!cue||busy.value)return;cueText.value=cue.line.speaker+'：'+cue.line.text;if(voice.value&&voiceGesture)narrator.play(`cue:${view.value?.route_id}:${view.value?.node_id}:${cue.id}`,cue.line.text,true)}
watch(voice,enabled=>{save('caocuan:voice',enabled?'on':'off');if(!enabled)narrator.stop();else{voiceGesture=true;readLine(true)}})
watch([page,drawer,exam,teacher,shipTask,tallyOpen],()=>{if(!['story','prologue'].includes(page.value)||drawer.value||exam.value||teacher.value||shipTask.value||tallyOpen.value)narrator.stop()})
function open(name:string){drawer.value=name;error.value='';nextTick(()=>document.querySelector<HTMLElement>('.s11-modal h2')?.focus())}
function close(){if(!busy.value)drawer.value=''}
async function enter(){if(booting.value)return;voiceGesture=true;entryIntent.value='new';if(!soundOptedOut)void startSound();if(!user.value){page.value='login';return}if(user.value.role==='teacher'){teacher.value=true;return}await newStory()}
async function resumeStory(){if(booting.value)return;voiceGesture=true;entryIntent.value='resume';if(!user.value){page.value='login';return}if(view.value){beforeMotion.value=null;heldVisual.value=null;afterMotion=null;stageMoving.value=false;page.value='story';setLines(playableLines(view.value));if(!soundOptedOut)void startSound()}else await newStory()}
function beginPrologue(){page.value='prologue';setLines(PROLOGUE);void startSound()}
async function login(){if(busy.value)return;busy.value=true;error.value='';try{const result=await request('/api/auth/login','POST',{user_id:loginId.value.trim(),password:password.value});auth.value=result.token;user.value=result.user;password.value='';view.value=null;sessionToken.value='';save('caocuan:auth',result.token);await restore();if(user.value?.role==='teacher'){teacher.value=true;page.value='cover'}else if(entryIntent.value==='resume'&&view.value){page.value='story';setLines(playableLines(view.value))}else await newStory()}catch(e){failure(e)}finally{busy.value=false}}
async function restore(){if(!user.value||user.value.role!=='student')return;const raw=stored(routeKey());if(!raw)return;try{const s=JSON.parse(raw);if(s.userId!==user.value.user_id)return;sessionToken.value=s.token;view.value=await request(`/api/s11/routes/${s.routeId}`)}catch(e){sessionToken.value='';view.value=null;if(!(e instanceof ApiError&&[403,404].includes(e.status)))throw e}}
async function logout(){if(busy.value)return;try{await request('/api/auth/logout','POST');auth.value='';sessionToken.value='';user.value=null;view.value=null;page.value='cover';drawer.value='';teacher.value=false;exam.value=false;save('caocuan:auth','');stopSound()}catch(e){failure(e)}}
async function start(){if(busy.value)return;busy.value=true;error.value='';try{const members=mode.value==='group'?[user.value!.name,...names.value.split(/[，,\n]/).map(s=>s.trim()).filter(Boolean)]:[user.value!.name];const chosen=role.value!=='C'&&['counterfire','no_contact'].includes(scenario.value)?'standard':scenario.value;const result=await request('/api/s11/sessions','POST',{role:role.value,scenario:chosen,activity_mode:mode.value,members});sessionToken.value=result.token;page.value='story';await adopt(result.view,true)}catch(e){failure(e)}finally{busy.value=false}}
async function adopt(v:StoryView,cut=false){const before=view.value;const changed=before?.node_id!==v.node_id||before?.route_id!==v.route_id;const added=(v.visual.first??0)+(v.visual.second??0)>(before?.visual.first??0)+(before?.visual.second??0);view.value=v;saveRoute();stageError.value='';if(changed){operationMode.value='';pending.value=null;placed.value=[];inspectText.value='';helpText.value=''}
 if(changed||cut){afterMotion=null;beforeMotion.value=null;heldVisual.value=null;stageMoving.value=false}
 if(added&&(reduced.value||v.role==='C'||v.ending)&&!cut)playEffect('arrow')
 if(changed||cut){const finalLines=sceneLines(v,!cut);
 if(added&&!cut&&!reduced.value&&before?.route_id===v.route_id&&v.role!=='C'&&!v.ending){const opening=playableLines(v),orders=finalLines.slice(0,Math.max(0,finalLines.length-opening.length));beforeMotion.value={opening,turned:v.visual.side!==before.visual.side};if(orders.length){heldVisual.value=publicStage(before);setLines(orders)}else beginArrowMotion()}else setLines(finalLines)
 transitioning.value=true;transitionLabel.value=screenTitle(v.node_id,v.title);clearTimeout(cutTimer);cutTimer=window.setTimeout(()=>transitioning.value=false,reduced.value?80:900)}
}
function motion(active:boolean){stageMoving.value=active;if(!active&&afterMotion){const value=afterMotion;afterMotion=null;setLines(value)}}
function commandId(kind:string,body:unknown){const fingerprint=JSON.stringify([view.value?.route_id,view.value?.revision,kind,body]);if(!identity||identity.fingerprint!==fingerprint)identity={fingerprint,id:crypto.randomUUID()};return identity.id}
async function mutate(path:string,body:Record<string,unknown>){if(!view.value||busy.value)return;busy.value=true;error.value='';const request_id=commandId(path,body);try{const v=await request(`/api/s11/routes/${view.value.route_id}/${path}`,'POST',{request_id,expected_revision:view.value.revision,actor_id:view.value.controller_id,...body});await adopt(v);identity=null;return v}catch(e){failure(e);if(e instanceof ApiError&&e.status===409){try{await adopt(await request(`/api/s11/routes/${view.value.route_id}`),true);identity=null;notify('同伴已更新了这一刻，现已回到最新场景。')}catch{}}}finally{busy.value=false}}
async function act(a:StoryAction){if(!view.value||!dialogueDone.value||busy.value)return;
 if(a.id==='COUNT1.done'&&tallyContext.value&&(tallyReadyRoute.value===view.value.route_id||tallyContext.value.progress.record_id)){if(tallyContext.value.progress.status==='complete'){await mutate('actions',{action_id:a.id,params:{}});return}tallyOpen.value=true;return}
 const task=taskBeforeAction(view.value,a)
 if(task){const v=view.value,key=taskIdentity(v.route_id,v.node_id,v.controller_id,task);if(!finishedTasks.has(key)){busy.value=true;try{const r=await request(`/api/s11/routes/${v.route_id}/review`);const latest=(r.tasks??[]).filter((t:any)=>t.task_id===TASK_IDS[task]&&t.node_id===v.node_id&&t.actor_id===v.controller_id).at(-1);if(latest?.payload.status==='complete')finishedTasks.add(key);else{const reports=(v.transition??[]).filter(l=>['岸上军士','哨长'].includes(l.speaker));shipContext.value={routeId:v.route_id,nodeId:v.node_id,actorId:v.controller_id,authorName:activeActor.value,activityMode:v.members.length>1?'group':'individual',material:visual.value.material,layout:visual.value.layout==='right'?'one':visual.value.layout,currentSide:visual.value.side,first:visual.value.first,second:visual.value.second,hadArrows:Number(v.visual.first??0)+Number(v.visual.second??0)>0,reportText:reports.map(l=>l.text).join(''),supportIds:(r.supports??[]).filter((s:any)=>(s.exposed_to??[s.actor_id]).includes(v.controller_id)).map((s:any)=>s.origin_support_id??s.id),recordId:latest?.record_id,initialPayload:latest?.payload} as ShipTaskContext;taskAction=a;shipTask.value=task;return}}catch(e){failure(e);return}finally{busy.value=false}}}
 if(a.id==='S8.ask'){expressionReceipt=null;expressionKind.value='utterance';text.value='';open('expression');pending.value=a;return}
 if(['turn','return','collect','water','drum'].includes(a.kind??'')||['A0.turn','A2.back','A3.turn','R0.return','COUNT1.done','F1.water','S10.drum'].includes(a.id)){pending.value=a;operationMode.value=a.id.includes('return')||a.kind==='return'?'return':a.kind==='turn'||a.id.endsWith('.turn')||a.id==='A2.back'?'helm':a.id==='COUNT1.done'?'collect':a.id==='F1.water'?'fire':'drum';inspectText.value=operationMode.value==='helm'?'韩伯：把空着的那一舷转向岸边，再叫后船跟上。':operationMode.value==='return'?'韩伯：南岸在来路那一边。您发令，我带头回去。':operationMode.value==='collect'?'阿成：取下来的箭放这里，我一束一束点。':operationMode.value==='fire'?'韩伯：桶在脚边！先把明火压下去。':'阿成：您发令，我就叫各船一起敲。';return}
 await mutate('actions',{action_id:a.id,params:{}})
}
function saveTask(payload:Record<string,any>){const route=view.value?.route_id,actor=view.value?.controller_id;const {task_id,...facts}=JSON.parse(JSON.stringify(payload));const job=taskQueue.then(async()=>{if(view.value?.route_id!==route||view.value?.controller_id!==actor){error.value='场景或操作者已改变，刚才的操作草稿仍保留在本机。';return}return mutate('tasks',{task_id,payload:facts})});taskQueue=job.catch(()=>undefined);return job}
async function completeTask(payload:Record<string,any>){if(!view.value||!shipTask.value)return;const task=shipTask.value,key=taskIdentity(view.value.route_id,view.value.node_id,view.value.controller_id,task);const saved=await saveTask(payload);if(!saved)return;finishedTasks.add(key);shipTask.value=null;shipContext.value=null;const next=taskAction;taskAction=null;if(next)await act(next)}
function closeTask(){shipTask.value=null;shipContext.value=null;taskAction=null}
async function answerTally(payload:Record<string,unknown>){await mutate('tasks',{task_id:'M12_TALLY',payload})}
async function finishTally(payload:Record<string,unknown>){if(!view.value||busy.value)return;if(tallyContext.value?.progress.status!=='complete'){const saved=await mutate('tasks',{task_id:'M12_TALLY',payload});if(!saved)return}const advanced=await mutate('actions',{action_id:'COUNT1.done',params:{}});if(advanced){tallyOpen.value=false;tallyReadyRoute.value='';operationMode.value=''}}
async function operate(op:Record<string,any>){if(!view.value||busy.value||!dialogueDone.value)return;
 if(op.kind==='inspect'&&view.value.role==='C'){inspectText.value=view.value.node_id==='C0'?'哨长：今夜这班哨还守在寨前，尚无新的江上军报。':view.value.visual.enemy_arrows==='visible_silhouette'?'哨长：箭射过去了，那排人影还立着。隔着江，船内看不清。':visual.value.weather==='clear'?'哨长：江上有船，船影比雾夜看得清。尚未近看。':'哨长：鼓声从雾里传来。只辨得出船影，看不清船上人脸。';return}
 if(op.kind==='inspect'){const words:Record<string,string>={rail:'韩伯：草束立在外边，青布挡住舱里的人。',passage:'韩伯：中间要走人，别把这儿堵住。',rope:'鲁肃：二十只船连在一起，号令才不乱。',lantern:'韩伯：看这盏灯，再看看对岸。',shore:visual.value.weather==='clear'?'韩伯：对岸的灯，一盏一盏都数得清。':'韩伯：只看得到灯影，看不清寨门。',right:'右舷 · 首先朝向曹营的一侧',left:'左舷 · 另一侧'};inspectText.value=words[op.part]??'';return}
 if(op.kind==='place'){placed.value=[...new Set([...placed.value,op.side])];inspectText.value=op.side==='right'?'韩伯：这边齐了。另一边也照着摆？':'韩伯：两旁都齐了，我来系牢。';return}
 if(op.kind==='drum'&&op.action==='sound'){playEffect('drum');return}
 if(op.kind==='collect'){playEffect('wood');inspectText.value=`已归筐 ${op.collected} / ${op.total} 束`;if(!op.complete)return;if(tallyContext.value){tallyReadyRoute.value=view.value.route_id;operationMode.value='';pending.value=null;tallyOpen.value=true;return}}
 const id=operationAction(view.value,op);if(id){if(op.kind==='drum')playEffect('drum');await mutate('actions',{action_id:id,params:{}})}else if(op.kind==='helm-confirm')inspectText.value='韩伯：这还是原来朝岸的一边。先看看另一侧的草束。'
}
function canAct(a:StoryAction){if(busy.value||beforeMotion.value||stageMoving.value||!dialogueDone.value||transitioning.value||stageError.value)return false;if(view.value?.node_id==='S2')return placed.value.includes('right')&&(a.id==='S2.one'||placed.value.includes('left'));return true}
async function express(){if(!text.value.trim()||!view.value)return;const a=pending.value;const value=text.value.trim();if(expressionReceipt?.route!==view.value.route_id||expressionReceipt?.text!==value){const saved=await mutate('expressions',{text:value,kind:expressionKind.value});if(!saved)return;expressionReceipt={route:view.value.route_id,text:value}}if(a){const advanced=await mutate('actions',{action_id:a.id,params:{text:value}});if(!advanced)return}else inspectText.value='阿成点点头，把你刚才的话记在船簿边。';expressionReceipt=null;text.value='';drawer.value='';await nextTick();readLine(false)}
function reflect(){expressionReceipt=null;pending.value=null;expressionKind.value='reflection';text.value='';open('expression')}
function help(){helpSpeaker.value=view.value?.role==='C'?'哨长':'沈砚';helpText.value='';open('help')}
async function getHelp(level:string){const v=await mutate('help',{level});if(v){helpText.value=typeof v.help==='string'?v.help:v.help?.text??v.help?.message??'';helpSpeaker.value=v.help?.speaker??helpSpeaker.value}}
async function showReview(){if(!view.value||busy.value)return;busy.value=true;try{const [r,list]=await Promise.all([request(`/api/s11/routes/${view.value.route_id}/review`),request(`/api/s11/sessions/${view.value.session_id}/routes`)]);review.value=r;routes.value=list.routes??[];selectedSnapshot.value=replayMemories(r.snapshots??[]).find(s=>s.node_id==='S8')?.id??r.snapshots?.filter((s:any)=>s.can_fork!==false).at(-1)?.id??'';forkRole.value=view.value.role==='L'?'Z':view.value.role;open('review')}catch(e){failure(e)}finally{busy.value=false}}
async function fork(){if(!selectedSnapshot.value)return;const v=await mutate('forks',{snapshot_id:selectedSnapshot.value,role:forkRole.value});if(v){drawer.value='';page.value='story';await nextTick();readLine(false)}}
async function switchRoute(id:string){if(busy.value)return;busy.value=true;try{await adopt(await request(`/api/s11/routes/${id}`),true);drawer.value='';await nextTick();readLine(false)}catch(e){failure(e)}finally{busy.value=false}}
async function newStory(){
 // Role selection is local and immediate. Optional replay presets must not block it.
 page.value='roles';drawer.value='';operationMode.value='';pending.value=null;beforeMotion.value=null;heldVisual.value=null;afterMotion=null;stageMoving.value=false;shipTask.value=null;tallyOpen.value=false;exam.value=false;error.value='';scenario.value='standard';role.value='L';mode.value='individual';names.value='';replay.value=!!view.value;scenarios.value=[];
 try{const c=await request('/api/s11/catalog?replay=true');scenarios.value=c.scenarios??[]}catch{scenarios.value=[]}
}
async function refresh(){if(!view.value)return;try{const value=await request(`/api/s11/routes/${view.value.route_id}`);const reset=!!stageError.value||stageMoving.value;afterMotion=null;stageMoving.value=false;if(reset)stageInstance.value++;await adopt(value,true);error.value=''}catch(e){failure(e)}}
async function fullscreen(){try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen()}catch{notify('请使用浏览器的全屏按钮。')}}
async function startSound(){
 if(soundStarting.value)return;soundStarting.value=true;soundOptedOut=false;
 try{if(!ambience){
  ambience=new AudioContext();master=ambience.createGain();master.gain.value=.16;master.connect(ambience.destination);
  const b=ambience.createBuffer(2,ambience.sampleRate*14,ambience.sampleRate);
  for(let channel=0;channel<2;channel++){const d=b.getChannelData(channel);let low=0;for(let i=0;i<d.length;i++){const t=i/ambience.sampleRate,n=Math.random()*2-1;low=low*.97+n*.03;const swell=.35+.65*Math.pow(.5+.5*Math.sin(t*Math.PI*2/3.5+channel*.8),2);const lap=Math.pow(Math.max(0,Math.sin(t*Math.PI*2/1.75+channel*.4)),8);const seam=Math.min(1,i/180,(d.length-1-i)/180);d[i]=(low*swell*.8+n*lap*.025)*seam}}
  wind=ambience.createBufferSource();wind.buffer=b;wind.loop=true;const filter=ambience.createBiquadFilter();filter.type='lowpass';filter.frequency.value=1700;wind.connect(filter);filter.connect(master);wind.start();
 }await ambience.resume();sound.value=ambience.state==='running';if(!sound.value)notify('请再点一次“环境声效”开启水声。')
 }catch{notify('环境声效暂不可用，字幕和操作仍可继续。')}finally{soundStarting.value=false}
}
function stopSound(){soundOptedOut=true;sound.value=false;void ambience?.suspend()}
function coverSoundGesture(event:Event){if(page.value!=='cover'||sound.value||soundOptedOut)return;const target=event.target as HTMLElement;if(target.closest('button,a,input,select'))return;void startSound()}
function playEffect(kind:string){if(!sound.value||!ambience||!master)return;const ctx=ambience;const o=ctx.createOscillator(),g=ctx.createGain(),t=ctx.currentTime;o.frequency.setValueAtTime(kind==='drum'?130:kind==='wood'?450:1300,t);o.frequency.exponentialRampToValueAtTime(kind==='drum'?40:180,t+.24);g.gain.setValueAtTime(.01,t);g.gain.exponentialRampToValueAtTime(kind==='drum'?1.4:.15,t+.015);g.gain.exponentialRampToValueAtTime(.001,t+.35);o.connect(g);g.connect(master);o.start();o.stop(t+.4)}
function onKey(e:KeyboardEvent){if(e.key==='Escape'){if(drawer.value)close();else if(operationMode.value){operationMode.value='';pending.value=null}}if((e.key==='Enter'||e.key===' ')&&!drawer.value&&!['INPUT','TEXTAREA','BUTTON','SELECT','CANVAS'].includes((e.target as HTMLElement)?.tagName??'')&&['story','prologue'].includes(page.value)&&(!dialogueDone.value||!!beforeMotion.value||page.value==='prologue')){e.preventDefault();nextLine()}}
onMounted(async()=>{document.addEventListener('keydown',onKey);reduced.value=matchMedia('(prefers-reduced-motion: reduce)').matches;try{auth.value=stored('caocuan:auth')??'';if(auth.value){try{user.value=(await request('/api/auth/me')).user;await restore()}catch{auth.value='';user.value=null}}}finally{booting.value=false}})
onBeforeUnmount(()=>{document.removeEventListener('keydown',onKey);clearInterval(typeTimer);[cutTimer,noticeTimer,rainTimer].forEach(clearTimeout);wind?.stop();ambience?.close();narrator.stop()})
</script>

<template>
<main class="s11-film" @click="coverSoundGesture" :class="[`is-${page}`,{'is-operation':!!operationMode,'is-ending':ended,'reduced-motion':reduced,'has-speaker':(page==='prologue'&&actorVisible)||(page==='story'&&nearSpeaker&&!operationMode&&!stageMoving)}]">
 <HarborCover v-if="page==='cover'" :reduced-motion="reduced"/><div v-else class="s11-world" :key="backdrop" :style="{backgroundImage:`url(${backdrop})`}"></div><div class="s11-vignette"></div><div class="s11-waterlight"></div><div v-if="page!=='prologue'&&visual.weather!=='clear'" class="s11-fog"></div>
 <header class="s11-header"><button class="s11-mark" @click="page='cover'">草船借箭<span>三日之约</span></button><p v-if="page==='story'">{{chapter}}</p><nav aria-label="观看设置"><button @click="toggleVoice" :aria-pressed="voice">人物对白 · {{voice?'开':'关'}}</button><button @click="sound?stopSound():startSound()" :aria-pressed="sound" :disabled="soundStarting">环境声效 · {{soundStarting?'开启中':sound?'开':'关'}}</button><button @click="fullscreen">全屏</button><button @click="open('settings')">设置</button></nav></header>
 <div v-if="error" class="s11-error" role="alert">{{error}} <button v-if="view" @click="refresh">重新连接</button><button @click="error=''" aria-label="关闭">×</button></div><div v-if="notice" class="s11-notice" role="status">{{notice}}</div>
 <section v-if="page==='cover'" class="s11-cover"><p class="s11-overline">一江雾起 · 两岸人心</p><h1>草船<span>借箭</span></h1><div class="s11-seal">三日之约</div><p class="s11-cover-story">十万支箭，三日期限。<br/>随船入雾，亲历这一夜。</p><button class="s11-gold s11-enter" :disabled="booting" @click="enter">{{booting?'稍候':user?.role==='teacher'?'进入教师工作台':'进入新的故事'}} <span>⟶</span></button><button v-if="user?.role==='student'&&view" class="s11-text" @click="resumeStory">回到上次进度</button><footer>取材《三国演义》第四十六回</footer></section>
 <section v-if="page==='login'" class="s11-login"><p class="s11-overline">入席</p><h1>先留下你的名字</h1><p>用老师分发的账号进入，故事与答卷会记在你的名下。</p><form @submit.prevent="login"><label>学号 / 教师号<input v-model="loginId" required autocomplete="username" /></label><label>密码<input v-model="password" required type="password" autocomplete="current-password" /></label><button class="s11-gold" :disabled="busy">{{busy?'正在入席':'进入'}} ⟶</button></form><button class="s11-text" @click="page='cover'">返回江边</button></section>
 <template v-if="page==='prologue'"><div class="s11-location">赤壁大战前 · 江东军营</div><CinematicActor v-if="actorVisible" :key="current.speaker" :name="current.speaker"/><button class="s11-skip" @click="page='roles'">跳过开场</button></template>
 <section v-if="page==='roles'" class="s11-casting"><p class="s11-overline">同一夜，从你所在的地方开始</p><h1>这一次，你是谁？</h1><div class="s11-role-line"><button v-for="(name,id) in ROLE_NAMES" :key="id" :class="{chosen:role===id}" @click="role=id"><CinematicActor :name="name"/><div><strong>{{name}}</strong><p>{{ROLE_PROMISES[id]}}</p></div></button></div><div class="s11-cast-bottom"><label>同行方式<select v-model="mode"><option value="individual">独自体验</option><option value="group">同桌共演</option></select></label><label v-if="mode==='group'">同伴姓名<input v-model="names" placeholder="用逗号分隔" /></label><label v-if="replay&&scenarios.length">再走一种处境<select v-model="scenario"><option v-for="s in availableScenarios" :key="s.id" :value="s.id">{{s.title??s.name??s.id}}</option></select></label><button class="s11-gold" :disabled="busy" @click="start">{{busy?'稍候':'随'+ROLE_NAMES[role]+'入场'}} ⟶</button></div></section>
 <template v-if="page==='story'&&view">
  <SceneStage v-if="showStage" :key="`${view.route_id}:${stageInstance}`" v-bind="visual" :backdrop="backdrop" :layout="stageLayout" :target-heading="visual.side==='left'?180:0" :perspective="view.role==='C'?'shore':'ship'" :enemy-visible="view.node_id!=='C0'" :scout-approaching="!!view.visual.scout_approaching" :mode="effectiveMode" :busy="busy||!!beforeMotion||stageMoving||!!shipTask||!dialogueDone||transitioning" :reduced-motion="reduced" @operate="operate" @motion="motion" @error="stageError=$event" />
  <div v-if="!operationMode" class="s11-scene-label"><span>{{ROLE_NAMES[view.role]}}视角</span><h1>{{stageMoving?(visual.side==='left'?'各船转舷':'箭雨入雾'):(view.node_id==='S12'&&view.visual.scout_approaching?view.title:screenTitle(view.node_id,view.title))}}</h1></div><CinematicActor v-if="nearSpeaker&&!operationMode&&!stageMoving" :key="speaking" :name="speaking"/>
  <div v-if="riverCue&&dialogueDone&&!beforeMotion&&!operationMode&&!drawer&&!ended" class="s13-river-cue" :class="riverCue.position"><button :disabled="busy||stageMoving||transitioning" @click="observeRiver" :aria-label="riverCue.label"><i aria-hidden="true"></i><span>{{riverCue.label}}</span></button><p v-if="cueText" role="status">{{cueText}}<button @click="cueText='';narrator.stop()" aria-label="收起观察">×</button></p></div>
  <div v-if="rain" class="s11-rain" aria-hidden="true"><i v-for="i in 28" :key="i" :style="{left:`${i*3.6}%`,animationDelay:`${i%7*.08}s`}"></i></div>
  <div v-if="stageError" class="s11-stage-failure" role="alert">{{stageError}}<button @click="refresh">重新载入场景</button></div><div v-if="inspectText&&dialogueDone" class="s11-object-speech" role="status">{{inspectText}}</div>
  <aside v-if="view.node_id==='COUNT1'&&dialogueDone&&!operationMode" class="s11-tally" aria-label="各船送来的箭簿"><h2>各船的点数送来了</h2><dl><div><dt>右舷所得</dt><dd>{{Number(view.visual.first??0).toLocaleString()}} 支</dd></div><div><dt>左舷所得</dt><dd>{{Number(view.visual.second??0).toLocaleString()}} 支</dd></div><div><dt>已经回射</dt><dd>{{Number(view.visual.spent??0).toLocaleString()}} 支</dd></div><div><dt>受损另放</dt><dd>{{Number(view.visual.loss??0).toLocaleString()}} 支</dd></div></dl><p>沈砚：可用的交都督，别把发出的和受损的算进去。</p></aside>
  <div v-if="dialogueDone&&!beforeMotion&&!ended&&!operationMode" class="s11-decisions" aria-label="眼前的行动"><p v-if="view.node_id==='S2'">在船上选中放置处，再请韩伯系牢。</p><button v-for="(a,i) in actions" :key="a.id" :disabled="!canAct(a)" @click="act(a)"><span class="s11-decision-mark">{{i+1}}</span>{{a.label}}<span class="s11-arrow">⟶</span></button></div>
  <button v-if="operationMode&&!busy" class="s11-operation-back" @click="operationMode='';pending=null;inspectText=''">← 回到船边商议</button>
  <div v-if="ended&&dialogueDone" class="s11-ending-choices"><p>{{view.ending?.title??''}}</p><button class="s11-gold" @click="exam=true">完成课题测试 ⟶</button><button class="s11-text" @click="showReview">回看一次决定</button><button class="s11-text" @click="newStory">再赴这一夜</button></div>
  <footer class="s11-story-footer"><span>{{activeActor}}<template v-if="view.members.length>1"> · <select :value="view.controller_id" aria-label="交给同伴" :disabled="busy" @change="mutate('control',{controller_id:($event.target as HTMLSelectElement).value})"><option v-for="m in view.members" :key="m.id" :value="m.id">{{m.name}}</option></select></template></span><nav><button v-if="['S15','S16','S17','COUNT1'].includes(view.node_id)" @click="reflect">{{view.node_id==='COUNT1'?'报清箭数':'低声告诉同伴'}}</button><button @click="showReview">回看</button><button @click="help">{{view.role==='C'?'问哨长':'请教沈砚'}}</button></nav></footer>
 </template>
 <section v-if="['prologue','story'].includes(page)&&lines.length&&(!operationMode||!dialogueDone)" class="s11-dialogue" :class="{compact:!!operationMode}" aria-label="人物对白"><div><span>{{current.speaker}}</span><button v-if="voice" @click="readLine(true)" aria-label="重听当前对白">重听</button><small v-if="voiceStatus==='speaking'" class="s13-speaking" aria-label="对白播放中">•••</small><small v-if="voiceStatus==='unavailable'">可阅读字幕</small></div><button class="s11-line" @click="nextLine"><span>{{typed}}</span><small>{{revealed<current.text.length?'点击显全文':lineIndex<lines.length-1||beforeMotion||page==='prologue'?'继续 ▸':' '}}</small></button></section>
 <div v-if="transitioning" class="s11-cut" aria-hidden="true"><span>{{transitionLabel}}</span></div>
 <div v-if="drawer" class="s11-overlay" @click.self="close"><section class="s11-modal" role="dialog" aria-modal="true"><button class="s11-close" :disabled="busy" @click="close" aria-label="关闭窗口">×</button>
  <template v-if="drawer==='settings'"><h2 tabindex="-1">观看设置</h2><label class="s11-check"><input type="checkbox" v-model="voice"/>人物对白朗读</label><label class="s11-check"><input type="checkbox" v-model="reduced"/>减少镜头动效</label><p>人物和场景为原创制作，故事取材《三国演义》，分支为教学改编。箭数用于本课件情境，不作历史战况数据。当前人物帮助来自已编写的剧本；DeepSeek实时对话尚未启用。环境声及操作拟音由本机合成，系统朗读为可选；尚无专业角色配音。</p><p v-if="user?.demo">当前为演示账号，记录用于软件体验。</p><button v-if="user" class="s11-text" @click="logout">退出 {{user.name}} 的账号</button><button v-if="user?.role==='teacher'" class="s11-gold" @click="drawer='';teacher=true">打开教师工作台</button></template>
  <template v-else-if="drawer==='expression'"><h2 tabindex="-1">{{expressionTitle}}</h2><p>{{expressionPrompt}}</p><blockquote v-if="expressionKind==='utterance'&&view?.old_utterances?.length">{{view.old_utterances.at(-1)?.text??view.old_utterances.at(-1)}}</blockquote><textarea v-model="text" rows="4" maxlength="1200" :aria-label="expressionTitle"></textarea><button class="s11-gold" :disabled="busy||!text.trim()" @click="express">{{expressionKind==='reflection'?'说给同伴听':view?.role==='Z'?'说给鲁肃听':'说给孔明听'}}</button><button class="s11-text" @click="close">再看看船边</button></template>
  <template v-else-if="drawer==='help'"><h2 tabindex="-1">{{helpSpeaker}}</h2><div class="s11-help-actions"><button v-for="q in helpChoices" :key="q.level" :disabled="busy" @click="getHelp(q.level)">{{q.label}}</button></div><blockquote v-if="helpText">{{helpText}}</blockquote></template>
  <template v-else-if="drawer==='review'"><h2 tabindex="-1">重回那一刻</h2><p>从走过的场景再作一次决定，原来的故事会留下。</p><div class="s11-memories"><label v-for="s in latestSnapshots" :key="s.id" :class="{selected:selectedSnapshot===s.id}"><input type="radio" v-model="selectedSnapshot" :value="s.id"/><span>{{screenTitle(s.node_id,s.title??s.node_id)}}</span><small>{{s.summary??''}}</small></label></div><details v-if="allSnapshots.length>3"><summary>其他走过的场景</summary><label v-for="s in allSnapshots" :key="s.id"><input type="radio" v-model="selectedSnapshot" :value="s.id"/> {{screenTitle(s.node_id,s.title??s.node_id)}}</label></details><p v-if="view?.role==='L' &amp;&amp; forkRole==='Z' &amp;&amp; allSnapshots.find(s=>s.id===selectedSnapshot)?.node_id==='S8'">旧问重答 · 新情况：把你当时的担心交给这一次的自己。</p><label>这次由谁回应<select v-model="forkRole"><option v-for="(name,id) in ROLE_NAMES" :key="id" :value="id">{{name}}</option></select></label><button class="s11-gold" :disabled="busy||!selectedSnapshot" @click="fork">回到这一刻</button><details><summary>已留下的故事</summary><button v-for="r in routes" :key="r.id" class="s11-route" :disabled="busy||r.id===view?.route_id" @click="switchRoute(r.id)">{{ROLE_NAMES[r.role as 'L'|'Z'|'C']??r.role}} · {{r.status==='ended'?'已走到结尾':'进行中'}}</button></details></template>
 </section></div>
 <ShipTasks v-if="shipTask&&shipContext" :task="shipTask" :context="{...shipContext,reducedMotion:reduced}" :busy="busy" :error="error" @progress="saveTask" @complete="completeTask" @close="closeTask"/>
 <TallyTask v-if="page==='story'&&tallyOpen&&tallyContext&&view" :key="`${view.route_id}:${view.controller_id}`" :identity="`${view.route_id}:${view.controller_id}`" :context="tallyContext" :busy="busy" :error="error" @answer="answerTally" @finish="finishTally" @close="tallyOpen=false"/>
 <ExamPanel v-if="exam&&user" :request="request" :user-id="user.user_id" @close="exam=false"/><TeacherPanel v-if="teacher&&user?.role==='teacher'" :request="request" @close="teacher=false"/>
</main>
</template>





