export interface ProviderStatus {ready:boolean;enabled:boolean;configured:boolean;mode:string;model:string;calls_remaining:number}
export interface GradeRow {item_id:string;model_score:number;rule_score:number;max_points:number;status:string;reason:string}
export interface Suggestion {item_id:string;suggested_score:number;criteria:{id:string;score:number;reason:string}[];feedback:string}
export interface GoalObservation {goal_id:string;status:string;observation:string;evidence_ids:string[];support_condition:string;next_step:string}
export interface AIRun {id:string;kind:string;status:string;mode:string;model:string;error_code:string|null;created_at:string;result:{objective_results?:GradeRow[];conflict_ids?:string[];subjective_suggestions?:Suggestion[];summary?:string;goals?:GoalObservation[];evidence_map?:Record<string,{source_id:string;route_id:string;node_id:string;kind:string;support_ids:string[]}>}}
export function modelSucceeded(run:AIRun|null|undefined){return run?.mode==='live'&&['completed','conflict'].includes(run.status)}
export function canResolveGrade(examId:string,run:AIRun|null|undefined,confirmed:boolean,values:Record<string,number|null>):boolean {
  if(examId!=='caocuan-exam-s1.2')return true
  if(!modelSucceeded(run))return confirmed
  return (run?.result.conflict_ids??[]).every(id=>{const max=run?.result.objective_results?.find(r=>r.item_id===id)?.max_points;const value=values[id];return typeof max==='number'&&typeof value==='number'&&Number.isInteger(value)&&value>=0&&value<=max})
}
export function runLabel(run:AIRun|null|undefined):string {
  if(!run)return '尚未请求模型'
  const labels:Record<string,string>={pending_model:'模型未配置 · 未调用',budget_exhausted:'本机调用上限已用完',running:'模型处理中',completed:'模型已返回 · 待教师复核',conflict:'判分有分歧 · 待教师复核',failed:'模型调用失败',invalid_response:'模型结果未通过校验',stale:'作答已变化 · 本次结果不采用',insufficient_evidence:'尚无足够的个人记录'}
  return labels[run.status]??run.status
}
