import sys,json,uuid,copy
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'public'))
from engine.browser_api import handle
from engine.exam import KEYS,CRITERIA
class Client:
 def __init__(self):self.store=None;self.token=None
 def call(self,path,method='GET',body=None,status=200):
  r=json.loads(handle(json.dumps(dict(store=self.store,path=path,method=method,body=body,token=self.token),ensure_ascii=False)))
  assert r['status']==status,r
  if status==200:self.store=r['store']
  return r['data']
 def login(self,id='S001'):self.token=self.call('/auth/login','POST',dict(user_id=id))['token']
 def start(self,role='L',scenario='mist'):return self.call('/v1/runs','POST',dict(role=role,scenario=scenario,design_version='V1.6'))
 def move(self,r,action,payload=None,**kw):return self.call('/v1/runs/'+r['id']+'/actions','POST',dict(request_id=str(uuid.uuid4()),revision=r['revision'],action=action,actor=0,payload=payload or {},**kw))
WITNESSES=json.loads((ROOT/'docs/witnesses.json').read_text(encoding='utf-8'))['witnesses']
@pytest.mark.parametrize('w',WITNESSES,ids=lambda w:w['role']+'-'+w['scenario']+'-'+str(w.get('target','route')))
def test_saved_witnesses_match_engine(w):
 c=Client();c.login();r=c.start(w['role'],w['scenario'])
 for x in w['steps']:
  assert r['scene']['node']==x['node']
  r=c.move(r,x['action'],x['payload']);assert not r.get('feedback'),r.get('feedback')
 assert r['status']=='ended'
 assert c.call('/v1/runs/'+r['id'])==r
def test_revision_idempotency_and_identity():
 c=Client();c.login();r=c.start();b=dict(request_id='one',revision=0,actor=0,action='explain',payload={})
 path='/v1/runs/'+r['id']+'/actions';a=c.call(path,'POST',b)
 assert c.call(path,'POST',b)==a
 c.call(path,'POST',dict(b,request_id='new'),409)
 c.call(path,'POST',dict(b,action='help'),409)
 c.login('S002');c.call('/v1/runs/'+r['id'],status=403)
 c.login('T001');c.call('/v1/runs','POST',{},403)
def test_preview_fork_help_and_isolation():
 c=Client();c.login();r=c.start();r=c.move(r,'help');assert len(r['supports'])==1
 r=c.move(r,'explain');p=c.call('/v1/runs/'+r['id']+'/snapshots/0');assert p['preview'] and not p['scene']['actions'];assert not p['supports']
 f=c.call('/v1/runs/'+r['id']+'/fork','POST',dict(snapshot=0));assert f['id']!=r['id'] and f['history']==[] and f['supports']==[]
 assert c.call('/v1/runs/'+r['id'])==r
def test_assessment_review_publish_and_comment():
 c=Client();c.login();w=WITNESSES[0];r=c.start(w['role'],w['scenario'])
 for x in w['steps']:r=c.move(r,x['action'],x['payload'])
 paper=c.call('/exam');assert len(paper['items'])==22 and sum(q['points'] for q in paper['items'])==100
 answers={**copy.deepcopy(KEYS),**{qid:'模拟：我选择撤离，因为雾渐散且哨艇靠近。先接应末船，再回营如实报告。' for qid in CRITERIA}}
 b=dict(exam_id=paper['id'],request_id='exam-1',answers=answers);a=c.call('/exam/attempts','POST',b);assert a['total'] is None
 assert c.call('/exam/attempts','POST',b)==a
 c.call('/teacher/students',status=403);c.login('T001')
 d=c.call('/teacher/students/S001');assert d['attempts'][0]['total'] is None;assert d['ai_mode']=='disabled'
 c.call('/teacher/attempts/'+a['id']+'/publish','POST',{},409)
 criteria={qid:[x['max_points'] for x in cs] for qid,cs in CRITERIA.items()}
 review=dict(criteria=criteria,scores={q:sum(v) for q,v in criteria.items()},comment='按逐项量规核读，示例分数用于软件验证。',confirm_rule_fallback=True)
 reviewed=c.call('/teacher/attempts/'+a['id']+'/review','PUT',review);assert reviewed['total']==100
 c.call('/teacher/attempts/'+a['id']+'/publish','POST',{});c.call('/teacher/attempts/'+a['id']+'/review','PUT',review,409)
 c.call('/teacher/students/S001/comment','PUT',dict(text='仅软件测试的演示评语'));c.call('/teacher/students/S001/comment/publish','POST',{})
 c.login();assert c.call('/exam/attempts')['attempts'][0]['total']==100
 assert 'answers' not in c.call('/exam/attempts')['attempts'][0]
def test_invalid_operation_preserves_scene():
 c=Client();c.login();r=c.start();before=r['scene']['node'];r=c.move(r,'assemble',{}) if before=='assembly' else c.move(r,'explain');
 # Malformed/unknown actions never mutate the store.
 saved=copy.deepcopy(c.store);c.call('/v1/runs/'+r['id']+'/actions','POST',dict(request_id='bad',revision=r['revision'],actor=0,action='does-not-exist',payload={}),422);assert c.store==saved
