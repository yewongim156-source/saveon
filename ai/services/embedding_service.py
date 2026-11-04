from __future__ import annotations

import math
import os

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


def _normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0:
        raise RuntimeError("임베딩 벡터의 크기가 0입니다.")
    return [value / norm for value in values]


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

    client = create_gemini_client()
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=cleaned[:12000],
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

    return {
        "model": EMBEDDING_MODEL,
        "dimensions": EMBEDDING_DIMENSIONS,
        "vector": vector,
    }

