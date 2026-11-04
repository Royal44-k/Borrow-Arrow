/** Keep the last decoded frame on failed or out-of-order requests. */
export class FrameLoader<T> {
 private ticket=0
 async load(url:string, decode:(url:string)=>Promise<T>, commit:(value:T)=>void){
  const id=++this.ticket
  try{const value=await decode(url);if(id!==this.ticket)return 'stale';commit(value);return 'ready'}
  catch{return id===this.ticket?'failed':'stale'}
 }
 cancel(){this.ticket++}
}
export function headingProgress(degrees:number){return Math.max(0,Math.min(100,degrees/180*100))}
