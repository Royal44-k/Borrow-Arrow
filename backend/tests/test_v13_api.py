from test_v12_story import api

def test_snapshot_is_read_only_and_projects_prior_history(api):
 c,h=api
 r=c.post('/api/v1/runs',headers=h,json={'design_version':'V1.3'}).json()
 rid=r['id']
 r=c.post(f'/api/v1/runs/{rid}/actions',headers=h,json={'request_id':'load','revision':0,'action':'load','payload':{'assembly':dict(port_straw=True,starboard_straw=True,cloth=True,clear_aisle=True)}}).json()
 before=c.get(f'/api/v1/runs/{rid}',headers=h).json()
 preview=c.get(f'/api/v1/runs/{rid}/snapshots/0',headers=h)
 assert preview.status_code==200
 p=preview.json();assert p['preview'] and p['scene']['node']=='prepare' and p['history']==[] and p['scene']['actions']==[]
 assert c.get(f'/api/v1/runs/{rid}',headers=h).json()==before
 assert c.get(f'/api/v1/runs/{rid}/snapshots/99',headers=h).status_code==404
 assert c.get(f'/api/v1/runs/{rid}/snapshots/0').status_code==401

def test_snapshot_hides_future_expressions_and_supports(api):
 c,h=api
 r=c.post('/api/v1/runs',headers=h,json={'design_version':'V1.3'}).json();rid=r['id']
 for action,payload in [('help',{}),('load',{'assembly':dict(port_straw=True,starboard_straw=True,cloth=True,clear_aisle=True)}),('signals',{'signal_order':['前船','后船','领船'],'signal_message':'归队'}),('launch',{}),('ask',{'text':'先接回末船，再一起回去。'})]:
  r=c.post(f'/api/v1/runs/{rid}/actions',headers=h,json={'request_id':str(r['revision']),'revision':r['revision'],'action':action,'payload':payload}).json()
 assert len(r['expressions'])==1
 p=c.get(f'/api/v1/runs/{rid}/snapshots/0',headers=h).json()
 assert p['expressions']==[] and p['supports']==[] and p['history']==[]
 idx=next(x['index'] for x in r['snapshots'] if x['node']=='K1')
 p=c.get(f'/api/v1/runs/{rid}/snapshots/{idx}',headers=h).json()
 assert p['expressions']==[] and len(p['supports'])==1
 assert c.get(f'/api/v1/runs/{rid}',headers=h).json()==r
