<script setup lang="ts">
import {computed,nextTick,onBeforeUnmount,onMounted,ref,watch} from 'vue'
import {Api,ApiError} from '../api'
import {Narration} from '../narration'
import {courseVoicePort} from './voice'
import ExamPanel from '../components/ExamPanel.vue'
import TeacherPanel from '../components/TeacherPanel.vue'
import V1Atmosphere from './V1Atmosphere.vue'
import V1Boat from './V1Boat.vue'
import './v1.css'
import SceneBackdrop from '../v11/SceneBackdrop.vue'
import Barrage from '../v11/Barrage.vue'
import BattleBarrage from '../v16/BattleBarrage.vue'
import SceneMotion from '../v16/SceneMotion.vue'
import BoatWorkshop from '../v12/BoatWorkshop.vue'
import SignalRelay from '../v12/SignalRelay.vue'
import NavSignal from '../v15/NavSignal.vue'
import {verifySignal} from '../v15/signal'
import '../v15/v15.css'
import DrumStage from '../v12/DrumStage.vue'
import RiverManeuver from '../v12/RiverManeuver.vue'
import ObservationStage from '../v12/ObservationStage.vue'
import MusterStage from '../v13/MusterStage.vue'
import ArrowTallyStage from '../v14/ArrowTallyStage.vue'
import {verifyTally,type TallyContext} from '../v14/tally'
import {shotFor,nextShots} from '../v16/shots'
import {previousSnapshot,nextSnapshot,musterPayload,afterVolleyArt} from '../v13/journey'
import {EMPTY_ASSEMBLY,type Assembly} from '../v12/workshopModel'
import {activityFor,selectionPayload,operationProblem,type Choice} from '../v12/experience'
import {Soundscape} from '../v11/soundscape'
import '../v11/v11.css'
import '../v12/v12.css'
import '../v13/v13.css'
import '../v14/v14.css'
type Person={name:string;account_id:string|null}
type Beat={battle?:{phase: "warning"|"first"|"second";view:"deck"|"north"};ship_load?:{port:number;starboard:number};signal_context?:string;design_version?:string;tally?:TallyContext;afterstory_note?:string;cargo?:{arrows:number;departed:boolean;peril:boolean};node:string;title:string;act:string;art:string;interaction:string;prompt:string;lines:{speaker:string;text:string}[];actions:{id:string;label:string}[];ending:string|null;role:string;weather:string;guide_text?:string;scenario_label?:string;scenario_brief?:string;choices?:Choice[];outcome?:{title:string;summary:string;bank:string;lesson:string;closing:string;other_bank:string};assembly?:Assembly;result?:{arrows:number;boats:number;peril:boolean;reason:string}}
type Run={id:string;revision:number;scene:Beat;members:Person[];snapshots:{index:number;title:string;node:string}[];history:any[];status:string;question:string;old_question:string;feedback?:string;assembly?:Assembly;design_version?:string}
const previewRun=ref<Run|null>(null),previewIndex=ref<number|null>(null),liveLine=ref(0),historyPrelude=ref(false)
let previewGeneration=0
const page=ref('cover'),auth=ref(localStorage.getItem('v1:auth')||''),user=ref<any>(null),run=ref<Run|null>(null),lineIndex=ref(0),intro=ref(0),role=ref('L'),scenario=ref('mist'),members=ref(''),actor=ref(0)
const browserEdition=import.meta.env.VITE_LST_BROWSER==='1'
const busy=ref(false),error=ref(''),loginId=ref(browserEdition?'S001':''),password=ref(''),exam=ref(false),teacher=ref(false),review=ref(false),settings=ref(false),inspecting=ref(false),voice=ref(true),ambience=ref(false),motion=ref(!matchMedia('(prefers-reduced-motion: reduce)').matches)
const drumVolume=ref(.85)
const music=ref(true),volleyFinished=ref(true),backdropReady=ref(false),backdropFailed=ref(false),maneuver=ref<'balance'|'rudder'|undefined>(),pan=ref(50)
const operationAuthors=ref<Record<string,number>>({}),assemblyAuthors=ref<Record<string,number>>({})
const activity=ref<string|null>(null),assembly=ref<Assembly>({...EMPTY_ASSEMBLY}),pairMode=ref(false),chosenReply=ref(''),ownThought=ref(false),guide=ref(false),riverX=ref(0),signalMessage=ref(''),operationDone=ref(false),activityDraft=ref<Record<string,any>>({})
const activityDialog=ref<HTMLDivElement>()
let activityReturnFocus:HTMLElement|null=null
watch(activity,async (active,previous)=>{
 if(active&&!previous)activityReturnFocus=document.activeElement instanceof HTMLElement?document.activeElement:null
 await nextTick()
 if(activity.value!==active)return
 if(active)activityDialog.value?.querySelector<HTMLButtonElement>('.activity-close')?.focus()
 else if(previous){const target=activityReturnFocus?.isConnected?activityReturnFocus:document.querySelector<HTMLElement>('.v12-action-invite');target?.focus();activityReturnFocus=null}
})
function trapActivityFocus(event:KeyboardEvent){
 if(event.key!=='Tab'||!activityDialog.value)return
 const controls=Array.from(activityDialog.value.querySelectorAll<HTMLElement>('button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')).filter(el=>!el.matches(':disabled')&&el.tabIndex>=0&&el.getClientRects().length>0)
 event.preventDefault()
 const index=controls.indexOf(document.activeElement as HTMLElement)
 const next=index<0?(event.shiftKey?controls.length-1:0):(index+(event.shiftKey?-1:1)+controls.length)%controls.length
 const target=controls[next]||activityDialog.value
 target.focus()
}
const scenarios=[{id:'mist',name:'雾夜初航',detail:'浓雾遮江，曹军弓弩已备。鼓响以后，对岸会怎样判断？',image:'harbor'}, {id:'quiet',name:'寨门无声',detail:'曹军闭寨不应。船队等不到箭，要另想办法，还是收兵？',image:'silent-gate'}, {id:'scout',name:'哨艇出寨',detail:'一支哨艇即将离寨。远远打探，还是逐渐逼近草船？',image:'scout'}, {id:'clear',name:'月下无雾',detail:'江面看得分明，草把难以藏身。计策还照原样走吗？',image:'clear-river'}]
const activeScenario=computed(()=>scenarios.find(x=>x.id===scenario.value)!)
const guideCopy:Record<string,string>={inspect:'船还没布置。先把草把挂到两舷，再盖青布，挪开舱中的货箱。你装上的东西，会留在这条船上。',signals:'归队令不能只喊一声。先送前船，听清复号，再交后船，最后由领船确认。传错了，停下来重传。',position:'把领船停在警戒线外，给整队留下转身的水面。点江面选落点，也可以直接拖船。',rescue:'末船落在右后方。把领船带回它的外侧，靠近后再发接应令，别独自往前走。',command:'把哨艇派到看得清、退得回的位置。追得太深，寨门就离你越来越远。',drum:'登上船艏，敲三声鼓。鼓声是传令，也会让对岸作出回应；江上情境不同，回应就不同。',expression:'眼前的人在等你答复。挑一句最接近你想法的话，直接对他说；愿意的话，也能再补充一句。',reflection:'挑出今晚最该说明的一件事。选项上写着要对谁说；愿意的话，也可以留下自己的想法。',balance:'先让这一阵箭过去，再握住船身慢慢转过来。满箭的一舷背向曹寨，空着的一舷接过去。',rudder:'拿到箭还不算完。拖转领船，对准返程水道，后船才知道往哪里跟。'}
const guideText=computed(()=>s.value?.guide_text||guideCopy[s.value?.interaction||'']||'先看江面上的船和寨灯，再听人物说了什么。每一道号令都会留下一条后果；想试另一条路，可以回望这一夜。')
const activityLabel=computed(()=>({inspect:'登船布置',signals:'传递归队令',nav_signal:'执掌鼓灯，向船队传令',position:'到江面上布阵',rescue:'驾船接应',command:'派出哨艇',look:'登高察看',listen:'循声察看江面',drum:'登上鼓台',muster:'登岸点验人船',arrow_tally:'到岸边取箭核数'} as Record<string,string>)[s.value?.interaction||''])
const selectedChoice=computed(()=>s.value?.choices?.find(x=>x.id===chosenReply.value))
const visibleActions=computed(()=>s.value?.interaction==='nav_signal'?(operationDone.value?(s.value.actions||[]).filter(a=>a.id===activityDraft.value.nav_signal?.command):[]):s.value?.choices?.length?[]:s.value?.actions||[])
const soundscape=new Soundscape()
const voiceStatus=ref('idle'),expression=ref(''),help=ref(''),progress=ref<string[]>([]),knob=ref(50),beats=ref(0),look=ref(50),count=ref(''),savedRuns=ref<any[]>([])
const api=new Api(()=>auth.value,()=>null),request=(p:string,m='GET',b?:unknown)=>api.request<any>(p,m,b)
const narration=new Narration(courseVoicePort(),s=>{voiceStatus.value=s;soundscape.duck(s==='speaking'||s==='starting')})
const prologue=[
 {speaker:'旁白',text:'建安十三年，曹操率军南下。江北是曹军水寨；江南，孙权与刘备决定联手抗曹。隔着这条江，两军都在打量对方。'},
 {speaker:'旁白',text:'诸葛亮代表刘备来到东吴，鲁肃居中联络，周瑜统率东吴水军。这三人同在抗曹的一方，却各有心思。曹操，则要守住江北的水寨。'},
 {speaker:'旁白',text:'《三国演义》在这一背景中，写下了另一场较量：周瑜限诸葛亮造十万支箭，诸葛亮却把期限缩成三日。'},
 {speaker:'诸葛亮',text:'第三日，请都督派五百军士到江边搬箭。'},
 {speaker:'旁白',text:'三天过去，江上起了变化。南岸的船正在解缆，北岸的守军尚不知情。你愿随谁走进这一夜？'}]
const s=computed(()=>previewRun.value?.scene||run.value?.scene),lines=computed(()=>page.value==='prologue'?prologue:s.value?.lines||[]),current=computed(()=>lines.value[page.value==='prologue'?intro.value:lineIndex.value]),ready=computed(()=>!!s.value&&lineIndex.value>=s.value.lines.length-1)
const art=computed(()=>page.value==='cover'?'harbor':page.value==='prologue'?'council':page.value==='roles'?activeScenario.value.image:s.value?.art||'harbor')
const artFile=computed(()=>page.value==='story'&&s.value?.weather==='clear'&&['harbor','deck','lookout','scout'].includes(art.value)?(s.value.role==='C'?'clear-lookout':'clear-river'):art.value)
const backdrop=computed(()=>{const node=s.value?.node;if(page.value==='story'&&run.value?.design_version==='V1.6'&&s.value){if(s.value.battle&&!volleyFinished.value&&!previewRun.value)return './v16/'+(s.value.battle.phase==='warning'?(s.value.weather==='clear'?'arrows_clear':'rain_warning'):(s.value.battle.phase==='second'?'second':'arrows')+(s.value.weather==='clear'?'_clear':''))+'.webp';if(['arrows','second'].includes(node||''))return './v16/'+node+'_after.webp';const image=shotFor(s.value);if(image)return './'+image+'.webp'}if(page.value==='story'&&['V1.4','V1.5','V1.6'].includes(run.value?.design_version||'')&&s.value){if(['arrows','second'].includes(node||'')&&!volleyFinished.value&&!previewRun.value)return node==='second'?'./v11/volley-starboard.webp':'./v11/volley-port.webp';const shot=shotFor(s.value);if(shot)return './'+shot+'.webp'}if(page.value==='story'&&['arrows','second'].includes(node||'')){if(!volleyFinished.value&&!previewRun.value)return node==='second'?'./v11/volley-starboard.webp':'./v11/volley-port.webp';return afterVolleyArt(node!,true)!}if(page.value==='story'&&s.value?.art.startsWith('v13/'))return './'+s.value.art+'.webp';const aftermath=page.value==='story'?afterVolleyArt(s.value?.node||'',volleyFinished.value):null;if(aftermath)return aftermath;if(page.value==='prologue'&&intro.value<2)return './v12/banks-map.webp';const n=s.value?.node;if(page.value==='story'){
 if(n==='done'){const ending=s.value?.ending;return ending==='E0'?'./v12/banks-map.webp':ending==='E1'?'./v12/ending-empty.webp':ending==='E2'?'./v12/ending-half.webp':ending==='E3'?'./v12/ending-full.webp':'./v12/ending-rescue.webp'}
 if(n==='arrows'||n==='side_check')return './v11/volley-port.webp'
 if(n==='second')return './v11/volley-starboard.webp'
 if(['silence','silence_again','disagree'].includes(n||''))return './v11/silent-gate.webp'
 if(['scout','late_rescue'].includes(n||'')&&s.value?.weather!=='clear')return './v11/river-rescue.webp'
 if(n==='return'&&s.value?.art==='dawn')return './v11/return-fleet.webp'
 if(['C_shoot','C_recognize'].includes(n||''))return './v11/north-bowline.webp'
 }return `./v11/${artFile.value}.webp`})
const hasVolleys=computed(()=>!previewRun.value&&page.value==='story'&&(run.value?.design_version==='V1.6'?!!s.value?.battle:['arrows','second'].includes(s.value?.node||'')))
const canOperate=computed(()=>!previewRun.value&&ready.value&&(backdropReady.value||backdropFailed.value)&&(!hasVolleys.value||volleyFinished.value||backdropFailed.value))
function portraitUrl(name:string){return name==='guide-cenzhou'?'./v12/guide-cenzhou.webp':`./v11/${name}.webp`}
watch(backdrop,()=>{backdropReady.value=false;backdropFailed.value=false})
const warmedShots=new Set<string>()
watch(()=>s.value?.node,()=>{if(!['V1.4','V1.5','V1.6'].includes(run.value?.design_version||'')||!s.value)return;for(const file of nextShots(s.value)){if(warmedShots.has(file))continue;const im=new Image();im.src='./'+file+'.webp';im.decode().then(()=>warmedShots.add(file)).catch(()=>{})}})
const roleNames:Record<string,string>={L:'鲁肃',Z:'诸葛亮',C:'曹操'}
const speakerImage=computed(()=>({'旁白':'guide-cenzhou','岑舟':'guide-cenzhou','鲁肃':'portrait-L','诸葛亮':'portrait-Z','曹操':'portrait-C','韩伯':'speaker-hanbo','周瑜':'speaker-zhouyu'} as Record<string,string>)[current.value?.speaker||''])
const roleCopy:Record<string,string>={L:'船是你借的。人，也要由你照应回来。',Z:'三日之期已定。计策要能进，也要能退。',C:'鼓声到了寨外。守住眼前，还是抢先出手？'}
const localKey=computed(()=>`v1:run:${user.value?.user_id||''}`)
const canResume=computed(()=>!!user.value&&(!!run.value||!!localStorage.getItem(localKey.value)))
const draftKey=computed(()=>`v1:draft:${user.value?.user_id}:${run.value?.id}:${s.value?.node}:${actor.value}`)
function saveDraft(){localStorage.setItem(draftKey.value,expression.value)}
function loadDraft(){expression.value=localStorage.getItem(draftKey.value)||''}
const controlLabels=computed(()=>({position:['外侧回转线','寨口深处',knob.value<=65?'仍在回转线内':'已越过警戒线'],balance:['原舷朝寨','另一舷朝寨',knob.value>=80?'另一舷已转过来':'船头尚未转足'],rudder:['返程水道','曹寨方向',knob.value<=35?'船头已收回返程线':'仍朝着寨口'],rescue:['前船','末船外侧',knob.value>=65?'能够接应末船':'还离末船太远'],command:['寨前水道','深水追线',knob.value<=65?'没有越过警戒水线':'已越过不可追击的界线']} as Record<string,string[]>)[s.value?.interaction||'position']||['近','远',''])
function sound(){soundscape.set(music.value,ambience.value)}
function drum(){soundscape.setDrumVolume(drumVolume.value);soundscape.drum()}
function musterVoice(text:string){if(voice.value)narration.play('muster:'+text,text,true,'韩伯')}
function openActivity(){if(previewRun.value)return;guide.value=false;narration.stop();if(!s.value)return;if(['balance','rudder'].includes(s.value.interaction)){maneuver.value=s.value.interaction as 'balance'|'rudder';return}activity.value=['muster','arrow_tally','nav_signal'].includes(s.value.interaction)?s.value.interaction:activityFor(s.value.interaction);if(!activity.value){lineIndex.value=s.value.lines.length-1;ownThought.value=false}}
function assemblyChange(a:Assembly){for(const key of Object.keys(a) as (keyof Assembly)[])if(assembly.value[key]!==a[key])assemblyAuthors.value[key]=actor.value;assembly.value=a;if(run.value){localStorage.setItem(`v12:assembly:${run.value.id}`,JSON.stringify(a));localStorage.setItem(`v12:assembly-authors:${run.value.id}`,JSON.stringify(assemblyAuthors.value))}}
function saveOperation(){if(run.value&&s.value)localStorage.setItem(`v12:operation:${run.value.id}:${s.value.node}:${actor.value}`,JSON.stringify({progress:progress.value,signalMessage:signalMessage.value,beats:beats.value,knob:knob.value,riverX:riverX.value,done:operationDone.value,authors:operationAuthors.value,drafts:activityDraft.value}))}
function loadOperation(){try{const saved=JSON.parse(localStorage.getItem(`v12:operation:${run.value?.id}:${s.value?.node}:${actor.value}`)||'null');progress.value=saved?.progress||[];signalMessage.value=saved?.signalMessage||'';beats.value=saved?.beats||0;knob.value=saved?.knob??(s.value?.interaction==='rudder'?100:0);riverX.value=saved?.riverX||0;operationDone.value=saved?.done||false;activityDraft.value=saved?.drafts||{};operationAuthors.value=saved?.authors||{};assemblyAuthors.value=JSON.parse(localStorage.getItem(`v12:assembly-authors:${run.value?.id}`)||'{}')}catch{operationDone.value=false;activityDraft.value={}}}
function changeActor(){loadDraft();chosenReply.value='';ownThought.value=false;loadOperation()}
function saveActivity(data:any){if(!activity.value)return;activityDraft.value[activity.value]=data;if(activity.value==='signals'){progress.value=data.signal_order;signalMessage.value=data.signal_message}if(activity.value==='drum')beats.value=data.drum_signals;if(['position','command','rescue'].includes(activity.value)){knob.value=data.position;riverX.value=data.river_x}operationDone.value=false;saveOperation()}
function finishActivity(data?:any){narration.stop();if(activity.value&&data)activityDraft.value[activity.value]=data;if(activity.value)operationAuthors.value[activity.value]=actor.value;if(activity.value==='assembly'&&data)assemblyChange(data);if(activity.value==='signals'&&data){progress.value=data.signal_order;signalMessage.value=data.signal_message}if(activity.value==='drum'&&data)beats.value=data.drum_signals;if(['position','command','rescue'].includes(activity.value||'')&&data){knob.value=data.position;riverX.value=data.river_x}operationDone.value=true;saveOperation();activity.value=null}
async function reply(){const c=selectionPayload(s.value?.choices||[],chosenReply.value,ownThought.value?expression.value:'');if(!c.action){error.value='先选一句回应。';return}await act(c.action)}
const battlePlaying=computed(()=>run.value?.design_version==='V1.6'&&hasVolleys.value&&!volleyFinished.value&&!backdropFailed.value)
watch(battlePlaying,v=>{if(v)narration.stop();else speak()})
function speak(repeat=false){if(!battlePlaying.value&&current.value&&voice.value)narration.play(`${page.value}:${run.value?.id}:${s.value?.node}:${page.value==='prologue'?intro.value:lineIndex.value}`,current.value.text,repeat,current.value.speaker)}
watch(current,()=>{if(!guide.value&&!activity.value&&!maneuver.value)speak()});watch(voice,v=>{if(!v)narration.stop();else if(guide.value)narration.play(`guide:${s.value?.interaction}`,guideText.value,true,'岑舟');else if(!activity.value&&!maneuver.value)speak(true)});watch(ambience,sound);watch(music,sound)
async function advance(){if(page.value==='prologue'){if(intro.value<prologue.length-1)intro.value++;else if(historyPrelude.value)await returnToFirstScene();else page.value='roles'}else if(s.value&&lineIndex.value<s.value.lines.length-1)lineIndex.value++;else if(previewRun.value)await nextPreview()}
function adopt(data:Run){historyPrelude.value=false;previewGeneration++;previewRun.value=null;previewIndex.value=null;const changed=data.scene.node!==run.value?.scene.node||data.id!==run.value?.id;run.value=data;localStorage.setItem(localKey.value,data.id);actor.value=Math.min(actor.value,data.members.length-1);if(changed){narration.stop();lineIndex.value=0;loadDraft();help.value='';progress.value=[];beats.value=0;count.value='';knob.value=data.scene.interaction==='rudder'?100:0;riverX.value=0;signalMessage.value='';inspecting.value=false;activity.value=null;guide.value=false;chosenReply.value='';ownThought.value=false;operationDone.value=false;maneuver.value=undefined;volleyFinished.value=data.design_version==='V1.6'?!data.scene.battle:!['arrows','second'].includes(data.scene.node);pan.value=50;try{assembly.value=data.scene.assembly||data.assembly||JSON.parse(localStorage.getItem(`v12:assembly:${data.id}`)||'null')||{...EMPTY_ASSEMBLY}}catch{assembly.value={...EMPTY_ASSEMBLY}}loadOperation()}page.value='story';if(data.feedback)error.value=data.feedback}
async function guarded(fn:()=>Promise<void>){if(busy.value)return;busy.value=true;error.value='';try{await fn()}catch(e){error.value=(e as Error).message;if(e instanceof ApiError&&e.status===401){auth.value='';localStorage.removeItem('v1:auth');user.value=null;page.value='login'}}finally{busy.value=false}}
function begin(){historyPrelude.value=false;previewGeneration++;previewRun.value=null;previewIndex.value=null;narration.stop();intro.value=0;page.value='prologue';ambience.value=true;sound();speak()}
function entryPayload(){return {role:role.value,scenario:scenario.value,design_version:'V1.6',members:pairMode.value?members.value.split(/[，,]/).map(x=>x.trim()).filter(Boolean):[]}}
async function login(){await guarded(async()=>{const out=await request('/auth/login','POST',{user_id:loginId.value,password:password.value});auth.value=out.token;user.value=out.user;password.value='';localStorage.setItem('v1:auth',out.token);if(user.value.role==='teacher'){page.value='cover';teacher.value=true}else adopt(await request('/v1/runs','POST',entryPayload()))})}
async function start(){if(!user.value){page.value='login';return}await guarded(async()=>adopt(await request('/v1/runs','POST',entryPayload())))}
async function enter(){if(pairMode.value&&!members.value.trim()){error.value='请写下共同参与者的姓名，便于区分谁在作决定。';return}if(!user.value){page.value='login';return}await start()}
let pending:{key:string;body:any}|null=null
async function act(id:string){
 if(!run.value||!s.value||previewRun.value)return
 if(!canOperate.value){error.value='等这一阵箭过去，再传号。';return}
 if(id==='turn'&&knob.value<80){error.value='先握舵转船，让另一舷朝向曹寨。';return}
 if(s.value.interaction==='expression'&&!chosenReply.value&&!expression.value.trim()){error.value='选一句话，回应眼前的人。';return}
 const operation={nav_signal:activityDraft.value.nav_signal,assembly_contributors:assemblyAuthors.value,operation_authors:operationAuthors.value,assembly:assembly.value,signal_order:progress.value,signal_message:signalMessage.value,relay_errors:activityDraft.value.signals?.relay_errors||0,drum_signals:beats.value}
 if(s.value.interaction==='nav_signal'&&(!operationDone.value||!verifySignal(activityDraft.value.nav_signal))){error.value='先把这道号传到前后船，等它们复号。';return}
 const issue=operationProblem(s.value.interaction,operation);if(issue){error.value=issue;return}
 if(['signals','drum'].includes(s.value.interaction)&&!operationDone.value){error.value='这次操作还没有收束。回到工位确认当前安排，再传下一道令。';return}
 if((['position','command'].includes(s.value.interaction)||(s.value.interaction==='rescue'&&id==='rescue'))&&!operationDone.value){error.value='先把船带到你选的位置，再传令。';return}
 if(s.value.interaction==='count'&&Number(count.value)!==20){error.value='韩伯报的是前队十条、后队十条。请再清点一次。';return}
 if(s.value.interaction==='muster'&&(!operationDone.value||!musterPayload(activityDraft.value.muster||{}))){error.value='先听完前后两队的回报，核齐船牌。';return}
 const tallyCheck=s.value.tally?verifyTally(activityDraft.value.arrow_tally,s.value.tally):null;
 if(s.value.interaction==='arrow_tally'&&(!operationDone.value||!tallyCheck?.ok)){error.value=tallyCheck&&!tallyCheck.ok?tallyCheck.message:'先到岸边完成取箭与清点。';return}
 const selected=selectionPayload(s.value.choices||[],chosenReply.value,(ownThought.value||!s.value.choices?.length)?expression.value:'')
 const body={request_id:crypto.randomUUID(),revision:run.value.revision,action:id,actor:actor.value,payload:{...operation,...selected.payload,arrow_tally:tallyCheck?.ok?tallyCheck.proof:undefined,muster:musterPayload(activityDraft.value.muster||{}),interaction:s.value.interaction,position:knob.value,river_x:riverX.value,count:count.value}}
 const key=JSON.stringify({...body,request_id:''});if(!pending||pending.key!==key)pending={key,body}
 await guarded(async()=>{const result=await request(`/v1/runs/${run.value!.id}/actions`,'POST',pending!.body);pending=null;adopt(result)})
}
async function askHelp(){if(!run.value||previewRun.value)return;await guarded(async()=>{const d=await request(`/v1/runs/${run.value!.id}/actions`,'POST',{request_id:crypto.randomUUID(),revision:run.value!.revision,action:'help',actor:actor.value,payload:{}});adopt(d);guide.value=true;narration.stop();if(voice.value)narration.play(`guide:${s.value?.interaction}`,guideText.value,true,'岑舟')})}
async function restore(id?:string){const saved=id||localStorage.getItem(localKey.value);if(saved)await guarded(async()=>adopt(await request(`/v1/runs/${saved}`)))}
async function openReview(){await guarded(async()=>{savedRuns.value=(await request('/v1/runs')).routes;review.value=true})}
async function fork(index:number,role?:string){await guarded(async()=>{adopt(await request(`/v1/runs/${run.value!.id}/fork`,'POST',{snapshot:index,role:role||null}));review.value=false})}

// The cursor views immutable snapshots. Only explicit story actions or replay create progress.
const hasPrevious=computed(()=>page.value==='prologue'||page.value==='roles'||(page.value==='story'&&!!run.value))
const hasForward=computed(()=>!!previewRun.value&&page.value==='story'||historyPrelude.value&&page.value==='cover')
async function previewSnapshot(index:number){if(!run.value)return;await guarded(async()=>{const ticket=++previewGeneration,routeId=run.value!.id;const result=await request(`/v1/runs/${routeId}/snapshots/${index}`);if(ticket!==previewGeneration||run.value?.id!==routeId||page.value!=='story')return;if(!previewRun.value)liveLine.value=lineIndex.value;narration.stop();guide.value=false;activity.value=null;maneuver.value=undefined;previewRun.value=result;previewIndex.value=index;lineIndex.value=0})}
function resumePresent(){previewGeneration++;historyPrelude.value=false;narration.stop();previewRun.value=null;previewIndex.value=null;page.value='story';lineIndex.value=liveLine.value;loadDraft();loadOperation()}
async function returnToFirstScene(){
 if(!run.value)return;historyPrelude.value=false;page.value='story';
 if(run.value.snapshots.length===1){resumePresent();return}
 await previewSnapshot(run.value.snapshots[0].index)
}
async function previousScene(){
 if(page.value==='prologue'){narration.stop();if(intro.value>0)intro.value--;else page.value='cover';return}
 if(page.value==='roles'){intro.value=4;page.value='prologue';return}
 if(page.value!=='story'||!run.value)return;
 const index=previousSnapshot(run.value.snapshots,previewIndex.value);
 if(index!==null){await previewSnapshot(index);return}
 if(!previewRun.value)liveLine.value=lineIndex.value;
 previewGeneration++;historyPrelude.value=true;narration.stop();guide.value=false;intro.value=prologue.length-1;page.value='prologue';
}
async function nextPreview(){
 if(historyPrelude.value&&page.value==='cover'){intro.value=0;page.value='prologue';return}
 if(!run.value||previewIndex.value===null)return;
 const next=nextSnapshot(run.value.snapshots,previewIndex.value);if(next===null)resumePresent();else await previewSnapshot(next)
}

async function logout(){previewGeneration++;await guarded(async()=>{await request('/auth/logout','POST');auth.value='';user.value=null;run.value=null;localStorage.removeItem('v1:auth');page.value='cover';teacher.value=false;settings.value=false;previewRun.value=null;previewIndex.value=null;guide.value=false;activity.value=null;review.value=false;exam.value=false;maneuver.value=undefined;narration.stop()})}
function fullscreen(){if(document.fullscreenElement)document.exitFullscreen();else document.documentElement.requestFullscreen().catch(()=>{error.value='当前窗口不支持全屏。'})}
function signal(id:string){if(!progress.value.includes(id))progress.value.push(id)}
onMounted(async()=>{if(auth.value)await guarded(async()=>{user.value=(await request('/auth/me')).user});for(const f of ['council','portrait-L','portrait-Z','portrait-C']){const image=new Image();image.src=`./v11/${f}.webp`}})
onBeforeUnmount(()=>{narration.stop();soundscape.close()})
</script>

<template>
 <main class="v1" :class="[{still:!motion,'has-speaker':!!speakerImage&&['story','prologue'].includes(page)&&(page==='prologue'||previewRun||run?.status!=='ended')},page]">
  <SceneBackdrop :drift="run?.design_version==='V1.6' && page==='story' ? (s?.node.startsWith('C_')?'bank':['rain_listen','arrows','second'].includes(s?.node||'')?'detail':'river'):undefined" :src="backdrop" fallback="./v11/harbor.webp" :motion="motion" :pan="s?.interaction==='look'&&page==='story'?pan:undefined" :transition="s?.node==='landing'?'shore':(['arrows','second'].includes(s?.node||'')&&volleyFinished)?'reveal':['council','command','v13/camp-debrief'].includes(art)?'unroll':'approach'" @ready="backdropReady=true;backdropFailed=false" @unavailable="backdropFailed=true;volleyFinished=true"/>
  <SceneMotion v-if="run?.design_version==='V1.6' && page==='story'" :node="s?.node||''" :weather="s?.weather" :active="motion"/><div class="v1-shade"></div><BattleBarrage v-if="run?.design_version==='V1.6'&&s?.battle&&hasVolleys&&!volleyFinished&&backdropReady" :key="run.id+':'+s.node" :phase="s.battle.phase" :view="s.battle.view" :motion="motion" :audible="ambience" @done="volleyFinished=true" @impact="ambience&&soundscape.hit()" @drum="ambience&&soundscape.drum()"/><Barrage v-if="run?.design_version!=='V1.6'&&hasVolleys&&!volleyFinished&&backdropReady" :key="s?.node" :motion="motion" :second="s?.node==='second'" @done="volleyFinished=true" @impact="ambience&&soundscape.hit()"/><V1Atmosphere :active="motion" :scene="artFile" :weather="page==='story'?s?.weather:'mist'"/>
  <header class="v1-top"><button class="wordmark" @click="page='cover';narration.stop()">草船借箭 <small>两岸 · 同一夜</small></button><nav aria-label="课件设置"><button @click="voice=!voice">人物对白 {{voice?'开':'关'}}</button><button @click="music=!music">背景音乐 {{music?'开':'关'}}</button><button @click="ambience=!ambience">环境声效 {{ambience?'开':'关'}}</button><button @click="fullscreen">全屏</button><button @click="settings=true">设置</button></nav></header>
  <button v-if="hasPrevious&&!activity&&!guide&&!maneuver&&!review&&!exam&&!settings" class="scene-back" :disabled="busy" @click="previousScene" aria-label="回看上一幕"><span>←</span><small>上一幕</small></button>
  <button v-if="hasForward&&!activity&&!guide&&!maneuver&&!review&&!exam&&!settings" class="scene-back scene-forward" :disabled="busy" @click="nextPreview" aria-label="沿原路线前往下一幕"><span>→</span><small>下一幕</small></button>
  <p v-if="error" role="alert" class="v1-error">{{error}} <button @click="error=''">关闭</button><button v-if="run" @click="restore(run.id)">重新载入</button></p>
  <section v-if="page==='cover'" class="v1-cover">
    <p class="eyebrow">一江雾起 · 三人入局</p><h1>草船<span>借箭</span></h1><p class="cover-copy">十万支箭，三日期限。<br/>这一夜，你会让故事走向何处？</p>
    <button class="gold" @click="begin">进入新的故事 <b>⟶</b></button><button v-if="canResume" class="text-link" @click="restore()">接续未尽的一夜</button>
    <small>取材《三国演义》第四十六回 · 三视角互动叙事</small>
  </section>
  <button v-if="page==='cover'" class="v1-teacher" @click="user?.role==='teacher'?teacher=true:page='login'">教师入口 / 学习账号</button>
  <section v-if="page==='login'" class="v1-login"><p class="eyebrow">入局之前</p><h1>{{browserEdition?'选择体验身份':'留下你的名字'}}</h1><p>{{browserEdition?'LST 公开体验 · 存档仅保存在当前浏览器，不跨设备同步。请勿填写真实学生资料。':'使用班级分配的账号，保存故事与课题作答。'}}</p><form @submit.prevent="login"><label v-if="browserEdition">体验身份<select v-model="loginId"><option value="S001">学生一 · S001</option><option value="S002">学生二 · S002</option><option value="S003">学生三 · S003</option><option value="T001">教师 · 查看本机体验记录</option></select></label><label v-else>学号 / 教师号<input v-model="loginId" autocomplete="username" required/></label><label v-if="!browserEdition">密码<input v-model="password" type="password" autocomplete="current-password" required/></label><button class="gold" :disabled="busy">{{busy?'正在装载剧情，请稍候…':'进入课件'}}</button></form><button class="text-link" @click="page='cover'">返回江边</button></section>
  <section v-if="page==='prologue'" class="v1-intro"><p class="eyebrow">序 · 赤壁之前</p><h1>{{intro<2?'隔江相望':'三日之约'}}</h1><p class="intro-note">{{intro<2?'历史背景 · 两岸为课件空间示意':'文学情境 · 后续含情境推演'}}</p></section>
  <div v-if="page==='prologue'&&intro<2" class="v12-banks"><div><small>江南 · 联手抗曹</small><strong>孙刘联军</strong><p>周瑜统军 · 鲁肃联络<br/>诸葛亮代表刘备</p></div><span>大江</span><div><small>江北 · 曹军水寨</small><strong>曹操</strong><p>统率北方军队南下<br/>隔江观察联军动向</p></div></div>
  <section v-if="page==='roles'" class="v1-roles"><p class="eyebrow">这一夜，从谁的眼睛看起</p><h1>选择你的立场</h1><div class="role-row"><button v-for="r in ['L','Z','C']" :key="r" :class="{chosen:role===r}" @click="role=r"><img :src="portraitUrl(`portrait-${r}`)" alt=""/><div><small>{{r==='L'?'东吴 · 借船与照应':r==='Z'?'刘备使者 · 谋划与进退':'曹军 · 守寨与判断'}}</small><h2>{{roleNames[r]}}</h2><p>{{roleCopy[r]}}</p></div></button></div><div class="v12-scenarios" aria-label="选择江上情境"><button v-for="item in scenarios" :key="item.id" :aria-pressed="scenario===item.id" :class="{selected:scenario===item.id}" @click="scenario=item.id"><img :src="`./v11/${item.image}.webp`" alt=""/><span><b>{{item.name}}</b><small>{{item.detail}}</small></span></button></div><div class="entry-options"><div class="pair-choice"><label><input type="checkbox" v-model="pairMode"/>两人共用一台设备</label><p>{{pairMode?'轮流操作、各自作出决定。每次先选“此刻执掌”，记录归到实际操作者名下。':'独自入局，也有随行讲解员岑舟可供求助。'}}</p><label v-if="pairMode">同伴姓名<input v-model="members" placeholder="请填写共同参与者的姓名"/></label></div><button class="gold" :disabled="busy" @click="enter">以{{roleNames[role]}}入局 ⟶</button></div><p class="scenario-rule">情境改变的是初始敌情；之后仍由你的号令决定走向。曹操可以更改原来的守寨安排。</p></section>
  <template v-if="page==='story'&&s&&run">
   <div class="v1-heading"><p class="eyebrow">{{s.act}} · {{s.scenario_label}}</p><h1>{{s.title}}</h1><span>{{s.role==='C'&&['return','landing','muster','unload','arrow_tally','south','epilogue_2'].includes(s.node)?'镜头转向南岸':s.role!=='C'&&['north','epilogue_1'].includes(s.node)?'镜头转向北岸':s.node==='epilogue_3'?'天亮后的江面':roleNames[s.role]+'视角'}}</span><p v-if="['prepare','C_alarm'].includes(s.node)" class="scenario-arrival">{{s.scenario_brief}}</p></div>
   <div class="v1-trail" v-if="!previewRun&&!battlePlaying"><button @click="openReview">回望这一夜</button><label v-if="run.members.length>1">此刻执掌<select v-model="actor" :disabled="!!activity" @change="changeActor"><option v-for="(p,i) in run.members" :value="i">{{p.name}}</option></select></label></div>
   <template v-if="canOperate&&run.status!=='ended'">
    <div class="v1-operation" :class="s.interaction">
      <button v-if="activityLabel" class="v12-action-invite" @click="openActivity"><span class="invite-orbit">{{s.interaction==='drum'?'鼓':s.interaction==='signals'?'令':s.interaction==='inspect'?'舟':'观'}}</span><span><b>{{activityLabel}}</b><small>{{operationDone?'已完成 · 可重新操作':'亲手完成这一段安排'}} ⟶</small></span></button>
      <div v-if="['balance','rudder'].includes(s.interaction)||s.node==='side_check'" class="helm-invite"><p>{{s.interaction==='rudder'?'箭已取到，该离开了。':'一侧草把已满，另一侧仍空着。'}}</p><button class="gold" @click="maneuver=s.interaction==='rudder'?'rudder':'balance'">{{s.interaction==='rudder'?'握舵领队归航':'握舵，调转船队'}} ↻</button><span v-if="knob>=80&&s.interaction!=='rudder'">另一舷已朝寨</span><span v-if="knob<=35&&s.interaction==='rudder'">已对准返程方向</span></div>
      <div v-if="s.choices?.length" class="v12-reply"><p>{{s.node==='south'?(s.role==='C'?'向哨长交代守令':'向周都督复命'):s.node==='disagree'?'眼前的计策，还走得下去吗？':'回应眼前的人'}}</p><button v-for="c in s.choices" :key="c.id" :class="{selected:chosenReply===c.id}" :aria-pressed="chosenReply===c.id" @click="chosenReply=c.id"><small>对{{c.recipient}}说</small>{{c.text}}</button><button class="text-link" @click="ownThought=!ownThought">{{ownThought?'收起自己的想法':'补充自己的想法（记入复盘）'}}</button><textarea v-if="ownThought" v-model="expression" @input="saveDraft" maxlength="1000" aria-label="说出我心中的想法" placeholder="我还想说……"></textarea><button class="gold speak-choice" :disabled="busy||!selectedChoice" @click="reply">对{{selectedChoice?.recipient||'他'}}说 ⟶</button></div>
      <label v-else-if="s.interaction==='expression'" class="v1-expression">{{s.prompt}}<textarea v-model="expression" @input="saveDraft" maxlength="1000" placeholder="我想说……"></textarea></label>
      <label v-if="s.interaction==='count'" class="count-tool">前队十条，后队十条。合计归队<input v-model="count" type="number" min="0" max="20" aria-label="归队船只总数"/>条。</label>
    </div>
    <div v-if="visibleActions.length" class="v1-actions"><small>你的号令</small><button v-for="(a,i) in visibleActions" :key="a.id" :data-action="a.id" :disabled="busy" @click="act(a.id)"><span>{{String(i+1).padStart(2,'0')}}</span>{{a.label}}<b>⟶</b></button></div>
   </template>
   <section v-if="run.status==='ended'&&!previewRun" class="v1-ending"><p>{{roleNames[s.role]}} · {{s.scenario_label}} · 这一夜的结局</p><h2>{{s.outcome?.title||s.title}}</h2><p>{{s.outcome?.summary||s.result?.reason}}</p><p>{{s.role==='C'?'南岸船队：':''}}{{s.ending==='E0'?'留岸':'归队'}} {{s.result?.boats}} 条 · {{s.role==='C'?'从曹军取得':'实得'}} {{s.result?.arrows.toLocaleString()}} 支箭</p><blockquote><small>{{s.outcome?.bank}} · {{roleNames[s.role]}}</small><p>“{{s.outcome?.closing}}”</p></blockquote><p class="other-bank">{{s.outcome?.other_bank}}</p><small>{{s.outcome?.lesson}}</small><details v-if="s.afterstory_note" class="afterstory-note"><summary>故事与历史</summary><p>{{s.afterstory_note}}</p></details><div><button class="gold" @click="exam=true">课题测试 · 100分</button><button @click="openReview">回看选择 / 换角重演</button><button @click="page='roles'">另入一局</button></div></section>
  </template>
  <img v-if="!battlePlaying&&speakerImage&&['story','prologue'].includes(page)&&(page==='prologue'||previewRun||run?.status!=='ended')" :key="speakerImage" :src="portraitUrl(speakerImage)" class="dialogue-portrait" :class="{cutout:speakerImage.startsWith('speaker')}" alt=""/>
  <div v-if="!battlePlaying&&current&&['story','prologue'].includes(page)&&(page==='prologue'||previewRun||run?.status!=='ended')" class="v1-dialogue"><span>{{current.speaker==='旁白'?'岑舟 · 行记':current.speaker}}</span><p :key="current.text" tabindex="0" aria-label="当前完整对白，可滚动阅读">{{current.text}}</p><div><button v-if="page==='story'&&!previewRun&&run?.status!=='ended'" @click="askHelp" :disabled="busy">请岑舟指点</button><button @click="speak(true)" aria-label="再听这句话">再听</button><button v-if="page==='prologue'||!ready||previewRun" class="continue" :disabled="busy" @click="advance">{{page==='prologue'&&intro===4?(historyPrelude?'回到这一夜':'选择人物'):previewRun&&ready?'下一幕':'继续听'}} ⟶</button><small v-else-if="!previewRun">{{canOperate?'轮到你作出安排':'箭正落在船舷上'}}</small></div></div>

  <aside v-if="guide" class="v12-guide" role="dialog" aria-label="随行讲解员岑舟"><button class="guide-close" @click="guide=false;narration.stop()" aria-label="关闭讲解员">×</button><img :src="'./v12/guide-cenzhou.webp'" alt="随行讲解员岑舟"/><div><small>随行讲解员</small><h2>岑舟</h2><p>{{guideText}}</p><button class="gold" @click="openActivity">{{activityLabel||(['balance','rudder'].includes(s?.interaction||'')?'到舵前试一试':'回去作出回应')}} ⟶</button><button class="text-link" @click="voice&&narration.play('guide-repeat',guideText,true,'岑舟')">再听一遍</button></div></aside>
  <div v-if="activity" ref="activityDialog" class="v12-activity" role="dialog" aria-modal="true" tabindex="-1" :aria-label="activityLabel" @keydown="trapActivityFocus" @keydown.esc.stop="activity=null;narration.stop()"><button class="activity-close" @click="activity=null;narration.stop()">返回当前一幕 ×</button><ArrowTallyStage v-if="activity==='arrow_tally'&&s?.tally" :key="run?.id+':'+s.node+':'+actor" :context="s.tally" :initial="activityDraft.arrow_tally" :motion="motion" @change="saveActivity" @complete="finishActivity" @narrate="musterVoice"/><MusterStage v-if="activity==='muster'" :arrows="s?.cargo?.arrows||0" :initial="activityDraft.muster" :motion="motion" @change="saveActivity" @complete="finishActivity" @narrate="musterVoice"/><BoatWorkshop :cinematic="run?.design_version==='V1.6'" v-if="activity==='assembly'" :initial="assembly" :motion="motion" @change="assemblyChange" @complete="finishActivity"/><NavSignal v-if="activity==='nav_signal'" :key="run?.id+':'+s?.node+':'+actor" :context="s?.signal_context||'outer'" :initial="activityDraft.nav_signal" :motion="motion" :audible="ambience" @change="saveActivity" @complete="finishActivity" @drum="ambience&&soundscape.drum()"/><SignalRelay v-if="activity==='signals'" :initial="activityDraft.signals" @change="saveActivity" @complete="finishActivity"/><DrumStage v-if="activity==='drum'" :initial="activityDraft.drum" @change="saveActivity" @hit="drum" @complete="finishActivity"/><RiverManeuver v-if="['position','rescue','command'].includes(activity)" :mode="activity" :motion="motion" :free-exploration="['V1.5','V1.6'].includes(run?.design_version||'')" :initial="activityDraft[activity]" @change="saveActivity" @complete="finishActivity"/><ObservationStage v-if="activity==='look'" :node="s?.node||''" :clear="s?.weather==='clear'" :cao="s?.role==='C'" :backdrop="backdrop" @complete="finishActivity"/></div>
  <div v-if="maneuver" class="v1-overlay boat-overlay maneuver-overlay"><button class="modal-close" @click="maneuver=undefined">带着当前朝向返回 ×</button><h2>{{maneuver==='balance'?'前船转，后船随——换另一舷':'船首收回，沿外侧归航'}}</h2><V1Boat :cinematic="run?.design_version==='V1.6'" :load="s?.ship_load" :mode="maneuver" :motion="motion" :initial-heading="knob*1.8" @heading="knob=$event;operationAuthors['helm']=actor;saveOperation()"/><button class="gold apply-heading" @click="maneuver=undefined">采用当前朝向 ⟶</button></div>
  <div v-if="inspecting" class="v1-overlay boat-overlay"><button class="modal-close" @click="inspecting=false">返回船上 ×</button><h2>把船看明白，再安排这一夜</h2><V1Boat :cinematic="run?.design_version==='V1.6'" :load="s?.ship_load" :motion="motion"/><p>拖动环视 · 滚轮缩放 · 方向键旋转</p></div>
  <div v-if="review" class="v1-overlay review-overlay"><button class="modal-close" @click="review=false">返回故事 ×</button><h2>这一夜的来路</h2><p>重演另存一条路线，原来的选择和原话仍保留。</p><div class="memory-list"><div v-for="snap in run?.snapshots" :key="snap.index"><small>{{String(snap.index+1).padStart(2,'0')}}</small><span>{{snap.title}}</span><button @click="fork(snap.index)">从这里重演</button><button v-if="snap.node==='K1'&&s?.role==='L'&&run?.question" @click="fork(snap.index,'Z')">换诸葛亮，回应原话</button></div></div><h3>已保存的故事</h3><button v-for="item in savedRuns" @click="restore(item.id);review=false">{{roleNames[item.role]}} · {{item.status==='ended'?'已收束':'进行中'}} · {{item.created_at.slice(0,16)}}</button></div>
  <div v-if="settings" class="v1-overlay settings-overlay"><button class="modal-close" @click="settings=false">关闭 ×</button><h2>课件设置</h2><div class="drum-volume"><p>战鼓力度</p><button v-for="d in [{name:'静音',v:0},{name:'轻声',v:.4},{name:'浑厚',v:.85},{name:'强劲',v:1}]" :aria-pressed="drumVolume===d.v" :class="{selected:drumVolume===d.v}" @click="drumVolume=d.v;soundscape.setDrumVolume(d.v)">{{d.name}}</button></div><label><input type="checkbox" v-model="motion"/>江雾、光影与镜头动效</label><label><input type="checkbox" v-model="voice"/>人物对白语音</label><p v-if="voiceStatus==='unavailable'">当前语音暂不可用，字幕仍完整保留。</p><p>《三国志》的赤壁背景与《三国演义》的借箭情节分开呈现；各支线为教学情境推演。短短、短长、长长是本课为这支船队设计的约定，取意于金鼓旌旗传令，不是已考证的汉代口令。岑舟为原创虚构讲解角色，当前采用预写场景指导；真实大模型仍暂缓接入。共用设备的同伴姓名只作课堂操作归属，不作为已验证的独立账户。未开展真实课堂效果实验。</p><button v-if="user" @click="logout">退出{{user.name}}的账号</button><small>LST · 万弩临江，一舷一策</small><p v-if="browserEdition">公开体验版：剧情、作品和答卷只存本机。教师入口也是本机演示，无跨设备认证。公开题目可查阅答案，适合作为练习；正式考核请另设题卷并部署服务器。真实 AI 未启用。</p></div>
  <ExamPanel v-if="exam&&user" :request="request" :user-id="user.user_id" @close="exam=false"/>
  <TeacherPanel v-if="teacher&&user?.role==='teacher'" :request="request" @close="teacher=false"/>
 </main>
</template>


<style scoped>.v1-login select{width:100%;padding:14px;background:#14242b;color:#eee6d5;border:1px solid #b7a576;font:inherit}.v1-login .gold{min-width:240px}</style>
