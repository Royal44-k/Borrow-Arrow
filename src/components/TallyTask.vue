<script setup lang="ts">
import {computed,nextTick,onMounted,ref,watch} from 'vue'
import {tallyInitial,tallySubmission,type TallyContext,type TallySide} from '../tally'
const props=defineProps<{context:TallyContext;identity:string;busy:boolean;error:string}>()
const emit=defineEmits<{answer:[payload:Record<string,unknown>];finish:[payload:Record<string,unknown>];close:[]}>()
const panel=ref<HTMLElement>(),total=ref(''),side=ref<TallySide|''>('')
const id=ref(props.context.progress.record_id??crypto.randomUUID())
const last=computed(()=>props.context.progress.attempts.at(-1))
const submission=computed(()=>tallySubmission(id.value,props.context.variant,total.value,side.value))
const unchanged=computed(()=>!!last.value&&submission.value?.answer_total===last.value.answer_total&&(props.context.variant==='balance'||submission.value?.answer_side===last.value.answer_side))
const key=`caocuan:tally:${props.identity}`
const locked=computed(()=>props.context.progress.status==='complete'||props.context.progress.attempts.length>=10)
const format=(n:number)=>n.toLocaleString('en-US')
function restore(){
 let local=null;try{local=JSON.parse(localStorage.getItem(key)??'null')}catch{}
 const restored=tallyInitial(props.context.progress,local,()=>id.value)
 id.value=restored.id;total.value=restored.total;side.value=restored.side
}
restore()
watch([total,side],()=>{try{localStorage.setItem(key,JSON.stringify({record_id:id.value,total:total.value,side:side.value}))}catch{}})
watch(()=>props.context.progress.record_id,v=>{if(v)id.value=v})
watch(locked,value=>{if(value&&last.value){total.value=String(last.value.answer_total);side.value=last.value.answer_side??''}})
onMounted(()=>void nextTick(()=>panel.value?.focus()))
function submit(){if(!props.busy&&submission.value&&!unchanged.value&&props.context.progress.attempts.length<10)emit('answer',{...submission.value,status:'draft'})}
function finish(){if(!props.busy&&last.value&&unchanged.value)emit('finish',{record_id:id.value,status:'complete'})}
function trap(e:KeyboardEvent){if(e.key==='Escape'){if(!props.busy)emit('close');return}if(e.key!=='Tab'||!panel.value)return;const all=Array.from(panel.value.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled)'));if(e.shiftKey&&(document.activeElement===all[0]||document.activeElement===panel.value)){e.preventDefault();all.at(-1)?.focus()}else if(!e.shiftKey&&document.activeElement===all.at(-1)){e.preventDefault();all[0]?.focus()}}
</script>
<template>
 <div class="tally-backdrop" @keydown="trap"><section ref="panel" tabindex="-1" class="tally-sheet" role="dialog" aria-modal="true" aria-label="归岸箭簿">
  <button class="tally-close" :disabled="busy" @click="emit('close')" aria-label="暂收箭簿">×</button>
  <header><span>南岸 · 船队已归</span><h1>这一夜，带回多少箭？</h1><p>沈砚摊开各船的报数：“给都督的数，得从这里合起来。”</p></header>
  <div class="tally-columns"><dl><div><dt>右舷取得</dt><dd>{{format(context.first)}}<small>支</small></dd></div><div><dt>左舷取得</dt><dd>{{format(context.second)}}<small>支</small></dd></div><div v-if="context.spent"><dt>已发出去</dt><dd>− {{format(context.spent)}}<small>支</small></dd></div><div v-if="context.loss"><dt>受损另放</dt><dd>− {{format(context.loss)}}<small>支</small></dd></div></dl>
   <form @submit.prevent="submit"><fieldset v-if="context.variant==='sides'"><legend>哪一舷取得的箭更多？</legend><button v-for="(name,value) in {right:'右舷',left:'左舷',equal:'一样多'}" :key="value" type="button" :aria-pressed="side===value" :disabled="busy||locked" @click="side=value as TallySide">{{name}}</button></fieldset>
    <label class="tally-answer">应送入军帐<input v-model="total" type="text" inputmode="numeric" maxlength="12" aria-label="应交箭数" autocomplete="off" :disabled="busy||locked"/><span>支</span></label>
    <button class="tally-verify" :disabled="busy||!submission||unchanged||context.progress.attempts.length>=10">{{busy?'正在核对…':'请沈砚核对'}}</button>
   </form>
  </div>
  <div v-if="last" class="tally-feedback" role="status"><b>沈砚</b><p>{{last.feedback?.text??'这一笔已经留下。看过各船的数，再决定是否修改。'}}</p><small v-if="!unchanged">这次改动还没核对，先把新数交给沈砚。</small></div>
  <p v-if="error" role="alert" class="tally-error">{{error}}</p>
  <footer><span v-if="context.progress.attempts.length>=10">这十次报数都在簿上，入帐时一并说明。</span><button :disabled="busy||!last||!unchanged" @click="finish">记入箭簿，进帐说明 <span>⟶</span></button></footer>
 </section></div>
</template>
<style scoped>
.tally-backdrop{position:fixed;inset:0;z-index:45;background:#0b100ee6;display:grid;place-items:center;padding:24px;overflow:auto}.tally-sheet{position:relative;width:min(950px,96vw);max-height:94vh;overflow:auto;color:#33271d;background:repeating-linear-gradient(0deg,#79542d07 0 1px,transparent 1px 7px),#eee0c3;padding:clamp(24px,4vw,50px);box-shadow:0 30px 100px #0009,inset 0 0 70px #8b642f18;border-left:10px solid #7b3e2c;border-right:2px solid #a9895b;outline:none}.tally-close{position:absolute;right:20px;top:14px;border:0;background:none;font-size:28px;color:#685640}.tally-sheet header>span{letter-spacing:.3em;color:#826741;font-size:12px}.tally-sheet h1{font-family:STSong,SimSun,serif;font-size:clamp(26px,3.8vw,42px);font-weight:500;margin:13px 0 18px}.tally-sheet p{line-height:1.8}.tally-columns{display:grid;grid-template-columns:1fr 1.2fr;gap:45px;border-top:1px solid #9d804b65;border-bottom:1px solid #9d804b65;padding:24px 0}.tally-columns dl{margin:0}.tally-columns dl>div{display:flex;justify-content:space-between;align-items:baseline;padding:9px 0}.tally-columns dt{font-size:14px}.tally-columns dd{font-size:25px;font-family:Georgia,serif}.tally-columns small{font-family:inherit;font-size:12px;margin-left:9px}.tally-columns fieldset{border:0;margin:0 0 20px;padding:0}.tally-columns legend{margin-bottom:12px;font-size:14px}.tally-columns fieldset button{border:1px solid #9d804b;background:transparent;color:#59432b;padding:9px 18px;margin-right:7px}.tally-columns fieldset button[aria-pressed=true]{background:#6e4630;color:#fff0d5}.tally-sheet label.tally-answer{position:relative;display:block;font-size:14px;color:#59432b}.tally-sheet .tally-answer input[type=text]{display:block;width:100%;border:0;border-bottom:2px solid #865a33;background:transparent;color:#352318;font:36px Georgia,serif;padding:10px 25px 10px 0;outline-offset:3px}.tally-answer>span{position:absolute;right:4px;bottom:14px}.tally-verify{margin-top:18px;border:0;padding:10px 19px;background:#75432e;color:#fff4df}.tally-feedback{display:flex;gap:15px;align-items:baseline;margin-top:16px;flex-wrap:wrap}.tally-feedback b{font-weight:500;color:#8a3e2b}.tally-feedback p{flex:1;margin:0}.tally-feedback small{width:100%}.tally-error{color:#972e20}.tally-sheet footer{display:flex;align-items:center;justify-content:flex-end;margin-top:22px;gap:20px}.tally-sheet footer button{background:#253d36;border:0;color:#f6e8cb;padding:14px 22px;letter-spacing:.05em}.tally-sheet button{cursor:pointer;transition:background .18s}.tally-sheet button:disabled{cursor:default;opacity:.4}.tally-sheet button:focus-visible{outline:3px solid #ab6534;outline-offset:3px}@media(max-width:650px){.tally-columns{grid-template-columns:1fr;gap:18px}.tally-sheet{padding:30px 22px}.tally-columns dl{display:grid;grid-template-columns:1fr 1fr;gap:0 20px}.tally-columns dd{font-size:20px;margin-left:8px}.tally-sheet footer{flex-direction:column;align-items:stretch}}
</style>
