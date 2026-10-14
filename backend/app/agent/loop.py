from __future__ import annotations

import json
import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.agent.prompts import SYSTEM_PROMPT, user_prompt
from app.agent.provider import ModelProvider, resolve_provider
from app.config import Settings
from app.models import AgentRun
from app.services.execution_log import log_tool, save_verification, touch_run
from app.services.verifier import verify_schedule
from app.tools.registry import ToolContext, ToolError
from app.tools.calendar import build_registry


def _safe_json(value) -> str:
    return json.dumps(value, default=str)


def _fingerprint(name: str, arguments: dict) -> str:
    return f"{name}:{json.dumps(arguments, sort_keys=True, default=str)}"


def execute_run(
    db: Session,
    settings: Settings,
    goal: str,
    *,
    date_hint: str | None = None,
    provider: ModelProvider | None = None,
    inject_create_failures: int = 0,
) -> AgentRun:
    model = resolve_provider(settings, provider)
    run = AgentRun(
        goal=goal,
        status="executing",
        provider_mode=model.mode,
        target_date=date_hint,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    registry = build_registry()
    ctx = ToolContext(
        db=db,
        settings=settings,
        run_id=run.id,
        inject_create_failures=inject_create_failures,
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": user_prompt(goal, settings.timezone, settings.work_start, settings.work_end),
        },
    ]
    started = time.monotonic()
    step = 0
    invalid = 0
    seen_success: set[str] = set()
    expected_for_verify: list[dict] = []
    parsed = None

    try:
        for _ in range(settings.max_tool_calls):
            db.refresh(run)
            if run.cancel_requested:
                touch_run(db, run, status="blocked", error_message="Cancelled by user")
                break
            if time.monotonic() - started > settings.run_timeout_seconds:
                touch_run(db, run, status="failed", error_message="Run exceeded timeout")
                break

            response = model.complete(messages, registry.schemas())
            if response.tool_calls:
                if response.raw_message is not None:
                    messages.append(response.raw_message)
                else:
                    openai_calls = []
                    for call in response.tool_calls:
                        call_dict = {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": _safe_json(call.arguments),
                            },
                        }
                        if call.raw and "extra_content" in call.raw:
                            call_dict["extra_content"] = call.raw["extra_content"]
                        openai_calls.append(call_dict)
                    messages.append({"role": "assistant", "content": response.content, "tool_calls": openai_calls})

                for call in response.tool_calls:
                    step += 1
                    is_retry = ":retry" in call.id or any(
                        log.tool_name == call.name and not log.success
                        for log in run.tool_logs
                    )
                    fingerprint = _fingerprint(call.name, call.arguments)
                    if call.name == "create_event" and fingerprint in seen_success:
                        payload = {
                            "ok": True,
                            "duplicate_prevented": True,
                            "result": {"created": False, "duplicate": True, "reason": "identical create already succeeded in this run"},
                            "arguments": call.arguments,
                        }
                        log_tool(
                            db,
                            run_id=run.id,
                            step_index=step,
                            tool_name=call.name,
                            arguments=call.arguments,
                            result=payload,
                            success=True,
                            is_retry=True,
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call.id,
                                "name": call.name,
                                "content": _safe_json(payload),
                            }
                        )
                        continue
                    try:
                        result = registry.execute(call.name, call.arguments, ctx)
                        wrapped = {"ok": True, "result": result, "arguments": call.arguments}
                        log_tool(
                            db,
                            run_id=run.id,
                            step_index=step,
                            tool_name=call.name,
                            arguments=call.arguments,
                            result=result,
                            success=True,
                            is_retry=bool(is_retry),
                        )
                        if call.name in {"create_event", "update_event", "delete_event"}:
                            seen_success.add(fingerprint)
                        if call.name == "parse_goal":
                            parsed = result
                            run = touch_run(
                                db,
                                run,
                                parsed_requirements=result,
                                target_date=result.get("date") or date_hint,
                            )
                            expected_for_verify = [
                                {"title": item["title"], "duration_minutes": item["duration_minutes"]}
                                for item in (result.get("fixed_events") or [])
                                + (result.get("breaks") or [])
                                + (result.get("tasks") or [])
                            ]
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call.id,
                                "name": call.name,
                                "content": _safe_json(wrapped),
                            }
                        )
                    except ToolError as exc:
                        invalid += int(exc.code in {"unknown_tool", "invalid_args"})
                        wrapped = {
                            "ok": False,
                            "error": str(exc),
                            "code": exc.code,
                            "arguments": call.arguments,
                        }
                        log_tool(
                            db,
                            run_id=run.id,
                            step_index=step,
                            tool_name=call.name,
                            arguments=call.arguments,
                            result=wrapped,
                            success=False,
                            error=str(exc),
                            is_retry=bool(is_retry),
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call.id,
                                "name": call.name,
                                "content": _safe_json(wrapped),
                            }
                        )
                        if invalid >= settings.max_invalid_tool_calls:
                            touch_run(db, run, status="failed", error_message="Too many invalid tool calls")
                            return _finalize(db, settings, run, parsed, expected_for_verify, "failed")
                continue

            content = (response.content or "").strip()
            messages.append({"role": "assistant", "content": content})
            return _finalize(db, settings, run, parsed, expected_for_verify, None, assistant_text=content)

        if run.status == "executing":
            touch_run(db, run, status="failed", error_message="Reached maximum tool-call limit")
        return _finalize(db, settings, run, parsed, expected_for_verify, run.status)
    except Exception as exc:  # noqa: BLE001 — persist failure, do not crash the API
        touch_run(db, run, status="failed", error_message=str(exc))
        return run


def _finalize(
    db: Session,
    settings: Settings,
    run: AgentRun,
    parsed: dict | None,
    expected: list[dict],
    forced_status: str | None,
    assistant_text: str | None = None,
) -> AgentRun:
    db.refresh(run)
    target = run.target_date
    verification = None
    if target and expected:
        from datetime import date as date_cls

        verification = verify_schedule(
            db,
            day=date_cls.fromisoformat(target),
            expected_tasks=expected,
            settings=settings,
            work_start=(parsed or {}).get("work_start"),
            work_end=(parsed or {}).get("work_end"),
            finish_by=(parsed or {}).get("finish_by"),
            report_claims=None,
        )
        save_verification(db, run.id, verification)

    unresolved = []
    missing = []
    passed = False
    if verification:
        passed = verification["passed"]
        missing = verification.get("evidence", {}).get("missing_titles") or []
        unresolved = missing

    has_successful_writes = any(
        log.success and log.tool_name in {"create_event", "update_event", "delete_event"}
        for log in run.tool_logs
    )

    if parsed and parsed.get("blocking"):
        status = "blocked"
    elif forced_status in {"failed", "blocked"}:
        status = forced_status
    elif passed and not unresolved:
        status = "verified"
    elif expected and (passed or not missing):
        status = "partially_completed" if unresolved else "completed"
    elif assistant_text and not expected and not has_successful_writes and parsed is None:
        # Goal was never parsed and agent gave text with no tool work — genuinely ambiguous
        status = "blocked"
    elif assistant_text:
        # Agent gave a text summary (possibly after tool work); treat as completed
        status = "completed" if has_successful_writes else "partially_completed"
    else:
        status = "partially_completed" if run.tool_logs else (forced_status or "failed")

    report = {
        "outcome": status,
        "provider_mode": run.provider_mode,
        "goal": run.goal,
        "target_date": target,
        "parsed_requirements": parsed,
        "assistant_summary": assistant_text,
        "verification_passed": passed,
        "missing_titles": missing,
        "scheduled_titles": (verification or {}).get("evidence", {}).get("scheduled_titles") if verification else [],
        "tool_call_count": len(run.tool_logs),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "notes": [
            "Final report is bound to persisted SQLite calendar rows and verification checks.",
            "Development mode uses a deterministic planner when no LLM key is configured."
            if run.provider_mode == "dev"
            else "LLM selected tools; Python enforced time constraints.",
        ],
    }
    if parsed and parsed.get("documented_defaults"):
        report["documented_defaults"] = parsed["documented_defaults"]
    if parsed and parsed.get("ambiguities"):
        report["ambiguities"] = parsed["ambiguities"]

    return touch_run(db, run, status=status, final_report=report, parsed_requirements=parsed or run.parsed_requirements)
