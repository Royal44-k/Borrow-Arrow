export type TallySide='left'|'right'|'equal'
export interface TallyAttempt {sequence:number;answer_total:number;answer_side?:TallySide;feedback?:{text?:string;id?:string;code?:string};feedback_before?:string[];support_ids?:string[];total_correct?:boolean;side_correct?:boolean}
export interface TallyContext {first:number;second:number;spent:number;loss:number;left:number;right:number;total:number;variant:'balance'|'sides';progress:{record_id:string|null;status:'not_started'|'draft'|'complete';attempts:TallyAttempt[]}}
export function tallyInitial(progress:TallyContext['progress'],local:any,newId:()=>string){
 const stored=local&&typeof local==='object'&&typeof local.record_id==='string'&&local.record_id.length>0&&local.record_id.length<=120?local:null
 const id=progress.record_id??stored?.record_id??newId(),last=progress.attempts.at(-1)
 const locked=progress.status==='complete'||progress.attempts.length>=10
 const draft=!locked&&stored?.record_id===id&&typeof stored.total==='string'?stored:null
 return{id,total:draft?draft.total:last?String(last.answer_total):'',side:(draft?['left','right','equal'].includes(draft.side)?draft.side:'':last?.answer_side??'') as TallySide|'',locked}
}
export function parseTallyTotal(value:string):number|null {
 const s=value.trim()
 if(!/^(?:\d+|\d{1,3}(?:,\d{3})+)$/.test(s))return null
 const n=Number(s.replaceAll(',',''))
 return Number.isSafeInteger(n)&&n>=0&&n<=10000000?n:null
}
export function tallySubmission(id:string,variant:'balance'|'sides',value:string,side:TallySide|'') {
 const amount=parseTallyTotal(value)
 if(amount===null||!id||variant==='sides'&&!['left','right','equal'].includes(side))return null
 return {record_id:id,answer_total:amount,...variant==='sides'?{answer_side:side as TallySide}:{}}
}
