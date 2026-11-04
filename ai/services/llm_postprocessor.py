from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite",
)
GEMINI_REQUEST_TIMEOUT_MS = int(
    os.getenv("GEMINI_REQUEST_TIMEOUT_MS", "30000")
)
GEMINI_RETRY_ATTEMPTS = int(
    os.getenv("GEMINI_RETRY_ATTEMPTS", "3")
)


def create_gemini_client() -> genai.Client:
    return genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=types.HttpOptions(
            timeout=GEMINI_REQUEST_TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(
                attempts=max(1, GEMINI_RETRY_ATTEMPTS),
                initial_delay=0.5,
                max_delay=2.0,
                exp_base=2.0,
                jitter=0.1,
                # Quota exhaustion (429) needs a quota or billing change,
                # not repeated requests. Retry only transient server errors.
                http_status_codes=[500, 502, 503, 504],
            ),
        ),
    )

MAX_TRANSCRIPT_CHARS = 3500
MAX_OCR_LINES = 20
MAX_OCR_LINE_LENGTH = 80
MAX_VISION_LABELS = 5

ALLOWED_CATEGORIES = [
    "장소/여행",
    "음식/레시피",
    "제품/쇼핑",
    "뷰티/패션",
    "학습/커리어",
    "건강/운동",
    "생활정보",
    "엔터테인먼트",
    "기타",
]

ALLOWED_CONTENT_TYPES = [
    "PLACE_RECOMMENDATION",
    "HOW_TO",
    "PRODUCT_REVIEW",
    "RECIPE",
    "EVENT_INFO",
    "EDUCATIONAL",
    "NEWS_CLAIM",
    "OTHER",
]

ALLOWED_ENTITY_TYPES = [
    "PLACE",
    "PRODUCT",
    "BRAND",
    "PERSON",
    "SERVICE",
    "EVENT",
    "DATE",
    "OTHER",
]

ALLOWED_CLAIM_TYPES = [
    "LOCATION",
    "DATE_TIME",
    "PRICE",
    "PRODUCT_PERFORMANCE",
    "HEALTH_BEAUTY",
    "TRAVEL_RULE",
    "STATISTIC",
    "OTHER",
]

UI_NOISE = {
    "esc",
    "caps",
    "caps lock",
    "shift",
    "ctrl",
    "alt",
    "enter",
    "tab",
    "space",
    "home",
    "end",
    "delete",
    "backspace",
    "command",
    "option",
}


def _clean_transcript(text: str) -> str:
    if not text:
        return ""

    cleaned = " ".join(text.split())

    if len(cleaned) > MAX_TRANSCRIPT_CHARS:
        cleaned = cleaned[:MAX_TRANSCRIPT_CHARS]

    return cleaned


def _looks_like_noise(text: str) -> bool:
    value = text.strip()

    if not value:
        return True

    lowered = value.lower()

    if lowered in UI_NOISE:
        return True

    if len(value) < 2:
        return True

    if len(value) > MAX_OCR_LINE_LENGTH:
        return True

    # 기호만 있는 OCR 제거
    if not re.search(r"[가-힣A-Za-z0-9]", value):
        return True

    # 영문/숫자/한글이 거의 없고 특수문자가 대부분인 경우 제거
    useful_chars = re.findall(
        r"[가-힣A-Za-z0-9]",
        value,
    )

    if len(useful_chars) < 2:
        return True

    return False


def _clean_ocr_lines(
    ocr_lines: list[str],
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for line in ocr_lines:
        cleaned = " ".join(
            str(line).split()
        ).strip()

        if _looks_like_noise(cleaned):
            continue

        normalized = cleaned.lower()

        if normalized in seen:
            continue

        seen.add(normalized)
        result.append(cleaned)

        if len(result) >= MAX_OCR_LINES:
            break

    return result


def _clean_vision_labels(
    labels: list[str],
) -> list[str]:
    result: list[str] = []

    for label in labels:
        label = str(label).strip()

        if not label:
            continue

        if label not in result:
            result.append(label)

        if len(result) >= MAX_VISION_LABELS:
            break

    return result


def _normalize_string_list(
    value,
    max_items: int,
) -> list[str]:
    if not isinstance(value, list):
        return []

    result: list[str] = []
    seen: set[str] = set()

    for item in value:
        if not isinstance(item, str):
            continue

        cleaned = item.strip()

        if not cleaned:
            continue

        normalized = cleaned.lower()

        if normalized in seen:
            continue

        seen.add(normalized)
        result.append(cleaned)

        if len(result) >= max_items:
            break

    return result


def _normalize_confidence(value) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))


def _normalize_entity_details(value) -> list[dict]:
    if not isinstance(value, list):
        return []

    result: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for item in value:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name", "")).strip()
        entity_type = str(item.get("type", "OTHER")).strip().upper()

        if not name:
            continue
        if entity_type not in ALLOWED_ENTITY_TYPES:
            entity_type = "OTHER"

        key = (name.lower(), entity_type)
        if key in seen:
            continue
        seen.add(key)

        result.append({
            "name": name[:80],
            "type": entity_type,
            "confidence": _normalize_confidence(item.get("confidence")),
        })

        if len(result) >= 12:
            break

    return result


def _normalize_claims(value) -> list[dict]:
    if not isinstance(value, list):
        return []

    result: list[dict] = []
    seen: set[str] = set()

    for item in value:
        if not isinstance(item, dict):
            continue

        text = " ".join(str(item.get("text", "")).split()).strip()
        if not text:
            continue

        normalized = text.lower()
        if normalized in seen:
            continue
        seen.add(normalized)

        claim_type = str(item.get("type", "OTHER")).strip().upper()
        if claim_type not in ALLOWED_CLAIM_TYPES:
            claim_type = "OTHER"

        verifiable = bool(item.get("verifiable", False))
        search_query = " ".join(
            str(item.get("searchQuery", "")).split()
        ).strip()

        result.append({
            "text": text[:240],
            "type": claim_type,
            "verifiable": verifiable,
            "searchQuery": search_query[:180],
            "confidence": _normalize_confidence(item.get("confidence")),
        })

        if len(result) >= 3:
            break

    return result


def _normalize_result(
    result: dict,
) -> dict:
    title = str(
        result.get("title", "")
    ).strip()

    summary = str(
        result.get("summary", "")
    ).strip()

    categories = _normalize_string_list(
        result.get("categories", []),
        max_items=3,
    )

    categories = [
        category
        for category in categories
        if category in ALLOWED_CATEGORIES
    ]

    if not categories:
        categories = ["기타"]

    keywords = _normalize_string_list(
        result.get("keywords", []),
        max_items=10,
    )

    entities = _normalize_string_list(
        result.get("entities", []),
        max_items=8,
    )

    primary_category = str(
        result.get("primaryCategory", "")
    ).strip()
    if primary_category not in ALLOWED_CATEGORIES:
        primary_category = categories[0]

    secondary_categories = _normalize_string_list(
        result.get("secondaryCategories", []),
        max_items=5,
    )
    tags = _normalize_string_list(
        result.get("tags", []),
        max_items=12,
    )

    content_type = str(
        result.get("contentType", "OTHER")
    ).strip().upper()
    if content_type not in ALLOWED_CONTENT_TYPES:
        content_type = "OTHER"

    entity_details = _normalize_entity_details(
        result.get("entityDetails", [])
    )
    claims = _normalize_claims(
        result.get("claims", [])
    )

    if not entities and entity_details:
        entities = [item["name"] for item in entity_details[:8]]

    if not title:
        title = "영상 콘텐츠"

    if not summary:
        summary = "영상의 핵심 내용을 분석했습니다."

    return {
        "title": title[:60],
        "summary": summary[:500],
        "categories": categories,
        "keywords": keywords,
        "entities": entities,
        "structured": {
            "primaryCategory": primary_category,
            "secondaryCategories": secondary_categories,
            "tags": tags,
            "contentType": content_type,
            "entityDetails": entity_details,
            "claims": claims,
            "factChecks": [],
        },
    }


def postprocess_with_llm(
    transcript: str,
    ocr_lines: list[str],
    vision_labels: list[str],
    *,
    source_title: str = "",
    source_description: str = "",
    source_channel: str = "",
) -> dict:
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY가 설정되어 있지 않습니다."
        )

    clean_transcript = _clean_transcript(
        transcript
    )

    clean_ocr = _clean_ocr_lines(
        ocr_lines
    )

    clean_vision = _clean_vision_labels(
        vision_labels
    )

    input_data = {
        "primary_evidence": {
            "speech_transcript": clean_transcript,
            "screen_text_ocr": clean_ocr,
        },
        "supporting_evidence": {
            "source_title": _clean_transcript(source_title)[:300],
            "source_channel": _clean_transcript(source_channel)[:120],
        },
        "weak_evidence": {
            "source_description": _clean_transcript(
                source_description
            )[:1200],
            "zero_shot_visual_labels": clean_vision,
        },
    }

    prompt = f"""
You are the metadata analysis engine for an app called save:on.

save:on stores short-form social media content and helps users
find it later.

The following information was automatically extracted from a video.
The STT and OCR data may contain recognition errors.

Your task is to infer the main subject of the video and create
clean Korean metadata.

IMPORTANT RULES:

1. Correct obvious STT recognition errors only when the intended
   meaning is reasonably clear.

2. Ignore meaningless OCR fragments and UI text.

3. Do not invent brands, products, places, people, prices,
   specifications, or other facts that are not supported by
   the provided data.

3a. Evidence priority is primary_evidence, then supporting_evidence,
    then weak_evidence. A platform description can be stale, promotional,
    or unrelated to the actual clip. Zero-shot visual labels are coarse.
    Never let weak evidence override a clear speech transcript or OCR.

    When primary_evidence contains meaningful content, ignore conflicting
    weak evidence completely, including secondary categories and tags.

3b. If the evidence sources conflict, describe the topic supported by the
    speech transcript and OCR. Omit the conflicting weak evidence instead
    of combining unrelated topics.

4. The title must describe the actual main topic naturally in Korean.

5. The summary should contain 1-3 concise Korean sentences.

6. categories must contain 1-3 items and must be selected ONLY
   from this list:

{ALLOWED_CATEGORIES}

7. keywords should contain 5-10 useful terms that would help
   the user search for this content later.

8. entities should contain only meaningful named or identifiable
   things such as:
   - brand
   - product
   - place
   - restaurant
   - person
   - service

9. Do not put generic UI text such as Esc, Shift, Caps Lock,
   buttons, timestamps, or random OCR fragments into entities.

10. If an entity cannot be confidently identified, omit it.

11. primaryCategory must be selected from the category list.
    secondaryCategories and tags may be more specific Korean labels.

12. contentType must be selected ONLY from:

{ALLOWED_CONTENT_TYPES}

13. entityDetails must classify each entity using ONLY:

{ALLOWED_ENTITY_TYPES}

14. claims must include at most 3 externally verifiable claims.
    Opinions and personal preferences are not verifiable claims.
    Use ONLY these claim types:

{ALLOWED_CLAIM_TYPES}

15. Set verifiable=true only for claims about dates, times, prices,
    locations, product performance, health or beauty effects,
    travel rules, statistics, or another objective fact. Provide a
    concise searchQuery that could locate authoritative evidence.

16. Confidence values must be numbers from 0 to 1.

17. Return JSON only.

INPUT DATA:

{json.dumps(input_data, ensure_ascii=False, indent=2)}
""".strip()

    client = create_gemini_client()

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
                    "title": {
                        "type": "string",
                    },
                    "summary": {
                        "type": "string",
                    },
                    "categories": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                    },
                    "keywords": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                    },
                    "entities": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                    },
                    "primaryCategory": {
                        "type": "string",
                        "enum": ALLOWED_CATEGORIES,
                    },
                    "secondaryCategories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 5,
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 12,
                    },
                    "contentType": {
                        "type": "string",
                        "enum": ALLOWED_CONTENT_TYPES,
                    },
                    "entityDetails": {
                        "type": "array",
                        "maxItems": 12,
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "type": {
                                    "type": "string",
                                    "enum": ALLOWED_ENTITY_TYPES,
                                },
                                "confidence": {"type": "number"},
                            },
                            "required": ["name", "type", "confidence"],
                        },
                    },
                    "claims": {
                        "type": "array",
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "type": {
                                    "type": "string",
                                    "enum": ALLOWED_CLAIM_TYPES,
                                },
                                "verifiable": {"type": "boolean"},
                                "searchQuery": {"type": "string"},
                                "confidence": {"type": "number"},
                            },
                            "required": [
                                "text",
                                "type",
                                "verifiable",
                                "searchQuery",
                                "confidence",
                            ],
                        },
                    },
                },
                "required": [
                    "title",
                    "summary",
                    "categories",
                    "keywords",
                    "entities",
                    "primaryCategory",
                    "secondaryCategories",
                    "tags",
                    "contentType",
                    "entityDetails",
                    "claims",
                ],
            },
        ),
    )

    if not response.text:
        raise RuntimeError(
            "Gemini 응답이 비어 있습니다."
        )

    try:
        parsed = json.loads(
            response.text
        )
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Gemini JSON 파싱 실패: {response.text}"
        ) from exc

    result = _normalize_result(
        parsed
    )

    print("[LLM] Gemini 후처리 완료")
    print(
        f"[LLM] input transcript chars="
        f"{len(clean_transcript)}"
    )
    print(
        f"[LLM] input ocr lines="
        f"{len(clean_ocr)}"
    )
    print(
        f"[LLM] result={result}"
    )

    return result
