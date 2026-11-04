import test from 'node:test'
import assert from 'node:assert/strict'
import * as geometry from '../src/sceneGeometry.ts'

test('both banks keep their cinematic plate visible without exposing hidden ship details',()=>{
 const select=(geometry as any).stageLayers
 assert.equal(typeof select,'function','stage layers must deliberately separate the plate from opaque environment meshes')
 for(const mode of ['inspect','river','drum','helm','return','fire','collect']){
  const layers=select(mode,'ship')
  assert.equal(layers.opaqueEnvironment,false)
  assert.equal(layers.neighborBoats,['river','helm','return'].includes(mode))
 }
 assert.equal(select('river','shore').opaqueEnvironment,false)
 assert.equal(select('collect','shore').opaqueEnvironment,false)
})

test('航行镜头必须有同坐标水面及浸没遮挡，独立看船则保留完整船底',()=>{
 for(const mode of ['river','drum','helm','return','fire']){
  assert.equal((geometry.stageLayers(mode,'ship') as any).contactWater,true,mode)
 }
 for(const mode of ['inspect','place','collect'])assert.equal((geometry.stageLayers(mode,'ship') as any).contactWater,false,mode)
 assert.equal((geometry.stageLayers('river','shore') as any).contactWater,true)
})
