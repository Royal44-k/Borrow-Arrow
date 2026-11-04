import * as T from 'three'
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js'
import {COMPLETE_ASSEMBLY} from '../v12/workshopModel.ts'
import type {Assembly} from '../v12/workshopModel.ts'

export type ShipLoad={port:number;starboard:number}
export type ShipOptions={lod?:'hero'|'fleet';load?:ShipLoad}
const released=new WeakSet<object>()

function textile(normal=false){
 const n=64,data=new Uint8Array(n*n*4)
 for(let y=0;y<n;y++)for(let x=0;x<n;x++){const i=(y*n+x)*4,v=normal?128:211+Math.sin(y*2.1)*10+Math.sin(x*1.8)*5;data[i]=normal?128:v;data[i+1]=normal?128:v-6;data[i+2]=normal?255:v-19;data[i+3]=255}
 const t=new T.DataTexture(data,n,n);t.wrapS=t.wrapT=T.RepeatWrapping;t.repeat.set(3,4);t.colorSpace=normal?T.NoColorSpace:T.SRGBColorSpace;t.needsUpdate=true;return t
}

/** Original mesh, in metres. Image textures enhance the real geometry; no image billboard boat. */
export function createCinematicShip(assembly:Assembly=COMPLETE_ASSEMBLY,{lod='hero',load={port:0,starboard:0}}:ShipOptions={}):T.Group{
 const hero=lod==='hero',ship=new T.Group();ship.name='cinematic-grass-boat'
 let seed=1607;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296}
 const fallback=textile(),normal=textile(true),wood=new T.MeshStandardMaterial({color:0xb49471,map:fallback,normalMap:normal,normalScale:new T.Vector2(.65,.65),roughness:.84})
 const woodTones=hero?[wood,...[0xa78b68,0xb99a75,0xa18664].map(color=>{const m=wood.clone();m.color.set(color);return m})]:[wood,wood,wood,wood]
 const dark=new T.MeshStandardMaterial({color:0x42362b,roughness:.89}),iron=new T.MeshStandardMaterial({color:0x514b3f,metalness:.55,roughness:.71}),rope=new T.MeshStandardMaterial({color:0xb19b70,roughness:1}),straw=new T.MeshStandardMaterial({color:0xd1b57b,roughness:1}),sailmat=new T.MeshStandardMaterial({color:0xe9ddba,map:fallback,normalMap:normal,normalScale:new T.Vector2(.23,.23),roughness:.97,side:T.DoubleSide}),blue=new T.MeshStandardMaterial({color:0x527b85,map:fallback,normalMap:normal,normalScale:new T.Vector2(.3,.3),roughness:.96,side:T.DoubleSide})
 const liveMaterials=[...woodTones]
 // Loading is browser-only. A late load cannot resurrect a disposed model.
 if(typeof window!=='undefined'&&typeof document!=='undefined'){
  const loader=new T.TextureLoader()
  for(const [file,kind] of [['wood-diff.jpg','map'],['wood-nor_gl.jpg','normalMap'],['wood-rough.jpg','roughnessMap']] as const){loader.load(`./v16/materials/${file}`,tx=>{
   if(ship.userData.disposed){tx.dispose();return}
   tx.wrapS=tx.wrapT=T.RepeatWrapping;tx.repeat.set(1.5,.7);tx.colorSpace=kind==='map'?T.SRGBColorSpace:T.NoColorSpace;tx.anisotropy=4
   for(const m of liveMaterials){m[kind]=tx;m.needsUpdate=true}
   ;(ship.userData.loadedTextures as T.Texture[]).push(tx)
  },undefined,()=>{/* Deterministic woven/grained fallback stays usable offline. */})}
 }
 ship.userData.loadedTextures=[];ship.userData.assembly={...assembly};ship.userData.load={...load};ship.userData.lod=lod
 const group=(name:string)=>{const g=new T.Group();g.name=name;ship.add(g);return g}
 const mesh=(g:T.Group,geo:T.BufferGeometry,mat:T.Material,p:[number,number,number]=[0,0,0],r:[number,number,number]=[0,0,0])=>{const m=new T.Mesh(geo,mat);m.position.set(...p);m.rotation.set(...r);m.castShadow=hero;m.receiveShadow=true;g.add(m);return m}
 const box=(g:T.Group,p:[number,number,number],s:[number,number,number],m:T.Material)=>mesh(g,new T.BoxGeometry(...s),m,p)
 const tube=(g:T.Group,ps:T.Vector3[],radius:number,m:T.Material,steps=hero?32:10,radial=hero?6:4)=>mesh(g,new T.TubeGeometry(new T.CatmullRomCurve3(ps),steps,radius,radial,false),m)
 const v=(x:number,y:number,z:number)=>new T.Vector3(x,y,z)
 const width=(z:number)=>.035+1.22*Math.pow(Math.max(0,Math.sin(Math.PI*(z+3.5)/7)),.64),rise=(z:number)=>Math.pow(Math.abs(z)/3.5,4)*.5
 const hull=group('hull-strakes'),segments=hero?64:18,bands=hero?9:6
 // Each strake is a closed solid ribbon; the stepped outer lip gives actual clinker thickness.
 for(const side of [-1,1])for(let band=0;band<bands;band++){
  const pos:number[]=[],uv:number[]=[],ix:number[]=[]
  for(let i=0;i<=segments;i++)for(let j=0;j<4;j++){
   const a=(band+(j%2)*1.035)/bands*Math.PI/2,z=-3.5+i*7/segments,inside=j>1
   pos.push(side*(width(z)*Math.sin(a)+(inside?-.025:.02)), -.27+1.02*(1-Math.cos(a))+rise(z)+(inside?.023:0),z);uv.push(i/segments*3,(band+j%2)*.23)
  }
  for(let i=0;i<segments;i++)for(const [a,b] of [[0,1],[1,3],[3,2],[2,0]]){const k=i*4;ix.push(k+a,k+b,k+4+a,k+b,k+4+b,k+4+a)}
  if(side<0)for(let k=0;k<ix.length;k+=3){const a=ix[k]!;ix[k]=ix[k+1]!;ix[k+1]=a}
  const geo=new T.BufferGeometry();geo.setAttribute('position',new T.Float32BufferAttribute(pos,3));geo.setAttribute('uv',new T.Float32BufferAttribute(uv,2));geo.setIndex(ix);geo.computeVertexNormals();mesh(hull,geo,woodTones[band%4]!)
 }
 const gunwale=group('gunwale'),ribs=group('deck-ribs'),deck=group('deck-planks')
 for(const side of [-1,1]){
  const points=[];for(let i=0;i<=32;i++){const z=-3.47+i*6.94/32;points.push(v(side*(width(z)+.025),.78+rise(z),z))}tube(gunwale,points,.075,dark)
  if(hero)for(const dy of [.05,-.05])tube(gunwale,points.map(p=>p.clone().add(v(0,dy,0))),.016,woodTones[2]!)
 }
 for(const z of [-3.48,3.48])tube(gunwale,[v(0,-.02,z*.99),v(0,.55,z),v(0,1.36,z*1.015)],.095,woodTones[2]!,12)
 for(let i=0;i<(hero?37:18);i++){const z=-3.15+i*(hero?.175:.36);box(deck,[0,.32+rise(z)*.12,z],[width(z)*1.88,.074,hero?.163:.345],woodTones[i%4]!)}
 for(let i=0;i<(hero?13:6);i++){
  const z=-2.85+i*(hero?.475:1.05),w=width(z)
  for(const side of [-1,1])tube(ribs,[v(side*w*.95,.76+rise(z),z),v(side*w*.88,.46,z),v(side*w*.62,.36,z)],.043,dark,hero?10:4)
 }
 const fittings=group('interior-fittings')
 for(const z of [-2.25,1.62,2.6])box(fittings,[0,.49,z],[width(z)*1.74,.1,.2],woodTones[2]!)
 // Canopy remains behind the mast, leaving the bow and afterdeck reachable.
 const frame=group('canopy-frame'),cloth=group('cloth');cloth.visible=assembly.cloth
 for(const z of [-.55,.1,.75,1.4]){const points=[];for(let i=0;i<=20;i++){const a=i/20*Math.PI;points.push(v(Math.cos(a)*.72,.61+Math.sin(a)*.94,z))}tube(frame,points,.031,dark,hero?20:8)}
 const cp:number[]=[],cu:number[]=[],ci:number[]=[],nx=hero?36:12,ny=hero?28:6
 for(let y=0;y<=ny;y++)for(let x=0;x<=nx;x++){const a=x/nx*Math.PI,z=-.6+y/ny*2.1;cp.push(Math.cos(a)*.745,.61+Math.sin(a)*.97-Math.sin(y/ny*12*Math.PI)*.025-Math.sin(a)*.025*Math.cos(x*1.7),z);cu.push(x/nx*2,y/ny*2)}
 for(let y=0;y<ny;y++)for(let x=0;x<nx;x++){const k=y*(nx+1)+x;ci.push(k,k+1,k+nx+1,k+1,k+nx+2,k+nx+1)}
 const cg=new T.BufferGeometry();cg.setAttribute('position',new T.Float32BufferAttribute(cp,3));cg.setAttribute('uv',new T.Float32BufferAttribute(cu,2));cg.setIndex(ci);cg.computeVertexNormals();mesh(cloth,cg,blue)
 const dummy=new T.Object3D()
 for(const side of [-1,1]){
  const grass=group(side<0?'port_straw':'starboard_straw');grass.visible=side<0?assembly.port_straw:assembly.starboard_straw
  const bundles=17,fibers=hero?100:12,count=bundles*fibers,stalks=new T.InstancedMesh(new T.CylinderGeometry(.006,.011,1,hero?4:3,1),straw,count),binds=new T.InstancedMesh(new T.TorusGeometry(.157,.018,hero?5:3,hero?18:8),rope,bundles*3)
  let cores:T.InstancedMesh|undefined
  if(!hero){
   // Closed packed straw silhouettes retain the volume lost when distant fibres are reduced.
   const geo=new T.CylinderGeometry(.14,.15,1.02,8,4,false),p=geo.getAttribute('position')
   for(let k=0;k<p.count;k++){
    const x=p.getX(k),y=p.getY(k),z=p.getZ(k),a=Math.atan2(z,x),end=Math.abs(y)>.5
    const taper=1+Math.sin(a*3+.4)*.055+Math.cos(a*5)*.04-Math.exp(-(((Math.abs(y)-.28)/.1)**2))*.06
    p.setXYZ(k,x*taper,y+(end?Math.sin(a*5+side)*.026:0),z*taper)
   }geo.computeVertexNormals()
   const data=new Uint8Array(64*64*4)
   for(let y=0;y<64;y++)for(let x=0;x<64;x++){const i=(y*64+x)*4,n=182+Math.sin(x*2.13)*22+Math.sin(x*.83+y*.12)*10;data[i]=n;data[i+1]=n*.85;data[i+2]=n*.56;data[i+3]=255}
   const map=new T.DataTexture(data,64,64);map.colorSpace=T.SRGBColorSpace;map.wrapS=map.wrapT=T.RepeatWrapping;map.repeat.set(2,1);map.needsUpdate=true
   cores=new T.InstancedMesh(geo,new T.MeshStandardMaterial({color:0xd6c39a,map,roughness:1}),bundles);cores.name='packed-straw-cores';cores.receiveShadow=true
   grass.add(cores)
  }
  stalks.name='individual-straw-fibers';stalks.castShadow=hero
  for(let i=0;i<bundles;i++){
   const z=-2.65+i*5.3/(bundles-1),x=side*(width(z)+.045),y=.99+rise(z)*.7
   if(cores){dummy.position.set(x,y,z);dummy.rotation.set(.02*Math.sin(i),0,-side*.12);dummy.scale.set(1+(i%3-1)*.035,.97+(i%4)*.024,1+(i%2)*.025);dummy.updateMatrix();cores.setMatrixAt(i,dummy.matrix);cores.setColorAt(i,new T.Color().setHSL(.112,.19,.77+(i%4)*.025))}
   for(let j=0;j<fibers;j++){const a=j*2.399963,r=Math.sqrt(random())*.156;dummy.position.set(x+Math.cos(a)*r,y+(random()-.5)*.12,z+Math.sin(a)*r);dummy.rotation.set((random()-.5)*.2,0,-side*(.1+random()*.07));dummy.scale.set(.65+random()*.7,.92+random()*.32,.75+random()*.55);dummy.updateMatrix();const at=i*fibers+j;stalks.setMatrixAt(at,dummy.matrix);stalks.setColorAt(at,new T.Color().setHSL(.105+random()*.028,.25+random()*.18,.32+random()*.28))}
   for(let j=0;j<3;j++){dummy.position.set(x,y-.3+j*.29,z);dummy.rotation.set(Math.PI/2,0,0);dummy.scale.set(1,1,1);dummy.updateMatrix();binds.setMatrixAt(i*3+j,dummy.matrix)}
  }grass.add(stalks,binds)
 }
 const rig=group('rigging'),battens=group('sail-battens'),sail=group('sail'),mastZ=-1.26
 tube(rig,[v(0,.35,mastZ),v(0,5.78,mastZ)],.063,woodTones[1]!,8)
 const sailPoint=(u:number,t:number)=>{
  const w=2.72-.46*t,x=(u-.48)*w,y=1.94+t*3.48
  return v(x,y,-1.34-Math.sin(u*Math.PI)*(.18+Math.sin(t*Math.PI)*.28)-Math.sin(u*18+t*8)*.022-Math.sin(t*5*Math.PI)*Math.sin(u*Math.PI)*.1)
 }
 const sp:number[]=[],su:number[]=[],si:number[]=[],sx=hero?64:12,sy=hero?80:20
 for(let j=0;j<=sy;j++)for(let i=0;i<=sx;i++){const p=sailPoint(i/sx,j/sy);sp.push(p.x,p.y,p.z);su.push(i/sx*2,j/sy*2)}
 for(let j=0;j<sy;j++)for(let i=0;i<sx;i++){const k=j*(sx+1)+i;si.push(k,k+sx+1,k+1,k+1,k+sx+1,k+sx+2)}
 const sg=new T.BufferGeometry();sg.setAttribute('position',new T.Float32BufferAttribute(sp,3));sg.setAttribute('uv',new T.Float32BufferAttribute(su,2));sg.setIndex(si);sg.computeVertexNormals();mesh(sail,sg,sailmat)
 for(let j=0;j<=5;j++){
  const ps=[];for(let i=0;i<=20;i++){const p=sailPoint(i/20,j/5);p.x+=(i/20-.5)*.22;p.z-=.036;ps.push(p)}tube(battens,ps,j===0||j===5?.035:.026,woodTones[j%4]!,hero?28:8)
  if(hero)for(const u of [.05,.45,.95]){const p=sailPoint(u,j/5);tube(rig,[p.clone().add(v(0,-.06,-.02)),p.clone().add(v(.02,.06,-.02))],.016,rope,3)}
 }
 for(const u of [0,1]){const points=[];for(let i=0;i<=24;i++)points.push(sailPoint(u,i/24));tube(rig,points,.014,rope,hero?28:8)}
 for(const side of [-1,1]){
  const ends=[v(side*.84,.77,2.3),v(side*.6,.77,-2.65)]
  for(const end of ends){const top=v(0,5.65,mastZ),mid=top.clone().lerp(end,.55).add(v(side*.06,-.12,0));tube(rig,[top,mid,end],.013,rope,hero?30:6)
   if(hero)for(let strand=0;strand<2;strand++){const points=[];for(let i=0;i<=70;i++){const t=i/70,p=top.clone().lerp(end,t);p.x+=Math.cos(t*100+strand*Math.PI)*.008;p.z+=Math.sin(t*100+strand*Math.PI)*.008;points.push(p)}tube(rig,points,.004,rope,80,3)}
  }
 }
 const oars=group('oars'),rudder=group('steering-rudder')
 for(const side of [-1,1])for(const z of [-1.9,2]){
  const x=side*(width(z)-.12);tube(oars,[v(x,.8,z-.7),v(x+side*.18,.83,z+.45),v(x+side*.2,.69,z+.95)],.031,woodTones[2]!,10)
  const blade=box(oars,[x+side*.19,.72,z+.9],[.19,.055,.6],woodTones[1]!);blade.rotation.x=.2;blade.rotation.y=side*.1
  mesh(oars,new T.TorusGeometry(.068,.015,5,12),rope,[x,.8,z],[Math.PI/2,0,0])
 }
 tube(rudder,[v(-.3,.87,2.3),v(0,.94,3.23),v(.1,-.05,3.62)],.055,woodTones[1]!,16);box(rudder,[.1,-.015,3.62],[.12,.53,.41],dark)
 const hardware=group('deck-hardware'),lanterns=group('lanterns')
 if(hero){
  const nail=new T.InstancedMesh(new T.SphereGeometry(.017,5,4),iron,148)
  for(let i=0;i<148;i++){const z=-3.15+Math.floor(i/4)*.175;dummy.position.set((i%4<2?-1:1)*width(z)*(.68+i%2*.15),.365,z);dummy.scale.set(1,.35,1);dummy.rotation.set(0,0,0);dummy.updateMatrix();nail.setMatrixAt(i,dummy.matrix)}hardware.add(nail)
  for(const side of [-1,1])for(const z of [-2.65,2.65]){mesh(hardware,new T.TorusGeometry(.09,.018,7,18),iron,[side*width(z),.84,z],[Math.PI/2,.4,0]);box(hardware,[side*width(z)*.77,.84,z],[.24,.065,.08],dark)}
  for(let i=0;i<7;i++)mesh(hardware,new T.TorusGeometry(.07+i*.025,.014,5,28),rope,[-.43,.385,-2.38],[Math.PI/2,0,0])
  for(const z of [.3,.8]){mesh(hardware,new T.CylinderGeometry(.23,.19,.47,12),woodTones[1]!,[-.42,.61,z]);for(const y of [.43,.72])mesh(hardware,new T.TorusGeometry(.222,.022,6,16),iron,[-.42,y,z],[Math.PI/2,0,0])}
 }
 const glow=new T.MeshStandardMaterial({color:0xffe0a0,emissive:0xffae43,emissiveIntensity:1.8,roughness:.6})
 for(const [x,z] of [[.42,-2.9],[-.48,2.75]]){
  tube(lanterns,[v(x,.55,z),v(x,1.34,z),v(x+.16,1.37,z)],.023,dark,8)
  mesh(lanterns,new T.CylinderGeometry(.105,.11,.28,hero?12:6),glow,[x+.16,1.12,z])
  for(const y of [.96,1.28])mesh(lanterns,new T.CylinderGeometry(.145,.145,.045,hero?12:6),dark,[x+.16,y,z])
  if(hero)for(let i=0;i<8;i++){const a=i/8*Math.PI*2;tube(lanterns,[v(x+.16+Math.cos(a)*.116,.98,z+Math.sin(a)*.116),v(x+.16+Math.cos(a)*.116,1.26,z+Math.sin(a)*.116)],.009,iron,2)}
 }
 const cargo=group('cargo');box(cargo,[0,0,0],[.72,.43,.7],woodTones[2]!)
 for(const z of [-.31,.31]){box(cargo,[0,0,z],[.75,.46,.045],dark);box(cargo,[0,.23,z],[.76,.035,.065],rope)}
 cargo.position.set(assembly.clear_aisle?.52:0,.61,assembly.clear_aisle?-2.35:1.98)
 for(const [side,key] of [[-1,'port'],[1,'starboard']] as const){
  const level=Number.isFinite(load[key])?Math.max(0,Math.min(2,Math.floor(load[key]))):0
  if(!level)continue
  const shaft=new T.CylinderGeometry(.008,.012,.94,hero?5:3),head=new T.ConeGeometry(.025,.09,4).rotateZ(Math.PI).translate(0,-.49,0)
  const feather=new T.BufferGeometry();feather.setAttribute('position',new T.Float32BufferAttribute([0,.24,0,.055,.42,0,0,.39,0,0,.24,0,-.055,.42,0,0,.39,0,0,.24,0,0,.42,.055,0,.39,0,0,.24,0,0,.42,-.055,0,.39,0],3));feather.setAttribute('uv',new T.Float32BufferAttribute(new Float32Array(24),2));feather.computeVertexNormals()
  const parts=[shaft.toNonIndexed(),head.toNonIndexed(),feather],arrowGeo=mergeGeometries(parts)!,count=level*(hero?94:28),arrows=new T.InstancedMesh(arrowGeo,dark,count);arrows.name=`${key}-received-arrows`
  for(const part of [shaft,head,...parts])part.dispose()
  for(let i=0;i<count;i++){const z=-2.55+random()*5.1;dummy.position.set(side*(width(z)+.4),1.17+random()*.33,z);dummy.rotation.set((random()-.5)*.35,random()*.3,side*-.91);dummy.scale.set(1,.83+random()*.24,1);dummy.updateMatrix();arrows.setMatrixAt(i,dummy.matrix)}
  ship.add(arrows)
 }
 // Companions share a small set of material batches; keep semantic group names for callers.
 if(!hero){const batch=group('fleet-static-batch');for(const g of [...ship.children]){if(!(g instanceof T.Group)||g===batch||['port_straw','starboard_straw','cloth','cargo'].includes(g.name))continue;for(const child of [...g.children])batch.add(child)}}
 // Merge static meshes within each named togglable part, preserving interaction contracts.
 for(const g of ship.children){if(!(g instanceof T.Group))continue;const buckets=new Map<T.Material,T.BufferGeometry[]>()
  for(const child of [...g.children]){if(!(child instanceof T.Mesh)||child instanceof T.InstancedMesh||Array.isArray(child.material))continue;child.updateMatrix();const geo=child.geometry.clone().applyMatrix4(child.matrix);const flat=geo.index?geo.toNonIndexed():geo;if(flat!==geo)geo.dispose();if(!flat.getAttribute('uv'))flat.setAttribute('uv',new T.Float32BufferAttribute(new Float32Array(flat.getAttribute('position').count*2),2));const list=buckets.get(child.material)??[];list.push(flat);buckets.set(child.material,list);child.geometry.dispose();g.remove(child)}
  for(const [m,geos] of buckets){const merged=mergeGeometries(geos);if(merged)mesh(g,merged,m);for(const geo of geos)geo.dispose()}
 }
 return ship
}

/** Dispose only after the entire scene/shared fleet has been removed. Idempotent across clones. */
export function disposeCinematicShip(root:T.Object3D){
 const dispose=(r:{dispose:()=>void})=>{if(!released.has(r)){released.add(r);r.dispose()}}
 root.traverse(o=>{
  o.userData.disposed=true
  for(const tx of (o.userData.loadedTextures??[]) as T.Texture[])dispose(tx)
  if(o instanceof T.InstancedMesh)dispose(o)
  if(o instanceof T.Mesh||o instanceof T.Line||o instanceof T.Points){dispose(o.geometry);for(const m of Array.isArray(o.material)?o.material:[o.material]){for(const value of Object.values(m))if(value instanceof T.Texture)dispose(value);dispose(m)}}
 })
}
