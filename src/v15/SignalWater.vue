<script setup lang="ts">
import {ref,onMounted,onBeforeUnmount} from 'vue'
import * as T from 'three'
import {createDetailedShip,EMPTY_ASSEMBLY} from '../v12/workshopModel'
import {riverMaterial} from '../v13/riverSurface'
const props=defineProps<{positions:number[][];motion:boolean;north:boolean}>(),emit=defineEmits<{markers:[p:number[][]]}>()
const host=ref<HTMLDivElement>();let renderer:T.WebGLRenderer,scene:T.Scene,raf=0,resize:ResizeObserver
onMounted(()=>{try{
 scene=new T.Scene();scene.fog=new T.FogExp2('#152e3b',.024)
 const camera=new T.PerspectiveCamera(42,1,.1,130);camera.position.set(15,25,29);camera.lookAt(0,0,4)
 renderer=new T.WebGLRenderer({alpha:true,antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.25));renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1.3;host.value!.append(renderer.domElement)
 scene.add(new T.HemisphereLight(0xd4e7f2,0x273c43,3));const moon=new T.DirectionalLight(0xc0d9f7,3);moon.position.set(-10,20,-8);scene.add(moon)
 const water=new T.Mesh(new T.PlaneGeometry(130,130),riverMaterial());water.rotation.x=-Math.PI/2;water.position.y=-.16;scene.add(water)
 const groups=Array.from({length:2},(_,i)=>{const g=new T.Group();for(let j=0;j<3;j++){const ship=createDetailedShip(props.north?{...EMPTY_ASSEMBLY,clear_aisle:true}:undefined);ship.scale.setScalar(.72);ship.position.set((j-1)*3.4,0,j===1?0:3.4);g.add(ship)}
 const l=new T.PointLight(0xffc36a,12,8,2);l.position.set(0,2,0);g.add(l);g.position.set((props.positions[i][0]-50)*.4,0,(props.positions[i][1]-35)*.4);scene.add(g);return g})
 const size=()=>{if(!host.value)return;const {clientWidth:w,clientHeight:h}=host.value;if(!w||!h)return;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix()};resize=new ResizeObserver(size);resize.observe(host.value!);size()
 let last=0,frames=0
 function draw(ms:number){raf=requestAnimationFrame(draw);const dt=Math.min(.05,(ms-last)/1000);last=ms
 groups.forEach((g,i)=>{const p=props.positions[i],target=new T.Vector3((p[0]-50)*.4,0,(p[1]-35)*.4);g.position.lerp(target,props.motion?1-Math.exp(-dt*1.7):1);g.rotation.z=props.motion?Math.sin(ms*.0012+i)*.012:0})
 water.material.uniforms.time.value=props.motion?ms*.001:0
 if(++frames%4===0)emit('markers',groups.map(g=>{const v=g.position.clone().add(new T.Vector3(0,2.7,0)).project(camera);return [(v.x*.5+.5)*100,(-v.y*.5+.5)*100]}))
 renderer.render(scene,camera)
 }raf=requestAnimationFrame(draw)
}catch{emit('markers',props.positions)}})
onBeforeUnmount(()=>{cancelAnimationFrame(raf);resize?.disconnect();const gs=new Set<T.BufferGeometry>(),ms=new Set<T.Material>(),textures=new Set<T.Texture>();scene?.traverse((o:any)=>{if(o.geometry)gs.add(o.geometry);if(o.material)(Array.isArray(o.material)?o.material:[o.material]).forEach((m:T.Material)=>ms.add(m))});gs.forEach(g=>g.dispose());ms.forEach(m=>{for(const v of Object.values(m))if(v instanceof T.Texture)textures.add(v);m.dispose()});textures.forEach(t=>t.dispose());renderer?.dispose();renderer?.forceContextLoss();renderer?.domElement.remove()})
</script><template><div ref="host" class="signal-water"></div></template><style scoped>.signal-water{position:absolute;inset:0;pointer-events:none;mask-image:radial-gradient(ellipse at center,#000 40%,transparent 75%)}.signal-water :deep(canvas){display:block;width:100%;height:100%}</style>
