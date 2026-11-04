export interface Line {speaker:string;text:string}
export interface StoryAction {id:string;label:string;kind?:string;requires_expression?:boolean}
export interface StoryView {
 version:string;session_id:string;route_id:string;revision:number;role:'L'|'Z'|'C';node_id:string;scene:string;title:string;speaker:string;lines:(string|Line)[];prompt:string;actions:StoryAction[];
 stage:{world:string};visual:Record<string,any>;status:string;ending:Record<string,any>|null;
 members:{id:string;name:string;account_id?:string}[];controller_id:string;snapshots:any[];old_utterances:any[];transition:Line[];help?:any;saved_expression?:any;task_context?:{M12_TALLY?:import('./tally').TallyContext};
}
export const PROLOGUE:Line[]=[
 {speaker:'旁白',text:'赤壁大战前，江东军营。周瑜把一只空箭筒放在案上。'},
 {speaker:'周瑜',text:'水上交战，少不得弓箭。先生可肯替军中筹十万支？'},
 {speaker:'诸葛亮',text:'何时要用？'}, {speaker:'周瑜',text:'十日。'},
 {speaker:'诸葛亮',text:'等不了十日。三日，交箭。'},
 {speaker:'周瑜',text:'军中无戏言。'}, {speaker:'诸葛亮',text:'立状便是。'},
 {speaker:'旁白',text:'鲁肃望着军令状。十万支箭，三日之内，要从哪里来？'}
]
export function publicStage(v:StoryView){const s=v.visual??{};return {
 material: ['S0','S1'].includes(v.node_id)?'none' as const:s.material==='straw'?'straw' as const:s.material==='armor'?'armor' as const:'none' as const,
 layout:['S0','S1','S2'].includes(v.node_id)?'none' as const:s.layout==='both'?'both' as const:s.layout==='one'?'right' as const:'none' as const,
 side:s.side==='left'?'left' as const:'right' as const,
 weather:s.weather==='clear'?'clear' as const:s.weather==='thinning'?'thinning' as const:'dense' as const,
 first:Math.max(0,Number(s.arrows?.right??s.first??0)),second:Math.max(0,Number(s.arrows?.left??s.second??0)),
 fire:v.role==='C'?(s.fire_hit?'hit' as const:s.fire_sent?'miss' as const:'none' as const):s.fire==='burning'?'hit' as const:['extinguished','scorched'].includes(s.fire)?'contained' as const:s.fire==='miss'?'miss' as const:'none' as const
}}
// Object controls enter only after the student chooses that action; choices and
// an unrelated prop panel must not compete for attention in the same shot.
export function stageMode(v:Pick<StoryView,'node_id'>){const n=v.node_id;return n==='S0'||n==='S1'?'inspect':n==='S2'?'place':'river'}
export function visibleActions(v:Pick<StoryView,'actions'>){return v.actions.slice(0,3).map(a=>a.id==='COUNT1.done'?{...a,label:'把箭取下，逐束入筐'}:a)}
export function playableLines(v:StoryView):Line[]{
 if(v.ending){const lines=v.ending.lines??v.ending.dialogue??[];return lines.map((l:any)=>typeof l==='string'?{speaker:v.role==='C'?'曹操':'诸葛亮',text:l}:l).filter((l:Line)=>l.text)}
 // Legacy servers split one authored turn at punctuation. Join only that
 // string representation; explicitly authored Line objects retain their beats.
 const raw=v.lines??[]
 const lines=raw.every(l=>typeof l==='string')?[{speaker:v.speaker,text:raw.join('')}]:raw.map(l=>typeof l==='string'?{speaker:v.speaker,text:l}:l)
 return lines.filter(l=>l.text&&!/采用02|当前角色专属|下一剧情阶段/.test(l.text))
}
export function sceneLines(v:StoryView,includeTransition=true):Line[]{
 const opening=playableLines(v)
 if(!includeTransition)return opening
 const clean=(l:Line)=>l.text.replace(/\s/gu,'')
 const transition=(v.transition??[]).filter(l=>l.speaker&&l.text&&!['导演','末场'].includes(l.speaker))
 // Old saved views may contain the target's complete utterance in transition.
 // Drop only exact same-speaker duplicates; never fuzzy-match student speech.
 const unique=transition.filter(l=>!opening.some(o=>o.speaker===l.speaker&&clean(o)===clean(l)))
 return [...unique,...opening].filter((l,i,a)=>i===0||l.speaker!==a[i-1]?.speaker||clean(l)!==clean(a[i-1]))
}
export function operationAction(v:Pick<StoryView,'node_id'|'actions'>,op:Record<string,any>):string|null {
 const available=(id:string)=>v.actions.some(a=>a.id===id)?id:null
 if(op.kind==='drum'&&op.action==='command')return available(v.node_id==='S11'?'S11.change':'S10.drum')
 if(op.kind==='fire'&&op.action==='water')return available('F1.water')
 if(op.kind==='collect'&&op.complete)return available('COUNT1.done')
 if(op.kind==='return-confirm')return available('R0.return')
 if(op.kind==='helm-confirm'){
  if(op.side==='left')return ['A0.turn','A2.back','A3.turn'].map(available).find(Boolean)??null
 }
 return null
}
export function replayMemories(snapshots:any[]){
 const unique=new Map<string,any>()
 for(const s of snapshots)if(s.can_fork!==false)unique.set(s.node_id,s)
 return [...unique.values()]
}
export function helpPrompts(node:string,role:string){
 let labels=['带我去船边看看','韩伯在哪边等着？','先要照看哪一处？']
 if(role==='C')labels=node==='C2'?['中箭的人影为何不倒？','停箭查看，还是派艇近看？','从寨墙能看清多少？']:['江上现在有什么动静？','弓手和哨艇各能做什么？','还有哪件事没看清？']
 else if(['S1','S2'].includes(node))labels=['草束该放在船上哪里？','绳子怎样绕，人才过得去？','另一边还要摆吗？']
 else if(['S4','S5','S7'].includes(node))labels=['从这里看得到岸灯吗？','这时候走，对岸能看清我们吗？','韩伯解缆了吗？']
 else if(node==='S8')labels=['曹军追来，往哪边退？','谁给后船传令？','这份担心怎么问孔明？']
 else if(node==='S9')labels=['回去的水路在哪边？','靠近后，对方也会看清我们吗？','韩伯等我指哪处？']
 else if(['S10','S11','S12'].includes(node))labels=['岸上回应了吗？','鼓声停下后，听到了什么？','阿成在等哪一道令？']
 else if(['A0','A2','A3','A4'].includes(node))labels=['哪边的草束还空着？','空着的一侧怎样朝岸？','请韩伯指一下船舵']
 else if(node==='H0')labels=['这一筐有多少支？','发出去，还能交给都督吗？','还来得及收回号令吗？']
 else if(['S15','S16','S17'].includes(node))labels=['岸上为什么停箭了？','现在听得见他们喊什么？','怎样叫后船一起退？']
 else if(['F1','F2','F3'].includes(node))labels=['哪里着火了？','人先退到哪里？','湿布下面还要检查什么？']
 else if(node==='R0')labels=['南岸在哪个方向？','后船怎样跟上？','船上的箭先怎么放？']
 else if(node==='COUNT1')labels=['从哪一侧开始取箭？','发出与受损的箭怎么记？','这一束已经数过了吗？']
 return labels.map((label,i)=>({label,level:['notice','organize','example'][i]!}))
}
export const ROLE_NAMES={L:'鲁肃',Z:'诸葛亮',C:'曹操'}
export const ROLE_PROMISES={L:'船与人，由你照应。',Z:'三日期限，由你筹措。',C:'守住水寨，辨清来船。'}
export const PROLOGUE_VERSION='S1.1'
const SCREEN_TITLES:Record<string,string>={S0:'借船',S1:'船舷上的“兵”',S2:'另一侧也要摆吗',S4:'趁雾出发',S5:'江面无雾',S7:'更鼓催人',S8:'孔明的打算',S9:'停在哪里',S10:'鼓声入雾',S11:'寂静的水寨',S12:'还是没有箭',A0:'箭落右舷',A2:'再等一阵？',A3:'箭声渐疏',A4:'另一舷也满了',H0:'这一筐箭',S15:'岸上停箭了',S16:'虚实渐明',S17:'天要亮了',F1:'船边起火',F2:'火落江中',F3:'余火已灭',R0:'回南岸',COUNT1:'把箭点清',C0:'北岸更鼓',C1:'雾里来船',C2:'那排人影没倒',C3:'哨长回报',C4:'不明来意',C5:'虚实已明',C7:'火箭之后',C6:'对面还箭了',CX:'值夜将尽'}
export function screenTitle(node:string,fallback:string){return SCREEN_TITLES[node]??fallback}
