export type BattlePhase='warning'|'first'|'second'
export type Flight={start:number;duration:number;sx:number;sy:number;sz:number;ex:number;ey:number;ez:number;arc:number;water:boolean;flyby:boolean;size:number}
export function battleSchedule(phase:BattlePhase):Flight[]{
 let seed=phase==='second'?1602:1601
 const rand=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296}
 const count=phase==='warning'?18:phase==='second'?680:480,rows:Flight[]=[]
 for(let i=0;i<count;i++){
  const t=rand(),water=phase==='warning'||rand()<.16,side=water?(rand()<.5?-1:1):(phase==='second'?1:-1)
  const flyby=!water&&rand()<.13,ez=flyby?13:-14+rand()*11,distance=10-ez
  rows.push({start:phase==='warning'?t*2:.3+Math.sqrt(t)*(phase==='second'?9:7.8),duration:1.5+rand()*.8,sx:(rand()-.5)*85,sy:4+rand()*12,sz:-90-rand()*35,ex:flyby?(rand()-.5)*6:side*(.3+rand()*.52)*distance*.84,ey:flyby?(rand()-.5)*3:-(.15+rand()*.48)*distance*.52,ez,arc:8+rand()*10,water,flyby,size:.8+rand()*.5})
 }
 return rows.sort((a,b)=>a.start-b.start)
}
export function arrowPose(a:Flight,t:number){
 t=Math.max(0,Math.min(1,t));return {x:a.sx+(a.ex-a.sx)*t,y:a.sy+(a.ey-a.sy)*t+Math.sin(t*Math.PI)*a.arc,z:a.sz+(a.ez-a.sz)*t}
}
