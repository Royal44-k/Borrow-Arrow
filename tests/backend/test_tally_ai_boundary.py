import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
from app.ai_assessment import build_analysis_payload

def test_unadapted_tally_is_excluded_from_model_evidence_without_losing_teacher_records():
    source={'tasks':[{'id':'t','record_id':'r','route_id':'route','actor_id':'a','account_id':'S','task_id':'M12_TALLY','revision':1,'created_at':'2026-01-01','payload':{'status':'complete','attempts':[{'answer_total':44000,'support_ids':[]}]}}]}
    payload,mapping=build_analysis_payload(source,'S',['S'])
    assert payload['evidence']==[]
    assert mapping=={}
    assert 'M12' in payload['scope']
    assert source['tasks'][0]['payload']['attempts'][0]['answer_total']==44000
