import pytest
from app.v1_story import initial, scene, step, operation_payload, OperationError


def go(s, a):
    return step(s, a, operation_payload(s, a))


@pytest.mark.parametrize('order,expected', [('explain',['prepare_discuss','prepare_reply','assembly','signals']),('load',['assembly','prepare_discuss','prepare_reply','signals'])])
def test_preparation_order(order, expected):
    s=initial('L','mist','V1.4')
    s=go(s,order)
    for node in expected:
        assert s['node']==node
        if node!='signals':s=go(s,scene(s)['actions'][0]['id'])
    assert s['assembly'] and s['preparation_discussed']


@pytest.mark.parametrize('count', [0,50000,100000])
def test_tally_follows_unload_and_requires_truth(count):
    s=initial('L','mist','V1.4');s.update(node='unload',contact=True,departed=True,**{'yield':count})
    s=go(s,'unload');assert s['node']=='arrow_tally'
    expected={'right':50000 if count else 0,'left':50000 if count==100000 else 0,'total':count}
    assert scene(s)['tally']==expected
    valid={'sample_checked':True,**expected}
    for proof in [{}, {**valid,'sample_checked':1},{**valid,'right':True},{**valid,'total':count+1},{**valid,'left':1},{**valid,'extra':1}]:
        with pytest.raises(OperationError):step(s,'verify',{'arrow_tally':proof})
    s=step(s,'verify',{'arrow_tally':valid});assert s['node']=='north' and s['arrow_tally']==valid


def test_k1_replies_to_each_concern_before_positioning():
    for role in ['L','Z']:
        s=initial(role,'mist','V1.4');s['node']='K1'
        replies=[]
        for c in scene(s)['choices']:
            t=step(s,'ask',{'utterance_id':c['id']})
            assert t['node']=='K1_reply'
            v=scene(t);assert v['interaction']=='none'
            assert any(x['speaker']==('诸葛亮' if role=='L' else '鲁肃') for x in v['lines'])
            replies.append(str(v['lines']))
            assert go(t,'continue')['node']=='approach'
        assert len(set(replies))==3


def test_v13_keeps_original_tail():
    s=initial('L','mist','V1.3');s['node']='unload'
    assert go(s,'unload')['node']=='north'


def test_cao_watches_southern_verification_without_operating():
    s=initial('C','mist','V1.4');s.update(node='muster',contact=True,departed=True,**{'yield':50000})
    assert scene(s)['interaction']=='none' and '南岸插叙' in scene(s)['act']
    s=step(s,'verify',{});assert s['node']=='unload'
    s=step(s,'unload',{});assert s['node']=='arrow_tally'
    assert scene(s)['interaction']=='none' and '韩伯' in str(scene(s)['lines'])
    assert step(s,'verify',{})['node']=='north'


def test_preparation_cannot_skip_safety_discussion_or_assembly():
    s=initial('L','mist','V1.4');s['node']='signals'
    with pytest.raises(OperationError):go(s,'signals')
    s=initial('Z','mist','V1.4');s=go(s,'load')
    with pytest.raises(OperationError):step(s,'assemble',{})


def test_v14_all_routes_terminate_without_repeated_nodes_or_shots():
    endings=set()
    def visit(s,nodes,arts):
        v=scene(s)
        assert s['node'] not in nodes
        assert v['art'] not in arts
        assert len(nodes)<40
        assert '退路' not in str(v)
        if s['node']=='done':endings.add(s['ending']);return
        for a in v['actions']:
            visit(go(s,a['id']),nodes+[s['node']],arts+[v['art']])
    for r in ['L','Z','C']:
        for scenario in ['mist','quiet','scout','clear']:visit(initial(r,scenario,'V1.4'),[],[])
    assert endings=={'E0','E1','E2','E3','E4'}


def test_delayed_turn_requires_turn_but_not_second_signal_station():
    s=initial('L','mist','V1.4');s.update(node='side_check',contact=True,**{'yield':50000})
    assert scene(s)['interaction']=='balance'
    with pytest.raises(OperationError):step(s,'turn',{'position':20})
    assert step(s,'turn',{'position':80})['node']=='second'

def test_specific_replies_address_meaning_and_z_is_acknowledged():
    concerns={'k1_retreat':['接缆','末船'],'k1_visibility':['看不真切','警戒线'],'k1_silence':['只再试一通','天亮'],'k1_reply_retreat':['后队我来','接住末船'],'k1_reply_wait':['水面先留','不能只顾等箭'],'k1_reply_check':['我来核船号','后队没齐']}
    for role in ['L','Z']:
        s=initial(role,'mist','V1.4');s['node']='K1'
        for option in scene(s)['choices']:
            v=scene(step(s,'ask',{'utterance_id':option['id']}))
            reply=v['lines'][1]
            assert reply['speaker']==('鲁肃' if role=='Z' else '诸葛亮')
            assert all(word in reply['text'] for word in concerns[option['id']])


@pytest.mark.parametrize('bad', [False, -1, 50000.0, '50000', None])
def test_tally_rejects_noninteger_or_wrong_values(bad):
    s=initial('Z','mist','V1.4');s.update(node='arrow_tally',**{'yield':50000})
    proof={'sample_checked':True,'right':bad,'left':0,'total':50000}
    with pytest.raises(OperationError):step(s,'verify',{'arrow_tally':proof})


def test_cancelled_route_never_claims_or_operates_arrow_samples():
    s=initial('Z','clear','V1.4');s['node']='weather';s=go(s,'cancel')
    visited=[]
    while s['node']!='done':
        visited.append(s['node']);s=go(s,scene(s)['actions'][0]['id'])
    assert 'arrow_tally' not in visited and 'unload' not in visited
    assert s['ending']=='E0' and s['yield']==0

def test_discussion_guide_after_loading_does_not_order_loading_again():
    s=go(initial('L','mist','V1.4'),'load');s=go(s,'assemble')
    assert s['node']=='prepare_discuss'
    assert '草把' not in scene(s)['guide_text']

@pytest.mark.parametrize('role', ['L','Z'])
def test_preparation_discussion_is_distinct_and_answers_both_opening_risks(role):
    s=initial(role,'mist','V1.4');s['node']='prepare_discuss'
    preparation=scene(s)['choices'];onsite=scene({**s,'node':'K1'})['choices']
    assert not ({x['id'] for x in preparation} & {x['id'] for x in onsite})
    assert not ({x['text'] for x in preparation} & {x['text'] for x in onsite})
    for option in preparation:
        assert option['id'].startswith('pre_')
        assert '前头究竟' not in option['text']
        reply=scene(step(s,'discuss',{'utterance_id':option['id']}))
        text=str(reply['lines'])
        assert '仍无箭' in text and '哨艇' in text and '接缆' in text
        assert option['text'] not in [x['text'] for x in reply['lines']]
        assert reply['lines'][0]['speaker']==('诸葛亮' if role=='L' else '鲁肃')


def test_preparation_responses_cover_independent_responsibility_topics():
    for role in ['L','Z']:
        s=initial(role,'mist','V1.4');s['node']='prepare_discuss'
        terms={'responsibility':'由我','shortfall':'都督','orders':'复述'}
        for option in scene(s)['choices']:
            reply=scene(step(s,'discuss',{'utterance_id':option['id']}))['lines'][0]['text']
            assert terms[option['id'].split('_')[-1]] in reply

def test_selected_answer_keeps_original_supplement_separate():
    for node,action,prefix in [('prepare_discuss','discuss','preparation'),('K1','ask','question')]:
        s=initial('L','mist','V1.4');s['node']=node;choice=scene(s)['choices'][0]
        result=step(s,action,{'utterance_id':choice['id'],'text':'我还想知道这条缆绳是否磨损。'})
        assert result[prefix+'_original']=='我还想知道这条缆绳是否磨损。'
        assert result[prefix+'_text']==choice['text']
        assert result[prefix+'_utterance']==choice['id']
        assert '磨损' not in str(scene(result)['lines'])


def test_k1_role_switch_preserves_previous_question_and_source():
    s=initial('Z','mist','V1.4');s.update(node='K1',old_question='先接最后一条船，还是先看寨门？',old_question_source='learner_original')
    spoken=scene(s)['lines'][-1]
    assert spoken['text']==s['old_question']
    assert spoken['speaker']=='鲁肃' and spoken['source']=='learner_original'
