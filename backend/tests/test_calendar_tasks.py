from datetime import date, timedelta

from app.config import get_settings
from app.timeutil import local_now


def _tomorrow() -> str:
    return (local_now(get_settings().timezone).date() + timedelta(days=1)).isoformat()


def test_calendar_and_task_retrieval(client):
    day = _tomorrow()
    calendar = client.get("/calendar", params={"date": day})
    assert calendar.status_code == 200
    events = calendar.json()["events"]
    titles = {event["title"] for event in events}
    assert "Team standup" in titles
    assert "Optional office hours" in titles
    tasks = client.get("/tasks")
    assert tasks.status_code == 200
    assert len(tasks.json()) >= 3


def test_event_create_and_update(client):
    day = _tomorrow()
    created = client.post(
        "/calendar",
        json={
            "title": "Focus block",
            "start_time": f"{day}T11:00:00+05:30",
            "end_time": f"{day}T11:30:00+05:30",
            "description": "Manual create",
        },
    )
    assert created.status_code == 201
    event_id = created.json()["id"]
    updated = client.patch(
        "/calendar/{event_id}".format(event_id=event_id),
        json={"title": "Focus block updated"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Focus block updated"


def test_invalid_time_ranges(client):
    day = _tomorrow()
    response = client.post(
        "/calendar",
        json={
            "title": "Backwards",
            "start_time": f"{day}T12:00:00+05:30",
            "end_time": f"{day}T11:00:00+05:30",
        },
    )
    assert response.status_code == 422


def test_overlapping_event_rejection(client):
    day = _tomorrow()
    response = client.post(
        "/calendar",
        json={
            "title": "Overlap standup",
            "start_time": f"{day}T09:00:00+05:30",
            "end_time": f"{day}T09:20:00+05:30",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "overlap"


def test_fixed_event_protection(client):
    day = _tomorrow()
    events = client.get("/calendar", params={"date": day}).json()["events"]
    standup = next(event for event in events if event["title"] == "Team standup")
    blocked = client.patch(
        f"/calendar/{standup['id']}",
        json={"title": "Moved standup"},
    )
    assert blocked.status_code == 403
    deleted = client.delete(f"/calendar/{standup['id']}")
    assert deleted.status_code == 403
