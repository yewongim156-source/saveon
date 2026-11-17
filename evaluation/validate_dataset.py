from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit


CATEGORIES = {
    "장소/여행",
    "음식/레시피",
    "제품/쇼핑",
    "뷰티/패션",
    "학습/커리어",
    "건강/운동",
    "생활정보",
    "엔터테인먼트",
    "기타",
}
CONTENT_TYPES = {
    "PLACE_RECOMMENDATION",
    "HOW_TO",
    "PRODUCT_REVIEW",
    "RECIPE",
    "EVENT_INFO",
    "EDUCATIONAL",
    "NEWS_CLAIM",
    "OTHER",
}
MODALITIES = {"STT", "OCR", "VISION", "METADATA"}
ANNOTATION_STATUSES = {"DRAFT", "SINGLE_REVIEWED", "ADJUDICATED"}


def _check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    items = payload.get("items")
    _check(isinstance(items, list) and bool(items), "items must be non-empty", errors)
    if not isinstance(items, list):
        return errors

    ids: set[str] = set()
    for index, item in enumerate(items):
        prefix = f"items[{index}]"
        item_id = item.get("id")
        _check(isinstance(item_id, str) and item_id.startswith("pilot-"), f"{prefix}: invalid id", errors)
        _check(item_id not in ids, f"{prefix}: duplicate id {item_id}", errors)
        ids.add(item_id)

        source = item.get("source", {})
        duration = source.get("durationSeconds")
        _check(isinstance(duration, int) and 1 <= duration <= 120, f"{prefix}: duration must be 1..120", errors)
        parsed = urlsplit(str(source.get("url", "")))
        _check(parsed.scheme == "https" and (parsed.hostname or "").endswith("youtube.com"), f"{prefix}: unsupported source URL", errors)

        profile = item.get("inputProfile", {})
        available = profile.get("availableModalities", [])
        _check(bool(available) and set(available) <= MODALITIES, f"{prefix}: invalid available modalities", errors)

        gold = item.get("gold", {})
        _check(gold.get("primaryCategory") in CATEGORIES, f"{prefix}: invalid primary category", errors)
        _check(gold.get("contentType") in CONTENT_TYPES, f"{prefix}: invalid content type", errors)
        _check(bool(str(gold.get("referenceSummary", "")).strip()), f"{prefix}: empty reference summary", errors)
        required_facts = gold.get("requiredFacts", [])
        _check(bool(required_facts), f"{prefix}: at least one required fact is needed", errors)

        fact_ids: set[str] = set()
        for group_name in ("requiredFacts", "optionalFacts"):
            for fact in gold.get(group_name, []):
                fact_id = fact.get("id")
                _check(fact_id not in fact_ids, f"{prefix}: duplicate fact id {fact_id}", errors)
                fact_ids.add(fact_id)
                _check(bool(str(fact.get("text", "")).strip()), f"{prefix}/{fact_id}: empty fact", errors)
                evidence = fact.get("evidence", [])
                _check(bool(evidence), f"{prefix}/{fact_id}: evidence required", errors)
                _validate_evidence(prefix, fact_id, evidence, duration, errors)

        for entity_index, entity in enumerate(gold.get("entities", [])):
            evidence = entity.get("evidence", [])
            _check(bool(evidence), f"{prefix}/entity[{entity_index}]: evidence required", errors)
            _validate_evidence(prefix, f"entity[{entity_index}]", evidence, duration, errors)

        _validate_extensions(gold, prefix, duration, errors)

        claim_ids: set[str] = set()
        for claim in gold.get("claims", []):
            claim_id = claim.get("id")
            _check(claim_id not in claim_ids, f"{prefix}: duplicate claim id {claim_id}", errors)
            claim_ids.add(claim_id)
            _check(isinstance(claim.get("verifiable"), bool), f"{prefix}/{claim_id}: verifiable must be boolean", errors)
            _validate_evidence(prefix, claim_id, claim.get("evidence", []), duration, errors)

        annotation = item.get("annotation", {})
        _check(annotation.get("status") in ANNOTATION_STATUSES, f"{prefix}: invalid annotation status", errors)
        _check(bool(annotation.get("annotators")), f"{prefix}: annotator required", errors)

    return errors


def _validate_extensions(gold: dict, prefix: str, duration: int | None, errors: list[str]) -> None:
    target_ids: set[str] = set()
    for target in gold.get("targets", []):
        target_id = target.get("id")
        _check(bool(target_id) and target_id not in target_ids, f"{prefix}: missing or duplicate target id {target_id}", errors)
        target_ids.add(target_id)
        _check(bool(target.get("name")), f"{prefix}/{target_id}: target name required", errors)
        _check(target.get("type") in {"PRODUCT", "PLACE", "RECIPE", "EXERCISE", "TOOL", "SKILL", "EVENT", "OTHER"}, f"{prefix}/{target_id}: invalid target type", errors)
        fact_ids: set[str] = set()
        for group in ("requiredFacts", "optionalFacts"):
            for fact in target.get(group, []):
                fact_id = fact.get("id")
                _check(bool(fact_id) and fact_id not in fact_ids, f"{prefix}/{target_id}: missing or duplicate fact id", errors)
                fact_ids.add(fact_id)
                _check(bool(fact.get("text")) and bool(fact.get("evidence")), f"{prefix}/{target_id}/{fact_id}: fact and evidence required", errors)
                _validate_evidence(prefix, fact_id, fact.get("evidence", []), duration, errors)
        _validate_steps(target.get("steps", []), f"{prefix}/{target_id}", duration, errors)
        _validate_external(target.get("externalExpectations", []), f"{prefix}/{target_id}", errors)
    _validate_steps(gold.get("globalSteps", []), prefix, duration, errors)
    _validate_external(gold.get("externalExpectations", []), prefix, errors)


def _validate_steps(steps: list[dict], prefix: str, duration: int | None, errors: list[str]) -> None:
    ids: set[str] = set()
    orders: list[int] = []
    for step in steps:
        step_id = step.get("id")
        _check(bool(step_id) and step_id not in ids, f"{prefix}: missing or duplicate step id", errors)
        ids.add(step_id)
        order = step.get("order")
        _check(isinstance(order, int) and not isinstance(order, bool) and order > 0, f"{prefix}/{step_id}: invalid order", errors)
        if isinstance(order, int) and not isinstance(order, bool):
            orders.append(order)
        _check(bool(step.get("text")) and isinstance(step.get("required"), bool), f"{prefix}/{step_id}: text and required flag needed", errors)
        _check(bool(step.get("evidence")), f"{prefix}/{step_id}: evidence required", errors)
        _validate_evidence(prefix, step_id, step.get("evidence", []), duration, errors)
    _check(orders == list(range(1, len(steps) + 1)), f"{prefix}: step order must be consecutive starting at 1", errors)


def _validate_external(expectations: list[dict], prefix: str, errors: list[str]) -> None:
    ids: set[str] = set()
    for expectation in expectations:
        expectation_id = expectation.get("id")
        _check(bool(expectation_id) and expectation_id not in ids, f"{prefix}: missing or duplicate external expectation id", errors)
        ids.add(expectation_id)
        _check(expectation.get("purpose") in {"VERIFY_CLAIM", "ENRICH_INFORMATION"}, f"{prefix}/{expectation_id}: invalid purpose", errors)
        status = expectation.get("reviewStatus")
        _check(status in {"NOT_REVIEWED", "REVIEWED", "NO_RELIABLE_SOURCE"}, f"{prefix}/{expectation_id}: invalid review status", errors)
        sources = expectation.get("sources", [])
        if status == "REVIEWED":
            _check(bool(sources), f"{prefix}/{expectation_id}: reviewed evidence requires a source", errors)
        for source in sources:
            parsed = urlsplit(str(source.get("url", "")))
            _check(parsed.scheme in {"https", "http"} and bool(parsed.hostname), f"{prefix}/{expectation_id}: invalid source URL", errors)
            _check(all(source.get(k) for k in ("title", "checkedAt", "supports")), f"{prefix}/{expectation_id}: source title, checkedAt and supports required", errors)


def _validate_evidence(
    prefix: str,
    owner: str,
    evidence: list[dict],
    duration_seconds: int | None,
    errors: list[str],
) -> None:
    maximum = duration_seconds * 1000 + 1000 if isinstance(duration_seconds, int) else None
    for evidence_index, unit in enumerate(evidence):
        label = f"{prefix}/{owner}/evidence[{evidence_index}]"
        _check(unit.get("modality") in MODALITIES, f"{label}: invalid modality", errors)
        start = unit.get("startMs")
        end = unit.get("endMs")
        time_ms = unit.get("timeMs")
        _check(
            any(value is not None for value in (start, end, time_ms)) or bool(unit.get("note")),
            f"{label}: timestamp or note required",
            errors,
        )
        if start is not None or end is not None:
            _check(isinstance(start, int) and isinstance(end, int), f"{label}: startMs/endMs must be paired integers", errors)
            if isinstance(start, int) and isinstance(end, int):
                _check(0 <= start <= end, f"{label}: invalid time range", errors)
                if maximum is not None:
                    _check(end <= maximum, f"{label}: time exceeds video duration", errors)
        if time_ms is not None:
            _check(isinstance(time_ms, int) and time_ms >= 0, f"{label}: invalid timeMs", errors)
            if isinstance(time_ms, int) and maximum is not None:
                _check(time_ms <= maximum, f"{label}: time exceeds video duration", errors)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the Save:On evaluation pilot.")
    parser.add_argument(
        "dataset",
        nargs="?",
        type=Path,
        default=Path(__file__).with_name("pilot_v1.json"),
    )
    args = parser.parse_args()
    errors = validate(args.dataset)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"Validation failed with {len(errors)} error(s).")
        return 1

    payload = json.loads(args.dataset.read_text(encoding="utf-8"))
    statuses: dict[str, int] = {}
    for item in payload["items"]:
        status = item["annotation"]["status"]
        statuses[status] = statuses.get(status, 0) + 1
    print(f"Valid dataset: {len(payload['items'])} items; statuses={statuses}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
