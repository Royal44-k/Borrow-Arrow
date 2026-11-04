import pytest
from fastapi.testclient import TestClient
from app.main import create_app

@pytest.fixture
def client(tmp_path):
    app=create_app(database_url=f'sqlite:///{tmp_path}/course.db',platform_database_url=f'sqlite:///{tmp_path}/platform.db')
    p=app.state.platform
    p.create_account('S001','小林','student','DemoStudent123!',class_id='DEMO7',demo=True)
    p.create_account('S002','小禾','student','DemoStudent123!',class_id='DEMO7',demo=True)
    p.create_account('T001','教师','teacher','DemoTeacher123!',class_ids=['DEMO7'],demo=True)
    return TestClient(app)
def login(c,id='S001',password='DemoStudent123!'):
    r=c.post('/api/auth/login',json={'user_id':id,'password':password})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['token']}
def test_auth_idempotency_revision_and_teacher_evidence(client):
    c=client;h=login(c)
    assert c.post('/api/v1/runs',json={}).status_code==401
    r=c.post('/api/v1/runs',headers=h,json={'role':'L','scenario':'mist','members':['同伴']}).json()
    body={'request_id':'a','revision':0,'action':'explain','actor':1,'payload':{'text':'先说明退路。'}}
    a=c.post(f"/api/v1/runs/{r['id']}/actions",headers=h,json=body)
    assert a.status_code==200,a.text
    assert c.post(f"/api/v1/runs/{r['id']}/actions",headers=h,json=body).json()['revision']==1
    assert c.post(f"/api/v1/runs/{r['id']}/actions",headers=h,json={**body,'action':'load'}).status_code==409
    assert c.post(f"/api/v1/runs/{r['id']}/actions",headers=h,json={**body,'request_id':'b','action':'signals'}).status_code==409
    h2=login(c,'S002');assert c.get(f"/api/v1/runs/{r['id']}",headers=h2).status_code==403
    ht=login(c,'T001','DemoTeacher123!');detail=c.get('/api/teacher/students/S001',headers=ht)
    assert detail.status_code==200,detail.text
    d=detail.json();assert any(x['version']=='V1.0' for x in d['routes'])
    assert not any(e.get('text')=='先说明退路。' for row in d['matrix'] for e in row['evidence'])

def test_k1_fork_preserves_real_sentence_and_original_route(client):
    c=client;h=login(c);r=c.post('/api/v1/runs',headers=h,json={'role':'L'}).json();rid=r['id']
    for i,a in enumerate(['explain','signals','launch','ask']):
        r=c.post(f'/api/v1/runs/{rid}/actions',headers=h,json={'request_id':str(i),'revision':r['revision'],'action':a,'payload':{'text':'曹军来船时，先把后船带回。','signal_order':['前船','后船','领船']}}).json()
    k=next(x['index'] for x in r['snapshots'] if x['node']=='K1')
    f=c.post(f'/api/v1/runs/{rid}/fork',headers=h,json={'snapshot':k,'role':'Z'})
    assert f.status_code==200,f.text
    assert f.json()['old_question']=='曹军来船时，先把后船带回。'
    assert f.json()['scene']['role']=='Z'
    assert c.get(f'/api/v1/runs/{rid}',headers=h).json()['scene']['node']=='approach'

def test_supported_work_not_reported_as_independent_after_fork(client):
    c=client;h=login(c);r=c.post('/api/v1/runs',headers=h,json={}).json();rid=r['id']
    for i,a in enumerate(['help','explain']):
        r=c.post(f'/api/v1/runs/{rid}/actions',headers=h,json={'request_id':str(i),'revision':r['revision'],'action':a,'payload':{}}).json()
    f=c.post(f'/api/v1/runs/{rid}/fork',headers=h,json={'snapshot':1}).json()
    assert len(f['supports'])==1

def test_wrong_signal_is_saved_without_advancing_and_can_be_corrected(client):
    c=client;h=login(c);r=c.post('/api/v1/runs',headers=h,json={}).json();rid=r['id']
    r=c.post(f'/api/v1/runs/{rid}/actions',headers=h,json={'request_id':'a','revision':0,'action':'load','payload':{}}).json()
    bad={'request_id':'wrong','revision':r['revision'],'action':'signals','payload':{'signal_order':['领船','后船','前船']}}
    r=c.post(f'/api/v1/runs/{rid}/actions',headers=h,json=bad).json()
    assert r['scene']['node']=='signals' and r['revision']==2 and r['feedback']
    assert r['history'][-1]['kind']=='operation_attempt'
    assert c.post(f'/api/v1/runs/{rid}/actions',headers=h,json=bad).json()['revision']==2
    r=c.post(f'/api/v1/runs/{rid}/actions',headers=h,json={'request_id':'fixed','revision':2,'action':'signals','payload':{'signal_order':['前船','后船','领船']}}).json()
    assert r['scene']['node']=='weather' and not r['feedback']

def test_database_revision_prevents_independent_service_overwrite(client):
    from sqlalchemy.orm import Session
    from app.v1_api import V1,Run
    from fastapi import HTTPException
    import copy
    c=client;h=login(c);r=c.post('/api/v1/runs',headers=h,json={}).json()
    first=c.app.state.v1;second=V1(first.engine,first.platform)
    with Session(first.engine) as db:
        old=db.get(Run,r['id']);stale=copy.deepcopy(old.data)
    c.post(f"/api/v1/runs/{r['id']}/actions",headers=h,json={'request_id':'a','revision':0,'action':'explain','payload':{}}).raise_for_status()
    with Session(first.engine) as db,db.begin():
        row=db.get(Run,r['id']);stale['revision']=1
        with pytest.raises(HTTPException) as caught:second.save_revision(db,row,stale,0)
        assert caught.value.status_code==409
    assert c.get(f"/api/v1/runs/{r['id']}",headers=h).json()['scene']['node']=='signals'

