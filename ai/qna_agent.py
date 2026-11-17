from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from services.comparison_grounding import ground_comparison_results


ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv(
    "GEMINI_QA_MODEL",
    os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
)


class KnowledgeContext(BaseModel):
    contentId: int
    title: str = ""
    summary: str = ""
    categories: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    structured: dict = Field(default_factory=dict)


class KnowledgeAskRequest(BaseModel):
    question: str
    contexts: list[KnowledgeContext] = Field(default_factory=list)


class KnowledgeAskResponse(BaseModel):
    answer: str
    citedContentIds: list[int] = Field(default_factory=list)


class CollectionNameRequest(BaseModel):
    seed: str
    titles: list[str] = Field(default_factory=list)
    summaries: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)


class CollectionNameResponse(BaseModel):
    title: str
    description: str


class ConflictClaimInput(BaseModel):
    contentId: int
    title: str = ""
    subject: str
    claimType: str
    claimText: str
    verificationStatus: str = ""
    factChecks: list[dict] = Field(default_factory=list)


class ConflictDetectRequest(BaseModel):
    claims: list[ConflictClaimInput] = Field(default_factory=list)


class ConflictEvidenceOutput(BaseModel):
    contentId: int
    claimText: str
    value: str = ""


class ConflictItemOutput(BaseModel):
    subject: str
    claimType: str
    title: str
    description: str
    severity: str = "WARN"
    evidences: list[ConflictEvidenceOutput] = Field(default_factory=list)


class ConflictDetectResponse(BaseModel):
    conflicts: list[ConflictItemOutput] = Field(default_factory=list)


class CollectionCompareContext(BaseModel):
    contentId: int
    title: str = ""
    summary: str = ""
    categories: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    structured: dict = Field(default_factory=dict)


class CollectionCompareRequest(BaseModel):
    collectionTitle: str = ""
    comparisonEntity: str = ""
    contexts: list[CollectionCompareContext] = Field(default_factory=list)
    autoVerifyExternal: bool = True


class EvidenceOutput(BaseModel):
    contentId: int
    title: str = ""
    quote: str = ""
    timestampSeconds: float | None = None


class ComparisonFindingOutput(BaseModel):
    topic: str
    statement: str
    evidences: list[EvidenceOutput] = Field(default_factory=list)


class ObjectiveDisagreementOutput(BaseModel):
    field: str
    label: str
    entity: str = ""
    values: list[str] = Field(default_factory=list)
    evidences: list[EvidenceOutput] = Field(default_factory=list)


class ExternalSourceOutput(BaseModel):
    title: str
    url: str


class ExternalFactOutput(BaseModel):
    label: str
    field: str
    entity: str = ""
    savedValues: list[str] = Field(default_factory=list)
    status: str
    currentValue: str = ""
    explanation: str = ""
    checkedAt: str
    sources: list[ExternalSourceOutput] = Field(default_factory=list)


class CollectionCompareResponse(BaseModel):
    eligible: bool
    reason: str = ""
    comparisonEntity: str = ""
    title: str
    summary: str
    commonPoints: list[ComparisonFindingOutput] = Field(default_factory=list)
    disagreements: list[ComparisonFindingOutput] = Field(default_factory=list)
    uniqueMentions: list[ComparisonFindingOutput] = Field(default_factory=list)
    objectiveDisagreements: list[ObjectiveDisagreementOutput] = Field(default_factory=list)
    externalFacts: list[ExternalFactOutput] = Field(default_factory=list)
    citedContentIds: list[int] = Field(default_factory=list)


app = FastAPI(
    title="SaveOn Knowledge Q&A Agent",
    version="1.0.0",
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "saveon-knowledge-qa-agent",
        "version": "1.0.0",
        "model": GEMINI_MODEL,
        "grounding": "USER_SAVED_CONTENT_ONLY",
    }


def _compact_context(context: KnowledgeContext) -> dict:
    structured = context.structured or {}

    return {
        "contentId": context.contentId,
        "title": context.title[:180],
        "summary": context.summary[:1200],
        "categories": context.categories[:5],
        "entities": context.entities[:12],
        "primaryCategory": structured.get("primaryCategory"),
        "contentType": structured.get("contentType"),
        "tags": (structured.get("tags") or [])[:12],
        "entityDetails": (structured.get("entityDetails") or [])[:12],
        "claims": (structured.get("claims") or [])[:5],
        "verificationStatus": structured.get("verificationStatus"),
        "verifiedFacts": (structured.get("verifiedFacts") or [])[:5],
        "corrections": (structured.get("corrections") or [])[:5],
        "unverifiedNotes": (structured.get("unverifiedNotes") or [])[:5],
    }


def answer_from_saved_content(
    request: KnowledgeAskRequest,
) -> KnowledgeAskResponse:
    question = " ".join(request.question.split()).strip()
    if not question:
        raise ValueError("질문을 입력해 주세요.")

    if not request.contexts:
        return KnowledgeAskResponse(
            answer="내 저장물에서 이 질문과 관련된 내용을 아직 찾지 못했어요.",
            citedContentIds=[],
        )

    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY가 설정되어 있지 않습니다.")

    contexts = [_compact_context(item) for item in request.contexts]
    allowed_ids = {item["contentId"] for item in contexts}

    prompt = f"""
USER QUESTION:
{question}

SAVED CONTENT:
{json.dumps(contexts, ensure_ascii=False, indent=2)}

Answer the user's question using ONLY SAVED CONTENT.
""".strip()

    client = genai.Client(api_key=GEMINI_API_KEY)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are Save:On's personal saved-content Q&A assistant. "
                "You answer questions only from content the user previously saved. "
                "Never use outside knowledge, web knowledge, or assumptions. "
                "If the supplied saved content is insufficient, explicitly say in Korean "
                "'저장한 콘텐츠만으로는 확인하기 어려워요.' and briefly explain what is missing. "
                "Prefer verifiedFacts and verifiedSummary-like information when present. "
                "Treat unverifiedNotes as uncertain and do not present them as established facts. "
                "If sources conflict, say that the saved contents disagree rather than choosing one. "
                "Write concise, natural Korean. "
                "SAVEON_QNA_TONE_V1. Do not open answers with filler such as 저장한 콘텐츠를 기반으로 분석한 결과 or 소개해 드리겠습니다. Lead with the answer if supported, then give grounded details naturally in Korean. "
                "citedContentIds must contain only content IDs that directly support the answer. "
                "Do not cite a content item merely because it is topically related."
            ),
            temperature=0.1,
            max_output_tokens=900,
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "citedContentIds": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                },
                "required": ["answer", "citedContentIds"],
            },
        ),
    )

    if not response.text:
        raise RuntimeError("Q&A 응답이 비어 있습니다.")

    parsed = json.loads(response.text)
    answer = " ".join(str(parsed.get("answer", "")).split()).strip()

    if not answer:
        raise RuntimeError("Q&A 답변 본문이 비어 있습니다.")

    cited: list[int] = []
    for value in parsed.get("citedContentIds", []):
        if isinstance(value, int) and value in allowed_ids and value not in cited:
            cited.append(value)

    return KnowledgeAskResponse(
        answer=answer[:2400],
        citedContentIds=cited[:6],
    )


@app.post(
    "/ask",
    response_model=KnowledgeAskResponse,
)
def ask(request: KnowledgeAskRequest):
    try:
        return answer_from_saved_content(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"저장물 Q&A 처리 실패: {exc}",
        ) from exc


@app.post(
    "/collections/name",
    response_model=CollectionNameResponse,
)
def name_collection(request: CollectionNameRequest):
    seed = " ".join(request.seed.split()).strip()

    # Gemini is optional here. Smart collections still work without it.
    if not GEMINI_API_KEY:
        fallback_title = seed or (
            request.categories[0]
            if request.categories
            else "자동 컬렉션"
        )
        return CollectionNameResponse(
            title=fallback_title[:40],
            description="같은 주제의 영상을 모아뒀어요.",
        )

    input_data = {
        "seed": seed,
        "titles": request.titles[:6],
        "summaries": request.summaries[:6],
        "categories": request.categories[:6],
        "keywords": request.keywords[:12],
        "entities": request.entities[:12],
    }

    prompt = f"""
Saved contents were grouped automatically because they are semantically
similar. Give this group a short, natural Korean collection title and one
short description.

DATA:
{json.dumps(input_data, ensure_ascii=False, indent=2)}
""".strip()

    client = genai.Client(api_key=GEMINI_API_KEY)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=(
                "You name Save:On smart collections. "
                "Describe only what is supported by the supplied saved contents. "
                "The title should feel like a user's folder name, ideally 2-12 Korean characters "
                "or a short phrase such as '성수 카페', '올리브영 할인', '나트랑 여행'. "
                "Do not use technical terms such as entity, embedding, semantic, cluster, AI. "
                "Do not add unsupported places, products, brands, dates, or recommendations. "
                "The description must be one concise Korean sentence explaining what the saved items have in common."
                "SAVEON_COLLECTION_NAME_TONE_V1. Write the description like a simple natural Korean folder note, not a marketing blurb. Avoid repetitive fillers such as 소개합니다, 공유합니다, and 자동으로 모았어요. Prefer specific shared topics supported by the supplied items. "
            ),
            temperature=0.2,
            max_output_tokens=220,
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["title", "description"],
            },
        ),
    )

    if not response.text:
        raise HTTPException(
            status_code=503,
            detail="스마트 컬렉션 이름 응답이 비어 있습니다.",
        )

    parsed = json.loads(response.text)
    title = " ".join(str(parsed.get("title", "")).split()).strip()
    description = " ".join(
        str(parsed.get("description", "")).split()
    ).strip()

    if not title:
        title = seed or "자동 컬렉션"

    if not description:
        description = "같은 주제의 영상을 모아뒀어요."

    return CollectionNameResponse(
        title=title[:50],
        description=description[:240],
    )


@app.post(
    "/conflicts/detect",
    response_model=ConflictDetectResponse,
)
def detect_conflicts(request: ConflictDetectRequest):
    claims = request.claims[:40]

    if len(claims) < 2:
        return ConflictDetectResponse(conflicts=[])

    if not GEMINI_API_KEY:
        return ConflictDetectResponse(conflicts=[])

    compact = [
        {
            "contentId": claim.contentId,
            "title": claim.title[:160],
            "subject": claim.subject[:100],
            "claimType": claim.claimType[:60],
            "claimText": claim.claimText[:500],
            "verificationStatus": claim.verificationStatus[:60],
            "factChecks": claim.factChecks[:3],
        }
        for claim in claims
    ]

    prompt = f"""
Compare the following claims extracted from the user's saved contents.

CLAIMS:
{json.dumps(compact, ensure_ascii=False, indent=2)}

Return ONLY genuine contradictions between different saved contents.
""".strip()

    client = genai.Client(api_key=GEMINI_API_KEY)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are Save:On's contradiction detector for a user's saved contents. "
                "A contradiction exists only when two claims concern the SAME subject and SAME factual dimension "
                "but cannot both be true at the same time. "
                "Examples: the same event starts on Nov 4 vs Nov 5; the same product price is 29,000 won vs 39,000 won "
                "for the same sale context; the same store closes at 21:00 vs 22:00. "
                "Do NOT mark complementary facts, different branches, different dates/conditions, opinions, vague wording, "
                "or merely different levels of detail as contradictions. "
                "Be conservative: when context is insufficient, return no conflict. "
                "Use only the supplied claims. Do not use web knowledge. "
                "For each conflict, cite exactly the content IDs and claim texts that conflict. "
                "title and description must be concise natural Korean for end users. "
                "Avoid technical words such as claim, entity, embedding, model, semantic, validation. "
                "severity should normally be WARN; use ERROR only when both supplied facts are explicit and directly incompatible."
            ),
            temperature=0.0,
            max_output_tokens=1200,
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "conflicts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "subject": {"type": "string"},
                                "claimType": {"type": "string"},
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "severity": {"type": "string"},
                                "evidences": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "contentId": {"type": "integer"},
                                            "claimText": {"type": "string"},
                                            "value": {"type": "string"},
                                        },
                                        "required": ["contentId", "claimText", "value"],
                                    },
                                },
                            },
                            "required": [
                                "subject",
                                "claimType",
                                "title",
                                "description",
                                "severity",
                                "evidences",
                            ],
                        },
                    },
                },
                "required": ["conflicts"],
            },
        ),
    )

    if not response.text:
        return ConflictDetectResponse(conflicts=[])

    parsed = json.loads(response.text)
    allowed_ids = {claim.contentId for claim in claims}
    result: list[ConflictItemOutput] = []

    for item in parsed.get("conflicts", [])[:10]:
        evidences = []
        seen_ids = set()

        for evidence in item.get("evidences", [])[:4]:
            content_id = evidence.get("contentId")
            if (
                not isinstance(content_id, int)
                or content_id not in allowed_ids
                or content_id in seen_ids
            ):
                continue

            seen_ids.add(content_id)
            evidences.append(
                ConflictEvidenceOutput(
                    contentId=content_id,
                    claimText=str(evidence.get("claimText", "")).strip()[:500],
                    value=str(evidence.get("value", "")).strip()[:120],
                )
            )

        if len(evidences) < 2:
            continue

        result.append(
            ConflictItemOutput(
                subject=str(item.get("subject", "")).strip()[:100],
                claimType=str(item.get("claimType", "")).strip()[:60],
                title=str(item.get("title", "")).strip()[:120],
                description=str(item.get("description", "")).strip()[:300],
                severity=(
                    "ERROR"
                    if str(item.get("severity", "")).upper() == "ERROR"
                    else "WARN"
                ),
                evidences=evidences,
            )
        )

    return ConflictDetectResponse(conflicts=result)


from datetime import datetime, timezone


OBJECTIVE_EXTERNAL_FIELDS = {
    "PRICE",
    "CAPACITY",
    "SIZE",
    "RELEASE_DATE",
    "EVENT_PERIOD",
    "OFFICIAL_NAME",
    "LOCATION",
    "OPENING_HOURS",
    "CLOSED_DAYS",
}


def _get_grounding_value(value, name: str):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _extract_grounding_sources(response) -> list[ExternalSourceOutput]:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return []

    metadata = _get_grounding_value(candidates[0], "grounding_metadata")
    chunks = _get_grounding_value(metadata, "grounding_chunks") or []

    result: list[ExternalSourceOutput] = []
    seen: set[str] = set()

    for chunk in chunks:
        web = _get_grounding_value(chunk, "web")
        if not web:
            continue

        url = str(_get_grounding_value(web, "uri") or "").strip()
        title = str(_get_grounding_value(web, "title") or "").strip()

        if not url or url in seen:
            continue

        seen.add(url)
        result.append(
            ExternalSourceOutput(
                title=(title or url)[:200],
                url=url,
            )
        )
        if len(result) >= 5:
            break

    return result


def _compact_compare_context(
    context: CollectionCompareContext,
) -> dict:
    structured = context.structured or {}

    return {
        "contentId": context.contentId,
        "title": context.title[:180],
        "summary": context.summary[:1400],
        "categories": context.categories[:5],
        "keywords": context.keywords[:12],
        "entities": context.entities[:12],
        "primaryCategory": structured.get("primaryCategory"),
        "contentType": structured.get("contentType"),
        "tags": (structured.get("tags") or [])[:12],
        "entityDetails": (structured.get("entityDetails") or [])[:12],
        "claims": (structured.get("claims") or [])[:6],
        "videoObservations": (structured.get("videoObservations") or [])[:12],
        "verifiedFacts": (structured.get("verifiedFacts") or [])[:6],
        "verificationStatus": structured.get("verificationStatus"),
        "corrections": (structured.get("corrections") or [])[:6],
        "unverifiedNotes": (structured.get("unverifiedNotes") or [])[:6],
    }


def _clean_evidence(raw: dict, allowed_ids: set[int]) -> EvidenceOutput | None:
    if not isinstance(raw, dict):
        return None

    content_id = raw.get("contentId")
    if not isinstance(content_id, int) or content_id not in allowed_ids:
        return None

    timestamp = raw.get("timestampSeconds")
    if not isinstance(timestamp, (int, float)) or timestamp < 0:
        timestamp = None

    return EvidenceOutput(
        contentId=content_id,
        title=" ".join(str(raw.get("title", "")).split()).strip()[:180],
        quote=" ".join(str(raw.get("quote", "")).split()).strip()[:500],
        timestampSeconds=float(timestamp) if timestamp is not None else None,
    )


def _clean_findings(
    value,
    allowed_ids: set[int],
    max_items: int,
) -> list[ComparisonFindingOutput]:
    if not isinstance(value, list):
        return []

    result: list[ComparisonFindingOutput] = []

    for raw in value[:max_items]:
        if not isinstance(raw, dict):
            continue

        evidences: list[EvidenceOutput] = []
        for evidence_raw in raw.get("evidences", []):
            evidence = _clean_evidence(evidence_raw, allowed_ids)
            if evidence is not None:
                evidences.append(evidence)

        statement = " ".join(
            str(raw.get("statement", "")).split()
        ).strip()

        if not statement or not evidences:
            continue

        result.append(
            ComparisonFindingOutput(
                topic=" ".join(
                    str(raw.get("topic", "")).split()
                ).strip()[:100] or "비교 항목",
                statement=statement[:700],
                evidences=evidences[:8],
            )
        )

    return result


def _clean_objective_disagreements(
    value,
    allowed_ids: set[int],
) -> list[ObjectiveDisagreementOutput]:
    if not isinstance(value, list):
        return []

    result: list[ObjectiveDisagreementOutput] = []

    for raw in value[:8]:
        if not isinstance(raw, dict):
            continue

        field = str(raw.get("field", "")).strip().upper()
        if field not in OBJECTIVE_EXTERNAL_FIELDS:
            continue

        values: list[str] = []
        seen_values: set[str] = set()

        for item in raw.get("values", []):
            cleaned = " ".join(str(item).split()).strip()
            normalized = cleaned.lower()
            if cleaned and normalized not in seen_values:
                seen_values.add(normalized)
                values.append(cleaned[:200])

        # 외부 검색 trigger의 핵심 규칙:
        # 실제 저장물 사이에 서로 다른 값이 2개 이상 있어야 한다.
        if len(values) < 2:
            continue

        evidences: list[EvidenceOutput] = []
        evidence_ids: set[int] = set()
        for evidence_raw in raw.get("evidences", []):
            evidence = _clean_evidence(evidence_raw, allowed_ids)
            if evidence is not None:
                evidences.append(evidence)
                evidence_ids.add(evidence.contentId)

        # 한 영상 내부 표현 차이가 아니라 서로 다른 영상 간 불일치여야 함.
        if len(evidence_ids) < 2:
            continue

        result.append(
            ObjectiveDisagreementOutput(
                field=field,
                label=" ".join(
                    str(raw.get("label", "")).split()
                ).strip()[:100] or field,
                entity=" ".join(
                    str(raw.get("entity", "")).split()
                ).strip()[:160],
                values=values[:6],
                evidences=evidences[:8],
            )
        )

    return result[:3]


# SAVEON_COMPARE_GROUNDING_V5

def _audit_comparison_evidence(checks: list[dict]) -> dict[str, bool]:
    """Independently check whether each cited quote entails the exact assertion.

    Any failure returns no approvals: unverified conclusions are not shown.
    """
    if not checks:
        return {}

    prompt = (
        "For each check, decide whether the QUOTE alone DIRECTLY entails the "
        "entire STATEMENT. Reject topic-only overlap, wording that exaggerates "
        "a feature into a positive evaluation, missing numbers, approximate "
        "values inferred as precise, and claims about current official prices "
        "from raw OCR. The quote is from a saved video, not external truth. "
        "Do not assume any information not in the quote. "
        "Examples: 'all colors reviewed' does NOT prove '5 colors released'; "
        "'brush application tip' does NOT prove 'excellent pore coverage'. "
        "Return one boolean per supplied key. Checks: "
        + json.dumps(checks, ensure_ascii=False)
    )
    try:
        response = genai.Client(api_key=GEMINI_API_KEY).models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=2400,
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "checks": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "key": {"type": "string"},
                                    "supported": {"type": "boolean"},
                                },
                                "required": ["key", "supported"],
                            },
                        }
                    },
                    "required": ["checks"],
                },
            ),
        )
        if not response.text:
            return {}
        data = json.loads(response.text)
        valid_keys = {x["key"] for x in checks}
        return {
            str(item["key"]): item["supported"]
            for item in data.get("checks", [])
            if isinstance(item, dict)
            and item.get("key") in valid_keys
            and type(item.get("supported")) is bool
        }
    except Exception as exc:
        # Do not leak full saved-video context to logs.
        print(f"[SAVEON] comparison evidence audit unavailable: {type(exc).__name__}")
        return {}


def _build_saved_comparison(
    request: CollectionCompareRequest,
) -> tuple[dict, list[ObjectiveDisagreementOutput]]:
    if len(request.contexts) < 2:
        raise ValueError("비교하려면 저장물이 2개 이상 필요해요.")

    if not request.comparisonEntity.strip():
        return {
            "eligible": False,
            "reason": "같은 주요 정보가 2개 이상의 저장물에서 반복되지 않았어요.",
            "comparisonEntity": "",
            "title": request.collectionTitle or "저장물 비교",
            "summary": "이 묶음은 비교보다 관심 정보 모아보기가 더 잘 맞아요.",
            "commonPoints": [],
            "disagreements": [],
            "uniqueMentions": [],
            "objectiveDisagreements": [],
            "citedContentIds": [],
        }, []

    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY가 설정되어 있지 않습니다.")

    contexts = [
        _compact_compare_context(context)
        for context in request.contexts[:8]
    ]
    allowed_ids = {
        context["contentId"]
        for context in contexts
    }

    prompt = f"""
COMPARISON ENTITY:
{request.comparisonEntity}

COLLECTION:
{request.collectionTitle}

SAVED CONTENTS:
{json.dumps(contexts, ensure_ascii=False, indent=2)}

Analyze only the saved contents above.

Return:
1. commonPoints:
   claims/opinions/features supported by at least 2 DIFFERENT saved videos.
2. disagreements:
   places where different saved videos express meaningfully different or
   opposing assessments/claims about the SAME topic.
3. uniqueMentions:
   useful information that appears in only one saved video.
4. objectiveDisagreements:
   only when at least 2 DIFFERENT videos contain DIFFERENT explicit values
   for the same objective field.

Allowed objective fields:
PRICE, CAPACITY, SIZE, RELEASE_DATE, EVENT_PERIOD, OFFICIAL_NAME,
LOCATION, OPENING_HOURS, CLOSED_DAYS.

Do not create an objective disagreement when:
- only one video mentions the field
- the values are actually equivalent
- the difference is subjective
- the information is missing

Prioritize videoObservations for concrete review outcomes when available.
Each videoObservation has a topic, source and verbatim quote. DIRECT_STATEMENT
means the creator said something specific, not that the statement is verified.
TOPIC_MENTION is NOT evidence of a positive/negative outcome, and OCR_UNVERIFIED
is never sufficient on its own to establish a product verdict, price or shade count.
Never infer a test's result from the test's title. Separate measured outcomes,
creator opinions, review topics and unverified on-screen text.

Every finding must cite the saved video(s) using contentId and a quote
copied VERBATIM as a continuous substring of that saved video's title,
summary, keywords, entities, tags, claims, or verifiedFacts.
Never invent or paraphrase evidence quotes.
A claim is common ONLY if at least two different saved videos each
directly support that full same claim, not merely the broad topic.
A statement such as 'excellent pore coverage' needs explicit praise
in every cited quote; an application tip is not evidence of excellence.
For numeric claims, every cited quote must explicitly give that
number or the same Korean count word, not 'all colors'.
UniqueMentions should emphasize concrete, video-specific facts and
tips, with precisely one directly supporting video each.
Do not turn unverified OCR text into an established official price.

timestampSeconds must be null unless an actual timestamp is present in
the supplied data. Never invent timestamps.
""".strip()

    client = genai.Client(api_key=GEMINI_API_KEY)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are Save:On's saved-video comparison engine. "
                "The user's saved reels/shorts are the only evidence for the comparison. "
                "Do not import outside facts into common points, disagreements, or unique mentions. "
                "The highest-value output is finding real disagreements between videos. "
                "Preserve disagreement instead of deciding which creator is correct. "
                "Do not recommend what the user should buy, visit, or choose. "
                "Provide decision material only. "
                "SAVEON_COMPARE_TONE_V1. Write the user-facing Korean findings plainly and briefly, without AI-style narration. Never trade away a necessary evidence caveat for brevity or imply agreement from a shared topic. "
                "Prefer verifiedFacts and user corrections over raw claims when present. "
                "If evidence is insufficient, omit the finding. "
                "Never invent a timestamp."
            ),
            temperature=0.05,
            max_output_tokens=2200,
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "commonPoints": {
                        "type": "array",
                        "maxItems": 6,
                        "items": {
                            "type": "object",
                            "properties": {
                                "topic": {"type": "string"},
                                "statement": {"type": "string"},
                                "evidences": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "contentId": {"type": "integer"},
                                            "title": {"type": "string"},
                                            "quote": {"type": "string"},
                                            "timestampSeconds": {
                                                "type": "NUMBER", "nullable": True
                                            },
                                        },
                                        "required": [
                                            "contentId",
                                            "title",
                                            "quote",
                                            "timestampSeconds",
                                        ],
                                    },
                                },
                            },
                            "required": ["topic", "statement", "evidences"],
                        },
                    },
                    "disagreements": {
                        "type": "array",
                        "maxItems": 6,
                        "items": {
                            "type": "object",
                            "properties": {
                                "topic": {"type": "string"},
                                "statement": {"type": "string"},
                                "evidences": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "contentId": {"type": "integer"},
                                            "title": {"type": "string"},
                                            "quote": {"type": "string"},
                                            "timestampSeconds": {
                                                "type": "NUMBER", "nullable": True
                                            },
                                        },
                                        "required": [
                                            "contentId",
                                            "title",
                                            "quote",
                                            "timestampSeconds",
                                        ],
                                    },
                                },
                            },
                            "required": ["topic", "statement", "evidences"],
                        },
                    },
                    "uniqueMentions": {
                        "type": "array",
                        "maxItems": 6,
                        "items": {
                            "type": "object",
                            "properties": {
                                "topic": {"type": "string"},
                                "statement": {"type": "string"},
                                "evidences": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "contentId": {"type": "integer"},
                                            "title": {"type": "string"},
                                            "quote": {"type": "string"},
                                            "timestampSeconds": {
                                                "type": "NUMBER", "nullable": True
                                            },
                                        },
                                        "required": [
                                            "contentId",
                                            "title",
                                            "quote",
                                            "timestampSeconds",
                                        ],
                                    },
                                },
                            },
                            "required": ["topic", "statement", "evidences"],
                        },
                    },
                    "objectiveDisagreements": {
                        "type": "array",
                        "maxItems": 8,
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {
                                    "type": "string",
                                    "enum": sorted(OBJECTIVE_EXTERNAL_FIELDS),
                                },
                                "label": {"type": "string"},
                                "entity": {"type": "string"},
                                "values": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "evidences": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "contentId": {"type": "integer"},
                                            "title": {"type": "string"},
                                            "quote": {"type": "string"},
                                            "timestampSeconds": {
                                                "type": "NUMBER", "nullable": True
                                            },
                                        },
                                        "required": [
                                            "contentId",
                                            "title",
                                            "quote",
                                            "timestampSeconds",
                                        ],
                                    },
                                },
                            },
                            "required": [
                                "field",
                                "label",
                                "entity",
                                "values",
                                "evidences",
                            ],
                        },
                    },
                    "citedContentIds": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                },
                "required": [
                    "title",
                    "summary",
                    "commonPoints",
                    "disagreements",
                    "uniqueMentions",
                    "objectiveDisagreements",
                    "citedContentIds",
                ],
            },
        ),
    )

    if not response.text:
        raise RuntimeError("컬렉션 비교 응답이 비어 있습니다.")

    parsed = json.loads(response.text)
    parsed = ground_comparison_results(
        parsed, contexts, semantic_audit=_audit_comparison_evidence,
        fallback_when_empty=True,
        comparison_entity=request.comparisonEntity,
    )  # SAVEON_COMPARE_GROUNDING_V6

    common_points = _clean_findings(
        parsed.get("commonPoints"),
        allowed_ids,
        6,
    )
    disagreements = _clean_findings(
        parsed.get("disagreements"),
        allowed_ids,
        6,
    )
    unique_mentions = _clean_findings(
        parsed.get("uniqueMentions"),
        allowed_ids,
        6,
    )
    objective_disagreements = _clean_objective_disagreements(
        parsed.get("objectiveDisagreements"),
        allowed_ids,
    )

    cited: list[int] = []
    for collection in (
        common_points,
        disagreements,
        unique_mentions,
    ):
        for finding in collection:
            for evidence in finding.evidences:
                if evidence.contentId not in cited:
                    cited.append(evidence.contentId)

    return {
        "eligible": True,
        "reason": "",
        "comparisonEntity": request.comparisonEntity,
        "title": " ".join(
            str(parsed.get("title", "")).split()
        ).strip()[:120] or f"{request.comparisonEntity} 저장물 비교",
        "summary": (
            f"저장 영상 {len(contexts)}개를 비교해 근거가 확인된 공통점 "
            f"{len(common_points)}개, 엇갈리는 점 {len(disagreements)}개, "
            f"영상별 정보 {len(unique_mentions)}개를 정리했어요. "
            "근거가 부족한 주장은 제외했어요."
        ),
        "commonPoints": common_points,
        "disagreements": disagreements,
        "uniqueMentions": unique_mentions,
        "objectiveDisagreements": objective_disagreements,
        "citedContentIds": cited[:8],
    }, objective_disagreements


def _verify_external_disagreement(
    disagreement: ObjectiveDisagreementOutput,
) -> ExternalFactOutput:
    client = genai.Client(api_key=GEMINI_API_KEY)
    grounding_tool = types.Tool(
        google_search=types.GoogleSearch()
    )

    saved_values_text = " / ".join(disagreement.values)

    prompt = f"""
The user's saved videos disagree on an objective fact.

Entity: {disagreement.entity}
Field: {disagreement.field}
Label: {disagreement.label}
Saved video values: {saved_values_text}

Find the CURRENT authoritative information.
Prefer official brand/store/venue/government/primary sources.

Do not declare a saved video "wrong" merely because the current value differs.
The saved video may be older. Explain the current value and preserve the
historical saved values separately.
""".strip()

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[grounding_tool],
            system_instruction=(
                "You are Save:On's objective external verification layer. "
                "You are invoked only because at least two saved videos contain "
                "different explicit values for the same objective field. "
                "Return the current authoritative value if available. "
                "Never overwrite or erase the saved-video values. "
                "Prefer official primary sources. "
                "If authoritative evidence is unavailable or ambiguous, return "
                "INSUFFICIENT_EVIDENCE. "
                "SUPPORTED means one current authoritative value matches a saved value. "
                "UPDATED means the current authoritative value differs plausibly because "
                "the information may have changed over time. "
                "CONFLICTING means authoritative evidence directly conflicts with the "
                "saved claims in a way not reasonably explained by time/version/context."
            ),
            temperature=0.05,
            max_output_tokens=650,
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": [
                            "SUPPORTED",
                            "UPDATED",
                            "CONFLICTING",
                            "INSUFFICIENT_EVIDENCE",
                        ],
                    },
                    "currentValue": {"type": "string"},
                    "explanation": {"type": "string"},
                },
                "required": [
                    "status",
                    "currentValue",
                    "explanation",
                ],
            },
        ),
    )

    checked_at = datetime.now(timezone.utc).isoformat()

    if not response.text:
        return ExternalFactOutput(
            label=disagreement.label,
            field=disagreement.field,
            entity=disagreement.entity,
            savedValues=disagreement.values,
            status="INSUFFICIENT_EVIDENCE",
            currentValue="",
            explanation="현재 외부 근거를 확인하지 못했어요.",
            checkedAt=checked_at,
            sources=[],
        )

    parsed = json.loads(response.text)
    sources = _extract_grounding_sources(response)

    status = str(
        parsed.get("status", "INSUFFICIENT_EVIDENCE")
    ).strip().upper()

    allowed = {
        "SUPPORTED",
        "UPDATED",
        "CONFLICTING",
        "INSUFFICIENT_EVIDENCE",
    }
    if status not in allowed:
        status = "INSUFFICIENT_EVIDENCE"

    if not sources and status != "INSUFFICIENT_EVIDENCE":
        status = "INSUFFICIENT_EVIDENCE"

    return ExternalFactOutput(
        label=disagreement.label,
        field=disagreement.field,
        entity=disagreement.entity,
        savedValues=disagreement.values,
        status=status,
        currentValue=" ".join(
            str(parsed.get("currentValue", "")).split()
        ).strip()[:500],
        explanation=" ".join(
            str(parsed.get("explanation", "")).split()
        ).strip()[:700],
        checkedAt=checked_at,
        sources=sources,
    )


@app.post(
    "/collections/compare",
    response_model=CollectionCompareResponse,
)
def compare_collection(request: CollectionCompareRequest):
    try:
        comparison, objective_disagreements = _build_saved_comparison(
            request
        )

        external_facts: list[ExternalFactOutput] = []

        if comparison["eligible"] and request.autoVerifyExternal:
            for disagreement in objective_disagreements[:3]:
                try:
                    external_facts.append(
                        _verify_external_disagreement(disagreement)
                    )
                except Exception as exc:
                    external_facts.append(
                        ExternalFactOutput(
                            label=disagreement.label,
                            field=disagreement.field,
                            entity=disagreement.entity,
                            savedValues=disagreement.values,
                            status="INSUFFICIENT_EVIDENCE",
                            currentValue="",
                            explanation=(
                                "외부 근거를 확인하지 못했어요: "
                                + str(exc)
                            )[:700],
                            checkedAt=datetime.now(
                                timezone.utc
                            ).isoformat(),
                            sources=[],
                        )
                    )

        return CollectionCompareResponse(
            eligible=comparison["eligible"],
            reason=comparison["reason"],
            comparisonEntity=comparison["comparisonEntity"],
            title=comparison["title"],
            summary=comparison["summary"],
            commonPoints=comparison["commonPoints"],
            disagreements=comparison["disagreements"],
            uniqueMentions=comparison["uniqueMentions"],
            objectiveDisagreements=comparison[
                "objectiveDisagreements"
            ],
            externalFacts=external_facts,
            citedContentIds=comparison["citedContentIds"],
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"컬렉션 비교 실패: {exc}",
        ) from exc
