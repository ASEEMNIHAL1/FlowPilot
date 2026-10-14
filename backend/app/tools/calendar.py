from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.models import AgentRun, CalendarEvent, Task
from app.services.calendar import (
    CalendarError,
    create_event,
    delete_event,
    list_events_for_date,
    serialize_event,
    update_event,
)
from app.services.parser import parse_goal
from app.services.scheduler import find_free_slots, propose_schedule
from app.services.verifier import verify_schedule
from app.timeutil import combine_local, parse_hhmm
from app.tools.registry import Tool, ToolContext, ToolError, ToolRegistry


class ParseGoalArgs(BaseModel):
    goal: str = Field(min_length=1, max_length=4000)


class DateArgs(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class GetTasksArgs(BaseModel):
    status: Optional[str] = None


class TaskIdArgs(BaseModel):
    task_id: int


class FindSlotsArgs(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    duration_minutes: int = Field(gt=0, le=12 * 60)
    work_start: Optional[str] = None
    work_end: Optional[str] = None
    finish_by: Optional[str] = None


class CreateEventArgs(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    start_time: str
    end_time: str
    description: Optional[str] = None
    is_fixed: bool = False
    task_id: Optional[int] = None


class UpdateEventArgs(BaseModel):
    event_id: int
    title: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    description: Optional[str] = None


class DeleteEventArgs(BaseModel):
    event_id: int
    justification: str = Field(min_length=8, max_length=400)


class VerifyArgs(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    expected_tasks: list[dict] = Field(default_factory=list)
    work_start: Optional[str] = None
    work_end: Optional[str] = None
    finish_by: Optional[str] = None


class RunIdArgs(BaseModel):
    run_id: int


class ProposeArgs(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    tasks: list[dict]
    work_start: Optional[str] = None
    work_end: Optional[str] = None
    finish_by: Optional[str] = None


def _day(value: str) -> date:
    return date.fromisoformat(value)


def handle_parse_goal(ctx: ToolContext, goal: str) -> dict:
    requirements = parse_goal(goal, ctx.settings)
    return requirements.model_dump()


def handle_get_calendar(ctx: ToolContext, date: str) -> dict:
    events = list_events_for_date(ctx.db, _day(date), ctx.settings.timezone)
    return {"date": date, "events": [serialize_event(event, ctx.settings.timezone) for event in events]}


def handle_get_tasks(ctx: ToolContext, status: str | None = None) -> dict:
    stmt = select(Task)
    if status:
        stmt = stmt.where(Task.status == status)
    tasks = list(ctx.db.scalars(stmt.order_by(Task.priority, Task.id)))
    return {
        "tasks": [
            {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "duration_minutes": task.duration_minutes,
                "deadline": task.deadline.isoformat() if task.deadline else None,
                "priority": task.priority,
                "status": task.status,
                "category": task.category,
            }
            for task in tasks
        ]
    }


def handle_get_task_details(ctx: ToolContext, task_id: int) -> dict:
    task = ctx.db.get(Task, task_id)
    if task is None:
        raise ToolError(f"Task {task_id} not found", "not_found")
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "duration_minutes": task.duration_minutes,
        "deadline": task.deadline.isoformat() if task.deadline else None,
        "priority": task.priority,
        "status": task.status,
        "category": task.category,
    }


def handle_find_free_slots(
    ctx: ToolContext,
    date: str,
    duration_minutes: int,
    work_start: str | None = None,
    work_end: str | None = None,
    finish_by: str | None = None,
) -> dict:
    payload = handle_get_calendar(ctx, date)
    slots = find_free_slots(
        day=_day(date),
        duration_minutes=duration_minutes,
        events=payload["events"],
        settings=ctx.settings,
        work_start=work_start,
        work_end=work_end,
        finish_by=finish_by,
    )
    return {"date": date, "duration_minutes": duration_minutes, "slots": slots[:12]}


def handle_propose_schedule(
    ctx: ToolContext,
    date: str,
    tasks: list[dict],
    work_start: str | None = None,
    work_end: str | None = None,
    finish_by: str | None = None,
) -> dict:
    payload = handle_get_calendar(ctx, date)
    proposal = propose_schedule(
        day=_day(date),
        flexible_tasks=tasks,
        events=payload["events"],
        settings=ctx.settings,
        work_start=work_start,
        work_end=work_end,
        finish_by=finish_by,
    )
    proposal["date"] = date
    return proposal


def handle_create_event(
    ctx: ToolContext,
    title: str,
    start_time: str,
    end_time: str,
    description: str | None = None,
    is_fixed: bool = False,
    task_id: int | None = None,
) -> dict:
    if ctx.inject_create_failures > 0:
        ctx.inject_create_failures -= 1
        raise ToolError("Temporary calendar write failure", "transient")
    try:
        event = create_event(
            ctx.db,
            title=title,
            start_time=datetime.fromisoformat(start_time),
            end_time=datetime.fromisoformat(end_time),
            settings=ctx.settings,
            description=description,
            is_fixed=is_fixed,
            source="agent",
            task_id=task_id,
            run_id=ctx.run_id,
        )
    except CalendarError as exc:
        conflicts = []
        if exc.code == "overlap":
            day = datetime.fromisoformat(start_time).date()
            conflicts = [
                serialize_event(item, ctx.settings.timezone)
                for item in list_events_for_date(ctx.db, day, ctx.settings.timezone)
            ]
        raise ToolError(str(exc), exc.code) from exc
    if task_id:
        task = ctx.db.get(Task, task_id)
        if task:
            task.status = "scheduled"
            ctx.db.commit()
    return {"created": True, "duplicate": False, "event": serialize_event(event, ctx.settings.timezone)}


def handle_update_event(
    ctx: ToolContext,
    event_id: int,
    title: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    description: str | None = None,
) -> dict:
    fields = {}
    if title is not None:
        fields["title"] = title
    if start_time is not None:
        fields["start_time"] = datetime.fromisoformat(start_time)
    if end_time is not None:
        fields["end_time"] = datetime.fromisoformat(end_time)
    if description is not None:
        fields["description"] = description
    try:
        event = update_event(ctx.db, event_id, fields, ctx.settings)
    except CalendarError as exc:
        raise ToolError(str(exc), exc.code) from exc
    return {"updated": True, "event": serialize_event(event, ctx.settings.timezone)}


def handle_delete_event(ctx: ToolContext, event_id: int, justification: str) -> dict:
    event = ctx.db.get(CalendarEvent, event_id)
    if event is None:
        raise ToolError(f"Event {event_id} not found", "not_found")
    if event.is_fixed:
        raise ToolError("Refusing to delete a fixed event", "fixed_protected")
    allowed = "conflict" in justification.lower() or "overlap" in justification.lower() or "block" in justification.lower()
    if not allowed:
        raise ToolError("delete_event requires a justification mentioning conflict, overlap, or block", "not_justified")
    try:
        snapshot = delete_event(ctx.db, event_id, run_id=ctx.run_id, force=True)
    except CalendarError as exc:
        raise ToolError(str(exc), exc.code) from exc
    return {"deleted": True, "event": snapshot, "justification": justification}


def handle_verify_schedule(
    ctx: ToolContext,
    date: str,
    expected_tasks: list[dict],
    work_start: str | None = None,
    work_end: str | None = None,
    finish_by: str | None = None,
) -> dict:
    return verify_schedule(
        ctx.db,
        day=_day(date),
        expected_tasks=expected_tasks,
        settings=ctx.settings,
        work_start=work_start,
        work_end=work_end,
        finish_by=finish_by,
    )


def handle_get_execution_status(ctx: ToolContext, run_id: int) -> dict:
    run = ctx.db.get(AgentRun, run_id)
    if run is None:
        raise ToolError(f"Run {run_id} not found", "not_found")
    return {
        "id": run.id,
        "status": run.status,
        "goal": run.goal,
        "provider_mode": run.provider_mode,
        "target_date": run.target_date,
        "error_message": run.error_message,
        "cancel_requested": run.cancel_requested,
    }


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(Tool("parse_goal", "Parse a natural-language scheduling goal into structured requirements. Does not invent missing critical fields.", ParseGoalArgs, handle_parse_goal, "read"))
    registry.register(Tool("get_calendar", "List persisted calendar events for a local date.", DateArgs, handle_get_calendar, "read"))
    registry.register(Tool("get_tasks", "List tasks in the simulated store, optionally filtered by status.", GetTasksArgs, handle_get_tasks, "read"))
    registry.register(Tool("get_task_details", "Fetch one task by id.", TaskIdArgs, handle_get_task_details, "read"))
    registry.register(Tool("find_free_slots", "Deterministically find free slots that fit a duration under working-hour constraints.", FindSlotsArgs, handle_find_free_slots, "read"))
    registry.register(Tool("propose_schedule", "Use the Python scheduler to place flexible tasks into free slots without writing the calendar.", ProposeArgs, handle_propose_schedule, "read"))
    registry.register(Tool("create_event", "Create a calendar event. Rejects overlaps and invalid ranges. Idempotent on title+start+end.", CreateEventArgs, handle_create_event, "write"))
    registry.register(Tool("update_event", "Update a non-fixed event. Fixed events are protected.", UpdateEventArgs, handle_update_event, "write"))
    registry.register(Tool("delete_event", "Delete a non-fixed event only with conflict/overlap justification. Never deletes fixed events.", DeleteEventArgs, handle_delete_event, "write"))
    registry.register(Tool("verify_schedule", "Independently verify persisted calendar state against expected tasks.", VerifyArgs, handle_verify_schedule, "read"))
    registry.register(Tool("get_execution_status", "Read the current agent run status.", RunIdArgs, handle_get_execution_status, "read"))
    return registry
