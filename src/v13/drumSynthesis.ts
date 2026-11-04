/** Fixed membrane modes, inharmonic overtones, a felt/wood transient and short diffuse tail.
 * No frequency sweep; seeded noise makes offline regression possible. Peak <= .82. */
export const WAR_DRUM_MODES=Object.freeze([{hz:57,level:.57,decay:1.12},{hz:91,level:.22,decay:.62},{hz:123,level:.13,decay:.38},{hz:166,level:.07,decay:.24},{hz:219,level:.035,decay:.13}])
export function warDrumSamples(sampleRate:number){
 const out=new Float32Array(Math.ceil(sampleRate*2.8));let seed=731,noise=0,peak=0
 for(let i=0;i<out.length;i++){const t=i/sampleRate;seed=(Math.imul(seed,1664525)+1013904223)>>>0;noise=noise*.72+(seed/4294967296*2-1)*.28
  const attack=1-Math.exp(-t/ .0035);let v=0
  for(const m of WAR_DRUM_MODES)v+=Math.sin(2*Math.PI*m.hz*t)*m.level*Math.exp(-t/m.decay)*attack
  v+=noise*.34*Math.exp(-t/.024)+noise*.045*Math.exp(-t/.22)
  // Diffuse bank return, no distinct repeating electronic echo.
  if(t>.065)v+=Math.sin(2*Math.PI*57*(t-.065))*.055*Math.exp(-(t-.065)/.43)*(1-Math.exp(-(t-.065)/.018))
  out[i]=Math.tanh(v*1.25);peak=Math.max(peak,Math.abs(out[i]))
 }
 const gain=.82/Math.max(.82,peak);for(let i=0;i<out.length;i++)out[i]*=gain;return out
}
