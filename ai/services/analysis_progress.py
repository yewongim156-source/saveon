"""In-process, request-scoped live analysis stages for development mode.

Only stage names and content IDs are stored; no URL, transcript, title, or
other user data. This registry is deliberately non-durable and expects a single
FastAPI worker. The Spring content status remains the source of truth for
completion/failure.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Iterator

_ACTIVE_ID: ContextVar[int | None] = ContextVar("analysis_progress_content_id", default=None)
_LOCK = Lock()
_ITEMS: dict[int, dict] = {}
_TTL_SECONDS = 60 * 60 * 2
_MAX_ITEMS = 512

_ORDER = {
    "STARTING": 0,
    "DOWNLOADING": 1,
    "TRANSCRIBING": 2,
    "READING_SCREEN": 3,
    "SUMMARIZING": 4,
    "FINALIZING": 5,
}


def _parse_id(content_id: str | int | None) -> int | None:
    try:
        number = int(content_id) if content_id is not None else 0
    except (ValueError, TypeError, OverflowError):
        return None
    return number if 0 < number <= 2**63 - 1 else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cleanup() -> None:
    """Call while holding _LOCK."""
    now = monotonic()
    for key, item in list(_ITEMS.items()):
        if now - item["_at"] > _TTL_SECONDS:
            del _ITEMS[key]
    if len(_ITEMS) > _MAX_ITEMS:
        oldest = sorted(_ITEMS, key=lambda k: _ITEMS[k]["_at"])
        for key in oldest[: len(_ITEMS) - _MAX_ITEMS]:
            del _ITEMS[key]


def _update(content_id: int, stage: str) -> None:
    with _LOCK:
        previous = _ITEMS.get(content_id)
        if previous and stage != "FAILED":
            previous_stage = previous["stage"]
            if previous_stage == "FAILED":
                return
            if _ORDER.get(stage, -1) < _ORDER.get(previous_stage, -1):
                return
        _ITEMS[content_id] = {
            "stage": stage,
            "updatedAt": _now(),
            "_at": monotonic(),
        }
        _cleanup()


@contextmanager
def progress_scope(content_id: str | int | None) -> Iterator[None]:
    """Start/reset a job, isolating concurrent requests via ContextVar."""
    parsed = _parse_id(content_id)
    if parsed is None:
        yield
        return
    with _LOCK:
        # A re-analysis for the same content ID must discard the old stage.
        _ITEMS[parsed] = {"stage": "STARTING", "updatedAt": _now(), "_at": monotonic()}
        _cleanup()
    token = _ACTIVE_ID.set(parsed)
    try:
        yield
    except BaseException:
        _update(parsed, "FAILED")
        raise
    else:
        # AI responded; Java still has to embed and persist the result.
        _update(parsed, "FINALIZING")
    finally:
        _ACTIVE_ID.reset(token)


def mark_pipeline_step(name: str) -> None:
    content_id = _ACTIVE_ID.get()
    if content_id is None:
        return
    if name == "source-download":
        stage = "DOWNLOADING"
    elif name == "speech-to-text":
        stage = "TRANSCRIBING"
    elif name in {"frame-sampling", "screen-text-ocr", "visual-classification"}:
        stage = "READING_SCREEN"
    elif name == "content-structuring" or name.startswith("fact-verification") or name.startswith("verified-summary"):
        stage = "SUMMARIZING"
    else:
        return
    _update(content_id, stage)


def get_progress(content_id: int) -> dict:
    parsed = _parse_id(content_id)
    if parsed is None:
        return {"contentId": content_id, "stage": "UNKNOWN", "updatedAt": None}
    with _LOCK:
        _cleanup()
        item = _ITEMS.get(parsed)
        if item is None:
            return {"contentId": parsed, "stage": "UNKNOWN", "updatedAt": None}
        return {"contentId": parsed, "stage": item["stage"], "updatedAt": item["updatedAt"]}
