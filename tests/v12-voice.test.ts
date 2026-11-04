import test from 'node:test'
import assert from 'node:assert/strict'
import {courseVoicePort} from '../src/v1/voice.ts'

const tick=()=>new Promise<void>(resolve=>setImmediate(resolve))

test('V1.2 static audio overrides old narration and untouched lines retain V1.1 paths',async()=>{
 const savedFetch=globalThis.fetch,savedAudio=(globalThis as any).Audio,savedWindow=(globalThis as any).window
 const urls:string[]=[]
 class Audio {src:string;onplaying?:()=>void;onended?:()=>void;onerror?:()=>void;constructor(src:string){this.src=src;urls.push(src)}play(){return Promise.resolve()}pause(){}}
 try{
  ;(globalThis as any).Audio=Audio;(globalThis as any).window={}
  globalThis.fetch=(async(url:any)=>({ok:true,json:async()=>(String(url).includes('./v13/')||String(url).includes('./v14/')||String(url).includes('./v15/'))?{}:String(url).includes('./v12/')?{'新旁白':'./v12/audio/male.mp3'}:{'新旁白':'old-female.mp3','旧人物句':'legacy.mp3'}})) as any
  const voice=courseVoicePort(),events={start(){},end(){},error(){}}
  voice.speak('新旁白',events);await tick()
  assert.equal(urls.at(-1),'./v12/audio/male.mp3')
  voice.cancel();voice.speak('旧人物句',events);await tick()
  assert.equal(urls.at(-1),'./v11/audio/legacy.mp3')
 }finally{globalThis.fetch=savedFetch;(globalThis as any).Audio=savedAudio;(globalThis as any).window=savedWindow}
})

test('late manifests cannot start canceled lines and missing V1.2 manifest preserves old audio',async()=>{
 const savedFetch=globalThis.fetch,savedAudio=(globalThis as any).Audio,savedWindow=(globalThis as any).window
 const urls:string[]=[];let finish:((v:unknown)=>void)|undefined
 class Audio {constructor(src:string){urls.push(src)}play(){return Promise.resolve()}pause(){}}
 try{
  ;(globalThis as any).Audio=Audio;(globalThis as any).window={}
  globalThis.fetch=(async(url:any)=>!String(url).includes('./v11/')?{ok:false}:{ok:true,json:()=>new Promise(resolve=>finish=resolve)}) as any
  const voice=courseVoicePort(),events={start(){},end(){},error(){}}
  voice.speak('旧句',events);voice.cancel();await tick();finish!({'旧句':'old.mp3'});await tick()
  assert.deepEqual(urls,[])
  voice.speak('旧句',events);await tick();assert.equal(urls.at(-1),'./v11/audio/old.mp3')
 }finally{globalThis.fetch=savedFetch;(globalThis as any).Audio=savedAudio;(globalThis as any).window=savedWindow}
})
