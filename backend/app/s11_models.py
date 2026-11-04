"""S1.1 persistence is deliberately separate from legacy case-version tables."""
from sqlalchemy import String, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from .models import uid, now

class S11Base(DeclarativeBase): pass

class S11Session(S11Base):
    __tablename__='s11_sessions'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    owner_id: Mapped[str]=mapped_column(String,index=True)
    token_hash: Mapped[str]=mapped_column(String)
    members: Mapped[list]=mapped_column(JSON)
    activity_mode: Mapped[str]=mapped_column(String)
    version_hash: Mapped[str]=mapped_column(String)
    created_at: Mapped[str]=mapped_column(String,default=now)

class S11Route(S11Base):
    __tablename__='s11_routes'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    session_id: Mapped[str]=mapped_column(String,index=True)
    parent_route_id: Mapped[str|None]=mapped_column(String,nullable=True)
    controller_id: Mapped[str]=mapped_column(String)
    node_id: Mapped[str]=mapped_column(String)
    revision: Mapped[int]=mapped_column(Integer,default=0)
    state: Mapped[dict]=mapped_column(JSON)
    events: Mapped[list]=mapped_column(JSON,default=list)
    expressions: Mapped[list]=mapped_column(JSON,default=list)
    supports: Mapped[list]=mapped_column(JSON,default=list)
    old_utterances: Mapped[list]=mapped_column(JSON,default=list)
    transition: Mapped[list]=mapped_column(JSON,default=list)
    created_at: Mapped[str]=mapped_column(String,default=now)

class S11Snapshot(S11Base):
    __tablename__='s11_snapshots'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    route_id: Mapped[str]=mapped_column(String,index=True)
    node_id: Mapped[str]=mapped_column(String)
    revision: Mapped[int]=mapped_column(Integer)
    state: Mapped[dict]=mapped_column(JSON)
    event_count: Mapped[int]=mapped_column(Integer)
    expression_count: Mapped[int]=mapped_column(Integer)
    support_count: Mapped[int]=mapped_column(Integer)
    created_at: Mapped[str]=mapped_column(String,default=now)

class S11Request(S11Base):
    __tablename__='s11_requests'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    route_id: Mapped[str]=mapped_column(String)
    request_id: Mapped[str]=mapped_column(String)
    fingerprint: Mapped[str]=mapped_column(String)
    response: Mapped[dict]=mapped_column(JSON)
    __table_args__=(UniqueConstraint('route_id','request_id'),)

class S11Preset(S11Base):
    __tablename__='s11_teacher_presets'
    student_id: Mapped[str]=mapped_column(String,primary_key=True)
    teacher_id: Mapped[str]=mapped_column(String)
    role: Mapped[str]=mapped_column(String)
    scenario: Mapped[str]=mapped_column(String)
    created_at: Mapped[str]=mapped_column(String,default=now)

class S11Task(S11Base):
    __tablename__='s11_task_submissions'
    id: Mapped[str]=mapped_column(String,primary_key=True,default=uid)
    route_id: Mapped[str]=mapped_column(String,index=True)
    node_id: Mapped[str]=mapped_column(String)
    task_id: Mapped[str]=mapped_column(String)
    record_id: Mapped[str]=mapped_column(String,index=True)
    actor_id: Mapped[str]=mapped_column(String)
    account_id: Mapped[str|None]=mapped_column(String,nullable=True)
    author_name: Mapped[str]=mapped_column(String)
    activity_mode: Mapped[str]=mapped_column(String)
    revision: Mapped[int]=mapped_column(Integer)
    payload: Mapped[dict]=mapped_column(JSON)
    previous_submission_id: Mapped[str|None]=mapped_column(String,nullable=True)
    created_at: Mapped[str]=mapped_column(String,default=now)
