export type Command='advance'|'spread'|'recall'
export type Pulse='short'|'long'
export type Relay={ship:string;code:Pulse[];ack:true}
export type SignalDraft={command:Command|null;channel:'sound'|'light';code:Pulse[];relays:Relay[]}
export const signalCode=(command:Command):Pulse[]=>command==='advance'?['short','short']:command==='spread'?['short','long']:['long','long']
export function restoreSignal(raw:any):SignalDraft{
 const command:Command|null=['advance','spread','recall'].includes(raw?.command)?raw.command:null
 const channel=raw?.channel==='sound'?'sound':'light'
 const code:Pulse[]=Array.isArray(raw?.code)?raw.code.filter((x:any)=>x==='short'||x==='long').slice(0,2):[]
 const relays:Relay[]=[]
 if(command&&JSON.stringify(code)===JSON.stringify(signalCode(command))&&Array.isArray(raw?.relays)){
  for(const [i,ship] of ['前船','后船'].entries()){
   const r=raw.relays[i]
   if(r?.ship!==ship||r.ack!==true||JSON.stringify(r.code)!==JSON.stringify(code))break
   relays.push({ship,code:[...code],ack:true})
  }
 }
 return {command,channel,code,relays}
}
export function verifySignal(raw:any):boolean{
 if(!raw||!['advance','spread','recall'].includes(raw.command)||!['light','sound'].includes(raw.channel))return false
 const clean=restoreSignal(raw)
 return clean.relays.length===2&&raw.relays?.length===2&&JSON.stringify(raw.code)===JSON.stringify(signalCode(raw.command))
}
