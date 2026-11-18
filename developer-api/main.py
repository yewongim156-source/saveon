from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

load_dotenv()

from database import Base, engine, get_db
from event_ingestion import ingest_event
from models import PipelineStep, TraceEvent, TraceSession
from schemas import (
    EventAccepted,
    EventDetail,
    OverviewResponse,
    StepDetail,
    TraceDetail,
    TraceEventIn,
    TraceSummary,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Save:On Developer API",
    version="0.1.0",
)

origins = [
    value.strip()
    for value in os.getenv(
        "DEVELOPER_CONSOLE_ORIGINS",
        "http://localhost:5173",
    ).split(",")
    if value.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Developer-Token"],
)


def verify_internal_token(
    x_developer_token: str | None = Header(default=None),
) -> None:
    expected = os.getenv("DEVELOPER_API_TOKEN", "").strip()
    if expected and x_developer_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효한 Developer API 토큰이 필요합니다.",
        )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "saveon-developer-api",
        "version": "0.1.0",
    }


@app.post(
    "/internal/events",
    response_model=EventAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_internal_token)],
)
def receive_event(
    event: TraceEventIn,
    db: Session = Depends(get_db),
):
    try:
        inserted = ingest_event(db, event)
        return EventAccepted(
            accepted=True,
            duplicate=not inserted,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get(
    "/admin/overview",
    response_model=OverviewResponse,
    dependencies=[Depends(verify_internal_token)],
)
def overview(db: Session = Depends(get_db)):
    total_sessions = db.scalar(select(func.count(TraceSession.id))) or 0
    active_sessions = db.scalar(
        select(func.count(TraceSession.id)).where(
            TraceSession.status == "RUNNING"
        )
    ) or 0
    completed_sessions = db.scalar(
        select(func.count(TraceSession.id)).where(
            TraceSession.status == "COMPLETED"
        )
    ) or 0
    failed_sessions = db.scalar(
        select(func.count(TraceSession.id)).where(
            TraceSession.status == "FAILED"
        )
    ) or 0
    total_steps = db.scalar(select(func.count(PipelineStep.id))) or 0
    total_errors = db.scalar(
        select(func.count(PipelineStep.id)).where(
            PipelineStep.status == "FAILED"
        )
    ) or 0
    estimated_cost = db.scalar(
        select(func.coalesce(func.sum(PipelineStep.estimated_cost_usd), 0.0))
    ) or 0.0
    average_duration = db.scalar(
        select(func.coalesce(func.avg(TraceSession.duration_ms), 0.0)).where(
            TraceSession.duration_ms.is_not(None)
        )
    ) or 0.0

    return OverviewResponse(
        totalSessions=int(total_sessions),
        activeSessions=int(active_sessions),
        completedSessions=int(completed_sessions),
        failedSessions=int(failed_sessions),
        totalSteps=int(total_steps),
        totalErrors=int(total_errors),
        estimatedCostUsd=float(estimated_cost),
        averageDurationMs=float(average_duration),
    )


def _trace_summary(trace: TraceSession, step_count: int) -> TraceSummary:
    return TraceSummary(
        id=trace.id,
        platform=trace.platform,
        status=trace.status,
        sourceHash=trace.source_hash,
        startedAt=trace.started_at,
        finishedAt=trace.finished_at,
        durationMs=trace.duration_ms,
        totalCostUsd=trace.total_cost_usd,
        error=trace.error,
        stepCount=step_count,
    )


@app.get(
    "/admin/traces",
    response_model=list[TraceSummary],
    dependencies=[Depends(verify_internal_token)],
)
def list_traces(
    trace_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    step_count = (
        select(func.count(PipelineStep.id))
        .where(PipelineStep.trace_id == TraceSession.id)
        .correlate(TraceSession)
        .scalar_subquery()
    )
    query = select(TraceSession, step_count).order_by(
        TraceSession.started_at.desc()
    )
    if trace_status:
        query = query.where(TraceSession.status == trace_status.upper())

    return [
        _trace_summary(trace, int(count or 0))
        for trace, count in db.execute(query.limit(limit)).all()
    ]


@app.get(
    "/admin/traces/{trace_id}",
    response_model=TraceDetail,
    dependencies=[Depends(verify_internal_token)],
)
def get_trace(trace_id: str, db: Session = Depends(get_db)):
    trace = db.get(TraceSession, trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace를 찾을 수 없습니다.")

    steps = db.scalars(
        select(PipelineStep)
        .where(PipelineStep.trace_id == trace_id)
        .order_by(PipelineStep.started_at.asc())
    ).all()
    events = db.scalars(
        select(TraceEvent)
        .where(TraceEvent.trace_id == trace_id)
        .order_by(TraceEvent.occurred_at.asc())
    ).all()

    summary = _trace_summary(trace, len(steps))
    return TraceDetail(
        **summary.model_dump(),
        steps=[
            StepDetail(
                id=step.id,
                parentStepId=step.parent_step_id,
                kind=step.kind,
                name=step.name,
                status=step.status,
                model=step.model,
                promptVersion=step.prompt_version,
                inputSummary=step.input_summary,
                outputSummary=step.output_summary,
                inputTokens=step.input_tokens,
                outputTokens=step.output_tokens,
                estimatedCostUsd=step.estimated_cost_usd,
                startedAt=step.started_at,
                finishedAt=step.finished_at,
                durationMs=step.duration_ms,
                error=step.error,
            )
            for step in steps
        ],
        events=[
            EventDetail(
                id=event.id,
                stepId=event.step_id,
                eventType=event.event_type,
                occurredAt=event.occurred_at,
                data=json.loads(event.payload_json),
            )
            for event in events
        ],
    )
