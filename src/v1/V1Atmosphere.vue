<script setup lang="ts">
import {onMounted,onBeforeUnmount,ref} from 'vue'
const props=defineProps<{active:boolean;scene:string;weather?:string}>();const el=ref<HTMLCanvasElement>();let raf=0,last=0,t=0
onMounted(()=>{const c=el.value!,ctx=c.getContext('2d')!;const resize=()=>{c.width=innerWidth;c.height=innerHeight};resize();window.addEventListener('resize',resize)
 const draw=(ms:number)=>{raf=requestAnimationFrame(draw);if(ms-last<45)return;last=ms;ctx.clearRect(0,0,c.width,c.height);if(!props.active)return;t+=.025;const w=c.width,h=c.height;const inside=['command','council','v13/camp-debrief'].includes(props.scene)
 const morning=props.scene.startsWith('v13/')&&!props.scene.includes('arrows');if(!inside){if(props.weather!=='clear'&&!morning)for(let i=0;i<9;i++){const x=((i*197+t*14)%(w+400))-200,y=h*(.48+(i%3)*.09);const g=ctx.createRadialGradient(x,y,0,x,y,w*.28);g.addColorStop(0,'rgba(196,213,219,.045)');g.addColorStop(1,'rgba(196,213,219,0)');ctx.fillStyle=g;ctx.fillRect(0,0,w,h)}
 for(let i=0;i<(morning?8:30);i++){const y=h*(.55+i*.009),x=w*(.7+Math.sin(i*1.71+t)*.14);ctx.strokeStyle=`rgba(205,218,221,${.025+(Math.sin(t*2+i)+1)*.02})`;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+10+(i%4)*10,y);ctx.stroke()}}
 // Restrained animated bloom. Texture and fire source remain in the original image.
 const x=inside?w*.18:w*.8,y=inside?h*.46:h*.48;const g=ctx.createRadialGradient(x,y,1,x,y,inside?80:50);g.addColorStop(0,`rgba(255,169,70,${.025+.025*Math.sin(t*7)})`);g.addColorStop(1,'rgba(255,169,70,0)');ctx.fillStyle=g;ctx.fillRect(x-90,y-90,180,180)
 };raf=requestAnimationFrame(draw);cleanup=()=>window.removeEventListener('resize',resize)
});let cleanup=()=>{};onBeforeUnmount(()=>{cancelAnimationFrame(raf);cleanup()})
</script>
<template><canvas ref="el" class="v1-atmosphere" aria-hidden="true"></canvas></template>
<style scoped>.v1-atmosphere{position:fixed;inset:0;pointer-events:none;z-index:-2;width:100%;height:100%;mix-blend-mode:screen}</style>
