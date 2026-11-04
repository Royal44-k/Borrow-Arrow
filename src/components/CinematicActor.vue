<script setup lang="ts">
import { computed } from 'vue'
import support from '../assets/cast-support-s11.png'
import principal from '../assets/cast-principal-s11.png'
import shen from '../assets/shen-yan.png'
import { ACTOR_ASSETS, resolveActor, actorVisibleInMode } from '../actor-identity'
const props=defineProps<{name:string;quiet?:boolean;mode?:string}>()
const actor=computed(()=>resolveActor(props.name))
const visible=computed(()=>actor.value!==null&&actorVisibleInMode(props.mode))
const spriteStyle=computed(()=>{
 if(!actor.value)return {}
 const asset=ACTOR_ASSETS[actor.value.atlas]
 const columnPosition=asset.columns>1?actor.value.frame/(asset.columns-1)*100:50
 return {backgroundImage:`url(${actor.value.atlas==='support'?support:principal})`,backgroundSize:`${asset.columns*100}% 100%`,backgroundPosition:`${columnPosition}% 50%`,aspectRatio:`${asset.width/asset.columns}/${asset.height}`}
})
</script>
<template><Transition name="actor-reveal" mode="out-in" appear><div v-if="visible&&actor" :key="actor.id" class="actor" :class="{quiet,cutout:actor.atlas!=='shen'}" :aria-label="name" role="img"><div v-if="actor.atlas!=='shen'" class="actor-sprite" :style="spriteStyle"></div><img v-else :src="shen" :alt="name" draggable="false" /></div></Transition></template>
<style scoped>
.actor{pointer-events:none;position:absolute;right:3%;bottom:100px;width:min(33vw,470px);height:70vh;z-index:7;filter:drop-shadow(0 15px 24px #0009);transform-origin:bottom center}.actor-sprite{height:100%;aspect-ratio:514/765;margin:auto;background-size:400% 100%;background-repeat:no-repeat;max-width:100%;mask-image:linear-gradient(#000 82%,#000b 94%,transparent);filter:brightness(.92) saturate(.79);animation:actor-breathe 6.4s ease-in-out infinite alternate}.actor img{width:100%;height:100%;object-fit:cover;object-position:50% 0;mask-image:radial-gradient(ellipse at 50% 38%,#000 30%,#000c 53%,transparent 73%);mix-blend-mode:lighten}.actor.quiet{opacity:.78;filter:brightness(.75);transform:scale(.92)}@keyframes actor-breathe{from{transform:translateY(0) rotate(-.12deg)}to{transform:translateY(-3px) rotate(.12deg)}}.actor.quiet .actor-sprite{animation-play-state:paused}.actor-reveal-enter-active{transition:opacity .3s ease-out,translate .3s ease-out}.actor-reveal-leave-active{transition:opacity .18s ease-in,translate .18s ease-in}.actor-reveal-enter-from,.actor-reveal-leave-to{opacity:0;translate:16px 0}@media(max-width:800px){.actor{right:-6%;width:46vw;height:55vh;bottom:160px}}@media(prefers-reduced-motion:reduce){.actor,.actor-sprite{animation:none}.actor-reveal-enter-active,.actor-reveal-leave-active{transition:none}}
</style>
<style scoped>
/* A portrait identifies the current speaker; it is not a substitute for acting. */
.actor{left:1.5%;right:auto;bottom:35px;width:17vw;max-width:260px;height:43vh;max-height:390px;z-index:19}
.actor-sprite{animation:none;filter:brightness(.92) saturate(.79);mask-image:linear-gradient(#000 88%,transparent)}
.actor-reveal-enter-from,.actor-reveal-leave-to{translate:0 0}
@media(max-width:800px){.actor{left:1%;right:auto;bottom:38px;width:21vw;height:27vh}}
</style>
