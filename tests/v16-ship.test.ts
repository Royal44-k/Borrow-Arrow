import test from 'node:test'
import assert from 'node:assert/strict'
import * as T from 'three'
import {readFileSync} from 'node:fs'
import {OrbitControls} from 'three/addons/controls/OrbitControls.js'
import {EMPTY_ASSEMBLY, COMPLETE_ASSEMBLY} from '../src/v12/workshopModel.ts'

// A missing factory is an explicit RED assertion, rather than a module-load error.
const model = await import('../src/v16/shipModel.ts').catch(()=>null)
test('cinematic maneuver keeps its wide camera across disabled OrbitControls updates; other views retain the legacy limit',()=>{
 const source=readFileSync(new URL('../src/v1/V1Boat.vue',import.meta.url),'utf8')
 const expression=source.match(/controls\.maxDistance=([^;]+)/)?.[1];assert(expression)
 const limit=(props:{cinematic?:boolean;mode?:'balance'|'rudder'})=>Function('props',`return ${expression}`)(props) as number
 for(const mode of ['balance','rudder'] as const){
  const camera=new T.PerspectiveCamera(38,1024/600,.1,220),controls=new OrbitControls(camera)
  camera.position.set(16,18,29);controls.target.set(0,1.5,-12);controls.enabled=false;controls.minDistance=6;controls.maxDistance=limit({cinematic:true,mode})
  const expected=camera.position.clone();for(let i=0;i<4;i++)controls.update()
  assert(camera.position.distanceTo(expected)<1e-8,`${mode} preset was pulled toward the fleet`)
  assert.equal(limit({mode}),20) // No DOM was connected, so there are no event listeners to dispose.
 }
 assert.equal(limit({}),20);assert.equal(limit({cinematic:true}),20)
})
test('cinematic model factory is present',()=>assert.equal(typeof model?.createCinematicShip,'function'))
test('empty assembly preserves removable named parts and the real movable cargo',()=>{
 assert(model);const empty=model.createCinematicShip(EMPTY_ASSEMBLY),full=model.createCinematicShip(COMPLETE_ASSEMBLY)
 for(const name of ['port_straw','starboard_straw','cloth']){assert.equal(empty.getObjectByName(name)?.visible,false);assert.equal(full.getObjectByName(name)?.visible,true)}
 assert.equal(empty.getObjectByName('cargo')?.position.z,1.98);assert.equal(full.getObjectByName('cargo')?.position.z,-2.35)
 model.disposeCinematicShip(empty);model.disposeCinematicShip(full)
})
test('original hull has thickness, UVs, tall battened sail and water contact',()=>{
 assert(model);const ship=model.createCinematicShip(),box=new T.Box3().setFromObject(ship)
 assert(box.min.y<-.15&&box.min.y>-.4);assert(box.max.y>5.4&&box.max.y<6.2)
 assert(box.max.z-box.min.z<8.4)
 for(const name of ['hull-strakes','deck-ribs','sail','sail-battens','rigging','oars','lanterns'])assert(ship.getObjectByName(name),name)
 const hull=ship.getObjectByName('hull-strakes')!.children[0] as T.Mesh
 assert(hull.geometry.getAttribute('uv').count>100);assert(hull.material instanceof T.MeshStandardMaterial)
 assert((hull.material as T.MeshStandardMaterial).normalMap)
 model.disposeCinematicShip(ship)
})
test('only server-loaded sides carry arrows, including companion LOD',()=>{
 assert(model)
 for(const lod of ['hero','fleet'] as const){const empty=model.createCinematicShip(undefined,{lod,load:{port:0,starboard:0}}),one=model.createCinematicShip(undefined,{lod,load:{port:1,starboard:0}}),two=model.createCinematicShip(undefined,{lod,load:{port:1,starboard:2}})
 assert.equal(empty.getObjectByName('port-received-arrows'),undefined);assert.equal(one.getObjectByName('starboard-received-arrows'),undefined)
 const port=one.getObjectByName('port-received-arrows') as T.InstancedMesh,starboard=two.getObjectByName('starboard-received-arrows') as T.InstancedMesh
 assert(port.count>0);assert(starboard.count>port.count)
 for(const s of [empty,one,two])model.disposeCinematicShip(s)}
})
test('fleet geometry is substantially cheaper than the hero and geometry is deterministic in Node',()=>{
 assert(model);const a=model.createCinematicShip(),b=model.createCinematicShip(),low=model.createCinematicShip(undefined,{lod:'fleet'})
 const count=(g:T.Group)=>{let n=0;g.traverse(o=>{if(o instanceof T.Mesh)n+=(o.geometry.index?.count??o.geometry.getAttribute('position').count)*(o instanceof T.InstancedMesh?o.count:1)});return n}
 assert(count(low)<count(a)*.3);assert.equal(count(a),count(b))
 for(const s of [a,b,low])model.disposeCinematicShip(s)
})
test('fleet straw bundles have closed opaque packed centers between bindings, rather than hollow cages',()=>{
 assert(model);const ship=model.createCinematicShip(undefined,{lod:'fleet'});ship.updateMatrixWorld(true)
 for(const name of ['port_straw','starboard_straw']){
  const side=ship.getObjectByName(name)!,core=side.getObjectByName('packed-straw-cores') as T.InstancedMesh
  assert(core instanceof T.InstancedMesh,`${name} needs packed straw volume`);assert.equal(core.count,17)
  assert(core.material instanceof T.MeshStandardMaterial);assert.equal((core.material as T.MeshStandardMaterial).transparent,false)
  const matrix=new T.Matrix4(),center=new T.Vector3();core.getMatrixAt(8,matrix);center.setFromMatrixPosition(matrix)
  // Crossing the middle of a bundle must hit the straw itself, away from its three rope rings.
  const ray=new T.Raycaster(center.clone().add(new T.Vector3(1,.13,0)),new T.Vector3(-1,0,0),0,2)
  assert(ray.intersectObject(core,false).length>0,`${name} bundle must occlude water/wood behind it`)
 }
 model.disposeCinematicShip(ship)
})
test('disposing a shared fleet once releases each geometry, material and texture exactly once',()=>{
 assert(model);const scene=new T.Group(),ship=model.createCinematicShip();scene.add(ship,ship.clone(true))
 const resources=new Set<T.BufferGeometry|T.Material|T.Texture>();let disposed=0
 scene.traverse(o=>{if(o instanceof T.Mesh){resources.add(o.geometry);for(const m of Array.isArray(o.material)?o.material:[o.material]){resources.add(m);for(const v of Object.values(m))if(v instanceof T.Texture)resources.add(v)}}})
 for(const r of resources)r.addEventListener('dispose',()=>disposed++)
 model.disposeCinematicShip(scene);model.disposeCinematicShip(scene);assert.equal(disposed,resources.size)
})
