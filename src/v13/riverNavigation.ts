import {riverProgress,riverSafe} from '../v12/experience.ts'
export function riverPoint(x:number,z:number){return {x:Math.max(-9,Math.min(9,Number.isFinite(x)?x:0)),z:Math.max(-12,Math.min(7,Number.isFinite(z)?z:5))}}
/** Five abreast, four ranks. The lead is the centre of the forward rank. */
export function fleetSlots(){return Array.from({length:20},(_,i)=>({x:(i%5-2)*2.7,z:Math.floor(i/5)*4.2})).sort((a,b)=>(a.z-b.z)||(Math.abs(a.x)-Math.abs(b.x)))}
export function riverFeedback(mode:string,x:number,z:number){const safe=riverSafe(mode,x,z);return {safe,progress:riverProgress(mode,z),message:mode==='rescue'?(safe?'接应船已在末船外侧，南向水道可供两船归队。':'把接应船移到右后方末船的外侧；避开它的回桨水面。'):mode==='command'?(safe?'哨艇仍在警戒水线内，可沿原航迹回寨。':'哨艇已越过警戒水线；先退回，再向曹寨复报。'):(safe?'二十船分四排纵深；右侧回转水道留空。':'领船已越警戒水线，后队仍在跟进；向江心退开。')}}

