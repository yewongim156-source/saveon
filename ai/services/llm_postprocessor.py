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
    """
    Shared Gemini client.

    Important: 429 quota exhaustion is intentionally NOT retried here.
    Repeating a request while the per-minute quota is exhausted only makes
    the burst worse. Retry only transient 5xx responses.
    """
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
                http_status_codes=[500, 502, 503, 504],
            ),
        ),
    )

MAX_TRANSCRIPT_CHARS = 3500
MAX_OCR_LINES = 20
MAX_OCR_LINE_LENGTH = 80
MAX_VISION_LABELS = 5

MIN_ENTITY_CONFIDENCE = 0.45
MIN_OTHER_ENTITY_CONFIDENCE = 0.65

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

GENERIC_TITLE_PATTERNS = [
    re.compile(r"^video\s+by\s+.+$", re.I),
    re.compile(r"^reel\s+by\s+.+$", re.I),
    re.compile(r"^instagram\s+video$", re.I),
    re.compile(r"^youtube\s+video$", re.I),
    re.compile(r"^untitled$", re.I),
]

GENERIC_KEYWORDS = {
    "video",
    "reel",
    "shorts",
    "instagram",
    "youtube",
    "by",
    "영상",
    "콘텐츠",
}


def _clean_transcript(text: str) -> str:
    if not text:
        return ""

    cleaned = " ".join(text.split())

    if len(cleaned) > MAX_TRANSCRIPT_CHARS:
        cleaned = cleaned[:MAX_TRANSCRIPT_CHARS]

    return cleaned


def _ascii_token_is_suspicious(value: str) -> bool:
    compact = re.sub(r"[^A-Za-z0-9]", "", value)

    if not compact:
        return True

    # OCR 단독 근거로 2글자 영문 토큰을 신뢰하지 않는다.
    if re.fullmatch(r"[A-Za-z]{1,2}", compact):
        return True

    # 숫자/영문 혼합의 지나치게 짧은 조각
    if len(compact) <= 3 and re.search(r"\d", compact):
        return True

    # 의미 없는 대문자 조각. URL/브랜드의 확실한 근거는 LLM이
    # source metadata에서 별도로 복원하도록 한다.
    if (
        re.fullmatch(r"[A-Z]{3,6}", compact)
        and not re.search(r"[aeiouAEIOU]", compact)
    ):
        return True

    return False


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

    if not re.search(r"[가-힣A-Za-z0-9]", value):
        return True

    useful_chars = re.findall(
        r"[가-힣A-Za-z0-9]",
        value,
    )

    if len(useful_chars) < 2:
        return True

    # 특수문자가 유효 문자보다 많으면 OCR 깨짐으로 간주
    special_chars = re.findall(
        r"[^가-힣A-Za-z0-9\s]",
        value,
    )
    if len(special_chars) > len(useful_chars):
        return True

    # 한글이 없고 짧은 ASCII 조각이면 보수적으로 제거
    if (
        not re.search(r"[가-힣]", value)
        and len(value) <= 8
        and _ascii_token_is_suspicious(value)
    ):
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
    *,
    filter_noise: bool = False,
) -> list[str]:
    if not isinstance(value, list):
        return []

    result: list[str] = []
    seen: set[str] = set()

    for item in value:
        if not isinstance(item, str):
            continue

        cleaned = " ".join(item.split()).strip()

        if not cleaned:
            continue

        if filter_noise and _looks_like_noise(cleaned):
            continue

        if cleaned.lower() in GENERIC_KEYWORDS:
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

        name = " ".join(
            str(item.get("name", "")).split()
        ).strip()
        entity_type = str(
            item.get("type", "OTHER")
        ).strip().upper()
        confidence = _normalize_confidence(
            item.get("confidence")
        )

        if not name or _looks_like_noise(name):
            continue

        if entity_type not in ALLOWED_ENTITY_TYPES:
            entity_type = "OTHER"

        min_confidence = (
            MIN_OTHER_ENTITY_CONFIDENCE
            if entity_type == "OTHER"
            else MIN_ENTITY_CONFIDENCE
        )

        if confidence < min_confidence:
            continue

        key = (name.lower(), entity_type)
        if key in seen:
            continue
        seen.add(key)

        result.append({
            "name": name[:80],
            "type": entity_type,
            "confidence": confidence,
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


def _is_generic_title(title: str) -> bool:
    value = " ".join(title.split()).strip()

    if not value:
        return True

    return any(
        pattern.match(value)
        for pattern in GENERIC_TITLE_PATTERNS
    )


def _fallback_title_from_description(
    source_description: str,
) -> str:
    cleaned = " ".join(
        source_description.split()
    ).strip()

    if not cleaned:
        return ""

    # 해시태그 전의 설명을 우선 사용
    before_tags = cleaned.split("#", 1)[0].strip()
    candidate = before_tags or cleaned

    candidate = re.sub(
        r"\s+",
        " ",
        candidate,
    ).strip(" -–—|/")

    if len(candidate) < 4:
        return ""

    return candidate[:60]


def _normalize_result(
    result: dict,
    *,
    source_title: str = "",
    source_description: str = "",
) -> dict:
    title = " ".join(
        str(result.get("title", "")).split()
    ).strip()

    summary = " ".join(
        str(result.get("summary", "")).split()
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
        filter_noise=True,
    )

    entity_details = _normalize_entity_details(
        result.get("entityDetails", [])
    )

    # top-level entities는 신뢰 가능한 entityDetails와 동기화한다.
    # LLM이 details에 넣지 않은 entity는 별도 검증 근거가 없으므로 제외.
    entities = [
        item["name"]
        for item in entity_details[:8]
    ]

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
        filter_noise=True,
    )

    content_type = str(
        result.get("contentType", "OTHER")
    ).strip().upper()
    if content_type not in ALLOWED_CONTENT_TYPES:
        content_type = "OTHER"

    claims = _normalize_claims(
        result.get("claims", [])
    )

    if _is_generic_title(title):
        description_title = _fallback_title_from_description(
            source_description
        )
        if description_title:
            title = description_title
        elif source_title and not _is_generic_title(source_title):
            title = source_title

    if not title:
        title = "영상 콘텐츠"

    if not summary:
        description = " ".join(
            source_description.split()
        ).strip()
        if description:
            summary = description[:500]
        else:
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
    review_excerpts: list[str] | None = None,
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

    clean_source_title = " ".join(
        source_title.split()
    ).strip()
    clean_source_description = " ".join(
        source_description.split()
    ).strip()[:1600]
    clean_source_channel = " ".join(
        source_channel.split()
    ).strip()

    input_data = {
        "source_metadata": {
            "title": clean_source_title,
            "description": clean_source_description,
            "channel": clean_source_channel,
        },
        "transcript": clean_transcript,
        "review_excerpts": (review_excerpts or [])[:9],
        "ocr": clean_ocr,
        "vision_labels": clean_vision,
    }

    prompt = f"""
You are the metadata analysis engine for an app called save:on.

save:on stores short-form social media content and helps users find it later.

The following information was automatically extracted from a video.
STT, OCR, and visual classification may contain recognition errors.

SOURCE PRIORITY:
- Source title/description/channel are publisher-provided metadata and are usually
  more reliable for the video's topic than noisy STT/OCR/vision labels.
- When source metadata clearly identifies the topic, use it as the primary signal.
- STT/OCR/vision should support or refine that topic, not override clear source metadata.
- If STT/OCR conflicts with a clear source description, treat the recognition output
  as likely noisy unless multiple independent signals support it.

IMPORTANT RULES:

1. Correct obvious STT recognition errors only when the intended meaning is reasonably clear.

2. Ignore meaningless OCR fragments, UI text, partial characters, and broken ASCII tokens.

3. Do not invent brands, products, places, people, prices, specifications, or other facts
   that are not supported by the provided data.

4. The title must describe the actual main topic naturally in Korean.
   Never return generic source titles such as "Video by username", "Reel by username",
   "Instagram video", or "YouTube video" when the description reveals the topic.

5. The summary should contain 1-3 concise Korean sentences.
   Do NOT output a raw diagnostic dump such as
   "음성 내용: ... / 화면 텍스트: ... / 화면 유형: ...".
   Synthesize the meaning into user-facing Korean.

6. categories must contain 1-3 items and must be selected ONLY from this list:

{ALLOWED_CATEGORIES}

7. When source description/hashtags contain strong domain evidence,
   use it for category choice. Example:
   #쿠션 #쿠션추천 #뷰티 #코덕 -> primaryCategory should normally be 뷰티/패션,
   not 생활정보 or 기술.

8. keywords should contain 5-10 useful search terms.
   Exclude random OCR fragments and generic words such as video, reel, by.

9. entities should contain only meaningful named or identifiable things such as
   a brand, product, place, restaurant, person, service, or event.

10. If an entity cannot be confidently identified, omit it.
    Do not create entities from isolated OCR fragments.
    entityDetails confidence below 0.5 should generally not be emitted.

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

15. Set verifiable=true only for objective facts. Provide a concise searchQuery.

16. Confidence values must be numbers from 0 to 1.

17. A review title saying "8-hour test" or "darkening test" does NOT
    establish whether wear was good or darkening occurred. Explicitly distinguish
    tests/mentions from observed outcomes.

18. When a spoken statement or reliable description provides a concrete review
    outcome, include that specific outcome and its uncertainty in the summary.
    Prefer DIRECT_STATEMENT excerpts when available. Do not infer an outcome from
    product claims, generic tags or low-quality OCR.

19. Any prices, shade counts or performance statements must be stated only as
    the video's claim (not an official/verified fact) unless independently verified.
    "All shades reviewed" never implies a specific number of shades.

20. Return JSON only.


5a. LANGUAGE STYLE (SAVEON_COPY_TONE_V1): Use natural, concise Korean like a personal saved-note.
    Avoid promotional narrator templates such as "소개합니다", "공유합니다",
    "본 영상에서는", and "관련 내용을 다룹니다". Prefer a concrete,
    descriptive sentence about what is actually shown or said, in 1-2 sentences.
    Never add unobserved claims, confidence, prices, or outcomes for style.
    Preserve factual uncertainty, conditions, measurements, and evidence.


INPUT DATA:

{json.dumps(input_data, ensure_ascii=False, indent=2)}
""".strip()

    client = create_gemini_client()

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.15,
            max_output_tokens=1050,
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "entities": {
                        "type": "array",
                        "items": {"type": "string"},
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
        parsed,
        source_title=clean_source_title,
        source_description=clean_source_description,
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
