from datetime import date, datetime, timedelta

from app.config import Settings
from app.timeutil import combine_local, parse_hhmm, to_local


def _busy_intervals(events: list[dict], tz_name: str) -> list[tuple[datetime, datetime, dict]]:
    busy = []
    for event in events:
        start = datetime.fromisoformat(event["start_time"]) if isinstance(event["start_time"], str) else to_local(event["start_time"], tz_name)
        end = datetime.fromisoformat(event["end_time"]) if isinstance(event["end_time"], str) else to_local(event["end_time"], tz_name)
        busy.append((start, end, event))
    busy.sort(key=lambda item: item[0])
    return busy


def merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda item: item[0])
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def find_free_slots(
    *,
    day: date,
    duration_minutes: int,
    events: list[dict],
    settings: Settings,
    work_start: str | None = None,
    work_end: str | None = None,
    finish_by: str | None = None,
    extra_busy: list[tuple[datetime, datetime]] | None = None,
) -> list[dict]:
    if duration_minutes <= 0:
        return []

    tz_name = settings.timezone
    window_start = combine_local(day, parse_hhmm(work_start or settings.work_start), tz_name)
    window_end = combine_local(day, parse_hhmm(finish_by or work_end or settings.work_end), tz_name)
    if window_end <= window_start:
        return []

    busy = [(start, end) for start, end, _ in _busy_intervals(events, tz_name)]
    if extra_busy:
        busy.extend(extra_busy)
    busy = merge_intervals(busy)

    cursor = window_start
    slots: list[dict] = []
    duration = timedelta(minutes=duration_minutes)

    for start, end in busy + [(window_end, window_end)]:
        gap_end = min(start, window_end)
        if cursor + duration <= gap_end:
            available = gap_end - cursor
            slots.append(
                {
                    "start_time": cursor.isoformat(),
                    "end_time": (cursor + duration).isoformat(),
                    "available_minutes": int(available.total_seconds() // 60),
                    "fits_duration": True,
                }
            )
            # also offer later placements in the same gap
            step = cursor + duration
            while step + duration <= gap_end:
                slots.append(
                    {
                        "start_time": step.isoformat(),
                        "end_time": (step + duration).isoformat(),
                        "available_minutes": int((gap_end - step).total_seconds() // 60),
                        "fits_duration": True,
                    }
                )
                step += duration
        cursor = max(cursor, end)
        if cursor >= window_end:
            break

    unique = []
    seen = set()
    for slot in slots:
        key = (slot["start_time"], slot["end_time"])
        if key not in seen:
            seen.add(key)
            unique.append(slot)
    unique.sort(key=lambda item: item["start_time"])
    return unique


def prioritize_tasks(tasks: list[dict]) -> list[dict]:
    def sort_key(task: dict):
        deadline = task.get("deadline") or "9999-12-31"
        return (int(task.get("priority") or 3), deadline, -int(task.get("duration_minutes") or 0))

    return sorted(tasks, key=sort_key)


def propose_schedule(
    *,
    day: date,
    flexible_tasks: list[dict],
    events: list[dict],
    settings: Settings,
    work_start: str | None = None,
    work_end: str | None = None,
    finish_by: str | None = None,
) -> dict:
    remaining_events = list(events)
    placements = []
    unresolved = []
    ordered = prioritize_tasks(flexible_tasks)

    for task in ordered:
        duration = int(task["duration_minutes"])
        slots = find_free_slots(
            day=day,
            duration_minutes=duration,
            events=remaining_events,
            settings=settings,
            work_start=work_start,
            work_end=work_end,
            finish_by=finish_by,
        )
        if not slots:
            unresolved.append(
                {
                    "title": task["title"],
                    "reason": "no_free_slot",
                    "duration_minutes": duration,
                }
            )
            continue
        chosen = slots[0]
        placements.append(
            {
                "title": task["title"],
                "start_time": chosen["start_time"],
                "end_time": chosen["end_time"],
                "duration_minutes": duration,
                "task_id": task.get("task_id"),
                "kind": task.get("kind", "flexible"),
            }
        )
        remaining_events.append(
            {
                "title": task["title"],
                "start_time": chosen["start_time"],
                "end_time": chosen["end_time"],
                "is_fixed": False,
            }
        )

    return {"placements": placements, "unresolved": unresolved}
