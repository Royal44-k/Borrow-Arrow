import test from 'node:test'
import assert from 'node:assert/strict'
import {Narration,type SpeechPort} from '../src/narration.ts'
function setup(){const spoken:string[]=[],events:any[]=[],states:string[]=[];let canceled=0;const port:SpeechPort={cancel(){canceled++},speak(text,e){spoken.push(text);events.push(e)}};const n=new Narration(port,s=>states.push(s));return {n,spoken,events,states,canceled:()=>canceled}}
test('同一发言只入队一次，主动重听才可再次入队',()=>{const s=setup();assert.equal(s.n.play('r:S9:1','前头就是曹营。还往近处走吗？'),true);assert.equal(s.n.play('r:S9:1','前头就是曹营。还往近处走吗？'),false);assert.equal(s.spoken.length,1);assert.equal(s.n.play('r:S9:1',s.spoken[0],true),true);assert.equal(s.spoken.length,2)})
test('换场取消旧音，旧事件不能冒充新场播放成功',()=>{const s=setup();s.n.play('old','旧句');s.n.play('new','新句');assert.equal(s.canceled(),2);s.events[0].start();assert.equal(s.states.at(-1),'starting');s.events[1].start();assert.equal(s.states.at(-1),'speaking');s.n.stop();s.events[1].end();assert.equal(s.states.at(-1),'idle')})
test('失败有明确状态而非假装已朗读，重听可以恢复',()=>{const s=setup();s.n.play('k','句子');s.events[0].error('language-unavailable');assert.equal(s.states.at(-1),'unavailable');s.n.play('k','句子',true);s.events[1].start();s.events[1].end();assert.equal(s.states.at(-1),'finished')})
