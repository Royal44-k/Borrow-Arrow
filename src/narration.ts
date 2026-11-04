export interface SpeechPort {cancel():void;speak(text:string,events:{start():void;end():void;error(code:string):void},speaker?:string):void}
export type VoiceStatus='idle'|'starting'|'speaking'|'finished'|'unavailable'
export class Narration {
 private port:SpeechPort;private status:(status:VoiceStatus)=>void
 private generation=0;private lastKey=''
 constructor(port:SpeechPort,status:(status:VoiceStatus)=>void){this.port=port;this.status=status}
 play(key:string,text:string,repeat=false,speaker?:string):boolean{
  if(!text.trim()||(!repeat&&key===this.lastKey))return false
  this.stop();this.lastKey=key;const ticket=this.generation
  const update=(s:VoiceStatus)=>{if(ticket===this.generation)this.status(s)}
  update('starting')
  try{this.port.speak(text,{start:()=>update('speaking'),end:()=>update('finished'),error:code=>{if(!['canceled','interrupted'].includes(code))update('unavailable')}},speaker)}catch{update('unavailable')}
  return true
 }
 stop():void{this.generation++;this.port.cancel();this.status('idle')}
}

/** Device-local voice only. Never sends text to an external paid TTS service. */
export function browserSpeechPort(preferMale=false):SpeechPort {
 let remove=()=>{},timer:ReturnType<typeof setTimeout>|undefined,active:SpeechSynthesisUtterance|null=null
 const cleanup=()=>{remove();remove=()=>{};if(timer)clearTimeout(timer);timer=undefined}
 return {
  cancel(){cleanup();active=null;if('speechSynthesis'in window)window.speechSynthesis.cancel()},
  speak(text,events){
   if(!('speechSynthesis'in window)){events.error('synthesis-unavailable');return}
   const synth=window.speechSynthesis
   const ready=()=>{
    const voices=synth.getVoices(),local=voices.filter(v=>v.localService&&/^zh/i.test(v.lang)),voice=preferMale?local.find(v=>/Kangkang|Yunyang|Yunxi|Yunjian|Yunxia|康康/i.test(v.name)):local.find(v=>/^zh[-_]CN$/i.test(v.lang))??local[0]
    if(!voice)return false
    cleanup();active=new SpeechSynthesisUtterance(text);active.lang=voice.lang;active.voice=voice;active.rate=.94
    active.onstart=events.start;active.onend=()=>{active=null;events.end()};active.onerror=e=>{active=null;events.error(e.error)}
    synth.speak(active);return true
   }
   if(ready())return
   const changed=()=>{ready()};synth.addEventListener('voiceschanged',changed);remove=()=>synth.removeEventListener('voiceschanged',changed)
   timer=setTimeout(()=>{cleanup();events.error('language-unavailable')},1800)
  }
 }
}
