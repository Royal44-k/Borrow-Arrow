import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from app.main import create_app


@pytest.fixture
def env(tmp_path,monkeypatch):
    # Retain the original S1.1 platform regression suite against its explicit
    # legacy contract; current S1.2 API behaviour is tested separately.
    import app.platform as platform_module
    from app import exam_legacy_s11 as legacy
    for name in ['EXAM_ID','public_exam','teacher_exam','validate_and_score']:
        monkeypatch.setattr(platform_module,name,getattr(legacy,name))
    app = create_app(database_url=f'sqlite:///{tmp_path / "course.sqlite"}', platform_database_url=f'sqlite:///{tmp_path / "platform.sqlite"}')
    p = app.state.platform
    p.create_account('S001', '小林', 'student', 'StudentPassword123!', 'DEMO7', [], True)
    p.create_account('S002', '小禾', 'student', 'StudentPassword123!', 'DEMO7', [], True)
    p.create_account('S003', '小云', 'student', 'StudentPassword123!', 'OTHER', [], True)
    p.create_account('T001', '示例教师', 'teacher', 'TeacherPassword123!', '', ['DEMO7'], True)
    c = TestClient(app)
    def login(uid):
        password = 'TeacherPassword123!' if uid.startswith('T') else 'StudentPassword123!'
        result = c.post('/api/auth/login', json={'user_id': uid, 'password': password})
        assert result.status_code == 200
        return {'Authorization': 'Bearer ' + result.json()['token']}
    return c, p, login


def finish(c, h):
    result = c.post('/api/sessions', headers=h, json={'role':'R_ZHUGE','scenario':'responsive_dense','activity_mode':'individual','members':['假名']})
    assert result.status_code == 200, result.text
    data = result.json(); v = data['view']; h = {**h, 'X-Session-Token': data['token']}
    for action in ['A_PREP_STRAW', 'A_CANCEL', 'A_REPORT']:
        response = c.post(f'/api/routes/{v["route_id"]}/actions', headers=h, json={'request_id':action,'expected_revision':v['revision'],'actor_id':v['controller_id'],'action_id':action,'params':{}})
        assert response.status_code == 200, response.text
        v = response.json()
    return data, v, h


def answers():
    return {'q1':'B','q2':'A','q3':'B','q4':'C','q5':['A','B'],'q6':['A','B'],'q7':['promise','prepare','approach','turn','return'],'q8':{'zhou':'deadline','lu':'retreat','zhuge':'mislead','han':'side','cao':'identify'},'q9':{'spent':'0','remaining':'44000','turn':'B','report':'A'},'q10':'先收鼓。请韩伯留好退路，若哨艇继续靠近，就退回。','q11':'鲁肃把箭簿放在案上：“只带回五万二千。”孔明拱手：“为保人船提前收船。”周瑜接过箭簿。'}



def test_auth_no_registration_and_password_not_returned(env):
    c, p, login = env
    assert c.post('/api/auth/register', json={'role':'teacher'}).status_code in (404,405)
    assert c.post('/api/auth/login', json={'user_id':'S001','password':'bad'}).status_code == 401
    h = login('S001')
    me = c.get('/api/auth/me', headers=h).json()
    assert me['user']['name'] == '小林'
    assert 'password' not in str(me)
    c.post('/api/auth/logout', headers=h)
    assert c.get('/api/auth/me', headers=h).status_code == 401


def test_course_owner_and_teacher_routes_guarded(env):
    c, p, login = env
    h = login('S001'); data, v, h = finish(c,h)
    other = {**login('S002'),'X-Session-Token':data['token']}
    assert c.get(f'/api/routes/{v["route_id"]}/view', headers=other).status_code == 403
    assert c.get(f'/api/routes/{v["route_id"]}/feedback', headers=h).status_code == 403
    assert c.get(f'/api/routes/{v["route_id"]}/feedback', headers={'X-Session-Token':data['token']}).status_code == 401
    assert c.get('/api/teacher/students', headers=h).status_code == 403
    assert c.get('/api/teacher/students/S003', headers=login('T001')).status_code == 403
    assert v['members'][0]['name'] == '小林'


def test_exam_no_answer_leaks_and_course_required(env):
    c, p, login = env; h=login('S001')
    exam=c.get('/api/exam',headers=h).json()
    assert sum(i['points'] for i in exam['items']) == 100
    assert {'single','multi','order','match','short'} <= {i['type'] for i in exam['items']}
    assert not any('correct' in i or 'answer' in i or 'answer_key' in i for i in exam['items'])
    assert c.post('/api/exam/attempts',headers=h,json={'answers':answers(),'request_id':'a'}).status_code == 409


def test_scores_review_publish_and_private_results(env):
    c,p,login=env; sh=login('S001'); finish(c,sh)
    posted=c.post('/api/exam/attempts',headers=sh,json={'answers':answers(),'request_id':'one'})
    assert posted.status_code == 200, posted.text
    attempt=posted.json(); aid=attempt['id']; assert attempt['total'] is None
    assert 'item_scores' not in attempt and 'answers' not in attempt
    same=c.post('/api/exam/attempts',headers=sh,json={'answers':answers(),'request_id':'one'})
    assert same.json()['id'] == aid
    th=login('T001')
    assert c.post(f'/api/teacher/attempts/{aid}/publish',headers=th).status_code == 409
    assert c.put(f'/api/teacher/attempts/{aid}/review',headers=sh,json={'scores':{'q10':15,'q11':15},'comment':'好'}).status_code == 403
    reviewed=c.put(f'/api/teacher/attempts/{aid}/review',headers=th,json={'scores':{'q10':12,'q11':13},'comment':'两处回应已经连贯，继续补清新情况。'})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()['total'] == 95
    assert c.get('/api/exam/attempts',headers=sh).json()['attempts'][0]['total'] is None
    published=c.post(f'/api/teacher/attempts/{aid}/publish',headers=th)
    assert published.status_code == 200
    assert c.get('/api/exam/attempts',headers=sh).json()['attempts'][0]['total'] == 95
    assert c.get('/api/exam/attempts',headers=login('S002')).json()['attempts'] == []
    assert c.put(f'/api/teacher/attempts/{aid}/review',headers=th,json={'scores':{'q10':15,'q11':15},'comment':'change'}).status_code == 409


def test_score_validation_comment_and_matrix_no_fabrication(env):
    c,p,login=env; sh=login('S001'); finish(c,sh); th=login('T001')
    aid=c.post('/api/exam/attempts',headers=sh,json={'answers':answers(),'request_id':'two'}).json()['id']
    assert c.put(f'/api/teacher/attempts/{aid}/review',headers=th,json={'scores':{'q10':16,'q11':15},'comment':'x'}).status_code == 422
    result=c.put('/api/teacher/students/S001/comment',headers=th,json={'text':'请在下一次归营报告中交代你改变安排的原因。'})
    assert result.status_code == 200
    detail=c.get('/api/teacher/students/S001',headers=th).json()
    assert all(row['status']=='unobserved' for row in detail['matrix'])
    assert detail['comment']['teacher_id'] == 'T001'
    assert detail['ai_mode'] == 'disabled'
    assert c.get('/api/teacher/students/S001',headers=sh).status_code == 403


def test_invalid_answers_and_idempotency_conflict(env):
    c,p,login=env; sh=login('S001'); finish(c,sh)
    bad=answers(); bad['q8']={'rusu':'defend'}
    assert c.post('/api/exam/attempts',headers=sh,json={'answers':bad,'request_id':'x'}).status_code == 422
    c.post('/api/exam/attempts',headers=sh,json={'answers':answers(),'request_id':'y'})
    changed=answers(); changed['q1']='A'
    assert c.post('/api/exam/attempts',headers=sh,json={'answers':changed,'request_id':'y'}).status_code == 409


def test_story_expression_is_in_world_and_attributed(env):
    c,p,login=env; h=login('S001')
    start=c.post('/api/sessions',headers=h,json={'role':'R_LUSU','scenario':'responsive_dense','activity_mode':'individual','members':['假名']}).json()
    v=start['view']; h={**h,'X-Session-Token':start['token']}
    result=c.post(f'/api/routes/{v["route_id"]}/expressions',headers=h,json={'actor_id':v['controller_id'],'text':'若岸上停射，我们是否先把现有的带回？','kind':'expression','goal_id':'G_ADAPT_EXPRESSION'})
    assert result.status_code == 200
    assert result.json()['latest_response']['text']=='这番话我记下了。接下来，你打算如何安排？'
    assert result.json()['latest_response']['source']=='prewritten'
    detail=c.get('/api/teacher/students/S001',headers=login('T001')).json()
    row=next(r for r in detail['matrix'] if r['goal_id']=='G4')
    assert row['status']=='observed'
    assert row['evidence'][0]['text']=='若岸上停射，我们是否先把现有的带回？'
    assert 'score' not in row


def test_model_stays_disabled_even_with_inherited_settings(tmp_path,monkeypatch):
    monkeypatch.setenv('COURSEWARE_AI_ENABLED','1')
    monkeypatch.setenv('COURSEWARE_AI_API_KEY','synthetic-never-used')
    app=create_app(database_url=f'sqlite:///{tmp_path / "course.sqlite"}',platform_database_url=f'sqlite:///{tmp_path / "platform.sqlite"}')
    assert app.state.service.language.mode=='disabled'
    assert not hasattr(app.state.service.language,'api_key')
    assert app.state.service.language.render({},'剧本回应','peer')==('剧本回应','prewritten','disabled')


def test_account_hash_and_login_survive_reopen(env):
    c,p,login=env
    from app.platform import Platform, Account
    from sqlalchemy.orm import Session
    with Session(p.engine) as db:
        row=db.get(Account,'S001')
        assert row.password_hash.startswith('pbkdf2_sha256$310000$')
        assert 'StudentPassword123!' not in row.password_hash
    header=login('S001')['Authorization']
    reopened=Platform(str(p.engine.url),p.course)
    assert reopened.authenticate(header)['user_id']=='S001'


def test_cross_class_review_and_unknown_routes_are_rejected(env):
    c,p,login=env; sh=login('S003'); finish(c,sh)
    aid=c.post('/api/exam/attempts',headers=sh,json={'answers':answers(),'request_id':'private'}).json()['id']
    th=login('T001')
    assert c.put(f'/api/teacher/attempts/{aid}/review',headers=th,json={'scores':{'q10':15,'q11':15},'comment':'越界'}).status_code==403
    assert c.post(f'/api/teacher/attempts/{aid}/publish',headers=th).status_code==403
    assert c.get('/api/routes/not-a-route/view',headers=sh).status_code==404


def test_authenticated_three_roles_eight_endings_keep_world_contract(env):
    import json
    c,p,login=env; auth=login('S001')
    witnesses=json.loads((Path(__file__).parent/'fixtures'/'legacy-route-witnesses.json').read_text(encoding='utf-8'))
    presentation=json.loads((ROOT/'content'/'caocuan'/'v3'/'presentation.json').read_text(encoding='utf-8'))
    assert len(witnesses)==24
    for row in witnesses:
        response=c.post('/api/sessions',headers=auth,json={'role':row['entry'],'scenario':row['scenario'],'activity_mode':'individual','members':['小林']})
        assert response.status_code==200
        data=response.json(); v=data['view']; headers={**auth,'X-Session-Token':data['token']}
        for index,step in enumerate(row['trace']):
            if step['action']=='A_RESOLVE_FIRE':
                assert step['action'] not in {a['id'] for a in v['actions']}
                continue
            response=c.post(f'/api/routes/{v["route_id"]}/actions',headers=headers,json={'request_id':f'action-{index}','expected_revision':v['revision'],'actor_id':v['controller_id'],'action_id':step['action'],'params':{}})
            assert response.status_code==200,(row['entry'],row['expected'],step,response.text)
            v=response.json()
            if row['entry']=='R_CAO': assert v['inventory'] is None and 'endpoint' not in v
        assert v['status']=='completed'
        assert v['ending']['title']==presentation['endings'][row['expected']][row['entry']]['title']


def new_route(c,auth,role='R_LUSU',scenario='responsive_dense'):
    response=c.post('/api/sessions',headers=auth,json={'role':role,'scenario':scenario,'activity_mode':'individual','members':['小林']})
    assert response.status_code==200
    data=response.json()
    return data['view'],{**auth,'X-Session-Token':data['token']}


def act(c,h,v,action,params=None,key=None):
    return c.post(f'/api/routes/{v["route_id"]}/actions',headers=h,json={'request_id':key or f'{action}-{v["revision"]}','expected_revision':v['revision'],'actor_id':v['controller_id'],'action_id':action,'params':params or {}})


def test_say_optional_goal_one_artifact_idempotent_and_validated(env):
    c,p,login=env; auth=login('S001'); v,h=new_route(c,auth)
    for aid in ['A_PREP_STRAW','A_LAUNCH']: v=act(c,h,v,aid).json()
    before=v
    params={'text':'倘若曹军追来，我们怎样退出江面？','goal_id':'G_PERSPECTIVE'}
    response=act(c,h,before,'A_SAY',params,'my-line')
    assert response.status_code==200,response.text
    v=response.json()
    assert len(v['artifacts'])==1
    assert v['artifacts'][0]['goal_id']=='G_PERSPECTIVE'
    assert act(c,h,before,'A_SAY',params,'my-line').json()['artifacts']==v['artifacts']
    review=c.get(f'/api/routes/{v["route_id"]}/review',headers=h).json()
    last=[s for s in review['snapshots'] if s['can_fork']][-1]
    replay=c.post(f'/api/routes/{v["route_id"]}/forks',headers=h,json={'snapshot_id':last['id'],'new_role':'R_ZHUGE','mode':'clip','actor_id':v['controller_id']})
    assert replay.status_code==200
    assert replay.json()['replay_context']['text']==params['text']
    assert replay.json()['replay_context']['is_new_evidence'] is False
    assert replay.json()['artifacts']==[]
    for bad in ['UNKNOWN',{},True]:
        rejected=act(c,h,v,'A_SAY',{'text':'这一句不应保存。','goal_id':bad},'bad-'+str(bad))
        assert rejected.status_code==422
    assert act(c,h,v,'A_SIGNAL',{'variant':'drum','goal_id':'G_PERSPECTIVE'}).status_code==422
    plain=act(c,h,v,'A_SAY',{'text':'此处且听一听。'}).json()
    assert plain['artifacts'][-1]['goal_id'] is None


def test_presentation_state_survives_refresh_and_cao_sees_no_hidden_preparation(env):
    c,p,login=env; auth=login('S001'); v,h=new_route(c,auth,'R_ZHUGE')
    assert v['presentation_state']=={'decoy':None,'side':'first','fire':'none','launched':False}
    v=act(c,h,v,'A_PREP_ARMOR').json()
    for aid in ['A_LAUNCH','A_SIGNAL','A_TURN']: v=act(c,h,v,aid).json()
    refreshed=c.get(f'/api/routes/{v["route_id"]}/view',headers=h).json()
    assert refreshed['presentation_state']=={'decoy':'armor','side':'second','fire':'none','launched':True}
    assert refreshed['inventory']['acquired']>0
    cao,ch=new_route(c,auth,'R_CAO')
    assert cao['presentation_state']=={'decoy':None,'side':None,'fire':None,'launched':None}
    cao=act(c,ch,cao,'A_NEAR').json()
    assert cao['presentation_state']['decoy'] is None


def test_terminal_presentation_does_not_invent_launch_or_leak_enemy_ending(env):
    c,p,login=env; auth=login('S001')
    _,unlaunched,_=finish(c,auth)
    assert unlaunched['presentation_state']['launched'] is False
    assert unlaunched['ending_code']=='T7'
    v,h=new_route(c,auth,'R_LUSU')
    for aid in ['A_PREP_STRAW','A_LAUNCH','A_SIGNAL','A_WITHDRAW','A_REPORT']:
        v=act(c,h,v,aid).json()
    assert v['presentation_state']['launched'] is True
    assert v['ending_code']=='T2'
    cao,ch=new_route(c,auth,'R_CAO','no_contact_patrol')
    for aid in ['A_PATROL_CLOSE','A_REPORT']: cao=act(c,ch,cao,aid).json()
    assert cao['status']=='completed'
    assert cao['presentation_state']['launched'] is None
    assert cao['ending_code'] is None


def test_cao_reveals_only_observed_outline_and_not_hidden_fire_contact(env):
    c,p,login=env; auth=login('S001')
    cao,h=new_route(c,auth,'R_CAO','skeptic_clear')
    cao=act(c,h,cao,'A_NEAR').json()
    assert cao['presentation_state']['decoy']=='straw'
    assert cao['presentation_state']['side'] is None
    fire,fh=new_route(c,auth,'R_CAO','fire_contact')
    fire=act(c,fh,fire,'A_FIRE').json()
    assert fire['presentation_state']['fire']=='light'
    assert fire['presentation_state']['decoy'] is None


def test_teacher_support_evidence_does_not_flow_backwards_in_time(env):
    c,p,login=env; auth=login('S001'); v,h=new_route(c,auth)
    endpoint=f'/api/routes/{v["route_id"]}'
    def say(text):
        result=c.post(endpoint+'/expressions',headers=h,json={'actor_id':v['controller_id'],'text':text,'kind':'expression','goal_id':'G_PERSPECTIVE'})
        assert result.status_code==200
        return result.json()
    before=say('先前的一句还没有求助。')['artifacts'][-1]
    help_result=c.post(endpoint+'/help',headers=h,json={'actor_id':v['controller_id'],'level':'H1'})
    assert help_result.status_code==200
    after=say('听过提示后，我想换一种说法。')['artifacts'][-1]
    detail=c.get('/api/teacher/students/S001',headers=login('T001')).json()
    evidence=next(row for row in detail['matrix'] if row['goal_id']=='G2')['evidence']
    indexed={e['artifact_id']:e for e in evidence}
    assert indexed[before['id']]['support_count']==0
    assert indexed[before['id']]['support_ids']==[]
    assert indexed[after['id']]['support_count']==1
    assert len(indexed[after['id']]['support_ids'])==1
