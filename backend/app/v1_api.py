"""Authenticated, revisioned V1 routes in a separate table; no model invocation."""
import copy
import hashlib
import json
from threading import RLock
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import String, JSON, select, update
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from .models import uid, now
from .v1_story import initial,scene,step,resolve_response,ROLES,SCENARIOS,SCENARIO_BRIEFS,OperationError

class Base(DeclarativeBase):pass
class Run(Base):
    __tablename__='cinematic_v1_runs'
    id:Mapped[str]=mapped_column(String,primary_key=True)
    owner_id:Mapped[str]=mapped_column(String,index=True)
    created_at:Mapped[str]=mapped_column(String,default=now)
    data:Mapped[dict]=mapped_column(JSON)
class Input(BaseModel):model_config=ConfigDict(extra='forbid')
class New(Input):
    role:str='L';scenario:str='mist';members:list[str]=Field(default_factory=list,max_length=7)
    design_version:str|None=None
class Move(Input):
    request_id:str=Field(min_length=1,max_length=100)
    revision:int=Field(ge=0)
    action:str=Field(min_length=1,max_length=100)
    actor:int=Field(default=0,ge=0,le=7)
    payload:dict=Field(default_factory=dict)
class Fork(Input):snapshot:int=Field(ge=0);role:str|None=None
def fail(code,text):raise HTTPException(code,text)

class V1:
    def __init__(self,engine,platform):
        self.engine=engine;self.platform=platform;self.lock=RLock();Base.metadata.create_all(engine)
    def owned(self,db,id,user):
        row=db.get(Run,id)
        if not row:fail(404,'这段故事不存在。')
        if row.owner_id!=user['user_id']:fail(403,'只能打开本人的故事。')
        return row
    def save_revision(self,db,row,data,expected):
        changed=db.execute(update(Run).where(Run.id==row.id,Run.data['revision'].as_integer()==expected).values(data=data).execution_options(synchronize_session=False))
        if changed.rowcount!=1:fail(409,'另一处窗口已先保存，请重新载入后继续。')
        db.expire(row);db.refresh(row)
    def public(self,row):
        d=row.data;s=d['state'];v=scene(s)
        return {'id':row.id,'revision':d['revision'],'scene':v,'members':d['members'],'parent':d.get('parent'),'snapshots':[{'index':i,'title':scene(x['state'])['title'],'node':x['state']['node']} for i,x in enumerate(d['snapshots'])],
            'history':d['events'],'feedback':d.get('feedback',''),'old_question':s.get('old_question',''),'old_question_source':s.get('old_question_source',''),'question':s.get('question',''),'question_source':s.get('question_source',''),'supports':d['supports'],'expressions':d['expressions'],'status':'ended' if s['node']=='done' else 'active','version':s.get('design_version','V1.0'),'design_version':s.get('design_version','V1.0')}
    def snapshot(self,id,index,user):
        with Session(self.engine) as db:
            row=self.owned(db,id,user);d=copy.deepcopy(row.data)
            if index<0 or index>=len(d['snapshots']):fail(404,'所选片段不存在。')
            snap=d['snapshots'][index];current=d['state']['node']
            d['state']=copy.deepcopy(snap['state'])
            d['events']=d['events'][:snap['event_count']]
            d['supports']=d['supports'][:snap.get('support_count',0)]
            expression_count=snap.get('expression_count')
            if expression_count is None:
                # Legacy snapshots predate this counter; match expressions to
                # successful action provenance in the selected prefix only.
                stamps={(e.get('created_at'),e.get('node_id'),e.get('actor_id')) for e in d['events'] if e.get('kind')=='action'}
                d['expressions']=[x for x in d['expressions'] if (x.get('created_at'),x.get('node_id'),x.get('actor_id')) in stamps]
            else:d['expressions']=d['expressions'][:expression_count]
            projected=Run(id=row.id,owner_id=row.owner_id,data=d)
            result=self.public(projected)
            result.update(preview=True,snapshot_index=index,current_node=current,current_revision=row.data['revision'],feedback='')
            result['scene']['actions']=[]
            return result

    def create(self,user,body):
        self.platform.require(user,'student')
        try:s=initial(body.role,body.scenario,body.design_version)
        except ValueError as e:fail(422,str(e))
        names=[user['name']]+[n.strip() for n in body.members if n.strip()]
        if len(names)!=len(set(names)) or any(len(n)>40 for n in names):fail(422,'共端成员应使用不同的简短姓名。')
        d={'state':s,'revision':0,'members':[{'name':n,'account_id':user['user_id'] if i==0 else None} for i,n in enumerate(names)],'events':[],'expressions':[],'supports':[],'requests':{},'snapshots':[]}
        d['snapshots'].append({'state':copy.deepcopy(s),'event_count':0,'support_count':0})
        with self.lock,Session(self.engine) as db,db.begin():
            row=Run(id=uid(),owner_id=user['user_id'],data=d);db.add(row);db.flush();return self.public(row)
    def move(self,id,user,body):
        with self.lock,Session(self.engine) as db,db.begin():
            row=self.owned(db,id,user);d=copy.deepcopy(row.data)
            fingerprint=hashlib.sha256(json.dumps(body.model_dump(exclude={'request_id'}),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            if body.request_id in d['requests']:
                if d['requests'][body.request_id]!=fingerprint:fail(409,'此提交编号已经用于另一条操作。')
                return self.public(row)
            if body.revision!=d['revision']:fail(409,'另一处窗口已推进故事；请重新载入当前场景。')
            if body.actor>=len(d['members']):fail(422,'请选择实际操作者。')
            before=d['state'];member=d['members'][body.actor];stamp=now();event_id=uid()
            d['feedback']=''
            if body.action=='help':
                if before['node']=='done':fail(409,'故事已结束，请从回望中另开重演。')
                d['supports'].append({'id':event_id,'route_id':id,'node_id':before['node'],'actor_id':str(body.actor),'account_id':member['account_id'],'text':scene(before)['guide_text'],'created_at':stamp,'role':before['role'],'source':'authored_context','speaker':'岑舟'})
            else:
                try:
                    after=step(before,body.action,body.payload)
                    selected,text=resolve_response(before,body.payload,body.action)
                except OperationError as e:
                    d['feedback']=str(e)
                    d['events'].append({'id':event_id,'route_id':id,'node_id':before['node'],'role':before['role'],'kind':'operation_attempt','action_id':body.action,'label':'操作尚未完成：'+str(e),'actor_id':str(body.actor),'account_id':member['account_id'],'author_name':member['name'],'payload':body.payload,'created_at':stamp,'success':False})
                    d['revision']+=1;d['requests'][body.request_id]=fingerprint;self.save_revision(db,row,d,body.revision);return self.public(row)
                except ValueError as e:fail(422,str(e))
                label=next(a['label'] for a in scene(before)['actions'] if a['id']==body.action)
                event_payload=copy.deepcopy(body.payload)
                if selected:
                    event_payload['selected_text']=selected['text'];event_payload['recipient']=selected['recipient']
                    # Older frontends echo the chosen sentence in text; omit that
                    # duplicate so teacher evidence cannot read it as a free response.
                    if not text:event_payload.pop('text',None)
                d['events'].append({'id':event_id,'route_id':id,'node_id':before['node'],'role':before['role'],'action_id':body.action,'label':label,'kind':'action','actor_id':str(body.actor),'author_name':member['name'],'account_id':member['account_id'],'created_at':stamp,'payload':event_payload,'scene_title':scene(before)['title'],'consequence':scene(after)['title']})
                if selected:
                    d['events'].append({'id':uid(),'route_id':id,'node_id':before['node'],'role':before['role'],'kind':'selected_response','source':'selected_response','action_id':body.action,'utterance_id':selected['id'],'text':selected['text'],'recipient':selected['recipient'],'actor_id':str(body.actor),'account_id':member['account_id'],'author_name':member['name'],'created_at':stamp,'label':'对'+selected['recipient']+'说：'+selected['text']})
                if text:
                    d['expressions'].append({'id':uid(),'route_id':id,'node_id':before['node'],'text':text,'source':'learner_original','role':before['role'],'actor_id':str(body.actor),'account_id':member['account_id'],'author_name':member['name'],'created_at':stamp,'goal_id':'G2' if before['node']=='K1' else 'G4','activity_mode':'group' if len(d['members'])>1 else 'individual','support_ids':[x['id'] for x in d['supports'] if x['actor_id']==str(body.actor)]})
                d['state']=after;d['snapshots'].append({'state':copy.deepcopy(after),'event_count':len(d['events']),'support_count':len(d['supports']),'expression_count':len(d['expressions'])})
            d['revision']+=1;d['requests'][body.request_id]=fingerprint;self.save_revision(db,row,d,body.revision);return self.public(row)
    def fork(self,id,user,body):
        with self.lock,Session(self.engine) as db,db.begin():
            row=self.owned(db,id,user);d=copy.deepcopy(row.data)
            if body.snapshot>=len(d['snapshots']):fail(422,'所选片段不存在。')
            snap=d['snapshots'][body.snapshot];s=copy.deepcopy(snap['state']);role=body.role or s['role']
            if role!=s['role']:
                if s['node']!='K1' or s['role']!='L' or role!='Z':fail(422,'换角重演从鲁肃的江上发问处开始。')
                chosen=next((e for e in d['events'] if e['node_id']=='K1' and e.get('kind')=='selected_response'),None)
                original=next((e for e in d['expressions'] if e['node_id']=='K1'),None)
                utterance=(original or chosen) if s.get('design_version') in ('V1.4','V1.5','V1.6') else (chosen or original)
                q=utterance['text'] if utterance else None
                if not q:fail(409,'这条路线还未留下鲁肃的原话。')
                s['role']='Z';s['old_question']=q;s['old_question_source']='learner_original' if utterance is original else 'selected_response';s['question']=''
            support_count=snap.get('support_count',0)
            prefix=[]
            if s.get('design_version') in ('V1.4','V1.5','V1.6'):
                # Earlier scenes are read-only context, not new learner evidence.
                prefix=[{'state':copy.deepcopy(x['state']),'event_count':0,
                         'support_count':0,'expression_count':0,
                         'inherited':True,'origin_route_id':id}
                        for x in d['snapshots'][:body.snapshot]]
            d.update(state=s,revision=0,parent=id,events=[],expressions=[],requests={},snapshots=prefix+[{'state':copy.deepcopy(s),'event_count':0,'support_count':support_count,'expression_count':0}])
            # Supports before the selected point are provenance, never new work.
            d['supports']=[{**x,'inherited':True,'origin_route_id':x['route_id']} for x in d['supports'][:support_count]]
            child=Run(id=uid(),owner_id=user['user_id'],data=d);db.add(child);db.flush();return self.public(child)
    def student_routes(self,student_id):
        with Session(self.engine) as db:
            rows=list(db.scalars(select(Run).where(Run.owner_id==student_id)))
            return [{'id':r.id,'route_id':r.id,'session_id':r.id,'role':r.data['state']['role'],'status':'ended' if r.data['state']['node']=='done' else 'active','created_at':r.created_at,'version':r.data['state'].get('design_version','V1.0'),'design_version':r.data['state'].get('design_version','V1.0'),'parent_route_id':r.data.get('parent')} for r in rows],{r.id:{'member_id':'0','mode':'group' if len(r.data['members'])>1 else 'individual'} for r in rows}
    def student_evidence(self,student_id):
        routes,_=self.student_routes(student_id);out={'routes':routes,'expressions':[],'events':[],'supports':[],'old_utterances':[],'tasks':[]}
        with Session(self.engine) as db:
            for r in routes:
                d=db.get(Run,r['id']).data
                for k in ['expressions','events','supports']:out[k]+=d[k]
        return out

class EvidenceBridge:
    def __init__(self,old,new):self.old=old;self.new=new
    def student_routes(self,id):
        a,ao=self.old.student_routes(id);b,bo=self.new.student_routes(id);return a+b,{**ao,**bo}
    def student_evidence(self,id):
        a=self.old.student_evidence(id);b=self.new.student_evidence(id);return {k:a.get(k,[])+b.get(k,[]) for k in set(a)|set(b)}

def router(service):
    api=APIRouter(prefix='/api/v1',tags=['V1.0'])
    @api.get('/catalog')
    def catalog():return {'version':'V1.6','roles':ROLES,'scenarios':SCENARIOS,'scenario_briefs':SCENARIO_BRIEFS,'supported_design_versions':['V1.0','V1.2','V1.3','V1.4','V1.5','V1.6']}
    @api.post('/runs')
    def create(request:Request,body:New):return service.create(request.state.user,body)
    @api.get('/runs')
    def runs(request:Request):return {'routes':service.student_routes(request.state.user['user_id'])[0]}
    @api.get('/runs/{id}')
    def read(id:str,request:Request):
        with Session(service.engine) as db:return service.public(service.owned(db,id,request.state.user))
    @api.get('/runs/{id}/snapshots/{index}')
    def snapshot(id:str,index:int,request:Request):return service.snapshot(id,index,request.state.user)
    @api.post('/runs/{id}/actions')
    def move(id:str,request:Request,body:Move):return service.move(id,request.state.user,body)
    @api.post('/runs/{id}/fork')
    def fork(id:str,request:Request,body:Fork):return service.fork(id,request.state.user,body)
    return api
