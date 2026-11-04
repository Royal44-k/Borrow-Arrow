import type {Line,StoryView} from './cinematic'
export interface SceneCue {id:string;label:string;line:Line;position:'shore'|'water';sound:'quiet'|'oars'|'gong'}
/** Only visible facts from the current authenticated view. No hidden enemy intent. */
export function sceneCue(v:Pick<StoryView,'node_id'|'role'|'visual'>):SceneCue|null {
 if(v.role==='C')return null
 const n=v.node_id
 if(n==='S12'&&v.visual.scout_approaching)return {id:'approaching-oars',label:'循桨声望去',line:{speaker:'韩伯',text:'听，桨声比刚才近了。那一点灯，正往咱们这边来。'},position:'water',sound:'oars'}
 if(n==='S11'||n==='S12')return {id:'no-response',label:'望向寨口',line:{speaker:'阿成',text:'岸灯还亮着。等了这些时候，弓弦还是没响。'},position:'shore',sound:'quiet'}
 if(n==='S15')return {id:'volley-stopped',label:'留意对岸',line:{speaker:'鲁肃',text:'箭停了，灯却还朝着这边。他们是在等，还是看出了什么？'},position:'shore',sound:'quiet'}
 if(n==='S16')return {id:'revealed',label:'望向岸灯',line:{speaker:'韩伯',text:'岸上那声喊，已经认出了船边的东西。再停着，便没了遮掩。'},position:'shore',sound:'quiet'}
 if(n==='S17')return {id:'daybreak',label:'看向天际',line:{speaker:'韩伯',text:v.visual.weather==='clear'?'天亮了，水上的船都露出来了。':'雾薄了，岸楼的轮廓都露出来了。'},position:'shore',sound:'gong'}
 return null
}
