<script setup lang="ts">
import {onMounted,onBeforeUnmount,ref,watch} from 'vue'
import * as THREE from 'three'
import plate from '../assets/river-night.png'
const props=defineProps<{reducedMotion:boolean}>()
const host=ref<HTMLDivElement>()
let renderer:THREE.WebGLRenderer|undefined,material:THREE.ShaderMaterial,geometry:THREE.PlaneGeometry,texture:THREE.Texture
let observer:ResizeObserver,frame=0,disposed=false
onMounted(()=>{
 try{
  renderer=new THREE.WebGLRenderer({antialias:false,alpha:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.outputColorSpace=THREE.SRGBColorSpace
  host.value!.append(renderer.domElement)
  const scene=new THREE.Scene(),camera=new THREE.OrthographicCamera(-1,1,1,-1,0,1)
  texture=new THREE.TextureLoader().load(plate,()=>{if(disposed)return;material.uniforms.imageSize!.value.set(texture.image.width,texture.image.height)});texture.colorSpace=THREE.SRGBColorSpace
  material=new THREE.ShaderMaterial({depthTest:false,depthWrite:false,toneMapped:false,uniforms:{picture:{value:texture},imageSize:{value:new THREE.Vector2(1672,941)},viewport:{value:new THREE.Vector2(1,1)},time:{value:0}},vertexShader:`varying vec2 uvImage;void main(){uvImage=uv;gl_Position=vec4(position.xy,0.,1.);}`,fragmentShader:`
   varying vec2 uvImage;uniform sampler2D picture;uniform vec2 imageSize,viewport;uniform float time;
   float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
   float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1.,0.)),f.x),mix(hash(i+vec2(0.,1.)),hash(i+vec2(1.,1.)),f.x),f.y);}
   void main(){float screenAspect=viewport.x/viewport.y, imageAspect=imageSize.x/imageSize.y;vec2 scale=vec2(min(1.,screenAspect/imageAspect),min(1.,imageAspect/screenAspect));vec2 p=(uvImage-.5)*scale+.5;float y=1.-p.y;
   // One continuous image warp: fixed horizon, water motion and a separately weighted bow.
   float edge=p.x<.60?mix(1.01,.60,p.x/.60):mix(.60,.83,(p.x-.60)/.40);
   // Include a water collar above the silhouette, so the mooring post and gunwales
   // move together instead of being pinned to the feathered edge of the mask.
   float bow=smoothstep(edge-.12,edge-.05,y);float water=smoothstep(.49,.54,y)*(1.-bow);
   vec2 q=p;q.y+=bow*(sin(time*1.1)*.015+sin(time*.57)*.003);q.x+=bow*((y-.59)*sin(time*.9)*.018+sin(time*.7)*.003);
   q.x+=water*sin(y*125.+time*2.4)*.0015;q.y+=water*(sin(p.x*65.+y*150.-time*2.)*.001+sin(y*230.+time*1.3)*.0004);
   vec3 color=texture2D(picture,q).rgb;
   for(int i=0;i<7;i++){
    float k=float(i);vec2 f=i==0?vec2(.059,.254):i==1?vec2(.109,.365):i==2?vec2(.195,.386):i==3?vec2(.272,.403):i==4?vec2(.356,.392):i==5?vec2(.409,.420):vec2(.485,.465);
    vec2 d=(vec2(p.x,y)-f)*vec2(1.,1.78);float flicker=.66+.23*sin(time*(7.+k)+k*4.)+.11*sin(time*13.1+k);
    float flameSize=mix(1.,.45,k/6.);float lift=-d.y/(.052*flameSize);float sway=sin(lift*8.-time*7.+k)*.0015*flameSize*max(lift,0.);
    float width=max(.0004,(1.-clamp(lift,0.,1.))*.0038*flameSize);
    float tongue=exp(-pow((d.x+sway)/width,2.))*smoothstep(-.1,.05,lift)*(1.-smoothstep(.35+flicker*.35,1.,lift));
    float core=exp(-pow(d.x/(.0016*flameSize),2.)-pow((d.y+.005)/(.012*flameSize),2.));
    float glow=exp(-dot(d,d)/( .00022*flameSize));
    color+=vec3(1.,.24,.018)*tongue*(.45+flicker*.65)+vec3(1.,.73,.24)*core*.5+vec3(.48,.14,.018)*glow*.24*flicker;
   }
   float band=exp(-pow((y-.495-sin(p.x*7.+time*.22)*.022)/.055,2.));
   float cloud=noise(vec2(p.x*8.-time*.21,y*25.+time*.09))*.65+noise(vec2(p.x*19.-time*.39,y*51.))*.35;
   color=mix(color,vec3(.30,.38,.42),band*smoothstep(.18,.8,cloud)*.40*(1.-bow));
   gl_FragColor=vec4(color,1.);
   #include <colorspace_fragment>
  }`})
  geometry=new THREE.PlaneGeometry(2,2);scene.add(new THREE.Mesh(geometry,material))
  observer=new ResizeObserver(()=>{if(!renderer||!host.value)return;const {width,height}=host.value.getBoundingClientRect();renderer.setSize(width,height,false);material.uniforms.viewport!.value.set(width,height)});observer.observe(host.value!)
  const draw=(t:number)=>{if(disposed)return;material.uniforms.time!.value=props.reducedMotion?0:t/1000;renderer!.render(scene,camera);frame=requestAnimationFrame(draw)};frame=requestAnimationFrame(draw)
 }catch{renderer?.dispose();renderer?.domElement.remove()}
})
watch(()=>props.reducedMotion,()=>{if(material)material.uniforms.time!.value=0})
onBeforeUnmount(()=>{disposed=true;cancelAnimationFrame(frame);observer?.disconnect();texture?.dispose();material?.dispose();geometry?.dispose();renderer?.dispose();renderer?.domElement.remove()})
</script>
<template><div ref="host" class="harbor-cover" aria-hidden="true" :style="{backgroundImage:`url(${plate})`}" /></template>
<style scoped>.harbor-cover{position:absolute;inset:0;z-index:-5;pointer-events:none;background-size:cover;background-position:center}.harbor-cover :deep(canvas){display:block;width:100%;height:100%}</style>
