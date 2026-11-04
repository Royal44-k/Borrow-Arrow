import copy
import pytest
from app.v1_story import initial, scene, step, operation_payload, OperationError

def walk(role, choices, scenario='mist'):
    s=initial(role,scenario)
    for c in choices:s=step(s,c,{**operation_payload(s),'text':'若敌船出寨，后船如何撤回？'})
    return s

def test_cao_does_not_end_at_hold():
    s=walk('C',['observe','hold'])
    assert s['node']=='C_wait' and not s['ending']
    assert any('鼓' in l['text'] for l in scene(s)['lines'])

def test_quiet_three_person_resolution():
    s=walk('C',['observe','hold','stay','return','north','south','report','finish'])
    assert s['ending']=='E1' and s['node']=='done'
    assert s['yield']==0

def test_turn_preserves_first_load_and_no_magic_weather():
    s=walk('Z',['load','signals','wait','launch','ask','approach'],'clear')
    assert s['weather']=='clear'
    assert s['node']=='clear_seen' and s['yield']==0
    s=walk('Z',['load','signals','launch','ask','approach','drum','turn'])
    assert s['yield']==100000 and s['turned']

def test_all_edges_terminate_without_infinite_wait():
    visited=set(); edges=set(); endings=set()
    def visit(s,depth):
        assert depth<24
        key=(s['role'],s['scenario'],s['node'],s['yield'],s['retry'],s['peril'],s['waited'])
        if key in visited:return
        visited.add(key);v=scene(s)
        if s['node']=='done':endings.add(s['ending']);return
        assert v['actions']
        assert len(v['actions'])<=4
        for a in v['actions']:
            edges.add((s['node'],a['id']))
            n=step(s,a['id'],operation_payload(s))
            assert s!=n and n['yield']>=s['yield']
            visit(n,depth+1)
    for r in ['L','Z','C']:
        for p in ['mist','quiet','scout','clear']:visit(initial(r,p),0)
    assert endings=={'E0','E1','E2','E3','E4'}
    assert len(edges)>45

def test_illegal_action_cannot_change_state():
    s=initial('C','mist');old=copy.deepcopy(s)
    with pytest.raises(ValueError):step(s,'turn',{})
    assert old==s

def test_hidden_enemy_yield_not_exposed_in_cao_scene():
    s=walk('C',['observe','shoot'])
    v=scene(s)
    assert '50000' not in str(v) and '五万' not in str(v)

def test_lusu_can_insist_and_be_heard():
    s=walk('L',['explain','signals','launch','ask','approach','drum','withdraw','insist'],'quiet')
    assert s['node']=='return' and s['urged']

def test_wrong_operation_cannot_fake_rescue_or_turn():
    s=walk('L',['explain','signals','launch','ask','approach','drum'],'scout')
    with pytest.raises(OperationError):step(s,'rescue',{'position':10})
    assert step(s,'rescue',{'position':80})['node']=='return'
    a=walk('Z',['explain','signals','launch','ask','approach','drum'])
    with pytest.raises(OperationError):step(a,'turn',{'position':10})

def test_cancelled_mist_does_not_invent_clear_night_or_sailing():
    s=walk('L',['explain','signals','cancel','north','south'])
    assert '无雾' not in str(scene(s))
    s=step(s,'report',operation_payload(s))
    assert '没有出航' in str(scene(s)) and '我在船上' not in str(scene(s))
    s=step(s,'finish',operation_payload(s))
    assert scene(s)['art']=='preparation' and '卸船' not in str(scene(s))

def test_clear_prep_keeps_weather_and_second_probe_is_not_urged():
    clear=walk('L',['load'],'clear')
    assert '夜里雾厚' not in str(scene(clear))
    s=walk('L',['load','signals','launch','ask','approach','drum','probe','withdraw'],'quiet')
    assert not s['urged']
    s=step(s,'north',operation_payload(s));s=step(s,'south',operation_payload(s))
    assert '劝我收船' not in str(scene(s))
