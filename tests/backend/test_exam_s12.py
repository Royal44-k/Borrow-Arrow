"""S1.2 content, versioning, validation and private-reference boundaries."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app import exam


def correct_answers():
    paper = exam.teacher_exam()
    return {q['id']: copy.deepcopy(q.get('answer_key', '我会先说明眼前的变化，再交代下一步安排。')) for q in paper['items']}


def test_new_paper_has_22_items_100_points_and_required_types():
    paper = exam.public_exam()
    assert paper['id'] == 'caocuan-exam-s1.2'
    assert len(paper['items']) == 22
    assert sum(q['points'] for q in paper['items']) == 100
    assert {q['type'] for q in paper['items']} == {'single', 'multi', 'fill', 'order', 'match', 'short', 'essay', 'reflection'}
    counts = {t: sum(q['type'] == t for q in paper['items']) for t in {q['type'] for q in paper['items']}}
    assert counts == {'single': 8, 'multi': 2, 'fill': 4, 'order': 1, 'match': 1, 'short': 4, 'essay': 1, 'reflection': 1}


def test_public_paper_never_returns_answers_private_rubrics_or_source_interpretations():
    forbidden = {'answer_key', 'accepted_answers', 'answer_example', 'rubric', 'rubric_criteria', 'score_rule', 'source_refs', 'teacher_note'}
    for item in exam.public_exam()['items']:
        assert not forbidden.intersection(item)
    paper = exam.public_exam()
    paper['items'][0]['prompt'] = 'mutated'
    assert exam.public_exam()['items'][0]['prompt'] != 'mutated'


def test_objective_reference_is_52_and_subjective_rubrics_48():
    scores = exam.validate_and_score(correct_answers())
    assert sum(v for v in scores.values() if v is not None) == 52
    assert [k for k, v in scores.items() if v is None] == ['q17', 'q18', 'q19', 'q20', 'q21', 'q22']
    subjective = [q for q in exam.teacher_exam()['items'] if q['type'] in exam.SUBJECTIVE_TYPES]
    assert sum(q['points'] for q in subjective) == 48
    for q in subjective:
        assert sum(c['max_points'] for c in q['rubric_criteria']) == q['points']
        assert len({c['id'] for c in q['rubric_criteria']}) == len(q['rubric_criteria'])
    assert len(exam.objective_reference()) == 16


def test_fill_normalization_accepts_typography_without_substring_credit():
    answers = correct_answers()
    answers.update(q11=' 军令状。 ', q12='神機妙算', q13='《三国演义》', q14='４４，０００支')
    scores = exam.validate_and_score(answers)
    assert all(scores[q] == 3 for q in ['q11', 'q12', 'q13', 'q14'])
    answers['q11'] = '可能是军令状，也可能是请战书'
    assert exam.validate_and_score(answers)['q11'] == 0
    answers['q14'] = '440.00'
    assert exam.validate_and_score(answers)['q14'] == 0


def test_partial_scoring_is_explicit_and_no_extra_selection_credit():
    answers = correct_answers()
    answers['q9'] = [answers['q9'][0]]
    answers['q10'] = ['A', 'B', 'C']
    answers['q15'][0], answers['q15'][1] = answers['q15'][1], answers['q15'][0]
    left = list(answers['q16'])
    answers['q16'][left[0]], answers['q16'][left[1]] = answers['q16'][left[1]], answers['q16'][left[0]]
    scores = exam.validate_and_score(answers)
    assert scores['q9'] == 2 and scores['q10'] == 0
    assert scores['q15'] == 2 and scores['q16'] == 2


@pytest.mark.parametrize('qid,value', [('q1', True), ('q9', ['A', 'A']), ('q11', 44), ('q15', ['promise']), ('q16', {}), ('q17', '   '), ('q21', '字' * 4001), ('q22', [])])
def test_malformed_answers_fail_before_grading(qid, value):
    answers = correct_answers()
    answers[qid] = value
    with pytest.raises(ValueError):
        exam.validate_and_score(answers)


def test_unknown_version_and_unknown_items_rejected():
    with pytest.raises(ValueError):
        exam.public_exam('unknown')
    answers = correct_answers()
    answers['not-a-question'] = 'A'
    with pytest.raises(ValueError):
        exam.validate_and_score(answers)


def test_legacy_version_is_explicit_and_unchanged():
    old = exam.public_exam('caocuan-exam-s1.1')
    assert len(old['items']) == 11 and old['items'][8]['type'] == 'scenario'
    answers = {'q1':'B','q2':'A','q3':'B','q4':'C','q5':['A','B'],'q6':['A','B'],
        'q7':['promise','prepare','approach','turn','return'],
        'q8':{'zhou':'deadline','lu':'retreat','zhuge':'mislead','han':'side','cao':'identify'},
        'q9':{'spent':'0','remaining':'44000','turn':'B','report':'A'},'q10':'先撤退。','q11':'鲁肃回营说明经过。'}
    assert sum(s or 0 for s in exam.validate_and_score(answers, exam_id=old['id']).values()) == 70
    with pytest.raises(ValueError):
        exam.validate_and_score(answers)


def test_every_item_has_a_source_mapping_and_reflection_allows_different_views():
    for q in exam.teacher_exam()['items']:
        assert q['source_refs']
        assert all(r['source_id'] and r['scope'] and r['use'] for r in q['source_refs'])
    reflection = exam.teacher_exam()['items'][-1]
    assert '保留' in reflection['prompt'] and '模拟' in reflection['prompt']
    assert '不按' in reflection['rubric']
