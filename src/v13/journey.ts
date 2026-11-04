type Snapshot={index:number;node:string}
export function previousSnapshot(snaps:Snapshot[],preview:number|null):number|null{
 const at=preview===null?snaps.length-1:snaps.findIndex(s=>s.index===preview)
 return at>0?snaps[at-1].index:null
}
/** null means return to the live current scene, never fetch it as a stale preview. */
export function nextSnapshot(snaps:Snapshot[],preview:number):number|null{
 const at=snaps.findIndex(s=>s.index===preview)
 return at>=0&&at+1<snaps.length-1?snaps[at+1].index:null
}
export type MusterDraft={front:boolean;rear:boolean;total:number|null}
export function musterPayload(draft:MusterDraft){
 return draft.front&&draft.rear&&draft.total===20?{front_checked:true,rear_checked:true,total:20}:null
}
export function afterVolleyArt(node:string,finished:boolean):string|null{
 return finished&&['arrows','second','side_check'].includes(node)?`./v13/${node==='second'?'arrows-both':'arrows-laden'}.webp`:null
}
export function musterBackdrop(arrows:number){return arrows>0?'./v13/muster-dock.webp':'./v13/landing-empty.webp'}
