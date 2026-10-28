from __future__ import annotations

import json
import os

from google import genai
from google.genai import types

from services.fact_verifier import FACT_CHECK_ENABLED
from services.llm_postprocessor import GEMINI_API_KEY, GEMINI_MODEL


VERIFIED_SUMMARY_MODEL = os.getenv(
    "GEMINI_VERIFIED_SUMMARY_MODEL",
    GEMINI_MODEL,
)

VERIFICATION_STATUSES = [
    "NOT_RUN",
    "NO_VERIFIABLE_CLAIMS",
    "VERIFIED",
    "PARTIALLY_VERIFIED",
    "INSUFFICIENT_EVIDENCE",
]


def _verification_status(structured: dict) -> str:
    claims = [
        claim
        for claim in structured.get("claims", [])
        if isinstance(claim, dict) and claim.get("verifiable")
    ]
    checks = [
        check
        for check in structured.get("factChecks", [])
        if isinstance(check, dict)
    ]

    if not FACT_CHECK_ENABLED:
        return "NOT_RUN"
    if not claims:
        return "NO_VERIFIABLE_CLAIMS"
    if not checks:
        return "INSUFFICIENT_EVIDENCE"

    verdicts = {
        str(check.get("verdict", "")).upper()
        for check in checks
    }
    if verdicts == {"SUPPORTED"}:
        return "VERIFIED"
    if verdicts == {"INSUFFICIENT_EVIDENCE"}:
        return "INSUFFICIENT_EVIDENCE"
    return "PARTIALLY_VERIFIED"


def _compact_fact_checks(structured: dict) -> list[dict]:
    compact: list[dict] = []

    for index, check in enumerate(
        structured.get("factChecks", [])
    ):
        if not isinstance(check, dict):
            continue

        sources = []
        for source in check.get("sources", [])[:5]:
            if not isinstance(source, dict):
                continue
            sources.append({
                "title": str(source.get("title", ""))[:200],
                "url": str(source.get("url", ""))[:1000],
            })

        compact.append({
            "factCheckIndex": index,
            "claim": str(check.get("claim", ""))[:240],
            "verdict": str(check.get("verdict", "")),
            "explanation": str(check.get("explanation", ""))[:500],
            "sources": sources,
        })

    return compact


def _generate_verified_summary(
    raw_summary: str,
    structured: dict,
) -> dict:
    client = genai.Client(api_key=GEMINI_API_KEY)
    fact_checks = _compact_fact_checks(structured)

    prompt = f"""
Original video summary:
{raw_summary}

Fact-check results:
{json.dumps(fact_checks, ensure_ascii=False)}

Rewrite the final user-facing summary in Korean using the rules in the
system instruction. Keep it concise and useful. Every verifiedFact must cite
the zero-based factCheckIndex values that support it. Do not output URLs.
""".strip()

    response = client.models.generate_content(
        model=VERIFIED_SUMMARY_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are Save:On's verification editor. You do not search "
                "the web yourself. Use only the supplied fact-check results. "
                "SUPPORTED claims may be stated as facts. "
                "PARTIALLY_SUPPORTED claims must be qualified. "
                "CONFLICTING claims must be corrected using the supplied "
                "explanation. INSUFFICIENT_EVIDENCE claims must not be stated "
                "as facts and must be identified as unverified. Never invent "
                "facts, sources, dates, prices, places, or URLs."
            ),
            temperature=0.1,
            max_output_tokens=800,
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "verifiedSummary": {"type": "string"},
                    "verifiedFacts": {
                        "type": "array",
                        "maxItems": 5,
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "factCheckIndexes": {
                                    "type": "array",
                                    "items": {"type": "integer"},
                                },
                            },
                            "required": ["text", "factCheckIndexes"],
                        },
                    },
                    "corrections": {
                        "type": "array",
                        "maxItems": 5,
                        "items": {"type": "string"},
                    },
                    "unverifiedNotes": {
                        "type": "array",
                        "maxItems": 5,
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "verifiedSummary",
                    "verifiedFacts",
                    "corrections",
                    "unverifiedNotes",
                ],
            },
        ),
    )

    if not response.text:
        raise RuntimeError("검증 요약 응답이 비어 있습니다.")

    parsed = json.loads(response.text)
    verified_summary = " ".join(
        str(parsed.get("verifiedSummary", "")).split()
    ).strip()
    if not verified_summary:
        raise RuntimeError("검증 요약 본문이 비어 있습니다.")

    valid_indexes = set(range(len(fact_checks)))
    verified_facts: list[dict] = []
    for item in parsed.get("verifiedFacts", []):
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get("text", "")).split()).strip()
        indexes = [
            index
            for index in item.get("factCheckIndexes", [])
            if isinstance(index, int) and index in valid_indexes
        ]
        if text and indexes:
            verified_facts.append({
                "text": text[:300],
                "factCheckIndexes": list(dict.fromkeys(indexes)),
            })

    def normalize_notes(name: str) -> list[str]:
        notes: list[str] = []
        for value in parsed.get(name, []):
            text = " ".join(str(value).split()).strip()
            if text and text not in notes:
                notes.append(text[:300])
        return notes[:5]

    return {
        "verifiedSummary": verified_summary[:1600],
        "verifiedFacts": verified_facts[:5],
        "corrections": normalize_notes("corrections"),
        "unverifiedNotes": normalize_notes("unverifiedNotes"),
    }


def apply_verified_summary(result: dict) -> dict:
    structured = dict(result.get("structured") or {})
    raw_summary = str(result.get("summary", "")).strip()
    status = _verification_status(structured)

    structured["rawSummary"] = raw_summary
    structured["verificationStatus"] = status
    structured["verifiedSummary"] = None
    structured["verifiedFacts"] = []
    structured["corrections"] = []
    structured["unverifiedNotes"] = []
    structured["summarySource"] = "RAW_ANALYSIS"

    if status in {"NOT_RUN", "NO_VERIFIABLE_CLAIMS"}:
        result["structured"] = structured
        return result

    if not GEMINI_API_KEY:
        structured["verificationStatus"] = "INSUFFICIENT_EVIDENCE"
        result["structured"] = structured
        return result

    try:
        generated = _generate_verified_summary(
            raw_summary,
            structured,
        )
        structured.update(generated)
        structured["summarySource"] = "VERIFIED_SYNTHESIS"
        result["summary"] = generated["verifiedSummary"]
    except Exception as exc:
        print(f"[VERIFIED SUMMARY] 생성 실패 - 원 요약 유지: {exc}")

    result["structured"] = structured
    return result
