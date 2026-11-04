"""SQLite persistence. World state is private; only service projections leave the API."""
from datetime import datetime, timezone
import uuid

from sqlalchemy import JSON, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class CaseVersion(Base):
    __tablename__ = 'case_versions'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    graph_hash: Mapped[str] = mapped_column(String)
    content_hash: Mapped[str] = mapped_column(String)
    content: Mapped[dict] = mapped_column(JSON)


class SessionRecord(Base):
    __tablename__ = 'sessions'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    token_hash: Mapped[str] = mapped_column(String, unique=True)
    scenario: Mapped[str] = mapped_column(String)
    activity_mode: Mapped[str] = mapped_column(String)
    members: Mapped[list] = mapped_column(JSON)
    case_version_id: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now)


class Route(Base):
    __tablename__ = 'routes'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(String, index=True)
    parent_route_id: Mapped[str | None] = mapped_column(String, nullable=True)
    controller_id: Mapped[str] = mapped_column(String)
    state: Mapped[dict] = mapped_column(JSON)
    latest_response: Mapped[dict] = mapped_column(JSON)
    replay_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=now)


class WorldEvent(Base):
    __tablename__ = 'events'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    route_id: Mapped[str] = mapped_column(String, index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String, default=now)
    __table_args__ = (UniqueConstraint('route_id', 'sequence'),)


class ActionRequest(Base):
    __tablename__ = 'action_requests'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    route_id: Mapped[str] = mapped_column(String)
    request_id: Mapped[str] = mapped_column(String)
    fingerprint: Mapped[str] = mapped_column(String)
    response: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint('route_id', 'request_id'),)


class Snapshot(Base):
    __tablename__ = 'snapshots'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(String, index=True)
    route_id: Mapped[str] = mapped_column(String, index=True)
    state: Mapped[dict] = mapped_column(JSON)
    checkpoint_hash: Mapped[str] = mapped_column(String)
    node_id: Mapped[str] = mapped_column(String)
    actor_id: Mapped[str] = mapped_column(String)
    artifact_ids: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String, default=now)


class Moment(Base):
    __tablename__ = 'moments'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    route_id: Mapped[str] = mapped_column(String, index=True)
    snapshot_id: Mapped[str] = mapped_column(String)
    node_id: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    actor_id: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now)


class Artifact(Base):
    __tablename__ = 'artifacts'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    route_id: Mapped[str] = mapped_column(String, index=True)
    author_id: Mapped[str] = mapped_column(String)
    author_name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text)
    node_id: Mapped[str] = mapped_column(String)
    goal_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=now)


class Support(Base):
    __tablename__ = 'supports'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    route_id: Mapped[str] = mapped_column(String, index=True)
    actor_id: Mapped[str] = mapped_column(String)
    node_id: Mapped[str] = mapped_column(String)
    level: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String)
    exposure_kind: Mapped[str] = mapped_column(String, default='current')
    origin_support_id: Mapped[str | None] = mapped_column(String, nullable=True)
    origin_route_id: Mapped[str | None] = mapped_column(String, nullable=True)
    provenance_chain: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[str] = mapped_column(String, default=now)


class FeedbackTask(Base):
    __tablename__ = 'feedback_tasks'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    route_id: Mapped[str] = mapped_column(String, index=True)
    actor_id: Mapped[str] = mapped_column(String)
    goal_id: Mapped[str] = mapped_column(String)
    goal_title: Mapped[str] = mapped_column(String)
    suggestion: Mapped[str] = mapped_column(Text)
    retry_instruction: Mapped[str] = mapped_column(Text)
    snapshot_id: Mapped[str] = mapped_column(String)
    target_node_id: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    basis_artifact_ids: Mapped[list] = mapped_column(JSON)
    limitations: Mapped[list] = mapped_column(JSON)
    retry_route_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=now)


class ResourceBatch(Base):
    __tablename__ = 'resource_batches'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    route_id: Mapped[str] = mapped_column(String)
    source_event: Mapped[str] = mapped_column(String)
    data: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint('route_id', 'source_event'),)


class ResourceMovement(Base):
    __tablename__ = 'resource_movements'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    route_id: Mapped[str] = mapped_column(String)
    request_id: Mapped[str] = mapped_column(String)
    source_event: Mapped[str] = mapped_column(String)
    delta: Mapped[dict] = mapped_column(JSON)


class Observation(Base):
    __tablename__ = 'observations'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    route_id: Mapped[str] = mapped_column(String)
    recipient_role: Mapped[str] = mapped_column(String)
    content_key: Mapped[str] = mapped_column(String)
    source_event: Mapped[str] = mapped_column(String)
    __table_args__ = (UniqueConstraint('route_id', 'recipient_role', 'content_key'),)


class EndingRecord(Base):
    __tablename__ = 'endings'
    route_id: Mapped[str] = mapped_column(String, primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class AIAudit(Base):
    __tablename__ = 'ai_audits'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    route_id: Mapped[str] = mapped_column(String)
    layer: Mapped[str] = mapped_column(String)
    outcome: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=now)
