<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { restoreTallyDraft, verifyTally, type TallyContext, type TallyDraft, type TallyProof } from './tally'
const props = defineProps<{context:TallyContext;initial?:unknown;motion?:boolean|string}>()
const emit = defineEmits<{change:[draft:TallyDraft];complete:[proof:TallyProof];narrate:[text:string]}>()
// Initial is a mount-time restoration. Parent change echoes must never replace a live draft.
const draft = reactive(restoreTallyDraft(props.initial))
const feedback = ref('')
const verified = ref(false)
const samplesTaken = ref(draft.sample_checked ? 3 : draft.samples_taken||0)
const dragStart = ref<number|null>(null)
const dragOffset = ref(0)
let suppressClick = false
const empty = computed(() => props.context.total === 0)
const fields = [{key:'right',label:'右舷'},{key:'left',label:'左舷'},{key:'total',label:'合计'}] as const
const tokens = [0,50000,100000]
const label = (n:number) => n === 0 ? '零' : `${n / 10000}万`
function changed() { verified.value=false; feedback.value=''; emit('change',{...draft}) }
function inspect() {
 if (draft.sample_checked) return
 if (!empty.value) {
  samplesTaken.value += 1
  draft.samples_taken=samplesTaken.value
  changed()
  if (samplesTaken.value < 3) {
   dragOffset.value=0
   emit('narrate', '样箭已放上案头，再取下一支。')
   return
  }
 }
 draft.sample_checked=true; dragOffset.value=0; changed()
 emit('narrate',empty.value ? '草把空空，确认没有实得箭。请将两舷与总数分别记为零。' : '样箭已从草把拔下。再看前后各船合报，分别记下两舷和总数。')
}
function pointerDown(event:PointerEvent) {
 if (draft.sample_checked || empty.value) return
 suppressClick=false; dragStart.value=event.clientX; (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
}
function pointerMove(event:PointerEvent) {
 if(dragStart.value!==null) dragOffset.value=Math.max(0,Math.min(145,event.clientX-dragStart.value))
}
function pointerUp() {
 if(dragStart.value!==null && dragOffset.value>=55) { suppressClick=true; inspect() }
 dragStart.value=null; dragOffset.value=0
}
function arrowClick() { if (suppressClick) { suppressClick=false; return }; inspect() }
function cancelDrag() { dragStart.value=null; dragOffset.value=0; suppressClick=true }
function select(key:'right'|'left'|'total',value:number) { draft[key]=value; changed() }
function verify() {
 const result=verifyTally(draft,props.context)
 if(!result.ok) { feedback.value=result.message;emit('narrate',result.message);return }
 verified.value=true;feedback.value='两舷与总数核对无误，可以入册。';emit('narrate',feedback.value);emit('complete',result.proof)
}
</script>

<template>
<section class="tally-dock" :class="{'still':motion===false || motion==='reduced','empty-tally':empty}" aria-label="岸边取箭清点">
 <header class="tally-heading"><span>归岸 · 核收</span><h2>从草把到军册</h2><p>{{ draft.sample_checked ? '对照船队合报，摆签记数。' : empty ? '先翻看空草把，核实实得。' : '亲手取三支样箭，逐支放上案头。' }}</p></header>
 <div class="tally-workbench">
  <div class="straw-area" :class="{'inspected':draft.sample_checked}">
   <div class="straw-object">
    <img class="straw" :src="'./v14/tally-straw-cutout.webp'" :alt="empty ? '没有箭的空草把' : draft.sample_checked ? '取下样箭后的草把' : '插着样箭的草把'" draggable="false"/>
    <svg class="embedded-arrows" viewBox="0 0 440 280" aria-hidden="true"><g v-for="n in (!empty && !draft.sample_checked ? 3-samplesTaken : 0)" :key="n" :transform="`translate(0,${(n-1)*22})`"><path d="M168 148L340 101" stroke="#bd9c64" stroke-width="4"/><path d="M317 107L325 92 341 88 332 103 346 112 330 117Z" fill="#ad9c7e"/><path d="M169 148L177 140" stroke="#242523" stroke-width="3"/></g></svg>
   </div>
   <div v-if="!empty && !draft.sample_checked && samplesTaken" class="taken-samples" aria-live="polite">案头已取 {{samplesTaken}} 支样箭<svg v-for="n in samplesTaken" :key="n" viewBox="0 0 250 26" aria-hidden="true"><path d="M12 13H230" stroke="#dfbb7e" stroke-width="3"/><path d="M239 13L222 6V20Z" fill="#aab9b5"/><path d="M15 13L2 2H22L36 13 22 24H2Z" fill="#a99165"/></svg></div><button v-if="!empty && !draft.sample_checked" class="pull-arrow" :style="{transform:`translateX(${dragOffset}px)`}" @pointerdown="pointerDown" @pointermove="pointerMove" @pointerup="pointerUp" @pointercancel="cancelDrag" @click="arrowClick" aria-label="拔下样箭，也可以向右拖动">
    <svg viewBox="0 0 240 40" aria-hidden="true"><defs><linearGradient id="shaftLight" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#e1c58f"/><stop offset=".45" stop-color="#ac8650"/><stop offset="1" stop-color="#493725"/></linearGradient></defs><path d="M18 20H224" stroke="url(#shaftLight)" stroke-width="4"/><path d="M6 20L26 15V25Z" fill="#9aa3a0"/><path d="M204 20L221 9H203L184 20 203 31H221Z" fill="#afa28a"/><g stroke="#514d43" stroke-width=".8"><path d="M195 14L204 20 195 26M202 10L212 20 202 30M211 10L220 20 211 30"/></g></svg>
    <span>取第 {{samplesTaken+1}} 支 · 向右拔或点按</span>
   </button>
   <button v-else-if="!draft.sample_checked" class="inspect-empty" @click="inspect">翻看草把 · 确认无箭</button>
   <div v-else class="sample-tray"><span>{{ empty ? '已查验 · 空草把' : '三支样箭已取下' }}</span><svg v-for="n in (empty ? 0 : 3)" :key="n" viewBox="0 0 250 26" aria-hidden="true"><path d="M12 13H230" stroke="#dfbb7e" stroke-width="3"/><path d="M239 13L222 6V20Z" fill="#aab9b5"/><path d="M15 13L2 2H22L36 13 22 24H2Z" fill="#a99165"/></svg></div>
  </div>
  <div v-if="draft.sample_checked" class="tally-record">
   <div class="fleet-reports" aria-label="船队整队汇总报签"><div v-for="side in fields.slice(0,2)" :key="side.key" class="report-slip"><span>{{ side.label }} · 前后各船合报</span><strong>{{ label(context[side.key]) }}<small>支</small></strong></div></div>
   <div class="count-rail"><fieldset v-for="field in fields" :key="field.key"><legend>{{field.label}}记数</legend><div class="token-row"><button v-for="value in tokens" :key="value" class="count-token" :class="{chosen:draft[field.key]===value}" :aria-pressed="draft[field.key]===value" :aria-label="`${field.label}记为${label(value)}支`" @click="select(field.key,value)">{{label(value)}}</button></div></fieldset></div>
   <div class="ledger-foot"><p role="status" aria-live="polite">{{feedback || '两舷各记一签，再将总数入册。'}}</p><button class="verify-seal" @click="verify">{{verified ? '已核收' : '核对入册'}}</button></div>
  </div>
  <p v-else class="await-report">{{empty ? '实得为零，也须查验后入册。' : '草把留下箭孔，样箭放上案头，再收各船报签。'}}</p>
 </div>
 <p class="tally-caption">{{draft.sample_checked ? (empty?'实得为零：确认草把与整队报签一致。':'三支仅作取样；计数按整支船队合报。') : '没有时限，取稳了再记。'}}</p>
</section>
</template>

<style scoped>
.tally-dock{--gold:#d9b575;--ink:#eee0c5;--dim:#b8aa90;position:relative;isolation:isolate;min-height:100dvh;display:flex;flex-direction:column;justify-content:center;color:var(--ink);padding:clamp(18px,3vw,34px);border:1px solid #9c7b443b;background:linear-gradient(110deg,#0c181bbd,#17181488),url('/v14/dock-tally.webp') center/cover;box-shadow:0 20px 60px #0005;font-family:'Noto Serif SC','Songti SC',SimSun,serif}.tally-dock.empty-tally{background-image:linear-gradient(110deg,#0c181bbd,#17181488),url('/v14/empty-tally.webp')}.tally-heading{padding-right:185px;width:min(1260px,100%);margin:0 auto}.tally-heading span{color:var(--gold);font-size:11px;letter-spacing:.3em}.tally-heading h2{font-size:clamp(24px,3vw,35px);font-weight:500;letter-spacing:.12em;margin:8px 0}.tally-heading p,.tally-caption{font-size:13px;color:var(--dim);line-height:1.7;margin:8px 0}.tally-workbench{margin:20px auto 0;width:min(1260px,100%);min-height:clamp(320px,46vh,500px);padding:14px 20px;background:repeating-linear-gradient(1deg,#261e16 0,#261e16 34px,#181711 35px,#35281c 36px,#2a221a 72px);border-top:3px solid #55422a;border-bottom:7px solid #17140f;box-shadow:inset 0 3px 15px #0008;display:grid;grid-template-columns:minmax(220px,.85fr) minmax(300px,1.3fr);align-items:center;gap:22px}.straw-area{position:relative;min-height:230px;display:flex;flex-direction:column;justify-content:center;align-items:center}.straw-object{position:relative;width:100%;max-width:480px}.embedded-arrows{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;filter:drop-shadow(0 3px 2px #0008)}.straw{display:block;width:100%;max-width:480px;user-select:none;filter:drop-shadow(0 12px 8px #0006)}button{font:inherit;cursor:pointer}button:focus-visible{outline:3px solid #f3d39c;outline-offset:5px}.pull-arrow{position:absolute;top:46%;left:30%;width:65%;padding:5px 0;background:none;border:0;color:var(--gold);touch-action:none;text-shadow:0 2px 5px #000}.pull-arrow svg{width:100%;filter:drop-shadow(0 4px 2px #0008)}.pull-arrow span{font-size:12px;display:block;letter-spacing:.08em}.inspect-empty{color:var(--ink);background:#30291b;border:1px solid #a4824c;padding:11px 20px;margin-top:-20px}.taken-samples{font-size:11px;color:#d9b575;width:70%;margin-top:-20px}.taken-samples svg{display:block;width:100%;height:15px}.sample-tray{width:85%;min-height:55px;border-bottom:1px solid #93784d;display:flex;align-items:center;gap:12px}.sample-tray span{white-space:nowrap;font-size:12px;color:var(--gold)}.sample-tray{flex-wrap:wrap}.sample-tray svg{width:60%;height:14px;margin-left:auto;transform:rotate(-4deg)}.await-report{max-width:260px;line-height:2.3;color:var(--dim);letter-spacing:.1em;font-size:16px}.fleet-reports{display:flex;gap:15px;transform:rotate(-1deg)}.report-slip{flex:1;padding:13px 15px 11px;background:linear-gradient(90deg,#ba9d68,#dcc08b 8%,#c5a570 95%,#92734c);color:#35291b;box-shadow:2px 4px 9px #0006;border-top:3px solid #6b5131;border-bottom:2px solid #6b5131}.report-slip>span{font-size:11px;display:block;letter-spacing:.06em}.report-slip strong{font-weight:500;font-size:29px;letter-spacing:.13em;display:block;margin-top:7px}.report-slip small{font-size:12px;margin-left:8px}.count-rail{margin-top:21px;border-top:1px solid #79613c;display:flex;gap:10px;padding-top:8px}fieldset{border:0;padding:4px 0;margin:0;flex:1;min-width:0}legend{font-size:12px;color:var(--dim);padding:0;margin-bottom:8px;letter-spacing:.12em}.token-row{display:flex;gap:5px}.count-token{min-width:34px;flex:1;padding:14px 3px;border:1px solid #6b5131;border-radius:3px;background:linear-gradient(90deg,#493723,#655034 50%,#41301f);box-shadow:0 4px 1px #17130f;color:#d4be96;font-size:13px;transition:transform .2s,background .2s}.count-token.chosen{background:linear-gradient(90deg,#b18b4d,#d4b476,#a78145);color:#292015;transform:translateY(-5px);box-shadow:0 8px 2px #110f0ba6;border-color:#e7c88c}.ledger-foot{display:flex;gap:12px;align-items:center;margin-top:17px}.ledger-foot p{font-size:12px;color:#d5bd95;line-height:1.8;margin:0;flex:1;min-height:42px}.verify-seal{flex-shrink:0;background:#6b3928;border:1px solid #af7858;color:#f5dcb3;padding:12px 15px;letter-spacing:.15em;box-shadow:0 3px 0 #24150e}.verify-seal:hover{background:#815039}.tally-caption{width:min(1260px,100%);margin:10px auto;text-align:right;font-size:11px}.still *{transition:none!important;animation:none!important}@media(prefers-reduced-motion:reduce){.tally-dock *{transition:none!important;animation:none!important}}@media(max-width:720px){.tally-heading{padding-top:46px;padding-right:0}.tally-workbench{grid-template-columns:1fr;padding:8px 14px 18px;gap:4px}.straw-area{min-height:180px}.straw{max-width:310px}.pull-arrow{left:34%;width:55%;max-width:240px;top:42%}.await-report{max-width:none;font-size:14px;text-align:center}.taken-samples{font-size:11px;color:#d9b575;width:70%;margin-top:-20px}.taken-samples svg{display:block;width:100%;height:15px}.sample-tray{max-width:300px;min-height:32px;margin-top:-18px}.fleet-reports{margin-top:12px}.report-slip{padding:10px}.report-slip>span{font-size:10px}.count-rail{gap:9px}.token-row{gap:4px}.count-token{min-width:0;font-size:12px;padding:13px 2px}.ledger-foot{align-items:flex-end}.tally-heading h2{margin-bottom:6px}}
</style>


