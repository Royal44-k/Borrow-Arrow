import test from 'node:test'
import assert from 'node:assert/strict'
import {courseVoicePort} from '../src/v1/voice.ts'
test('a new authored recording replaces only its exact text, retaining previous voices',async()=>{
 const oldFetch=globalThis.fetch,oldAudio=(globalThis as any).Audio,oldWindow=(globalThis as any).window,urls:string[]=[]
 try{(globalThis as any).window={};(globalThis as any).Audio=class{constructor(src:string){urls.push(src)}play(){return Promise.resolve()}pause(){}}
 globalThis.fetch=(async(url:any)=>({ok:true,json:async()=>String(url).includes('./v13/')?{'靠岸':'./v13/audio/new.mp3'}:String(url).includes('./v12/')?{'靠岸':'./v12/audio/old.mp3','前情':'./v12/audio/keep.mp3'}:{}})) as any
 const voice=courseVoicePort(),events={start(){},end(){},error(){}};voice.speak('靠岸',events);await new Promise(setImmediate);assert.equal(urls.at(-1),'./v13/audio/new.mp3');voice.speak('前情',events);await new Promise(setImmediate);assert.equal(urls.at(-1),'./v12/audio/keep.mp3')
 }finally{globalThis.fetch=oldFetch;(globalThis as any).Audio=oldAudio;(globalThis as any).window=oldWindow}
})
