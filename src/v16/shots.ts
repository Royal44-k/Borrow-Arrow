import {shotFor as oldShot,nextShots as oldNext} from '../v15/shots'
export const NEW_SHOTS=['rain_warning','rain_ranks','rain_early_return','turn_gap','rain_listen','rain_lull','rain_feint','rain_escape','C_draw_bows','C_probe_report','C_first_rain','C_stop_signal','C_reload','C_second_rain','C_arrow_depart','C_holdfire','arrows','second']
const edges:Record<string,string[]>={challenge:['rain_warning'],rain_warning:['rain_ranks','rain_early_return'],rain_ranks:['arrows'],arrows:['turn_gap'],side_check:['turn_gap'],turn_gap:['rain_listen','rain_lull','second'],rain_listen:['second'],rain_lull:['rain_feint'],rain_feint:['rain_escape'],C_observe:['C_draw_bows'],C_wait:['C_draw_bows'],C_draw_bows:['C_probe_report','C_first_rain'],C_probe_report:['C_first_rain','C_holdfire'],C_first_rain:['C_shoot'],C_shoot:['C_stop_signal','C_reload'],C_reload:['C_stop_signal','C_second_rain'],C_second_rain:['C_arrow_depart']}
export function shotFor(scene:any):string|null{
 if(scene.design_version!=='V1.6')return oldShot(scene)
 if(scene.node==='C_draw_bows'&&scene.weather==='clear')return 'v16/C_draw_bows_clear'
 return NEW_SHOTS.includes(scene.node)?'v16/'+scene.node:oldShot({...scene,design_version:'V1.5'})
}
export function nextShots(scene:any):string[]{
 if(scene.design_version!=='V1.6')return oldNext(scene)
 return [...new Set([...(edges[scene.node]||[]).map(node=>shotFor({...scene,node})),...oldNext({...scene,design_version:'V1.5'})].filter((v):v is string=>!!v))].slice(0,3)
}
