from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.loop import execute_run
from app.config import Settings, get_settings
from app.db import get_db
from app.models import AgentRun, Task, VerificationResult
from app.schemas.api import (
    AgentRunRequest,
    AgentRunSummary,
    CalendarEventCreate,
    CalendarEventOut,
    CalendarEventUpdate,
    HealthResponse,
    TaskOut,
    ToolLogOut,
    VerificationOut,
)
from app.services.calendar import (
    CalendarError,
    create_event,
    list_events_for_date,
    serialize_event,
    update_event,
    delete_event,
)
from app.services.seed import reset_demo_data
from app.timeutil import to_local

router = APIRouter()


def _settings() -> Settings:
    return get_settings()


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(_settings)):
    mode = settings.llm_provider
    configured = bool(settings.openai_api_key) and settings.llm_provider == "openai"
    if settings.llm_provider == "openai" and not settings.openai_api_key:
        mode = "dev"
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        timezone=settings.timezone,
        provider_mode=mode if configured else "dev",
        llm_configured=configured,
    )


@router.get("/demo/info")
def demo_info(settings: Settings = Depends(_settings)):
    health_payload = health(settings)
    return {
        **health_payload.model_dump(),
        "work_start": settings.work_start,
        "work_end": settings.work_end,
        "lunch_start": settings.lunch_start,
        "lunch_end": settings.lunch_end,
        "defaults": {
            "meeting_minutes": settings.default_meeting_minutes,
            "lunch_minutes": settings.default_lunch_minutes,
        },
    }


@router.get("/calendar")
def get_calendar(
    date_str: str = Query(alias="date", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(_settings),
):
    events = list_events_for_date(db, date.fromisoformat(date_str), settings.timezone)
    return {"date": date_str, "timezone": settings.timezone, "events": [serialize_event(e, settings.timezone) for e in events]}


@router.post("/calendar", status_code=201)
def post_calendar(
    payload: CalendarEventCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(_settings),
):
    try:
        event = create_event(
            db,
            title=payload.title,
            start_time=payload.start_time,
            end_time=payload.end_time,
            settings=settings,
            description=payload.description,
            is_fixed=payload.is_fixed,
            source="user",
            task_id=payload.task_id,
        )
    except CalendarError as exc:
        status = 409 if exc.code == "overlap" else 422
        if exc.code == "not_found":
            status = 404
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)}) from exc
    return serialize_event(event, settings.timezone)


@router.patch("/calendar/{event_id}")
def patch_calendar(
    event_id: int,
    payload: CalendarEventUpdate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(_settings),
):
    fields = payload.model_dump(exclude_unset=True)
    try:
        event = update_event(db, event_id, fields, settings)
    except CalendarError as exc:
        status = {"overlap": 409, "fixed_protected": 403, "not_found": 404}.get(exc.code, 422)
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)}) from exc
    return serialize_event(event, settings.timezone)


@router.delete("/calendar/{event_id}")
def remove_calendar(event_id: int, db: Session = Depends(get_db)):
    try:
        snapshot = delete_event(db, event_id, force=True)
    except CalendarError as exc:
        status = {"fixed_protected": 403, "not_found": 404}.get(exc.code, 422)
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)}) from exc
    return {"deleted": True, "event": snapshot}


@router.get("/tasks", response_model=list[TaskOut])
def get_tasks(db: Session = Depends(get_db), settings: Settings = Depends(_settings)):
    tasks = list(db.scalars(select(Task).order_by(Task.priority, Task.id)))
    out = []
    for task in tasks:
        item = TaskOut.model_validate(task)
        if task.deadline:
            item.deadline = to_local(task.deadline, settings.timezone)
        out.append(item)
    return out


@router.post("/agent/run", response_model=AgentRunSummary)
def run_agent(payload: AgentRunRequest, db: Session = Depends(get_db), settings: Settings = Depends(_settings)):
    if len(payload.goal) > settings.max_goal_length:
        raise HTTPException(status_code=422, detail="Goal exceeds maximum length")
    run = execute_run(db, settings, payload.goal, date_hint=payload.date)
    return AgentRunSummary.model_validate(run)


@router.get("/agent/runs", response_model=list[AgentRunSummary])
def list_runs(db: Session = Depends(get_db)):
    runs = list(db.scalars(select(AgentRun).order_by(AgentRun.id.desc()).limit(20)))
    return [AgentRunSummary.model_validate(run) for run in runs]


@router.get("/agent/runs/{run_id}", response_model=AgentRunSummary)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return AgentRunSummary.model_validate(run)


@router.get("/agent/runs/{run_id}/events", response_model=list[ToolLogOut])
def get_run_events(run_id: int, db: Session = Depends(get_db)):
    run = db.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return [ToolLogOut.model_validate(item) for item in run.tool_logs]


@router.get("/agent/runs/{run_id}/verification", response_model=VerificationOut | None)
def get_run_verification(run_id: int, db: Session = Depends(get_db)):
    run = db.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    latest = db.scalar(
        select(VerificationResult)
        .where(VerificationResult.run_id == run_id)
        .order_by(VerificationResult.id.desc())
    )
    if latest is None:
        return None
    return VerificationOut.model_validate(latest)


@router.post("/agent/runs/{run_id}/cancel")
def cancel_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    run.cancel_requested = True
    if run.status == "executing":
        run.status = "blocked"
        run.error_message = "Cancelled by user"
    db.commit()
    return {"id": run.id, "cancel_requested": True, "status": run.status}


@router.post("/demo/reset")
def demo_reset(db: Session = Depends(get_db), settings: Settings = Depends(_settings)):
    summary = reset_demo_data(db, settings)
    return {"reset": True, **summary}
