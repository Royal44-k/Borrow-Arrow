export type Choice={id:string;text:string;recipient:string;action_id:string}
export function riverStart(mode:string){return mode==='command'?{x:0,z:-10}:{x:-4,z:5}}
export function riverProgress(mode:string,z:number){return Math.round(((mode==='command'||mode==='rescue')?z+12:7-z)/19*100)}
export function riverSafe(mode:string,x:number,z:number){return mode==='rescue'?riverProgress(mode,z)>=65&&x>=2:riverProgress(mode,z)<=65}
export function activityFor(interaction:string):string|null{return ({inspect:'assembly',signals:'signals',position:'position',rescue:'rescue',command:'command',look:'look',listen:'look',drum:'drum'} as Record<string,string>)[interaction]||null}
export function selectionPayload(choices:Choice[],id:string,text:string):{action:string;payload:Record<string,string>}{const choice=choices.find(x=>x.id===id);return {action:choice?.action_id||'',payload:{...(choice?{utterance_id:choice.id}:{}),...(text.trim()?{text:text.trim()}:{})}}}
export function operationProblem(interaction:string,p:any):string{
 if(interaction==='inspect'&&!['port_straw','starboard_straw','cloth','clear_aisle'].every(k=>p.assembly?.[k]===true))return '两舷挂好草把，盖上青布，再把舱道清出来。'
 if(interaction==='signals'&&(JSON.stringify(p.signal_order)!==JSON.stringify(['前船','后船','领船'])||p.signal_message!=='归队'))return '前船、后船、领船都要复号确认，归队令才算传齐。'
 if(interaction==='drum'&&Number(p.drum_signals)<3)return '登上鼓台，敲响三声，再发下一道令。'
 return ''
}
