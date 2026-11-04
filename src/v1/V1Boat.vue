<script setup lang="ts">
import {onMounted,onBeforeUnmount,ref,watch} from 'vue'
import * as T from 'three'
import {OrbitControls} from 'three/addons/controls/OrbitControls.js'
import {headingProgress} from '../v11/frameLoader'
import {createDetailedShip,disposeShip} from '../v12/workshopModel'
import {createCinematicShip,disposeCinematicShip} from '../v16/shipModel'
import type {ShipLoad} from '../v16/shipModel'
const props=defineProps<{mode?:'balance'|'rudder';initialHeading?:number;motion?:boolean;cinematic?:boolean;load?:ShipLoad}>(),emit=defineEmits<{heading:[value:number]}>()
const heading=ref(props.initialHeading??(props.mode==='rudder'?180:0)),dragging=ref(false)
const listeners=new AbortController()
let fleet:T.Group[]=[];let dragStart=0,startHeading=0
function turn(amount:number){heading.value=Math.max(0,Math.min(180,amount));for(const boat of fleet)boat.rotation.y=heading.value*Math.PI/180;emit('heading',headingProgress(heading.value))}
const host=ref<HTMLDivElement>(),focus=ref('草把扎在两舷，中央留出军士与操舟的通道。'),fault=ref(false)
let renderer:T.WebGLRenderer,controls:OrbitControls,scene:T.Scene,frame=0,resize:ResizeObserver
const textures:T.Texture[]=[]
function surface(cloth=false){const c=document.createElement('canvas');c.width=c.height=512;const x=c.getContext('2d')!;x.fillStyle=cloth?'#9d9d8e':'#9c805d';x.fillRect(0,0,512,512);let n=37;const rnd=()=>{n=(n*1664525+1013904223)>>>0;return n/4294967296};for(let i=0;i<950;i++){const y=rnd()*512;x.strokeStyle=`rgba(20,16,9,${rnd()*.2})`;x.lineWidth=.3+rnd();x.beginPath();x.moveTo(0,y);x.bezierCurveTo(150,y+rnd()*5,380,y-rnd()*5,512,y);x.stroke()}if(cloth)for(let i=0;i<512;i+=3){x.strokeStyle='#ddd9b924';x.beginPath();x.moveTo(i,0);x.lineTo(i,512);x.stroke()}const t=new T.CanvasTexture(c);t.colorSpace=T.SRGBColorSpace;t.wrapS=t.wrapT=T.RepeatWrapping;t.anisotropy=4;textures.push(t);return t}
function inspect(part:string){focus.value=({straw:'草把扎在船舷外侧。两侧都有受箭面，不能把整船通道也堵住。',hold:'青布罩住舱位。人物、桨手与回转空间要留在船内。',rudder:'艉部操舟处连着退路。前船转向，要等后船复号。'} as any)[part]}
onMounted(()=>{try{
 scene=new T.Scene();scene.background=new T.Color('#071016');const camera=new T.PerspectiveCamera(38,1,.1,100);camera.position.set(props.cinematic?9:7,props.cinematic?6.2:4.6,props.cinematic?11.2:8.8);renderer=new T.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.setSize(host.value!.clientWidth,host.value!.clientHeight);renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;renderer.outputColorSpace=T.SRGBColorSpace;renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1.35;host.value!.appendChild(renderer.domElement)
 controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.minDistance=6;controls.maxDistance=props.cinematic&&props.mode?60:20;controls.maxPolarAngle=Math.PI*.48;controls.target.set(0,props.cinematic?2:.4,0)
 if(props.mode){camera.position.set(props.cinematic?16:0,props.cinematic?18:16,props.cinematic?29:30);camera.far=220;controls.target.set(0,props.cinematic?1.5:0,props.cinematic?-12:-8);controls.enabled=false;camera.lookAt(controls.target);scene.fog=new T.FogExp2('#152d3a',.012);scene.background=new T.Color('#152d3a');renderer.setPixelRatio(Math.min(devicePixelRatio,1.25))}
 scene.add(new T.HemisphereLight(0xcbdfee,0x20180e,1.2));const key=new T.DirectionalLight(0xffe2af,3);key.position.set(-4,7,5);key.castShadow=true;key.shadow.mapSize.set(2048,2048);Object.assign(key.shadow.camera,{left:-6,right:6,top:6,bottom:-6});key.shadow.bias=-.0004;scene.add(key);const rim=new T.DirectionalLight(0x73afd2,2);rim.position.set(4,4,-5);scene.add(rim)
 const ship=props.cinematic?createCinematicShip(undefined,{load:props.load}):createDetailedShip();scene.add(ship)
 if(props.mode&&!props.cinematic){const arrows=new T.InstancedMesh(new T.CylinderGeometry(.013,.013,1.05,5),new T.MeshStandardMaterial({color:0x786344,roughness:.85}),props.mode==='rudder'?48:24);const d=new T.Object3D();for(let i=0;i<arrows.count;i++){const side=i<24?-1:1,z=-2.6+(i%24)*.22,w=.06+1.24*Math.sin(Math.PI*(z+3.5)/7);d.position.set(side*(w+.25),1.15+(i%3)*.045,z);d.rotation.set(.2,-.1,side*-.8);d.updateMatrix();arrows.setMatrixAt(i,d.matrix)}ship.add(arrows)}
 const floor=new T.Mesh(new T.PlaneGeometry(200,200),new T.ShadowMaterial({opacity:.25}));floor.rotation.x=-Math.PI/2;floor.position.y=-.3;floor.receiveShadow=true;scene.add(floor)
 fleet=[ship]
 let water:T.Mesh|undefined
 if(props.mode){
  scene.remove(floor);floor.geometry.dispose();(floor.material as T.Material).dispose()
  const wm=new T.ShaderMaterial({uniforms:{time:{value:0}},vertexShader:`varying vec3 world; void main(){vec4 p=modelMatrix*vec4(position,1.);world=p.xyz;gl_Position=projectionMatrix*viewMatrix*p;}`,fragmentShader:`uniform float time;varying vec3 world;
  void main(){vec2 p=world.xz;float w=sin(p.x*2.3+p.y*.9+time)*.14+sin(p.x*.8-p.y*3.2-time*.7)*.09;vec3 n=normalize(vec3(w,1.,cos(p.y*1.8+p.x*.6+time)*.18));vec3 v=normalize(cameraPosition-world);float fres=pow(1.-max(dot(n,v),0.),3.);vec3 color=mix(vec3(.028,.085,.115),vec3(.22,.33,.39),fres);float spec=pow(max(dot(reflect(-normalize(vec3(-.3,1.,-.5)),n),v),0.),48.);color+=spec*vec3(.5,.62,.67);float lines=pow(.5+.5*sin(p.y*12.+sin(p.x*3.+time)*2.+time),20.);color+=lines*.055;float fog=1.-exp(-length(cameraPosition-world)*.009);gl_FragColor=vec4(mix(color,vec3(.082,.16,.2),fog),1.);}`})
  water=new T.Mesh(new T.PlaneGeometry(230,230),wm);water.rotation.x=-Math.PI/2;water.position.y=-.15;scene.add(water)
  // Share actual curved hull, planks, rope and instanced fibres, rather than substituting box boats.
  const companion=props.cinematic?createCinematicShip(undefined,{lod:'fleet',load:props.load}):ship
  for(let i=1;i<20;i++){const other=props.cinematic?(i===1?companion:companion.clone(true)):ship.clone(true)
   other.position.set(i%2?6:-6,0,-Math.ceil(i/2)*8);scene.add(other);fleet.push(other)
  }
  for(const boat of fleet){const wakePoints=[];for(let j=0;j<30;j++){const a=j/29*Math.PI*2;wakePoints.push(new T.Vector3(boat.position.x+Math.cos(a)*1.45,-.13,boat.position.z+Math.sin(a)*3.8))}const wake=new T.LineLoop(new T.BufferGeometry().setFromPoints(wakePoints),new T.LineBasicMaterial({color:0x9ebcc4,transparent:true,opacity:.2}));scene.add(wake)}
  turn(heading.value)
  const ray=new T.Raycaster(),pointer=new T.Vector2(),canvas=renderer.domElement;canvas.style.touchAction='none'
  canvas.addEventListener('pointerdown',e=>{const rect=canvas.getBoundingClientRect();pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);ray.setFromCamera(pointer,camera);if(!ray.intersectObjects(fleet,true).length)return;dragging.value=true;dragStart=e.clientX;startHeading=heading.value;canvas.setPointerCapture(e.pointerId)},{signal:listeners.signal})
  canvas.addEventListener('pointermove',e=>{if(dragging.value)turn(startHeading+(e.clientX-dragStart)/canvas.clientWidth*300)},{signal:listeners.signal})
  canvas.addEventListener('pointerup',()=>dragging.value=false,{signal:listeners.signal});canvas.addEventListener('pointercancel',()=>dragging.value=false,{signal:listeners.signal})
 }
 renderer.domElement.addEventListener('webglcontextlost',e=>{e.preventDefault();fault.value=true;cancelAnimationFrame(frame)},{signal:listeners.signal})
 const size=()=>{if(!host.value)return;const w=host.value.clientWidth,h=host.value.clientHeight;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix()};resize=new ResizeObserver(size);resize.observe(host.value!);size()
 const draw=(ms=0)=>{frame=requestAnimationFrame(draw);controls.update();if(props.mode){const t=props.motion===false?0:ms;for(const [i,boat] of fleet.entries()){boat.position.y=Math.sin(t*.0014+i*.7)*.025;boat.rotation.z=Math.sin(t*.0011+i)*.008}if(water)(water.material as T.ShaderMaterial).uniforms.time.value=t*.001}renderer.render(scene,camera)};draw()
 }catch{fault.value=true}})
watch(()=>props.load,value=>{
 if(!props.cinematic||!scene||!fleet.length)return
 const old=new T.Group();for(const boat of fleet){scene.remove(boat);old.add(boat)}
 const hero=createCinematicShip(undefined,{load:value}),companion=props.mode?createCinematicShip(undefined,{lod:'fleet',load:value}):null
 fleet=old.children.map((boat,i)=>{const next=i===0?hero:i===1?companion!:companion!.clone(true);next.position.copy(boat.position);next.rotation.copy(boat.rotation);scene.add(next);return next})
 disposeCinematicShip(old)
},{deep:true})
function keydown(e:KeyboardEvent){if(!['ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();if(props.mode){turn(heading.value+(e.key==='ArrowLeft'?-15:15));return}if(scene){const ship=scene.children.find(x=>x.type==='Group');if(ship)ship.rotation.y+=e.key==='ArrowLeft'?-.15:.15}}
onBeforeUnmount(()=>{listeners.abort();cancelAnimationFrame(frame);resize?.disconnect();controls?.dispose();if(scene){(props.cinematic?disposeCinematicShip:disposeShip)(scene);scene.traverse(o=>{if(o instanceof T.DirectionalLight)o.shadow.dispose()});scene.clear()}textures.forEach(t=>t.dispose());renderer?.dispose()})
</script>
<template><div ref="host" class="v1-boat" :class="{maneuver:mode,dragging,cinematic}" tabindex="0" :aria-label="mode?'拖动船身，让二十条船转向；左右键也可转动':'立体船只，拖动或左右方向键转动'" @keydown="keydown"></div><div class="boat-parts"><template v-if="mode"><p class="heading-readout">{{mode==='balance'?'调转两舷':'转向归航'}} · 船首已转 {{Math.round(heading)}}°</p><button @click="turn(heading-15)">向左转 15°</button><button @click="turn(heading+15)">向右转 15°</button><p>{{mode==='balance'?(headingProgress(heading)>=80?'另一舷已朝向曹寨，可传转舷令。':'按住船身向右拖转，让另一舷迎向曹寨。'):(headingProgress(heading)<=35?'船首已收回返程方向，可归航。':'按住船身向左拖回，领队离开寨前水道。')}}</p></template><template v-else><button @click="inspect('straw')">两舷草把</button><button @click="inspect('hold')">舱与通道</button><button @click="inspect('rudder')">操舟位置</button><p>{{focus}}</p></template><p v-if="fault">当前设备未能打开三维画面；可用左右转向按钮完成号令。</p></div></template>
<style scoped>.v1-boat{position:absolute;inset:80px 0 60px}.boat-parts{position:absolute;left:8vw;bottom:75px;max-width:80vw;background:#07151bcd;padding:12px 18px}.boat-parts button{border-bottom:1px solid #ccb77f;padding:10px;margin-right:20px;color:#e2c894}.boat-parts p{font-size:13px;max-width:650px}.v1-boat canvas{display:block}.v1-boat.cinematic{inset:65px 0 60px}.v1-boat.cinematic+.boat-parts{bottom:65px;padding:8px 14px}.v1-boat.cinematic+.boat-parts button{padding:6px 10px}.v1-boat.cinematic+.boat-parts p{margin:6px 0}@media(max-height:650px){.v1-boat.cinematic+.boat-parts{bottom:55px;max-width:82vw}.v1-boat.cinematic+.boat-parts p{font-size:11px}}
</style>
