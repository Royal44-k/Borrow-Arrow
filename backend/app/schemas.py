from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class NewSession(Input):
    role: Literal['R_LUSU', 'R_ZHUGE', 'R_CAO']
    scenario: str = Field(min_length=1, max_length=80)
    activity_mode: Literal['individual', 'group'] = 'individual'
    members: list[str] = Field(min_length=1, max_length=8)

    @field_validator('members')
    @classmethod
    def clean_members(cls, members):
        names = [name.strip() for name in members]
        if any(not name or len(name) > 30 for name in names) or len(names) != len(set(names)):
            raise ValueError('成员别名须为1至30字且不重复')
        return names


class ActionInput(Input):
    request_id: str = Field(min_length=1, max_length=100)
    expected_revision: int = Field(ge=0)
    actor_id: str = Field(min_length=1, max_length=100)
    action_id: str = Field(min_length=1, max_length=80)
    params: dict = Field(default_factory=dict)


class ExpressionInput(Input):
    actor_id: str
    text: str = Field(min_length=1, max_length=2000)
    kind: Literal['expression', 'report']
    goal_id: str | None = None


class HelpInput(Input):
    actor_id: str
    level: Literal['H1', 'H2', 'H3']


class ForkInput(Input):
    snapshot_id: str
    actor_id: str
    new_role: Literal['R_LUSU', 'R_ZHUGE', 'R_CAO']
    mode: Literal['route', 'clip']


class FeedbackInput(Input):
    actor_id: str
    goal_id: str


class FeedbackEdit(Input):
    suggestion: str = Field(min_length=1, max_length=2000)
    retry_instruction: str = Field(min_length=1, max_length=2000)


class RetryInput(Input):
    actor_id: str
    new_role: Literal['R_LUSU', 'R_ZHUGE', 'R_CAO'] | None = None


class ControlInput(Input):
    from_actor_id: str
    to_actor_id: str


class ClipCompleteInput(Input):
    actor_id: str = Field(min_length=1, max_length=100)
