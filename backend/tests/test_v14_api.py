from test_v1_api import client,login
from app.v1_story import initial,step,operation_payload

def test_v14_original_supplement_remains_distinct_and_role_replay_preserves_it(client):
    c=client;h=login(c);state=initial('L','mist','V1.4')
    route=c.post('/api/v1/runs',headers=h,json={'role':'L','scenario':'mist','design_version':'V1.4'}).json()
    for i,a in enumerate(['explain','discuss','continue','assemble','signals','launch','ask']):
        payload=operation_payload(state,a)
        if a=='ask':payload['text']='若后船遇险，先救人还是先收箭？'
        route=c.post('/api/v1/runs/'+route['id']+'/actions',headers=h,json={'request_id':str(i),'revision':route['revision'],'action':a,'payload':payload}).json()
        state=step(state,a,payload)
    assert route['scene']['node']=='K1_reply'
    assert any(e.get('kind')=='selected_response' for e in route['history'])
    k=next(x['index'] for x in route['snapshots'] if x['node']=='K1')
    before=c.get('/api/v1/runs/'+route['id'],headers=h).json()
    preview=c.get('/api/v1/runs/'+route['id']+'/snapshots/'+str(k),headers=h).json()
    assert preview['preview'] and preview['scene']['actions']==[]
    assert c.get('/api/v1/runs/'+route['id'],headers=h).json()['revision']==before['revision']
    fork=c.post('/api/v1/runs/'+route['id']+'/fork',headers=h,json={'snapshot':k,'role':'Z'}).json()
    assert fork['old_question']=='若后船遇险，先救人还是先收箭？'
    assert fork['old_question_source']=='learner_original'
    assert fork['scene']['lines'][-1]['text']==fork['old_question']
    assert c.get('/api/v1/runs/'+route['id'],headers=h).json()['scene']['node']=='K1_reply'
    assert [x['node'] for x in fork['snapshots']]==[x['node'] for x in route['snapshots'][:k+1]]
    assert fork['history']==[] and fork['expressions']==[]
    past=c.get('/api/v1/runs/'+fork['id']+'/snapshots/'+str(k-1),headers=h).json()
    assert past['scene']['role']=='L' and past['scene']['actions']==[]
    assert past['history']==[] and past['expressions']==[]
    assert c.get('/api/v1/runs/'+fork['id'],headers=h).json()==fork


def test_v14_same_role_replay_keeps_context_without_duplicating_evidence(client):
    c=client;h=login(c);state=initial('L','mist','V1.4')
    route=c.post('/api/v1/runs',headers=h,json={'role':'L','scenario':'mist','design_version':'V1.4'}).json()
    for i,a in enumerate(['explain','discuss','continue']):
        payload=operation_payload(state,a)
        route=c.post('/api/v1/runs/'+route['id']+'/actions',headers=h,json={'request_id':str(i),'revision':route['revision'],'action':a,'payload':payload}).json()
        state=step(state,a,payload)
    child=c.post('/api/v1/runs/'+route['id']+'/fork',headers=h,json={'snapshot':2}).json()
    assert [x['node'] for x in child['snapshots']]==['prepare','prepare_discuss','prepare_reply']
    assert child['revision']==0 and child['history']==[] and child['expressions']==[]
    response=c.post('/api/v1/runs/'+child['id']+'/actions',headers=h,json={'request_id':'child','revision':0,'action':'continue','payload':{}})
    assert response.status_code==200
    advanced=response.json()
    assert advanced['scene']['node']=='assembly' and len(advanced['history'])==1
    assert advanced['history'][0]['route_id']==child['id']
    preview=c.get('/api/v1/runs/'+child['id']+'/snapshots/1',headers=h).json()
    assert preview['scene']['node']=='prepare_discuss' and preview['history']==[]
    assert c.get('/api/v1/runs/'+route['id'],headers=h).json()==route
