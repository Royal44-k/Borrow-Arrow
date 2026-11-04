import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
from app.s11_service import S11Service
from app.s11_runtime import NODES,initial,advance,render_edge
from app.s11_dialogue import scene_line,ending

def test_one_turn_keeps_sentence_boundaries_inside_turn():
    assert S11Service.lines('前头就是曹营。还往近处走吗？')==['前头就是曹营。还往近处走吗？']

def test_physical_action_does_not_copy_next_scene_dialogue():
    s=initial('Z','standard');edge=NODES['S0']['edges'][0];after=advance(edge,s)
    _,reply=render_edge(edge,s,after)
    assert S11Service.spoken_transition(reply,NODES['S0'],edge,after)==[]

def test_named_action_response_is_not_lost():
    s=initial('L','standard');edge=NODES['S4']['edges'][0];after=advance(edge,s)
    _,reply=render_edge(edge,s,after)
    beats=S11Service.spoken_transition(reply,NODES['S4'],edge,after)
    assert [b['speaker'] for b in beats]==['鲁肃','诸葛亮']

def test_revelation_is_actually_spoken_once_not_only_hidden_direction():
    s=initial('L','standard');s.update(first=52000,material='armor')
    edge=next(e for e in NODES['S15']['edges'] if e['id']=='S15.hear');after=advance(edge,s)
    _,reply=render_edge(edge,s,after)
    beats=S11Service.spoken_transition(reply,NODES['S15'],edge,after)
    report=[b for b in beats if b['speaker']=='岸上军士']
    assert len(report)==1
    assert '木撑' in report[0]['text']

def test_dawn_does_not_invent_a_scout_and_silence_does_not_establish_discovery():
    s=initial('L','clear')
    assert '来艇' not in scene_line('S17',s,NODES['S17']['speech'])
    assert '？' in scene_line('S15',s,NODES['S15']['speech'])

def test_clear_dawn_ending_without_scout_has_no_invented_boat():
    s=initial('L','clear');s.update(ending='E8')
    assert '来艇' not in ending(s)['text']
