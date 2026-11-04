"""No external model calls: bounded scoring, privacy and review contracts."""
import sys, copy
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
from app.platform import Platform, Attempt, ReviewInput, AIRequest
from app.ai_assessment import validate_grade, validate_analysis, build_analysis_payload, criteria_for, AiRun
from app.ai_provider import DeepSeekProvider, ProviderReply, ProviderError

PAPER={'id':'caocuan-exam-s1.2','items':[
 {'id':'a','type':'single','points':3,'goal_id':'G1','prompt':'期限？','answer_key':'B','options':[{'id':'A','text':'一日'},{'id':'B','text':'三日'}]},
 {'id':'b','type':'fill','points':3,'goal_id':'G2','prompt':'材料？','answer_key':['草束']},
 {'id':'c','type':'reflection','points':4,'goal_id':'G5','prompt':'说出一次调整','rubric_criteria':[{'id':'example','title':'具体经历','max_points':2},{'id':'next','title':'下次安排','max_points':2}]}]}
GOOD={'objective':[{'item_id':'a','score':3,'reason':'答案B符合题面。'},{'item_id':'b','score':3,'reason':'填草束。'}],
 'subjective_suggestions':[{'item_id':'c','criteria':[{'id':'example','score':1,'reason':'有具体动作。'},{'id':'next','score':2,'reason':'提出可执行改变。'}],'feedback':'可以补充当时如何决定。'}], 'summary':'客观答案与题面一致，表达建议须教师复核。'}
class FakeProvider:
 def __init__(self,result=None): self.result=result or GOOD; self.calls=0; self.max_calls=10; self.timeout=45
 def status(self): return {'enabled':True,'configured':True,'ready':True,'model':'deepseek-v4-pro','mode':'test_double','max_calls':self.max_calls,'timeout_seconds':self.timeout}
 def complete(self,system,payload):
  self.calls+=1; self.last=(system,copy.deepcopy(payload))
  if isinstance(self.result,Exception): raise self.result
  return ProviderReply(copy.deepcopy(self.result),'deepseek-v4-pro',{'total_tokens':123})

@pytest.fixture
def env(tmp_path):
 p=Platform(f'sqlite:///{tmp_path/"platform.db"}')
 p.create_account('S1','林同学','student','Password12345','A')
 p.create_account('S2','外班同学','student','Password12345','B')
 p.create_account('T1','老师','teacher','Password12345',class_ids=['A'])
 p.create_account('T2','另班老师','teacher','Password12345',class_ids=['B'])
 def user(uid):
  with Session(p.engine) as db:
   from app.platform import Account
   return p.user(db.get(Account,uid))
 with p.transaction() as db:
  db.add(Attempt(id='attempt',user_id='S1',request_id='r',fingerprint='f',exam_id=PAPER['id'],exam_snapshot=copy.deepcopy(PAPER),answers={'a':'B','b':'草束','c':'我叫林同学，S1，先等了又退。'},item_scores={'a':3,'b':3,'c':None},status='pending_review'))
 p.ai.provider=FakeProvider()
 p.s11=SimpleNamespace(student_evidence=lambda sid:{'routes':[],'expressions':[],'events':[],'supports':[],'tasks':[]})
 return p,user

def test_disabled_provider_no_network_and_no_secret_status(monkeypatch):
 monkeypatch.delenv('CAOCUAN_AI_ENABLED',raising=False)
 monkeypatch.setenv('CAOCUAN_DEEPSEEK_API_KEY','must-not-appear')
 p=DeepSeekProvider(); assert not p.status()['ready']; assert 'must-not-appear' not in str(p.status())
 with pytest.raises(ProviderError,match='disabled'): p.complete('x',{})

def test_grade_bounded_complete_and_no_unknown_item():
 assert validate_grade(GOOD,PAPER,{'a':3,'b':3})['conflict_ids']==[]
 for path,bad in [('score',True),('score',4),('score',-1),('score',1.5)]:
  value=copy.deepcopy(GOOD);value['objective'][0][path]=bad
  with pytest.raises(ValueError): validate_grade(value,PAPER,{'a':3,'b':3})
 value=copy.deepcopy(GOOD);value['objective'][0]['item_id']='invented'
 with pytest.raises(ValueError):validate_grade(value,PAPER,{'a':3,'b':3})

def test_model_disagreement_is_not_silently_replaced():
 value=copy.deepcopy(GOOD);value['objective'][0]['score']=0
 out=validate_grade(value,PAPER,{'a':3,'b':3})
 assert out['conflict_ids']==['a'] and out['objective_results'][0]['model_score']==0 and out['objective_results'][0]['rule_score']==3

def test_teacher_grade_is_idempotent_and_minimizes_identity(env):
 p,user=env
 result=p.ai.grade(user('T1'),'attempt',AIRequest(request_id='g1'))
 assert result['status']=='completed' and result['mode']=='test_double'
 assert p.ai.grade(user('T1'),'attempt',AIRequest(request_id='g1'))['id']==result['id']
 assert p.ai.grade(user('T1'),'attempt',AIRequest(request_id='g2'))['id']==result['id']
 assert p.ai.provider.calls==1
 assert '林同学' not in str(p.ai.provider.last) and 'S1' not in str(p.ai.provider.last)
 assert '忽略' in p.ai.provider.last[0] and 'untrusted_student_data' in p.ai.provider.last[1]
 with Session(p.engine) as db:
  row=db.get(Attempt,'attempt');assert row.item_scores['c'] is None and row.status=='pending_review'

def test_only_teacher_of_class_can_trigger(env):
 p,user=env
 for uid in ['S1','T2']:
  with pytest.raises(HTTPException) as e:p.ai.grade(user(uid),'attempt',AIRequest(request_id='g'))
  assert e.value.status_code==403
 assert p.ai.provider.calls==0

def test_budget_counts_attempts_and_no_automatic_retry(env):
 p,user=env;p.ai.provider.max_calls=1;p.ai.provider.result=ProviderError('timeout')
 first=p.ai.grade(user('T1'),'attempt',AIRequest(request_id='timeout'))
 assert first['status']=='failed' and first['error_code']=='timeout'
 assert p.ai.grade(user('T1'),'attempt',AIRequest(request_id='timeout'))['id']==first['id']
 second=p.ai.grade(user('T1'),'attempt',AIRequest(request_id='new'))
 assert second['status']=='budget_exhausted' and p.ai.provider.calls==1

def test_invalid_model_return_never_changes_grade(env):
 p,user=env;p.ai.provider.result={'objective':[],'summary':'直接给满分'}
 out=p.ai.grade(user('T1'),'attempt',AIRequest(request_id='bad'))
 assert out['status']=='invalid_response'
 with Session(p.engine) as db:assert db.get(Attempt,'attempt').item_scores=={'a':3,'b':3,'c':None}

def test_conflict_needs_teacher_resolution_and_criteria(env):
 p,user=env;p.ai.provider.result=copy.deepcopy(GOOD);p.ai.provider.result['objective'][0]['score']=0
 p.ai.grade(user('T1'),'attempt',AIRequest(request_id='conflict'))
 body={'scores':{'c':3},'criteria':{'c':[1,2]},'comment':'核对了题面和原答。'}
 with pytest.raises(HTTPException):p.review(user('T1'),'attempt',ReviewInput(**body))
 result=p.review(user('T1'),'attempt',ReviewInput(**body,objective_scores={'a':3}))
 assert result['item_scores']=={'a':3,'b':3,'c':3}

def test_rule_only_requires_explicit_teacher_acceptance(env):
 p,user=env
 body={'scores':{'c':3},'criteria':{'c':[1,2]},'comment':'按参考答案与量规复核。'}
 with pytest.raises(HTTPException):p.review(user('T1'),'attempt',ReviewInput(**body))
 p.review(user('T1'),'attempt',ReviewInput(**body,confirm_rule_fallback=True))
 published=p.publish(user('T1'),'attempt');assert published['total']==9
 with pytest.raises(HTTPException):p.ai.grade(user('T1'),'attempt',AIRequest(request_id='after-publish'))

def test_analysis_excludes_peers_names_and_tracks_help():
 source={'expressions':[{'id':'mine','account_id':'S1','author_name':'林同学','route_id':'route1','goal_id':'G4','text':'林同学S1先留退路','support_ids':['h']},{'id':'peer','account_id':None,'author_name':'同伴','text':'不属于本人'}],
 'events':[],'tasks':[],'supports':[{'id':'h','account_id':'S1','text':'先找退路','author_name':'林同学'}]}
 payload,mapping=build_analysis_payload(source,'S1',['S1','林同学'])
 assert '不属于本人' not in str(payload) and '林同学' not in str(payload) and 'S1' not in str(payload)
 assert any(x.get('support_ids') for x in payload['evidence'])
 assert any(x['source_id']=='mine' for x in mapping.values())

def test_analysis_cannot_forge_evidence_or_numeric_ability():
 evidence=[{'id':'E001','kind':'expression','goal_id':'G4','support_ids':['h']}]
 value={'summary':'只针对本次表达。','goals':[{'goal_id':g,'status':'insufficient','observation':'尚缺本人相关作品。','evidence_ids':[],'support_condition':'insufficient','next_step':'补一段自己的安排。'} for g in ['G1','G2','G3','G4','G5']]}
 assert len(validate_analysis(value,evidence)['goals'])==5
 value['goals'][3].update(status='observed',evidence_ids=['not-there'])
 with pytest.raises(ValueError): validate_analysis(value,evidence)
 value['goals'][3].update(evidence_ids=['E001'],support_condition='independent')
 with pytest.raises(ValueError):validate_analysis(value,evidence)
 value['goals'][3]['support_condition']='assisted';value['goals'][3]['score']=95
 with pytest.raises(ValueError):validate_analysis(value,evidence)

def test_no_evidence_returns_no_model_call(env):
 p,user=env
 result=p.ai.analyse(user('T1'),'S1',AIRequest(request_id='empty'))
 assert result['status']=='insufficient_evidence' and p.ai.provider.calls==0

def test_student_attempt_view_excludes_model_results(env):
 p,user=env;p.ai.grade(user('T1'),'attempt',AIRequest(request_id='private'))
 with Session(p.engine) as db:public=p.attempt_view(db.get(Attempt,'attempt'))
 assert not {'answers','items','item_scores','ai_assessment','ai_grading','answer_key'}&public.keys()

def test_process_task_latest_revision_preserves_first_try_and_feedback():
 common={'account_id':'S1','route_id':'r','actor_id':'a','node_id':'M07','task_id':'M07_SIDE','record_id':'rec'}
 first={'sequence':1,'side':'near','feedback_before':[],'support_ids':[]}
 second={'sequence':2,'side':'empty','feedback_before':['compare'],'support_ids':['hint']}
 source={'tasks':[{**common,'id':'old','revision':1,'created_at':'2026-10-28T01:00:00Z','payload':{'record_id':'rec','attempts':[first]}},
 {**common,'id':'new','revision':2,'created_at':'2026-10-28T01:01:00Z','payload':{'record_id':'rec','attempts':[first,second],'feedback':[{'id':'compare','code':'COMPARE_SIDES'}],'status':'completed'}}]}
 payload,mapping=build_analysis_payload(source,'S1',['S1'])
 assert len(payload['evidence'])==2 and {v['source_id'] for v in mapping.values()}=={'new'}
 assert payload['evidence'][0]['payload']['side']=='near' and not payload['evidence'][0]['support_ids']
 assert payload['evidence'][1]['payload']['side']=='empty' and len(payload['evidence'][1]['support_ids'])==2

def test_action_help_does_not_include_future_or_other_member_exposure():
 source={'events':[{'id':'event','kind':'action','route_id':'r','account_id':'S1','actor_id':'a','created_at':'2026-10-28T01:00:00Z','action_id':'S1.straw'}],
 'supports':[{'id':'before','route_id':'r','actor_id':'a','created_at':'2026-10-28T00:50:00Z'},
 {'id':'future','route_id':'r','actor_id':'a','created_at':'2026-10-28T01:10:00Z'},
 {'id':'peer','route_id':'r','actor_id':'b','exposed_to':['b'],'created_at':'2026-10-28T00:40:00Z'}]}
 payload,mapping=build_analysis_payload(source,'S1',['S1'])
 assert len(payload['evidence'][0]['support_ids'])==1
 assert mapping['E001']['support_ids']==['before']

def test_unexpected_provider_failure_finishes_run(env):
 p,user=env;p.ai.provider.result=RuntimeError('secret must not leak')
 out=p.ai.grade(user('T1'),'attempt',AIRequest(request_id='unexpected'))
 assert out['status']=='failed' and 'secret' not in str(out)

def test_request_id_reuse_for_different_kind_is_rejected(env):
 p,user=env;p.ai.grade(user('T1'),'attempt',AIRequest(request_id='reuse'))
 with pytest.raises(HTTPException) as e:p.ai.analyse(user('T1'),'S1',AIRequest(request_id='reuse'))
 assert e.value.status_code==409

def test_score_rules_and_fill_aliases_are_sent_to_model(env):
 p,user=env
 with p.transaction() as db:
  row=db.get(Attempt,'attempt');paper=copy.deepcopy(row.exam_snapshot)
  paper['items'][1].update(score_rule='等价词给3分',accepted_answers=['草束','稻草'])
  row.exam_snapshot=paper
 p.ai.grade(user('T1'),'attempt',AIRequest(request_id='keys'))
 item=p.ai.provider.last[1]['items'][1]
 assert item['accepted_answers']==['草束','稻草'] and item['score_rule']=='等价词给3分'

def test_current_exam_http_submission_review_and_old_open_page_rejection(tmp_path,monkeypatch):
 monkeypatch.setenv('CAOCUAN_AI_ENABLED','0')
 from fastapi.testclient import TestClient
 from app.main import create_app
 from app.exam import teacher_exam
 app=create_app(database_url=f'sqlite:///{tmp_path/"course.db"}',platform_database_url=f'sqlite:///{tmp_path/"accounts.db"}')
 p=app.state.platform
 p.create_account('S','本班生','student','Password12345','A')
 p.create_account('T','本班师','teacher','Password12345',class_ids=['A'])
 p.create_account('OTHER','外班师','teacher','Password12345',class_ids=['B'])
 p.s11=SimpleNamespace(student_routes=lambda sid:([{'id':'r','status':'ended'}],{}),student_evidence=lambda sid:{'routes':[],'expressions':[],'supports':[],'events':[],'tasks':[]})
 c=TestClient(app)
 def login(uid):return {'Authorization':'Bearer '+c.post('/api/auth/login',json={'user_id':uid,'password':'Password12345'}).json()['token']}
 sh,th,oh=login('S'),login('T'),login('OTHER')
 paper=teacher_exam();answers={q['id']:copy.deepcopy(q.get('answer_key','我会根据雾薄和停射，先安排退路并说明原因。')) for q in paper['items']}
 assert len(c.get('/api/exam',headers=sh).json()['items'])==22
 assert c.post('/api/exam/attempts',headers=sh,json={'exam_id':'caocuan-exam-s1.1','answers':answers,'request_id':'old-page'}).status_code==409
 submitted=c.post('/api/exam/attempts',headers=sh,json={'exam_id':paper['id'],'answers':answers,'request_id':'current'});assert submitted.status_code==200,submitted.text
 aid=submitted.json()['id']
 replay=c.post('/api/exam/attempts',headers=sh,json={'exam_id':'caocuan-exam-s1.1','answers':answers,'request_id':'current'})
 assert replay.status_code==200 and replay.json()['id']==aid
 for h in [sh,oh]:
  assert c.post(f'/api/teacher/attempts/{aid}/ai-grade',headers=h,json={'request_id':'denied'}).status_code==403
 assert c.get('/api/teacher/ai/status',headers=sh).status_code==403
 p.ai.provider=DeepSeekProvider()
 pending=c.post(f'/api/teacher/attempts/{aid}/ai-grade',headers=th,json={'request_id':'disabled'})
 assert pending.status_code==200 and pending.json()['status']=='pending_model'
 subjective=[q for q in paper['items'] if q['type'] in {'short','essay','reflection'}]
 body={'scores':{q['id']:q['points'] for q in subjective},'criteria':{q['id']:[r['max_points'] for r in q['rubric_criteria']] for q in subjective},'comment':'合成验收，按各项量规复核。'}
 assert c.put(f'/api/teacher/attempts/{aid}/review',headers=th,json=body).status_code==409
 body['confirm_rule_fallback']=True
 checked=c.put(f'/api/teacher/attempts/{aid}/review',headers=th,json=body)
 assert checked.status_code==200 and checked.json()['total']==100 and checked.json()['ai_grade']['target_id']==aid
 assert c.post(f'/api/teacher/attempts/{aid}/publish',headers=th).status_code==200
 public=c.get('/api/exam/attempts',headers=sh).json()['attempts'][0]
 assert public['total']==100 and 'ai_grade' not in public and 'answers' not in public

def test_valid_analysis_is_bound_to_actual_evidence_and_cached(env):
 p,user=env
 p.s11.student_evidence=lambda sid:{'expressions':[{'id':'original','account_id':'S1','node_id':'K1','goal_id':'G4','text':'请韩伯留下退路。','support_ids':[]}]}
 result={'summary':'本次有一条回应同伴的原话。','goals':[{'goal_id':g,'status':'insufficient','observation':'尚无本人相关作品。','evidence_ids':[],'support_condition':'insufficient','next_step':'补一个具体回应。'} for g in ['G1','G2','G3','G4','G5']]}
 result['goals'][3].update(status='observed',observation='向韩伯提出留下退路的安排。',evidence_ids=['E001'],support_condition='independent')
 p.ai.provider.result=result
 run=p.ai.analyse(user('T1'),'S1',AIRequest(request_id='analysis'))
 assert run['status']=='completed' and run['result']['evidence_map']['E001']['source_id']=='original'
 assert p.ai.analyse(user('T1'),'S1',AIRequest(request_id='analysis-again'))['id']==run['id']
 assert p.ai.provider.calls==1 and run['result']['ability_scores'] is None

def test_expired_worker_reservation_requires_explicit_new_request(env):
 p,user=env
 with p.transaction() as db:
  db.add(AiRun(id='stalled',teacher_id='T1',student_id='S1',target_id='attempt',kind='grade',request_id='stalled',input_hash='old',status='running',mode='test_double',model='deepseek-v4-pro',created_at='2000-01-01T00:00:00+00:00',provider_attempted=True))
 run=p.ai.grade(user('T1'),'attempt',AIRequest(request_id='resume'))
 assert run['status']=='completed' and p.ai.status(user('T1'))['calls_used']==2
 with Session(p.engine) as db:assert db.get(AiRun,'stalled').error_code=='interrupted_or_expired'

@pytest.mark.parametrize('response_kind,code',[
 ('valid',None),('length','incomplete_response'),('badjson','invalid_json'),
 ('auth','provider_http_401'),('redirect','provider_http_302'),('timeout','timeout')])
def test_provider_transport_is_bounded_and_never_follows_redirects(monkeypatch,response_kind,code):
 import httpx,json
 import app.ai_provider as provider_module
 monkeypatch.setenv('CAOCUAN_AI_ENABLED','1')
 monkeypatch.setenv('CAOCUAN_DEEPSEEK_API_KEY','synthetic-key-never-real')
 monkeypatch.setenv('CAOCUAN_AI_MAX_CALLS','2')
 captured=[];RealClient=httpx.Client
 def transport(request):
  captured.append(request);body=json.loads(request.content)
  assert str(request.url)=='https://api.deepseek.com/chat/completions'
  assert body['model']=='deepseek-v4-pro' and body['thinking']=={'type':'disabled'}
  assert body['response_format']=={'type':'json_object'} and body['max_tokens']==7000
  if response_kind=='timeout':raise httpx.ReadTimeout('synthetic',request=request)
  if response_kind=='auth':return httpx.Response(401,json={'error':'secret-provider-content'})
  if response_kind=='redirect':return httpx.Response(302,headers={'location':'https://example.invalid/'})
  return httpx.Response(200,json={'choices':[{'finish_reason':'length' if response_kind=='length' else 'stop','message':{'content':'not JSON' if response_kind=='badjson' else '{"ok":true}'}}],'usage':{'total_tokens':12,'unexpected':999}})
 def client(**kwargs):
  assert kwargs['follow_redirects'] is False and kwargs['trust_env'] is False
  assert kwargs['timeout'].read==45
  return RealClient(transport=httpx.MockTransport(transport),**kwargs)
 monkeypatch.setattr(provider_module.httpx,'Client',client)
 provider=DeepSeekProvider()
 if code:
  with pytest.raises(ProviderError) as exc:provider.complete('JSON only',{'synthetic':True})
  assert exc.value.code==code and 'secret-provider-content' not in str(exc.value)
 else:
  result=provider.complete('JSON only',{'synthetic':True})
  assert result.data=={'ok':True} and result.usage=={'total_tokens':12}
 assert len(captured)==1

def test_oversized_input_rejected_before_transport(monkeypatch):
 monkeypatch.setenv('CAOCUAN_AI_ENABLED','1');monkeypatch.setenv('CAOCUAN_DEEPSEEK_API_KEY','synthetic-key')
 with pytest.raises(ProviderError,match='input_too_large'):DeepSeekProvider().complete('JSON',{'text':'字'*90001})

def test_legacy_criteria_ids_match_teacher_ui_contract():
 assert [c['id'] for c in criteria_for({'type':'short','points':15})]==['c1','c2','c3']

def test_identity_redaction_never_changes_objective_answers(env):
 p,user=env
 p.create_account('B','草束','student','Password12345','A')
 with p.transaction() as db:
  row=db.get(Attempt,'attempt');row.user_id='B'
  row.answers={'a':'B','b':'草束','c':'我叫草束，学号B，先留退路。'}
 p.ai.grade(user('T1'),'attempt',AIRequest(request_id='stable-answers'))
 sent=p.ai.provider.last[1]['untrusted_student_data']['answers']
 assert sent['a']=='B' and sent['b']=='草束'
 assert '我叫草束' not in sent['c'] and '学号B' not in sent['c']

def test_fork_analysis_retains_snapshot_help_not_later_parent_help(tmp_path,monkeypatch):
 from fastapi.testclient import TestClient
 from app.main import create_app
 monkeypatch.setenv('CAOCUAN_AI_ENABLED','0')
 app=create_app(database_url=f'sqlite:///{tmp_path/"story.db"}',platform_database_url=f'sqlite:///{tmp_path/"auth.db"}')
 app.state.platform.create_account('S1','林同学','student','Password12345','A')
 c=TestClient(app);h={'Authorization':'Bearer '+c.post('/api/auth/login',json={'user_id':'S1','password':'Password12345'}).json()['token']}
 start=c.post('/api/s11/sessions',headers=h,json={'role':'Z'}).json();v=start['view'];h['X-Session-Token']=start['token']
 def post(view,kind,**data):
  r=c.post('/api/s11/routes/'+view['route_id']+'/'+kind,headers=h,json={'request_id':kind+str(view['revision']),'expected_revision':view['revision'],'actor_id':view['controller_id'],**data})
  assert r.status_code==200,r.text
  return r.json()
 v=post(v,'help',level='notice');early=v['help']['id']
 v=post(v,'actions',action_id='S0.look',params={});snap=v['snapshots'][-1];parent=v['route_id']
 v=post(v,'help',level='example');late=v['help']['id']
 child=post(v,'forks',snapshot_id=snap['id'],role='Z');child_id=child['route_id']
 child=post(child,'actions',action_id='S1.armor',params={})
 payload={'record_id':'m03','status':'complete','placements':[{'sequence':1,'object_id':'loose_bundle','from':'passage','to':'right_rack','client_at':'one'}],'blocked_after':False,'walked':True}
 child=post(child,'tasks',task_id='M03_PASSAGE',payload=payload)
 for action in ['S2.both','S4.go','S8.route','S9.far','S10.drum']:
  child=post(child,'actions',action_id=action,params={})
 side_attempt={'sequence':1,'side':'left','feedback_before':[],'support_ids':[],'client_at':'one'}
 child=post(child,'tasks',task_id='M07_SIDE',payload={'record_id':'m07','status':'complete','attempts':[side_attempt],'first_attempt':side_attempt,'feedback':[],'selected_side':'left'})
 child=post(child,'actions',action_id='A0.turn',params={})
 assert child['node_id']=='S15'
 listen={'record_id':'m09','status':'complete','heard':[{'sequence':1,'clip_id':'arrow_change','mode':'local_web_audio','client_at':'one'},{'sequence':2,'clip_id':'shore_report','mode':'text_equivalent','client_at':'two'}],'replays':{'arrow_change':1,'shore_report':1},'response':'停射了，我先请韩伯留下退路。','sound_source':'local_web_audio'}
 child=post(child,'tasks',task_id='M09_LISTEN',payload=listen)
 source=app.state.s11.student_evidence('S1')
 inherited=next(s for s in source['supports'] if s.get('inherited'))
 assert inherited['route_id']==parent and inherited['evidence_route_id']==child_id
 sent,mapping=build_analysis_payload(source,'S1',['S1','林同学'])
 child_records=[(e,mapping[e['id']]) for e in sent['evidence'] if mapping[e['id']]['route_id']==child_id and e['kind'] in {'action','task'}]
 assert child_records and {'M03_PASSAGE','M07_SIDE','M09_LISTEN'}<={e.get('task_id') for e,_ in child_records}
 for record,local in child_records:
  assert early in local['support_ids'] and late not in local['support_ids'] and record['support_ids']

