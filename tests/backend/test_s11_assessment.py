"""S1.1 assessment privacy, deterministic marking and attributed observations."""
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.main import create_app
from app.exam_legacy_s11 import public_exam, validate_and_score


def answers():
    return {'q1':'B','q2':'A','q3':'B','q4':'C','q5':['A','B'],'q6':['A','B'],
            'q7':['promise','prepare','approach','turn','return'],
            'q8':{'zhou':'deadline','lu':'retreat','zhuge':'mislead','han':'side','cao':'identify'},
            'q9':{'spent':'0','remaining':'44000','turn':'B','report':'A'},
            'q10':'先收鼓。请韩伯留好退路，若哨艇继续靠近，就退回。',
            'q11':'鲁肃把箭簿放在案上：“只带回五万二千。”孔明拱手：“雾散了，为保人船提前收船。”周瑜接过箭簿：“把经过说清楚。”'}


@pytest.fixture
def env(tmp_path,monkeypatch):
    # Deliberate historical paper fixture, not production shape inference.
    import app.platform as platform_module
    from app import exam_legacy_s11 as legacy
    for name in ['EXAM_ID','public_exam','teacher_exam','validate_and_score']:
        monkeypatch.setattr(platform_module,name,getattr(legacy,name))
    app=create_app(database_url=f'sqlite:///{tmp_path / "course.db"}',platform_database_url=f'sqlite:///{tmp_path / "platform.db"}')
    p=app.state.platform
    for sid,cls in [('S1','A'),('S2','A'),('S3','B')]: p.create_account(sid,sid,'student','Password12345',cls)
    p.create_account('T1','教师','teacher','Password12345',class_ids=['A'])
    c=TestClient(app)
    def login(uid): return {'Authorization':'Bearer '+c.post('/api/auth/login',json={'user_id':uid,'password':'Password12345'}).json()['token']}
    route={'id':'s11-route','session_id':'s11-session','role':'R_LUSU','status':'ended','created_at':'2026-10-27T00:00:00Z'}
    evidence={'routes':[route],'expressions':[], 'supports':[], 'events':[]}
    p.s11=SimpleNamespace(student_routes=lambda sid: ([route],{}) if sid=='S1' else ([],{}),student_evidence=lambda sid:evidence if sid=='S1' else {'routes':[],'expressions':[],'supports':[],'events':[]})
    return c,p,login,evidence


def test_s11_paper_is_eleven_items_with_private_rubrics_and_common_case():
    paper=public_exam()
    assert paper['id']=='caocuan-exam-s1.1'
    assert len(paper['items'])==11 and sum(q['points'] for q in paper['items'])==100
    assert '三日' in paper['items'][0]['options'][1]['text']
    assert len(paper['items'][6]['options'])==5
    assert len(paper['items'][7]['left'])==5
    assert len(paper['items'][8]['parts'])==4
    assert '52,000' in paper['items'][8]['prompt']
    assert all('rubric' not in q and 'answer_key' not in q and 'correct' not in q for q in paper['items'])


def test_partial_marks_and_four_case_parts_are_deterministic():
    assert sum(v for v in validate_and_score(answers()).values() if v is not None)==70
    partial=answers(); partial['q5']=['A']; partial['q6']=['B']; partial['q9']['remaining']='52000'
    scores=validate_and_score(partial)
    assert scores['q5']==2 and scores['q6']==2 and scores['q9']==15
    partial['q5']=['A','C']; assert validate_and_score(partial)['q5']==0
    partial['q9']['spent']=False
    with pytest.raises(ValueError): validate_and_score(partial)


def test_only_teacher_paper_includes_keys_and_rubrics(env):
    c,p,login,_=env
    assert c.get('/api/teacher/exam',headers=login('S1')).status_code==403
    paper=c.get('/api/teacher/exam',headers=login('T1'))
    assert paper.status_code==200,paper.text
    assert paper.json()['items'][0]['answer_key']=='B'
    assert 'rubric' in paper.json()['items'][-1]
    public=c.get('/api/exam',headers=login('S1')).json()
    assert 'answer_key' not in str(public) and 'rubric' not in str(public)


def test_s11_completion_allows_individual_exam_and_only_published_total(env):
    c,p,login,_=env; sh=login('S1'); th=login('T1')
    posted=c.post('/api/exam/attempts',headers=sh,json={'answers':answers(),'request_id':'s11'})
    assert posted.status_code==200,posted.text
    attempt=posted.json(); aid=attempt['id']
    assert attempt['total'] is None and 'answers' not in attempt and 'item_scores' not in attempt
    assert c.post(f'/api/teacher/attempts/{aid}/publish',headers=th).status_code==409
    for marks in ({'q10':12,'q11':13},{'q10':13,'q11':13}):
        assert c.put(f'/api/teacher/attempts/{aid}/review',headers=th,json={'scores':marks,'comment':'指出了停射与退路。'}).status_code==200
    detail=c.get('/api/teacher/students/S1',headers=th).json()
    assert len(detail['attempts'][0]['review_history'])==2
    assert 'rubric' in detail['attempts'][0]['items'][-1]
    before=c.get('/api/exam/attempts',headers=sh).json()['attempts'][0]
    assert before['total'] is None and 'review_history' not in before
    assert c.post(f'/api/teacher/attempts/{aid}/publish',headers=th).status_code==200
    student=c.get('/api/exam/attempts',headers=sh).json()['attempts'][0]
    assert student['total']==96 and not {'answers','items','item_scores','review_comment'} & student.keys()
    assert c.get('/api/teacher/students/S3',headers=th).status_code==403
    assert c.get('/api/teacher/students/S1',headers=sh).status_code==403
    assert c.post('/api/exam/attempts',headers=login('S2'),json={'answers':answers(),'request_id':'not-owner'}).status_code==409


def test_teacher_observation_keeps_actual_author_help_and_retry_separate(env):
    c,p,login,evidence=env
    evidence['expressions']=[
        {'id':'mine','route_id':'s11-route','node_id':'K1','actor_id':'owner','author_name':'S1','account_id':'S1','activity_mode':'group','text':'请韩伯留好退路。','kind':'retry','goal_id':'G5','created_at':'2026-10-27T01:00:00Z','support_ids':['help']},
        {'id':'peer','route_id':'s11-route','node_id':'M05','actor_id':'peer','author_name':'同伴','account_id':None,'activity_mode':'group','text':'同伴的原话','kind':'expression','goal_id':'G4','created_at':'2026-10-27T00:00:00Z','support_ids':[]}]
    evidence['supports']=[{'id':'help','route_id':'s11-route','node_id':'K1','actor_id':'owner','account_id':'S1','activity_mode':'group','text':'先告诉他退路。','level':'hint','source':'prewritten','created_at':'2026-10-27T00:30:00Z'}]
    evidence['events']=[{'route_id':'s11-route','node_id':'M07','actor_id':'peer','account_id':None,'action':'turn','reaction':'已转向'}]
    d=c.get('/api/teacher/students/S1',headers=login('T1')).json()
    assert len(d['matrix'])==5
    g5=next(r for r in d['matrix'] if r['goal_id']=='G5')
    assert g5['status']=='observed' and g5['evidence'][0]['text']=='请韩伯留好退路。'
    assert g5['evidence'][0]['support_count']==1 and g5['evidence'][0]['kind']=='individual_in_group'
    assert next(r for r in d['matrix'] if r['goal_id']=='G4')['status']=='unobserved'
    assert d['s11']['expressions'][1]['text']=='同伴的原话'
    assert not any('score' in r for r in d['matrix'])


def test_comment_draft_release_preserves_published_version_and_class_guard(env):
    c,p,login,_=env; th=login('T1')
    assert c.put('/api/teacher/students/S1/comment',headers=th,json={'text':'先说明退路，再安排谁传令。'}).status_code==200
    released=c.post('/api/teacher/students/S1/comment/publish',headers=th)
    assert released.status_code==200,released.text
    assert released.json()['version']==1
    c.put('/api/teacher/students/S1/comment',headers=th,json={'text':'第二次已说清传令对象。'})
    detail=c.get('/api/teacher/students/S1',headers=th).json()
    assert detail['comment']['status']=='draft' and detail['comment']['version']==2
    assert detail['published_comment']['version']==1 and detail['published_comment']['text']=='先说明退路，再安排谁传令。'
    assert c.post('/api/teacher/students/S3/comment/publish',headers=th).status_code==403
    assert c.post('/api/teacher/students/S1/comment/publish',headers=login('S1')).status_code==403


def test_real_s11_route_can_submit_without_creating_legacy_route(env):
    c,p,login,_=env
    p.s11=c.app.state.s11
    sh=login('S1')
    start=c.post('/api/s11/sessions',headers=sh,json={'role':'Z','activity_mode':'group','members':['同伴']})
    assert start.status_code==200,start.text
    data=start.json(); v=data['view']; headers={**sh,'X-Session-Token':data['token']}
    # Common-terminal signatures are retained; a peer's statement is not the
    # owner's individual evidence and does not qualify another account to test.
    response=c.post(f'/api/s11/routes/{v["route_id"]}/expressions',headers=headers,json={'request_id':'peer-line','expected_revision':v['revision'],'actor_id':v['members'][1]['id'],'text':'同伴说，先留好通道。'})
    assert response.status_code==200,response.text
    v=response.json()
    for index,action in enumerate(['S0.look','S1.straw','S2.both','S4.go','S8.route','S9.far','S10.drum','A0.turn','A4.go','R0.return','COUNT1.done']):
        result=c.post(f'/api/s11/routes/{v["route_id"]}/actions',headers=headers,json={'request_id':str(index),'expected_revision':v['revision'],'actor_id':v['controller_id'],'action_id':action,'params':{}})
        assert result.status_code==200,result.text
        v=result.json()
    assert p.legacy_student_routes('S1')[0]==[]
    assert c.post('/api/exam/attempts',headers=sh,json={'answers':answers(),'request_id':'real-s11'}).status_code==200
    d=c.get('/api/teacher/students/S1',headers=login('T1')).json()
    assert all(row['status']=='unobserved' for row in d['matrix'])
    assert d['s11']['expressions'][0]['account_id'] is None
    assert c.post('/api/exam/attempts',headers=login('S2'),json={'answers':answers(),'request_id':'group-copy'}).status_code==409


def test_three_rubric_marks_are_saved_and_must_agree_with_totals(env):
    c,p,login,_=env; th=login('T1')
    aid=c.post('/api/exam/attempts',headers=login('S1'),json={'answers':answers(),'request_id':'rubric'}).json()['id']
    body={'scores':{'q10':12,'q11':13},'criteria':{'q10':[4,3,5],'q11':[4,4,5]},'comment':'已逐项核对实际变化、执行安排、人物关系和收束。'}
    saved=c.put(f'/api/teacher/attempts/{aid}/review',headers=th,json=body)
    assert saved.status_code==200,saved.text
    d=c.get('/api/teacher/students/S1',headers=th).json()
    assert d['attempts'][0]['review_history'][0]['criteria']==body['criteria']
    body['criteria']['q10']=[4,4,5]
    assert c.put(f'/api/teacher/attempts/{aid}/review',headers=th,json=body).status_code==422
