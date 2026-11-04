import type {StoryAction,StoryView} from './cinematic'
import type {ShipTask} from './shipTasks'

/** Embedded tasks occur only where the student's chosen action needs them. */
export function taskBeforeAction(view:Pick<StoryView,'node_id'|'role'>, action:StoryAction):ShipTask|null {
 if(view.role==='C')return null
 if(view.node_id==='S2'&&['S2.one','S2.both'].includes(action.id))return 'passage'
 if(['A0','A2','A3'].includes(view.node_id)&&(action.kind==='turn'||['A0.turn','A2.back','A3.turn'].includes(action.id)))return 'side'
 // Hearing belongs to the scene. It must never delay a retreat or demand a
 // written response before an already intelligible choice can be made.
 return null
}
export function taskIdentity(route:string,node:string,actor:string,task:string){return [route,node,actor,task].join(':')}
