<script setup lang="ts">
import {ref,onMounted,onBeforeUnmount} from 'vue'
const props=defineProps<{motion:boolean;second?:boolean}>(),emit=defineEmits<{done:[];impact:[]}>()
const canvas=ref<HTMLCanvasElement>();let frame=0,start=0,finished=false,lastHit=-1
const duration=9500
function finish(){if(finished)return;finished=true;cancelAnimationFrame(frame);emit('done')}
onMounted(()=>{const c=canvas.value!,x=c.getContext('2d')!;let w=0,h=0
 const draw=(now:number)=>{if(!start)start=now;const age=now-start;if(age>=duration){finish();return}frame=requestAnimationFrame(draw)
 if(w!==innerWidth||h!==innerHeight){w=c.width=innerWidth;h=c.height=innerHeight}x.clearRect(0,0,w,h)
 const origin={x:w*(props.second?.25:.77),y:h*.29};const wave=Math.floor(age/1150)
 if(wave!==lastHit){lastHit=wave;emit('impact')}
 if(!props.motion)return
 // Arrows travel from the distant fort towards the viewer, with growing projected size.
 for(let i=0;i<78;i++){
  const phase=((age+i*91)%1950)/1950;if(phase<.1)continue;const p=(phase-.1)/.9
  const target={x:w*((i*0.618033)%1.5-.25),y:h*(.38+(i%11)*.072)}
  const depth=p*p;const px=origin.x+(target.x-origin.x)*depth,py=origin.y+(target.y-origin.y)*depth-Math.sin(p*Math.PI)*h*.12
  const a=Math.atan2(target.y-origin.y,target.x-origin.x),length=5+Math.pow(p,5)*165,thick=.5+p*p*3
  x.save();x.translate(px,py);x.rotate(a);x.globalAlpha=Math.min(1,p*4)*(p>.95?(1-p)*20:1)
  x.strokeStyle='#7f7259';x.lineWidth=thick;x.beginPath();x.moveTo(-length,0);x.lineTo(0,0);x.stroke()
  x.strokeStyle='#d1c3a2';x.lineWidth=Math.max(.4,thick*.25);x.beginPath();x.moveTo(-length,-1);x.lineTo(0,-1);x.stroke()
  x.fillStyle='#8c989b';x.beginPath();x.moveTo(6*p,0);x.lineTo(-3*p,-2*p);x.lineTo(-3*p,2*p);x.closePath();x.fill()
  if(p>.45){x.strokeStyle='#a6997f';x.lineWidth=1.2*p;for(const side of [-1,1])for(let j=0;j<4;j++){x.beginPath();x.moveTo(-length+j*length*.045,0);x.lineTo(-length+(j+1)*length*.045,side*4*p);x.stroke()}}
  x.restore()
 }
 // Impacts accumulate at the lower rails, not fireballs or screen flashes.
 for(let i=0;i<Math.min(30,Math.floor(age/230));i++){const left=i%2===0,px=w*(left?.08+(i%9)*.022:.79+(i%9)*.02),py=h*(.77+(i%5)*.032);x.strokeStyle='#aa9672';x.lineWidth=2;x.beginPath();x.moveTo(px,py);x.lineTo(px+(left?30:-28),py-45-(i%4)*12);x.stroke()}
 };frame=requestAnimationFrame(draw)
});onBeforeUnmount(()=>cancelAnimationFrame(frame))
</script>
<template><div class="barrage" role="status" aria-label="箭雨正从寨前迎面落入两舷草把"><canvas ref="canvas" aria-hidden="true"/><p>{{second?'另一舷，箭声渐密':'箭从寨前来了——伏低身子！'}}</p><button @click="finish">略过箭雨，接续故事</button></div></template>
<style scoped>.barrage{position:fixed;inset:0;z-index:4;pointer-events:none}.barrage canvas{width:100%;height:100%}.barrage p{position:absolute;top:27%;left:0;right:0;text-align:center;color:#ead9b6;letter-spacing:.18em;text-shadow:0 2px 8px #000;font:20px 'SimSun'}.barrage button{position:absolute;right:5vw;top:185px;pointer-events:auto;color:#e2d3b6;font-size:12px;border-bottom:1px solid #a58e62!important;padding:10px!important}</style>
