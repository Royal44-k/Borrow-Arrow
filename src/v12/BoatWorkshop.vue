<script setup lang="ts">
import {computed,onBeforeUnmount,onMounted,ref,watch} from 'vue'
import * as T from 'three'
import {OrbitControls} from 'three/addons/controls/OrbitControls.js'
import {riverMaterial} from './riverWater'
import {createCinematicShip,disposeCinematicShip} from '../v16/shipModel'
import {EMPTY_ASSEMBLY,WORKSHOP_TARGETS,assemblyReady,createDetailedShip,disposeShip,placeAssembly,removeAssembly} from './workshopModel'
import type {Assembly,AssemblyTarget,WorkshopItem} from './workshopModel'

const props=withDefaults(defineProps<{initial?:Assembly;motion?:boolean;cinematic?:boolean}>(),{motion:true})
const emit=defineEmits<{change:[Assembly];complete:[Assembly]}>()
const root=ref<HTMLElement>(),stage=ref<HTMLElement>(),assembly=ref<Assembly>({...EMPTY_ASSEMBLY,...props.initial})
const selected=ref<WorkshopItem|null>(null),message=ref('船已靠稳。先取草把绑在两舷，再搭青布，收好挡路的货箱。')
const ready=computed(()=>assemblyReady(assembly.value)),keyboardOpen=ref(false),fault=ref(''),loaded=ref(false),dragging=ref(false)
const targets=Object.entries(WORKSHOP_TARGETS).map(([id,value])=>({id:id as AssemblyTarget,...value}))
const completed=computed(()=>targets.filter(t=>assembly.value[t.id]).length)
const projected=ref<{id:AssemblyTarget;x:number;y:number;visible:boolean}[]>([])
const tools:{id:WorkshopItem;title:string;desc:string}[]=[{id:'straw',title:'取草把',desc:'绑在左、右两舷'},{id:'cloth',title:'取青布',desc:'搭上拱形舱架'},{id:'cargo',title:'搬货箱',desc:'让出船中通道'}]
const responses:Record<AssemblyTarget,string>={port_straw:'左舷草把缚好了。转过船身，看看另一舷。',starboard_straw:'右舷草把也要缚牢，不能只顾一边。',cloth:'青布已搭上舱架。人在舱内活动，从外面不易看清。',clear_aisle:'货箱收进了艏舱。船中留出路，军士才能走动、换舷。'}
let renderer:T.WebGLRenderer|undefined,scene:T.Scene|undefined,camera:T.PerspectiveCamera|undefined,controls:OrbitControls|undefined,ship:T.Group|undefined,water:T.Mesh|undefined,preview:T.Group|undefined
let raf=0,observer:ResizeObserver|undefined,alive=true,frame=0,lastTime=0,pointerStart:{x:number;y:number;id:number;fromTool:boolean}|null=null
let cameraFlight:{from:T.Vector3;to:T.Vector3;lookFrom:T.Vector3;lookTo:T.Vector3;start:number}|undefined
let cargoMotion:{from:T.Vector3;to:T.Vector3;start:number}|undefined
const partMotion=new Map<string,number>(),zones=new Map<AssemblyTarget,T.Mesh>(),ray=new T.Raycaster(),mouse=new T.Vector2(),world=new T.Vector3()
const particleObjects:T.Object3D[]=[]
const reduce=()=>!props.motion||window.matchMedia('(prefers-reduced-motion: reduce)').matches

function choose(item:WorkshopItem){
 selected.value=selected.value===item?null:item
 if(selected.value===item)message.value=item==='straw'?'拖动草把到金色挂点，或先点草把，再点船舷。另一舷在船的背面，可以转过去。':item==='cloth'?'把青布放到舱架上。舱架上的金点就是落点。':'船尾通道被货箱挡住了。把箱子搬到船头的空位。'
 syncZones()
}
function syncZones(){for(const [id,mesh] of zones)mesh.visible=!!selected.value&&!assembly.value[id]}
function install(target:AssemblyTarget){
 if(!selected.value){message.value='先取一件要布置的物件。';return}
 if(assembly.value[target]){message.value='这里已经放好了。需要调整时，可以先拆回。';return}
 try{assembly.value=placeAssembly(assembly.value,selected.value,target)}catch(e){message.value=(e as Error).message;return}
 const now=performance.now(),obj=ship?.getObjectByName(target)
 if(obj){obj.visible=true;if(!reduce()){obj.scale.setScalar(.05);partMotion.set(target,now)}}
 if(target==='clear_aisle'&&ship){const cargo=ship.getObjectByName('cargo')!;const to=new T.Vector3(.52,.61,-2.35);if(reduce())cargo.position.copy(to);else cargoMotion={from:cargo.position.clone(),to,start:now}}
 if(ship)ship.userData.assembly={...assembly.value}
 message.value=responses[target]
 if(ready.value){message.value='两舷齐备，青布搭好，通道也通了。转船检查一遍，就可以让军士登船。';selected.value=null}
 else if(target==='cloth'||target==='clear_aisle')selected.value=null
 emit('change',{...assembly.value});syncZones()
}
function remove(target:AssemblyTarget){
 assembly.value=removeAssembly(assembly.value,target);partMotion.delete(target)
 if(target==='clear_aisle'){cargoMotion=undefined;ship?.getObjectByName('cargo')?.position.set(0,.61,1.98)}
 else {const obj=ship?.getObjectByName(target);if(obj){obj.visible=false;obj.scale.setScalar(1)}}
 if(ship)ship.userData.assembly={...assembly.value}
 message.value=target==='clear_aisle'?'货箱放回了原处，通道又被挡住。':'已经拆回，可以重新布置。'
 emit('change',{...assembly.value});syncZones()
}
function finish(){if(ready.value)emit('complete',{...assembly.value})}
function view(which:'port'|'starboard'|'deck'|'whole'){
 if(!camera||!controls)return
 const positions=props.cinematic?{port:new T.Vector3(-9,5.8,8.5),starboard:new T.Vector3(9,5.8,8.5),deck:new T.Vector3(2.2,9,5),whole:new T.Vector3(9,6.4,11)}:{port:new T.Vector3(-7.2,4.7,6.8),starboard:new T.Vector3(7.2,4.7,6.8),deck:new T.Vector3(2.2,8,4.5),whole:new T.Vector3(8,6.5,9)}
 cameraFlight={from:camera.position.clone(),to:positions[which],lookFrom:controls.target.clone(),lookTo:new T.Vector3(0,props.cinematic?(which==='deck'?.7:2):.8,0),start:performance.now()}
 if(reduce()){camera.position.copy(cameraFlight.to);controls.target.copy(cameraFlight.lookTo);cameraFlight=undefined;controls.update()}
}
function setRay(clientX:number,clientY:number){
 if(!renderer||!camera)return false
 const r=renderer.domElement.getBoundingClientRect();if(clientX<r.left||clientX>r.right||clientY<r.top||clientY>r.bottom)return false
 mouse.set((clientX-r.left)/r.width*2-1,-(clientY-r.top)/r.height*2+1);ray.setFromCamera(mouse,camera);return true
}
function visibleInTree(o:T.Object3D){let p:T.Object3D|null=o;while(p){if(!p.visible)return false;p=p.parent}return true}
function modelHits(){return ship?ray.intersectObject(ship,true).filter(h=>visibleInTree(h.object)):[]}
function hitTarget(x:number,y:number):AssemblyTarget|null{
 if(!setRay(x,y))return null
 const hits=ray.intersectObjects([...zones.values()].filter(z=>z.visible),false),blocker=modelHits()[0]
 const hit=hits.find(h=>!blocker||h.distance<=blocker.distance+.12)
 return hit?(hit.object.userData.target as AssemblyTarget):null
}
function canvasDown(e:PointerEvent){if(e.button!==0)return;cameraFlight=undefined;pointerStart={x:e.clientX,y:e.clientY,id:e.pointerId,fromTool:false}}
function canvasUp(e:PointerEvent){
 if(!pointerStart||pointerStart.fromTool||pointerStart.id!==e.pointerId)return
 const tap=Math.hypot(e.clientX-pointerStart.x,e.clientY-pointerStart.y)<7;pointerStart=null
 if(!tap)return
 if(selected.value){const hit=hitTarget(e.clientX,e.clientY);if(hit)install(hit);else message.value='放到船上亮起的挂点。看不到另一边时，拖动空处转船，或按“看左舷 / 看右舷”。'}
 else if(setRay(e.clientX,e.clientY)){const hit=modelHits()[0];let obj:T.Object3D|null=hit?.object??null;while(obj&&obj!==ship){if(obj.name==='cargo'){choose('cargo');break}obj=obj.parent}}
}
function toolDown(e:PointerEvent,item:WorkshopItem){
 if(e.button!==0)return
 selected.value=item;syncZones();pointerStart={x:e.clientX,y:e.clientY,id:e.pointerId,fromTool:true}
 if(controls)controls.enabled=false
 e.preventDefault()
}
function movePointer(e:PointerEvent){
 if(!pointerStart?.fromTool||e.pointerId!==pointerStart.id)return
 if(Math.hypot(e.clientX-pointerStart.x,e.clientY-pointerStart.y)>6)dragging.value=true
 if(!dragging.value||!preview||!setRay(e.clientX,e.clientY))return
 preview.visible=true;preview.children.forEach(p=>p.visible=p.name===selected.value)
 const point=new T.Vector3();if(ray.ray.intersectPlane(new T.Plane(new T.Vector3(0,1,0),-1.5),point))preview.position.copy(point)
 const hit=hitTarget(e.clientX,e.clientY)
 for(const [id,z] of zones)(z.material as T.MeshBasicMaterial).color.set(id===hit?0xfff1ba:0xdcb96d)
}
function endPointer(e:PointerEvent){
 if(!pointerStart?.fromTool||pointerStart.id!==e.pointerId)return
 const wasDragging=dragging.value;pointerStart=null;dragging.value=false;if(preview)preview.visible=false;if(controls)controls.enabled=true
 if(wasDragging){const hit=hitTarget(e.clientX,e.clientY);if(hit)install(hit);else message.value='还没放上船。把物件送到亮起的挂点，或点一次挂点完成放置。'}
 else message.value=selected.value==='cargo'?'把货箱移到船头的空位，让出船中通道。':'物件已拿起，点船上的挂点即可放置；也可以按住物件拖过去。'
}
function cancelPointer(){pointerStart=null;dragging.value=false;if(preview)preview.visible=false;if(controls)controls.enabled=true}
function onKey(e:KeyboardEvent){if(e.key==='Escape'){selected.value=null;syncZones();cancelPointer()}}
function contextLost(e:Event){e.preventDefault();fault.value=props.cinematic?'三维画面中断。已放物件保留，可继续使用按键清单整备。':'三维画面中断了。请关闭整备窗口后重新进入；已经放好的物件仍会保留。';if(props.cinematic){keyboardOpen.value=true;loaded.value=true}cancelAnimationFrame(raf)}
function makePreview(){
 const g=new T.Group(),straw=new T.Group(),cloth=new T.Group(),cargo=new T.Group();straw.name='straw';cloth.name='cloth';cargo.name='cargo'
 const sm=new T.MeshStandardMaterial({color:0xc3b078,roughness:1}),cm=new T.MeshStandardMaterial({color:0x426c78,roughness:1}),wm=new T.MeshStandardMaterial({color:0x87613d,roughness:.8})
 for(let i=0;i<25;i++){const mesh=new T.Mesh(new T.CylinderGeometry(.009,.014,.7+(i%5)*.04,4),sm);const a=i*2.39996;mesh.position.set(Math.cos(a)*.12,0,Math.sin(a)*.12);straw.add(mesh)}
 const roll=new T.Mesh(new T.CylinderGeometry(.14,.14,.65,12),cm);roll.rotation.z=Math.PI/2;cloth.add(roll)
 const box=new T.Mesh(new T.BoxGeometry(.6,.37,.55),wm);cargo.add(box);g.add(straw,cloth,cargo);g.visible=false;return g
}
function init(){
 if(!stage.value||!alive)return
 try{
  renderer=new T.WebGLRenderer({antialias:true,alpha:false,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(window.devicePixelRatio,1.75));renderer.outputColorSpace=T.SRGBColorSpace;renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1.15;renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap
  renderer.domElement.setAttribute('aria-label','三维空船整备：拖动空处转船，滚轮缩放，选择物件后点击或拖至船上挂点。');renderer.domElement.tabIndex=0;stage.value.append(renderer.domElement)
  scene=new T.Scene();scene.background=new T.Color(0x0a1721);scene.fog=new T.Fog(0x0a1721,22,58)
  camera=new T.PerspectiveCamera(38,1,.1,90);camera.position.set(props.cinematic?9:8,props.cinematic?6.4:6.5,props.cinematic?11:9)
  controls=new OrbitControls(camera,renderer.domElement);controls.target.set(0,props.cinematic?2:.8,0);controls.enableDamping=true;controls.dampingFactor=.08;controls.enablePan=false;controls.minDistance=6;controls.maxDistance=props.cinematic?23:17;controls.minPolarAngle=.22;controls.maxPolarAngle=Math.PI*.47;controls.rotateSpeed=.6
  const sky=new T.HemisphereLight(0xb4d4e6,0x4d392b,2);scene.add(sky)
  const moon=new T.DirectionalLight(0xbad7f0,2.4);moon.position.set(-5,11,5);moon.castShadow=true;moon.shadow.mapSize.set(1024,1024);moon.shadow.camera.left=-6;moon.shadow.camera.right=6;moon.shadow.camera.top=7;moon.shadow.camera.bottom=-7;moon.shadow.bias=-.0005;scene.add(moon)
  const lamplight=new T.DirectionalLight(0xffbf75,1.65);lamplight.position.set(5,4,-4);scene.add(lamplight)
  const decklight=new T.PointLight(0xf6b65d,6,10,2);decklight.position.set(0,3,1);scene.add(decklight)
  water=new T.Mesh(new T.PlaneGeometry(90,90,36,36),riverMaterial());water.rotation.x=-Math.PI/2;water.position.y=-.15;water.receiveShadow=true;scene.add(water)
  ship=props.cinematic?createCinematicShip(assembly.value):createDetailedShip(assembly.value);scene.add(ship)
  // A modest mooring gives the boat a waterline and scale without obscuring the assembly.
  const dock=new T.Group(),dockmat=new T.MeshStandardMaterial({color:0x594737,roughness:.95})
  for(let i=0;i<18;i++){const plank=new T.Mesh(new T.BoxGeometry(1.7,.17,.3),dockmat);plank.position.set(-4,.01,-2.6+i*.31);plank.receiveShadow=true;dock.add(plank)}
  for(const z of [-2.5,2.5]){const post=new T.Mesh(new T.CylinderGeometry(.12,.14,1.2,10),dockmat);post.position.set(-3.24,-.12,z);dock.add(post)}scene.add(dock);particleObjects.push(dock)
  preview=makePreview();scene.add(preview)
  for(const target of targets){
   const sphere=new T.Mesh(new T.SphereGeometry(.19,12,10),new T.MeshBasicMaterial({color:0xdcb96d,transparent:true,opacity:.62,depthWrite:false}));sphere.position.set(...target.position);sphere.userData.target=target.id;sphere.visible=false;scene.add(sphere);zones.set(target.id,sphere)
  }
  renderer.domElement.addEventListener('pointerdown',canvasDown);renderer.domElement.addEventListener('pointerup',canvasUp);renderer.domElement.addEventListener('webglcontextlost',contextLost)
  observer=new ResizeObserver(()=>resize());observer.observe(stage.value);resize();syncZones();loaded.value=true
  tick(performance.now())
 }catch(e){fault.value=props.cinematic?'当前设备未能打开三维画面。可用左侧“按键布置 / 拆回”逐项整备，完成后继续。':'当前设备未能打开三维画面。请关闭整备窗口后重试，或在支持 WebGL 的浏览器中打开。';if(props.cinematic){keyboardOpen.value=true;loaded.value=true}console.error('BoatWorkshop renderer initialization failed',e)}
}
function resize(){if(!renderer||!camera||!stage.value)return;const {width,height}=stage.value.getBoundingClientRect();if(!width||!height)return;renderer.setSize(width,height);camera.aspect=width/height;camera.updateProjectionMatrix()}
function animateParts(now:number){
 for(const [name,start] of partMotion){const obj=ship?.getObjectByName(name);if(!obj){partMotion.delete(name);continue}const t=Math.min(1,(now-start)/450);obj.scale.setScalar(.05+.95*(1-(1-t)**3));if(t===1)partMotion.delete(name)}
 if(cargoMotion&&ship){const t=Math.min(1,(now-cargoMotion.start)/850),p=ship.getObjectByName('cargo')!;p.position.lerpVectors(cargoMotion.from,cargoMotion.to,t*t*(3-2*t));p.position.y+=Math.sin(t*Math.PI)*.32;if(t===1)cargoMotion=undefined}
}
function projectLabels(){
 if(!camera||!renderer||!stage.value)return
 const w=stage.value.clientWidth,h=stage.value.clientHeight
 projected.value=targets.map(t=>{world.set(...t.position);const dir=world.clone().sub(camera!.position),distance=dir.length();ray.set(camera!.position,dir.normalize());const first=modelHits()[0];const uncovered=!first||first.distance>distance-.22;world.project(camera!);return {id:t.id,x:(world.x+1)*w/2,y:(1-world.y)*h/2,visible:!!selected.value&&!assembly.value[t.id]&&WORKSHOP_TARGETS[t.id].item===selected.value&&uncovered&&world.z>-1&&world.z<1&&Math.abs(world.x)<.96&&Math.abs(world.y)<.88}})
}
function tick(now:number){
 if(!alive||!renderer||!scene||!camera||!controls)return
 const dt=Math.min(.05,(now-lastTime)/1000||.016);lastTime=now
 if(cameraFlight){const t=Math.min(1,(now-cameraFlight.start)/650),s=t*t*(3-2*t);camera.position.lerpVectors(cameraFlight.from,cameraFlight.to,s);controls.target.lerpVectors(cameraFlight.lookFrom,cameraFlight.lookTo,s);if(t===1)cameraFlight=undefined}
 controls.update();animateParts(now)
 if(water)(water.material as T.ShaderMaterial).uniforms.time.value=reduce()?0:now*.001
 if(water&&!reduce()){
  const pos=water.geometry.getAttribute('position');for(let i=0;i<pos.count;i++)pos.setZ(i,Math.sin(pos.getX(i)*1.5+now*.0007)*.024+Math.sin(pos.getY(i)*.6+now*.0005)*.018);pos.needsUpdate=true
 }
 // Keep the ship's attachment zones fixed to the same model; water moves under it.
 for(const [id,z] of zones){const mat=z.material as T.MeshBasicMaterial;mat.opacity=selected.value&&WORKSHOP_TARGETS[id].item===selected.value?.7:.18;if(!reduce())z.scale.setScalar(1+Math.sin(now*.003)*.07)}
 if(++frame%4===0||dt>.04)projectLabels()
 renderer.render(scene,camera);raf=requestAnimationFrame(tick)
}
watch(()=>props.initial,value=>{if(!value)return;assembly.value={...EMPTY_ASSEMBLY,...value};partMotion.clear();cargoMotion=undefined;for(const id of ['port_straw','starboard_straw','cloth'] as const){const p=ship?.getObjectByName(id);if(p){p.visible=assembly.value[id];p.scale.setScalar(1)}}ship?.getObjectByName('cargo')?.position.set(assembly.value.clear_aisle?.52:0,.61,assembly.value.clear_aisle?-2.35:1.98);syncZones()},{deep:true})
onMounted(()=>{window.addEventListener('pointermove',movePointer);window.addEventListener('pointerup',endPointer);window.addEventListener('pointercancel',cancelPointer);root.value?.addEventListener('keydown',onKey);init();emit('change',{...assembly.value})})
onBeforeUnmount(()=>{
 alive=false;cancelAnimationFrame(raf);observer?.disconnect();window.removeEventListener('pointermove',movePointer);window.removeEventListener('pointerup',endPointer);window.removeEventListener('pointercancel',cancelPointer);root.value?.removeEventListener('keydown',onKey)
 if(renderer){renderer.domElement.removeEventListener('pointerdown',canvasDown);renderer.domElement.removeEventListener('pointerup',canvasUp);renderer.domElement.removeEventListener('webglcontextlost',contextLost)}controls?.dispose()
 if(scene){scene.traverse(o=>{if(o instanceof T.DirectionalLight||o instanceof T.PointLight||o instanceof T.SpotLight)o.shadow.dispose()});(props.cinematic?disposeCinematicShip:disposeShip)(scene);scene.clear()}renderer?.dispose();renderer?.forceContextLoss();renderer?.domElement.remove();zones.clear();partMotion.clear();particleObjects.length=0
})
</script>

<template>
 <section ref="root" :class="{cinematic}" class="boat-workshop" aria-label="草船整备工坊" data-testid="boat-workshop">
  <div ref="stage" class="workshop-stage" :class="{'is-dragging':dragging}" />
  <div class="workshop-vignette" aria-hidden="true" />
  <header class="workshop-title"><span>南岸 · 整备码头</span><h2>空船待发，亲手布置</h2><p>拖动空处转船 · 滚轮或双指缩放</p></header>
  <aside class="workshop-tools" aria-label="整备物件">
   <span class="tools-label">从这里取用</span>
   <button v-for="tool in tools" :key="tool.id" type="button" :class="{chosen:selected===tool.id}" :aria-pressed="selected===tool.id" @pointerdown="toolDown($event,tool.id)" @click="$event.detail===0 && choose(tool.id)">
    <span class="tool-drawing" :class="tool.id" aria-hidden="true"><i/><i/><i/><i/><i/></span><span><strong>{{tool.title}}</strong><small>{{tool.desc}}</small></span>
   </button>
   <p class="tool-hint">按住物件拖上船<br>或点物件，再点挂点</p>
   <button class="keyboard-toggle" type="button" :aria-expanded="keyboardOpen" @click="keyboardOpen=!keyboardOpen">{{keyboardOpen?'收起位置清单':'按键布置 / 拆回'}}</button>
   <div v-if="keyboardOpen" class="keyboard-targets">
    <button v-for="target in targets" :key="target.id" type="button" @click="assembly[target.id]?remove(target.id):install(target.id)">{{assembly[target.id]?'拆回':'放置'}} · {{target.label}}</button>
   </div>
  </aside>
  <div class="projected-targets" aria-label="船上挂点">
   <button v-for="p in projected.filter(p=>p.visible)" :key="p.id" type="button" :style="{left:p.x+'px',top:p.y+'px'}" @pointerdown.stop @click="install(p.id)"><span class="target-dot"/><span>{{WORKSHOP_TARGETS[p.id].label}}</span></button>
  </div>
  <aside class="workshop-check" aria-label="整备检查">
   <h3>登船前查看</h3>
   <div v-for="t in targets" :key="t.id" :class="{done:assembly[t.id]}"><span aria-hidden="true">{{assembly[t.id]?'✓':'○'}}</span>{{t.id==='port_straw'?'左舷草把':t.id==='starboard_straw'?'右舷草把':t.id==='cloth'?'青布遮舱':'通道畅通'}}<button v-if="assembly[t.id]" type="button" :aria-label="'拆回'+t.label" @click="remove(t.id)">拆回</button></div>
   <p>{{completed}} / 4 处已备妥</p>
  </aside>
  <div class="workshop-camera" aria-label="查看船身">
   <button type="button" @click="view('port')">看左舷</button><button type="button" @click="view('starboard')">看右舷</button><button type="button" @click="view('deck')">看船舱</button><button type="button" @click="view('whole')">全船</button>
  </div>
  <footer class="workshop-footer"><p role="status" aria-live="polite">{{message}}</p><button type="button" :disabled="!ready||(!cinematic&&!!fault)||!loaded" @click="finish">检查完毕，让军士登船 <span aria-hidden="true">→</span></button></footer>
  <div v-if="fault" class="workshop-fault" role="alert"><strong>三维画面暂不可用</strong><p>{{fault}}</p></div>
  <div v-else-if="!loaded" class="workshop-loading" role="status">正在泊船，点亮码头……</div>
 </section>
</template>

<style scoped>
.boat-workshop{position:absolute;inset:0;overflow:hidden;background:#091821;color:#ecdfc3;font-family:'Noto Serif SC','SimSun',serif;isolation:isolate}.workshop-stage{position:absolute;inset:0;touch-action:none}.workshop-stage :deep(canvas){display:block;width:100%;height:100%;outline-offset:-4px;cursor:grab}.workshop-stage.is-dragging :deep(canvas){cursor:grabbing}.workshop-vignette{position:absolute;inset:0;pointer-events:none;background:linear-gradient(90deg,rgba(4,13,18,.88),transparent 27%,transparent 75%,rgba(4,13,18,.6)),linear-gradient(0deg,rgba(4,13,18,.95),transparent 29%,transparent 71%,rgba(4,13,18,.65));z-index:1}.workshop-title{position:absolute;left:32px;top:70px;pointer-events:none;z-index:2}.workshop-title>span{font-size:12px;letter-spacing:.25em;color:#bb9d68}.workshop-title h2{font-size:24px;font-weight:500;letter-spacing:.12em;margin:8px 0}.workshop-title p{font-size:12px;color:#aeb9b9;margin:0}.workshop-tools{position:absolute;left:28px;top:192px;width:180px;z-index:4;max-height:calc(100% - 370px);overflow-y:auto;scrollbar-width:thin}.tools-label{font-size:11px;color:#b8a687;letter-spacing:.2em;display:block;margin-bottom:10px}.workshop-tools>button:not(.keyboard-toggle){width:100%;display:flex;align-items:center;gap:12px;text-align:left;background:linear-gradient(90deg,rgba(13,29,34,.92),rgba(13,29,34,.08));border:0;border-left:2px solid #58696a;color:inherit;min-height:66px;margin-bottom:10px;padding:8px 5px;cursor:grab;touch-action:none;user-select:none}.workshop-tools>button.chosen{border-left-color:#e0bd78;background:linear-gradient(90deg,#514326b3,transparent)}.workshop-tools strong{display:block;font-size:15px;font-weight:500}.workshop-tools small{display:block;font:11px/1.8 system-ui,sans-serif;color:#b3bdbb}.tool-drawing{display:block;position:relative;width:44px;height:42px;flex-shrink:0}.tool-drawing.straw{transform:rotate(-18deg)}.tool-drawing.straw i{position:absolute;left:12px;top:3px;height:36px;width:4px;background:linear-gradient(90deg,#4f412b,#c1a665,#806b3f);border-radius:2px}.tool-drawing.straw i:nth-child(2){left:17px;top:0}.tool-drawing.straw i:nth-child(3){left:22px;top:3px}.tool-drawing.straw i:nth-child(4){left:27px;top:1px}.tool-drawing.straw i:nth-child(5){left:10px;top:17px;width:25px;height:6px;background:#443e31;border-top:1px solid #ba9f70;border-bottom:1px solid #ba9f70}.tool-drawing.cloth{background:repeating-linear-gradient(85deg,#2c4850 0,#6d8d90 4px,#3d5c66 8px);height:27px;margin-top:5px;transform:skewY(-8deg);border-radius:4px 10px 7px 4px;box-shadow:inset 0 -5px 8px #152d38}.tool-drawing.cargo{width:36px;height:32px;margin:4px;background:repeating-linear-gradient(0deg,#795d3d 0,#5d452b 6px,#b39161 8px);box-shadow:4px -4px 0 #4a3928;transform:skewY(8deg);border:2px solid #b7a17b}.tool-drawing.cargo:after{content:'';position:absolute;left:8px;width:5px;height:100%;background:#b1a180}.tool-hint{font:11px/1.7 system-ui,sans-serif;color:#aab6b5;margin:12px 0}.keyboard-toggle{background:none;border:0;border-bottom:1px solid #6b6757;padding:6px 0;color:#c4b791;font-size:12px;cursor:pointer}.keyboard-targets{display:grid;gap:5px;margin-top:8px}.keyboard-targets button{background:#132831;color:#d6dccf;border:1px solid #45575c;padding:8px;text-align:left;font-size:12px;cursor:pointer}.projected-targets{position:absolute;inset:0;pointer-events:none;z-index:3}.projected-targets button{position:absolute;transform:translate(-50%,-50%);display:flex;flex-direction:column;align-items:center;gap:7px;background:none;border:0;color:#f4d68f;font:13px/1.5 inherit;text-shadow:0 2px 5px #000;cursor:pointer;pointer-events:auto;min-width:90px;min-height:52px}.projected-targets button>span:last-child{padding:3px 8px;border-radius:2px;background:#07161dba}.target-dot{width:17px;height:17px;border:1px solid #efd390;border-radius:50%;background:#dcc48a66;box-shadow:0 0 0 7px #cfa85d26,0 0 20px #e5c18173}.workshop-check{position:absolute;right:26px;top:170px;width:166px;z-index:4;pointer-events:auto}.workshop-check h3{font-size:12px;font-weight:400;color:#a8b7b4;letter-spacing:.16em;margin:0 0 15px}.workshop-check>div{font-size:13px;display:flex;align-items:center;gap:9px;color:#939f9d;min-height:34px}.workshop-check>div.done{color:#ddc695}.workshop-check>div>span{width:12px}.workshop-check>div>button{margin-left:auto;background:none;border:0;color:#a4b4b3;font-size:11px;padding:5px;cursor:pointer}.workshop-check>p{font:11px system-ui,sans-serif;color:#8e9e9e;margin-top:12px}.workshop-camera{position:absolute;left:50%;bottom:172px;transform:translateX(-50%);display:flex;gap:6px;z-index:4;white-space:nowrap}.workshop-camera button{border:1px solid #60727480;background:#0c1d25c7;color:#c4d2d0;border-radius:20px;padding:8px 14px;font-size:12px;cursor:pointer;backdrop-filter:blur(8px)}.workshop-footer{position:absolute;left:28px;right:28px;bottom:70px;z-index:4;display:flex;align-items:center;justify-content:space-between;gap:28px;border-top:1px solid #96a4a329;padding-top:15px}.workshop-footer p{font-size:14px;line-height:1.8;max-width:660px;margin:0;color:#d2d5c8}.workshop-footer>button{flex-shrink:0;border:1px solid #c4a569;background:#79613457;color:#f0d8a4;padding:14px 20px;border-radius:2px;cursor:pointer;font:14px inherit;white-space:nowrap}.workshop-footer>button>span{margin-left:18px}.workshop-footer>button:disabled{opacity:.4;cursor:not-allowed}.workshop-fault,.workshop-loading{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);max-width:460px;padding:30px;background:#101e27;border:1px solid #6c746b;z-index:10;color:#ded6c0;line-height:1.8}.boat-workshop button:focus-visible{outline:2px solid #f4dc9c;outline-offset:4px}.boat-workshop button:not(:disabled):hover{filter:brightness(1.2)}
@media(max-height:760px){.workshop-title{top:66px}.workshop-title h2{font-size:20px}.workshop-tools{top:162px;max-height:calc(100% - 330px)}.workshop-tools>button:not(.keyboard-toggle){min-height:56px;margin-bottom:7px}.workshop-check{top:160px}.workshop-camera{bottom:155px}.workshop-footer{bottom:65px}.workshop-footer p{font-size:12px;max-width:570px}.workshop-footer>button{padding:12px}.tool-hint{margin:6px 0}}
@media(max-width:900px){.workshop-title{left:20px}.workshop-tools{left:16px;width:147px}.workshop-tools>button:not(.keyboard-toggle){gap:6px}.workshop-check{right:16px;width:142px}.workshop-footer{left:20px;right:20px;gap:12px}.workshop-footer p{font-size:12px;max-width:50%}.workshop-footer>button{font-size:12px}.workshop-camera button{padding:7px 10px}.workshop-title h2{font-size:19px}}
@media(max-width:600px){.workshop-title{top:64px}.workshop-title h2{font-size:18px}.workshop-title p{font-size:10px}.workshop-tools{top:150px;width:120px}.workshop-tools strong{font-size:13px}.workshop-tools small{font-size:10px}.tool-drawing{width:28px;transform:scale(.8);transform-origin:left center}.workshop-check{top:150px;width:116px;right:10px}.workshop-check>div{font-size:11px;gap:5px}.workshop-check h3{font-size:11px}.workshop-footer{display:block;bottom:65px;padding-top:8px}.workshop-footer p{max-width:none;min-height:38px;font-size:11px}.workshop-footer>button{display:block;width:100%;padding:9px;margin-top:7px}.workshop-camera{bottom:190px}.workshop-camera button{font-size:10px;padding:6px 8px}.workshop-tools{max-height:calc(100% - 375px)}.projected-targets button{font-size:11px}.keyboard-toggle{font-size:10px}.tool-hint{font-size:10px}}
.cinematic .workshop-fault{top:95px;max-width:400px;padding:12px 18px;font-size:12px;pointer-events:none}.cinematic .workshop-fault strong{display:none}
@media(max-height:650px){.cinematic .workshop-title{top:64px}.cinematic .workshop-tools{top:150px;max-height:calc(100% - 280px)}.cinematic .workshop-check{top:150px}.cinematic .workshop-camera{bottom:135px}.cinematic .workshop-footer{bottom:55px}.cinematic .workshop-tools>button:not(.keyboard-toggle){min-height:44px;margin-bottom:4px}.cinematic .tool-hint{display:none}}
</style>
