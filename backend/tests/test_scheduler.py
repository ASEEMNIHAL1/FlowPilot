from datetime import date, timedelta

from app.config import get_settings
from app.services.scheduler import find_free_slots, propose_schedule
from app.timeutil import local_now


def test_free_slot_selection():
    settings = get_settings()
    day = local_now(settings.timezone).date() + timedelta(days=1)
    events = [
        {
            "title": "Busy",
            "start_time": f"{day.isoformat()}T09:00:00+05:30",
            "end_time": f"{day.isoformat()}T10:00:00+05:30",
        }
    ]
    slots = find_free_slots(day=day, duration_minutes=60, events=events, settings=settings)
    assert slots
    assert slots[0]["start_time"].startswith(f"{day.isoformat()}T10:00")


def test_impossible_deadlines():
    settings = get_settings()
    day = date(2026, 10, 13)
    events = [
        {
            "title": "Locked morning",
            "start_time": "2026-10-13T09:00:00+05:30",
            "end_time": "2026-10-13T18:30:00+05:30",
        }
    ]
    proposal = propose_schedule(
        day=day,
        flexible_tasks=[{"title": "Huge task", "duration_minutes": 180, "priority": 1}],
        events=events,
        settings=settings,
        finish_by="19:00",
    )
    assert proposal["placements"] == []
    assert proposal["unresolved"][0]["reason"] == "no_free_slot"


def test_normal_successful_scheduling():
    settings = get_settings()
    day = date(2026, 10, 13)
    proposal = propose_schedule(
        day=day,
        flexible_tasks=[
            {"title": "DSA practice", "duration_minutes": 120, "priority": 2},
            {"title": "Project work", "duration_minutes": 180, "priority": 3},
        ],
        events=[
            {
                "title": "Standup",
                "start_time": "2026-10-13T09:00:00+05:30",
                "end_time": "2026-10-13T09:15:00+05:30",
            }
        ],
        settings=settings,
        finish_by="19:00",
    )
    assert len(proposal["placements"]) == 2
    assert not proposal["unresolved"]
