import edges from '../../docs/v14/actual-edges.json'
import registry from '../../docs/v14/shot-map.json'
type Scene={node:string;role:string;weather:string;ending:string|null;cargo?:{arrows:number}}
type Shot={default:string;variants?:{when:Record<string,unknown>;art:string}[]}
const nodes=registry.nodes as Record<string,Shot>
export function shotFor(scene:Scene):string|null{
 const row=nodes[scene.node];if(!row)return null
 const value=(key:string):unknown=>key.split('.').reduce<any>((part,k)=>part?.[k],scene)
 return row.variants?.find(v=>Object.entries(v.when).every(([k,v])=>value(k)===v))?.art||row.default
}

export function nextShots(scene:Scene):string[]{
 const targets=[...new Set(edges.filter(e=>e.role===scene.role&&e.from===scene.node).map(e=>e.to))];
 return [...new Set(targets.map(node=>shotFor({...scene,node})).filter((x):x is string=>!!x))].slice(0,3)
}
