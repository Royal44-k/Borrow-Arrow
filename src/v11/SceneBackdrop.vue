<script setup lang="ts">
import {ref,watch,onBeforeUnmount} from 'vue'
import {FrameLoader} from './frameLoader'
const props=defineProps<{src:string;fallback:string;motion:boolean;transition?:string;pan?:number;drift?:'river'|'bank'|'detail'}>()
const emit=defineEmits<{ready:[];unavailable:[]}>(),front=ref(''),back=ref(''),fading=ref(false),failed=ref(false)
const loader=new FrameLoader<HTMLImageElement>();let fadeTimer:ReturnType<typeof setTimeout>
async function update(){failed.value=false;const result=await loader.load(props.src,async url=>{
 const im=new Image();im.src=url;try{await im.decode();return im}catch(e){if(front.value)throw e;const fallback=new Image();fallback.src=props.fallback;await fallback.decode();return fallback}
},im=>{clearTimeout(fadeTimer);back.value=front.value;front.value=im.src;fading.value=true;failed.value=im.src!==new URL(props.src,location.href).href;if(failed.value)emit('unavailable');else emit('ready');fadeTimer=setTimeout(()=>{back.value='';fading.value=false},1100)})
 if(result==='failed'){failed.value=true;emit('unavailable')}
}
watch(()=>props.src,update,{immediate:true});onBeforeUnmount(()=>{loader.cancel();clearTimeout(fadeTimer)})
</script>
<template><div class="scene-backdrop" :class="[transition||'dissolve',{moving:motion},drift?'drift-'+drift:'']" :style="pan!==undefined?{transform:`scale(1.14) translateX(${(50-pan)*.055}%)`}:{}">
 <img v-if="back" :src="back" class="frame previous" alt=""/>
 <img v-if="front" :key="front" :src="front" class="frame current" :class="{arriving:fading&&motion}" alt=""/>
 <div v-if="!front" class="first-load"><span>江上灯火渐近</span></div>
</div><button v-if="failed" class="scene-retry" @click="update">场景暂未载入 · 重试</button></template>
<style scoped>
.scene-backdrop{position:fixed;inset:0;z-index:-5;background:radial-gradient(ellipse at 60% 60%,#29404b,#0e222e 70%);overflow:hidden}.frame{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}.moving .frame{transform:scale(1.025)}.arriving{animation:arrive 1.05s both}.unroll .arriving{animation:unroll 1.05s both}.approach .arriving{animation:approach 1.05s both}.shore .arriving{animation:shore 1.1s both}.reveal .arriving{animation:reveal 1.1s both}.moving .previous{animation:none}.first-load{height:100%;display:grid;place-items:center;color:#c4b28d;letter-spacing:.4em;background:linear-gradient(110deg,transparent,#8aabbb12,transparent)}.scene-retry{position:fixed;left:42%;top:80px;z-index:25!important;background:#203541ed!important;padding:8px 14px!important;font-size:12px}
@keyframes arrive{from{opacity:0}to{opacity:1}}@keyframes unroll{from{clip-path:inset(0 50%);opacity:.5}to{clip-path:inset(0);opacity:1}}@keyframes approach{from{opacity:0;transform:scale(1.09)}to{opacity:1;transform:scale(1.025)}}
@keyframes shore{from{opacity:0;transform:scale(1.045) translateY(1.2%)}to{opacity:1;transform:scale(1.025) translateY(0)}}@keyframes reveal{from{opacity:0;clip-path:inset(0 12% 0 0)}to{opacity:1;clip-path:inset(0)}}
.moving.drift-river .current:not(.arriving){animation:river-drift 17s ease-in-out infinite alternate}.moving.drift-bank .current:not(.arriving){animation:bank-drift 23s ease-in-out infinite alternate}.moving.drift-detail .current:not(.arriving){animation:detail-drift 27s ease-in-out infinite alternate}
@keyframes river-drift{from{transform:scale(1.025) translateY(-.18%)}to{transform:scale(1.036) translateY(.18%) rotate(.1deg)}}@keyframes bank-drift{from{transform:scale(1.025) translateX(-.15%)}to{transform:scale(1.038) translateX(.15%)}}@keyframes detail-drift{from{transform:scale(1.025)}to{transform:scale(1.043)}}
</style>
