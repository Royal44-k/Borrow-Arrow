export interface TallyContext { right: number; left: number; total: number }
export interface TallyDraft { sample_checked: boolean; samples_taken?:number; right?: number; left?: number; total?: number }
export interface TallyProof extends TallyContext { sample_checked: true }
const fields = ['right', 'left', 'total'] as const
const count = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 && value <= 100000
export function restoreTallyDraft(input?: unknown): TallyDraft {
 const source = input && typeof input === 'object' ? input as Record<string,unknown> : {}
 const samples=typeof source.samples_taken==='number'&&Number.isInteger(source.samples_taken)&&source.samples_taken>=0&&source.samples_taken<=3?source.samples_taken:0
 const draft: TallyDraft = { sample_checked: source.sample_checked === true, samples_taken:source.sample_checked===true?3:samples }
 for (const key of fields) if (count(source[key])) draft[key] = source[key]
 return draft
}
export function verifyTally(input: unknown, context: TallyContext): {ok:true;proof:TallyProof} | {ok:false;message:string} {
 const draft = restoreTallyDraft(input)
 if (!draft.sample_checked) return {ok:false,message:'先查看草把，核实箭是否已经取下。'}
 if (!fields.every(key => count(context[key])) || context.right + context.left !== context.total) return {ok:false,message:'船队合报尚未齐备，请稍后核收。'}
 if (fields.some(key => draft[key] === undefined)) return {ok:false,message:'把右舷、左舷和总数的计数签都摆好。'}
 if (draft.right !== context.right || draft.left !== context.left) return {ok:false,message:'舷数与船队合报不符。再对照两张报签，换一枚计数签。'}
 if (draft.total !== context.total) return {ok:false,message:'两舷相加才是总数。再算一遍，换好总数签。'}
 return {ok:true,proof:{sample_checked:true,right:draft.right!,left:draft.left!,total:draft.total!}}
}
