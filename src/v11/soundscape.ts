import {warDrumSamples} from '../v13/drumSynthesis'
/** Original, locally synthesized pentatonic underscore. No external audio service. */
export class Soundscape {
 private drumOutput:GainNode|null=null;private drumVolume=.85;private drumBus:WaveShaperNode|null=null;private drumBuffer:AudioBuffer|null=null;private lastDrum=-10;private ctx:AudioContext|null=null;private music:GainNode|null=null;private environment:GainNode|null=null
 private timer:ReturnType<typeof setInterval>|undefined;private tick=0;private enabled=false;private speaking=false
 private ensure(){if(this.ctx)return;this.ctx=new AudioContext();const c=this.ctx;this.music=c.createGain();this.music.gain.value=0;this.music.connect(c.destination);this.environment=c.createGain();this.environment.gain.value=0;this.environment.connect(c.destination)
  const buffer=c.createBuffer(1,c.sampleRate*8,c.sampleRate),data=buffer.getChannelData(0);let previous=0;for(let i=0;i<data.length;i++){previous=(previous+(Math.random()*2-1)*.025)/1.018;data[i]=previous*2*(.6+.4*Math.sin(i/c.sampleRate*.8)**2)}
  const source=c.createBufferSource();source.buffer=buffer;source.loop=true;const filter=c.createBiquadFilter();filter.type='lowpass';filter.frequency.value=640;source.connect(filter);filter.connect(this.environment);source.start()
  this.timer=setInterval(()=>this.schedule(),720)
 }
 private schedule(){if(!this.ctx||!this.enabled)return;const c=this.ctx,t=c.currentTime;const notes=[146.83,0,220,0,261.63,293.66,0,220,196,0,146.83,0,130.81,0,0,0];const f=notes[this.tick++%notes.length];if(!f)return
  // Soft struck strings with a quiet fifth; short attacks, long decays, sparse phrasing.
  for(const [ratio,level] of [[1,.11],[2,.025],[3,.008]]){const o=c.createOscillator(),g=c.createGain();o.type='sine';o.frequency.value=f*ratio;g.gain.setValueAtTime(0,t);g.gain.linearRampToValueAtTime(level,t+.015);g.gain.exponentialRampToValueAtTime(.0001,t+3.6);o.connect(g);g.connect(this.music!);o.start(t);o.stop(t+3.7)}
  if(this.tick%8===1){const o=c.createOscillator(),g=c.createGain();o.type='sine';o.frequency.value=73.415;g.gain.setValueAtTime(0,t);g.gain.linearRampToValueAtTime(.07,t+.8);g.gain.linearRampToValueAtTime(0,t+5);o.connect(g);g.connect(this.music!);o.start(t);o.stop(t+5.1)}
 }
 set(music:boolean,environment:boolean){this.ensure();this.ctx!.resume();this.enabled=music;this.music!.gain.setTargetAtTime(music?(this.speaking?.15:.45):0,this.ctx!.currentTime,.3);this.environment!.gain.setTargetAtTime(environment?.12:0,this.ctx!.currentTime,.3)}
 duck(speaking:boolean){this.speaking=speaking;if(this.ctx)this.music!.gain.setTargetAtTime(this.enabled?(speaking?.15:.45):0,this.ctx.currentTime,.2)}
 hit(){if(!this.ctx)return;const c=this.ctx,t=c.currentTime,b=c.createBuffer(1,c.sampleRate*.16,c.sampleRate),a=b.getChannelData(0);for(let i=0;i<a.length;i++)a[i]=(Math.random()*2-1)*Math.exp(-i/a.length*9);const s=c.createBufferSource(),g=c.createGain(),f=c.createBiquadFilter();s.buffer=b;f.type='bandpass';f.frequency.value=1350;g.gain.value=.07;s.connect(f);f.connect(g);g.connect(c.destination);s.start(t)}
 setDrumVolume(value:number){this.drumVolume=Number.isFinite(value)?Math.max(0,Math.min(1,value)):0;if(this.ctx&&this.drumOutput)this.drumOutput.gain.setTargetAtTime(this.drumVolume,this.ctx.currentTime,.02)}
 drum(){this.ensure();const c=this.ctx!;void c.resume();const now=c.currentTime;if(now-this.lastDrum<.1)return;this.lastDrum=now;
  if(!this.drumBus){const compressor=c.createDynamicsCompressor();compressor.threshold.value=-10;compressor.knee.value=8;compressor.ratio.value=12;compressor.attack.value=.003;compressor.release.value=.22;
   this.drumBus=c.createWaveShaper();const curve=new Float32Array(4096);for(let i=0;i<curve.length;i++)curve[i]=.88*Math.tanh((i/(curve.length-1)*2-1)*1.4);this.drumBus.curve=curve;this.drumBus.oversample='2x';this.drumBus.connect(compressor);this.drumOutput=c.createGain();this.drumOutput.gain.value=this.drumVolume;compressor.connect(this.drumOutput);this.drumOutput.connect(c.destination);
   const samples=warDrumSamples(c.sampleRate);this.drumBuffer=c.createBuffer(1,samples.length,c.sampleRate);this.drumBuffer.copyToChannel(new Float32Array(samples),0)
  }
  const hit=c.createBufferSource();hit.buffer=this.drumBuffer;const gain=c.createGain();gain.gain.value=1;hit.connect(gain);gain.connect(this.drumBus);hit.onended=()=>{hit.disconnect();gain.disconnect()};hit.start(now)
 }

 close(){clearInterval(this.timer);this.ctx?.close()}
}
