from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import uuid4

import httpx

from app.config import Settings


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: dict[str, Any]
    raw: dict[str, Any] | None = None


@dataclass
class ProviderResponse:
    content: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    raw_message: dict[str, Any] | None = None


class ModelProvider(Protocol):
    mode: str

    def complete(self, messages: list[dict], tools: list[dict]) -> ProviderResponse:
        ...


class OpenAIProvider:
    mode = "openai"

    def __init__(self, settings: Settings):
        self.settings = settings

    def complete(self, messages: list[dict], tools: list[dict]) -> ProviderResponse:
        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        payload = {
            "model": self.settings.openai_model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.2,
        }
        try:
            response = httpx.post(
                f"{self.settings.openai_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=45.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            error_body = exc.response.text
            raise RuntimeError(f"OpenAI/Gemini API error ({exc.response.status_code}): {error_body}") from exc

        message = response.json()["choices"][0]["message"]
        tool_calls = []
        for call in message.get("tool_calls") or []:
            raw_args = call["function"].get("arguments") or "{}"
            try:
                arguments = json.loads(raw_args)
            except json.JSONDecodeError:
                arguments = {"_invalid_json": raw_args}
            tool_calls.append(
                ToolCallRequest(
                    id=call.get("id") or str(uuid4()),
                    name=call["function"]["name"],
                    arguments=arguments,
                    raw=call,
                )
            )
        return ProviderResponse(content=message.get("content"), tool_calls=tool_calls, raw_message=message)



class ScriptedProvider:
    mode = "scripted"

    def __init__(self, script: list[ProviderResponse]):
        self.script = list(script)
        self.index = 0

    def complete(self, messages: list[dict], tools: list[dict]) -> ProviderResponse:
        if self.index >= len(self.script):
            return ProviderResponse(content="Script exhausted; stopping.")
        item = self.script[self.index]
        self.index += 1
        return item


def _history(messages: list[dict]) -> list[dict]:
    pending = {}
    history = []
    for message in messages:
        if message.get("role") == "assistant" and message.get("tool_calls"):
            for call in message["tool_calls"]:
                pending[call["id"]] = {
                    "name": call["function"]["name"],
                    "arguments": json.loads(call["function"].get("arguments") or "{}"),
                }
        if message.get("role") == "tool":
            meta = pending.get(message.get("tool_call_id"), {})
            try:
                payload = json.loads(message.get("content") or "{}")
            except json.JSONDecodeError:
                payload = {"ok": False, "error": "unparseable tool payload"}
            history.append(
                {
                    "name": meta.get("name") or message.get("name"),
                    "arguments": payload.get("arguments") or meta.get("arguments") or {},
                    "ok": payload.get("ok", True),
                    "payload": payload,
                    "result": payload.get("result") if payload.get("ok") else None,
                    "code": payload.get("code"),
                }
            )
    return history


def _last(history: list[dict], name: str) -> dict | None:
    for item in reversed(history):
        if item["name"] == name:
            return item
    return None


def _call(name: str, arguments: dict, retry: bool = False) -> ProviderResponse:
    suffix = "retry" if retry else "call"
    return ProviderResponse(
        content=None,
        tool_calls=[ToolCallRequest(id=f"{name}-{suffix}-{uuid4().hex[:8]}", name=name, arguments=arguments)],
    )


def _present(title: str, events: list[dict], created: list[dict]) -> bool:
    needle = title.lower()
    for event in events:
        if needle in event.get("title", "").lower() or event.get("title", "").lower() in needle:
            return True
    for item in created:
        if not item["ok"] or not item["result"]:
            continue
        event = item["result"].get("event") or {}
        actual = event.get("title", "").lower()
        if needle in actual or actual in needle:
            return True
    return False


def _strip_tz(dt: datetime) -> datetime:
    """Remove timezone info for naive comparison (same-day overlap check)."""
    return dt.replace(tzinfo=None)


def _overlap_event(events: list[dict], args: dict) -> dict | None:
    try:
        start = _strip_tz(datetime.fromisoformat(args["start_time"]))
        end = _strip_tz(datetime.fromisoformat(args["end_time"]))
    except Exception:
        return None
    for event in events:
        try:
            other_start = _strip_tz(datetime.fromisoformat(event["start_time"]))
            other_end = _strip_tz(datetime.fromisoformat(event["end_time"]))
        except Exception:
            continue
        if start < other_end and other_start < end:
            return event
    return None


class DeterministicProvider:
    """Labeled development-mode planner. One tool call per step, driven by observations."""

    mode = "dev"

    def complete(self, messages: list[dict], tools: list[dict]) -> ProviderResponse:
        history = _history(messages)
        user_text = next((m["content"] for m in messages if m.get("role") == "user"), "")
        goal = user_text.split("User goal:", 1)[-1].split("Timezone:", 1)[0].strip()

        parsed_item = _last(history, "parse_goal")
        if parsed_item is None:
            return _call("parse_goal", {"goal": goal})
        if not parsed_item["ok"]:
            return ProviderResponse(content="I could not parse that goal. Please rephrase with a date and task durations.")
        parsed = parsed_item["result"]
        if parsed.get("blocking"):
            return ProviderResponse(
                content="I need clarification before changing the calendar. "
                + " ".join(parsed.get("ambiguities") or [])
            )

        date = parsed["date"]
        calendar_item = _last(history, "get_calendar")
        if calendar_item is None or not calendar_item["ok"]:
            return _call("get_calendar", {"date": date})

        tasks_item = _last(history, "get_tasks")
        if tasks_item is None:
            return _call("get_tasks", {})

        created = [item for item in history if item["name"] == "create_event"]
        last = history[-1]
        events = (calendar_item["result"] or {}).get("events") or []

        if last["name"] == "create_event" and not last["ok"]:
            if last.get("code") == "transient":
                return _call("create_event", last["arguments"], retry=True)
            if last.get("code") == "overlap":
                overlap = _overlap_event(events, last["arguments"])
                if overlap and not overlap.get("is_fixed"):
                    return _call(
                        "delete_event",
                        {
                            "event_id": overlap["id"],
                            "justification": "Non-fixed event overlaps a required meeting; removing the conflict block.",
                        },
                    )
                return ProviderResponse(
                    content=f"Blocked by a fixed calendar conflict: {last['payload'].get('error')}"
                )

        if last["name"] == "delete_event" and last["ok"]:
            failed = next((item for item in reversed(history) if item["name"] == "create_event" and not item["ok"]), None)
            if failed:
                return _call("create_event", failed["arguments"], retry=True)
            return _call("get_calendar", {"date": date})

        required = list(parsed.get("fixed_events") or []) + list(parsed.get("breaks") or [])
        for item in required:
            if _present(item["title"], events, created):
                continue
            return _call(
                "create_event",
                {
                    "title": item["title"],
                    "start_time": f"{date}T{item['start_time']}:00",
                    "end_time": f"{date}T{item['end_time']}:00",
                    "description": f"Scheduled from user goal ({item.get('kind')})",
                    "is_fixed": item.get("kind") == "fixed",
                },
            )

        flexible = parsed.get("tasks") or []
        proposal_item = _last(history, "propose_schedule")
        if flexible and proposal_item is None:
            return _call(
                "propose_schedule",
                {
                    "date": date,
                    "tasks": flexible,
                    "work_start": parsed.get("work_start"),
                    "work_end": parsed.get("work_end"),
                    "finish_by": parsed.get("finish_by"),
                },
            )

        if proposal_item and proposal_item["ok"]:
            for placement in proposal_item["result"].get("placements") or []:
                if _present(placement["title"], events, created):
                    continue
                return _call(
                    "create_event",
                    {
                        "title": placement["title"],
                        "start_time": placement["start_time"],
                        "end_time": placement["end_time"],
                        "description": "Flexible work block from Python scheduler",
                        "task_id": placement.get("task_id"),
                    },
                )

        verify_item = _last(history, "verify_schedule")
        expected = [{"title": t["title"], "duration_minutes": t["duration_minutes"]} for t in required + flexible]
        if verify_item is None:
            return _call(
                "verify_schedule",
                {
                    "date": date,
                    "expected_tasks": expected,
                    "work_start": parsed.get("work_start"),
                    "work_end": parsed.get("work_end"),
                    "finish_by": parsed.get("finish_by"),
                },
            )

        verify = verify_item["result"] or {}
        unresolved = []
        if proposal_item and proposal_item["ok"]:
            unresolved = proposal_item["result"].get("unresolved") or []
        missing = (verify.get("evidence") or {}).get("missing_titles") or []
        passed = bool(verify.get("passed"))
        status = "completed" if passed and not unresolved else "partially completed"
        lines = [
            f"Status: {status}.",
            f"Independent verification passed: {passed}.",
            f"Target date: {date}.",
        ]
        scheduled = (verify.get("evidence") or {}).get("scheduled_titles") or []
        if scheduled:
            lines.append("Persisted events matching the goal: " + ", ".join(scheduled))
        if unresolved:
            lines.append("Scheduler could not place: " + ", ".join(item["title"] for item in unresolved))
        if missing:
            lines.append("Missing during verification: " + ", ".join(missing))
        recoveries = [item for item in history if item["name"] == "delete_event" and item["ok"]]
        if recoveries:
            lines.append("Recovered from a conflict by removing a non-fixed overlapping event.")
        transients = [item for item in history if item.get("code") == "transient"]
        if transients:
            lines.append("Recovered from a transient create_event failure with a bounded retry.")
        lines.append("This report uses tool observations and SQLite state only.")
        return ProviderResponse(content="\n".join(lines))


def resolve_provider(settings: Settings, override: ModelProvider | None = None) -> ModelProvider:
    if override is not None:
        return override
    requested = (settings.llm_provider or "dev").lower()
    if requested == "openai" and settings.openai_api_key:
        return OpenAIProvider(settings)
    return DeterministicProvider()
