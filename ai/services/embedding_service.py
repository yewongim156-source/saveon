from __future__ import annotations

from collections import OrderedDict
from hashlib import sha256
import math
import os
import threading
import time

from google.genai import types

from services.llm_postprocessor import (
    GEMINI_API_KEY,
    create_gemini_client,
)


EMBEDDING_MODEL = os.getenv(
    "GEMINI_EMBEDDING_MODEL",
    "gemini-embedding-2",
)
EMBEDDING_DIMENSIONS = int(
    os.getenv("GEMINI_EMBEDDING_DIMENSIONS", "768")
)

EMBEDDING_CACHE_TTL_SECONDS = int(
    os.getenv("EMBEDDING_CACHE_TTL_SECONDS", "600")
)
EMBEDDING_CACHE_MAX_ITEMS = int(
    os.getenv("EMBEDDING_CACHE_MAX_ITEMS", "256")
)
EMBEDDING_FAILURE_COOLDOWN_SECONDS = float(
    os.getenv("EMBEDDING_FAILURE_COOLDOWN_SECONDS", "8")
)

_CACHE: "OrderedDict[str, tuple[float, dict]]" = OrderedDict()
_CACHE_LOCK = threading.Lock()
_FAILURE_LOCK = threading.Lock()
_LAST_FAILURE_AT = 0.0
_LAST_FAILURE_MESSAGE = ""


def _normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0:
        raise RuntimeError("임베딩 벡터의 크기가 0입니다.")
    return [value / norm for value in values]


def _cache_key(cleaned: str) -> str:
    payload = (
        EMBEDDING_MODEL
        + "|"
        + str(EMBEDDING_DIMENSIONS)
        + "|"
        + cleaned
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def _get_cached(key: str) -> dict | None:
    if EMBEDDING_CACHE_TTL_SECONDS <= 0:
        return None

    now = time.monotonic()
    with _CACHE_LOCK:
        item = _CACHE.get(key)
        if item is None:
            return None

        created_at, value = item
        if now - created_at > EMBEDDING_CACHE_TTL_SECONDS:
            _CACHE.pop(key, None)
            return None

        _CACHE.move_to_end(key)
        return {
            "model": value["model"],
            "dimensions": value["dimensions"],
            "vector": list(value["vector"]),
        }


def _put_cached(key: str, value: dict) -> None:
    if EMBEDDING_CACHE_MAX_ITEMS <= 0:
        return

    with _CACHE_LOCK:
        _CACHE[key] = (
            time.monotonic(),
            {
                "model": value["model"],
                "dimensions": value["dimensions"],
                "vector": list(value["vector"]),
            },
        )
        _CACHE.move_to_end(key)

        while len(_CACHE) > EMBEDDING_CACHE_MAX_ITEMS:
            _CACHE.popitem(last=False)


def _raise_if_in_failure_cooldown() -> None:
    if EMBEDDING_FAILURE_COOLDOWN_SECONDS <= 0:
        return

    with _FAILURE_LOCK:
        elapsed = time.monotonic() - _LAST_FAILURE_AT
        if (
            _LAST_FAILURE_AT > 0
            and elapsed < EMBEDDING_FAILURE_COOLDOWN_SECONDS
        ):
            remaining = (
                EMBEDDING_FAILURE_COOLDOWN_SECONDS - elapsed
            )
            raise RuntimeError(
                "임베딩 API가 잠시 불안정해 재호출을 제한하고 있습니다. "
                f"{remaining:.1f}초 후 다시 시도해 주세요. "
                f"이전 오류: {_LAST_FAILURE_MESSAGE[:180]}"
            )


def _remember_failure(exc: Exception) -> None:
    global _LAST_FAILURE_AT, _LAST_FAILURE_MESSAGE
    with _FAILURE_LOCK:
        _LAST_FAILURE_AT = time.monotonic()
        _LAST_FAILURE_MESSAGE = str(exc)


def _clear_failure() -> None:
    global _LAST_FAILURE_AT, _LAST_FAILURE_MESSAGE
    with _FAILURE_LOCK:
        _LAST_FAILURE_AT = 0.0
        _LAST_FAILURE_MESSAGE = ""


def embed_text(text: str) -> dict:
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        raise ValueError("임베딩할 텍스트가 비어 있습니다.")
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY가 설정되어 있지 않습니다.")
    if EMBEDDING_DIMENSIONS <= 0:
        raise RuntimeError(
            "GEMINI_EMBEDDING_DIMENSIONS는 0보다 커야 합니다."
        )

    cleaned = cleaned[:12000]
    key = _cache_key(cleaned)

    cached = _get_cached(key)
    if cached is not None:
        print("[EMBED] cache hit")
        return cached

    _raise_if_in_failure_cooldown()

    try:
        client = create_gemini_client()
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=cleaned,
            config=types.EmbedContentConfig(
                output_dimensionality=EMBEDDING_DIMENSIONS,
            ),
        )

        if not response.embeddings:
            raise RuntimeError("Gemini 임베딩 응답이 비어 있습니다.")

        values = response.embeddings[0].values
        if not values:
            raise RuntimeError("Gemini 임베딩 벡터가 비어 있습니다.")

        vector = _normalize([float(value) for value in values])
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise RuntimeError(
                "Gemini 임베딩 차원이 설정과 일치하지 않습니다: "
                f"expected={EMBEDDING_DIMENSIONS}, actual={len(vector)}"
            )

        result = {
            "model": EMBEDDING_MODEL,
            "dimensions": EMBEDDING_DIMENSIONS,
            "vector": vector,
        }

        _put_cached(key, result)
        _clear_failure()
        return result

    except Exception as exc:
        _remember_failure(exc)
        raise
