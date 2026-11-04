import type { Action, RoleView, Ending } from './types'
const titles:Record<string,string>={A_PREP_STRAW:'布置草束',A_PREP_ARMOR:'布置空甲',A_WAIT_WEATHER:'候天',A_LAUNCH:'启舟',A_CANCEL:'罢行',A_PATROL_CLOSE:'交班',A_SIGNAL:'传声',A_NEAR:'近岸',A_OBSERVE:'察看',A_PROBE:'隔江相问',A_VOLLEY:'普通箭回应',A_HOLD:'收住射令',A_TURN:'转舷',A_RETURN_FIRE:'回射',A_FIRE:'带火回应',A_EVADE:'应对火光',A_WAIT_WINDOW:'等下一报',A_WITHDRAW:'收舟归岸',A_REPORT:'归营交代',A_SAY:'向同伴开口',A_FACE_RUSU:'转向鲁肃',A_FAN_SIGNAL:'以扇示意'}
export function actionTitle(id:string,fallback:string){return titles[id]??fallback}
type DirectedView=RoleView&{ending_code?:string|null;presentation_state?:RoleView['presentation_state']&{launched?:boolean|null}}
export function stageFor(v:DirectedView|null):'river'|'camp'|'dawn'{
  if(v?.ending||v?.scene.stage==='return'){
    if(v.role==='R_CAO'||v.ending_code==='T7'||v.presentation_state?.launched===false)return 'camp'
    return v.presentation_state?.launched===true?'dawn':'camp'
  }
  return v?.scene.stage==='camp'?'camp':'river'
}
export function arrowBurst(a:RoleView,b:RoleView,id:string){return (b.inventory?.acquired??0)>(a.inventory?.acquired??0)||(b.role==='R_CAO'&&id==='A_VOLLEY'&&b.observations.some(o=>o.id==='arrows_fired'))}
export function sceneDialogue(v:RoleView):{speaker:string;text:string}{return v.latest_response&&v.latest_response.speaker!=='场记'?v.latest_response:v.scene.lines[0]??{speaker:'沈砚',text:'江声未歇。你来定这一回。'}}
export function availableDecisions(a:Action[]){return a.filter(x=>x.id!=='A_RESOLVE_FIRE')}
export interface SavedRoute{userId:string;routeId:string;sessionId:string;token:string}
export function savedRoute(raw:string|null,userId:string):SavedRoute|null{try{const a=JSON.parse(raw??'null');return a&&a.userId===userId&&['routeId','sessionId','token'].every(k=>typeof a[k]==='string'&&a[k].length>0)?a:null}catch{return null}}
export interface ActionIdentity{fingerprint:string;requestId:string}
export function actionIdentity(route:string,revision:number,id:string,params:unknown,old:ActionIdentity|null,uuid:()=>string):ActionIdentity{const fingerprint=JSON.stringify([route,revision,id,params]);return old?.fingerprint===fingerprint?old:{fingerprint,requestId:uuid()}}
export function fogOpacity(fog:string):number{return fog==='clear'?0:fog==='thinning'?.24:.7}
export function endingPresentation(ending:Ending|null|undefined):Pick<Ending,'title'|'description'|'lines'>|null{return ending?{title:ending.title,description:ending.description,lines:ending.lines}:null}
export function showBoatInspection(v:RoleView|null,page:string,open:boolean){return page==='story'&&open&&!!v&&v.role!=='R_CAO'&&v.status==='active'&&!v.ending}

// Student-facing speech. Authoring notes remain in the content registry.
export const actionNarratives:Record<string,string>={
  A_PREP_STRAW:'把草束人形立在船外侧。先看清船上各人的位置，再让船夫照此安放。',
  A_PREP_ARMOR:'这回换作空壳盔甲，仍摆在船外侧。看过这一身轮廓，再把安排定下来。',
  A_WAIT_WEATHER:'暂留岸边，等下一报天气，再决定去留。',
  A_LAUNCH:'船已备下。就着眼前的江色启程，看看这一夜会把你带到哪里。',
  A_CANCEL:'这一回不出发。安顿人手、归还物件，向等候的人交代你的决定。',
  A_PATROL_CLOSE:'这一班巡守已到交接时分。把本方见过的动静留给接班的人。',
  A_SIGNAL:'把声势送过江面：击鼓、呼喊，或举旗示意。也可以先静下来，听那边的回音。',
  A_NEAR:'让船再靠近一处。换个位置，看眼前的岸影会不会清楚些。',
  A_OBSERVE:'先不急着变招。再留意一回眼前的人影、声响与船势。',
  A_PROBE:'把一句追问送过江面，听那边有没有应声。',
  A_VOLLEY:'以寻常箭矢回应这一阵动静，再听哨卒怎样来报。',
  A_HOLD:'收住射令，让弓手继续戒备。再听、再看，不急着发出下一箭。',
  A_TURN:'把船缓缓转过来。另一侧的布置和眼前的岸影，一起再看一遍。',
  A_RETURN_FIRE:'向对岸回射一次。先看看这回要用去多少箭，再决定是否出手。',
  A_FIRE:'这一回换作带火的箭矢。火光划过之后，接着听江上的动静。',
  A_RESOLVE_FIRE:'火光划过江面。接下来的动静，正有人赶来相告。',
  A_EVADE:'火光来过。先顾着船上的人，再决定就此离开，还是处置眼前这一处后再定。',
  A_WAIT_WINDOW:'把这一刻交给江面，等下一阵动静。等来的也许是箭声，也许仍是寂静。',
  A_WITHDRAW:'这一回到此为止。传话收舟，把人和带回的物件一同交代清楚。',
  A_REPORT:'这一夜怎样安排，又怎样收场？把你经手的事情向等候的人交代清楚。',
  A_SAY:'转向眼前的同伴，把此刻想说的那句话留给他。',
  A_FACE_RUSU:'转向子敬，先把他的话听完，再接着回应。',
  A_FAN_SIGNAL:'轻抬羽扇，请同伴稍等片刻，给你留一句话的空当。',
}
export function actionDescription(action:Action,role?:string):string{
  let text=actionNarratives[action.id]??'把这个打算想清楚，再决定是否动手。'
  if(role==='R_CAO'){
    if(action.id==='A_NEAR')text='让本方哨卒换到近一处的位置，再向江面看一眼。'
    if(action.id==='A_PROBE')text='向江上问一句，听来船有没有应声。'
    if(action.id==='A_REPORT')text='把今夜守营的所见与处置，交代给接班的人。'
  }
  if(role==='R_LUSU'&&['A_WAIT_WEATHER','A_LAUNCH','A_CANCEL','A_NEAR','A_TURN','A_RETURN_FIRE','A_EVADE','A_WAIT_WINDOW','A_WITHDRAW'].includes(action.id))text='向孔明提个主意：'+text
  const preview=(action as Action&{preview?:{cost:number;deliverable_after:number;batches?:{kind:string;amount:number}[]}}).preview
  if(action.id==='A_RETURN_FIRE'&&preview&&Number.isFinite(preview.cost)&&preview.cost>=0&&Number.isFinite(preview.deliverable_after)&&preview.deliverable_after>=0){
    const batches=preview.batches?.filter(b=>Number.isFinite(b.amount)&&b.amount>=0).map(b=>`${b.kind==='本次取得'?'今夜借得的':'原先备下的'}${b.amount.toLocaleString()}支`).join('、')
    text+=`这一回要用去${preview.cost.toLocaleString()}支${batches?`（${batches}）`:''}；出手后，留下${preview.deliverable_after.toLocaleString()}支可交付。`
  }
  return text
}
const scenarioNarratives:Record<string,string>={
  responsive_dense:'浓雾笼着江面，灯火隐约。先听一听，你这一岸的消息。',
  skeptic_clear:'今夜岸影分明。隔江相望的人，会怎样理解彼此的来意？',
  quiet_dense:'声音传进雾里，又落回水面。谁会先打破这阵寂静？',
  battle_dense:'两岸各有人守候，一阵动静正在江上展开。你从自己这一边入局。',
  fire_contact:'夜已深，江雾未散。有人在灯下等着一声新的来报。',
  fire_miss:'同样的夜色，不同的等待。先走到你的位置，听眼前的人开口。',
  no_fog_stays:'江面清朗，船还未发。等待、出发，还是另作交代？',
  fog_forming:'眼下还看得清岸影。你在等天色，旁人也在等你的决定。',
  early_return:'雾里有船，灯下有约。把你的这一段故事，从头走到收场。',
  no_contact_patrol:'灯下到了交班的时候。有人守着江岸，也有人仍在筹备。',
}
export function scenarioDescription(id:string){return scenarioNarratives[id]??'先走到你的位置，听听这一夜的江声。'}
