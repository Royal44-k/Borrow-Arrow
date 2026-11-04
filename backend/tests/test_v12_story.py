"""V1.2 contracts: meaningful operations, authored choices and bounded branches."""
import copy
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.v1_story import initial, scene, step, operation_payload, OperationError


def fresh(role='L', scenario='mist'):
    s = initial(role, scenario)
    s['design_version'] = 'V1.2'
    return s


ASSEMBLY = dict(port_straw=True, starboard_straw=True, cloth=True, clear_aisle=True)


def travel(actions, role='L', scenario='mist'):
    s = fresh(role, scenario)
    for a in actions:
        s = step(s, a, operation_payload(s))
    return s


def test_assembly_is_required_complete_and_saved_without_mutating_old_state():
    s = fresh()
    original = copy.deepcopy(s)
    for assembly in [None, {}, {**ASSEMBLY, 'cloth': False}, {**ASSEMBLY, 'cloth': 1}]:
        with pytest.raises(OperationError):
            step(s, 'load', {'assembly': assembly})
    done = step(s, 'load', {'assembly': ASSEMBLY})
    assert done['node'] == 'signals' and done['assembly'] == ASSEMBLY
    assert s == original
    assert step(initial('L'), 'load', {})['node'] == 'signals'


def test_return_signal_requires_message_and_order_but_not_speed():
    s = fresh(); s['node'] = 'signals'
    for payload in [dict(signal_order=['前船', '后船', '领船']),
                    dict(signal_order=['领船', '前船', '后船'], signal_message='归队'),
                    dict(signal_order=['前船', '后船', '领船'], signal_message='进攻')]:
        with pytest.raises(OperationError):
            step(s, 'signals', payload)
    assert step(s, 'signals', {'signal_order': ['前船', '后船', '领船'], 'signal_message': '归队'})['node'] == 'weather'
    s['node'] = 'side_check'
    with pytest.raises(OperationError):
        step(s, 'turn', {'position': 90, 'signal_order': ['前船', '后船', '领船']})


@pytest.mark.parametrize('hits', [0, 1, 2, True, 3.0, '3'])
def test_drum_rejects_incomplete_or_non_integer_signals(hits):
    s = fresh(); s['node'] = 'challenge'
    with pytest.raises(OperationError):
        step(s, 'drum', {'drum_signals': hits})


@pytest.mark.parametrize('scenario,node', [('mist','arrows'), ('quiet','silence'), ('scout','scout')])
def test_three_drum_signals_have_scenario_specific_consequences(scenario, node):
    s = fresh(scenario=scenario); s['node'] = 'challenge'
    assert step(s, 'drum', {'drum_signals': 3})['node'] == node


@pytest.mark.parametrize('x', [None, 0, -4, 10, float('inf'), float('nan'), True])
def test_rescue_cannot_ignore_last_boat_horizontal_position(x):
    s = fresh(scenario='scout'); s['node'] = 'scout'
    with pytest.raises(OperationError):
        step(s, 'rescue', {'position': 80, 'river_x': x})
    assert step(s, 'rescue', {'position': 80, 'river_x': 5})['node'] == 'return'


@pytest.mark.parametrize('role', ['L', 'Z', 'C'])
def test_scenario_openings_expose_four_different_situations(role):
    views = [scene(fresh(role, p)) for p in ['mist','quiet','scout','clear']]
    assert len({str(v['lines']) for v in views}) == 4
    assert {v['scenario_id'] for v in views} == {'mist','quiet','scout','clear'}
    assert all(v['scenario_brief'] for v in views)
    # The player can still change Cao's orders in every situation.
    if role == 'C':
        for p in ['mist','quiet','scout','clear']:
            s = step(fresh('C', p), 'observe', {})
            assert {'hold','shoot','boats','delegate'} == {a['id'] for a in scene(s)['actions']}


def test_choice_is_addressed_to_character_and_server_owns_canonical_text():
    s = fresh(); s['node'] = 'K1'
    choices = scene(s)['choices']
    assert len(choices) >= 2 and all(c['recipient'] == '诸葛亮' for c in choices)
    picked = choices[0]
    n = step(s, 'ask', {'utterance_id': picked['id'], 'text': '我补充的退路建议。'})
    assert n['question'] == picked['text']
    assert n['question_source'] == 'selected_response'
    with pytest.raises(ValueError):
        step(s, 'ask', {'utterance_id':'invented', 'text':'伪造的预设句。'})
    s['role'] = 'Z'
    assert all(c['recipient'] == '鲁肃' for c in scene(s)['choices'])
    # Existing routes also gain the optional choices without losing free text.
    old = initial('L'); old['node'] = 'K1'
    assert scene(old)['choices']
    assert step(old, 'ask', {'text':'若有哨船，先接末船。'})['question'] == '若有哨船，先接末船。'


def test_all_reachable_new_edges_terminate_and_show_specific_outcomes():
    seen = set(); endings = set(); role_titles = {}
    def visit(s, depth):
        assert depth < 24
        key = (s['role'], s['scenario'], s['node'], s['yield'], s['retry'], s['peril'], s['waited'])
        if key in seen: return
        seen.add(key); v = scene(s)
        if s['node'] == 'done':
            endings.add(s['ending'])
            assert all(v['outcome'][k] for k in ['title','summary','bank','lesson'])
            role_titles.setdefault(s['ending'], {})[s['role']] = v['outcome']['title']
            return
        for a in v['actions']:
            visit(step(s, a['id'], operation_payload(s, a['id'])), depth + 1)
    for role in ['L','Z','C']:
        for scenario in ['mist','quiet','scout','clear']:
            visit(fresh(role, scenario), 0)
    assert endings == {'E0','E1','E2','E3','E4'}
    for ending, titles in role_titles.items():
        assert len(set(titles.values())) == len(titles)


def test_scout_aftermath_does_not_claim_enemy_remained_motionless():
    s = travel(['load','signals','launch','ask','approach','drum','rescue','north','south'], scenario='scout')
    assert s['node'] == 'south'
    assert '寨门不动' not in str(scene(s)) and '哨' in str(scene(s))
    s = step(s, 'report', operation_payload(s))
    assert '曹军始终未发一箭' not in str(scene(s))


def test_export_payload_without_action_remains_valid_for_both_disagreement_actions():
    s = fresh(); s['node'] = 'disagree'; s['contact'] = True
    for action in ['probe', 'insist']:
        assert step(s, action, operation_payload(s))['node'] != 'disagree'


def test_cao_endings_reveal_southern_consequence_without_flattening_arrow_counts():
    endings = {}
    tails = ['return','north','south','report','finish']
    for key, decisions in [('none',['observe','hold','stay']),
                           ('half',['observe','shoot','stop','stay']),
                           ('full',['observe','shoot','continue']),
                           ('scout',['observe','shoot','boats','recall'])]:
        endings[key] = scene(travel(decisions+tails, role='C'))['outcome']['other_bank']
    assert '诸葛亮' in endings['none'] and '鲁肃' in endings['none']
    assert '五万' in endings['half'] and '十万' in endings['full']
    assert '末船' in endings['scout'] and '五万' in endings['scout']
    assert len(set(endings.values())) == 4


def test_clear_night_cao_success_for_enemy_does_not_invent_fog_at_ending():
    s = travel(['observe','shoot','continue','return','north','south','report','finish'], role='C', scenario='clear')
    other = scene(s)['outcome']['other_bank']
    assert '月' in other and '浓雾' not in other


@pytest.mark.parametrize('role', ['L', 'Z'])
def test_clear_night_withdrawal_never_claims_a_drum_action_that_did_not_happen(role):
    s = travel(['load','signals','launch','ask','approach'], role=role, scenario='clear')
    assert '不再擂鼓' not in str(scene(s)['lines'])
    for action in ['withdraw','north','south','report','finish']:
        s = step(s, action, operation_payload(s, action))
        view = scene(s)
        text = str([view['lines'],view['choices'],view.get('outcome')])
        assert all(phrase not in text for phrase in ['未应鼓','鼓声没有换来','鼓声没了','收起鼓槌','停鼓'])
    assert '月' in scene(s)['outcome']['summary']
    assert '月' in s['reason']


def test_clear_probe_enters_scout_without_inventing_a_prior_drum_signal():
    s = travel(['load','signals','launch','ask','approach','probe'], scenario='clear')
    assert s['node'] == 'scout'
    assert '停鼓' not in str(scene(s)['lines'])
    s = step(s, 'rescue', operation_payload(s))
    assert s.get('drum_started') is not True


def test_cao_clear_full_load_southern_dialogue_does_not_invent_mist():
    s = travel(['observe','shoot','continue','return','north','south'],role='C',scenario='clear')
    assert '借着浓雾' not in str(scene(s)['lines'])


def test_real_drum_attempt_is_preserved_in_quiet_aftermath():
    s = travel(['load','signals','launch','ask','approach','drum','probe','withdraw','north','south'], scenario='quiet')
    assert s['drum_started'] is True
    assert '未应鼓' in next(x['text'] for x in scene(s)['choices'] if x['id']=='south_result')


@pytest.fixture
def api(tmp_path):
    app = create_app(database_url=f'sqlite:///{tmp_path}/course.db', platform_database_url=f'sqlite:///{tmp_path}/platform.db')
    app.state.platform.create_account('S12','新同学','student','DemoStudent123!',class_id='DEMO7',demo=True)
    c = TestClient(app)
    token = c.post('/api/auth/login', json={'user_id':'S12','password':'DemoStudent123!'}).json()['token']
    return c, {'Authorization':'Bearer ' + token}


@pytest.mark.parametrize('version', [None, 'V1.2'])
def test_help_records_exact_server_guide_displayed_to_student(api, version):
    c,h = api
    r = c.post('/api/v1/runs',headers=h,json={'design_version':version}).json()
    shown = r['scene']['guide_text']
    assert shown and shown != r['scene']['prompt']
    r = c.post(f"/api/v1/runs/{r['id']}/actions",headers=h,json={
        'request_id':'guide','revision':0,'action':'help','payload':{'text':'伪造的客户端帮助'}}).json()
    assert r['supports'][-1]['text'] == shown
    assert r['scene']['guide_text'] == shown
    assert r['supports'][-1]['source'] == 'authored_context'


def test_versioned_api_records_choice_separately_and_forks_it(api):
    c,h = api
    response = c.post('/api/v1/runs', headers=h, json={'role':'L','design_version':'V1.2'})
    assert response.status_code == 200, response.text
    r = response.json(); assert r['design_version'] == 'V1.2'
    def move(action,payload):
        nonlocal r
        reply = c.post(f"/api/v1/runs/{r['id']}/actions",headers=h,json={'request_id':str(r['revision']),'revision':r['revision'],'action':action,'payload':payload})
        assert reply.status_code == 200, reply.text
        r = reply.json()
    move('load', {'assembly': ASSEMBLY})
    move('signals', {'signal_order':['前船','后船','领船'],'signal_message':'归队'})
    move('launch', {})
    choice = r['scene']['choices'][0]
    move('ask', {'utterance_id':choice['id'],'text':choice['text']})
    assert not r['expressions']  # Echoed authored copy is not a learner essay.
    selected = [e for e in r['history'] if e['kind'] == 'selected_response']
    assert selected[0]['text'] == choice['text'] and selected[0]['recipient'] == '诸葛亮'
    snapshot = next(s['index'] for s in r['snapshots'] if s['node'] == 'K1')
    fork = c.post(f"/api/v1/runs/{r['id']}/fork",headers=h,json={'snapshot':snapshot,'role':'Z'}).json()
    assert fork['old_question'] == choice['text'] and fork['design_version'] == 'V1.2'
    old = c.post('/api/v1/runs',headers=h,json={}).json()
    reply = c.post(f"/api/v1/runs/{old['id']}/actions",headers=h,json={'request_id':'old','revision':0,'action':'load','payload':{}})
    assert reply.json()['scene']['node'] == 'signals'


def test_original_addition_remains_distinct_from_authored_sentence(api):
    c,h = api
    r = c.post('/api/v1/runs',headers=h,json={'design_version':'V1.2'}).json()
    for a,p in [('load',{'assembly':ASSEMBLY}),('signals',{'signal_order':['前船','后船','领船'],'signal_message':'归队'}),('launch',{})]:
        r = c.post(f"/api/v1/runs/{r['id']}/actions",headers=h,json={'request_id':str(r['revision']),'revision':r['revision'],'action':a,'payload':p}).json()
    picked = r['scene']['choices'][0]
    r = c.post(f"/api/v1/runs/{r['id']}/actions",headers=h,json={'request_id':'say','revision':r['revision'],'action':'ask','payload':{'utterance_id':picked['id'],'text':'还要让后船先应一声。'}}).json()
    assert r['question'] == picked['text']
    assert r['expressions'][0]['source'] == 'learner_original'
    assert r['expressions'][0]['text'] == '还要让后船先应一声。'
