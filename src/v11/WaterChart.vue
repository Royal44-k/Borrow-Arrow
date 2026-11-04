<script setup lang="ts">
import {computed,ref,onMounted} from 'vue'
const props=defineProps<{mode:string}>(),emit=defineEmits<{change:[value:number]}>()
const host=ref<SVGSVGElement>(),point=ref({x:260,y:120}),moving=ref(false)
const rescue=computed(()=>props.mode==='rescue')
onMounted(()=>emit('change',rescue.value?100*(point.value.y-65)/180:100*(245-point.value.y)/180))
function place(e:PointerEvent){if(!host.value)return;const p=host.value.createSVGPoint();p.x=e.clientX;p.y=e.clientY;const m=host.value.getScreenCTM();if(!m)return;const pos=p.matrixTransform(m.inverse());point.value={x:Math.max(30,Math.min(490,pos.x)),y:Math.max(65,Math.min(245,pos.y))};emit('change',rescue.value?100*(point.value.y-65)/180:100*(245-point.value.y)/180)}
function down(e:PointerEvent){moving.value=true;host.value?.setPointerCapture(e.pointerId);place(e)}
function step(delta:number){point.value.y=Math.max(65,Math.min(245,point.value.y+delta));emit('change',rescue.value?100*(point.value.y-65)/180:100*(245-point.value.y)/180)}
</script>
<template><div class="water-chart"><p>{{rescue?'把接应船移到末船外侧，留出抛缆的位置。':'把船队停在警戒水线之外，留出回桨的余地。'}}</p>
 <svg ref="host" viewBox="0 0 520 270" tabindex="0" role="application" :aria-label="rescue?'江面接应布位':'江面船队布位'" @pointerdown="down" @pointermove="moving&&place($event)" @pointerup="moving=false" @pointercancel="moving=false" @keydown.down.prevent="step(15)" @keydown.up.prevent="step(-15)">
 <defs><pattern id="ripples" width="70" height="23" patternUnits="userSpaceOnUse"><path d="M0 10q15 -6 30 0t30 0" fill="none" stroke="#8bb0be" opacity=".18"/></pattern></defs>
 <rect width="520" height="270" fill="#102c39"/><rect width="520" height="270" fill="url(#ripples)"/><path d="M0 48L520 48" stroke="#c49b60" stroke-width="4"/><text x="18" y="30">曹寨</text><path d="M0 128L520 128" stroke="#cfb782" stroke-dasharray="6 7"/><text x="350" y="115">警戒水线</text>
 <g v-if="rescue" transform="translate(360 214)"><path d="M-28 0Q0 -26 28 0Q0 26 -28 0" fill="#8d6844" stroke="#d4ba83"/><text x="-40" y="40">末船 · 横流</text></g>
 <path v-if="rescue&&point.y>182" :d="`M${point.x} ${point.y}Q310 170 360 214`" fill="none" stroke="#e1d2a8" stroke-width="2"/>
 <g :transform="`translate(${point.x} ${point.y})`" class="chart-ship"><ellipse rx="42" ry="27" fill="#cfbb7b22"/><path d="M-34 0Q0 -27 34 0Q0 27 -34 0" fill="#7f5637" stroke="#e6d0a1" stroke-width="2"/><path d="M-19 -5H19M-19 5H19" stroke="#d6b776" stroke-width="4"/></g>
 </svg><div class="chart-tools"><span>拖动船影，或点水面落位</span><button @click="step(-20)">向寨侧</button><button @click="step(20)">向外侧</button></div>
 </div></template>
<style scoped>.water-chart{background:#0b1d25e8;padding:13px;border:1px solid #8d9e9d40}.water-chart p{font-size:13px;margin:0 0 8px}.water-chart svg{width:100%;max-height:225px;touch-action:none;cursor:grab}.water-chart text{fill:#dacbb0;font:14px 'Microsoft YaHei'}.chart-tools{display:flex;align-items:center;gap:9px;flex-wrap:wrap;font-size:11px;color:#bfb7a5}.chart-tools button{padding:7px!important;border:1px solid #8d9e9d55!important}.chart-ship{filter:drop-shadow(0 2px 4px #0008)}</style>
