from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

from app import v1_story as story


NEW_NODES = set('rain_warning rain_ranks rain_early_return turn_gap rain_listen rain_lull rain_feint rain_escape C_draw_bows C_probe_report C_first_rain C_stop_signal C_reload C_second_rain C_arrow_depart C_holdfire'.split())


def start(role='L', node=None, scenario='mist', version='V1.6'):
    s = story.initial(role, scenario, version)
    if node:
        s.update(node=node, departed=True, contact=True)
    return s


def go(s, choice=None, payload=None):
    choice = choice or story.scene(s)['actions'][0]['id']
    return story.step(s, choice, story.operation_payload(s, choice) if payload is None else payload)


def finish(s):
    seen = []
    while s['node'] != 'done':
        assert s['node'] not in seen
        seen.append(s['node'])
        s = go(s)
    return s, seen


def first_rain(command='spread', close=False):
    s = go(start(node='approach'), 'approach', {'position':66 if close else 40})
    if close:
        s = go(s)
    s = go(s, command)
    s = go(s, 'probe' if s['node'] in {'gap_escape', 'hold_channel'} else 'continue')
    s = go(s, 'drum')
    assert s['node'] == 'rain_warning' and s['yield'] == 0
    s = go(s, 'steady')
    assert s['node'] == 'rain_ranks' and s['yield'] == 0
    s = go(s, 'receive')
    assert s['node'] == 'arrows' and s['yield'] == 50000
    return s


def test_v16_initial_is_version_gated_and_does_not_receive_arrows_before_rain():
    s = start()
    assert s['design_version'] == 'V1.6' and s['yield'] == 0
    first_rain()


@pytest.mark.parametrize('turn_from', ['arrows', 'side_check'])
@pytest.mark.parametrize('position', [None, True, False, -1, 79, 101, '80', float('nan'), float('inf')])
def test_turn_requires_real_finite_maneuver_and_preserves_old_state(turn_from, position):
    s = first_rain()
    if turn_from == 'side_check':
        s = go(s, 'holdside')
    before = deepcopy(s)
    with pytest.raises(story.OperationError):
        go(s, 'turn', {'position': position})
    assert s == before
    result = go(s, 'turn', {'position':80})
    assert result['node'] == 'turn_gap' and result['turned'] and result['yield'] == 50000


@pytest.mark.parametrize('command,close,turn_choice,expected', [
    ('spread', False, 'drumturn', 'second'),
    ('advance', False, 'drumturn', 'rain_lull'),
    ('spread', True, 'drumturn', 'rain_lull'),
    ('recall', False, 'drumturn', 'second'),
    ('advance', False, 'quietturn', 'rain_listen'),
])
def test_turn_response_depends_on_actual_earlier_orders(command, close, turn_choice, expected):
    s = go(first_rain(command, close), 'turn')
    s = go(s, turn_choice)
    assert s['node'] == expected
    assert s['yield'] == (100000 if expected == 'second' else 50000)


@pytest.mark.parametrize('path,count', [
    (['withdraw'], 50000),
    (['holdside', 'withdraw'], 50000),
    (['turn', 'quietturn', 'withdraw'], 50000),
    (['turn', 'quietturn', 'signal'], 100000),
    (['turn', 'drumturn', 'withdraw'], 50000),
    (['turn', 'drumturn', 'feint', 'continue', 'withdraw'], 50000),
])
def test_south_branches_keep_exact_tally_and_cause_to_ending(path, count):
    s = first_rain('advance')
    for choice in path:
        s = go(s, choice)
    s, nodes = finish(s)
    assert s['yield'] == count
    assert {'landing', 'muster', 'unload', 'arrow_tally'} <= set(nodes)
    assert s['arrow_tally']['total'] == count
    assert s['narrative_reason'] in story.ending_outcome(s)['summary']
    assert str(count) in story.ending_outcome(s)['summary']


def test_early_departure_has_zero_arrows_because_it_precedes_receiving():
    s = go(start(node='challenge'), 'drum')
    s = go(s, 'withdraw')
    assert s['node'] == 'rain_early_return' and s['yield'] == 0
    assert '未等箭入草' in str(story.scene(s)['lines'])
    s, _ = finish(s)
    assert s['yield'] == 0 and '未等箭入草' in story.ending_outcome(s)['summary']
    assert '曹操没有开弓' not in str(story.ending_outcome(s))


@pytest.mark.parametrize('opening', ['C_observe', 'C_wait'])
@pytest.mark.parametrize('path,count,last', [
    (['shoot', 'mass', 'continue', 'stop', 'continue', 'stay'], 50000, 'C_depart'),
    (['shoot', 'probe', 'mass', 'continue', 'continue', 'halt', 'continue', 'stay'], 50000, 'C_depart'),
    (['shoot', 'mass', 'continue', 'continue', 'volley', 'continue', 'continue'], 100000, 'C_depart'),
    (['shoot', 'probe', 'hold', 'watch'], 0, 'C_depart'),
    (['shoot', 'probe', 'boats'], 0, 'C_scout'),
    (['shoot', 'probe', 'hold', 'boats'], 0, 'C_scout'),
])
def test_north_orders_have_separate_draw_fire_reload_and_departure(opening, path, count, last):
    s = start('C', opening)
    for choice in path:
        s = go(s, choice)
        expected = 100000 if s['node'] in {'C_second_rain', 'C_arrow_depart'} else count if s['node'] == last else 50000 if s['node'] in {'C_first_rain', 'C_shoot', 'C_reload', 'C_stop_signal', 'C_recognize'} else 0
        assert s['yield'] == expected
    assert s['node'] == last
    s, _ = finish(s)
    assert s['yield'] == count and s['narrative_reason'] in story.ending_outcome(s)['summary']


def test_second_rain_requires_real_return_heading_and_does_not_repeat_receive():
    s = go(go(first_rain(), 'turn'), 'drumturn')
    assert s['node'] == 'second'
    for p in [{}, {'position':80}, {'position':True}, {'position':float('nan')}]:
        with pytest.raises(story.OperationError):
            go(s, 'return', p)
    returned = go(s, 'return', {'position':25})
    assert returned['node'] == 'return' and returned['yield'] == 100000


def test_scene_battle_load_and_browsing_are_read_only_story_facts():
    cases = [('rain_warning', 0, False, 'warning', 'deck'), ('C_probe_report', 0, False, 'warning', 'north'),
             ('arrows', 50000, False, 'first', 'deck'), ('C_first_rain', 50000, False, 'first', 'north'),
             ('second', 100000, True, 'second', 'deck'), ('C_second_rain', 100000, True, 'second', 'north'),
             ('turn_gap', 50000, True, None, None)]
    for node, count, turned, phase, view in cases:
        s = start('C' if node.startswith('C_') else 'L', node)
        s.update(turned=turned, **{'yield':count})
        before = deepcopy(s)
        v = story.scene(s)
        assert v['battle'] == ({'phase':phase, 'view':view} if phase else None)
        assert v['ship_load'] == {'port':1 if count == 100000 else 0, 'starboard':1 if count else 0}
        assert v['cargo']['arrows'] == count
        if phase and view == 'north':
            assert '南船' in str(v['lines'])
            assert '镜头' not in str(v['lines'])
        if node in {'arrows','second'}:
            assert v['art'] == 'v16/' + node
        for _ in range(3):
            story.scene(s)
            story.operation_payload(s)
        assert s == before


@pytest.mark.parametrize('role,node,choice', [('L','assembly','assemble'), ('Z','fleet_order','advance'), ('C','C_order','spread'), ('L','muster','verify'), ('L','arrow_tally','verify')])
def test_inherited_evidence_contracts_still_reject_missing_and_forged_proof(role,node,choice):
    s=start(role,node)
    before=deepcopy(s)
    for payload in [{}, {'utterance_id':'invented'}, {'nav_signal':{'command':choice}}, {'assembly':{}}, {'muster':{'total':20}}, {'arrow_tally':{'total':0}}]:
        with pytest.raises(ValueError):
            go(s,choice,payload)
        assert s == before
    assert go(s,choice)['node'] != node


@pytest.mark.parametrize('position', [65,66])
@pytest.mark.parametrize('channel', ['sound','light'])
def test_wrong_close_position_is_consequential_and_signal_proof_remains_executable(position,channel):
    s=go(start(node='approach'),'approach',{'position':position})
    if position > 65:
        s=go(s)
    p=story.operation_payload(s,'spread')
    p['nav_signal']['channel']=channel
    invalid=deepcopy(p)
    invalid['nav_signal']['relays'].reverse()
    before=deepcopy(s)
    with pytest.raises(story.OperationError):
        go(s,'spread',invalid)
    assert s == before
    s=go(s,'spread',p)
    assert s['node'] == ('gap_escape' if position>65 else 'spread_channel')
    assert s['nav_signal'][0]['channel'] == channel


@pytest.mark.parametrize('node', sorted(NEW_NODES))
def test_new_story_beats_do_not_accept_fabricated_response_or_cutscene_actions(node):
    s=start('C' if node.startswith('C_') else 'L',node)
    before=deepcopy(s)
    with pytest.raises(ValueError):
        go(s,payload={'utterance_id':'from-another-scene'})
    for action in ['back','skip_animation','receive_again','complete_battle']:
        with pytest.raises(ValueError):
            go(s,action,{})
    assert s == before


def test_every_new_node_and_edge_is_reachable_on_complete_legal_routes():
    nodes, edges, endings, seen = set(), set(), set(), set()
    def visit(s, path, stations):
        key = repr(sorted(s.items()))
        if key in seen:
            return
        seen.add(key)
        before = deepcopy(s)
        v = story.scene(s)
        assert s == before and s['node'] not in path and len(path) < 64
        stations += int(v['interaction'] == 'nav_signal')
        assert stations <= 1
        assert s['yield'] in {0, 50000, 100000}
        with pytest.raises(ValueError):
            go(s, 'not_an_action')
        assert s == before
        if s['node'] in NEW_NODES:
            nodes.add(s['node'])
            assert v['stage_description'] and v['title'] and len(v['lines']) >= 3
            assert v['art'] == 'v16/' + s['node']
        if s['node'] == 'done':
            endings.add(s['ending'])
            return
        for a in v['actions']:
            payloads = [story.operation_payload(s, a['id'])]
            if s['node'] == 'approach' or (s['node'] == 'C_scout' and a['id'] == 'press'):
                payloads = [{**payloads[0], 'position':p} for p in [65,66]]
            for payload in payloads:
                after = go(s, a['id'], payload)
                assert s == before
                if s['node'] in NEW_NODES or after['node'] in NEW_NODES:
                    edges.add((s['node'],a['id'],after['node']))
                visit(after, path + [s['node']], stations)
    for role in ['L','Z','C']:
        for scenario in ['mist','quiet','scout','clear']:
            visit(start(role,scenario=scenario), [], 0)
    assert nodes == NEW_NODES and endings == {'E0','E1','E2','E3','E4'}
    expected = {
        ('rain_warning','steady','rain_ranks'), ('rain_warning','withdraw','rain_early_return'),
        ('rain_ranks','receive','arrows'), ('rain_early_return','return','return'),
        ('turn_gap','quietturn','rain_listen'), ('turn_gap','drumturn','second'), ('turn_gap','drumturn','rain_lull'),
        ('rain_listen','signal','second'), ('rain_listen','withdraw','return'),
        ('rain_lull','feint','rain_feint'), ('rain_lull','withdraw','return'),
        ('rain_feint','continue','rain_escape'), ('rain_escape','withdraw','return'),
        ('C_draw_bows','probe','C_probe_report'), ('C_draw_bows','mass','C_first_rain'),
        ('C_probe_report','mass','C_first_rain'), ('C_probe_report','hold','C_holdfire'), ('C_probe_report','boats','C_scout'),
        ('C_first_rain','continue','C_shoot'), ('C_stop_signal','continue','C_recognize'),
        ('C_reload','volley','C_second_rain'), ('C_reload','halt','C_stop_signal'),
        ('C_second_rain','continue','C_arrow_depart'), ('C_arrow_depart','continue','C_depart'),
        ('C_holdfire','watch','C_depart'), ('C_holdfire','boats','C_scout'),
    }
    assert expected <= edges
    assert len(edges) == 33


def test_prior_version_scenes_actions_and_states_match_backup():
    backup = Path(__file__).resolve().parent / 'fixtures/pre_v16_story.py'
    spec = importlib.util.spec_from_file_location('pre_v16_story', backup)
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    seen = set()
    def visit(s):
        key = repr(sorted(s.items()))
        if key in seen:
            return
        seen.add(key)
        assert story.scene(s) == old.scene(s)
        assert story.response_choices(s) == old.response_choices(s)
        if s['node'] == 'done':
            assert story.ending_outcome(s) == old.ending_outcome(s)
        for a in old.scene(s)['actions']:
            p = old.operation_payload(s,a['id'])
            assert story.operation_payload(s,a['id']) == p
            result = story.step(s,a['id'],p)
            assert result == old.step(s,a['id'],p)
            visit(result)
    for version in [None,'V1.0','V1.2','V1.3','V1.4','V1.5']:
        for role in ['L','Z','C']:
            for scenario in ['mist','quiet','scout','clear']:
                s = start(role,scenario=scenario,version=version)
                assert s == old.initial(role,scenario,version)
                visit(s)


@pytest.mark.parametrize('scenario', ['mist','quiet','scout','clear'])
def test_probe_hold_full_route_title_reports_missed_probe_not_unfired_bows(scenario):
    s=start('C',scenario=scenario)
    for choice in ['observe','shoot','probe','hold','watch']:
        s=go(s,choice)
    s,nodes=finish(s)
    out=story.ending_outcome(s)
    assert s['ending']=='E1' and s['yield']==0
    assert {'landing','muster','unload','arrow_tally'} <= set(nodes)
    assert out['title']=='远箭入水，未再齐发'
    assert story.scene(s)['outcome']['title']==out['title']
    assert '落水' in out['summary'] and '停弓' in out['summary']
    assert '弓未开' not in str(story.scene(s))


def test_v15_no_shot_title_remains_on_its_original_full_route():
    s=start('C',version='V1.5')
    for choice in ['observe','hold','stay']:
        s=go(s,choice)
    s,_=finish(s)
    assert story.ending_outcome(s)['title']=='弓未开，寨未失'


@pytest.mark.parametrize('path,node', [
    (['observe','shoot'],'C_draw_bows'),
    (['observe','shoot','probe'],'C_probe_report'),
    (['observe','shoot','mass'],'C_first_rain'),
    (['observe','shoot','mass','continue','stop'],'C_stop_signal'),
    (['observe','shoot','mass','continue','continue'],'C_reload'),
    (['observe','shoot','mass','continue','continue','volley'],'C_second_rain'),
    (['observe','shoot','mass','continue','continue','volley','continue'],'C_arrow_depart'),
    (['observe','shoot','probe','hold'],'C_holdfire'),
])
def test_clear_north_stage_stays_moonlit_through_legal_route_and_ending(path,node):
    s=start('C',scenario='clear')
    for choice in path:
        s=go(s,choice)
    assert s['node']==node and s['weather']=='clear'
    v=story.scene(s)
    assert '雾' not in v['stage_description']
    assert '月光' in v['stage_description']
    assert v['weather']=='clear' and v['art']=='v16/'+node
    s,_=finish(s)
    assert s['weather']=='clear' and s['ending'] in {'E1','E2','E3','E4'}


@pytest.mark.parametrize('scenario', ['mist', 'clear'])
def test_v16_spoken_orders_respect_weather_drums_and_prior_knowledge(scenario):
    draw = str(story.scene(start('C', 'C_draw_bows', scenario=scenario))['lines'])
    stop = str(story.scene(start('C', 'C_stop_signal', scenario=scenario))['lines'])
    rain = str(story.scene(start('C', 'C_second_rain', scenario=scenario))['lines'])
    assert '来船来意不明' in draw and '不露声息' not in draw
    assert '前哨盯住它们转船' in stop and '守紧水门' in stop
    assert '人影挨箭也不倒' not in stop and '给我看清楚' not in stop
    assert '箭越过江面' in rain and '江雾' not in rain
