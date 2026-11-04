"""S1.1 script behavior, persistence, ownership and information boundaries."""
import importlib
import json
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
SPEC = ROOT / 'content/caocuan/s11'
WITNESSES = json.loads((SPEC/'route-witnesses.json').read_text(encoding='utf-8'))

def runtime():
    try: return importlib.import_module('app.s11_runtime')
    except ModuleNotFoundError: pytest.fail('S1.1 runtime must exist and execute the approved network')

@pytest.mark.parametrize('w', WITNESSES, ids=lambda w:w['id'])
def test_approved_route(w):
    r=runtime(); state=r.initial(w['role'],w['preset']); node='C0' if w['role']=='C' else 'S0'
    for eid in w['path']:
        edge=next(e for e in r.NODES[node]['edges'] if e['id']==eid)
        assert r.legal(edge,state)
        state=r.advance(edge,state);node=edge['to']
    assert node==w['ending']
    assert state==w['state']
    assert r.ending(state)==w['ending_scene']

@pytest.fixture
def env(tmp_path):
    from app.main import create_app
    app=create_app(f'sqlite:///{tmp_path}/course.sqlite',platform_database_url=f'sqlite:///{tmp_path}/platform.sqlite')
    p=app.state.platform
    for uid in ['S1','S2']:
        p.create_account(uid,uid,'student','Password123!','C',[],True)
    p.create_account('T1','Teacher','teacher','Password123!','',['C'],True)
    c=TestClient(app)
    def auth(uid):return {'Authorization':'Bearer '+c.post('/api/auth/login',json={'user_id':uid,'password':'Password123!'}).json()['token']}
    return c,auth,app

def start(env,role='L',**extra):
    c,auth,_=env;h=auth('S1');r=c.post('/api/s11/sessions',headers=h,json={'role':role,**extra});assert r.status_code==200,r.text
    d=r.json();return c,{**h,'X-Session-Token':d['token']},d['view'],d

def act(c,h,v,aid,**extra):
    body={'request_id':str(v['revision'])+aid,'expected_revision':v['revision'],'actor_id':v['controller_id'],'action_id':aid,'params':{},**extra}
    return c.post('/api/s11/routes/'+v['route_id']+'/actions',headers=h,json=body)

def path(c,h,v,ids):
    for aid in ids:
        r=act(c,h,v,aid);assert r.status_code==200,r.text;v=r.json()
    return v

def test_catalog_and_first_session_hide_debug(env):
    c,h,v,d=start(env)
    cat=c.get('/api/s11/catalog',headers=h).json()
    assert [s['id'] for s in cat['scenarios']]==['standard']
    assert v['node_id']=='S0' and len(v['actions'])<=3
    assert not any(x in json.dumps(v) for x in ['"when"','"effects"','"preset"'])
    r=c.post('/api/s11/sessions',headers=h,json={'role':'L','scenario':'fire_contact'})
    assert r.status_code==403

def test_directors_run_automatically_without_student_menu(env):
    c,h,v,_=start(env)
    v=path(c,h,v,['S0.look','S1.straw','S2.both'])
    assert v['node_id']=='S4'
    assert {a['id'] for a in v['actions']}=={'S4.go','S4.cancel'}

def test_idempotency_conflict_revision_and_ownership(env):
    c,h,v,d=start(env)
    r=act(c,h,v,'S0.look');assert r.status_code==200
    assert act(c,h,v,'S0.look').json()==r.json()
    assert act(c,h,v,'S0.look',request_id='different').status_code==409
    assert act(c,h,v,'S1.armor').status_code==409
    wrong={**env[1]('S2'),'X-Session-Token':d['token']}
    assert c.get('/api/s11/routes/'+v['route_id'],headers=wrong).status_code==403
    assert c.get('/api/s11/routes/'+v['route_id'],headers=env[1]('S1')).status_code==403

def test_k1_empty_expression_and_role_fork_keep_old_question(env):
    c,h,v,_=start(env)
    v=path(c,h,v,['S0.look','S1.straw','S2.both','S4.go'])
    assert v['node_id']=='S8'
    body={'request_id':'utterance','expected_revision':v['revision'],'actor_id':v['controller_id'],'text':'  '}
    assert c.post('/api/s11/routes/'+v['route_id']+'/expressions',headers=h,json=body).status_code==422
    assert act(c,h,v,'S8.ask').status_code==422
    body['text']='船到曹营太近，若被看穿怎么退？'
    r=c.post('/api/s11/routes/'+v['route_id']+'/expressions',headers=h,json=body);assert r.status_code==200,r.text;v=r.json()
    snapshot=next(s for s in reversed(v['snapshots']) if s['node_id']=='S8')
    r=c.post('/api/s11/routes/'+v['route_id']+'/forks',headers=h,json={'request_id':'fork','expected_revision':v['revision'],'actor_id':v['controller_id'],'snapshot_id':snapshot['id'],'role':'Z'})
    assert r.status_code==200,r.text
    fork=r.json();assert fork['role']=='Z' and fork['node_id']=='S8'
    assert body['text'] in str(fork['old_utterances'])
    assert c.get('/api/s11/routes/'+v['route_id'],headers=h).json()['role']=='L'

def test_cao_public_view_never_has_enemy_exact_arrows(env):
    c,h,v,_=start(env,'C')
    v=path(c,h,v,['C0.look','C1.shoot','C2.shoot'])
    assert 'first' not in v['visual'] and 'second' not in v['visual'] and 'arrows' not in v['visual']
    assert v['visual']['material']=='unknown'
    assert '103000' not in json.dumps(v,ensure_ascii=False)
    v=path(c,h,v,['CX.close'])
    assert v['ending']['id']=='E1' and '103000' not in str(v)

def test_group_member_attribution_and_control(env):
    c,h,v,_=start(env,activity_mode='group',members=['同伴'])
    other=v['members'][1]['id'];assert v['members'][1]['account_id'] is None
    assert act(c,h,v,'S0.look',actor_id=other).status_code==403
    r=c.post('/api/s11/routes/'+v['route_id']+'/expressions',headers=h,json={'request_id':'peer','expected_revision':v['revision'],'actor_id':other,'text':'我看船的另一侧还空着。'})
    assert r.status_code==200;v=r.json()
    evidence=env[2].state.s11.student_evidence('S1')
    assert evidence['expressions'][0]['actor_id']==other and evidence['expressions'][0]['account_id'] is None
    assert evidence['expressions'][0]['activity_mode']=='group'

def test_help_uses_current_visible_context_and_persists(env):
    c,h,v,_=start(env,'C')
    r=c.post('/api/s11/routes/'+v['route_id']+'/help',headers=h,json={'request_id':'help','expected_revision':v['revision'],'actor_id':v['controller_id'],'level':'example'})
    assert r.status_code==200,r.text
    v=r.json();assert v['help']['source']=='authored_context'
    assert not any(x in v['help']['text'] for x in ['103000','十万','火箭','草束'])
    review=c.get('/api/s11/routes/'+v['route_id']+'/review',headers=h).json()
    assert len(review['supports'])==1
    assert 'state' not in review

def test_standard_success_counts_once_and_persists(env):
    c,h,v,_=start(env,'Z')
    v=path(c,h,v,['S0.look','S1.straw','S2.both','S4.go','S8.route','S9.far','S10.drum','A0.turn','A4.go','R0.return','COUNT1.done'])
    assert v['status']=='ended' and v['ending']['id']=='E1'
    assert v['visual']['arrows']['tray']==103000
    assert v['visual']['arrows']['right']==v['visual']['arrows']['left']==0
    assert c.get('/api/s11/routes/'+v['route_id'],headers=h).json()==v

def test_fork_retains_prior_help_and_original_attribution(env):
    c,h,v,_=start(env)
    v=path(c,h,v,['S0.look','S1.straw','S2.both','S4.go'])
    common={'expected_revision':v['revision'],'actor_id':v['controller_id']}
    v=c.post('/api/s11/routes/'+v['route_id']+'/help',headers=h,json={**common,'request_id':'help-before','level':'organize'}).json()
    source_help=v['help']['id'];snapshot=v['snapshots'][-1]
    fork=c.post('/api/s11/routes/'+v['route_id']+'/forks',headers=h,json={'expected_revision':v['revision'],'actor_id':v['controller_id'],'request_id':'retry','snapshot_id':snapshot['id'],'role':'Z'}).json()
    r=c.post('/api/s11/routes/'+fork['route_id']+'/expressions',headers=h,json={'request_id':'answer','expected_revision':fork['revision'],'actor_id':fork['controller_id'],'text':'不登岸，留好来路；若停射便退。'})
    assert r.status_code==200
    expression=r.json()['saved_expression']
    assert source_help in expression['support_ids']
    assert expression['goal_id']=='G5'
    ev=env[2].state.s11.student_evidence('S1')
    assert all(e['route_id']!=fork['route_id'] for e in ev['events'])

def test_k1_transition_does_not_recite_production_instructions(env):
    c,h,v,_=start(env)
    v=path(c,h,v,['S0.look','S1.straw','S2.both','S4.go'])
    v=c.post('/api/s11/routes/'+v['route_id']+'/expressions',headers=h,json={'request_id':'u','expected_revision':v['revision'],'actor_id':v['controller_id'],'text':'我担心退路被封，该如何回来？'}).json()
    v=act(c,h,v,'S8.ask').json()
    assert any(t['speaker']=='诸葛亮' for t in v['transition'])
    assert not any(word in str(v['transition']) for word in ['存入K1','保存诸葛亮','本路','结算','实际返航操作'])

def test_teacher_preset_allows_planned_context_without_student_debug(env):
    c,auth,app=env
    r=c.put('/api/s11/teacher/students/S1/preset',headers=auth('T1'),json={'role':'L','scenario':'fire_contact'})
    assert r.status_code==200,r.text
    c,h,v,_=start(env,scenario='fire_contact')
    assert v['node_id']=='S0' and 'preset' not in v
    assert c.put('/api/s11/teacher/students/S2/preset',headers=h,json={'role':'C','scenario':'counterfire'}).status_code==403

def test_all_72_approved_routes_through_saved_http_api(env):
    c,h,v,_=start(env)
    path(c,h,v,['S0.look','S1.straw','S2.both','S4.cancel'])
    owner_auth={k:value for k,value in h.items() if k!='X-Session-Token'}
    r=runtime()
    for w in WITNESSES:
        response=c.post('/api/s11/sessions',headers=owner_auth,json={'role':w['role'],'scenario':w['preset']})
        assert response.status_code==200,(w['id'],response.text)
        data=response.json();view=data['view'];headers={**owner_auth,'X-Session-Token':data['token']}
        for eid in w['path']:
            node=eid.split('.')[0]
            if r.NODES[node]['kind']=='director':continue
            if eid=='S8.ask':
                response=c.post('/api/s11/routes/'+view['route_id']+'/expressions',headers=headers,json={'request_id':'K1','expected_revision':view['revision'],'actor_id':view['controller_id'],'text':'我担心对岸看清我们，退路怎样安排？'})
                assert response.status_code==200,(w['id'],response.text)
                view=response.json()
            response=act(c,headers,view,eid)
            assert response.status_code==200,(w['id'],eid,response.text)
            view=response.json()
            assert len(view['actions'])<=3
            assert r.NODES[view['node_id']]['kind']!='director'
            if w['role']=='C':
                assert not {'first','second','spent','loss','net','arrows'} & set(view['visual'])
        assert view['ending']['id']=='E'+w['ending'][1:],w['id']
        assert view['ending']['text']==w['ending_scene']['text'],w['id']
        assert c.get('/api/s11/routes/'+view['route_id'],headers=headers).json()==view,w['id']

def test_cross_role_cao_review_hides_ship_help_inventory(env):
    c,h,v,_=start(env)
    v=path(c,h,v,['S0.look','S1.straw','S2.both','S4.go','S8.route','S9.far','S10.drum','A0.turn','A4.go','R0.return','COUNT1.done'])
    v=c.post('/api/s11/routes/'+v['route_id']+'/help',headers=h,json={'request_id':'last-help','expected_revision':v['revision'],'actor_id':v['controller_id'],'level':'notice'}).json()
    fork=c.post('/api/s11/routes/'+v['route_id']+'/forks',headers=h,json={'request_id':'cao-fork','expected_revision':v['revision'],'actor_id':v['controller_id'],'snapshot_id':v['snapshots'][-1]['id'],'role':'C'}).json()
    assert 'returned' not in fork['visual'] and 'collected' not in fork['visual']
    review=c.get('/api/s11/routes/'+fork['route_id']+'/review',headers=h).json()
    assert '103000' not in json.dumps(review,ensure_ascii=False)

def test_expression_help_temporal_attribution_and_persistent_reload(env):
    c,h,v,d=start(env)
    def write(view,rid):return c.post('/api/s11/routes/'+view['route_id']+'/expressions',headers=h,json={'request_id':rid,'expected_revision':view['revision'],'actor_id':view['controller_id'],'text':'我先去听听韩伯说船的布置。'}).json()
    v=write(v,'before');assert not v['saved_expression']['support_ids']
    v=c.post('/api/s11/routes/'+v['route_id']+'/help',headers=h,json={'request_id':'help','expected_revision':v['revision'],'actor_id':v['controller_id'],'level':'organize'}).json()
    v=write(v,'after');assert len(v['saved_expression']['support_ids'])==1
    from app.s11_service import S11Service
    reopened=S11Service(env[2].state.service.engine,env[2].state.platform)
    auth=env[2].state.platform.authenticate(h['Authorization'])
    restored=reopened.get_view(auth,v['route_id'],d['token'])
    assert restored['revision']==v['revision']
    expressions=reopened.student_evidence('S1')['expressions']
    assert len(expressions[0]['support_ids'])==0 and len(expressions[1]['support_ids'])==1

def test_public_transition_is_performed_dialogue_not_build_notes():
    from app.s11_service import S11Service
    r=runtime()
    for w in WITNESSES:
        state=r.initial(w['role'],w['preset']);node='C0' if w['role']=='C' else 'S0'
        for eid in w['path']:
            e=next(e for e in r.NODES[node]['edges'] if e['id']==eid)
            after=r.advance(e,state);_,reply=r.render_edge(e,state,after)
            transitions=S11Service.spoken_transition(reply,r.NODES[node],e,after)
            for item in transitions:
                assert not any(word in item['text'] for word in ['学生确认','本路','玩家','全知','结算','不显示','不覆盖','实际返航操作','不把镜头','按实际','只播','末场保留']), (eid,item)
            state=after;node=e['to']

def test_help_has_concrete_scene_work_instead_of_sentence_templates(env):
    c,h,v,_=start(env)
    v=path(c,h,v,['S0.look'])
    v=c.post('/api/s11/routes/'+v['route_id']+'/help',headers=h,json={'request_id':'place-help','expected_revision':v['revision'],'actor_id':v['controller_id'],'level':'example'}).json()
    assert v['help']['speaker']=='沈砚'
    assert '中间韩伯还要走过去' in v['help']['text']
    assert not any(w in v['help']['text'] for w in ['先听眼前','先说','把空处','我听见你说'])

def test_ending_has_structured_performed_lines_and_shot(env):
    c,h,v,_=start(env,'Z')
    v=path(c,h,v,['S0.look','S1.straw','S2.both','S4.cancel'])
    assert all(set(x)=={'speaker','text'} for x in v['ending']['lines'])
    assert any(x['speaker']=='诸葛亮' for x in v['ending']['lines'])
    assert '泊岸绳' in v['ending']['closing_shot']
    assert not any(w in str(v['ending']['lines']) for w in ['末镜','本路','教学账'])

def test_k1_fork_old_question_is_actual_current_spoken_line(env):
    c,h,v,_=start(env)
    v=path(c,h,v,['S0.look','S1.straw','S2.both','S4.go'])
    question='他们若出船追来，咱们怎么回去？'
    v=c.post('/api/s11/routes/'+v['route_id']+'/expressions',headers=h,json={'request_id':'q','expected_revision':v['revision'],'actor_id':v['controller_id'],'text':question}).json()
    snap=v['snapshots'][-1]
    assert snap['title']=='寨外发问' and snap['summary']
    f=c.post('/api/s11/routes/'+v['route_id']+'/forks',headers=h,json={'request_id':'f','expected_revision':v['revision'],'actor_id':v['controller_id'],'snapshot_id':snap['id'],'role':'Z'}).json()
    assert f['speaker']=='鲁肃' and ''.join(f['lines'])==question
    answer=c.post('/api/s11/routes/'+f['route_id']+'/expressions',headers=h,json={'request_id':'new-answer','expected_revision':f['revision'],'actor_id':f['controller_id'],'text':'不登岸。请韩伯留住回南岸的路，听令便退。'}).json()['saved_expression']
    assert answer['responds_to_id']==v['saved_expression']['id']
    assert answer['responds_to_route_id']==v['route_id']

def test_help_does_not_offer_used_change_or_invent_approaching_boat():
    from app.s11_help import scene_help
    r=runtime();state=r.initial('L','quiet');state.update(method='drum',drummed=True,changed=True)
    assert '换法' not in scene_help('S12',state,'organize')[1]
    state.update(material='armor',first=34000,turned=True)
    assert '正在靠近' not in scene_help('S15',state,'organize')[1]
    state=r.initial('C','clear')
    assert '雾里看不清' not in scene_help('C1',state,'notice')[1]

def test_shared_screen_help_is_not_claimed_as_independent_peer_work(env):
    c,h,v,_=start(env,activity_mode='group',members=['同伴'])
    peer=v['members'][1]['id']
    v=c.post('/api/s11/routes/'+v['route_id']+'/help',headers=h,json={'request_id':'shared-help','expected_revision':v['revision'],'actor_id':v['controller_id'],'level':'notice'}).json()
    help_id=v['help']['id']
    v=c.post('/api/s11/routes/'+v['route_id']+'/expressions',headers=h,json={'request_id':'peer-after-help','expected_revision':v['revision'],'actor_id':peer,'text':'韩伯站在船边，我们先跟他去看。'}).json()
    assert help_id in v['saved_expression']['support_ids']
    assert v['saved_expression']['account_id'] is None

def test_k1_zhuge_retry_faces_new_unshot_watchboat_question_and_keeps_source(env):
    c,h,v,_=start(env)
    v=path(c,h,v,['S0.look','S1.straw','S2.both','S4.go'])
    question='他们若出船追来，咱们怎么回去？'
    v=c.post('/api/s11/routes/'+v['route_id']+'/expressions',headers=h,json={'request_id':'original-k1','expected_revision':v['revision'],'actor_id':v['controller_id'],'text':question}).json()
    source_id=v['route_id'];snapshot=v['snapshots'][-1]
    source_review=c.get('/api/s11/routes/'+source_id+'/review',headers=h).json()
    fork=c.post('/api/s11/routes/'+source_id+'/forks',headers=h,json={'request_id':'k1-watchboat','expected_revision':v['revision'],'actor_id':v['controller_id'],'snapshot_id':snapshot['id'],'role':'Z'}).json()
    assert fork['node_id']=='S8' and ''.join(fork['lines'])==question
    assert fork['visual']['first']==fork['visual']['second']==0
    assert not fork['visual']['drummed'] and not fork['visual']['hailed']
    fork=c.post('/api/s11/routes/'+fork['route_id']+'/expressions',headers=h,json={'request_id':'new-k1-answer','expected_revision':fork['revision'],'actor_id':fork['controller_id'],'text':'我们不登岸。韩伯留好回路，若他们出艇就收船。'}).json()
    assert fork['visual']['first']==0 and not fork['visual'].get('scout_approaching')
    fork=path(c,h,fork,['S8.ask','S9.far','S10.drum'])
    assert fork['node_id']=='S12'
    assert fork['speaker']=='鲁肃'
    assert ''.join(fork['lines'])=='他们真的出艇了，现在就走，还是再等？'
    assert fork['visual']['first']==fork['visual']['second']==0
    assert fork['visual']['scout_approaching'] is True
    assert {'S12.go','S12.wait'} <= {a['id'] for a in fork['actions']}
    fork_review=c.get('/api/s11/routes/'+fork['route_id']+'/review',headers=h).json()
    assert any(e['responds_to_id']==v['saved_expression']['id'] for e in fork_review['expressions'])
    after=c.get('/api/s11/routes/'+source_id+'/review',headers=h).json()
    assert after['events']==source_review['events']
    assert after['expressions']==source_review['expressions']
    original=path(c,h,c.get('/api/s11/routes/'+source_id,headers=h).json(),['S8.ask','S9.far','S10.drum'])
    assert original['node_id']=='A0' and original['visual']['first']==52000
    fork=path(c,h,fork,['S12.go','R0.return'])
    assert fork['ending']['id']=='E4' and fork['visual']['net']==0


def test_non_k1_same_role_and_other_snapshot_forks_keep_standard_response(env):
    c,h,v,_=start(env)
    v=path(c,h,v,['S0.look','S1.straw','S2.both','S4.go'])
    for snap,role,steps in [(v['snapshots'][-1],'L',['S8.route','S9.far','S10.drum']),(v['snapshots'][0],'Z',['S0.look','S1.straw','S2.both','S4.go','S8.route','S9.far','S10.drum'])]:
        source=c.get('/api/s11/routes/'+v['route_id'],headers=h).json()
        fork=c.post('/api/s11/routes/'+source['route_id']+'/forks',headers=h,json={'request_id':'ordinary-'+role,'expected_revision':source['revision'],'actor_id':source['controller_id'],'snapshot_id':snap['id'],'role':role}).json()
        fork=path(c,h,fork,steps)
        assert fork['node_id']=='A0' and fork['visual']['first']==52000
        assert not fork['visual'].get('scout_approaching')
