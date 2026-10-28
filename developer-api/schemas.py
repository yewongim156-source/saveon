from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


EventType = Literal[
    "TRACE_STARTED",
    "TRACE_FINISHED",
    "TRACE_FAILED",
    "STEP_STARTED",
    "STEP_FINISHED",
    "STEP_FAILED",
]


class TraceEventIn(BaseModel):
    eventId: str = Field(min_length=1, max_length=36)
    traceId: str = Field(min_length=1, max_length=36)
    stepId: str | None = Field(default=None, max_length=36)
    eventType: EventType
    occurredAt: datetime
    data: dict[str, Any] = Field(default_factory=dict)


class EventAccepted(BaseModel):
    accepted: bool
    duplicate: bool = False


class OverviewResponse(BaseModel):
    totalSessions: int
    activeSessions: int
    completedSessions: int
    failedSessions: int
    totalSteps: int
    totalErrors: int
    estimatedCostUsd: float
    averageDurationMs: float


class TraceSummary(BaseModel):
    id: str
    platform: str
    status: str
    sourceHash: str | None
    startedAt: datetime
    finishedAt: datetime | None
    durationMs: int | None
    totalCostUsd: float
    error: str | None
    stepCount: int


class StepDetail(BaseModel):
    id: str
    parentStepId: str | None
    kind: str
    name: str
    status: str
    model: str | None
    promptVersion: str | None
    inputSummary: str | None
    outputSummary: str | None
    inputTokens: int
    outputTokens: int
    estimatedCostUsd: float
    startedAt: datetime
    finishedAt: datetime | None
    durationMs: int | None
    error: str | None


class EventDetail(BaseModel):
    id: str
    stepId: str | None
    eventType: str
    occurredAt: datetime
    data: dict[str, Any]


class TraceDetail(TraceSummary):
    steps: list[StepDetail]
    events: list[EventDetail]
