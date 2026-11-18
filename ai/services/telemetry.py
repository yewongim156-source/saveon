from __future__ import annotations

import atexit
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from queue import Empty, Full, Queue
from threading import Event, Thread
import time
from typing import Any, Iterator
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import uuid4
from services.analysis_progress import mark_pipeline_step


TELEMETRY_ENABLED = os.getenv(
    "DEVELOPER_TELEMETRY_ENABLED",
    "false",
).lower() in {"1", "true", "yes", "on"}
DEVELOPER_API_URL = os.getenv(
    "DEVELOPER_API_URL",
    "http://localhost:8100",
).rstrip("/")
DEVELOPER_API_TOKEN = os.getenv("DEVELOPER_API_TOKEN", "").strip()

_TRACE_ID: ContextVar[str | None] = ContextVar(
    "saveon_trace_id",
    default=None,
)
_STEP_ID: ContextVar[str | None] = ContextVar(
    "saveon_step_id",
    default=None,
)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_value(value: Any, depth: int = 0) -> Any:
    if depth >= 3:
        return "[truncated]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:2000]
    if isinstance(value, dict):
        return {
            str(key)[:100]: _safe_value(item, depth + 1)
            for key, item in list(value.items())[:30]
        }
    if isinstance(value, (list, tuple, set)):
        return [_safe_value(item, depth + 1) for item in list(value)[:30]]
    return str(value)[:500]


class TelemetryClient:
    def __init__(self) -> None:
        self.enabled = TELEMETRY_ENABLED
        self.queue: Queue[dict | None] = Queue(maxsize=1000)
        self.stop_event = Event()
        self.worker: Thread | None = None

        if self.enabled:
            self.worker = Thread(
                target=self._run,
                name="saveon-telemetry",
                daemon=True,
            )
            self.worker.start()

    def emit(self, payload: dict) -> None:
        if not self.enabled:
            return
        try:
            self.queue.put_nowait(payload)
        except Full:
            print("[TELEMETRY] 큐가 가득 차 이벤트를 버렸습니다.")

    def _send(self, payload: dict) -> None:
        body = json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if DEVELOPER_API_TOKEN:
            headers["X-Developer-Token"] = DEVELOPER_API_TOKEN

        request = Request(
            f"{DEVELOPER_API_URL}/internal/events",
            data=body,
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=1.5) as response:
            response.read()

    def _run(self) -> None:
        while not self.stop_event.is_set() or not self.queue.empty():
            try:
                payload = self.queue.get(timeout=0.2)
            except Empty:
                continue
            if payload is None:
                self.queue.task_done()
                continue
            try:
                self._send(payload)
            except (OSError, URLError, TimeoutError) as exc:
                print(f"[TELEMETRY] 전송 실패 - 분석은 계속 진행: {exc}")
            finally:
                self.queue.task_done()

    def flush(self, timeout_seconds: float = 2.0) -> None:
        if not self.enabled:
            return
        deadline = time.monotonic() + timeout_seconds
        while self.queue.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(0.02)

    def close(self) -> None:
        if not self.enabled:
            return
        self.flush()
        self.stop_event.set()
        try:
            self.queue.put_nowait(None)
        except Full:
            pass
        if self.worker:
            self.worker.join(timeout=1.0)


CLIENT = TelemetryClient()
atexit.register(CLIENT.close)


def current_trace_id() -> str | None:
    return _TRACE_ID.get()


def _event(
    event_type: str,
    *,
    trace_id: str,
    step_id: str | None = None,
    data: dict | None = None,
) -> dict:
    return {
        "eventId": str(uuid4()),
        "traceId": trace_id,
        "stepId": step_id,
        "eventType": event_type,
        "occurredAt": _utc_iso(),
        "data": _safe_value(data or {}),
    }


@contextmanager
def trace_session(
    *,
    platform: str,
    source_url: str = "",
    content_id: str | None = None,
) -> Iterator[str]:
    trace_id = str(uuid4())
    token = _TRACE_ID.set(trace_id)
    started = time.monotonic()
    source_hash = (
        hashlib.sha256(source_url.encode("utf-8")).hexdigest()
        if source_url
        else None
    )

    CLIENT.emit(_event(
        "TRACE_STARTED",
        trace_id=trace_id,
        data={
            "platform": platform,
            "sourceHash": source_hash,
            "contentId": content_id,
        },
    ))

    try:
        yield trace_id
    except Exception as exc:
        CLIENT.emit(_event(
            "TRACE_FAILED",
            trace_id=trace_id,
            data={
                "durationMs": int((time.monotonic() - started) * 1000),
                "error": str(exc),
            },
        ))
        raise
    else:
        CLIENT.emit(_event(
            "TRACE_FINISHED",
            trace_id=trace_id,
            data={
                "durationMs": int((time.monotonic() - started) * 1000),
            },
        ))
    finally:
        _TRACE_ID.reset(token)


@dataclass
class StepRecorder:
    trace_id: str | None
    step_id: str | None
    output_summary: Any = None
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def set_output(self, value: Any) -> None:
        self.output_summary = _safe_value(value)

    def set_usage(
        self,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        estimated_cost_usd: float = 0.0,
    ) -> None:
        self.input_tokens = max(0, int(input_tokens))
        self.output_tokens = max(0, int(output_tokens))
        self.estimated_cost_usd = max(0.0, float(estimated_cost_usd))


@contextmanager
def pipeline_step(
    name: str,
    *,
    kind: str,
    model: str | None = None,
    prompt_version: str | None = None,
    input_summary: Any = None,
) -> Iterator[StepRecorder]:
    trace_id = _TRACE_ID.get()
    if not trace_id:
        yield StepRecorder(None, None)
        return

    # save:on TRUE_PROGRESS_V1: only real pipeline steps advance the UI.
    mark_pipeline_step(name)
    step_id = str(uuid4())
    parent_step_id = _STEP_ID.get()
    token = _STEP_ID.set(step_id)
    started = time.monotonic()
    recorder = StepRecorder(trace_id, step_id)

    CLIENT.emit(_event(
        "STEP_STARTED",
        trace_id=trace_id,
        step_id=step_id,
        data={
            "parentStepId": parent_step_id,
            "kind": kind.upper(),
            "name": name,
            "model": model,
            "promptVersion": prompt_version,
            "inputSummary": _safe_value(input_summary),
        },
    ))

    try:
        yield recorder
    except Exception as exc:
        CLIENT.emit(_event(
            "STEP_FAILED",
            trace_id=trace_id,
            step_id=step_id,
            data={
                "kind": kind.upper(),
                "name": name,
                "durationMs": int((time.monotonic() - started) * 1000),
                "error": str(exc),
            },
        ))
        raise
    else:
        CLIENT.emit(_event(
            "STEP_FINISHED",
            trace_id=trace_id,
            step_id=step_id,
            data={
                "durationMs": int((time.monotonic() - started) * 1000),
                "outputSummary": recorder.output_summary,
                "inputTokens": recorder.input_tokens,
                "outputTokens": recorder.output_tokens,
                "estimatedCostUsd": recorder.estimated_cost_usd,
                **recorder.extra,
            },
        ))
    finally:
        _STEP_ID.reset(token)

# save:on TRUE_PROGRESS_V1
