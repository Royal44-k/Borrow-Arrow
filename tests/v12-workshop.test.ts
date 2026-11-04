import test from 'node:test'
import assert from 'node:assert/strict'
import * as T from 'three'
import {EMPTY_ASSEMBLY,COMPLETE_ASSEMBLY,placeAssembly,removeAssembly,assemblyReady,createDetailedShip,disposeShip} from '../src/v12/workshopModel.ts'

test('empty boat requires both sides, canopy and a clear aisle; the source snapshot stays untouched',()=>{
 let a={...EMPTY_ASSEMBLY}
 assert.equal(assemblyReady(a),false)
 for(const [item,target] of [['straw','port_straw'],['straw','starboard_straw'],['cloth','cloth'],['cargo','clear_aisle']] as const)a=placeAssembly(a,item,target)
 assert.deepEqual(a,COMPLETE_ASSEMBLY);assert.equal(assemblyReady(a),true);assert.equal(EMPTY_ASSEMBLY.port_straw,false)
})
test('wrong material or target cannot silently complete the assembly',()=>{
 assert.throws(()=>placeAssembly(EMPTY_ASSEMBLY,'cloth','port_straw'))
 assert.throws(()=>placeAssembly(EMPTY_ASSEMBLY,'straw','clear_aisle'))
 assert.throws(()=>placeAssembly(EMPTY_ASSEMBLY,'cargo','cloth'))
})
test('removing a fitted part makes the boat incomplete without erasing other work',()=>{
 const a=removeAssembly(COMPLETE_ASSEMBLY,'port_straw');assert.equal(a.port_straw,false);assert.equal(a.starboard_straw,true);assert.equal(assemblyReady(a),false)
})
test('actual three dimensional assembly changes visible groups and cargo location',()=>{
 const empty=createDetailedShip(EMPTY_ASSEMBLY),full=createDetailedShip()
 for(const name of ['port_straw','starboard_straw','cloth']){assert.equal(empty.getObjectByName(name)?.visible,false);assert.equal(full.getObjectByName(name)?.visible,true)}
 const blocked=empty.getObjectByName('cargo')!,stored=full.getObjectByName('cargo')!
 assert.notEqual(blocked.position.z,stored.position.z)
 const bounds=new T.Box3().setFromObject(full);assert(bounds.min.y>=-.32);assert(bounds.max.z-bounds.min.z<8.5)
 assert(full.getObjectByName('hull-strakes'));assert(full.getObjectByName('deck-ribs'));assert(full.getObjectByName('oars'));assert(full.getObjectByName('lanterns'))
 disposeShip(empty);disposeShip(full)
})

test('reopening uses an independent model; resource disposal deduplicates shared materials',()=>{
 const first=createDetailedShip(EMPTY_ASSEMBLY),second=createDetailedShip(EMPTY_ASSEMBLY)
 const geometries=new Set<T.BufferGeometry>(),materials=new Set<T.Material>(),textures=new Set<T.Texture>()
 let geometryDisposals=0,materialDisposals=0,textureDisposals=0,instanceCount=0,instanceDisposals=0
 first.traverse(object=>{if(!(object instanceof T.Mesh))return;if(object instanceof T.InstancedMesh){instanceCount++;object.addEventListener('dispose',()=>instanceDisposals++)}geometries.add(object.geometry);for(const material of Array.isArray(object.material)?object.material:[object.material]){materials.add(material);for(const value of Object.values(material))if(value instanceof T.Texture)textures.add(value)}})
 for(const g of geometries)g.addEventListener('dispose',()=>geometryDisposals++)
 for(const m of materials)m.addEventListener('dispose',()=>materialDisposals++)
 for(const t of textures)t.addEventListener('dispose',()=>textureDisposals++)
 const firstHull=first.getObjectByName('hull-strakes')!.children[0] as T.Mesh
 const secondHull=second.getObjectByName('hull-strakes')!.children[0] as T.Mesh
 assert.notEqual(firstHull.geometry,secondHull.geometry);assert.notEqual(firstHull.material,secondHull.material)
 disposeShip(first)
 assert.equal(geometryDisposals,geometries.size);assert.equal(materialDisposals,materials.size);assert.equal(textureDisposals,textures.size);assert.equal(instanceDisposals,instanceCount)
 assert(secondHull.geometry.getAttribute('position').count>0)
 disposeShip(second)
})
