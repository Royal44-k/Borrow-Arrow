"""LST browser-only demonstration. Same story engine, device-local data, no AI calls.
Not an authentication/security boundary: public accounts and practice keys are inspectable.
"""
import copy,json,re,uuid
from datetime import datetime,timezone
from .v1_story import initial,scene,step,resolve_response,OperationError
from .exam import public_exam,teacher_exam,validate_and_score,EXAM_ID,GOALS,CRITERIA

def uid():return str(uuid.uuid4())
def now():return datetime.now(timezone.utc).isoformat()
class Failure(Exception):
 def __init__(self,status,message):self.status=status;self.message=message
def fail(status,message):raise Failure(status,message)
def require(user,role):
 if user['role']!=role:fail(403,'请切换到对应的体验身份。')
def empty():return dict(runs={},attempts={},comments={},releases={},tokens={},schema=1)
def account(id):
 if id not in ['S001','S002','S003','T001']:fail(401,'请选择公开体验账号 S001、S002、S003 或 T001。')
 return dict(user_id=id,name={'S001':'体验学生一','S002':'体验学生二','S003':'体验学生三','T001':'体验教师'}[id],role='teacher' if id=='T001' else 'student',class_id='LST体验班',class_ids=['LST体验班'],demo=True)
def view(d):
 s=d['state'];return dict(id=d['id'],revision=d['revision'],scene=scene(s),members=d['members'],parent=d.get('parent'),snapshots=[dict(index=i,title=scene(x['state'])['title'],node=x['state']['node']) for i,x in enumerate(d['snapshots'])],history=d['events'],feedback=d.get('feedback',''),old_question=s.get('old_question',''),old_question_source=s.get('old_question_source',''),question=s.get('question',''),question_source=s.get('question_source',''),supports=d['supports'],expressions=d['expressions'],status='ended' if s['node']=='done' else 'active',version=s['design_version'],design_version=s['design_version'])
def snapshot(d):return dict(state=copy.deepcopy(d['state']),event_count=len(d['events']),support_count=len(d['supports']),expression_count=len(d['expressions']))
def owned(store,id,user):
 d=store['runs'].get(id)
 if not d:fail(404,'这段故事不存在。')
 if d['owner']!=user['user_id']:fail(403,'请先切换到创建此存档的体验学生。')
 return d
def routes(store,id):return [dict(id=d['id'],route_id=d['id'],session_id=d['id'],role=d['state']['role'],status='ended' if d['state']['node']=='done' else 'active',created_at=d['created_at'],version='V1.6',design_version='V1.6',parent_route_id=d.get('parent')) for d in store['runs'].values() if d['owner']==id]
def attempt_view(a,teacher=False):
 complete=all(v is not None for v in a['item_scores'].values())
 out={k:a[k] for k in ['id','exam_id','status','created_at','published_at']}
 out.update(total=sum(a['item_scores'].values()) if complete and (teacher or a['status']=='published') else None,max_score=100)
 if teacher:out.update({k:copy.deepcopy(a.get(k)) for k in ['answers','item_scores','review_comment','review_history']},items=teacher_exam()['items'],ai_grade=None)
 return out
def provider():return dict(ready=False,enabled=False,configured=False,mode='disabled',model='',calls_remaining=0)
def detail(store,id):
 student=account(id);rows=[d for d in store['runs'].values() if d['owner']==id]
 evidence={k:[e for d in rows for e in d[k]] for k in ['events','supports','expressions']}
 evidence.update(routes=routes(store,id),tasks=[],old_utterances=[])
 matrix=[]
 for gid,title in GOALS.items():
  items=[dict(e,artifact_id=e['id'],kind='individual_in_group' if e['activity_mode']=='group' else 'individual',support_count=len(e['support_ids'])) for e in evidence['expressions'] if e['account_id']==id and e['goal_id']==gid]
  matrix.append(dict(goal_id=gid,title=title,status='observed' if items else 'unobserved',description='已保留本人表达，需结合情境和帮助核读。' if items else '尚无可归属的表达作品，不由通关推定掌握。',evidence=items))
 comment=copy.deepcopy(store['comments'].get(id));released=store['releases'].get(id)
 if comment:comment['status']='published' if released and released['version']==comment['version'] else 'draft'
 return dict(student=student,routes=routes(store,id),s11=evidence,matrix=matrix,attempts=[attempt_view(a,True) for a in reversed(list(store['attempts'].values())) if a['owner']==id],comment=comment,published_comment=released,ai_mode='disabled',ai_assessment=dict(provider=provider(),latest_analysis=None),limitations=['本页是本机体验记录；不跨设备同步，不用于保存真实学生资料。','真实模型未连接。客观题采用公开规则，表达题由体验教师按量规批阅。','点击、通关、共同操作不直接转换为个人能力分。'])

def dispatch(store,path,method,body,token):
 path=path.removeprefix('/api');b=body or {}
 if path=='/auth/login' and method=='POST':
  u=account(b.get('user_id',''));t=uid();store['tokens'][t]=u['user_id'];return dict(token=t,user=u)
 if token not in store['tokens']:fail(401,'请选择体验身份后继续。')
 user=account(store['tokens'][token]);owner=user['user_id']
 if path=='/auth/me':return dict(user=user)
 if path=='/auth/logout' and method=='POST':store['tokens'].pop(token,None);return dict(ok=True)
 if path=='/v1/runs' and method=='GET':return dict(routes=routes(store,owner))
 if path=='/v1/runs' and method=='POST':
  require(user,'student');s=initial(b.get('role','L'),b.get('scenario','mist'),b.get('design_version','V1.6'))
  names=[user['name']]+[n.strip() for n in b.get('members',[]) if n.strip()]
  if len(names)>8 or len(names)!=len(set(names)) or any(len(n)>40 for n in names):fail(422,'共学成员请使用不同昵称，最多八人。')
  d=dict(id=uid(),owner=owner,created_at=now(),state=s,revision=0,members=[dict(name=n,account_id=owner if i==0 else None) for i,n in enumerate(names)],events=[],expressions=[],supports=[],requests={},snapshots=[])
  d['snapshots'].append(snapshot(d));store['runs'][d['id']]=d;return view(d)
 m=re.fullmatch(r'/v1/runs/([^/]+)(?:/(actions|fork|snapshots/\d+))?',path)
 if m:
  d=owned(store,m[1],user);op=m[2]
  if not op and method=='GET':return view(d)
  if op and op.startswith('snapshots/') and method=='GET':
   i=int(op.split('/')[1])
   if i>=len(d['snapshots']):fail(404,'所选片段不存在。')
   p=copy.deepcopy(d);snap=d['snapshots'][i];p['state']=snap['state']
   for k,c in [('events','event_count'),('supports','support_count'),('expressions','expression_count')]:p[k]=p[k][:snap.get(c,0)]
   out=view(p);out.update(preview=True,snapshot_index=i,current_node=d['state']['node'],current_revision=d['revision'],feedback='');out['scene']['actions']=[];return out
  if op=='fork' and method=='POST':
   i=b.get('snapshot',-1)
   if not isinstance(i,int) or not 0<=i<len(d['snapshots']):fail(422,'所选片段不存在。')
   snap=d['snapshots'][i];s=copy.deepcopy(snap['state']);role=b.get('role') or s['role']
   if role!=s['role']:
    if s['node']!='K1' or s['role']!='L' or role!='Z':fail(422,'从鲁肃的江上发问处换成诸葛亮。')
    original=next((e for e in d['expressions'] if e['node_id']=='K1'),None)
    chosen=next((e for e in d['events'] if e['node_id']=='K1' and e.get('kind')=='selected_response'),None);utterance=original or chosen
    if not utterance:fail(409,'这条路线还没有留下鲁肃的话。')
    s.update(role='Z',old_question=utterance['text'],old_question_source='learner_original' if original else 'selected_response',question='')
   child=copy.deepcopy(d);child.update(id=uid(),created_at=now(),state=s,revision=0,parent=d['id'],events=[],expressions=[],requests={},feedback='')
   child['supports']=[dict(x,inherited=True,origin_route_id=x['route_id']) for x in d['supports'][:snap.get('support_count',0)]]
   child['snapshots']=[dict(state=copy.deepcopy(x['state']),event_count=0,support_count=0,expression_count=0,inherited=True,origin_route_id=d['id']) for x in d['snapshots'][:i]]+[snapshot(child)]
   store['runs'][child['id']]=child;return view(child)
  if op=='actions' and method=='POST':
   fingerprint=json.dumps({k:v for k,v in b.items() if k!='request_id'},sort_keys=True,ensure_ascii=False);rid=b.get('request_id')
   if not isinstance(rid,str) or not 1<=len(rid)<=100:fail(422,'提交编号不合法。')
   if rid in d['requests']:
    if d['requests'][rid]!=fingerprint:fail(409,'此提交编号已用于另一操作。')
    return view(d)
   if b.get('revision')!=d['revision']:fail(409,'另一窗口已经推进故事，请重新打开当前存档。')
   actor=b.get('actor',0)
   if not isinstance(actor,int) or not 0<=actor<len(d['members']):fail(422,'请选择实际操作者。')
   before=d['state'];member=d['members'][actor];action=b.get('action');payload=b.get('payload',{});stamp=now();event_id=uid();d['feedback']=''
   base=dict(id=event_id,route_id=d['id'],node_id=before['node'],role=before['role'],actor_id=str(actor),account_id=member['account_id'],author_name=member['name'],created_at=stamp)
   if action=='help':
    if before['node']=='done':fail(409,'故事已结束，请从回望中另开重演。')
    d['supports'].append(dict(base,text=scene(before)['guide_text'],source='authored_context',speaker='岑舟'))
   else:
    try:after=step(before,action,payload);selected,text=resolve_response(before,payload,action)
    except OperationError as e:
     d['feedback']=str(e);d['events'].append(dict(base,kind='operation_attempt',action_id=action,label='操作尚未完成：'+str(e),payload=payload,success=False));d['revision']+=1;d['requests'][rid]=fingerprint;return view(d)
    label=next(a['label'] for a in scene(before)['actions'] if a['id']==action)
    ep=copy.deepcopy(payload)
    if selected:
     ep.update(selected_text=selected['text'],recipient=selected['recipient'])
     if not text:ep.pop('text',None)
    d['events'].append(dict(base,action_id=action,label=label,kind='action',payload=ep,scene_title=scene(before)['title'],consequence=scene(after)['title']))
    if selected:d['events'].append(dict(base,id=uid(),kind='selected_response',source='selected_response',action_id=action,utterance_id=selected['id'],text=selected['text'],recipient=selected['recipient'],label='对'+selected['recipient']+'说：'+selected['text']))
    if text:d['expressions'].append(dict(base,text=text,source='learner_original',goal_id='G2' if before['node']=='K1' else 'G4',activity_mode='group' if len(d['members'])>1 else 'individual',support_ids=[x['id'] for x in d['supports'] if x['actor_id']==str(actor)]))
    d['state']=after;d['snapshots'].append(snapshot(d))
   d['revision']+=1;d['requests'][rid]=fingerprint;return view(d)
 if path=='/exam' and method=='GET':return public_exam()
 if path=='/exam/attempts':
  require(user,'student')
  if method=='GET':return dict(attempts=[attempt_view(a) for a in reversed(list(store['attempts'].values())) if a['owner']==owner])
  if method=='POST':
   if b.get('exam_id')!=EXAM_ID:fail(409,'试卷版本不匹配。')
   if not b.get('request_id'):fail(422,'缺少交卷编号。')
   old=next((a for a in store['attempts'].values() if a['owner']==owner and a['request_id']==b['request_id']),None)
   if old:
    if old['answers']!=b.get('answers'):fail(409,'该提交编号已经用于另一份答案。')
    return attempt_view(old)
   if not any(r['status']=='ended' for r in routes(store,owner)):fail(409,'请先完成一条故事路线，再交卷。')
   scores=validate_and_score(b.get('answers',{}));a=dict(id=uid(),owner=owner,exam_id=EXAM_ID,request_id=b['request_id'],created_at=now(),published_at=None,answers=b['answers'],item_scores=scores,status='pending_review',review_comment='',review_history=[])
   store['attempts'][a['id']]=a;return attempt_view(a)
 if path.startswith('/teacher/'):
  require(user,'teacher')
  if path=='/teacher/exam':return teacher_exam()
  if path=='/teacher/ai/status':return provider()
  if path.endswith('/ai-grade') or path.endswith('/ai-analysis'):fail(409,'公开体验版不调用真实模型；请使用教师量规批阅。')
  if path=='/teacher/students':
   students=[]
   for id in ['S001','S002','S003']:
    attempts=[a for a in store['attempts'].values() if a['owner']==id];published=next((a for a in reversed(attempts) if a['status']=='published'),None)
    students.append(dict(account(id),route_count=len(routes(store,id)),attempt_count=len(attempts),published_total=attempt_view(published)['total'] if published else None))
   return dict(students=students)
  m=re.fullmatch(r'/teacher/students/([^/]+)(?:/(comment(?:/publish)?))?',path)
  if m:
   id=m[1];account(id)
   if id=='T001':fail(422,'请选学生。')
   if not m[2] and method=='GET':return detail(store,id)
   if m[2]=='comment' and method=='PUT':
    text=b.get('text','')
    if not isinstance(text,str) or len(text)>5000:fail(422,'评语过长。')
    c=dict(text=text,version=store['comments'].get(id,{}).get('version',0)+1,updated_at=now(),teacher_id=owner);store['comments'][id]=c;return c
   if m[2]=='comment/publish' and method=='POST':
    if id not in store['comments']:fail(409,'请先保存评语。')
    store['releases'][id]=copy.deepcopy(store['comments'][id]);return store['releases'][id]
  m=re.fullmatch(r'/teacher/attempts/([^/]+)/(review|publish)',path)
  if m:
   a=store['attempts'].get(m[1])
   if not a:fail(404,'答卷不存在。')
   if m[2]=='review' and method=='PUT':
    if a['status']=='published':fail(409,'已发布答卷不能修改。')
    if not b.get('confirm_rule_fallback'):fail(422,'请确认客观题使用规则评分；未调用模型。')
    if not isinstance(b.get('comment'),str) or not b['comment'].strip():fail(422,'请填写批阅说明。')
    scores=validate_and_score(a['answers']);criteria=b.get('criteria',{})
    for qid,cs in CRITERIA.items():
     values=criteria.get(qid)
     if not isinstance(values,list) or len(values)!=len(cs):fail(422,'请完成每项量规。')
     if any(type(v)!=int or not 0<=v<=c['max_points'] for v,c in zip(values,cs)):fail(422,'量规分数超出范围。')
     if b.get('scores',{}).get(qid)!=sum(values):fail(422,'题目总分与量规不一致。')
     scores[qid]=sum(values)
    a.update(item_scores=scores,status='reviewed',review_comment=b['comment']);a['review_history'].append(dict(id=uid(),teacher_id=owner,created_at=now(),scores=scores,criteria=criteria,comment=b['comment']));return attempt_view(a,True)
   if m[2]=='publish' and method=='POST':
    if a['status'] not in ['reviewed','published'] or any(v is None for v in a['item_scores'].values()):fail(409,'请先完成全部表达题批阅。')
    a.update(status='published',published_at=a['published_at'] or now());return attempt_view(a,True)
 fail(404,'此接口不在公开体验范围。')

def handle(raw):
 request=json.loads(raw);store=request.get('store') or empty();working=copy.deepcopy(store)
 try:
  result=dispatch(working,request['path'],request['method'],request.get('body'),request.get('token'))
  return json.dumps(dict(status=200,data=result,store=working),ensure_ascii=False)
 except Failure as e:return json.dumps(dict(status=e.status,data=dict(detail=e.message)),ensure_ascii=False)
 except (ValueError,KeyError,TypeError) as e:return json.dumps(dict(status=422,data=dict(detail=str(e))),ensure_ascii=False)
