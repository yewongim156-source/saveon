from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field


ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.1-flash-lite",
)

CACHE_TTL_SECONDS = int(
    os.getenv("INTEREST_AGENT_CACHE_TTL_SECONDS", "1800")
)
CACHE_MAX_ITEMS = int(
    os.getenv("INTEREST_AGENT_CACHE_MAX_ITEMS", "128")
)


class RelatedEntityInput(BaseModel):
    entity: str
    type: str
    count: int


class HighlightInput(BaseModel):
    contentId: int
    title: str
    summary: str


class InterestSynthesisRequest(BaseModel):
    entity: str
    type: str
    count: int
    fallbackOverview: str = ""
    categories: list[str] = Field(default_factory=list)
    commonKeywords: list[str] = Field(default_factory=list)
    commonTags: list[str] = Field(default_factory=list)
    relatedEntities: list[RelatedEntityInput] = Field(default_factory=list)
    highlights: list[HighlightInput] = Field(default_factory=list)


class InterestSynthesisResponse(BaseModel):
    summary: str
    keyInterests: list[str] = Field(default_factory=list)
    takeaways: list[str] = Field(default_factory=list)


_CACHE: dict[str, tuple[float, InterestSynthesisResponse]] = {}


def _cache_key(request: InterestSynthesisRequest) -> str:
    payload = request.model_dump(mode="json")
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _get_cached(key: str) -> InterestSynthesisResponse | None:
    cached = _CACHE.get(key)
    if not cached:
        return None

    saved_at, value = cached
    if time.time() - saved_at > CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        return None

    return value


def _put_cached(key: str, value: InterestSynthesisResponse) -> None:
    if len(_CACHE) >= CACHE_MAX_ITEMS:
        oldest_key = min(
            _CACHE,
            key=lambda item: _CACHE[item][0],
        )
        _CACHE.pop(oldest_key, None)

    _CACHE[key] = (time.time(), value)


def _clean_string_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []

    result: list[str] = []
    seen: set[str] = set()

    for item in value:
        text = " ".join(str(item).split()).strip()
        if not text:
            continue

        normalized = text.lower()
        if normalized in seen:
            continue

        seen.add(normalized)
        result.append(text)

        if len(result) >= limit:
            break

    return result


def _normalize_result(raw: dict[str, Any]) -> InterestSynthesisResponse:
    summary = " ".join(str(raw.get("summary", "")).split()).strip()
    key_interests = _clean_string_list(
        raw.get("keyInterests", []),
        5,
    )
    takeaways = _clean_string_list(
        raw.get("takeaways", []),
        5,
    )

    if not summary:
        raise RuntimeError("Interest Agent 요약이 비어 있습니다.")

    return InterestSynthesisResponse(
        summary=summary[:600],
        keyInterests=[item[:80] for item in key_interests],
        takeaways=[item[:220] for item in takeaways],
    )


def synthesize_interest(
    request: InterestSynthesisRequest,
) -> tuple[InterestSynthesisResponse, bool]:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY가 설정되어 있지 않습니다.")

    key = _cache_key(request)
    cached = _get_cached(key)
    if cached is not None:
        return cached, True

    input_data = request.model_dump(mode="json")

    prompt = f"""
You are the Interest Synthesis Agent for an app called save:on.

save:on lets a user save short-form videos and later connects saved
content that mentions the same entity. You receive an already-built
bundle of related saved content.

Your job is NOT to re-analyze the original videos and NOT to perform
web fact checking. Your job is to synthesize the user's saved content
into one useful Korean interest summary.

IMPORTANT RULES:

1. Use ONLY the information in INPUT DATA. Do not invent facts.
2. Do not infer sensitive traits, identity, demographics, health
   conditions, political views, religion, or other personal attributes.
3. Do not overstate user preference from a small sample. Prefer wording
   such as "저장한 콘텐츠에서는 ...가 반복돼요" rather than
   "사용자는 ...를 좋아합니다".
4. If highlights appear duplicated or nearly identical, do not pretend
   they are independent evidence. Summarize the repeated topic once.
5. summary: 1-3 concise Korean sentences. Explain the central pattern
   across the saved content and why the bundle is useful.
6. keyInterests: 2-5 short Korean phrases describing recurring themes.
7. takeaways: 2-5 concrete pieces of information supported by the bundle.
   Write them as observations about what the saved content says.
   Good: "저장한 콘텐츠에서는 대형 매장 방문과 선착순 특가 확인이 반복적으로 언급돼요."
   Bad: "대형 매장을 방문하여 선착순 특가를 확인하는 것이 좋습니다."
   NEVER use recommendation or instruction endings such as
   "좋습니다", "추천합니다", "권장합니다", "~하세요", "~해보세요",
   "~하는 것이 좋습니다", or "적극적으로 활용".
8. summary and takeaways must describe the saved material, not tell the
   user what they should do. Prefer sentence frames such as
   "저장한 콘텐츠에서는...", "...가 반복적으로 언급돼요",
   "...에 대한 내용이 여러 저장물에 나와요".
9. Do not recommend actions yet. A separate Action Agent will handle
   maps, calendars, shopping comparisons, checklists, etc.
10. Do not claim external verification. The input may contain analysis
   results that have not been fact-checked.
11. Return JSON only.

INPUT DATA:
{json.dumps(input_data, ensure_ascii=False, indent=2)}
""".strip()

    client = genai.Client(api_key=GEMINI_API_KEY)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=700,
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "keyInterests": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 5,
                    },
                    "takeaways": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 5,
                    },
                },
                "required": [
                    "summary",
                    "keyInterests",
                    "takeaways",
                ],
            },
        ),
    )

    if not response.text:
        raise RuntimeError("Gemini Interest Agent 응답이 비어 있습니다.")

    try:
        parsed = json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Gemini Interest Agent JSON 파싱 실패: {response.text}"
        ) from exc

    result = _normalize_result(parsed)
    _put_cached(key, result)

    return result, False
