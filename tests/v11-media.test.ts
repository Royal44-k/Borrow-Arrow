import {test} from 'node:test'
import assert from 'node:assert/strict'
import {FrameLoader,headingProgress} from '../src/v11/frameLoader.ts'
test('a rejected next frame leaves last visible frame untouched',async()=>{
 const loader=new FrameLoader<string>();let visible='river';
 assert.equal(await loader.load('bad',async()=>{throw Error('offline')},x=>visible=x),'failed');assert.equal(visible,'river')
})
test('slow obsolete image cannot overwrite newer decoded scene',async()=>{
 const loader=new FrameLoader<string>();let release!:(x:string)=>void,visible='river';
 const slow=loader.load('a',()=>new Promise(r=>release=r),x=>visible=x)
 await loader.load('b',async()=> 'shore',x=>visible=x);release('obsolete');
 assert.equal(await slow,'stale');assert.equal(visible,'shore')
})
test('boat heading maps actual yaw to bounded server command',()=>{
 assert.equal(headingProgress(0),0);assert.equal(headingProgress(180),100);assert.equal(headingProgress(-12),0);assert.equal(headingProgress(240),100);assert.equal(headingProgress(90),50)
})
