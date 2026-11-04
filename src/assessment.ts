export interface ExamOption { id:string; text:string }
export interface ExamPart { id:string;type:'number'|'single';prompt:string;points:number;options?:ExamOption[] }
export interface RubricCriterion { id:string; title:string; max_points:number; description:string }
export interface ExamItem { id:string; type:'single'|'multi'|'order'|'match'|'scenario'|'fill'|'short'|'essay'|'reflection'; prompt:string; points:number; goal_id:string; options?:ExamOption[]; left?:ExamOption[]; right?:ExamOption[]; parts?:ExamPart[]; rubric?:unknown; rubric_criteria?:RubricCriterion[]; answer_key?:unknown; suggested_words?:string|number; suggested_length?:string; input_hint?:string; source_refs?:unknown; material?:string }
export type Answer = string | string[] | Record<string,string>
export interface SubmissionIdentity { fingerprint:string; requestId:string }
export function isAnswered(item:ExamItem,answer:unknown):boolean {
  const ids=(item.options??[]).map(o=>o.id)
  if(isWriting(item)||item.type==='fill') return typeof answer==='string' && answer.trim().length>0 && answer.trim().length<=(item.type==='fill'?200:2000)
  if(item.type==='scenario'&&item.parts){
    if(!answer||typeof answer!=='object'||Array.isArray(answer))return false
    const values=answer as Record<string,unknown>
    return Object.keys(values).length===item.parts.length&&item.parts.every(p=>typeof values[p.id]==='string'&&(p.type==='number'?/^[0-9]{1,9}$/.test(values[p.id] as string):p.options?.some(o=>o.id===values[p.id])))
  }
  if(item.type==='single'||item.type==='scenario') return typeof answer==='string' && ids.includes(answer)
  if(item.type==='multi'||item.type==='order') {
    if(!Array.isArray(answer)||!answer.length||new Set(answer).size!==answer.length||!answer.every(a=>typeof a==='string'&&ids.includes(a))) return false
    return item.type==='multi'||answer.length===ids.length
  }
  if(item.type==='match') {
    if(!answer||typeof answer!=='object'||Array.isArray(answer))return false
    const map=answer as Record<string,unknown>,right=(item.right??[]).map(o=>o.id)
    return !!item.left?.length && Object.keys(map).length===item.left.length && new Set(Object.values(map)).size===right.length && item.left.every(o=>typeof map[o.id]==='string'&&right.includes(map[o.id] as string))
  }
  return false
}
export function moveInOrder(ids:string[],index:number,direction:number):string[] {
  const next=[...ids],target=index+direction
  if(index<0||target<0||index>=next.length||target>=next.length)return next
  ;[next[index],next[target]]=[next[target]!,next[index]!]
  return next
}
export function visibleScore(attempt:{status:string;total:number|null}):string {
  return attempt.status==='published'&&typeof attempt.total==='number'?String(attempt.total):attempt.status==='pending_review'?'待批阅':'待发布'
}
export function submissionIdentity(answers:Record<string,unknown>,previous:SubmissionIdentity|null,id:()=>string):SubmissionIdentity {
  const fingerprint=JSON.stringify(answers)
  return previous?.fingerprint===fingerprint?previous:{fingerprint,requestId:id()}
}
export function isWriting(item:ExamItem):boolean { return ['short','essay','reflection'].includes(item.type) }
export function criteriaFor(item:ExamItem):RubricCriterion[] {
  if(item.rubric_criteria?.length) return item.rubric_criteria
  const legacy:Record<string,string[]>={q10:['回应场景中的变化','安排具体可执行','前后连贯并说明后果'],q11:['承接给定结果','人物动机可辨','动作与对白推进收束']}
  return (legacy[item.id]??['按原卷第一项量规','按原卷第二项量规','按原卷第三项量规']).map((title,i)=>({id:`c${i+1}`,title,max_points:5,description:''}))
}
export function reviewComplete(items:ExamItem[],criteria:Record<string,(number|null)[]>):boolean {
  return items.length>0&&items.every(q=>{
    const defs=criteriaFor(q),values=criteria[q.id]
    return values?.length===defs.length&&values.every((v,i)=>Number.isInteger(v)&&Number(v)>=0&&Number(v)<=defs[i]!.max_points)
  })
}
export function canPublishReview(saved:{status:string;item_scores:Record<string,number|null>;review_comment?:string},scores:Record<string,number|null>,comment:string,items?:ExamItem[]):boolean {
  const ids=items?items.filter(isWriting).map(q=>q.id):['q10','q11']
  return saved.status==='reviewed' && comment===(saved.review_comment??'') && ids.length>0 && Object.keys(scores).length===ids.length && ids.every(id=>typeof scores[id]==='number'&&scores[id]===saved.item_scores[id])
}
