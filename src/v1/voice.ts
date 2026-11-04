import {browserSpeechPort,type SpeechPort} from '../narration.ts'
/** Pre-rendered authored narration; runtime learner text stays on the device. */
export function courseVoicePort():SpeechPort{
 const fallback=browserSpeechPort(true);let current:HTMLAudioElement|null=null,ticket=0
 const load=(path:string):Promise<Record<string,string>>=>fetch(path).then(r=>r.ok?r.json():{}).catch(()=>({}))
 const manifest:Promise<Record<string,string>>=Promise.all([load('./v11/voices.json'),load('./v12/voices.json'),load('./v13/voices.json'),load('./v14/voices.json'),load('./v15/voices.json'),load('./v16/voices.json')]).then(([old,current,newest,v14,v15,v16])=>({...Object.fromEntries(Object.entries(old).map(([text,file])=>[text,`./v11/audio/${file}`])),...current,...newest,...v14,...v15,...Object.fromEntries(Object.entries(v16).filter(([key])=>key.includes('|')))}))
 return {cancel(){ticket++;fallback.cancel();if(current){current.pause();current.src='';current=null}},speak(text,events,speaker){const request=++ticket;manifest.then(index=>{if(request!==ticket)return;const url=index[(speaker||'')+'|'+text]||index[text];if(!url){fallback.speak(text,events);return}const a=new Audio(url);current=a;a.onplaying=()=>{if(request===ticket)events.start()};a.onended=()=>{if(request===ticket)events.end()};a.onerror=()=>{if(request===ticket)fallback.speak(text,events)};a.play().catch(()=>{if(request===ticket)events.error('playback-unavailable')})})}}
}
