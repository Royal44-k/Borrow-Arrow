"""S1.1 deterministic course runtime; no model calls and no hidden-state responses."""
import copy
import hashlib
import hmac
import json
import re
import secrets
from threading import RLock
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from .models import uid, now
from .platform import Ownership
from .s11_models import S11Base, S11Session, S11Route, S11Snapshot, S11Request, S11Preset, S11Task
from .s11_runtime import CONTENT, NETWORK, NODES, PRESETS, initial, legal, advance, scene_line, render_edge, ending
from .s11_help import scene_help
from .s11_tasks import normalize as normalize_task, protect_prefix, public_task

ROLES={'L':'鲁肃','Z':'诸葛亮','C':'曹操'}
ROLE_ALIASES={'R_LUSU':'L','R_ZHUGE':'Z','R_CAO':'C'}
SCENARIOS={'standard':'江上借箭','late_fog':'等一更再看江面','clear':'清夜行船','quiet':'寨中未开弓','fire_contact':'船边火光','fire_miss':'火箭落水','fire_after_turn':'转舷时的火光','counterfire':'北岸遭遇还箭','no_contact':'北岸巡夜'}
K1_FOLLOWUP=json.loads((CONTENT/'k1-followup.json').read_text(encoding='utf-8'))

def fail(code,message):raise HTTPException(code,message)
def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def role_id(value):
    value=ROLE_ALIASES.get(value,value)
    if value not in ROLES:fail(422,'请选择鲁肃、诸葛亮或曹操。')
    return value

def interaction(edge,state):
    eid=edge['id']
    if eid.startswith('S1.'):return 'material'
    if eid.startswith('S2.'):return 'layout'
    if eid in ['A0.turn','A2.back','A3.turn']:return 'turn'
    if eid=='R0.return':return 'return'
    if eid=='COUNT1.done':return 'collect'
    if eid=='F1.water':return 'water'
    if eid=='S8.ask':return 'expression'
    if eid.startswith('S9.'):return 'position'
    if eid=='S10.drum' or (eid=='S11.change' and state['method']!='drum'):return 'drum'
    if eid=='S10.hail' or eid=='S11.change':return 'hail'
    return 'continue'

class S11Service:
    def __init__(self,engine,platform):
        self.engine=engine;self.platform=platform;self.lock=RLock()
        S11Base.metadata.create_all(engine)
        self.version_hash=digest(NETWORK)

    def catalog(self,user,replay=False):
        permitted=user['role']=='teacher' or (replay and self.has_completed(user['user_id']))
        return {'version':'S1.1','title':'草船借箭','ai_mode':'authored_context','roles':[{'id':k,'name':v} for k,v in ROLES.items()],
            'scenarios':[{'id':k,'title':v,'description':'课后重玩情境' if k!='standard' else '从借船开始，听眼前人物的话。'} for k,v in SCENARIOS.items() if k=='standard' or permitted]}

    def has_completed(self,student_id):
        routes,_=self.student_routes(student_id)
        return any(r['status']=='ended' for r in routes)

    def set_preset(self,teacher,student_id,body):
        self.platform.target_student(teacher,student_id)
        role=role_id(body.role)
        if body.scenario not in PRESETS or (role!='C' and body.scenario in ['no_contact','counterfire']):fail(422,'此角色没有该预置情境。')
        with self.lock,Session(self.engine) as db,db.begin():
            item=db.get(S11Preset,student_id)
            if not item:item=S11Preset(student_id=student_id);db.add(item)
            item.teacher_id=teacher['user_id'];item.role=role;item.scenario=body.scenario;item.created_at=now()
        return {'student_id':student_id,'role':role,'scenario':body.scenario}

    def create(self,user,body):
        self.platform.require(user,'student')
        role=role_id(body.role);scenario=body.scenario
        if scenario not in PRESETS or (role!='C' and scenario in ['counterfire','no_contact']):fail(422,'此角色没有该重玩情境。')
        if scenario!='standard' and not self.has_completed(user['user_id']):
            with Session(self.engine) as db:
                preset=db.get(S11Preset,user['user_id'])
                if not preset or preset.role!=role or preset.scenario!=scenario:fail(403,'先完成一条故事，再从课后重玩选择情境。')
        names=[user['name']]
        if body.activity_mode=='group':names += [n for n in body.members if n!=user['name']]
        if len(names)>8 or len(set(names))!=len(names):fail(422,'共端成员须互不重名，最多8人。')
        members=[{'id':uid(),'name':name,'account_id':user['user_id'] if i==0 else None} for i,name in enumerate(names)]
        token=secrets.token_urlsafe(32)
        with self.lock, Session(self.engine) as db,db.begin():
            session=S11Session(id=uid(),owner_id=user['user_id'],token_hash=digest(token),members=members,activity_mode=body.activity_mode,version_hash=self.version_hash)
            route=S11Route(id=uid(),session_id=session.id,controller_id=members[0]['id'],node_id='C0' if role=='C' else 'S0',revision=0,state=initial(role,scenario),events=[],expressions=[],supports=[],old_utterances=[],transition=[])
            db.add_all([session,route]);db.flush();self.snapshot(db,route)
            result={'session_id':session.id,'route_id':route.id,'token':token,'view':self.view(db,route,session)}
        # Reuse the platform ownership table without legacy Route rows.
        with self.platform.transaction() as db:
            db.add(Ownership(session_id=result['session_id'],user_id=user['user_id'],member_id=members[0]['id'],activity_mode=body.activity_mode))
        return result

    def authorized(self,db,route_id,user,token):
        route=db.get(S11Route,route_id)
        if not route:fail(404,'路线不存在。')
        session=db.get(S11Session,route.session_id)
        if user['role']!='student' or session.owner_id!=user['user_id']:fail(403,'只能进入本人学习会话。')
        if not token or not hmac.compare_digest(digest(token),session.token_hash):fail(403,'会话凭据无效。')
        if session.version_hash!=self.version_hash:fail(409,'此存档的脚本版本需要对应版本读取。')
        return route,session

    def member(self,session,actor_id):
        member=next((m for m in session.members if m['id']==actor_id),None)
        if not member:fail(403,'操作人不属于此共端会话。')
        return member

    def snapshot(self,db,route):
        snap=S11Snapshot(id=uid(),route_id=route.id,node_id=route.node_id,revision=route.revision,state=copy.deepcopy(route.state),event_count=len(route.events),expression_count=len(route.expressions),support_count=len(route.supports))
        db.add(snap);db.flush();return snap

    @staticmethod
    def snapshot_view(s):
        title=NODES[s.node_id]['title'].replace('K1','')
        if s.state['role']=='C':summary='寨门与哨报，保留这一刻的守寨安排。'
        elif s.node_id=='S8':summary='船在寨外，尚未发声；留下这一问时的来路还在。'
        elif NODES[s.node_id]['kind']=='ending':summary='这一趟已经收束，原来的经过和原话都留在旧路线。'
        elif not s.state['launched']:summary='船仍系在岸边，保留当时的装置和天气。'
        elif s.state['fire_hit']:summary='船边起过火，焦痕与已经取得的箭都保留。'
        elif s.state['first']:summary='船侧已经受箭，保留当时的两舷和朝向。'
        else:summary='船已离岸，保留当时的位置和声息。'
        return {'id':s.id,'node_id':s.node_id,'title':title,'summary':summary,'revision':s.revision,'created_at':s.created_at}

    @staticmethod
    def performed_ending(state):
        result=ending(state);text=result['text'];lines=[]
        names=r'诸葛亮|鲁肃|孔明|曹操|周瑜|韩伯|沈砚|哨长|阿成'
        for match in re.finditer(r'“([^”]+)”',text):
            prefix=text[:match.start()]
            # A subject can look toward another character before speaking.
            # Take the first named person in the current sentence.
            segment=re.split(r'[。！？]',prefix)[-1]
            found=re.search(names,segment)
            if not found:
                found=re.search(names,prefix.split('”')[-1])
            speaker=found.group(0).replace('孔明','诸葛亮') if found else ('岸上军士' if '岸上喊声' in segment else ROLES[state['role']])
            lines.append({'speaker':speaker,'text':match.group(1)})
        shot=text.split('末镜：',1)[-1] if '末镜：' in text else ''
        shot=shot.split(' 己方箭库教学账：',1)[0]
        return {'id':state['ending'],**result,'lines':lines,'closing_shot':shot}

    @staticmethod
    def tally_inventory(route):
        if route.node_id!='COUNT1' or route.state['role']=='C':return None
        values={k:route.state[k] for k in ['first','second','spent','loss']}
        total=values['first']+values['second']-values['spent']-values['loss']
        if total<=0:return None
        right=max(0,values['first']-values['spent']-values['loss'])
        return {**values,'left':max(0,total-right),'right':right,'total':total,'variant':'balance' if values['spent'] else 'sides'}

    def tally_context(self,db,route):
        inventory=self.tally_inventory(route)
        if inventory is None:return {}
        latest=db.scalar(select(S11Task).where(S11Task.route_id==route.id,S11Task.task_id=='M12_TALLY',S11Task.actor_id==route.controller_id).order_by(S11Task.revision.desc()))
        progress={'record_id':None,'status':'not_started','attempts':[]} if not latest else {k:copy.deepcopy(latest.payload[k]) for k in ['record_id','status','attempts']}
        return {'M12_TALLY':{**inventory,'progress':progress}}

    def view(self,db,route,session):
        s=route.state;n=NODES[route.node_id];ended=n['kind']=='ending';cao=s['role']=='C'
        performed=self.performed_ending(s) if ended else None
        if ended:
            last=performed;speech=last['lines'][0]['text'] if last['lines'] else '';title=last['title']
        else:speech=scene_line(n['id'],s,n['speech']);title=n['title']
        if n['id']=='S8' and s['role']=='Z':
            old_question=next((x for x in reversed(route.old_utterances) if x.get('kind')=='rusu_question'),None)
            speech=old_question['text'] if old_question else '孔明，你说来取箭，怎倒把船开到曹营来了？'
        k1_question=n['id']=='S12' and s.get('k1_followup')=='watchboat_visible'
        if k1_question:speech=K1_FOLLOWUP['question'];title='哨艇灯影靠近'
        actions=[]
        for edge in n['edges']:
            if legal(edge,s):
                label,_=render_edge(edge,s,s)
                actions.append({'id':edge['id'],'source_id':edge['id'],'label':label,'kind':interaction(edge,s),'requires_expression':edge['id']=='S8.ask'})
        if len(actions)>3:raise RuntimeError('Authored action cap exceeded')
        returned=any(e['action_id']=='R0.return' for e in route.events)
        collected=any(e['action_id']=='COUNT1.done' for e in route.events)
        extinguished=any(e['action_id'] in ['F1.water','F1.leave'] for e in route.events)
        fire='burning' if s['fire_hit'] and not extinguished else ('extinguished' if s['fire_hit'] and extinguished else 'none')
        if returned and s['fire_hit']:fire='scorched'
        visual={'weather':s['weather'],'distance':s['distance'],'material':s['material'],'layout':s['layout'],'side':'left' if s['turned'] else 'right','fire':fire,'fire_sent':s['fire_sent'],'fire_hit':s['fire_hit'],'returned':returned,'collected':collected,'launched':s['launched'],'drummed':s['drummed'],'hailed':s['hailed']}
        if s.get('k1_followup'):visual['scout_approaching']=bool(s.get('scout_approaching')) and not returned
        net=s['first']+s['second']-s['spent']-s['loss']
        if cao:
            visual.pop('returned');visual.pop('collected')
            visual.update(material=s['material'] if s['revealed'] else 'unknown',layout='unknown',cao_used=s['cao_used'],cao_remaining=s['cao_initial']-s['cao_used'],enemy_arrows='visible_silhouette' if s['first'] else 'unknown')
        else:
            # Loss/spend are taken from the loaded side first; collection moves,
            # rather than duplicates, the actual remaining inventory.
            right=max(0,s['first']-s['spent']-s['loss']);left=max(0,net-right)
            visual.update(first=s['first'],second=s['second'],spent=s['spent'],loss=s['loss'],net=net,arrows={'right':0 if collected else right,'left':0 if collected else left,'tray':net if collected else 0})
        world='ending' if ended else ('camp' if cao else ('count' if n['id']=='COUNT1' else ('return' if n['id']=='R0' else ('shore' if n['scene'] in ['M02','M03','M04'] else 'ship'))))
        snapshots=[self.snapshot_view(x) for x in db.scalars(select(S11Snapshot).where(S11Snapshot.route_id==route.id).order_by(S11Snapshot.revision))]
        old=[] if cao else [x for x in route.old_utterances if x.get('kind') in ['rusu_question','canonical_question']]
        return {'version':'S1.1','session_id':session.id,'route_id':route.id,'revision':route.revision,'role':s['role'],'role_name':ROLES[s['role']],'node_id':n['id'],'scene':n['scene'],'title':title.replace('K1',''),'speaker':'鲁肃' if k1_question else (n['speaker'] if not ended else (performed['lines'][0]['speaker'] if performed['lines'] else ROLES[s['role']])),'lines':self.lines(speech),'prompt':n['prompt'],'actions':actions,'stage':{'world':world},'visual':visual,'ending':performed,'status':'ended' if ended else 'active','members':session.members,'controller_id':route.controller_id,'snapshots':snapshots,'old_utterances':old,'transition':route.transition,'parent_route_id':route.parent_route_id,'replay_context':K1_FOLLOWUP['public_context'] if s.get('k1_followup') and not cao else None,'task_context':self.tally_context(db,route)}

    @staticmethod
    def lines(speech):
        # A full authored utterance is one turn, not one turn per punctuation.
        return [speech.strip()] if speech.strip() else []

    def get_view(self,user,route_id,token):
        with Session(self.engine) as db:
            route,session=self.authorized(db,route_id,user,token)
            return self.view(db,route,session)

    def list_routes(self,user,session_id,token):
        with Session(self.engine) as db:
            session=db.get(S11Session,session_id)
            if not session:fail(404,'会话不存在。')
            routes=list(db.scalars(select(S11Route).where(S11Route.session_id==session_id).order_by(S11Route.created_at)))
            self.authorized(db,routes[0].id,user,token)
            return {'routes':[{'id':r.id,'route_id':r.id,'role':r.state['role'],'role_name':ROLES[r.state['role']],'status':'ended' if NODES[r.node_id]['kind']=='ending' else 'active','parent_route_id':r.parent_route_id,'created_at':r.created_at} for r in routes]}

    def mutate(self,user,route_id,token,kind,body):
        fingerprint=digest({'kind':kind,'body':body.model_dump()})
        with self.lock,Session(self.engine) as db,db.begin():
            route,session=self.authorized(db,route_id,user,token)
            old=db.scalar(select(S11Request).where(S11Request.route_id==route_id,S11Request.request_id==body.request_id))
            if old:
                if old.fingerprint!=fingerprint:fail(409,'此请求编号已用于另一项操作。')
                return old.response
            if body.expected_revision!=route.revision:fail(409,'画面已更新，请读取最新场景。')
            member=self.member(session,body.actor_id)
            if kind in ['actions','control','forks'] and body.actor_id!=route.controller_id:fail(403,'请由当前操作者传令，或先交接操作。')
            # Compare-and-swap also protects against a second service process.
            result=db.execute(update(S11Route).where(S11Route.id==route.id,S11Route.revision==body.expected_revision).values(revision=route.revision+1).execution_options(synchronize_session=False))
            if result.rowcount!=1:fail(409,'路线同时被更新，请读取最新场景。')
            route.revision+=1
            extra={}
            if kind=='actions':self.do_action(route,session,member,body)
            elif kind=='expressions':extra['saved_expression']=self.do_expression(route,session,member,body)
            elif kind=='help':extra['help']=self.do_help(route,session,member,body)
            elif kind=='tasks':extra['saved_task']=self.do_task(db,route,session,member,body)
            elif kind=='control':self.member(session,body.controller_id);route.controller_id=body.controller_id;route.transition=[]
            elif kind=='forks':
                child=self.do_fork(db,route,session,member,body)
                self.snapshot(db,route);self.snapshot(db,child)
                response=self.view(db,child,session)
                db.add(S11Request(route_id=route_id,request_id=body.request_id,fingerprint=fingerprint,response=response))
                return response
            db.flush();self.snapshot(db,route)
            response=self.view(db,route,session);response.update(extra)
            db.add(S11Request(route_id=route_id,request_id=body.request_id,fingerprint=fingerprint,response=response))
            return response

    def do_action(self,route,session,member,body):
        node=NODES[route.node_id];state=route.state
        edge=next((e for e in node['edges'] if e['id']==body.action_id and legal(e,state)),None)
        if not edge:fail(422,'此刻没有这个动作。')
        if edge['id']=='S8.ask' and not any(e['node_id']=='S8' and e['actor_id']==body.actor_id and e['kind'] in ['rusu_question','zhuge_answer'] for e in route.expressions):
            fail(422,'先留下你这一次要说的话，再向人物开口。')
        transition=[];events=list(route.events)
        for _ in range(20):
            before=state;state=advance(edge,before);label,reply=render_edge(edge,before,state)
            source_node=NODES[route.node_id]
            # Authored direction is used as visible action narration. Quotes are
            # emitted with their actual named speakers when present.
            performed=self.spoken_transition(reply,source_node,edge,state)
            transition.extend(performed)
            situation=edge['id']=='K1.watchboat'
            events.append({'id':uid(),'route_id':route.id,'node_id':route.node_id,'action_id':edge['id'],'label':label,'role':state['role'],'actor_id':None if situation else member['id'],'author_name':'场景' if situation else member['name'],'account_id':None if situation else member['account_id'],'activity_mode':session.activity_mode,'kind':'situation' if situation else ('director' if source_node['kind']=='director' else 'action'),'reaction':' '.join(t['speaker']+'：'+t['text'] for t in performed),'created_at':now()})
            route.node_id=edge['to']
            if NODES[route.node_id]['kind']!='director':break
            edges=[K1_FOLLOWUP['transition']] if route.node_id=='D0' and state.get('k1_followup')=='awaiting_signal' else [e for e in NODES[route.node_id]['edges'] if legal(e,state)]
            if len(edges)!=1:raise RuntimeError('Director must have one deterministic transition')
            edge=edges[0]
        else:raise RuntimeError('Director cycle')
        route.state=state;route.events=events;route.transition=transition

    @staticmethod
    def spoken_transition(reply,node,edge,state):
        if edge['id']=='S8.ask':
            return [{'speaker':'诸葛亮' if state['role']=='L' else '鲁肃','text':'不登岸，各船听号令。韩伯，把来路留好。' if state['role']=='L' else '退路说清了，我去告诉韩伯，各船跟紧。','source_id':edge['id']}]
        quotes=re.findall(r'([\u4e00-\u9fff]{1,5})[：:]“([^”]+)”',reply)
        if quotes:return [{'speaker':speaker.replace('孔明','诸葛亮').replace('岸上传来','岸上军士'),'text':text,'source_id':edge['id']} for speaker,text in quotes]
        if edge['id']=='S2.one':return [{'speaker':'韩伯','text':'先生吩咐两侧。你留一边空着，那边的人可不能站出去。','source_id':edge['id']}]
        if edge['id'] in ['A2.fire','A4.fire']:return [{'speaker':'沈砚','text':'这一筐是八千支。发出去的，就不能再交了。','source_id':edge['id']}]
        # Unquoted physical direction is performed by the stage. The next
        # node owns its opening utterance; copying it here causes two deliveries.
        return []

    def attribution(self,route,session,member):
        return {'id':uid(),'route_id':route.id,'node_id':route.node_id,'actor_id':member['id'],'author_name':member['name'],'account_id':member['account_id'],'activity_mode':session.activity_mode,'created_at':now()}

    def do_expression(self,route,session,member,body):
        text=body.text.strip()
        if not text:fail(422,'请留下你自己的话。')
        kind=('rusu_question' if route.state['role']=='L' else 'zhuge_answer') if route.node_id=='S8' and route.state['role']!='C' else body.kind
        goal='G5' if route.parent_route_id else ('G2' if route.node_id=='S8' else ('G3' if NODES[route.node_id]['scene'] in ['M09','M10'] else ('G4' if route.node_id in ['R0','COUNT1'] else 'G1')))
        item={**self.attribution(route,session,member),'text':text,'kind':kind,'role':route.state['role'],'goal_id':goal,'support_ids':list(dict.fromkeys(s.get('origin_support_id',s['id']) for s in route.supports if member['id'] in s.get('exposed_to',[s['actor_id']]))) }
        if route.node_id=='S8' and route.state['role']=='Z':
            question=next((x for x in reversed(route.old_utterances) if x.get('kind')=='rusu_question'),None)
            item.update(responds_to_id=question['id'] if question else None,responds_to_route_id=question['route_id'] if question else None,response_basis='saved_original_question' if question else 'canonical_script_question')
        route.expressions=[*route.expressions,item];route.transition=[]
        return item

    def do_help(self,route,session,member,body):
        s=route.state;speaker,text=scene_help(route.node_id,s,body.level)
        exposed=[m['id'] for m in session.members] if session.activity_mode=='group' else [member['id']]
        item={**self.attribution(route,session,member),'level':body.level,'text':text,'speaker':speaker,'source':'authored_context','role':s['role'],'exposed_to':exposed,'exposure_kind':'shared_screen' if session.activity_mode=='group' else 'individual'}
        route.supports=[*route.supports,item];route.transition=[];return item

    def do_task(self,db,route,session,member,body):
        task_id=body.task_id
        if task_id=='M12_TALLY':return self.do_tally(db,route,session,member,body.payload)
        allowed={'M03_PASSAGE':{'S1','S2'},'M07_SIDE':{'A0','A2','A3'},'M09_LISTEN':{'S11','S12','S15','S16','S17'}}
        if route.state['role']=='C' or route.node_id not in allowed[task_id]:fail(422,'此时不在这项任务的实际场景。')
        if task_id in ['M03_PASSAGE','M07_SIDE'] and member['id']!=route.controller_id:fail(403,'这项操作由当前操作者留下记录。')
        if task_id=='M07_SIDE' and not any(legal(e,route.state) and interaction(e,route.state)=='turn' for e in NODES[route.node_id]['edges']):fail(422,'此刻没有可执行的转舷任务。')
        data=normalize_task(task_id,body.payload,route.supports,member['id'])
        previous=db.scalar(select(S11Task).where(S11Task.route_id==route.id,S11Task.record_id==data['record_id']).order_by(S11Task.revision.desc()))
        if previous:
            if previous.actor_id!=member['id']:fail(403,'不能覆盖另一位成员的任务署名；请另开本人记录。')
            if previous.task_id!=task_id:fail(409,'此记录编号已经用于另一项任务。')
            protect_prefix(task_id,previous.payload,data)
            if previous.payload==data:return public_task(previous)
        row=S11Task(id=uid(),route_id=route.id,node_id=route.node_id,task_id=task_id,record_id=data['record_id'],actor_id=member['id'],account_id=member['account_id'],author_name=member['name'],activity_mode=session.activity_mode,revision=route.revision,payload=copy.deepcopy(data),previous_submission_id=previous.id if previous else None)
        db.add(row);db.flush()
        if task_id=='M09_LISTEN' and data['response'].strip() and (not previous or previous.payload['response']!=data['response']):
            support_ids=list(dict.fromkeys(s.get('origin_support_id',s['id']) for s in route.supports if member['id'] in s.get('exposed_to',[s['actor_id']])))
            expression={**self.attribution(route,session,member),'text':data['response'],'kind':'process_response','role':route.state['role'],'goal_id':'G3','support_ids':support_ids,'task_record_id':data['record_id'],'task_submission_id':row.id}
            route.expressions=[*route.expressions,expression]
        route.transition=[]
        return public_task(row)

    def do_tally(self,db,route,session,member,payload):
        inventory=self.tally_inventory(route)
        if inventory is None:fail(422,'此刻没有需要填写的归岸箭簿。空返只说明实际无箭。')
        if member['id']!=route.controller_id:fail(403,'请由当前操作者留下本次清点记录。')
        if not isinstance(payload,dict):fail(422,'清点记录格式不合法。')
        record_id=payload.get('record_id');status=payload.get('status')
        if not isinstance(record_id,str) or not 1<=len(record_id.strip())<=120 or not isinstance(status,str) or status not in {'draft','complete'}:fail(422,'请使用有效的清点记录编号与状态。')
        record_id=record_id.strip()
        fields={'record_id','status'}
        if status=='draft':
            fields.add('answer_total')
            if inventory['variant']=='sides':fields.add('answer_side')
        if set(payload)!=fields:fail(422,'只提交本次清点答案；不能提交标准数、判断结果、帮助或历史记录。')
        if status=='draft':
            total=payload['answer_total']
            if type(total) is not int or not 0<=total<=1000000000:fail(422,'应交箭数须填写非负整数。')
            if inventory['variant']=='sides' and (not isinstance(payload['answer_side'],str) or payload['answer_side'] not in {'left','right','equal'}):fail(422,'请选择左舷、右舷或两舷相同。')
        previous=db.scalar(select(S11Task).where(S11Task.route_id==route.id,S11Task.record_id==record_id).order_by(S11Task.revision.desc()))
        if previous:
            if previous.actor_id!=member['id']:fail(403,'不能接管另一位成员的清点记录。')
            if previous.task_id!='M12_TALLY':fail(409,'此记录编号已用于另一项任务。')
            if previous.payload.get('context')!=inventory:fail(409,'本次清点依据已经变化，请重新读取现场，不覆盖原作答。')
        latest=db.scalar(select(S11Task).where(S11Task.route_id==route.id,S11Task.task_id=='M12_TALLY',S11Task.actor_id==member['id']).order_by(S11Task.revision.desc()))
        if latest and latest.record_id!=record_id:fail(409,'本路线已有你的清点记录，请接续原记录。')
        attempts=copy.deepcopy(previous.payload['attempts']) if previous else []
        if status=='complete':
            if not attempts:fail(422,'先留下本次答案并查看反馈，再确认记入箭簿。')
            if previous.payload['status']=='complete':return public_task(previous)
        else:
            if previous and previous.payload['status']=='complete':fail(409,'本次清点已确认；保留原记录，不再覆盖作答。')
            if len(attempts)>=10:fail(409,'已保留十次尝试，请查看反馈后确认本次记录。')
            matches={'total':payload['answer_total']==inventory['total']}
            if inventory['variant']=='sides':
                side='right' if inventory['first']>inventory['second'] else 'left' if inventory['second']>inventory['first'] else 'equal'
                matches['side']=payload['answer_side']==side
            feedback_text=(f"右舷取得{inventory['first']}支，左舷取得{inventory['second']}支；" if inventory['variant']=='sides' else f"本次共取得{inventory['first']+inventory['second']}支；")
            feedback_text+=f"实际射出{inventory['spent']}支，损失{inventory['loss']}支，应交{inventory['total']}支。"
            feedback_text+=('这笔对上了，进帐时照实说。' if all(matches.values()) else '这笔还没对上。把发出去的、留下来的分开，再合一遍，我等你。')
            exposed=[s for s in route.supports if member['id'] in s.get('exposed_to',[s['actor_id']])]
            support_ids=list(dict.fromkeys(s.get('origin_support_id',s['id']) for s in exposed if s.get('source')!='authored_task_feedback'))
            feedback_before=list(dict.fromkeys([a['feedback']['id'] for a in attempts]+[s.get('origin_support_id',s['id']) for s in exposed if s.get('source')=='authored_task_feedback']))
            attempt={'sequence':len(attempts)+1,'answer_total':payload['answer_total'],'created_at':now(),'support_ids':support_ids,'feedback_before':feedback_before,'matches':matches,'feedback':{'id':uid(),'code':'TALLY_CONFIRMED' if all(matches.values()) else 'CHECK_TALLY','text':feedback_text,'source':'authored_task_feedback'}}
            if inventory['variant']=='sides':attempt['answer_side']=payload['answer_side']
            attempts.append(attempt)
            # The returned feedback is visible on the shared screen. Preserve
            # that exposure across controller changes and later snapshot forks.
            feedback=attempt['feedback']
            exposure={**self.attribution(route,session,member),'id':feedback['id'],'level':'feedback','text':feedback['text'],'speaker':'沈砚','source':'authored_task_feedback','role':route.state['role'],'task_id':'M12_TALLY','task_record_id':record_id,'exposed_to':[m['id'] for m in session.members] if session.activity_mode=='group' else [member['id']],'exposure_kind':'shared_screen' if session.activity_mode=='group' else 'individual'}
            route.supports=[*route.supports,exposure]
        data={'record_id':record_id,'status':status,'context':inventory,'attempts':attempts,'completion_meaning':'确认已记录本次作答与反馈，不代表能力达标。'}
        row=S11Task(id=uid(),route_id=route.id,node_id=route.node_id,task_id='M12_TALLY',record_id=record_id,actor_id=member['id'],account_id=member['account_id'],author_name=member['name'],activity_mode=session.activity_mode,revision=route.revision,payload=data,previous_submission_id=previous.id if previous else None)
        db.add(row);db.flush();route.transition=[]
        return public_task(row)

    def do_fork(self,db,route,session,member,body):
        snap=db.get(S11Snapshot,body.snapshot_id)
        if not snap or snap.route_id!=route.id:fail(403,'只能从本路线真实留下的时刻再试。')
        state=copy.deepcopy(snap.state);role=role_id(body.role or state['role']);old_role=state['role'];node=snap.node_id
        old=[*route.old_utterances,*copy.deepcopy(route.expressions[:snap.expression_count])]
        inherited_supports=[{**copy.deepcopy(s),'inherited':True,'origin_support_id':s.get('origin_support_id',s['id']),'origin_route_id':s.get('origin_route_id',s['route_id'])} for s in route.supports[:snap.support_count]]
        state['role']=role
        if node=='S8' and old_role=='L' and role=='Z':state['k1_followup']='awaiting_signal'
        if role!=old_role and 'C' in [role,old_role]:
            if role=='C':
                if node.startswith('X'):pass
                elif node in ['S0','S1','S2','S4','S5','S7']:node='C0'
                elif node in ['S8','S9','S10','S11','S12']:node='C1' if not state['first'] else 'C4'
                elif node in ['F1','F2','F3']:node='C7'
                elif state['exchanged']:node='C6'
                elif state['revealed']:node='C5'
                elif node in ['R0','COUNT1']:node='CX';state['ending']=self.resolve_ending(state)
                else:node='C2' if not state['second'] else 'CX';state['ending']=self.resolve_ending(state)
                # Ship-side acquisition does not establish the exact northern
                # stock expenditure; known scripted volley correspondence only.
                state['cao_used']=(60000 if state['first'] else 0)+(60000 if state['second'] else 0)+(800 if state['fire_sent'] else 0)
            else:
                node={'C0':'S0','C1':'S10','C2':'A0','C3':'S15','C4':'S11','C5':'S16','C6':'R0','C7':'F3' if state['fire_hit'] else 'F2','CX':'R0'}.get(node,node)
                state['turned']=bool(state['second']);state['method']='drum';state['drummed']=True
        inherited_events=[{**copy.deepcopy(e),'inherited':True,'origin_event_id':e.get('origin_event_id',e['id'])} for e in route.events[:snap.event_count]]
        child=S11Route(id=uid(),session_id=session.id,parent_route_id=route.id,controller_id=member['id'],node_id=node,revision=0,state=state,events=inherited_events,expressions=[],supports=inherited_supports,old_utterances=old,transition=[])
        db.add(child);db.flush();return child

    @staticmethod
    def resolve_ending(s):
        if s['exchanged']:return 'E6'
        if s['fire_hit']:return 'E5'
        if s['late']:return 'E8'
        if s['revealed']:return 'E3'
        net=s['first']+s['second']-s['spent']-s['loss']
        return 'E1' if net>=100000 else ('E2' if net else 'E4')

    def review(self,user,route_id,token):
        with Session(self.engine) as db:
            route,session=self.authorized(db,route_id,user,token)
            return {'route_id':route.id,'role':route.state['role'],'parent_route_id':route.parent_route_id,'events':[e for e in route.events if e['kind'] in ['action','situation'] and e.get('role')==route.state['role']],'tasks':[public_task(t) for t in db.scalars(select(S11Task).where(S11Task.route_id==route.id).order_by(S11Task.revision))],'expressions':route.expressions,'supports':[s for s in route.supports if s.get('role')==route.state['role']],'old_utterances':[] if route.state['role']=='C' else route.old_utterances,'snapshots':self.view(db,route,session)['snapshots'],'limitations':['共端成员为本机会话署名，未绑定账号的同伴不能作为已认证个人能力证据。','重玩继承的旧句保留原作者，不计为新角色的新表达。']}

    def student_routes(self,student_id):
        with Session(self.engine) as db:
            sessions=list(db.scalars(select(S11Session).where(S11Session.owner_id==student_id)))
            owner_map={s.id:{'member_id':s.members[0]['id'],'mode':s.activity_mode} for s in sessions}
            if not owner_map:return [],{}
            routes=list(db.scalars(select(S11Route).where(S11Route.session_id.in_(owner_map)).order_by(S11Route.created_at)))
            return [{'id':r.id,'route_id':r.id,'session_id':r.session_id,'role':r.state['role'],'status':'ended' if NODES[r.node_id]['kind']=='ending' else 'active','created_at':r.created_at,'version':'S1.1','parent_route_id':r.parent_route_id} for r in routes],owner_map

    def student_evidence(self,student_id):
        routes,owners=self.student_routes(student_id)
        result={'routes':routes,'expressions':[],'supports':[],'events':[],'old_utterances':[],'tasks':[]}
        with Session(self.engine) as db:
            for r in routes:
                row=db.get(S11Route,r['id'])
                result['expressions'].extend(row.expressions)
                # A fork contains only the help included in its saved snapshot.
                # Keep the original attribution, but identify the container so
                # analysis can see help already carried into this child route.
                result['supports'].extend({**s,'evidence_route_id':row.id} for s in row.supports)
                result['events'].extend([e for e in row.events if e['kind'] in ['action','situation'] and not e.get('inherited')])
                result['old_utterances'].extend([{**e,'origin_route_id':e.get('origin_route_id',e['route_id']),'origin_expression_id':e.get('origin_expression_id',e['id']),'route_id':row.id,'inherited':True} for e in row.old_utterances])
                result['tasks'].extend(public_task(t) for t in db.scalars(select(S11Task).where(S11Task.route_id==row.id).order_by(S11Task.revision)))
        return result

