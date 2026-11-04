from copy import deepcopy
import math
import pytest
from app.v1_story import initial, scene, step, operation_payload, OperationError, ending_outcome

COMMANDS={'advance':['short','short'],'spread':['short','long'],'recall':['long','long']}

def start(role='L',node='approach',scenario='mist'):
    s=initial(role,scenario,'V1.5');s.update(node=node,departed=True)
    return s

def go(s,choice=None,payload=None):
    choice=choice or scene(s)['actions'][0]['id']
    return step(s,choice,operation_payload(s,choice) if payload is None else payload)

def proof(command,channel='sound'):
    code=COMMANDS[command]
    return {'command':command,'channel':channel,'code':code[:], 'relays':[{'ship':ship,'code':code[:],'ack':True} for ship in ['前船','后船']]}

@pytest.mark.parametrize('role',['L','Z'])
def test_agreement_precedes_weather_without_old_signal_proof(role):
    s=start(role,'signals');s.update(assembly={'complete':True},preparation_discussed=True)
    assert scene(s)['interaction']=='none'
    assert '原创' not in str(scene(s)['lines'])
    assert go(s,'signals',{})['node']=='weather'

@pytest.mark.parametrize('role',['L','Z'])
@pytest.mark.parametrize('position,expected',[(0,'fleet_order'),(65,'fleet_order'),(66,'near_bank'),(100,'near_bank')])
def test_waterline_crossing_continues_story(role,position,expected):
    s=go(start(role),'approach',{'position':position})
    assert s['node']==expected and s['berth']==position and s['contact']

@pytest.mark.parametrize('node,role,action',[('approach','L','approach'),('C_scout','C','press')])
@pytest.mark.parametrize('position',[True,False,float('nan'),float('inf'),-1,101,'66',None])
def test_position_rejects_malformed_values(node,role,action,position):
    with pytest.raises(OperationError):go(start(role,node),action,{'position':position})

@pytest.mark.parametrize('role',['L','Z','C'])
@pytest.mark.parametrize('position',[65,66])
@pytest.mark.parametrize('command',list(COMMANDS))
@pytest.mark.parametrize('channel',['sound','light'])
def test_all_commands_channels_and_waterline_consequences(role,position,command,channel):
    s=start(role,'C_scout' if role=='C' else 'approach')
    s=go(s,'press' if role=='C' else 'approach',{'position':position})
    if s['node'] in ['near_bank','C_far_contact']:s=go(s)
    assert s['node']==('C_order' if role=='C' else 'near_order' if position>65 else 'fleet_order')
    context='north' if role=='C' else 'close' if position>65 else 'outer'
    assert scene(s)['interaction']=='nav_signal' and scene(s)['signal_context']==context
    result=go(s,command,{'nav_signal':proof(command,channel)})
    expected=({'advance':'C_contact','spread':'C_flank','recall':'C_holdline'} if role=='C' else {'advance':'exposed','spread':'gap_escape','recall':'close_withdraw'} if position>65 else {'advance':'press_channel','spread':'spread_channel','recall':'hold_channel'})[command]
    assert result['node']==expected
    assert result['nav_signal'][-1]=={'context':context,**proof(command,channel)}
    assert scene(result)['nav_signal']==result['nav_signal']
    assert result['drum_started']==(role=='C' or (channel=='sound' and command!='recall'))
    if context=='close':
        assert ('金声' if channel=='sound' and command=='recall' else '鼓金' if channel=='sound' else '灯影') in str(scene(result)['lines'])

@pytest.mark.parametrize('node,role',[('fleet_order','L'),('near_order','Z'),('C_order','C')])
def test_signal_validation_rejects_forgery_without_mutating_state(node,role):
    s=start(role,node);before=deepcopy(s);valid=proof('advance')
    malformed=[None,[],{}, {k:v for k,v in valid.items() if k!='code'}, {**valid,'command':'spread'}, {**valid,'channel':'voice'}, {**valid,'code':['short']}, {**valid,'code':['short','long']}, {**valid,'code':[True,True]}, {**valid,'extra':True}, {**valid,'relays':valid['relays'][::-1]}, {**valid,'relays':[valid['relays'][0]]}, {**valid,'relays':valid['relays']*2}]
    for key,value in [('ship','前船'),('ack',1),('ack',False),('code',['long','long'])]:
        relays=deepcopy(valid['relays']);relays[1][key]=value;malformed.append({**valid,'relays':relays})
    malformed.extend([{**valid,'relays':[None,valid['relays'][1]]},{**valid,'relays':[valid['relays'][0],{'ship':'后船','ack':True}]}])
    for item in malformed:
        with pytest.raises(OperationError):go(s,'advance',{'nav_signal':item})
        assert s==before
    with pytest.raises(OperationError):go(s,'advance',{})
    assert go(s,'advance')['node'] in ['press_channel','exposed','C_contact']

@pytest.mark.parametrize('role',['L','Z'])
def test_near_rescue_is_a_real_maneuver_and_preserves_zero_tally(role):
    s=go(start(role),'approach',{'position':66});s=go(s);s=go(s,'advance',{'nav_signal':proof('advance','light')})
    s=go(s,'bluff');assert s['node']=='caught_tail' and scene(s)['interaction']=='rescue'
    with pytest.raises(OperationError):go(s,'rescue',{'position':20,'river_x':5})
    s=go(s,'rescue');assert s['node']=='return' and s['peril'] and not s['drum_started']
    nodes=[]
    while s['node']!='done':
        nodes.append(s['node']);v=scene(s)
        if s['node']=='arrow_tally':assert v['tally']=={'right':0,'left':0,'total':0}
        assert '鼓声' not in str(v['lines'])
        s=go(s)
    assert 'arrow_tally' in nodes and s['ending']=='E4'
    assert '进舟' in ending_outcome(s)['summary'] and '近寨' in str(ending_outcome(s))

@pytest.mark.parametrize('command',['advance','spread','recall'])
def test_northern_departure_explains_actual_order(command):
    s=go(start('C','C_order'),command,{'nav_signal':proof(command,'light')})
    if command=='spread':
        s=go(s);assert s['node']=='C_regroup';assert '收拢' in str(scene(s)['lines'])
    s=go(s);assert s['node']=='C_depart'
    assert {'advance':'草把','spread':'收拢','recall':'回寨'}[command] in str(scene(s)['lines'])


def test_every_finite_route_terminates_with_at_most_one_signal_station():
    endings=set();orders=set()
    def visit(s,path,signals):
        v=scene(s);assert s['node'] not in path;assert len(path)<48
        signals+=int(v['interaction']=='nav_signal');assert signals<=1
        if s['node']=='done':endings.add(s['ending']);return
        for a in v['actions']:
            payloads=[operation_payload(s,a['id'])]
            if s['node']=='approach' or (s['node']=='C_scout' and a['id']=='press'):payloads=[{**payloads[0],'position':x} for x in [65,66]]
            if v['interaction']=='nav_signal':
                orders.add((s['role'],s['node'],a['id']))
                payloads=[{'nav_signal':proof(a['id'],c)} for c in ['sound','light']]
            for p in payloads:visit(go(s,a['id'],p),path+[s['node']],signals)
    for role in ['L','Z','C']:
        for scenario in ['mist','quiet','scout','clear']:visit(initial(role,scenario,'V1.5'),[],0)
    assert endings=={'E0','E1','E2','E3','E4'} and len(orders)==15


def test_older_waterline_and_signal_contract_is_unchanged():
    for version in ['V1.2','V1.3','V1.4']:
        s=initial('L','mist',version);s['node']='approach'
        with pytest.raises(OperationError):go(s,'approach',{'position':66})
        s['node']='signals';s.update(assembly={'complete':True},preparation_discussed=True)
        assert scene(s)['interaction']=='signals'

@pytest.mark.parametrize('scenario',['mist','quiet','scout','clear'])
@pytest.mark.parametrize('node,choice',[('press_channel','continue'),('spread_channel','continue'),('hold_channel','probe'),('gap_escape','probe')])
def test_outer_reprobe_reaches_the_authored_challenge(scenario,node,choice):
    assert go(start('L',node,scenario),choice)['node']=='challenge'

@pytest.mark.parametrize('channel',['sound','light'])
def test_latest_outcome_remains_in_close_branch_afterword(channel):
    s=go(start('Z','near_order'),'spread',{'nav_signal':proof('spread',channel)})
    s=go(s,'probe');s=go(s);s=go(s,'withdraw')
    if s['node']=='disagree':s=go(s,'insist')
    while s['node']!='done':s=go(s)
    text=ending_outcome(s)['summary']
    assert '分队' in text and '近寨' in text and '50000' in text
    assert s['drum_started']


def test_sound_order_does_not_make_near_probe_repeat_drum_station():
    s=go(start('L','near_order'),'advance',{'nav_signal':proof('advance','sound')})
    assert s['drum_started']
    s=go(s,'withdraw')
    texts=[]
    while s['node']!='done':
        texts.append(str(scene(s)['lines']));s=go(s)
    assert '未曾擂鼓' not in ''.join(texts)


def test_reprobe_then_scout_rescue_keeps_both_actual_causes():
    s=start('L','near_order','scout');s=go(s,'spread',{'nav_signal':proof('spread','light')})
    s=go(s,'probe');s=go(s);s=go(s,'rescue')
    while s['node']!='done':s=go(s)
    assert '间隙' in ending_outcome(s)['summary'] and '接应末船' in ending_outcome(s)['summary']

@pytest.mark.parametrize('position',[65,66])
def test_original_north_recall_does_not_force_a_second_decision(position):
    s=go(start('C','C_scout'),'recall',{'position':position})
    assert s['node']=='C_depart' and s['nav_signal']==[]
    assert '回寨' in str(scene(s)['lines'])
    while s['node']!='done':s=go(s)
    assert '收回' in ending_outcome(s)['summary']

@pytest.mark.parametrize('role',['L','Z'])
def test_gong_only_recall_never_invents_drums_or_lamp_only_passage(role):
    s=go(start(role,'near_order'),'recall',{'nav_signal':proof('recall','sound')})
    assert not s['drum_started']
    assert '金声' in str(scene(s)['lines'])
    s=go(s)
    while s['node']!='done':
        text=str(scene(s)['lines'])
        assert '只用灯号' not in text and '依灯号' not in text
        s=go(s)
    summary=ending_outcome(s)['summary']
    assert '金声' in summary and '未曾擂鼓' in summary and '依灯号' not in summary

@pytest.mark.parametrize('node,role',[('signals','L'),('approach','Z'),('C_scout','C'),('fleet_order','Z'),('near_order','L'),('C_order','C')])
def test_in_story_copy_does_not_expose_implementation_instructions(node,role):
    v=scene(start(role,node));text=str(v['lines'])+v['prompt']+v['guide_text']
    assert all(term not in text for term in ['本课','原创','汉代真实编码','0—100','合法位置','都会继续','交互'])


def test_spoken_lines_are_unique_to_their_voice_actor_across_all_routes():
    actors={};collisions=[];visited=set()
    def visit(s):
        key=repr(sorted(s.items()))
        if key in visited:return
        visited.add(key);v=scene(s)
        for item in v['lines']:
            text=item['text'];speaker=item['speaker']
            if text in actors and actors[text]!=speaker:collisions.append((text,actors[text],speaker))
            actors[text]=speaker
        for a in v['actions']:
            payloads=[operation_payload(s,a['id'])]
            if s['node'] in ['approach','C_scout']:payloads=[{**payloads[0],'position':value} for value in [65,66]]
            if v['interaction']=='nav_signal':payloads=[{'nav_signal':proof(a['id'],channel)} for channel in ['sound','light']]
            for p in payloads:visit(go(s,a['id'],p))
    for role in ['L','Z','C']:
        for scenario in ['mist','quiet','scout','clear']:visit(initial(role,scenario,'V1.5'))
    assert not collisions, collisions[:8]


def test_full_tally_ending_does_not_invent_unfinished_arrow_obligation():
    s=start('L','fleet_order');s=go(s,'advance');s=go(s);s=go(s);s=go(s,'turn')
    texts={}
    while s['node']!='done':
        texts[s['node']]=str(scene(s)['lines']);s=go(s)
    assert s['ending']=='E3' and s['yield']==100000
    assert '三日之约还在' not in texts['south']
    assert '余下的筹箭' not in texts['epilogue_2']
    assert '足数' in texts['south'] and '核收' in texts['epilogue_2']


def test_northern_recall_afterword_does_not_invent_contact_or_lost_lamps():
    s=initial('C','mist','V1.5')
    for a in ['observe','boats','press','recall','continue']:s=go(s,a)
    texts={}
    while s['node']!='done':
        texts[s['node']]=str(scene(s)['lines']);s=go(s)
    assert '看清的草把' not in texts['epilogue_1']
    assert '失去的灯影' not in texts['epilogue_1']
    assert '召回' in texts['epilogue_1']
