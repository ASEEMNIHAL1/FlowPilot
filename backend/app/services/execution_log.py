from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import AgentRun, ToolLog, VerificationResult


def log_tool(
    db: Session,
    *,
    run_id: int,
    step_index: int,
    tool_name: str,
    arguments: dict,
    result: dict | None,
    success: bool,
    error: str | None = None,
    is_retry: bool = False,
) -> ToolLog:
    entry = ToolLog(
        run_id=run_id,
        step_index=step_index,
        tool_name=tool_name,
        arguments=arguments,
        result=result,
        success=success,
        error=error,
        is_retry=is_retry,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def save_verification(db: Session, run_id: int, payload: dict) -> VerificationResult:
    row = VerificationResult(
        run_id=run_id,
        passed=payload["passed"],
        checks=payload["checks"],
        summary=payload["summary"],
        evidence=payload.get("evidence"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def touch_run(db: Session, run: AgentRun, **fields) -> AgentRun:
    for key, value in fields.items():
        setattr(run, key, value)
    run.updated_at = datetime.now(timezone.utc)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run
