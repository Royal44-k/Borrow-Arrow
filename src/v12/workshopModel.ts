import * as T from 'three'
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js'

export type Assembly={port_straw:boolean;starboard_straw:boolean;cloth:boolean;clear_aisle:boolean}
export type AssemblyTarget=keyof Assembly
export type WorkshopItem='straw'|'cloth'|'cargo'
export const EMPTY_ASSEMBLY:Assembly=Object.freeze({port_straw:false,starboard_straw:false,cloth:false,clear_aisle:false})
export const COMPLETE_ASSEMBLY:Assembly=Object.freeze({port_straw:true,starboard_straw:true,cloth:true,clear_aisle:true})
export const WORKSHOP_TARGETS:Record<AssemblyTarget,{label:string;position:[number,number,number];item:WorkshopItem}>={
 port_straw:{label:'左舷绑草把',position:[-1.12,1.16,1.45],item:'straw'},
 starboard_straw:{label:'右舷绑草把',position:[1.12,1.16,1.45],item:'straw'},
 cloth:{label:'把青布搭上舱架',position:[0,1.54,.35],item:'cloth'},
 clear_aisle:{label:'把货箱收进艏舱',position:[.53,.63,-2.3],item:'cargo'},
}
export function assemblyReady(a:Assembly){return Object.keys(EMPTY_ASSEMBLY).every(k=>a[k as AssemblyTarget]===true)}
export function placeAssembly(a:Assembly,item:WorkshopItem,target:AssemblyTarget):Assembly{
 if(!WORKSHOP_TARGETS[target]||WORKSHOP_TARGETS[target].item!==item)throw new Error('物件与位置不合。草把缚在两舷，青布搭舱架，货箱收进艏舱。')
 return {...a,[target]:true}
}
export function removeAssembly(a:Assembly,target:AssemblyTarget):Assembly{return {...a,[target]:false}}

function grain(cloth=false):T.DataTexture{
 const size=128,data=new Uint8Array(size*size*4);let seed=725
 const rand=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296}
 for(let y=0;y<size;y++)for(let x=0;x<size;x++){
  const line=cloth?((x%3===0||y%3===0)?-.09:.045):Math.sin(y*.67+Math.sin(x*.025)*1.6)*.08+Math.sin(y*2.1+x*.03)*.035
  const v=Math.max(0,Math.min(1,.68+line+(rand()-.5)*.12)),i=(y*size+x)*4
  data[i]=Math.round(v*255);data[i+1]=Math.round(v*240);data[i+2]=Math.round(v*213);data[i+3]=255
 }
 const tx=new T.DataTexture(data,size,size);tx.needsUpdate=true;tx.wrapS=tx.wrapT=T.RepeatWrapping;tx.colorSpace=T.SRGBColorSpace;tx.minFilter=T.LinearMipmapLinearFilter;tx.generateMipmaps=true;return tx
}

/** Project-authored teaching model, not an archaeological reconstruction. Units match V1 boat. */
export function createDetailedShip(assembly:Assembly=COMPLETE_ASSEMBLY):T.Group{
 const ship=new T.Group();ship.name='detailed-grass-boat'
 const woodMap=grain(),clothMap=grain(true)
 const mats={wood:new T.MeshStandardMaterial({color:0x9b7753,map:woodMap,bumpMap:woodMap,bumpScale:.018,roughness:.68,side:T.DoubleSide}),dark:new T.MeshStandardMaterial({color:0x392c20,roughness:.85}),iron:new T.MeshStandardMaterial({color:0x3b4244,metalness:.55,roughness:.64}),rope:new T.MeshStandardMaterial({color:0x9a855e,roughness:1}),straw:new T.MeshStandardMaterial({color:0xb39b65,roughness:1}),cloth:new T.MeshStandardMaterial({color:0x345e69,map:clothMap,bumpMap:clothMap,bumpScale:.012,roughness:.94,side:T.DoubleSide}),lamp:new T.MeshStandardMaterial({color:0xd9a756,emissive:0xd17828,emissiveIntensity:.7,roughness:.8,transparent:true,opacity:.93})}
 const named=(name:string)=>{const g=new T.Group();g.name=name;ship.add(g);return g}
 const width=(z:number)=>.055+1.21*Math.pow(Math.max(0,Math.sin(Math.PI*(z+3.5)/7)),.72)
 const rise=(z:number)=>Math.pow(Math.abs(z)/3.5,4)*.43
 const add=(g:T.Group,geo:T.BufferGeometry,mat:T.Material,p:[number,number,number]=[0,0,0],rot:[number,number,number]=[0,0,0])=>{const m=new T.Mesh(geo,mat);m.position.set(...p);m.rotation.set(...rot);m.castShadow=m.receiveShadow=true;g.add(m);return m}
 const box=(g:T.Group,p:[number,number,number],s:[number,number,number],mat:T.Material)=>add(g,new T.BoxGeometry(...s),mat,p)
 const tube=(g:T.Group,pts:T.Vector3[],radius:number,mat:T.Material,segments=36)=>add(g,new T.TubeGeometry(new T.CatmullRomCurve3(pts),segments,radius,5,false),mat)
 const strakes=named('hull-strakes')
 for(const side of [-1,1])for(let band=0;band<7;band++){
  const verts:number[]=[],uv:number[]=[],ix:number[]=[];const segments=36
  for(let i=0;i<=segments;i++){const z=-3.5+i*7/segments;for(let j=0;j<2;j++){const a=(band+j*.96)/7*Math.PI/2;verts.push(side*Math.cos(a)*width(z),.62-Math.sin(a)*.9+rise(z),z);uv.push(i/segments*3,(band+j)/7)}}
  for(let i=0;i<segments;i++){const k=i*2;ix.push(k,k+2,k+1,k+1,k+2,k+3)}
  const geo=new T.BufferGeometry();geo.setAttribute('position',new T.Float32BufferAttribute(verts,3));geo.setAttribute('uv',new T.Float32BufferAttribute(uv,2));geo.setIndex(ix);geo.computeVertexNormals();add(strakes,geo,mats.wood)
 }
 const gunwale=named('gunwale')
 for(const side of [-1,1])for(const dy of [0,.15]){const pts=[];for(let i=0;i<=36;i++){const z=-3.5+i*7/36;pts.push(new T.Vector3(side*width(z),.64+rise(z)+dy,z))}tube(gunwale,pts,dy?.025:.065,mats.dark)}
 for(const z of [-3.5,3.5])tube(gunwale,[new T.Vector3(0,.15+rise(z),z),new T.Vector3(0,.85+rise(z),z),new T.Vector3(0,1.13+rise(z),z*.98)],.075,mats.wood,12)
 const deck=named('deck-planks')
 for(let i=0;i<32;i++){const z=-3.2+i*.2;box(deck,[0,.32+rise(z)*.14,z],[width(z)*1.85,.065,.187],mats.wood)}
 // Ribs are visible above the deck between the removable equipment.
 const ribs=named('deck-ribs')
 for(let i=0;i<12;i++){const z=-2.85+i*.52,w=width(z)*.92;for(const side of [-1,1])tube(ribs,[new T.Vector3(side*w,.59+rise(z),z),new T.Vector3(side*w*.94,.37,z),new T.Vector3(side*w*.68,.29,z)],.035,mats.dark,8)}
 const nails=new T.InstancedMesh(new T.SphereGeometry(.018,5,4),mats.iron,128);nails.name='plank-fasteners';const dummy=new T.Object3D()
 for(let i=0;i<128;i++){const z=-3.15+Math.floor(i/4)*.2;dummy.position.set((i%4<2?-1:1)*width(z)*(.72+(i%2)*.11),.36+rise(z)*.14,z);dummy.scale.set(1,.35,1);dummy.updateMatrix();nails.setMatrixAt(i,dummy.matrix)}ship.add(nails)
 const interior=named('interior-fittings')
 for(const z of [-1.8,1.75])box(interior,[0,.48,z],[width(z)*1.7,.1,.19],mats.wood)
 const arch=named('canopy-frame')
 for(const z of [-.55,.1,.75,1.4]){const pts=[];for(let j=0;j<=18;j++){const a=Math.PI*j/18;pts.push(new T.Vector3(Math.cos(a)*.71,.6+Math.sin(a)*.9,z))}tube(arch,pts,.034,mats.dark,18)}
 for(const x of [-.7,.7])tube(arch,[new T.Vector3(x,.62,-.6),new T.Vector3(x,.62,1.45)],.025,mats.wood,3)
 const cloth=named('cloth'),cv:number[]=[],cu:number[]=[],ci:number[]=[]
 for(let j=0;j<=18;j++)for(let i=0;i<=24;i++){const a=Math.PI*i/24;cv.push(Math.cos(a)*.735,.61+Math.sin(a)*.92-.016*Math.sin(j*Math.PI/3),-.6+j*2.1/18);cu.push(i/8,j/6)}
 for(let j=0;j<18;j++)for(let i=0;i<24;i++){const k=j*25+i;ci.push(k,k+1,k+25,k+1,k+26,k+25)}
 const cg=new T.BufferGeometry();cg.setAttribute('position',new T.Float32BufferAttribute(cv,3));cg.setAttribute('uv',new T.Float32BufferAttribute(cu,2));cg.setIndex(ci);cg.computeVertexNormals();add(cloth,cg,mats.cloth);cloth.visible=assembly.cloth
 for(const side of [-1,1]){
  const grass=named(side<0?'port_straw':'starboard_straw');grass.visible=side<0?assembly.port_straw:assembly.starboard_straw
  const stalks=new T.InstancedMesh(new T.CylinderGeometry(.008,.013,1,4),mats.straw,11*65);stalks.castShadow=true;let at=0
  const binds=new T.InstancedMesh(new T.TorusGeometry(.175,.018,5,16),mats.rope,22)
  for(let i=0;i<11;i++){const z=-2.55+i*.5,w=width(z)+.025,base=.93+rise(z)
   for(let j=0;j<65;j++){const a=j*2.39996,r=Math.sqrt(j/65)*.17;dummy.position.set(side*w+Math.cos(a)*r,base,z+Math.sin(a)*r);dummy.rotation.set(Math.sin(j)*.05,0,-side*.13);dummy.scale.set(.8+(j%3)*.1,.91+(j%9)*.025,1);dummy.updateMatrix();stalks.setMatrixAt(at,dummy.matrix);stalks.setColorAt(at,new T.Color().setHSL(.12,.25,.32+(j%7)*.035));at++}
   for(let k=0;k<2;k++){dummy.position.set(side*w,base-.19+k*.35,z);dummy.rotation.set(Math.PI/2,0,0);dummy.scale.set(1,1,1);dummy.updateMatrix();binds.setMatrixAt(i*2+k,dummy.matrix)}
  }grass.add(stalks,binds)
 }
 const rig=named('rigging');tube(rig,[new T.Vector3(0,.36,-1.35),new T.Vector3(0,2.9,-1.35)],.055,mats.wood,5)
 tube(rig,[new T.Vector3(-.86,2.57,-1.35),new T.Vector3(.86,2.57,-1.35)],.04,mats.dark,4)
 add(rig,new T.CylinderGeometry(.085,.105,1.64,10),mats.cloth,[0,2.57,-1.35],[0,0,Math.PI/2])
 for(const side of [-1,1]){tube(rig,[new T.Vector3(0,2.88,-1.35),new T.Vector3(side*.45,1.6,-2.2),new T.Vector3(side*.62,.7,-2.7)],.014,mats.rope,12);tube(rig,[new T.Vector3(0,2.88,-1.35),new T.Vector3(side*.8,.71,1.8)],.012,mats.rope,7)}
 const oars=named('oars')
 for(const side of [-1,1])for(const z of [-1.65,1.95]){
  const x=side*(width(z)-.1);tube(oars,[new T.Vector3(x,.71,z-.48),new T.Vector3(x,.75,z+.6)],.025,mats.wood,3)
  const blade=box(oars,[x,.75,z+.71],[.12,.035,.42],mats.wood);blade.rotation.y=side*.08
  add(oars,new T.TorusGeometry(.055,.013,5,12),mats.rope,[x,.72,z],[Math.PI/2,0,0])
 }
 const steering=named('steering-rudder');tube(steering,[new T.Vector3(0,.65,2.3),new T.Vector3(0,.83,3.35),new T.Vector3(0,.13,3.55)],.045,mats.wood,6);box(steering,[0,.02,3.52],[.12,.54,.43],mats.dark)
 const lanterns=named('lanterns')
 for(const [x,z] of [[.45,-2.8],[-.5,2.65]]){
  tube(lanterns,[new T.Vector3(x,.5,z),new T.Vector3(x,1.12,z),new T.Vector3(x+.12,1.17,z)],.023,mats.dark,5)
  add(lanterns,new T.CylinderGeometry(.09,.095,.23,10),mats.lamp,[x+.12,.98,z])
  for(const dy of [-.13,.13])add(lanterns,new T.CylinderGeometry(.12,.12,.035,10),mats.dark,[x+.12,.98+dy,z])
 }
 const ropeCoils=named('rope-coils')
 for(let i=0;i<5;i++)add(ropeCoils,new T.TorusGeometry(.11+i*.032,.018,5,20),mats.rope,[-.45,.4,-2.3],[Math.PI/2,0,0])
 const cargo=named('cargo');box(cargo,[0,0,0],[.72,.43,.7],mats.wood)
 for(const z of [-.31,.31]){box(cargo,[0,0,z],[.75,.46,.045],mats.dark);box(cargo,[0,.225,z],[.77,.035,.07],mats.rope)}
 cargo.position.set(assembly.clear_aisle?.52:0,.61,assembly.clear_aisle?-2.35:1.98)
 // Consolidate repeated static meshes into one draw per material per named group.
 for(const group of ship.children){if(!(group instanceof T.Group))continue;const buckets=new Map<T.Material,T.BufferGeometry[]>();const remove:T.Mesh[]=[]
  for(const child of group.children){if(!(child instanceof T.Mesh)||child instanceof T.InstancedMesh||Array.isArray(child.material))continue;child.updateMatrix();const geo=child.geometry.clone().applyMatrix4(child.matrix);for(const attr of Object.keys(geo.attributes))if(!['position','normal','uv'].includes(attr))geo.deleteAttribute(attr);if(!geo.attributes.uv)geo.setAttribute('uv',new T.Float32BufferAttribute(new Float32Array(geo.attributes.position.count*2),2));const list=buckets.get(child.material)||[];list.push(geo);buckets.set(child.material,list);remove.push(child)}
  for(const m of remove){group.remove(m);m.geometry.dispose()}
  for(const [mat,geos] of buckets){const flat=geos.map(g=>g.index?g.toNonIndexed():g);const merged=mergeGeometries(flat);if(merged){const m=new T.Mesh(merged,mat);m.castShadow=m.receiveShadow=true;group.add(m)}for(const g of new Set([...geos,...flat]))g.dispose()}
 }
 ship.userData.assembly={...assembly};return ship
}

/** Call only when this model/its shared clones are no longer used. */
export function disposeShip(ship:T.Object3D){
 const geometries=new Set<T.BufferGeometry>(),materials=new Set<T.Material>(),textures=new Set<T.Texture>()
 ship.traverse(o=>{if(!(o instanceof T.Mesh))return;if(o instanceof T.InstancedMesh)o.dispose();geometries.add(o.geometry);for(const m of Array.isArray(o.material)?o.material:[o.material]){materials.add(m);for(const value of Object.values(m))if(value instanceof T.Texture)textures.add(value)}})
 for(const g of geometries)g.dispose();for(const m of materials)m.dispose();for(const t of textures)t.dispose()
}
