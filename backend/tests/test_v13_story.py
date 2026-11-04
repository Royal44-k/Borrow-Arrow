import pytest
from app.v1_story import initial,scene,step,operation_payload,OperationError

def test_v13_shore_before_count_and_muster():
 s=initial('L','mist','V1.3');s.update(node='return',contact=True,**{'yield':50000})
 assert scene(s)['interaction']!='count'
 for a,node in [('moor','landing'),('muster','muster')]:
  s=step(s,a,operation_payload(s,a));assert s['node']==node
 with pytest.raises(OperationError):step(s,'verify',{'count':20})
 s=step(s,'verify',{'muster':{'front_checked':True,'rear_checked':True,'total':20}})
 assert s['node']=='unload' and s['muster']['total']==20

def test_v13_cancel_never_returns_and_epilogues_are_distinct():
 s=initial('Z','clear','V1.3');s['node']='weather'
 s=step(s,'cancel',{});assert s['node']=='cancelled'
 assert '归航' not in scene(s)['act']
 for a in ['account','south','report','finish','next','next','finish']:
  s=step(s,a,operation_payload(s,a))
 assert s['node']=='done' and s['ending']=='E0'

def test_v13_all_edges_terminate():
 seen=set();ends=set()
 def visit(s,depth):
  assert depth<32
  key=repr(sorted(s.items()))
  if key in seen:return
  seen.add(key)
  if s['node']=='done':ends.add(s['ending']);return
  assert scene(s)['actions']
  for a in scene(s)['actions']:visit(step(s,a['id'],operation_payload(s,a['id'])),depth+1)
 for r in ['L','Z','C']:
  for p in ['mist','quiet','scout','clear']:visit(initial(r,p,'V1.3'),0)
 assert ends=={'E0','E1','E2','E3','E4'}
@pytest.mark.parametrize('muster',[{}, {'front_checked':True,'rear_checked':False,'total':20},{'front_checked':True,'rear_checked':True,'total':True},{'front_checked':True,'rear_checked':True,'total':10}])
def test_muster_cannot_be_shortcut_with_partial_or_wrong_checks(muster):
 s=initial('L','mist','V1.3');s['node']='muster'
 with pytest.raises(OperationError):step(s,'verify',{'muster':muster})

def test_cao_southern_camera_is_explicit_and_clear_full_has_no_fog():
 s=initial('C','clear','V1.3')
 for a in ['observe','shoot','continue','return']:
  s=step(s,a,operation_payload(s,a))
 assert s['node']=='return' and '镜头' in str(scene(s)['lines'])
 for a in ['moor','muster','verify','unload','south','report','finish','next','next','finish']:
  s=step(s,a,operation_payload(s,a))
 assert s['ending']=='E3' and s['node']=='done'
 assert '浓雾' not in str(scene(s)['outcome'])

def test_v13_epilogue_dialogue_has_no_methodology_exposition():
 for ending in ['E0','E1','E2','E3','E4']:
  s=initial('L','mist','V1.3');s.update(ending=ending,contact=ending!='E0',peril=ending=='E4',**{'yield':50000 if ending=='E2' else 100000 if ending=='E3' else 0})
  for node in ['epilogue_1','epilogue_2','epilogue_3']:
   s['node']=node
   text=str(scene(s)['lines'])
   assert not any(word in text for word in ['条件推演','小说叙事','实测','史籍','学习','本段','本体验','不作为','并非新增史实'])

def test_v13_cao_report_art_and_epilogue_time_are_consistent():
 s=initial('C','mist','V1.3');s.update(node='report',contact=True,peril=True,**{'yield':50000})
 assert scene(s)['art']=='v13/north-dawn'
 for ending in ['E0','E1','E2','E3','E4']:
  s.update(ending=ending,node='epilogue_1')
  text=str(scene(s)['lines'])
  assert any(word in text for word in ['晨','天光','天已亮'])
  s['node']='epilogue_2'
  text=str(scene(s)['lines'])
  assert '还有一半呢？' not in text and '三日之约，你打算如何？' not in text and '有人落水么？' not in text

def test_v13_empty_muster_does_not_show_loaded_dock():
 s=initial('L','quiet','V1.3');s.update(node='muster',contact=True)
 assert scene(s)['art']=='v13/landing-empty'
 s['yield']=50000
 assert scene(s)['art']=='v13/muster-dock'
