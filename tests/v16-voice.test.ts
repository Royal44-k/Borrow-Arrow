import test from 'node:test'
import assert from 'node:assert/strict'
import {courseVoicePort} from '../src/v1/voice.ts'
test('identical sentence selects the actual speaker, old unqualified lines remain usable',async()=>{
 const oldFetch=globalThis.fetch,oldAudio=(globalThis as any).Audio,oldWindow=(globalThis as any).window,urls:string[]=[]
 try{
  (globalThis as any).window={};(globalThis as any).Audio=class{constructor(src:string){urls.push(src)}play(){return Promise.resolve()}pause(){}}
  globalThis.fetch=(async(url:any)=>({ok:true,json:async()=>String(url).includes('./v16/')?{'曹操|收兵。':'./v16/cao.mp3','鲁肃|收兵。':'./v16/lu.mp3'}:String(url).includes('./v15/')?{'旧句':'./v15/keep.mp3'}:{}}))as any
  const port=courseVoicePort(),events={start(){},end(){},error(){}}
  port.speak('收兵。',events,'曹操');await new Promise(setImmediate);assert.equal(urls.at(-1),'./v16/cao.mp3')
  port.speak('收兵。',events,'鲁肃');await new Promise(setImmediate);assert.equal(urls.at(-1),'./v16/lu.mp3')
  port.speak('旧句',events);await new Promise(setImmediate);assert.equal(urls.at(-1),'./v15/keep.mp3')
 }finally{globalThis.fetch=oldFetch;(globalThis as any).Audio=oldAudio;(globalThis as any).window=oldWindow}
})
