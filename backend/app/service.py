"""Transactional application boundary around the finite, private world rules."""
from contextlib import contextmanager
import copy
import hashlib
import hmac
import json
import secrets

from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from . import rules
from .content import digest, load_content
from .language import DisabledLanguageAdapter
from .models import (Base, CaseVersion, SessionRecord, Route, WorldEvent, ActionRequest,
                     Snapshot, Moment, Artifact, Support, FeedbackTask, ResourceBatch,
                     ResourceMovement, Observation, EndingRecord, AIAudit, uid, now)


def fail(status, detail):
    raise HTTPException(status, detail)


def serial(row, fields):
    return {field: getattr(row, field) for field in fields.split()}


class Courseware:
    def __init__(self, database_url, content_dir=None):
        self.content = load_content(content_dir)
        self.language = DisabledLanguageAdapter()
        # v3 is intentionally a finite runtime. A different graph needs a reviewed runtime.
        if digest(rules.SPEC) != self.content['graph_hash']:
            raise ValueError('The content graph does not match the supported v3 runtime')
        self.engine = create_engine(database_url, connect_args={'check_same_thread': False, 'timeout': 30})
        Base.metadata.create_all(self.engine)
        self.migrate_support_provenance()
        self.case_id = self.content['graph_hash'] + ':' + self.content['content_hash']
        with self.transaction() as db:
            if not db.get(CaseVersion, self.case_id):
                db.add(CaseVersion(id=self.case_id, graph_hash=self.content['graph_hash'],
                                   content_hash=self.content['content_hash'], content=self.content))

    def migrate_support_provenance(self):
        """Additive migration preserves existing local records without inventing history."""
        columns = {column['name'] for column in inspect(self.engine).get_columns('supports')}
        additions = {
            'exposure_kind': "VARCHAR NOT NULL DEFAULT 'current'",
            'origin_support_id': 'VARCHAR', 'origin_route_id': 'VARCHAR',
            'provenance_chain': "JSON NOT NULL DEFAULT '[]'",
        }
        missing = set(additions) - columns
        if not missing:
            return
        with self.engine.begin() as connection:
            for name, definition in additions.items():
                if name in missing:
                    connection.execute(text(f'ALTER TABLE supports ADD COLUMN {name} {definition}'))
            for row in connection.execute(text('SELECT id, route_id, source FROM supports')).mappings():
                historical = ':inherited_exposure' in row['source']
                # Older inherited copies did not retain source IDs; mark unknown explicitly.
                connection.execute(text('UPDATE supports SET exposure_kind=:kind, origin_support_id=:origin, origin_route_id=:route, provenance_chain=:chain WHERE id=:id'), {
                    'id': row['id'], 'kind': 'historical' if historical else 'current',
                    'origin': None if historical else row['id'], 'route': None if historical else row['route_id'],
                    'chain': json.dumps([{'support_id': row['id'], 'route_id': row['route_id']}]),
                })

    @contextmanager
    def transaction(self):
        with Session(self.engine, expire_on_commit=False) as db:
            try:
                # Serialize SQLite writers before checking revision/idempotency. A double
                # click cannot pass the check concurrently and credit the same batch twice.
                db.execute(text('BEGIN IMMEDIATE'))
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    def presentation(self, db, session):
        case = db.get(CaseVersion, session.case_version_id)
        if not case or case.graph_hash != self.content['graph_hash']:
            fail(409, '此存档绑定的规则版本未加载。')
        return case.content['presentation']

    def session(self, db, session_id, token):
        record = db.get(SessionRecord, session_id)
        if record is None:
            fail(404, '会话不存在。')
        hashed = hashlib.sha256((token or '').encode()).hexdigest()
        if not token or not hmac.compare_digest(record.token_hash, hashed):
            fail(403, '此会话需要有效的本地会话令牌。')
        return record

    def authorized(self, db, route_id, token):
        route = db.get(Route, route_id)
        if route is None:
            fail(404, '路线不存在。')
        return route, self.session(db, route.session_id, token)

    def member(self, session, actor_id):
        for member in session.members:
            if member['id'] == actor_id:
                return member
        fail(403, '提交者不属于本地会话。')

    def rows(self, db, model, route_id):
        return list(db.scalars(select(model).where(model.route_id == route_id).order_by(model.created_at, model.id)))

    def artifacts(self, db, route_id):
        return [serial(a, 'id author_id author_name kind text node_id goal_id created_at route_id') for a in self.rows(db, Artifact, route_id)]

    def supports(self, db, route_id, actor_id=None):
        route = db.get(Route, route_id)
        session = db.get(SessionRecord, route.session_id)
        names = {member['id']: member['name'] for member in session.members}
        result = []
        for support in self.rows(db, Support, route_id):
            if actor_id is not None and support.actor_id != actor_id:
                continue
            item = serial(support, 'id level text node_id actor_id source created_at exposure_kind origin_support_id origin_route_id provenance_chain')
            item['actor_name'] = names.get(support.actor_id, '本地成员')
            item['provenance_complete'] = bool(support.origin_support_id and support.origin_route_id)
            result.append(item)
        return result

    def task_view(self, db, task):
        result = serial(task, 'id route_id actor_id goal_id goal_title suggestion retry_instruction snapshot_id target_node_id status source basis_artifact_ids retry_route_id limitations')
        route = db.get(Route, task.route_id)
        session = db.get(SessionRecord, route.session_id)
        result['actor_name'] = self.member(session, task.actor_id)['name']
        return result

    def snapshot(self, db, route, actor_id, node=None):
        state = copy.deepcopy(route.state)
        snapshot = Snapshot(id=uid(), session_id=route.session_id, route_id=route.id,
                            state=state, checkpoint_hash=rules.checkpoint(state),
                            node_id=node or state['node'], actor_id=actor_id,
                            artifact_ids=[a.id for a in self.rows(db, Artifact, route.id)])
        db.add(snapshot)
        db.flush()
        return snapshot

    def add_moment(self, db, route, snapshot, node, actor_id):
        db.add(Moment(id=uid(), route_id=route.id, snapshot_id=snapshot.id, node_id=node,
                      role=route.state['role'], actor_id=actor_id))

    def create_session(self, body):
        p = self.content['presentation']
        if body.scenario not in self.content['spec']['scenarios']:
            fail(422, '未知情境。')
        if body.activity_mode == 'individual' and len(body.members) != 1:
            fail(422, '个人活动只填写一位成员。')
        token = secrets.token_urlsafe(32)
        with self.transaction() as db:
            session = SessionRecord(id=uid(), token_hash=hashlib.sha256(token.encode()).hexdigest(),
                                    members=[{'id': uid(), 'name': name} for name in body.members],
                                    scenario=body.scenario, activity_mode=body.activity_mode, case_version_id=self.case_id)
            db.add(session)
            state = rules.new_state(body.role, body.scenario)
            route_id = uid()
            state.update(session_id=session.id, route_id=route_id, events=[], checkpoints=[])
            if body.role == 'R_CAO' and state['launched']:
                eid = rules.event(state, 'preset_contact', source='declared scenario prehistory')
                rules.both(state, 'audible_signal', eid)
            rules.scene(state, state['node'])
            rules.remember(state)
            route = Route(id=route_id, session_id=session.id, parent_route_id=None,
                          controller_id=session.members[0]['id'], state=state, replay_context=None,
                          latest_response={'speaker': '场记', 'text': '本路已经开始。请依据此刻所知作出安排。', 'source': 'prewritten'})
            db.add(route)
            db.flush()
            snap = self.snapshot(db, route, route.controller_id)
            self.add_moment(db, route, snap, state['node'], route.controller_id)
            self.persist_world(db, route, {}, state, 'initial', route.controller_id)
            db.flush()
            return {'session_id': session.id, 'token': token, 'view': self.view(db, route, session)}

    def available(self, state, p):
        actions = []
        for action_id in rules.available_actions(state):
            item = copy.deepcopy(p['actions'][action_id])
            item.update(item.get('role_overrides', {}).get(state['role'], {}))
            result = {'id': action_id, 'label': item['label'], 'description': item['description']}
            choices = item.get('choices', [])
            if action_id == 'A_EVADE':
                choices = [c for c in choices if c.get('params', {}).get('mode') != 'contain' or (
                    state['actual_danger'] and state['fire'] == 'contact'
                    and rules.SPEC['scenarios'][state['scenario']].get('containable'))]
            if choices:
                result['choices'] = [{'label': c['label'], 'params': c['params']} for c in choices]
            if action_id == 'A_RETURN_FIRE' and state['role'] != 'R_CAO':
                left = rules.C['return_cost']
                batches = []
                eligible_spent = 0
                for batch in sorted(state['ledger'], key=lambda b: not b['eligible']):
                    take = min(left, batch['remaining'])
                    if take:
                        batches.append({'kind': '本次取得' if batch['eligible'] else '原有可用', 'amount': take})
                        eligible_spent += take if batch['eligible'] else 0
                    left -= take
                after = rules.inventory(state)['deliverable'] - eligible_spent
                result['preview'] = {'cost': rules.C['return_cost'], 'batches': batches, 'deliverable_after': after}
                batch_text = '、'.join(f'{batch["kind"]}{batch["amount"]}支' for batch in batches)
                result['description'] += f' 本次支出：{batch_text}，合计{rules.C["return_cost"]}支；扣除后可交付{after}支，随后如有新来箭另记新批次。'
            actions.append(result)
        return actions

    def view(self, db, route, session):
        state, role = route.state, route.state['role']
        p = self.presentation(db, session)
        data = p['scenes'][state['node']]
        role_scene = data.get('roles', {}).get(role, {})
        scene = {key: role_scene.get(key, data[key]) for key in ['title', 'act', 'location', 'stage']}
        scene.update(id=state['node'], fog=state['fog'],
                     description=role_scene.get('description', data['description']),
                     lines=copy.deepcopy(role_scene.get('lines', [])))
        projected = rules.actor_view(state, role)
        observations = [{'id': code, 'text': p['observations'].get(code, '本角色收到一条现场观察。')} for code in projected['observations']]
        # Dynamic statements are derived from actual role observations, never node labels.
        codes = set(projected['observations'])
        if state['node'] == 'N07_CEASEFIRE' and 'arrows_stopped' in codes:
            scene['lines'].append({'speaker': '现场', 'text': '此前确有来箭；现在的箭声停了。'})
        elif state['node'] == 'N07_CEASEFIRE' and 'no_arrow_response' in codes:
            scene['lines'].append({'speaker': '现场', 'text': '这一次尚未见到来箭回应。'})
        if role != 'R_CAO' and 'actual_contact' in codes:
            scene['lines'].append({'speaker': '船侧报告', 'text': '已经见到实际接触；后续安排须依据船上的当前情况。'})
        if route.replay_context and state['version'] == route.replay_context.get('fork_revision'):
            scene['lines'].append({'speaker': '鲁肃｜上一轮留下的话', 'text': route.replay_context['text']})
        members = {m['id']: m['name'] for m in session.members}
        moments = []
        for moment in self.rows(db, Moment, route.id):
            snap = db.get(Snapshot, moment.snapshot_id)
            d = p['scenes'][moment.node_id]
            moments.append({'id': moment.id, 'snapshot_id': moment.snapshot_id,
                            'node_id': moment.node_id, 'title': d.get('roles', {}).get(moment.role, {}).get('title', d['title']),
                            'summary': '已保存的片段；从此处另开一条路线。',
                            'role': moment.role, 'actor_name': members.get(moment.actor_id, '本地成员'),
                            'can_fork': bool(snap and snap.state['status'] == 'active')})
        ending = None
        if state['status'] == 'ended':
            ending = copy.deepcopy(p['endings'][state['endpoint']][role])
            ending = {k: ending[k] for k in ['title', 'description', 'lines', 'closing_shot']}
            ending['side_notes'] = []
            if role != 'R_CAO':
                inv = projected['inventory']
                ending['side_notes'].append(f"本路可交付{inv['deliverable']}支；已支出{inv['spent']}支，损失{inv['lost']}支。数量来自剧本规则。")
                if state['actual_danger']:
                    ending['side_notes'].append('本路曾有实际险情；处置后仍保留这段经历。')
            if route.parent_route_id:
                ending['side_notes'].append('本路线由快照接演，包含已继承的前史。')
        result = {'session_id': session.id, 'route_id': route.id, 'revision': state['version'],
                  'role': role, 'role_name': p['roles'][role]['name'], 'activity_mode': session.activity_mode,
                  'members': session.members, 'controller_id': route.controller_id,
                  'status': {'active': 'active', 'ended': 'completed', 'clip_complete': 'clip_complete'}[state['status']],
                  'parent_route_id': route.parent_route_id, 'scene': scene, 'observations': observations,
                  'can_complete_clip': self.can_complete_clip(db, route),
                  'inventory': projected.get('inventory'), 'actions': self.available(state, p),
                  'moments': moments, 'artifacts': self.artifacts(db, route.id),
                  'supports': self.supports(db, route.id), 'ending': ending,
                  'ai_mode': self.language.mode, 'latest_response': route.latest_response,
                  'replay_context': route.replay_context}
        # Visuals use the same persisted, role-projected facts as the narrative.
        # The camp cannot see the enemy's private prep, side labels or damage.
        if role == 'R_CAO':
            visible_decoy = 'straw' if 'outline_straw' in codes else ('armor' if 'outline_armor' in codes else None)
            visible_fire = ('contact' if 'visible_local_fire' in codes else
                            'miss' if 'no_contact_seen' in codes else
                            'light' if 'fire_light_seen' in codes else None)
            result['presentation_state'] = {'decoy': visible_decoy, 'side': None, 'fire': visible_fire, 'launched': None}
        else:
            result['presentation_state'] = {'decoy': state.get('decoy'), 'side': state['side'],
                'fire': 'light' if state['fire'] == 'launched' else state['fire'], 'launched': bool(state['launched'])}
        result['ending_code'] = state['endpoint'] if role != 'R_CAO' and state['status'] == 'ended' else None
        retry_task = db.scalar(select(FeedbackTask).where(FeedbackTask.retry_route_id == route.id))
        result['retry_task'] = None
        if retry_task:
            task = self.task_view(db, retry_task)
            result['retry_task'] = {key: task[key] for key in ['id', 'goal_id', 'goal_title', 'actor_id', 'actor_name', 'retry_instruction']}
        if role == 'R_CAO':
            result['own_arrow_batches'] = projected['own_arrow_batches']
        return result

    def can_complete_clip(self, db, route):
        if route.state.get('mode') != 'clip' or route.state['status'] != 'active':
            return False
        return db.scalar(select(Artifact.id).where(Artifact.route_id == route.id,
            Artifact.author_id == route.controller_id,
            Artifact.kind.in_(['expression', 'report'])).limit(1)) is not None

    def complete_clip(self, route_id, token, body):
        with self.transaction() as db:
            route, session = self.authorized(db, route_id, token)
            self.member(session, body.actor_id)
            if route.controller_id != body.actor_id:
                fail(403, '请由当前控制者结束自己的片段，或先明确交接。')
            if route.state.get('mode') != 'clip':
                fail(400, '这条路线不是片段接演，不能按片段完成。')
            if route.state['status'] == 'clip_complete':
                return self.view(db, route, session)
            if not self.can_complete_clip(db, route):
                fail(400, '请先在本片段留下当前控制者自己的新表达或报告。')
            old = copy.deepcopy(route.state)
            snap = self.snapshot(db, route, body.actor_id)
            new = copy.deepcopy(old)
            evidence_ids = [a.id for a in self.rows(db, Artifact, route.id)
                            if a.author_id == body.actor_id and a.kind in {'expression', 'report'}]
            rules.event(new, 'clip_complete', actor_id=body.actor_id, basis_artifact_ids=evidence_ids)
            new.update(status='clip_complete', endpoint=None, version=old['version'] + 1)
            rules.remember(new)
            route.state = new
            route.latest_response = {'speaker': '场记', 'text': '这次片段已完成，新的表达已留下。可到回看中比较本次作品；世界前史保持原样。', 'source': 'prewritten'}
            self.persist_world(db, route, old, new, 'clip-complete-' + uid(), body.actor_id)
            self.add_moment(db, route, snap, old['node'], body.actor_id)
            db.flush()
            return self.view(db, route, session)

    def persist_world(self, db, route, old, new, request_id, actor_id):
        for index, event in enumerate(new['events'][len(old.get('events', [])):], len(old.get('events', []))):
            db.add(WorldEvent(id=event['id'], route_id=route.id, sequence=index, actor_id=actor_id, payload=event))
        for role, codes in new['observations'].items():
            for code in codes:
                exists = db.scalar(select(Observation).where(Observation.route_id == route.id,
                    Observation.recipient_role == role, Observation.content_key == code))
                if not exists:
                    db.add(Observation(route_id=route.id, recipient_role=role, content_key=code,
                                       source_event=new['observation_refs'][role][code]))
        old_batches = {b['source']: b for b in old.get('ledger', [])}
        for batch in new['ledger']:
            record = db.scalar(select(ResourceBatch).where(ResourceBatch.route_id == route.id,
                                                           ResourceBatch.source_event == batch['source']))
            if record:
                record.data = copy.deepcopy(batch)
            else:
                db.add(ResourceBatch(route_id=route.id, source_event=batch['source'], data=batch))
            previous = old_batches.get(batch['source'], {})
            delta = {k: batch[k] - previous.get(k, 0) for k in ['initial', 'remaining', 'spent', 'lost']}
            if any(delta.values()):
                db.add(ResourceMovement(route_id=route.id, request_id=request_id, source_event=batch['source'], delta=delta))
        if new['status'] == 'ended':
            db.merge(EndingRecord(route_id=route.id, data={'endpoint': new['endpoint'],
                'stopping_cause': new['stop_reason'], 'inventory': rules.inventory(new),
                'known_facts': new['observations'], 'inherited_prehistory': bool(route.parent_route_id)}))

    def action(self, route_id, token, body):
        with self.transaction() as db:
            route, session = self.authorized(db, route_id, token)
            self.member(session, body.actor_id)
            fingerprint = digest(body.model_dump(exclude={'request_id'}))
            existing = db.scalar(select(ActionRequest).where(ActionRequest.route_id == route_id, ActionRequest.request_id == body.request_id))
            if existing:
                if existing.fingerprint != fingerprint:
                    fail(409, '同一请求编号已用于不同内容。')
                return existing.response
            if route.controller_id != body.actor_id:
                fail(403, '请由本幕控制者提交行动，或先明确交接。')
            if body.action_id == 'A_RESOLVE_FIRE':
                fail(403, '系统接续不能由学生提交。')
            if body.action_id not in rules.ACTIONS:
                fail(422, '未知行动。')
            allowed_keys = {'variant'} if body.action_id == 'A_SIGNAL' else ({'mode'} if body.action_id == 'A_EVADE' else ({'text', 'goal_id'} if body.action_id == 'A_SAY' else set()))
            if set(body.params) - allowed_keys:
                fail(422, '行动参数不在白名单内。')
            if body.action_id == 'A_SIGNAL':
                variant = body.params.get('variant', 'drum')
                if not isinstance(variant, str) or variant not in {'drum', 'shout', 'flag', 'quiet'}:
                    fail(422, '未知信号形式。')
            if body.action_id == 'A_SAY':
                if not isinstance(body.params.get('text'), str) or not body.params['text'].strip() or len(body.params['text']) > 2000:
                    fail(422, '请写下1至2000字的原话。')
                goal_id = body.params.get('goal_id')
                if goal_id is not None and (not isinstance(goal_id, str) or goal_id not in self.presentation(db, session)['goals']):
                    fail(422, '未知学习目标。')
            old = copy.deepcopy(route.state)
            if old['version'] != body.expected_revision:
                fail(409, '页面版本已过期，请刷新当前场景后再次选择。')
            snap = self.snapshot(db, route, body.actor_id)
            try:
                # Goal metadata belongs to the learner artifact, not the canonical
                # world's command parameters. Idempotency above still covers it.
                world_params = {k: v for k, v in body.params.items() if k != 'goal_id'}
                new = rules.apply_action(old, body.action_id, body.request_id, old['version'], world_params)
                if 'A_RESOLVE_FIRE' in rules.available_actions(new, include_system=True):
                    new = rules.apply_action(new, 'A_RESOLVE_FIRE', 'server-' + body.request_id, new['version'], {'_actor': 'system'})
                # One client command is one transaction/revision, including its automatic continuation.
                new['version'] = old['version'] + 1
                rules.remember(new)
            except (ValueError, AssertionError, TypeError) as error:
                fail(400, '此刻不能执行该行动或参数。')
            route.state = new
            p = self.presentation(db, session)
            item = copy.deepcopy(p['actions'][body.action_id])
            item.update(item.get('role_overrides', {}).get(new['role'], {}))
            response = item.get('response', {}).get(new['role'], {'speaker': '现场', 'text': '行动已记录，请查看现场变化。'})
            for choice in item.get('choices', []):
                if choice.get('params') == body.params:
                    response = choice.get('response', {}).get(new['role'], response)
            route.latest_response = {**response, 'source': 'prewritten'}
            if new['role'] == 'R_LUSU' and body.action_id in rules.STRATEGIC:
                route.latest_response = {**route.latest_response, 'speaker': '诸葛亮', 'text': '此议可行，照你方才的安排执行。' + route.latest_response['text']}
            self.persist_world(db, route, old, new, body.request_id, body.actor_id)
            seen = set()
            for event in new['events'][len(old['events']):]:
                if event['type'] == 'scene_enter' and event['node'] not in seen:
                    self.add_moment(db, route, snap, event['node'], body.actor_id)
                    seen.add(event['node'])
            # Every performed action has a recoverable pre-action anchor, including its origin scene.
            self.add_moment(db, route, snap, old['node'], body.actor_id)
            if body.action_id == 'A_SAY' and body.params.get('text'):
                member = self.member(session, body.actor_id)
                db.add(Artifact(route_id=route.id, author_id=member['id'], author_name=member['name'],
                                text=body.params['text'], kind='expression', node_id=old['node'], goal_id=body.params.get('goal_id')))
            db.flush()
            if body.action_id == 'A_SAY':
                # A separate post-expression checkpoint keeps exactly one artifact
                # while allowing the next role to answer the real previous line.
                spoken_snapshot = self.snapshot(db, route, body.actor_id)
                self.add_moment(db, route, spoken_snapshot, new['node'], body.actor_id)
            self.adapt(db, route, session, route.latest_response['text'], 'peer', actor_id=body.actor_id)
            result = self.view(db, route, session)
            db.add(ActionRequest(route_id=route_id, request_id=body.request_id, fingerprint=fingerprint, response=result))
            return result

    def expression(self, route_id, token, body):
        with self.transaction() as db:
            route, session = self.authorized(db, route_id, token)
            member = self.member(session, body.actor_id)
            if body.goal_id and body.goal_id not in self.presentation(db, session)['goals']:
                fail(422, '未知学习目标。')
            db.add(Artifact(route_id=route_id, author_id=body.actor_id, author_name=member['name'],
                            kind=body.kind, text=body.text, node_id=route.state['node'], goal_id=body.goal_id))
            route.latest_response = {'speaker': '沈砚', 'text': '这番话我记下了。接下来，你打算如何安排？', 'source': 'prewritten'}
            db.flush()
            self.adapt(db, route, session, route.latest_response['text'], 'peer', actor_id=body.actor_id)
            return self.view(db, route, session)

    def language_context(self, view, layer='peer', actor_id=None, goal_id=None):
        # Role-visible facts are separate from learning records. A help exposure is
        # not something an in-story companion automatically knows after role replay.
        context = {key: copy.deepcopy(view[key]) for key in
                   ['route_id', 'revision', 'role', 'role_name', 'scene', 'observations', 'actions']}
        if layer == 'peer':
            context['artifacts'] = [{key: artifact[key] for key in
                ['id', 'author_id', 'author_name', 'kind', 'text', 'node_id']}
                for artifact in view['artifacts'] if artifact['route_id'] == view['route_id']]
            context['artifact_scope'] = '当前路线中学习者已说出的原话；它们是角色听到的表达，不是已验证世界事实。'
            return context
        if layer not in {'learner', 'teacher'} or actor_id is None:
            raise ValueError('Learning context requires a known layer and target member')
        context['target_actor_id'] = actor_id
        artifacts = [artifact for artifact in view['artifacts'] if artifact['author_id'] == actor_id]
        supports = [support for support in view['supports'] if support['actor_id'] == actor_id]
        if layer == 'teacher':
            if goal_id is None:
                raise ValueError('Teacher context requires a target goal')
            context['goal_id'] = goal_id
            artifacts = [artifact for artifact in artifacts if artifact['goal_id'] == goal_id]
            evidence_nodes = {artifact['node_id'] for artifact in artifacts}
            supports = [support for support in supports if support['node_id'] in evidence_nodes]
            context['support_scope'] = '只含该成员在目标作品所在节点的已展示支持；节点相关不等于逐条帮助已被该作品采用。'
        else:
            context['support_scope'] = '只含请求成员本人已接触的支持；historical是此前学习经历，不是当前角色的新事实。'
        context['artifacts'] = copy.deepcopy(artifacts)
        context['supports'] = copy.deepcopy(supports)
        return context

    def adapt(self, db, route, session, fallback, layer, extra=None, actor_id=None, goal_id=None):
        context = self.language_context(self.view(db, route, session), layer, actor_id, goal_id)
        if extra:
            context.update(extra)
        rendered, source, outcome = self.language.render(context, fallback, layer)
        if self.language.enabled:
            db.add(AIAudit(route_id=route.id, layer=layer, outcome=outcome))
        if layer == 'peer':
            route.latest_response = {**route.latest_response, 'text': rendered, 'source': source}
        return rendered, source

    def recent_help_transition(self, db, route, session):
        """A completed teaching transition is context, never the current action node."""
        if route.state['status'] != 'active' or route.state['node'] != 'N12_DECIDE':
            return None
        # These are events committed by THIS route. Inherited parent events in
        # state are deliberately excluded, including after a same-role replay.
        events = [row.payload for row in db.scalars(select(WorldEvent).where(
            WorldEvent.route_id == route.id).order_by(WorldEvent.sequence))]
        latest = next((index for index in reversed(range(len(events)))
            if events[index]['type'] == 'learner_action'
            and rules.ACTIONS.get(events[index].get('action'), {}).get('effect')
                not in {'say', 'face_rusu', 'fan_signal'}), None)
        if latest is None:
            return None
        action = events[latest].get('action')
        node = {'A_TURN': 'N08_TURN', 'A_RETURN_FIRE': 'N10_RETURN_FIRE'}.get(action)
        if node is None:
            return None
        transition = next((event for event in events[latest + 1:]
            if event['type'] == 'scene_enter' and event['node'] == node
            and event.get('phase') == 'action_transition'
            and event.get('retry_action') == action and event.get('anchor_route') == route.id), None)
        if transition is None:
            return None
        for moment in reversed(self.rows(db, Moment, route.id)):
            if moment.node_id != node or moment.role != route.state['role']:
                continue
            snap = db.get(Snapshot, moment.snapshot_id)
            if not snap or snap.route_id != route.id or snap.checkpoint_hash != transition.get('retry_checkpoint'):
                continue
            if snap.checkpoint_hash != rules.checkpoint(snap.state):
                continue
            data = self.presentation(db, session)['scenes'][node]
            title = data.get('roles', {}).get(route.state['role'], {}).get('title', data['title'])
            return {'kind': 'recent_transition', 'node_id': node, 'title': title,
                    'current_node_id': route.state['node'], 'action_id': action,
                    'event_id': transition['id'], 'moment_id': moment.id,
                    'scope': '回看本路刚发生的教学片段；它不是当前可操作场景，行动仍只取context.actions。'}
        return None

    def help(self, route_id, token, body):
        with self.transaction() as db:
            route, session = self.authorized(db, route_id, token)
            self.member(session, body.actor_id)
            view = self.view(db, route, session)
            observed = view['observations'][-1]['text'] if view['observations'] else '先说明此刻画面与字幕中你实际获得的信息。'
            action_names = '、'.join(a['label'] for a in view['actions'][:3])
            templates = {
                'H1': f'先留意这一条已呈现的信息：{observed} 你能把观察和自己的猜想分开说吗？',
                'H2': f'先选一个现场变化，写出你知道什么，再说明下一步安排。当前可以考虑：{action_names or "整理本路报告"}。',
                'H3': '可改写示例：“我听到／看到……；现在还不能确认……；我打算……，因为……。”请只填入本角色确实收到的信息；示例不会自动执行行动。',
            }
            case_content = db.get(CaseVersion, session.case_version_id).content
            teaching_context = self.recent_help_transition(db, route, session)
            lesson_node = teaching_context['node_id'] if teaching_context else route.state['node']
            lesson = case_content.get('assistance', {}).get('nodes', {}).get(lesson_node, {})
            taught = {**lesson.get('source_prompts', {}), **lesson.get('role_prompts', {}).get(route.state['role'], {})}
            source_pointer = lesson.get('source_pointer', 'role_safe_fallback')
            help_data = {'text': taught.get(body.level, templates[body.level]), 'level': body.level,
                         'source': 'prewritten:' + source_pointer}
            if self.language.configured:
                extra = {'help_level': body.level}
                if teaching_context:
                    extra['teaching_context'] = teaching_context
                help_data['text'], help_data['source'] = self.adapt(db, route, session, help_data['text'], 'learner', extra, actor_id=body.actor_id)
                if teaching_context:
                    help_data['source'] += ':' + source_pointer
            if teaching_context:
                # Keep this distinction even if an optional model omits it.
                help_data['text'] = (f'回看刚才的“{teaching_context["title"]}”教学片段；'
                    f'当前可操作场景仍为“{view["scene"]["title"]}”。' + help_data['text'])
            support_id = uid()
            db.add(Support(id=support_id, route_id=route.id, actor_id=body.actor_id, node_id=route.state['node'],
                exposure_kind='current', origin_support_id=support_id, origin_route_id=route.id,
                provenance_chain=[{'support_id': support_id, 'route_id': route.id}], **help_data))
            db.flush()
            return {'help': help_data, 'view': self.view(db, route, session)}

    def control(self, route_id, token, body):
        with self.transaction() as db:
            route, session = self.authorized(db, route_id, token)
            self.member(session, body.from_actor_id)
            self.member(session, body.to_actor_id)
            if route.controller_id != body.from_actor_id:
                fail(403, '只能由本幕当前控制者交接。')
            if route.state['status'] != 'active':
                fail(400, '已完成路线不能继续交接行动。')
            old = copy.deepcopy(route.state)
            new = copy.deepcopy(old)
            rules.event(new, 'control_transfer', from_actor_id=body.from_actor_id, to_actor_id=body.to_actor_id)
            new['version'] += 1
            rules.remember(new)
            route.state, route.controller_id = new, body.to_actor_id
            self.persist_world(db, route, old, new, 'control-' + uid(), body.from_actor_id)
            db.flush()
            return self.view(db, route, session)

    def fork_in_transaction(self, db, route, session, snapshot_id, new_role, mode, actor_id):
        self.member(session, actor_id)
        snap = db.get(Snapshot, snapshot_id)
        if snap is None:
            fail(404, '快照不存在。')
        if snap.session_id != session.id:
            fail(403, '快照不属于本会话。')
        ancestor = route
        lineage = set()
        while ancestor and ancestor.id not in lineage:
            lineage.add(ancestor.id)
            ancestor = db.get(Route, ancestor.parent_route_id) if ancestor.parent_route_id else None
        if snap.route_id not in lineage or snap.checkpoint_hash != rules.checkpoint(snap.state):
            fail(403, '快照不属于本路合法祖先。')
        try:
            state = rules.fork_route(route.state, snap.state, new_role, mode)
        except ValueError:
            fail(400, '此快照在所选角色下没有合法后续，请选另一处动作前片段。')
        new = Route(id=state['route_id'], session_id=session.id, parent_route_id=route.id,
                    controller_id=actor_id, state=state, replay_context=None,
                    latest_response={'speaker': '场记', 'text': '从已走过的片段接演；前史已继承，接下来留下新的表达与安排。', 'source': 'prewritten'})
        if snap.state['role'] == 'R_LUSU' and new_role == 'R_ZHUGE':
            eligible = [a for a in self.rows(db, Artifact, snap.route_id) if a.id in snap.artifact_ids and a.kind == 'expression' and a.author_id == actor_id]
            if eligible:
                old_line = eligible[-1]
                new.replay_context = {'artifact_id': old_line.id, 'source_route_id': old_line.route_id,
                    'author_name': old_line.author_name, 'text': old_line.text, 'is_new_evidence': False,
                    'fork_revision': state['version']}
                new.latest_response = {'speaker': '鲁肃｜上一轮留下的话', 'text': old_line.text, 'source': 'prior_learner_quote'}
        db.add(new)
        db.flush()
        for support in self.rows(db, Support, route.id):
            support_id = uid()
            chain = copy.deepcopy(support.provenance_chain) or [{'support_id': support.id, 'route_id': support.route_id}]
            chain.append({'support_id': support_id, 'route_id': new.id})
            source = support.source if ':inherited_exposure' in support.source else support.source + ':inherited_exposure'
            db.add(Support(id=support_id, route_id=new.id, actor_id=support.actor_id, node_id=support.node_id,
                level=support.level, text=support.text, source=source, exposure_kind='historical',
                origin_support_id=support.origin_support_id, origin_route_id=support.origin_route_id,
                provenance_chain=chain))
        new_snap = self.snapshot(db, new, actor_id)
        self.add_moment(db, new, new_snap, state['node'], actor_id)
        # The inherited world remains in the private state; only new route events get new ownership.
        inherited = copy.deepcopy(snap.state)
        self.persist_world(db, new, inherited, state, 'fork-' + uid(), actor_id)
        db.flush()
        return new

    def fork(self, route_id, token, body):
        with self.transaction() as db:
            route, session = self.authorized(db, route_id, token)
            new = self.fork_in_transaction(db, route, session, body.snapshot_id, body.new_role, body.mode, body.actor_id)
            return self.view(db, new, session)

    def review(self, db, route, session):
        p = self.presentation(db, session)
        snapshots = []
        for snap in self.rows(db, Snapshot, route.id):
            scene_data = p['scenes'][snap.node_id]
            snapshots.append({'id': snap.id, 'node_id': snap.node_id, 'title': scene_data.get('roles', {}).get(snap.state['role'], {}).get('title', scene_data['title']),
                'role': snap.state['role'], 'revision': snap.state['version'],
                'summary': '此快照保留当时已经发生的前史，另演不会改写旧路。', 'can_fork': snap.state['status'] == 'active'})
        return {'view': self.view(db, route, session), 'snapshots': snapshots,
                'artifacts': self.artifacts(db, route.id), 'supports': self.supports(db, route.id),
                'parent_route_id': route.parent_route_id}

    def retry_plan(self, db, route, session, basis, actor_id, fallback):
        """Bind the saved teaching task to a recoverable point in this real history."""
        if route.state['status'] == 'active':
            self.snapshot(db, route, actor_id)
        snapshots = [snap for snap in self.rows(db, Snapshot, route.id)
            if snap.state['status'] == 'active'
            and snap.checkpoint_hash == rules.checkpoint(snap.state)
            and snap.checkpoint_hash in route.state['checkpoints']
            and route.state['events'][:len(snap.state['events'])] == snap.state['events']
            and rules.available_actions(snap.state)]
        if not snapshots:
            fail(409, '没有可接演的已存快照；请先保存一段有合法后续的本人过程。')
        by_id = {snap.id: snap for snap in snapshots}
        by_checkpoint = {snap.checkpoint_hash: snap for snap in snapshots}
        teaching = db.get(CaseVersion, session.case_version_id).content['teaching']
        evidence_node = basis[-1].node_id if basis else route.state['node']
        terminal = route.state.get('endpoint') if evidence_node == 'N13_CLOSE' and route.state['status'] == 'ended' else None
        lesson = next((row for row in teaching['terminals'] if row['terminal_id'] == terminal), None) if terminal else None
        if lesson is None:
            lesson = next((row for row in teaching['nodes'] if row['node_id'] == evidence_node), {})
        snap, anchor_node = None, None
        notes = []
        # A terminal about the closed window must really rewind an authored wait,
        # not merely choose a later decision scene whose window is already closed.
        if terminal == 'T8':
            for event in reversed(route.state['events']):
                candidate = by_checkpoint.get(event.get('retry_checkpoint'))
                if event.get('retry_action') in {'A_WAIT_WEATHER', 'A_WAIT_WINDOW'} and candidate and not candidate.state['window_closed']:
                    snap, anchor_node = candidate, candidate.state['node']
                    break
        else:
            moments = self.rows(db, Moment, route.id)
            for node in lesson.get('retry_node_ids', [evidence_node]):
                snap = next((item for item in reversed(snapshots) if item.state['node'] == node), None)
                if snap is None:
                    snap = next((by_id[item.snapshot_id] for item in reversed(moments)
                        if item.node_id == node and item.snapshot_id in by_id), None)
                if snap is not None:
                    anchor_node = node
                    break
        matched = snap is not None
        if not matched:
            snap = snapshots[-1]
            notes.append('教学任务的候选场景没有可接演的真实快照，已改用最近的合法保存点；未提供新条件。')
        elif anchor_node != snap.state['node']:
            notes.append('教学目标涉及过场，本次从触发该过场的动作前快照接演；目标落点按实际保存节点显示。')
        instruction = lesson.get('retry_task', fallback) if matched else '在当前角色已知信息范围内，说明一条观察、一个尚不能确认的判断和下一步允许的安排。'
        # The map describes possible classroom variants. This service replays a
        # real snapshot and does not manufacture those variants or promise an end.
        replacements = {
            '接演一条注明不同初态的天气报告': '回看该快照已有的天气报告',
            '保留同一布置，换到对方实际允许的观察位置，演一段该位置的报告；也可回本方补一处布置说明。': '依据当前角色实际所知补一处布置或观察说明；若另行明确换角，再按新角色可见范围作报告。',
            '接演“有声无影”或“有影而无新箭声”的一种新条件': '回看当前实际可见或可听的报告',
            '收到一条信息范围不同的新报告': '回看当前信息范围内已有的报告',
            '从另一个明示可见条件接演一段观察报告': '从该快照明示可见的条件接演一段观察报告',
            '换一条只有声响或仍模糊的报告': '依据当前实际收到的报告',
            '但前史或新报告不同': '以该快照实际前史为准',
            '保留同一次转向，换到曹营作一段实际可见变化的报告，再回到原方接一句。': '按当前角色可见范围说明转向前后的观察；只有合法行动实际带来转向或明确换角后，再承接相应变化。',
            '保留一次声响事件，接演对方没有按预想回应的情况': '回看该快照已有的声响与对方实际回应',
            '保留已发生回射与同一结尾，在归营报告中连接“已取得、实际用出、仍带回”；或另开完整路线改变本次决定。': '依据当前账目连接“已取得、实际用出、仍带回”；未实际回射时，只说明当前决定，不补写支出或交锋。',
            '接演一段明确仅有危险信号、尚未接触的场景': '依据该快照实际危险阶段接演一段',
            '保留同一个故事结果，给当前角色一项新的允许观察或换一个报告对象': '保留原路线结果作比较，依据当前角色已有观察或换一个报告对象',
            '换位报告或接演另一种对方回应；保留本路达成及暴露状态。': '依据当前角色已知情况作报告；原路线的结果保留为比较材料，只有明确换角或合法行动带来变化后，再承接变化。',
            '保留提前结束': '保留原路线提前结束的记录',
            '区分船方实际听见的停射和另一方私下原因': '区分本方实际听见的停射与尚不能确认的原因',
            '加入一项明示新观察接演': '若合法行动实际带来新观察，再承接变化',
            '保留未出发结尾向委托者交代；新条件接演须明示，未经历的对岸片段仍未观察。': '保留原路线未出发的记录向委托者交代；本次未提供新条件，未经历的对岸片段仍未观察。',
            '从明确等候前接演一次，比较新条件与收束': '从本路实际等候前接演一次，比较合法等候后实际出现的报告与收束',
        }
        for old, new in replacements.items():
            instruction = instruction.replace(old, new)
        if matched and anchor_node == 'N10_RETURN_FIRE' and not snap.state['return_fired']:
            instruction = '回到本次回射决定前，说明当前已取得与可支出的数量，再作一个允许的决定；只有实际回射后，才连接真实响应、实际支出与后续收束。'
        if evidence_node == 'N07_CEASEFIRE' and not snap.state.get('volleys') and not rules.inventory(snap.state)['deliverable']:
            instruction = instruction.replace('仍是停射', '当前尚无来箭回应')
        # Cao's end classification may encode boat-side causes that he cannot know.
        # The task therefore stays with his own report and known response/spending.
        if route.state['role'] == 'R_CAO':
            instruction = '回看本方已收到的报告，区分观察与推测，向本方听者说明实际安排及已知结果；涉及来箭、响应或支出时，只使用本方已有记录。'
            if terminal == 'T8' and matched:
                instruction = '从本路实际等候前接演一次，依据本方随后实际收到的报告作安排；现实操作时间不推进条件。'
        scene_data = self.presentation(db, session)['scenes'][snap.state['node']]
        title = scene_data.get('roles', {}).get(route.state['role'], {}).get('title', scene_data['title'])
        prefix = f'本次从“{title}”接演，以该快照已呈现的信息为准。'
        if not matched:
            prefix += '原候选场景没有可接演快照，本次未提供新条件。'
        return snap, prefix + instruction, notes

    def feedback(self, route_id, token, body):
        with self.transaction() as db:
            route, session = self.authorized(db, route_id, token)
            self.member(session, body.actor_id)
            p = self.presentation(db, session)
            if body.goal_id not in p['goals']:
                fail(422, '未知学习目标。')
            basis = [a for a in self.rows(db, Artifact, route.id) if a.author_id == body.actor_id and a.goal_id == body.goal_id]
            focus = {
                'G_PERSPECTIVE': ('区分本角色观察与推测', '在接演处说出一条你确知的信息，再说明一条尚不能确认的判断。'),
                'G_NARRATIVE': ('把观察、实际安排和后来结果连起来', '用两三句话交代你见到什么、实际怎样安排及后来发生了什么。'),
                'G_ADAPT_EXPRESSION': ('让表达回应刚发生的变化', '针对本角色新收到的变化，改写一句给同行或部下的说明。'),
            }.get(body.goal_id, ('说明所依据的信息', '说明你如何核对助手的一句话与当前已见信息。'))
            limitations = ['只比较归属明确的本次作品；剧情结果不等于文学能力等级。',
                           '未记录的同伴口头支持未知；没有帮助记录不证明完全独立。']
            snap, retry_instruction, retry_notes = self.retry_plan(db, route, session, basis, body.actor_id, focus[1])
            limitations.extend(retry_notes)
            if not basis:
                limitations.insert(0, '材料不足：尚无此成员面向该目标的本人作品，不能以通关或事件替代。')
            suggestion = (f'你在“{p["scenes"][basis[-1].node_id]["title"]}”留下了作品。下一次请' if basis else '当前个人作品材料不足。先留下自己的表达，再尝试') + focus[0] + '。'
            source = 'prewritten_design_suggestion'
            if self.language.configured and basis:
                retry_scene = p['scenes'][snap.state['node']]
                retry_title = retry_scene.get('roles', {}).get(route.state['role'], {}).get('title', retry_scene['title'])
                suggestion, source = self.adapt(db, route, session, suggestion, 'teacher',
                    {'goal_title': p['goals'][body.goal_id]['title'], 'basis_artifacts': [serial(a, 'id text node_id goal_id author_id') for a in basis],
                     'retry_instruction': retry_instruction, 'retry_target_node_id': snap.state['node'],
                     'retry_target_title': retry_title, 'limitations': limitations},
                    actor_id=body.actor_id, goal_id=body.goal_id)
            task = FeedbackTask(id=uid(), route_id=route.id, actor_id=body.actor_id, goal_id=body.goal_id,
                goal_title=p['goals'][body.goal_id]['title'], suggestion=suggestion, retry_instruction=retry_instruction,
                snapshot_id=snap.id, target_node_id=snap.state['node'], status='proposed', source=source,
                basis_artifact_ids=[a.id for a in basis], limitations=limitations, retry_route_id=None)
            db.add(task)
            db.flush()
            return self.task_view(db, task)

    def authorized_task(self, db, task_id, token):
        task = db.get(FeedbackTask, task_id)
        if task is None:
            fail(404, '反馈任务不存在。')
        route, session = self.authorized(db, task.route_id, token)
        return task, route, session

    def edit_feedback(self, task_id, token, body):
        with self.transaction() as db:
            task, _, _ = self.authorized_task(db, task_id, token)
            task.suggestion, task.retry_instruction = body.suggestion, body.retry_instruction
            task.source = 'local_edit'
            db.flush()
            return self.task_view(db, task)

    def retry(self, task_id, token, body):
        with self.transaction() as db:
            task, route, session = self.authorized_task(db, task_id, token)
            if body.actor_id != task.actor_id:
                fail(403, '此任务须由原归属成员提交新的尝试。')
            if task.retry_route_id:
                return self.view(db, db.get(Route, task.retry_route_id), session)
            new = self.fork_in_transaction(db, route, session, task.snapshot_id,
                body.new_role or route.state['role'], 'route', body.actor_id)
            task.retry_route_id, task.status = new.id, 'attempt_started'
            db.flush()
            return self.view(db, new, session)

    def comparison(self, db, task, route, session):
        before = [a for a in self.artifacts(db, route.id) if a['id'] in task.basis_artifact_ids]
        after = [] if not task.retry_route_id else [a for a in self.artifacts(db, task.retry_route_id)
            if a['author_id'] == task.actor_id and a['goal_id'] == task.goal_id]
        status = 'awaiting_attempt' if not task.retry_route_id else ('ready' if after else 'awaiting_new_evidence')
        note = '比较同一目标的本人作品；此处呈现材料，不自动计算能力进步。再演已经知道前史，帮助和视角条件可能改变。'
        if not before:
            note += '首次个人作品材料不足，不能得出前后提高结论。'
        return {'before': before, 'after': after, 'supports_before': self.supports(db, route.id, task.actor_id),
                'supports_after': self.supports(db, task.retry_route_id, task.actor_id) if task.retry_route_id else [],
                'status': status, 'note': note}
