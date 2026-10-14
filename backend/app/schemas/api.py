from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class HealthResponse(BaseModel):
    status: str
    app: str
    timezone: str
    provider_mode: str
    llm_configured: bool


class CalendarEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    start_time: datetime
    end_time: datetime
    description: Optional[str] = None
    is_fixed: bool = False
    task_id: Optional[int] = None

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class CalendarEventUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    description: Optional[str] = None

    @model_validator(mode="after")
    def validate_range(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class CalendarEventOut(BaseModel):
    id: int
    title: str
    start_time: datetime
    end_time: datetime
    description: Optional[str]
    is_fixed: bool
    source: str
    task_id: Optional[int]
    run_id: Optional[int]

    model_config = {"from_attributes": True}


class TaskOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    duration_minutes: int
    deadline: Optional[datetime]
    priority: int
    status: str
    category: Optional[str]

    model_config = {"from_attributes": True}


class ParsedTask(BaseModel):
    title: str
    duration_minutes: int
    priority: int = 3
    deadline: Optional[str] = None
    kind: str = "flexible"
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    task_id: Optional[int] = None


class GoalRequirements(BaseModel):
    date: Optional[str] = None
    tasks: list[ParsedTask] = Field(default_factory=list)
    fixed_events: list[ParsedTask] = Field(default_factory=list)
    breaks: list[ParsedTask] = Field(default_factory=list)
    finish_by: Optional[str] = None
    work_start: Optional[str] = None
    work_end: Optional[str] = None
    priorities: dict[str, int] = Field(default_factory=dict)
    ambiguities: list[str] = Field(default_factory=list)
    documented_defaults: list[str] = Field(default_factory=list)
    blocking: bool = False


class AgentRunRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=4000)
    date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    @field_validator("goal")
    @classmethod
    def strip_goal(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("goal must not be empty")
        return cleaned


class ToolLogOut(BaseModel):
    id: int
    step_index: int
    tool_name: str
    arguments: dict[str, Any]
    result: Optional[dict[str, Any]]
    success: bool
    error: Optional[str]
    is_retry: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class VerificationCheck(BaseModel):
    name: str
    passed: bool
    evidence: str


class VerificationOut(BaseModel):
    id: int
    run_id: int
    passed: bool
    checks: list[Any]
    summary: str
    evidence: Optional[dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentRunSummary(BaseModel):
    id: int
    goal: str
    status: str
    provider_mode: str
    target_date: Optional[str]
    parsed_requirements: Optional[dict[str, Any]]
    final_report: Optional[dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
