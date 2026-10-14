from datetime import date, timedelta

import app.db as db_module
from app.agent.loop import execute_run
from app.agent.provider import ProviderResponse, ScriptedProvider, ToolCallRequest
from app.config import get_settings
from app.models import CalendarEvent
from app.services.calendar import serialize_event
from app.services.verifier import verify_schedule
from app.timeutil import local_now


SAMPLE_GOAL = (
    "Plan tomorrow. I need two hours of DSA practice, three hours for my project, "
    "lunch, and a team meeting at 2 PM. Finish by 7 PM."
)


def test_invalid_model_tool_calls(client):
    settings = get_settings()
    db = db_module.SessionLocal()
    provider = ScriptedProvider(
        [
            ProviderResponse(
                content=None,
                tool_calls=[ToolCallRequest(id="bad-1", name="drop_database", arguments={})],
            ),
            ProviderResponse(
                content=None,
                tool_calls=[ToolCallRequest(id="bad-2", name="create_event", arguments={"title": "x"})],
            ),
            ProviderResponse(
                content=None,
                tool_calls=[ToolCallRequest(id="bad-3", name="not_a_tool", arguments={})],
            ),
        ]
    )
    run = execute_run(db, settings, "Schedule anything tomorrow", provider=provider)
    db.close()
    assert run.status == "failed"
    assert run.error_message == "Too many invalid tool calls"


def test_tool_failure_and_bounded_retry(client):
    settings = get_settings()
    db = db_module.SessionLocal()
    tomorrow = (local_now(settings.timezone).date() + timedelta(days=1)).isoformat()
    start = f"{tomorrow}T11:00:00+05:30"
    end = f"{tomorrow}T11:30:00+05:30"
    provider = ScriptedProvider(
        [
            ProviderResponse(None, [ToolCallRequest("c1", "create_event", {"title": "Retry block", "start_time": start, "end_time": end})]),
            ProviderResponse(None, [ToolCallRequest("c2", "create_event", {"title": "Retry block", "start_time": start, "end_time": end})]),
            ProviderResponse("Created after retry", []),
        ]
    )
    run = execute_run(db, settings, "Add a 30 minute retry block tomorrow at 11", provider=provider, inject_create_failures=1)
    names = [(log.tool_name, log.success, log.error) for log in run.tool_logs]
    db.close()
    assert names[0][0] == "create_event"
    assert names[0][1] is False
    assert "Temporary" in (names[0][2] or "")
    assert names[1][0] == "create_event"
    assert names[1][1] is True


def test_duplicate_prevention(client):
    settings = get_settings()
    db = db_module.SessionLocal()
    tomorrow = (local_now(settings.timezone).date() + timedelta(days=1)).isoformat()
    args = {
        "title": "Unique lab",
        "start_time": f"{tomorrow}T11:45:00+05:30",
        "end_time": f"{tomorrow}T12:00:00+05:30",
    }
    provider = ScriptedProvider(
        [
            ProviderResponse(None, [ToolCallRequest("d1", "create_event", args)]),
            ProviderResponse(None, [ToolCallRequest("d2", "create_event", args)]),
            ProviderResponse("done", []),
        ]
    )
    run = execute_run(db, settings, "Schedule unique lab tomorrow", provider=provider)
    successes = [log for log in run.tool_logs if log.tool_name == "create_event"]
    db.close()
    assert successes[0].success is True
    assert successes[1].result.get("duplicate_prevented") is True


def test_missing_event_detection(client):
    settings = get_settings()
    db = db_module.SessionLocal()
    tomorrow = local_now(settings.timezone).date() + timedelta(days=1)
    result = verify_schedule(
        db,
        day=tomorrow,
        expected_tasks=[{"title": "Does not exist", "duration_minutes": 30}],
        settings=settings,
    )
    db.close()
    assert result["passed"] is False
    assert "Does not exist" in result["evidence"]["missing_titles"]


def test_verification_failure_and_repair(client):
    settings = get_settings()
    db = db_module.SessionLocal()
    tomorrow = (local_now(settings.timezone).date() + timedelta(days=1)).isoformat()
    provider = ScriptedProvider(
        [
            ProviderResponse(
                None,
                [
                    ToolCallRequest(
                        "v1",
                        "verify_schedule",
                        {"date": tomorrow, "expected_tasks": [{"title": "Ghost task", "duration_minutes": 30}]},
                    )
                ],
            ),
            ProviderResponse(
                None,
                [
                    ToolCallRequest(
                        "v2",
                        "create_event",
                        {
                            "title": "Ghost task",
                            "start_time": f"{tomorrow}T11:00:00+05:30",
                            "end_time": f"{tomorrow}T11:30:00+05:30",
                        },
                    )
                ],
            ),
            ProviderResponse(
                None,
                [
                    ToolCallRequest(
                        "v3",
                        "verify_schedule",
                        {"date": tomorrow, "expected_tasks": [{"title": "Ghost task", "duration_minutes": 30}]},
                    )
                ],
            ),
            ProviderResponse("Repaired missing event using tool observations.", []),
        ]
    )
    run = execute_run(db, settings, "Repair the ghost task tomorrow", provider=provider)
    verify_logs = [log for log in run.tool_logs if log.tool_name == "verify_schedule"]
    db.close()
    assert verify_logs[0].success is True
    assert verify_logs[0].result["passed"] is False
    assert verify_logs[-1].result["passed"] is True
    assert run.status in {"verified", "completed", "partially_completed"}


def test_accurate_final_reporting_and_e2e_goal(client):
    response = client.post("/agent/run", json={"goal": SAMPLE_GOAL})
    assert response.status_code == 200
    body = response.json()
    assert body["id"]
    assert body["parsed_requirements"]["date"]
    assert body["final_report"]
    run_id = body["id"]
    events = client.get(f"/agent/runs/{run_id}/events")
    assert events.status_code == 200
    names = [item["tool_name"] for item in events.json()]
    assert "parse_goal" in names
    assert "get_calendar" in names
    assert "create_event" in names
    assert "verify_schedule" in names
    verification = client.get(f"/agent/runs/{run_id}/verification")
    assert verification.status_code == 200
    assert verification.json()["checks"]
    day = body["target_date"]
    calendar = client.get("/calendar", params={"date": day}).json()["events"]
    titles = [event["title"] for event in calendar]
    assert any("meeting" in title.lower() for title in titles)
    assert any("DSA" in title or "dsa" in title.lower() for title in titles)
    assert any("project" in title.lower() for title in titles)
    assert any("lunch" in title.lower() for title in titles)
    standup = next(event for event in calendar if event["title"] == "Team standup")
    assert standup["is_fixed"] is True
    report = body["final_report"]
    persisted = [title for title in report.get("scheduled_titles", [])]
    for title in persisted:
        assert any(title.lower() in event.lower() or event.lower() in title.lower() for event in titles)


def test_dev_mode_conflict_recovery(client):
    response = client.post("/agent/run", json={"goal": SAMPLE_GOAL})
    day = response.json()["target_date"]
    calendar = client.get("/calendar", params={"date": day}).json()["events"]
    titles = {event["title"] for event in calendar}
    assert "Optional office hours" not in titles
    logs = client.get(f"/agent/runs/{response.json()['id']}/events").json()
    assert any(item["tool_name"] == "delete_event" and item["success"] for item in logs)
