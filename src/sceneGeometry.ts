export type SceneSide = 'right' | 'left';
export type SceneLayout = 'none' | 'right' | 'both';
export type SceneMaterial = 'none' | 'straw' | 'armor';
export interface Placement { x:number; z:number; side:SceneSide; index:number }
export interface Bundle extends Placement { id:string }
/** Coordinates belong to the boat, never the observing camera. Right = positive z. */
export function placementsFor(layout:SceneLayout):Placement[] {
  if (layout==='none') return [];
  return (layout==='both'?['right','left']:['right']).flatMap(side =>
    Array.from({length:8},(_,index) => ({x:-3.5+index,z:(side==='right'?1:-1)*(1.1+.28*Math.sin(index/7*Math.PI)),side:side as SceneSide,index})));
}
export function sideForHeading(heading:number):SceneSide {
  return Math.cos((Number.isFinite(heading)?heading:0)*Math.PI/180) < 0 ? 'left' : 'right';
}
/** These are representative visible bundles, never a conversion to the story inventory. */
export function collectionBundles(material:SceneMaterial,layout:SceneLayout,first:number,second:number):Bundle[] {
  if(material==='none') return [];
  return placementsFor(layout).filter(p => [1,3,6].includes(p.index) && Number.isFinite(p.side==='right'?first:second) && (p.side==='right'?first:second)>0)
    .map(p=>({...p,id:`${p.side}-${p.index}`}));
}
export function takeBundle(bundles:Bundle[],collected:string[],id:string) {
  const accepted=bundles.some(b=>b.id===id) && !collected.includes(id);
  const next=accepted?[...collected,id]:[...collected];
  return {accepted,collected:next,complete:bundles.length>0 && bundles.every(b=>next.includes(b.id))};
}
export function fleetHeading(from:number,to:number,progress:number,index:number) {
  const delay=Math.min(19,Math.max(0,index))*.016;
  const t=Math.max(0,Math.min(1,(progress-delay)/(1-delay)));
  return from+(to-from)*(t*t*(3-2*t));
}

export function representativeBundleId(side:SceneSide,index:number):string { return side+'-'+(index<3?1:index<5?3:6); }

export function stageCommand(mode:string):string|null { return mode==='return'?'return-confirm':mode==='helm'?'helm-confirm':null; }
export function stageVisibility(perspective:'ship'|'shore',enemyVisible:boolean) {const ship=perspective==='ship';return {showFleet:ship||enemyVisible,shipDetails:ship,allowZoom:ship};}

export function arrowBatchPhase(current:number,target:number,now:number,started:number|null):string {if(Math.abs(current-target)>.05)return 'turning';if(started===null)return 'ready';return now-started>=2.9?'settled':'flying';}
export function encodeBundleTransfer(id:string):string {return 'caocuan-arrow:'+id;}
export function resolveBundleTransfer(payload:string,fallback:string,bundles:Bundle[],collected:string[]):string {const id=payload.startsWith('caocuan-arrow:')?payload.slice(14):payload?'':fallback;return bundles.some(b=>b.id===id)&&!collected.includes(id)?id:'';}

export function pointerDroppedInBasket(start:{x:number;y:number},end:{x:number;y:number},rect:{left:number;right:number;top:number;bottom:number}|undefined):boolean {return !!rect&&Math.hypot(end.x-start.x,end.y-start.y)>=8&&end.x>=rect.left&&end.x<=rect.right&&end.y>=rect.top&&end.y<=rect.bottom;}

export function scoutPosition(progress:number):[number,number,number] {const t=Number.isFinite(progress)?Math.max(0,Math.min(1,progress)):0;return [8,-.1,28-11*t*t*(3-2*t)];}

export function hotspotInSafeArea(mode:string,x:number,y:number,height:number):boolean {if(mode!=='river'&&mode!=='inspect')return true;return y>=90&&y<=height-150&&!(x<360&&y<190);}

export interface StageShot {kind:'shore'|'deck'|'object'|'fleet'|'collection';position:[number,number,number];target:[number,number,number];fov:number}
/** Object shots use boat-local coordinates; collection and fleet shots use world coordinates. */
export function stageShot(mode:string,perspective:'ship'|'shore',moving:boolean):StageShot {
 if(perspective==='shore')return {kind:'shore',position:[3,3.4,32],target:[-2,2.5,-12],fov:42};
 if(moving||mode==='return')return {kind:'fleet',position:[18,8.5,-24],target:[-3,6.8,-7],fov:45};
 if(mode==='collect')return {kind:'collection',position:[.6,3.8,12.2],target:[.6,1.1,0],fov:43};
 if(mode==='drum')return {kind:'object',position:[4.9,2.5,.35],target:[2.05,.9,.15],fov:43};
 if(mode==='helm')return {kind:'object',position:[-6.9,2.4,.4],target:[-3.6,.85,.15],fov:44};
 if(mode==='fire')return {kind:'object',position:[-2.9,2.6,5.1],target:[-.65,.85,1.1],fov:46};
 if(mode==='river')return {kind:'deck',position:[-6.6,3.2,7.4],target:[2.2,2.55,-.7],fov:48};
 return {kind:'deck',position:[9.5,4.6,9.5],target:[-.2,.8,0],fov:44};
}
export function helmFromDrag(startHeading:number,startX:number,currentX:number,width:number):number {
 if(!Number.isFinite(width)||width<=0)return startHeading;
 return Math.max(0,Math.min(180,Math.round((startHeading+(currentX-startX)/width*180)/15)*15));
}
/** This is a close-up layout of the existing source objects, not an extra arrow inventory. */
export function collectionDisplayPositions(bundles:Bundle[]):Array<{id:string;x:number;z:number}> {
 const gap=1.35,start=-(bundles.length-1)*gap/2-.65;
 return bundles.map((b,i)=>({id:b.id,x:start+i*gap,z:0}));
}

export function shotProgress(now:number,started:number,duration=1.05):number {const t=Math.max(0,Math.min(1,(now-started)/duration));return t*t*(3-2*t);}

/** Ship shots composite actual interactive objects over the original cinematic plate.
 * An opaque procedural dome/water plane would silently erase that plate. */
export function stageLayers(mode:string,perspective:'ship'|'shore') {
 return {opaqueEnvironment:false,contactWater:!['inspect','place','collect'].includes(mode),neighborBoats:perspective==='ship'&&['river','helm','return'].includes(mode)};
}
