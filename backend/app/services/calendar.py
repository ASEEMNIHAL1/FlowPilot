from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import CalendarEvent
from app.timeutil import coerce_utc, to_local, to_utc, zone


class CalendarError(Exception):
    def __init__(self, message: str, code: str = "calendar_error"):
        super().__init__(message)
        self.code = code


def event_fingerprint(title: str, start: datetime, end: datetime) -> str:
    return f"{title.strip().lower()}|{start.astimezone(timezone.utc).isoformat()}|{end.astimezone(timezone.utc).isoformat()}"


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def _normalize(dt: datetime, tz_name: str) -> datetime:
    return to_utc(dt, tz_name)


def list_events_for_date(db: Session, day: date, tz_name: str) -> list[CalendarEvent]:
    start = datetime.combine(day, datetime.min.time(), tzinfo=zone(tz_name))
    end = datetime.combine(day, datetime.max.time(), tzinfo=zone(tz_name))
    start_utc = start.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end.astimezone(timezone.utc).replace(tzinfo=None)
    stmt = (
        select(CalendarEvent)
        .where(CalendarEvent.start_time < end_utc, CalendarEvent.end_time > start_utc)
        .order_by(CalendarEvent.start_time)
    )
    events = list(db.scalars(stmt))
    for event in events:
        event.start_time = coerce_utc(event.start_time)
        event.end_time = coerce_utc(event.end_time)
    return events


def overlapping_events(
    db: Session,
    start: datetime,
    end: datetime,
    exclude_id: int | None = None,
) -> list[CalendarEvent]:
    stmt = select(CalendarEvent).where(CalendarEvent.start_time < end, CalendarEvent.end_time > start)
    events = list(db.scalars(stmt))
    if exclude_id is not None:
        events = [event for event in events if event.id != exclude_id]
    return events


def create_event(
    db: Session,
    *,
    title: str,
    start_time: datetime,
    end_time: datetime,
    settings: Settings,
    description: str | None = None,
    is_fixed: bool = False,
    source: str = "user",
    task_id: int | None = None,
    run_id: int | None = None,
    allow_overlap: bool = False,
) -> CalendarEvent:
    start = _normalize(start_time, settings.timezone)
    end = _normalize(end_time, settings.timezone)
    if end <= start:
        raise CalendarError("end_time must be after start_time", "invalid_range")

    fingerprint = event_fingerprint(title, start, end)
    existing = db.scalar(select(CalendarEvent).where(CalendarEvent.fingerprint == fingerprint))
    if existing:
        existing.start_time = coerce_utc(existing.start_time)
        existing.end_time = coerce_utc(existing.end_time)
        return existing

    conflicts = overlapping_events(db, start.replace(tzinfo=None), end.replace(tzinfo=None))
    if conflicts and not allow_overlap:
        titles = ", ".join(event.title for event in conflicts)
        raise CalendarError(
            f"Event overlaps existing calendar items: {titles}",
            "overlap",
        )

    event = CalendarEvent(
        title=title.strip(),
        start_time=start.replace(tzinfo=None),
        end_time=end.replace(tzinfo=None),
        description=description,
        is_fixed=is_fixed,
        source=source,
        task_id=task_id,
        run_id=run_id,
        fingerprint=fingerprint,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    event.start_time = coerce_utc(event.start_time)
    event.end_time = coerce_utc(event.end_time)
    return event


def update_event(
    db: Session,
    event_id: int,
    fields: dict,
    settings: Settings,
) -> CalendarEvent:
    event = db.get(CalendarEvent, event_id)
    if event is None:
        raise CalendarError(f"Event {event_id} not found", "not_found")
    if event.is_fixed:
        raise CalendarError("Fixed events cannot be modified", "fixed_protected")

    current_start = coerce_utc(event.start_time)
    current_end = coerce_utc(event.end_time)
    start = _normalize(fields["start_time"], settings.timezone) if "start_time" in fields else current_start
    end = _normalize(fields["end_time"], settings.timezone) if "end_time" in fields else current_end
    if end <= start:
        raise CalendarError("end_time must be after start_time", "invalid_range")

    conflicts = overlapping_events(
        db,
        start.replace(tzinfo=None),
        end.replace(tzinfo=None),
        exclude_id=event.id,
    )
    if conflicts:
        titles = ", ".join(item.title for item in conflicts)
        raise CalendarError(f"Updated event would overlap: {titles}", "overlap")

    if "title" in fields and fields["title"]:
        event.title = fields["title"].strip()
    event.start_time = start.replace(tzinfo=None)
    event.end_time = end.replace(tzinfo=None)
    if "description" in fields:
        event.description = fields["description"]
    event.fingerprint = event_fingerprint(event.title, start, end)
    db.commit()
    db.refresh(event)
    event.start_time = coerce_utc(event.start_time)
    event.end_time = coerce_utc(event.end_time)
    return event


def delete_event(db: Session, event_id: int, *, run_id: int | None = None, force: bool = False) -> dict:
    event = db.get(CalendarEvent, event_id)
    if event is None:
        raise CalendarError(f"Event {event_id} not found", "not_found")
    if event.is_fixed:
        raise CalendarError("Fixed events cannot be deleted", "fixed_protected")
    if event.source == "seed" and not force:
        if run_id is None:
            raise CalendarError("Seed events can only be removed by an agent run when blocking a required meeting", "seed_protected")
    snapshot = {"id": event.id, "title": event.title}
    db.delete(event)
    db.commit()
    return snapshot


def serialize_event(event: CalendarEvent, tz_name: str) -> dict:
    return {
        "id": event.id,
        "title": event.title,
        "start_time": to_local(coerce_utc(event.start_time), tz_name).isoformat(),
        "end_time": to_local(coerce_utc(event.end_time), tz_name).isoformat(),
        "description": event.description,
        "is_fixed": event.is_fixed,
        "source": event.source,
        "task_id": event.task_id,
        "run_id": event.run_id,
    }
