from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import PipelineStep, TraceEvent, TraceSession
from schemas import TraceEventIn


def _text(value, max_length: int = 4000) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        rendered = value
    else:
        rendered = json.dumps(value, ensure_ascii=False, default=str)
    return rendered[:max_length]


def _ensure_trace(db: Session, event: TraceEventIn) -> TraceSession:
    trace = db.get(TraceSession, event.traceId)
    if trace is None:
        trace = TraceSession(
            id=event.traceId,
            platform=str(event.data.get("platform", "UNKNOWN"))[:30],
            source_hash=_text(event.data.get("sourceHash"), 64),
            status="RUNNING",
            started_at=event.occurredAt,
        )
        db.add(trace)
        db.flush()
    return trace


def _update_trace_totals(db: Session, trace: TraceSession) -> None:
    total = db.scalar(
        select(func.coalesce(func.sum(PipelineStep.estimated_cost_usd), 0.0))
        .where(PipelineStep.trace_id == trace.id)
    )
    trace.total_cost_usd = float(total or 0.0)


def ingest_event(db: Session, event: TraceEventIn) -> bool:
    if db.get(TraceEvent, event.eventId) is not None:
        return False

    trace = _ensure_trace(db, event)
    data = event.data

    if event.eventType == "TRACE_STARTED":
        trace.platform = str(data.get("platform", trace.platform))[:30]
        trace.source_hash = _text(data.get("sourceHash"), 64)
        trace.content_id = _text(data.get("contentId"), 100)
        trace.status = "RUNNING"
        trace.started_at = event.occurredAt

    elif event.eventType in {"TRACE_FINISHED", "TRACE_FAILED"}:
        trace.status = (
            "COMPLETED"
            if event.eventType == "TRACE_FINISHED"
            else "FAILED"
        )
        trace.finished_at = event.occurredAt
        trace.duration_ms = int(data.get("durationMs", 0))
        trace.error = _text(data.get("error"), 2000)
        _update_trace_totals(db, trace)

    elif event.eventType == "STEP_STARTED":
        step_id = event.stepId
        if not step_id:
            raise ValueError("STEP_STARTED에는 stepId가 필요합니다.")
        step = db.get(PipelineStep, step_id)
        if step is None:
            step = PipelineStep(
                id=step_id,
                trace_id=event.traceId,
                parent_step_id=_text(data.get("parentStepId"), 36),
                kind=str(data.get("kind", "TOOL"))[:20],
                name=str(data.get("name", "unknown"))[:100],
                status="RUNNING",
                model=_text(data.get("model"), 120),
                prompt_version=_text(data.get("promptVersion"), 80),
                input_summary=_text(data.get("inputSummary")),
                started_at=event.occurredAt,
            )
            db.add(step)

    elif event.eventType in {"STEP_FINISHED", "STEP_FAILED"}:
        if not event.stepId:
            raise ValueError(f"{event.eventType}에는 stepId가 필요합니다.")
        step = db.get(PipelineStep, event.stepId)
        if step is None:
            step = PipelineStep(
                id=event.stepId,
                trace_id=event.traceId,
                kind=str(data.get("kind", "TOOL"))[:20],
                name=str(data.get("name", "unknown"))[:100],
                status="RUNNING",
                started_at=event.occurredAt,
            )
            db.add(step)

        step.status = (
            "COMPLETED"
            if event.eventType == "STEP_FINISHED"
            else "FAILED"
        )
        step.finished_at = event.occurredAt
        step.duration_ms = int(data.get("durationMs", 0))
        step.output_summary = _text(data.get("outputSummary"))
        step.input_tokens = int(data.get("inputTokens", 0))
        step.output_tokens = int(data.get("outputTokens", 0))
        step.estimated_cost_usd = float(data.get("estimatedCostUsd", 0.0))
        step.error = _text(data.get("error"), 2000)

    db.add(TraceEvent(
        id=event.eventId,
        trace_id=event.traceId,
        step_id=event.stepId,
        event_type=event.eventType,
        occurred_at=event.occurredAt,
        payload_json=json.dumps(data, ensure_ascii=False, default=str),
    ))
    db.commit()
    return True
