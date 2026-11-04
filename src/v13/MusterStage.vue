<script setup lang="ts">
import {ref,computed} from 'vue'
import {musterPayload,musterBackdrop,type MusterDraft} from './journey'
const props=defineProps<{initial?:MusterDraft;motion:boolean;arrows:number}>()
const emit=defineEmits<{change:[draft:MusterDraft];complete:[draft:MusterDraft];narrate:[text:string]}>()
const draft=ref<MusterDraft>(props.initial?{...props.initial}:{front:false,rear:false,total:null})
const spoken=ref('韩伯站在栈桥上，等候前后两队依次报齐。'),active=ref('')
const ready=computed(()=>!!musterPayload(draft.value))
function check(team:'front'|'rear'){
 active.value=team;draft.value[team]=true;draft.value.total=null
 spoken.value=team==='front'?'前队回报：“十条船，军士全部登岸！”':'后队回报：“十条船，末船也已系牢。人都在！”'
 emit('narrate',team==='front'?'前队回报：十条船，军士全部登岸！':'后队回报：十条船，末船也已系牢。人都在！')
 emit('change',{...draft.value})
}
function select(n:number){draft.value.total=n;emit('change',{...draft.value});spoken.value=n===20?'韩伯合起两队船牌：“二十条，齐了。一条也没落下。”':'两队各报十条。别漏了末船，再合看一次。';emit('narrate',n===20?'二十条，齐了。一条也没落下。':'两队各报十条。别漏了末船，再合看一次。')}
</script>
<template><section class="muster-stage" :class="{still:!motion}" :style="{backgroundImage:`url('${musterBackdrop(arrows)}')`}">
 <div class="muster-scrim"></div><header><span>靠岸之后 · 先人后物</span><h2>人船都齐，才算归来</h2><p>召前后两队报齐，再将船牌交给韩伯。</p></header>
 <div class="muster-manifest">
  <div class="muster-staves"><button v-for="team in (['front','rear'] as const)" :key="team" :class="{checked:draft[team],active:active===team}" @click="check(team)" :aria-pressed="draft[team]" :aria-label="team==='front'?'点验前队':'点验后队'"><small>{{team==='front'?'第一队':'第二队'}}</small><b>{{team==='front'?'前队':'后队'}}</b><span class="tally-marks"><i v-for="n in 10" :key="n" :style="{'--i':n}"></i></span><strong>{{draft[team]?'十条 · 人船齐全':'点旗，等候回报'}}</strong><em>{{draft[team]?'已点验':'候报'}}</em></button></div>
  <p class="muster-response" aria-live="polite">{{spoken}}</p>
  <div v-if="draft.front&&draft.rear" class="muster-total"><p>前后两队合计归队</p><div><button v-for="n in [10,20,30]" :key="n" @click="select(n)" :aria-pressed="draft.total===n" :class="{selected:draft.total===n}"><b>{{n}}</b>条</button></div></div>
  <button class="gold muster-finish" :disabled="!ready" @click="emit('complete',{...draft})">点验无误，交还船牌 ⟶</button>
 </div><aside class="muster-context">借来二十条船，便须交还二十条。<br/>取到多少箭，是下一件要办的事。</aside>
</section></template>
<style scoped>
.muster-stage{position:absolute;inset:0;min-height:620px;background:#0b1a1e url('/v13/muster-dock.webp') center/cover}.muster-scrim{position:absolute;inset:0;background:linear-gradient(90deg,#08171dda,#08171d66 65%,#08171d1a),linear-gradient(0deg,#091b23,transparent 50%)}header{position:relative;padding:10vh 6vw 0}header span{font-size:12px;letter-spacing:.23em;color:#d3b478}header h2{font:40px/1.4 SimSun;margin:12px 0;color:#f3e4c6}header p{font-size:14px;color:#d0d8d4}.muster-manifest{position:relative;margin:25px 6vw;width:min(580px,85vw)}.muster-staves{display:grid;grid-template-columns:1fr 1fr;gap:24px}.muster-staves button{display:grid;grid-template-columns:1fr auto;gap:8px;text-align:left;padding:20px 24px;background:linear-gradient(100deg,#b1915bdc,#dbc697ed)!important;color:#31291d!important;border-top:4px solid #77603d!important;box-shadow:0 12px 25px #0005;clip-path:polygon(0 0,100% 0,100% 92%,95% 100%,0 100%);transition:transform .25s}.muster-staves button:hover{transform:translateY(-4px)}.muster-staves b{grid-row:2;font:30px SimSun}.muster-staves small{grid-column:1;font-size:10px;letter-spacing:.15em}.muster-staves strong{grid-column:1/3;font-size:12px;font-weight:400}.muster-staves em{grid-row:1/3;grid-column:2;border:1px solid #665736;padding:8px;writing-mode:vertical-rl;font:16px SimSun;font-style:normal;opacity:.5}.muster-staves .checked em{color:#663a26;opacity:1;border:2px solid #663a26;transform:rotate(-8deg)}.tally-marks{grid-column:1/3;display:flex;gap:8px;margin:10px 0}.tally-marks i{width:3px;height:24px;background:#665c45;opacity:.16;transform:rotate(8deg)}.checked .tally-marks i{opacity:.9;animation:tally-in .3s both;animation-delay:calc(var(--i)*.05s)}.muster-response{min-height:3.2em;line-height:1.6;color:#f1e2bf;font:17px/1.8 SimSun;margin:20px 0 10px}.muster-total{display:flex;align-items:center;gap:24px;margin-bottom:15px}.muster-total p{font-size:12px}.muster-total>div{display:flex;gap:14px}.muster-total button{border-bottom:2px solid #a59165!important;padding:6px 12px!important;color:#dcc796!important}.muster-total button b{font:28px Georgia;margin-right:7px}.muster-total button.selected{background:#cead71!important;color:#17252b!important}.muster-finish{min-width:270px}.muster-context{position:absolute;right:6vw;bottom:10vh;font:18px/2 SimSun;color:#ece0c3;text-shadow:0 2px 10px #000}@keyframes tally-in{from{opacity:0;transform:translateY(-8px)}to{opacity:.9;transform:rotate(8deg)}}.still *{animation:none!important}@media(max-width:900px){.muster-context{display:none}header{padding-top:90px}.muster-manifest{margin-top:15px}}@media(max-height:760px){header{padding-top:65px}header h2{font-size:28px;margin:8px 0}.muster-staves button{padding:12px 20px}.muster-manifest{margin-top:12px}.muster-response{margin-top:12px}.muster-total{margin-bottom:10px}.muster-finish{padding:12px 20px}}@media(max-width:550px){.muster-staves{gap:10px}.muster-staves button{padding:15px 12px}.tally-marks{gap:6px}.muster-total{display:block}.muster-stage{min-height:720px}.muster-staves strong{font-size:11px}}@media(prefers-reduced-motion:reduce){.tally-marks i{animation:none!important}}
</style>
