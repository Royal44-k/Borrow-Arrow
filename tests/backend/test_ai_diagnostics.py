"""Synthetic provider replies only; diagnostic persistence never contacts a model."""
import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.platform import Platform, Account, Attempt, AIRequest
from app.ai_assessment import AiRun
from app.ai_provider import ProviderReply


USAGE = {'prompt_tokens': 120, 'completion_tokens': 45, 'total_tokens': 165}
PRIVATE_BODY = 'SYNTHETIC_UNVALIDATED_RESPONSE_MUST_NOT_BE_SAVED'
PAPER = {'id': 'caocuan-exam-s1.2', 'items': [
    {'id': 'q1', 'type': 'single', 'points': 3, 'prompt': '期限？', 'answer_key': 'B'},
    {'id': 'q2', 'type': 'short', 'points': 2, 'prompt': '说明理由。',
     'rubric_criteria': [{'id': 'reason', 'title': '理由', 'max_points': 2}]},
]}


class ReplyOnlyProvider:
    def __init__(self, data):
        self.data = data

    def status(self):
        return {'enabled': True, 'configured': True, 'ready': True,
                'mode': 'test_double', 'model': 'synthetic-model', 'max_calls': 10}

    def complete(self, system, payload):
        return ProviderReply(copy.deepcopy(self.data), 'synthetic-model', dict(USAGE))


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv('CAOCUAN_AI_ENABLED', '0')
    platform = Platform(f'sqlite:///{tmp_path / "diagnostics.db"}')
    platform.create_account('S', '合成学生', 'student', 'SyntheticPassword123', 'A')
    platform.create_account('T', '合成教师', 'teacher', 'SyntheticPassword123', class_ids=['A'])
    with Session(platform.engine) as db:
        teacher = platform.user(db.get(Account, 'T'))
    source = {'expressions': [{'id': 'source-one', 'account_id': 'S', 'goal_id': 'G4',
                              'text': '请先留出退路。', 'support_ids': []}]}
    platform.s11 = SimpleNamespace(student_evidence=lambda _: source)
    with platform.transaction() as db:
        db.add(Attempt(id='attempt', user_id='S', request_id='submit', fingerprint='f',
                       exam_id=PAPER['id'], exam_snapshot=copy.deepcopy(PAPER),
                       answers={'q1': 'B', 'q2': '先留出退路。'}, item_scores={'q1': 3, 'q2': None},
                       status='pending_review'))
        db.add(AiRun(id='historical-invalid', teacher_id='T', student_id='S', target_id='S',
                     kind='analysis', request_id='old', input_hash='old', status='invalid_response',
                     mode='test_double', model='synthetic-model', result={},
                     error_code='schema_or_evidence_invalid', usage={}, provider_attempted=True,
                     created_at='2020-01-01T00:00:00+00:00', finished_at='2020-01-01T00:01:00+00:00'))
    yield platform, teacher, source
    platform.engine.dispose()


def analysis_reply():
    return {'summary': PRIVATE_BODY, 'goals': [
        {'goal_id': goal, 'status': 'insufficient', 'observation': '尚缺本人相关作品。',
         'evidence_ids': [], 'support_condition': 'insufficient', 'next_step': '再写一个具体安排。'}
        for goal in ['G1', 'G2', 'G3', 'G4', 'G5']]}


def assert_failed_diagnostic(platform, result, category):
    assert result['status'] == 'invalid_response'
    assert result['error_code'] == category
    assert result['usage'] == USAGE
    assert result['result'] == {}
    assert PRIVATE_BODY not in str(result)
    with Session(platform.engine) as db:
        saved = db.get(AiRun, result['id'])
        assert saved.error_code == category and saved.usage == USAGE and saved.result == {}
        old = db.get(AiRun, 'historical-invalid')
        assert old.error_code == 'schema_or_evidence_invalid' and old.usage == {} and old.result == {}


@pytest.mark.parametrize('case,category', [
    ('unknown_evidence', 'evidence_ids'), ('too_many_evidence', 'evidence_ids'),
    ('duplicate_evidence', 'evidence_ids'), ('insufficient_condition', 'inconsistent_condition'),
    ('invented_help', 'invented_help'), ('hidden_help', 'assisted_claimed_independent'),
    ('long_summary', 'invalid_text'),
])
def test_rejected_analysis_keeps_category_and_usage_without_response_body(env, case, category):
    platform, teacher, source = env
    reply = analysis_reply()
    goal = reply['goals'][3]
    if case == 'long_summary':
        reply['summary'] = PRIVATE_BODY + '字' * 1601
    elif case == 'insufficient_condition':
        goal['support_condition'] = 'independent'
    else:
        goal.update(status='observed', support_condition='independent', evidence_ids=['E001'])
        if case == 'unknown_evidence': goal['evidence_ids'] = ['E999']
        elif case == 'too_many_evidence': goal['evidence_ids'] = ['E001'] * 9
        elif case == 'duplicate_evidence': goal['evidence_ids'] = ['E001', 'E001']
        elif case == 'invented_help': goal['support_condition'] = 'assisted'
        elif case == 'hidden_help': source['expressions'][0]['support_ids'] = ['actual-help']
    platform.ai.provider = ReplyOnlyProvider(reply)
    result = platform.ai.analyse(teacher, 'S', AIRequest(request_id='new-analysis'))
    assert_failed_diagnostic(platform, result, 'schema_or_evidence_invalid:' + category)


def test_rejected_grade_keeps_usage_without_mutating_original_scores(env):
    platform, teacher, _ = env
    platform.ai.provider = ReplyOnlyProvider({
        'objective': [{'item_id': 'q1', 'score': 4, 'reason': PRIVATE_BODY}],
        'subjective_suggestions': [], 'summary': PRIVATE_BODY})
    result = platform.ai.grade(teacher, 'attempt', AIRequest(request_id='new-grade'))
    assert_failed_diagnostic(platform, result, 'schema_or_evidence_invalid:invalid_score')
    with Session(platform.engine) as db:
        attempt = db.get(Attempt, 'attempt')
        assert attempt.item_scores == {'q1': 3, 'q2': None} and attempt.status == 'pending_review'


@pytest.mark.parametrize('kind', ['grade', 'analysis'])
@pytest.mark.parametrize('error', [ValueError('SYNTHETIC_SECRET_INPUT'),
                                  ValueError('evidence_ids', 'SYNTHETIC_SECRET_INPUT'),
                                  TypeError('SYNTHETIC_SECRET_INPUT'),
                                  KeyError('SYNTHETIC_SECRET_INPUT')])
def test_unknown_validator_error_is_sanitized_but_usage_survives(env, monkeypatch, kind, error):
    platform, teacher, _ = env
    platform.ai.provider = ReplyOnlyProvider({'unvalidated_body': PRIVATE_BODY})
    def reject(*args):
        raise error
    monkeypatch.setattr('app.ai_assessment.validate_' + kind, reject)
    result = (platform.ai.grade(teacher, 'attempt', AIRequest(request_id='unknown')) if kind == 'grade'
              else platform.ai.analyse(teacher, 'S', AIRequest(request_id='unknown')))
    assert_failed_diagnostic(platform, result, 'schema_or_evidence_invalid')
    assert 'SYNTHETIC_SECRET_INPUT' not in str(result)


def test_valid_analysis_keeps_existing_success_contract(env):
    platform, teacher, _ = env
    reply = analysis_reply()
    reply['summary'] = '仅说明这次已有记录。'
    platform.ai.provider = ReplyOnlyProvider(reply)
    result = platform.ai.analyse(teacher, 'S', AIRequest(request_id='valid'))
    assert result['status'] == 'completed' and result['error_code'] is None
    assert result['usage'] == USAGE and result['result']['requires_teacher_review'] is True
