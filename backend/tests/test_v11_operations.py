import pytest
from app.v1_story import initial, step, OperationError, operation_payload

def test_late_signal_does_not_waive_physical_turn_requirement():
    s=initial('L');s.update(node='side_check',contact=True,**{'yield':50000})
    with pytest.raises(OperationError,match='船头还没有转过去'):
        step(s,'turn',{'position':0,'signal_order':['前船','后船','领船']})
    result=step(s,'turn',operation_payload(s))
    assert result['turned'] and result['node']=='second' and result['yield']==100000

def test_return_heading_keeps_fleet_out_of_fort():
    s=initial('Z');s.update(node='second',contact=True,turned=True,**{'yield':100000})
    with pytest.raises(OperationError):step(s,'return',{'position':100})
    assert step(s,'return',{'position':0})['node']=='return'
