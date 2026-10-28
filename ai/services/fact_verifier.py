from __future__ import annotations

import json
import os

from google import genai
from google.genai import types

from services.llm_postprocessor import GEMINI_API_KEY, GEMINI_MODEL


FACT_CHECK_ENABLED = os.getenv(
    "FACT_CHECK_ENABLED",
    "false",
).lower() in {"1", "true", "yes", "on"}
FACT_CHECK_MODEL = os.getenv(
    "GEMINI_FACT_CHECK_MODEL",
    GEMINI_MODEL,
)
MAX_FACT_CHECK_CLAIMS = int(
    os.getenv("MAX_FACT_CHECK_CLAIMS", "3")
)

VERDICTS = [
    "SUPPORTED",
    "PARTIALLY_SUPPORTED",
    "CONFLICTING",
    "INSUFFICIENT_EVIDENCE",
]


def _get_value(value, name: str):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _extract_sources(response) -> list[dict]:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return []

    metadata = _get_value(candidates[0], "grounding_metadata")
    chunks = _get_value(metadata, "grounding_chunks") or []
    sources: list[dict] = []
    seen: set[str] = set()

    for chunk in chunks:
        web = _get_value(chunk, "web")
        if not web:
            continue

        url = str(_get_value(web, "uri") or "").strip()
        title = str(_get_value(web, "title") or "").strip()
        if not url or url in seen:
            continue

        seen.add(url)
        sources.append({
            "title": title[:200] or url,
            "url": url,
        })

        if len(sources) >= 5:
            break

    return sources


def _verify_claim(claim: dict) -> dict:
    claim_text = str(claim.get("text", "")).strip()
    search_query = str(claim.get("searchQuery", "")).strip()

    client = genai.Client(api_key=GEMINI_API_KEY)
    grounding_tool = types.Tool(
        google_search=types.GoogleSearch()
    )

    prompt = f"""
Verify the following claim using current web evidence.

Claim: {claim_text}
Suggested search query: {search_query}

Prefer official primary sources. If reliable evidence is missing, choose
INSUFFICIENT_EVIDENCE. Do not treat search snippets alone as conclusive.
Return a concise Korean explanation and JSON only.
""".strip()

    response = client.models.generate_content(
        model=FACT_CHECK_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[grounding_tool],
            temperature=0.1,
            max_output_tokens=500,
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "verdict": {
                        "type": "string",
                        "enum": VERDICTS,
                    },
                    "confidence": {"type": "number"},
                    "explanation": {"type": "string"},
                },
                "required": [
                    "verdict",
                    "confidence",
                    "explanation",
                ],
            },
        ),
    )

    if not response.text:
        raise RuntimeError("Gemini 사실 검증 응답이 비어 있습니다.")

    parsed = json.loads(response.text)
    verdict = str(parsed.get("verdict", "")).strip().upper()
    if verdict not in VERDICTS:
        verdict = "INSUFFICIENT_EVIDENCE"

    try:
        confidence = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    sources = _extract_sources(response)
    if not sources and verdict != "INSUFFICIENT_EVIDENCE":
        verdict = "INSUFFICIENT_EVIDENCE"
        confidence = min(confidence, 0.3)

    return {
        "claim": claim_text,
        "claimType": claim.get("type", "OTHER"),
        "verdict": verdict,
        "confidence": confidence,
        "explanation": str(parsed.get("explanation", "")).strip()[:500],
        "sources": sources,
    }


def verify_structured_claims(structured: dict) -> dict:
    if not FACT_CHECK_ENABLED:
        return structured
    if not GEMINI_API_KEY:
        print("[FACT CHECK] GEMINI_API_KEY 없음 - 검증 건너뜀")
        return structured

    claims = [
        claim
        for claim in structured.get("claims", [])
        if isinstance(claim, dict) and claim.get("verifiable")
    ][:max(0, MAX_FACT_CHECK_CLAIMS)]

    checks: list[dict] = []
    for claim in claims:
        try:
            checks.append(_verify_claim(claim))
        except Exception as exc:
            print(f"[FACT CHECK] 주장 검증 실패 - 계속 진행: {exc}")
            checks.append({
                "claim": str(claim.get("text", "")),
                "claimType": claim.get("type", "OTHER"),
                "verdict": "INSUFFICIENT_EVIDENCE",
                "confidence": 0.0,
                "explanation": "검색 근거를 확인하지 못했습니다.",
                "sources": [],
            })

    structured["factChecks"] = checks
    return structured

