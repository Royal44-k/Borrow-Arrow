import {test} from 'node:test'
import assert from 'node:assert/strict'
import {previousSnapshot,nextSnapshot,musterPayload,afterVolleyArt} from '../src/v13/journey.ts'
test('back/forward moves through actual snapshots, not arithmetic node names',()=>{
 const snaps=[{index:0,node:'prepare'},{index:1,node:'signals'},{index:2,node:'weather'}]
 assert.equal(previousSnapshot(snaps,null),1)
 assert.equal(previousSnapshot(snaps,1),0)
 assert.equal(previousSnapshot(snaps,0),null)
 assert.equal(nextSnapshot(snaps,0),1)
 assert.equal(nextSnapshot(snaps,1),null)
})
test('muster requires both actual teams and matching count, not a typed arbitrary number',()=>{
 assert.equal(musterPayload({front:false,rear:true,total:20}),null)
 assert.equal(musterPayload({front:true,rear:true,total:10}),null)
 assert.deepEqual(musterPayload({front:true,rear:true,total:20}),{front_checked:true,rear_checked:true,total:20})
})
test('arrow aftermath reflects two sides only after second volley',()=>{
 assert.equal(afterVolleyArt('arrows',true),'./v13/arrows-laden.webp')
 assert.equal(afterVolleyArt('second',true),'./v13/arrows-both.webp')
 assert.equal(afterVolleyArt('arrows',false),null)
 assert.equal(afterVolleyArt('silence',true),null)
})

import {musterBackdrop} from '../src/v13/journey.ts'
test('zero-arrow muster never displays the arrow-bearing dock',()=>{assert.equal(musterBackdrop(0),'./v13/landing-empty.webp');assert.equal(musterBackdrop(50000),'./v13/muster-dock.webp');assert.equal(musterBackdrop(100000),'./v13/muster-dock.webp')})
