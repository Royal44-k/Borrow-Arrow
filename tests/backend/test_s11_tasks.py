"""Only M03/M07/M09 raw process facts, never client-provided capability scores."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from test_s11 import env,start,path


def submit(c,h,v,task_id,payload,**extra):
    body={'request_id':f'task-{v["revision"]}','expected_revision':v['revision'],'actor_id':v['controller_id'],'task_id':task_id,'payload':payload,**extra}
    return c.post('/api/s11/routes/'+v['route_id']+'/tasks',headers=h,json=body)


def passage(record='passage-1',complete=True):
    return {'record_id':record,'status':'complete' if complete else 'draft','placements':[{'sequence':1,'object_id':'loose_bundle','from':'passage','to':'right_rack','client_at':'client-clock'}],'blocked_after':False,'walked':complete}


def test_m03_task_saved_with_server_identity_and_idempotency(env):
    c,h,v,_=start(env)
    assert submit(c,h,v,'M03_PASSAGE',passage()).status_code==422
    v=path(c,h,v,['S0.look','S1.straw'])
    before=dict(v['visual']);r=submit(c,h,v,'M03_PASSAGE',passage());assert r.status_code==200,r.text
    data=r.json();task=data['saved_task']
    assert task['account_id']=='S1' and task['author_name']=='S1'
    assert task['activity_mode']=='individual' and task['created_at']!='client-clock'
    assert data['visual']==before and 'score' not in task
    assert submit(c,h,v,'M03_PASSAGE',passage()).json()==data
    review=c.get('/api/s11/routes/'+v['route_id']+'/review',headers=h).json()
    assert len(review['tasks'])==1
    teacher=c.get('/api/teacher/students/S1',headers=env[1]('T1')).json()
    assert len(teacher['s11']['tasks'])==1
    assert all(row['status']=='unobserved' for row in teacher['matrix'])


def test_task_only_three_whitelisted_contexts_and_completed_facts(env):
    c,h,v,_=start(env)
    v=path(c,h,v,['S0.look','S1.straw'])
    invalid=passage();invalid['walked']=False
    assert submit(c,h,v,'M03_PASSAGE',invalid).status_code==422
    invalid=passage();invalid['score']=100
    assert submit(c,h,v,'M03_PASSAGE',invalid).status_code==422
    assert submit(c,h,v,'INVENTED',passage()).status_code==422
    wrong={**env[1]('S2'),'X-Session-Token':h['X-Session-Token']}
    assert submit(c,wrong,v,'M03_PASSAGE',passage()).status_code==403


def test_m07_preserves_first_attempt_feedback_and_revision_history(env):
    c,h,v,_=start(env)
    v=path(c,h,v,['S0.look','S1.straw','S2.both','S4.go','S8.route','S9.far','S10.drum'])
    first={'sequence':1,'side':'right','feedback_before':[],'support_ids':[],'client_at':'first'}
    p={'record_id':'side-1','status':'draft','attempts':[first],'first_attempt':first,'feedback':[],'selected_side':'right'}
    r=submit(c,h,v,'M07_SIDE',p);assert r.status_code==200,r.text;v=r.json()
    p2={**p,'status':'complete','attempts':[first,{'sequence':3,'side':'left','feedback_before':['f1'],'support_ids':[],'client_at':'second'}],'feedback':[{'id':'f1','sequence':2,'code':'COMPARE_SIDES','source':'authored_task_feedback','client_at':'hint'}],'selected_side':'left'}
    r=submit(c,h,v,'M07_SIDE',p2);assert r.status_code==200,r.text;v=r.json()
    assert v['saved_task']['payload']['first_attempt']['side']=='right'
    review=c.get('/api/s11/routes/'+v['route_id']+'/review',headers=h).json()
    assert len(review['tasks'])==2
    assert review['tasks'][0]['payload']['attempts']==[first]
    changed={**p2,'attempts':[{**first,'side':'left'},p2['attempts'][1]],'first_attempt':{**first,'side':'left'}}
    assert submit(c,h,v,'M07_SIDE',changed).status_code==409
    duplicate=submit(c,h,v,'M07_SIDE',p2);assert duplicate.status_code==200
    assert duplicate.json()['saved_task']['id']==v['saved_task']['id']


def test_m07_rejects_future_or_invented_help_and_actor_takeover(env):
    c,h,v,_=start(env,activity_mode='group',members=['同伴'])
    v=path(c,h,v,['S0.look','S1.straw','S2.both','S4.go','S8.route','S9.far','S10.drum'])
    a={'sequence':1,'side':'right','feedback_before':['late'],'support_ids':[],'client_at':'first'}
    p={'record_id':'side-1','status':'complete','attempts':[a],'first_attempt':a,'feedback':[{'id':'late','sequence':2,'code':'LOOK_EMPTY_SIDE','source':'authored_task_feedback','client_at':'late'}],'selected_side':'right'}
    assert submit(c,h,v,'M07_SIDE',p).status_code==422
    p['feedback']=[];a['feedback_before']=[];a['support_ids']=['fake-help']
    assert submit(c,h,v,'M07_SIDE',p).status_code==422
    a['support_ids']=[]
    r=submit(c,h,v,'M07_SIDE',p);assert r.status_code==200;v=r.json()
    assert submit(c,h,v,'M07_SIDE',p,actor_id=v['members'][1]['id']).status_code==403


def test_m09_keeps_heard_sound_sources_and_own_words_without_quality_score(env):
    c,h,v,_=start(env)
    v=path(c,h,v,['S0.look','S1.armor','S2.both','S4.go','S8.route','S9.far','S10.drum','A0.turn'])
    assert v['node_id']=='S15'
    p={'record_id':'listen-1','status':'complete','heard':[{'sequence':1,'clip_id':'arrow_change','mode':'local_web_audio','client_at':'one'},{'sequence':2,'clip_id':'shore_report','mode':'text_equivalent','client_at':'two'}],'replays':{'arrow_change':1,'shore_report':1},'response':'箭声停了，岸上又喊着查看，我担心退路被截。','sound_source':'local_web_audio'}
    r=submit(c,h,v,'M09_LISTEN',p);assert r.status_code==200,r.text;v=r.json()
    task=v['saved_task'];assert task['payload']['heard'][1]['mode']=='text_equivalent'
    detail=c.get('/api/teacher/students/S1',headers=env[1]('T1')).json()
    assert detail['s11']['tasks'][0]['id']==task['id']
    owned=[e for e in detail['s11']['expressions'] if e.get('task_record_id')=='listen-1']
    assert len(owned)==1 and owned[0]['text']==p['response'] and owned[0]['goal_id']=='G3'
    assert not any(key in owned[0] for key in ['score','level','mastery'])
    revised={**p,'response':'我改为请韩伯带头收船，后船跟紧。'}
    r=submit(c,h,v,'M09_LISTEN',revised);assert r.status_code==200,r.text
    detail=c.get('/api/teacher/students/S1',headers=env[1]('T1')).json()
    owned=[e for e in detail['s11']['expressions'] if e.get('task_record_id')=='listen-1']
    assert len(owned)==2 and owned[0]['text']==p['response']
