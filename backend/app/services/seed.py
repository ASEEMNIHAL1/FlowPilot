from datetime import timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AgentRun, CalendarEvent, Task, ToolLog, VerificationResult
from app.timeutil import combine_local, local_now, parse_hhmm


def _utc_naive(dt):
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def seed_if_empty(db: Session, settings: Settings) -> None:
    has_events = db.scalar(select(CalendarEvent.id).limit(1))
    has_tasks = db.scalar(select(Task.id).limit(1))
    if has_events or has_tasks:
        return
    reset_demo_data(db, settings)


def reset_demo_data(db: Session, settings: Settings) -> dict:
    db.execute(delete(VerificationResult))
    db.execute(delete(ToolLog))
    db.execute(delete(CalendarEvent))
    db.execute(delete(Task))
    db.execute(delete(AgentRun))
    db.commit()

    tz_name = settings.timezone
    today = local_now(tz_name).date()
    tomorrow = today + timedelta(days=1)

    tasks = [
        Task(
            title="Finish intern assignment writeup",
            description="Incomplete draft still needs a verification section.",
            duration_minutes=90,
            deadline=_utc_naive(combine_local(tomorrow, parse_hhmm("19:00"), tz_name)),
            priority=2,
            status="pending",
            category="project",
        ),
        Task(
            title="Review algorithms notes",
            description="Pending DSA review that has not been scheduled.",
            duration_minutes=45,
            deadline=_utc_naive(combine_local(tomorrow, parse_hhmm("19:00"), tz_name)),
            priority=3,
            status="pending",
            category="study",
        ),
        Task(
            title="Send mentor follow-up email",
            description="Low-priority admin task.",
            duration_minutes=30,
            deadline=_utc_naive(combine_local(today, parse_hhmm("18:00"), tz_name)),
            priority=4,
            status="pending",
            category="admin",
        ),
    ]
    db.add_all(tasks)
    db.flush()

    events = [
        CalendarEvent(
            title="Team standup",
            start_time=_utc_naive(combine_local(tomorrow, parse_hhmm("09:00"), tz_name)),
            end_time=_utc_naive(combine_local(tomorrow, parse_hhmm("09:15"), tz_name)),
            description="Daily standup. Fixed — do not move.",
            is_fixed=True,
            source="seed",
        ),
        CalendarEvent(
            title="Mentorship session",
            start_time=_utc_naive(combine_local(tomorrow, parse_hhmm("18:00"), tz_name)),
            end_time=_utc_naive(combine_local(tomorrow, parse_hhmm("18:30"), tz_name)),
            description="Fixed 1:1.",
            is_fixed=True,
            source="seed",
        ),
        CalendarEvent(
            title="Optional office hours",
            start_time=_utc_naive(combine_local(tomorrow, parse_hhmm("14:00"), tz_name)),
            end_time=_utc_naive(combine_local(tomorrow, parse_hhmm("15:00"), tz_name)),
            description="Non-fixed block that conflicts with a 2 PM meeting request.",
            is_fixed=False,
            source="seed",
        ),
        CalendarEvent(
            title="Gym",
            start_time=_utc_naive(combine_local(today, parse_hhmm("18:30"), tz_name)),
            end_time=_utc_naive(combine_local(today, parse_hhmm("19:30"), tz_name)),
            description="Existing personal event.",
            is_fixed=True,
            source="seed",
        ),
    ]
    db.add_all(events)
    db.commit()
    return {
        "tasks": len(tasks),
        "events": len(events),
        "today": today.isoformat(),
        "tomorrow": tomorrow.isoformat(),
        "timezone": tz_name,
    }
