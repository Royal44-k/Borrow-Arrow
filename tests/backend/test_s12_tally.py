"""M12 authored tally practice uses actual route inventory, never model grading."""
import copy
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.platform import Platform
from app.s11 import NewSession, Task, Action, Help, Control, Fork
from app.s11_models import S11Route, S11Task
from app.s11_service import S11Service


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv('CAOCUAN_AI_ENABLED', '0')
    platform = Platform(f'sqlite:///{tmp_path / "auth.db"}')
    engine = create_engine(f'sqlite:///{tmp_path / "story.db"}')
    service = S11Service(engine, platform)
    user = {'user_id': 'S', 'name': '合成学生', 'role': 'student'}
    created = service.create(user, NewSession(activity_mode='group', members=['合成同伴']))
    yield service, user, created
    engine.dispose()
    platform.engine.dispose()


def at_count(env, first=52000, second=51000, spent=0, loss=0, role='Z', node='COUNT1'):
    service, user, created = env
    with Session(service.engine) as db, db.begin():
        route = db.get(S11Route, created['route_id'])
        route.node_id = node
        route.state = {**route.state, 'role': role, 'first': first, 'second': second,
                       'spent': spent, 'loss': loss, 'launched': True}
    return service.get_view(user, created['route_id'], created['token'])


def submit(env, view, payload, request_id=None, actor_id=None):
    service, user, created = env
    body = Task(task_id='M12_TALLY', payload=payload, actor_id=actor_id or view['controller_id'],
                request_id=request_id or f'tally-{view["revision"]}', expected_revision=view['revision'])
    return service.mutate(user, view['route_id'], created['token'], 'tasks', body)


def draft(total, side=None, record='tally-one'):
    result = {'record_id': record, 'status': 'draft', 'answer_total': total}
    if side is not None: result['answer_side'] = side
    return result


def test_tally_context_uses_real_ledger_and_original_side_acquisition(env):
    view = at_count(env, loss=4000)
    context = view['task_context']['M12_TALLY']
    assert {k: context[k] for k in ['first', 'second', 'spent', 'loss', 'left', 'right', 'total', 'variant']} == {
        'first': 52000, 'second': 51000, 'spent': 0, 'loss': 4000,
        'left': 51000, 'right': 48000, 'total': 99000, 'variant': 'sides'}
    assert context['progress'] == {'record_id': None, 'status': 'not_started', 'attempts': []}
    saved = submit(env, view, draft(99000, 'right'))['saved_task']['payload']
    assert saved['attempts'][0]['matches'] == {'total': True, 'side': True}


def test_return_fire_asks_only_deliverable_total_and_never_changes_inventory(env):
    service, _, created = env
    view = at_count(env, spent=8000, loss=4000)
    before = copy.deepcopy(view['visual'])
    assert view['task_context']['M12_TALLY']['variant'] == 'balance'
    result = submit(env, view, draft(91000))
    task = result['saved_task']
    assert result['visual'] == before and result['node_id'] == 'COUNT1'
    assert task['account_id'] == 'S' and task['author_name'] == '合成学生'
    assert task['payload']['attempts'][0]['matches'] == {'total': True}
    assert 'score' not in task['payload'] and 'mastery' not in str(task)
    with Session(service.engine) as db:
        state = db.get(S11Route, created['route_id']).state
        assert [state[k] for k in ['first', 'second', 'spent', 'loss']] == [52000, 51000, 8000, 4000]


def test_wrong_answer_feedback_help_and_retry_are_server_appended(env):
    service, user, created = env
    view = at_count(env)
    first = submit(env, view, draft(52000, 'left'))
    one = first['saved_task']['payload']['attempts'][0]
    assert one['answer_total'] == 52000 and one['answer_side'] == 'left'
    assert one['matches'] == {'total': False, 'side': False}
    assert one['support_ids'] == [] and one['feedback_before'] == []
    help_body = Help(request_id='help', expected_revision=first['revision'], actor_id=first['controller_id'])
    helped = service.mutate(user, first['route_id'], created['token'], 'help', help_body)
    second = submit(env, helped, draft(103000, 'right'))
    attempts = second['saved_task']['payload']['attempts']
    assert attempts[0] == one and attempts[1]['sequence'] == 2
    assert attempts[1]['support_ids'] == [helped['help']['id']]
    assert attempts[1]['feedback_before'] == [one['feedback']['id']]
    assert attempts[1]['matches'] == {'total': True, 'side': True}
    completed = submit(env, second, {'record_id': 'tally-one', 'status': 'complete'})
    assert completed['saved_task']['payload']['attempts'] == attempts
    assert completed['task_context']['M12_TALLY']['progress']['status'] == 'complete'
    assert completed['saved_task']['previous_submission_id'] == second['saved_task']['id']


def test_completion_acknowledges_feedback_without_forcing_correctness(env):
    view = at_count(env)
    with pytest.raises(HTTPException) as exc:
        submit(env, view, {'record_id': 'tally-one', 'status': 'complete'})
    assert exc.value.status_code == 422
    wrong = submit(env, view, draft(1, 'equal'))
    done = submit(env, wrong, {'record_id': 'tally-one', 'status': 'complete'})
    assert done['saved_task']['payload']['status'] == 'complete'
    assert done['saved_task']['payload']['attempts'][0]['answer_total'] == 1
    with pytest.raises(HTTPException) as exc:
        submit(env, done, draft(103000, 'right'))
    assert exc.value.status_code == 409


@pytest.mark.parametrize('invalid', [
    {'record_id': 'tally-one', 'status': 'draft', 'answer_total': True, 'answer_side': 'right'},
    {'record_id': 'tally-one', 'status': 'draft', 'answer_total': '103000', 'answer_side': 'right'},
    {'record_id': 'tally-one', 'status': 'draft', 'answer_total': -1, 'answer_side': 'right'},
    {'record_id': 'tally-one', 'status': 'draft', 'answer_total': 103000},
    {'record_id': 'tally-one', 'status': 'draft', 'answer_total': 103000, 'answer_side': 'fake'},
    {'record_id': 'tally-one', 'status': 'draft', 'answer_total': 103000, 'answer_side': []},
    {'record_id': 'tally-one', 'status': [], 'answer_total': 103000, 'answer_side': 'right'},
    {'record_id': 'tally-one', 'status': 'draft', 'answer_total': 103000, 'answer_side': 'right', 'right': True},
    {'record_id': 'tally-one', 'status': 'draft', 'answer_total': 103000, 'answer_side': 'right', 'expected': 103000},
    {'record_id': 'tally-one', 'status': 'complete', 'answer_total': 103000},
])
def test_task_rejects_invalid_answers_or_client_expected_values(env, invalid):
    view = at_count(env)
    with pytest.raises(HTTPException) as exc: submit(env, view, invalid)
    assert exc.value.status_code == 422


def test_same_request_is_idempotent_and_stale_revision_cannot_add_attempt(env):
    service, _, _ = env
    view = at_count(env)
    first = submit(env, view, draft(103000, 'right'), request_id='same')
    assert submit(env, view, draft(103000, 'right'), request_id='same') == first
    with pytest.raises(HTTPException) as exc: submit(env, view, draft(103000, 'right'), request_id='different')
    assert exc.value.status_code == 409
    with Session(service.engine) as db:
        assert len(list(db.scalars(select(S11Task)))) == 1


def test_noncontroller_and_record_takeover_are_rejected(env):
    service, user, created = env
    view = at_count(env)
    peer = view['members'][1]['id']
    with pytest.raises(HTTPException) as exc: submit(env, view, draft(103000, 'right'), actor_id=peer)
    assert exc.value.status_code == 403
    first = submit(env, view, draft(103000, 'right'))
    changed = service.mutate(user, first['route_id'], created['token'], 'control', Control(
        request_id='control', expected_revision=first['revision'], actor_id=first['controller_id'], controller_id=peer))
    assert changed['task_context']['M12_TALLY']['progress']['status'] == 'not_started'
    with pytest.raises(HTTPException) as exc: submit(env, changed, draft(103000, 'right'))
    assert exc.value.status_code == 403
    peer_answer = submit(env, changed, draft(103000, 'right', record='peer-record'))
    peer_task = peer_answer['saved_task']
    assert peer_task['account_id'] is None and peer_task['author_name'] == '合成同伴'
    assert peer_task['payload']['attempts'][0]['feedback_before'] == [first['saved_task']['payload']['attempts'][0]['feedback']['id']]


def test_count_fork_keeps_feedback_exposure_without_copying_personal_completion(env):
    service, user, created = env
    view = at_count(env)
    first = submit(env, view, draft(103000, 'right'))
    done = submit(env, first, {'record_id': 'tally-one', 'status': 'complete'})
    child = service.mutate(user, done['route_id'], created['token'], 'forks', Fork(
        request_id='fork-count', expected_revision=done['revision'], actor_id=done['controller_id'],
        snapshot_id=done['snapshots'][-1]['id']))
    assert child['task_context']['M12_TALLY']['progress']['status'] == 'not_started'
    retry = submit(env, child, draft(103000, 'right', record='child-record'))
    assert retry['saved_task']['previous_submission_id'] is None
    assert retry['saved_task']['payload']['attempts'][0]['feedback_before'] == [first['saved_task']['payload']['attempts'][0]['feedback']['id']]


def test_one_record_retains_first_attempt_and_detects_changed_inventory(env):
    service, user, created = env
    view = at_count(env)
    first = submit(env, view, draft(1, 'equal'))
    with pytest.raises(HTTPException) as exc: submit(env, first, draft(103000, 'right', record='replacement'))
    assert exc.value.status_code == 409
    with Session(service.engine) as db, db.begin():
        route = db.get(S11Route, first['route_id'])
        route.state = {**route.state, 'loss': 4000}
    fresh = service.get_view(user, first['route_id'], created['token'])
    with pytest.raises(HTTPException) as exc: submit(env, fresh, draft(99000, 'right'))
    assert exc.value.status_code == 409


def test_empty_return_and_cao_never_receive_arithmetic_task(env):
    service, user, created = env
    view = at_count(env, first=0, second=0, node='R0')
    assert view['task_context'] == {}
    result = service.mutate(user, view['route_id'], created['token'], 'actions', Action(
        request_id='empty-return', expected_revision=view['revision'], actor_id=view['controller_id'], action_id='R0.return'))
    assert result['status'] == 'ended' and result['task_context'] == {}
    cao = at_count(env, role='C')
    assert cao['task_context'] == {}
    with pytest.raises(HTTPException) as exc: submit(env, cao, draft(103000, 'right'))
    assert exc.value.status_code == 422


def test_old_count_save_can_still_leave_without_new_task(env):
    service, user, created = env
    view = at_count(env)
    result = service.mutate(user, view['route_id'], created['token'], 'actions', Action(
        request_id='old-done', expected_revision=view['revision'], actor_id=view['controller_id'], action_id='COUNT1.done'))
    assert result['status'] == 'ended' and result['visual']['net'] == 103000


def test_legal_return_fire_path_reaches_count_with_44000(env):
    service, user, _ = env
    created = service.create(user, NewSession(role='Z'))
    view = created['view']
    for action_id in ['S0.look', 'S1.straw', 'S2.both', 'S4.go', 'S8.route', 'S9.far', 'S10.drum', 'A0.other', 'A2.fire', 'H0.yes', 'R0.return']:
        view = service.mutate(user, view['route_id'], created['token'], 'actions', Action(
            request_id=action_id, expected_revision=view['revision'], actor_id=view['controller_id'], action_id=action_id))
    assert view['node_id'] == 'COUNT1'
    context = view['task_context']['M12_TALLY']
    assert (context['first'], context['second'], context['spent'], context['loss'], context['total']) == (52000, 0, 8000, 0, 44000)
