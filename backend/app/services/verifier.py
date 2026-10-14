from datetime import date, datetime

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import CalendarEvent
from app.services.calendar import list_events_for_date, overlaps, serialize_event
from app.timeutil import combine_local, parse_hhmm, to_local


def _norm(title: str) -> str:
    return " ".join(title.lower().split())


def titles_match(expected: str, actual: str) -> bool:
    exp = _norm(expected)
    act = _norm(actual)
    return exp == act or exp in act or act in exp


def verify_schedule(
    db: Session,
    *,
    day: date,
    expected_tasks: list[dict],
    settings: Settings,
    work_start: str | None = None,
    work_end: str | None = None,
    finish_by: str | None = None,
    protected_fixed_ids: list[int] | None = None,
    report_claims: dict | None = None,
) -> dict:
    tz_name = settings.timezone
    events = list_events_for_date(db, day, tz_name)
    serialized = [serialize_event(event, tz_name) for event in events]
    checks = []

    window_start = combine_local(day, parse_hhmm(work_start or settings.work_start), tz_name)
    window_end = combine_local(day, parse_hhmm(finish_by or work_end or settings.work_end), tz_name)

    scheduled_titles = []
    missing = []
    for expected in expected_tasks:
        title = expected.get("title") or ""
        match = next((event for event in events if titles_match(title, event.title)), None)
        if match is None:
            missing.append(title)
            checks.append(
                {
                    "name": f"task_scheduled:{title}",
                    "passed": False,
                    "evidence": f"No persisted event matching '{title}' on {day.isoformat()}",
                }
            )
        else:
            scheduled_titles.append(title)
            start = to_local(match.start_time, tz_name)
            end = to_local(match.end_time, tz_name)
            duration_ok = True
            expected_minutes = expected.get("duration_minutes")
            if expected_minutes:
                actual_minutes = int((match.end_time - match.start_time).total_seconds() // 60)
                duration_ok = actual_minutes >= int(expected_minutes) - 15
            valid_time = start < end
            checks.append(
                {
                    "name": f"task_scheduled:{title}",
                    "passed": valid_time and duration_ok,
                    "evidence": f"Event {match.id} '{match.title}' {start.isoformat()}–{end.isoformat()}",
                }
            )

    overlap_found = []
    for i, left in enumerate(events):
        for right in events[i + 1 :]:
            if overlaps(left.start_time, left.end_time, right.start_time, right.end_time):
                overlap_found.append((left.title, right.title))
    checks.append(
        {
            "name": "no_unintended_overlaps",
            "passed": not overlap_found,
            "evidence": "none" if not overlap_found else str(overlap_found),
        }
    )

    fixed_ok = True
    fixed_evidence = []
    if protected_fixed_ids:
        for event_id in protected_fixed_ids:
            current = db.get(CalendarEvent, event_id)
            if current is None:
                fixed_ok = False
                fixed_evidence.append(f"Fixed event {event_id} is missing")
    else:
        for event in events:
            if event.is_fixed and event.source == "seed":
                fixed_evidence.append(f"Fixed seed event {event.id} '{event.title}' still present")
    checks.append(
        {
            "name": "fixed_events_protected",
            "passed": fixed_ok,
            "evidence": "; ".join(fixed_evidence) or "No protected fixed events were removed",
        }
    )

    hours_ok = True
    hours_evidence = []
    agent_events = [event for event in events if event.source == "agent"]
    for event in agent_events:
        start = to_local(event.start_time, tz_name)
        end = to_local(event.end_time, tz_name)
        if start < window_start or end > window_end:
            hours_ok = False
            hours_evidence.append(f"{event.title} outside working window")
    checks.append(
        {
            "name": "working_hours_respected",
            "passed": hours_ok,
            "evidence": "; ".join(hours_evidence) or f"Agent events fall within {window_start.isoformat()}–{window_end.isoformat()}",
        }
    )

    times_valid = all(event.end_time > event.start_time for event in events)
    checks.append(
        {
            "name": "valid_time_ranges",
            "passed": times_valid,
            "evidence": "All persisted events have end_time after start_time",
        }
    )

    report_ok = True
    report_evidence = "No report claims to compare"
    if report_claims:
        claimed_success = report_claims.get("scheduled") or []
        for title in claimed_success:
            if not any(titles_match(title, event.title) for event in events):
                report_ok = False
                report_evidence = f"Report claimed '{title}' was scheduled but it is not persisted"
                break
        else:
            report_evidence = "Report scheduled titles match persisted events"
    checks.append(
        {
            "name": "report_matches_state",
            "passed": report_ok,
            "evidence": report_evidence,
        }
    )

    passed = all(check["passed"] for check in checks) and not missing
    unresolved = missing + [item.get("title") for item in expected_tasks if item.get("unresolved")]
    summary = "All verification checks passed" if passed else "Verification found problems in the persisted calendar"
    return {
        "passed": passed,
        "checks": checks,
        "summary": summary,
        "evidence": {
            "date": day.isoformat(),
            "events": serialized,
            "scheduled_titles": scheduled_titles,
            "missing_titles": missing,
            "unresolved": unresolved,
        },
    }
