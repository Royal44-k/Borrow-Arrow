<script setup lang="ts">
import {ref,onMounted,onBeforeUnmount,watch} from 'vue'
import * as T from 'three'
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js'
import {battleSchedule,arrowPose,type BattlePhase} from './battle'
const props=defineProps<{phase:BattlePhase;view:'deck'|'north';motion:boolean;audible:boolean}>()
const emit=defineEmits<{done:[];impact:[];drum:[]}>()
const host=ref<HTMLDivElement>(),paused=ref(false),elapsed=ref(0),failed=ref(false),pulse=ref(0)
let renderer:T.WebGLRenderer|undefined,scene:T.Scene,camera:T.PerspectiveCamera,raf=0,resize:ResizeObserver|undefined,ended=false,last=0,hitClock=0
let meshes:T.InstancedMesh[]=[],splashes:T.InstancedMesh,flights=battleSchedule(props.phase),hit=new Set<number>()
let trails:T.LineSegments,trailPositions:Float32Array
const length=props.phase==='warning'?5.2:props.phase==='second'?13.5:12
const dummy=new T.Object3D(),next=new T.Vector3(),axis=new T.Vector3(0,0,1),direction=new T.Vector3()
const caption=()=>props.phase==='warning'?'几支箭先落进船前的水里。':elapsed.value<3?'弓弦齐响，第一排箭越过寨墙。':elapsed.value<7?'后排接上——箭势越来越密。':'箭落草把，船舷渐沉。'
function finish(){if(ended)return;ended=true;cancelAnimationFrame(raf);emit('done')}
function drum(){if(paused.value||ended)return;pulse.value++;if(props.audible)emit('drum')}
function draw(now:number){
 if(ended||!renderer)return
 const dt=last?Math.min(.05,(now-last)/1000):0;last=now
 if(!paused.value&&!document.hidden)elapsed.value+=dt
 const time=props.motion?elapsed.value:Math.min(8,length-1)
 let splashCount=0
 for(let i=0;i<flights.length;i++){
  const a=flights[i],u=(time-a.start)/a.duration
  dummy.scale.setScalar(0)
  if(u>=0){
   const p=arrowPose(a,u),p2=arrowPose(a,Math.min(.999,Math.max(0,u)+.003))
   dummy.position.set(p.x,p.y,p.z)
   if(u<1)direction.set(p2.x-p.x,p2.y-p.y,p2.z-p.z).normalize()
   else {const before=arrowPose(a,.99);direction.set(p.x-before.x,p.y-before.y,p.z-before.z).normalize()}
   dummy.quaternion.setFromUnitVectors(axis,direction)
   if(u<1||(!a.water&&!a.flyby&&i%7===0))dummy.scale.setScalar(a.size)
   if(u>=1&&!hit.has(i)){hit.add(i);if(props.motion&&props.audible&&elapsed.value-hitClock>.13){emit('impact');hitClock=elapsed.value}}
   if(a.water&&u>=1&&u<1.35){
    const age=(u-1)/.35;dummy.updateMatrix()
    const d=new T.Object3D();d.position.set(a.ex,a.ey+.8*Math.sin(age*Math.PI),a.ez);d.scale.set(1.2*age+.05,.7*Math.sin(age*Math.PI)+.01,1);d.updateMatrix();splashes.setMatrixAt(splashCount++,d.matrix)
   }
  }
  dummy.updateMatrix();for(const m of meshes)m.setMatrixAt(i,dummy.matrix)
  const tip=arrowPose(a,Math.max(0,u)),tail=arrowPose(a,Math.max(0,u-.022));const at=i*6
  if(u>0&&u<1){trailPositions.set([tip.x,tip.y,tip.z,tail.x,tail.y,tail.z],at)}else trailPositions.fill(0,at,at+6)
 }
 trails.geometry.getAttribute('position').needsUpdate=true
 for(const m of meshes)m.instanceMatrix.needsUpdate=true
 splashes.count=splashCount;splashes.instanceMatrix.needsUpdate=true
 if(props.motion&&!paused.value){camera.position.x=Math.sin(time*12)*.014;camera.position.y=Math.sin(time*9)*.012}else{camera.position.x=0;camera.position.y=0}
 renderer.render(scene,camera)
 if(elapsed.value>=length)finish();else raf=requestAnimationFrame(draw)
}
function init(){
 if(!host.value)return
 try{
  scene=new T.Scene();scene.add(new T.HemisphereLight(0xd9eaf6,0x665440,3));const light=new T.DirectionalLight(0xe8c899,4);light.position.set(-5,8,12);scene.add(light)
  renderer=new T.WebGLRenderer({alpha:true,antialias:true,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(devicePixelRatio,1.75));renderer.setClearColor(0,0);renderer.outputColorSpace=T.SRGBColorSpace;renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1.3
  host.value.appendChild(renderer.domElement);camera=new T.PerspectiveCamera(55,1,.1,180);camera.position.set(0,0,10)
  const shaft=new T.CylinderGeometry(.012,.016,1.55,7);shaft.rotateX(Math.PI/2)
  const tip=new T.ConeGeometry(.035,.22,4);tip.rotateX(Math.PI/2);tip.translate(0,0,.84)
  const feathers=[];for(let j=0;j<3;j++){const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute([0,0,-.7,.075,0,-.65,.06,0,-.38,0,0,-.7,.06,0,-.38,0,0,-.34],3));g.computeVertexNormals();g.rotateZ(j*Math.PI*2/3);feathers.push(g)}
  const feather=mergeGeometries(feathers);feathers.forEach(g=>g.dispose())
  const parts:[T.BufferGeometry,T.MeshStandardMaterial][]=[[shaft,new T.MeshStandardMaterial({color:0x38342e,roughness:.85})],[tip,new T.MeshStandardMaterial({color:0x9da8b4,metalness:.75,roughness:.3})],[feather,new T.MeshStandardMaterial({color:0x514c43,roughness:.95,side:T.DoubleSide})]]
  meshes=parts.map(([g,m])=>{const x=new T.InstancedMesh(g,m,flights.length);x.frustumCulled=false;x.instanceMatrix.setUsage(T.DynamicDrawUsage);scene.add(x);return x})
  trailPositions=new Float32Array(flights.length*6);const trailGeometry=new T.BufferGeometry();trailGeometry.setAttribute('position',new T.BufferAttribute(trailPositions,3).setUsage(T.DynamicDrawUsage));trails=new T.LineSegments(trailGeometry,new T.LineBasicMaterial({color:0xc4c9cb,transparent:true,opacity:.22,depthWrite:false}));trails.frustumCulled=false;scene.add(trails)
  splashes=new T.InstancedMesh(new T.ConeGeometry(.13,1,5),new T.MeshBasicMaterial({color:0xd3e1e6,transparent:true,opacity:.5}),flights.length);splashes.frustumCulled=false;scene.add(splashes)
  resize=new ResizeObserver(()=>{if(!host.value||!renderer)return;const {width,height}=host.value.getBoundingClientRect();renderer.setSize(width,height);camera.aspect=width/height;camera.updateProjectionMatrix()});resize.observe(host.value)
  raf=requestAnimationFrame(draw)
 }catch{failed.value=true}
}
watch(()=>props.motion,()=>{hit.clear()})
onMounted(init)
onBeforeUnmount(()=>{ended=true;cancelAnimationFrame(raf);resize?.disconnect();for(const m of [...meshes,...(splashes?[splashes]:[])]){m.geometry.dispose();(m.material as T.Material).dispose();m.dispose()}trails?.geometry.dispose();(trails?.material as T.Material)?.dispose();renderer?.dispose();renderer?.domElement.remove()})
</script>
<template><section class="battle-barrage" :class="{still:!motion,paused}" aria-label="江上箭阵" :data-phase="phase" :data-elapsed="Math.floor(elapsed)">
 <div ref="host" class="projectile-view" aria-hidden="true"></div>
 <div class="volley-distance" aria-hidden="true"></div>
 <div class="battle-heading"><span>{{view==='north'?'江上 · 南船':'船上所见'}}</span><p aria-live="off">{{failed?'箭声沿江传来，众人伏身躲在草把后。':caption()}}</p></div>
 <div class="battle-tools"><button @click="paused=!paused" :aria-pressed="paused">{{paused?'继续箭阵':'暂停画面'}}</button><button @click="finish">略过这一阵 ›</button></div>
 <button v-if="phase!=='warning'" class="battle-drum" :disabled="paused" @click="drum" aria-label="击鼓壮声"><span :key="pulse" class="drum-ring"></span><b>鼓</b><small>击鼓壮声</small></button>
 <button v-if="failed||!motion" class="battle-static-next" @click="finish">{{failed?'继续这一幕':'看清了，继续'}} ›</button>
</section></template>
<style scoped>
.battle-barrage{position:fixed;inset:0;z-index:5;pointer-events:none;overflow:hidden}.projectile-view{position:absolute;inset:0}.projectile-view:deep(canvas){display:block;width:100%;height:100%}.battle-heading{position:absolute;top:100px;left:50%;transform:translateX(-50%);text-align:center;color:#f3ead8;text-shadow:0 2px 8px #000;max-width:50vw}.battle-heading span{font-size:12px;letter-spacing:.25em;color:#d6bc85}.battle-heading p{margin:8px 0;font-family:serif;font-size:18px}.battle-tools{position:absolute;right:25px;top:118px;display:flex;gap:8px;pointer-events:auto}.battle-tools button,.battle-static-next{background:#0b1824c9;border:1px solid #ccb37d80;border-radius:25px;padding:9px 15px;color:#f3e5c7;cursor:pointer}.battle-drum{position:absolute;right:5%;top:43%;width:108px;height:108px;pointer-events:auto;border-radius:50%;border:3px solid #ba8a49;color:#ffe4ad;background:radial-gradient(circle at 40% 35%,#865229,#342113 80%);box-shadow:0 0 50px #e3a54e20,inset 0 0 20px #120a04;cursor:pointer;isolation:isolate}.battle-drum b{font:36px serif}.battle-drum small{display:block;font-size:11px;margin-top:4px;letter-spacing:.15em}.drum-ring{position:absolute;inset:-9px;border:1px solid #e8c27d88;border-radius:50%;animation:drum-wave .7s ease-out both}.battle-static-next{position:absolute;top:56%;right:5%;pointer-events:auto}.volley-distance{position:absolute;inset:0;box-shadow:inset 0 0 110px #06141b55}.paused .drum-ring,.still .drum-ring{animation:none}@keyframes drum-wave{to{transform:scale(1.8);opacity:0}}@media(max-height:650px){.battle-heading{top:82px}.battle-heading p{font-size:15px}.battle-tools{top:130px;right:15px}.battle-drum{top:40%;width:80px;height:80px;right:3%}}@media(prefers-reduced-motion:reduce){.drum-ring{animation:none}}
</style>
