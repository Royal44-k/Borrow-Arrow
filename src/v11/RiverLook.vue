<script setup lang="ts">
import {ref} from 'vue'
const props=defineProps<{clear:boolean;cao:boolean}>(),emit=defineEmits<{pan:[value:number]}>(),x=ref(50),drag=ref(false)
function look(e:PointerEvent){const r=(e.currentTarget as HTMLElement).getBoundingClientRect();x.value=Math.min(100,Math.max(0,(e.clientX-r.left)/r.width*100));emit('pan',x.value)}
function move(n:number){x.value=Math.min(100,Math.max(0,x.value+n));emit('pan',x.value)}
</script>
<template><div class="river-look" tabindex="0" role="application" aria-label="巡看江面，左右拖动或方向键移动视线" @pointerdown="drag=true;($event.currentTarget as HTMLElement).setPointerCapture($event.pointerId);look($event)" @pointermove="drag&&look($event)" @pointerup="drag=false" @pointercancel="drag=false" @keydown.left.prevent="move(-15)" @keydown.right.prevent="move(15)">
 <div class="look-reticle" :style="{left:x+'%'}"><i></i><span>{{x<34?'来船方向':x>66?'水寨灯火':'江心水线'}}</span></div>
 <p>{{clear?'月光明亮，换个角度看船边的人影。':cao?'雾里只能辨出断续的船影。沿水线慢慢看。':'顺着灯影看过去，记住能回船的那片水面。'}}</p>
 </div><div class="look-keys"><button @click="move(-20)">向左看</button><span>拖动巡看江面</span><button @click="move(20)">向右看</button></div></template>
<style scoped>.river-look{height:135px;position:relative;touch-action:none;cursor:ew-resize;background:linear-gradient(0deg,#122b3888,transparent);border-bottom:1px solid #a5b4ad77}.look-reticle{position:absolute;top:5px;transform:translateX(-50%);width:85px;text-align:center;pointer-events:none}.look-reticle i{display:block;margin:auto;width:45px;height:45px;border:1px solid #ead5a4;border-radius:50%;box-shadow:0 0 25px #ecd9ad22}.look-reticle span{font-size:11px;color:#e6d4b0}.river-look p{position:absolute;bottom:3px;padding:0 12px;font-size:12px}.look-keys{display:flex;align-items:center;justify-content:space-between;font-size:11px}.look-keys button{padding:10px!important;border-bottom:1px solid #8d9e9d55!important}</style>
