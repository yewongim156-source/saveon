from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

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
    os.getenv("ACTION_AGENT_CACHE_TTL_SECONDS", "1800")
)
CACHE_MAX_ITEMS = int(
    os.getenv("ACTION_AGENT_CACHE_MAX_ITEMS", "128")
)

ActionKind = Literal[
    "MAP_SEARCH",
    "WEB_SEARCH",
    "COMPARE_SEARCH",
    "CALENDAR_ADD",
    "CHECKLIST_CREATE",
]

ALLOWED_ACTIONS = {
    "MAP_SEARCH",
    "WEB_SEARCH",
    "COMPARE_SEARCH",
    "CALENDAR_ADD",
    "CHECKLIST_CREATE",
}

SEARCH_ACTIONS = {
    "MAP_SEARCH",
    "WEB_SEARCH",
    "COMPARE_SEARCH",
}


class RelatedEntityInput(BaseModel):
    entity: str
    type: str
    count: int


class EntityDetailInput(BaseModel):
    name: str
    type: str
    confidence: float = 0.0


class InterestSynthesisInput(BaseModel):
    source: str = "RULE_BASED"
    summary: str = ""
    keyInterests: list[str] = Field(default_factory=list)
    takeaways: list[str] = Field(default_factory=list)


class HighlightInput(BaseModel):
    contentId: int
    title: str = ""
    summary: str = ""


class ActionFactInput(BaseModel):
    contentId: int | None = None
    text: str
    type: str
    confidence: float = 0.0


class ActionPlanRequest(BaseModel):
    contextType: Literal[
        "SINGLE_CONTENT",
        "CONTENT_BUNDLE",
    ] = "CONTENT_BUNDLE"
    entity: str = ""
    type: str = "CONTENT"
    count: int = 1
    title: str = ""
    summary: str = ""
    categories: list[str] = Field(default_factory=list)
    commonKeywords: list[str] = Field(default_factory=list)
    commonTags: list[str] = Field(default_factory=list)
    contentTypes: list[str] = Field(default_factory=list)
    relatedEntities: list[RelatedEntityInput] = Field(default_factory=list)
    entityDetails: list[EntityDetailInput] = Field(default_factory=list)
    highlights: list[HighlightInput] = Field(default_factory=list)
    actionFacts: list[ActionFactInput] = Field(default_factory=list)
    synthesis: InterestSynthesisInput | None = None
    currentDate: str = ""
    timezone: str = "Asia/Seoul"


class ActionItem(BaseModel):
    kind: ActionKind
    title: str
    description: str
    query: str = ""
    eventTitle: str = ""
    eventDate: str = ""
    checklistItems: list[str] = Field(default_factory=list)


class ActionPlanResponse(BaseModel):
    actions: list[ActionItem] = Field(default_factory=list)


_CACHE: dict[str, tuple[float, ActionPlanResponse]] = {}


def _cache_key(request: ActionPlanRequest) -> str:
    canonical = json.dumps(
        request.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _get_cached(key: str) -> ActionPlanResponse | None:
    cached = _CACHE.get(key)
    if not cached:
        return None

    saved_at, value = cached
    if time.time() - saved_at > CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        return None

    return value


def _put_cached(key: str, value: ActionPlanResponse) -> None:
    if len(_CACHE) >= CACHE_MAX_ITEMS:
        oldest_key = min(
            _CACHE,
            key=lambda item: _CACHE[item][0],
        )
        _CACHE.pop(oldest_key, None)

    _CACHE[key] = (time.time(), value)


def _clean_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split()).strip()
    return text[:limit]


def _clean_items(value: Any, max_items: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []

    result: list[str] = []
    seen: set[str] = set()

    for raw in value:
        item = _clean_text(raw, 100)
        key = item.lower()
        if not item or key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= max_items:
            break

    return result


def _has_entity_type(
    request: ActionPlanRequest,
    allowed_types: set[str],
) -> bool:
    root_type = request.type.strip().upper()

    if root_type in allowed_types:
        return True

    return any(
        item.type.strip().upper() in allowed_types
        and item.confidence >= 0.65
        and bool(item.name.strip())
        for item in request.entityDetails
    )


def _best_entity(
    request: ActionPlanRequest,
    allowed_types: set[str],
) -> str:
    candidates = [
        item
        for item in request.entityDetails
        if item.type.strip().upper() in allowed_types
        and item.confidence >= 0.65
        and item.name.strip()
    ]

    candidates.sort(
        key=lambda item: item.confidence,
        reverse=True,
    )

    if candidates:
        return candidates[0].name.strip()

    if request.type.strip().upper() in allowed_types:
        return request.entity.strip()

    return ""


def _has_date_fact(request: ActionPlanRequest) -> bool:
    return any(
        fact.type.strip().upper() == "DATE_TIME"
        and fact.confidence >= 0.65
        and bool(fact.text.strip())
        for fact in request.actionFacts
    )


def _event_date_supported_by_facts(
    event_date: str,
    request: ActionPlanRequest,
) -> bool:
    try:
        parsed = date.fromisoformat(event_date)
    except ValueError:
        return False

    year = parsed.year
    month = parsed.month
    day = parsed.day

    patterns = [
        f"{year}년 {month}월 {day}일",
        f"{year}년{month}월{day}일",
        f"{month}월 {day}일",
        f"{month}월{day}일",
        f"{year}-{month:02d}-{day:02d}",
        f"{month:02d}-{day:02d}",
        f"{month}/{day}",
        f"{month:02d}/{day:02d}",
    ]

    for fact in request.actionFacts:
        if fact.type.strip().upper() != "DATE_TIME":
            continue
        if fact.confidence < 0.65:
            continue

        compact = " ".join(fact.text.split())
        if any(pattern in compact for pattern in patterns):
            return True

    return False


def _checklist_supported(request: ActionPlanRequest) -> bool:
    content_types = {
        item.strip().upper()
        for item in request.contentTypes
    }
    if content_types.intersection({"RECIPE", "HOW_TO"}):
        return True

    return "음식/레시피" in request.categories


def _parse_reference_date(value: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except Exception:
        return date.today()


def _valid_event_date(value: str, reference: date) -> str:
    value = _clean_text(value, 10)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return ""

    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return ""

    if parsed < reference:
        return ""

    if parsed > reference + timedelta(days=730):
        return ""

    return value


def _normalize_result(
    raw: dict[str, Any],
    request: ActionPlanRequest,
) -> ActionPlanResponse:
    raw_actions = raw.get("actions", [])
    if not isinstance(raw_actions, list):
        return ActionPlanResponse(actions=[])

    root_type = request.type.strip().upper()
    reference_date = _parse_reference_date(request.currentDate)
    result: list[ActionItem] = []
    seen: set[str] = set()

    for item in raw_actions:
        if not isinstance(item, dict):
            continue

        kind = str(item.get("kind", "")).strip().upper()
        if kind not in ALLOWED_ACTIONS:
            continue

        if (
            kind == "MAP_SEARCH"
            and not _has_entity_type(
                request,
                {"PLACE"},
            )
        ):
            continue

        if (
            kind == "COMPARE_SEARCH"
            and not _has_entity_type(
                request,
                {"PRODUCT", "BRAND"},
            )
        ):
            continue

        if kind == "CALENDAR_ADD" and not _has_date_fact(request):
            continue

        if kind == "CHECKLIST_CREATE" and not _checklist_supported(request):
            continue

        title = _clean_text(item.get("title"), 60)
        description = _clean_text(item.get("description"), 180)
        query = _clean_text(item.get("query"), 140)
        event_title = _clean_text(item.get("eventTitle"), 80)
        event_date = _valid_event_date(
            str(item.get("eventDate", "")),
            reference_date,
        )
        checklist_items = _clean_items(item.get("checklistItems"))

        if not title:
            continue

        if kind in SEARCH_ACTIONS:
            if not query:
                continue
            identity = f"{kind}|{query.lower()}"

        elif kind == "CALENDAR_ADD":
            if (
                not event_title
                or not event_date
                or not _event_date_supported_by_facts(
                    event_date,
                    request,
                )
            ):
                continue
            identity = f"{kind}|{event_date}|{event_title.lower()}"

        else:
            if len(checklist_items) < 2:
                continue
            identity = f"{kind}|{'|'.join(x.lower() for x in checklist_items)}"

        if identity in seen:
            continue
        seen.add(identity)

        result.append(
            ActionItem(
                kind=kind,
                title=title,
                description=description,
                query=query,
                eventTitle=event_title,
                eventDate=event_date,
                checklistItems=checklist_items,
            )
        )

        if len(result) >= 3:
            break

    return ActionPlanResponse(actions=result)


def plan_actions(
    request: ActionPlanRequest,
) -> tuple[ActionPlanResponse, bool]:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY가 설정되어 있지 않습니다.")

    root_type = request.type.strip().upper()

    if (
        not request.entity.strip()
        and not request.title.strip()
        and not request.entityDetails
    ):
        raise ValueError(
            "행동을 만들 수 있는 콘텐츠 정보가 비어 있습니다."
        )

    key = _cache_key(request)
    cached = _get_cached(key)
    if cached is not None:
        return cached, True

    input_data = request.model_dump(mode="json")

    prompt = f"""
You are the Action Agent for an app called save:on.

save:on lets a user save short-form content and turn saved information
into useful next actions.

You can receive TWO context types:

- SINGLE_CONTENT:
  One saved content item. Actions should be immediately useful even if
  the user has never saved another related content item.

- CONTENT_BUNDLE:
  Multiple connected saved contents already grouped into one interest
  bundle. Actions should use the combined information.

Your job is to choose 1-3 safe, useful next actions.

IMPORTANT RULES:

1. Use ONLY INPUT DATA. Do not invent facts, dates, prices, locations,
   products, events, ingredients, steps, or user preferences.
2. Do NOT execute an action. Return only structured action data.
3. Do NOT return URLs, deep links, shell commands, purchase instructions,
   booking instructions, contact information, messages, or payment steps.
4. Allowed action kinds are ONLY:
   - MAP_SEARCH: search a PLACE in a map app.
   - WEB_SEARCH: search the web for related/current information.
   - COMPARE_SEARCH: search comparisons for a PRODUCT or BRAND.
   - CALENDAR_ADD: create an all-day calendar candidate from an explicit
     DATE_TIME actionFact.
   - CHECKLIST_CREATE: create a short in-app checklist from content that
     is explicitly RECIPE or HOW_TO.
5. MAP_SEARCH may be used when either:
   - root type is PLACE, or
   - entityDetails contains a PLACE with confidence >= 0.65.
   For SINGLE_CONTENT, prefer the actual PLACE entity name as query.
6. COMPARE_SEARCH may be used when either:
   - root type is PRODUCT or BRAND, or
   - entityDetails contains PRODUCT or BRAND with confidence >= 0.65.
7. CALENDAR_ADD may be used ONLY if actionFacts contains a DATE_TIME fact
   with confidence >= 0.65. eventDate must be directly supported by that
   fact. Never infer a date from a general keyword or summary.
8. If a DATE_TIME fact gives month/day but omits a year, use currentDate
   only to resolve the nearest occurrence that is not in the past.
   Do not infer a time. The app will create an all-day event.
9. CHECKLIST_CREATE may be used ONLY when contentTypes includes RECIPE or
   HOW_TO, or category explicitly includes 음식/레시피.
10. For SINGLE_CONTENT checklistItems must be directly supported by the
    title/summary/highlight. For CONTENT_BUNDLE they may additionally use
    synthesis.takeaways. Never add absent ingredients or steps.
11. When CALENDAR_ADD is eligible, prefer it over a generic WEB_SEARCH.
    When CHECKLIST_CREATE is eligible, prefer it over a generic WEB_SEARCH
    if an action slot remains.
12. For BRAND/PRODUCT, prefer comparison/search actions grounded in the
    provided keywords, tags, entities, or synthesis.
13. For SINGLE_CONTENT, do not require repeated entities. One confident
    PLACE/PRODUCT/BRAND entity is enough to suggest an appropriate action.
14. title must be a short Korean button label.
15. description must be one concise Korean sentence.
16. For MAP_SEARCH/WEB_SEARCH/COMPARE_SEARCH:
    - query is required.
    - eventTitle="", eventDate="", checklistItems=[].
17. For CALENDAR_ADD:
    - eventTitle and eventDate(YYYY-MM-DD) are required.
    - query="" and checklistItems=[].
18. For CHECKLIST_CREATE:
    - checklistItems must contain 2-8 concise Korean items.
    - query="", eventTitle="", eventDate="".
19. Return JSON only.

CONTEXT TYPE: {request.contextType}
ROOT ENTITY TYPE: {root_type}

INPUT DATA:
{json.dumps(input_data, ensure_ascii=False, indent=2)}
""".strip()

    client = genai.Client(api_key=GEMINI_API_KEY)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=900,
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "actions": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "properties": {
                                "kind": {
                                    "type": "string",
                                    "enum": [
                                        "MAP_SEARCH",
                                        "WEB_SEARCH",
                                        "COMPARE_SEARCH",
                                        "CALENDAR_ADD",
                                        "CHECKLIST_CREATE",
                                    ],
                                },
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "query": {"type": "string"},
                                "eventTitle": {"type": "string"},
                                "eventDate": {"type": "string"},
                                "checklistItems": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "maxItems": 8,
                                },
                            },
                            "required": [
                                "kind",
                                "title",
                                "description",
                                "query",
                                "eventTitle",
                                "eventDate",
                                "checklistItems",
                            ],
                        },
                    },
                },
                "required": ["actions"],
            },
        ),
    )

    if not response.text:
        raise RuntimeError("Gemini Action Agent 응답이 비어 있습니다.")

    try:
        parsed = json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Gemini Action Agent JSON 파싱 실패: {response.text}"
        ) from exc

    result = _normalize_result(parsed, request)
    if not result.actions:
        raise RuntimeError("Action Agent가 유효한 행동을 만들지 못했습니다.")

    _put_cached(key, result)
    return result, False
