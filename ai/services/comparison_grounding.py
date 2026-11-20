"""Conservative grounding for Save:on saved-video comparison results.

This module has no network / Gemini dependency. The caller supplies a semantic
entailment auditor. If auditing fails, unverified model claims fail closed.
"""
from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher
import re
import unicodedata
from typing import Callable


# Avoid accepting vague evaluative conclusions as proof from feature mentions.
_STRONG_OPINION = re.compile(
    r"뛰어|우수|탁월|최고|완벽|훌륭|높게 평가|매우 좋|대단하|만족도|효과가 좋|"
    r"excellent|superior|best|outstanding", re.IGNORECASE
)
_OPINION_EVIDENCE = re.compile(
    r"뛰어|우수|탁월|최고|완벽|훌륭|좋아|좋다|좋은|좋았|만족|인상적|"
    r"효과적|잘 돼|잘되|excellent|superior|best|outstanding", re.IGNORECASE
)
_NUMBER = re.compile(r"(?<![\w])\d[\d,]*(?:\.\d+)?", re.UNICODE)
_KOREAN_COUNTS = {
    "1": ("한", "하나", "일"), "2": ("두", "둘", "이"),
    "3": ("세", "셋", "삼"), "4": ("네", "넷", "사"),
    "5": ("다섯", "오"), "6": ("여섯", "육"),
    "7": ("일곱", "칠"), "8": ("여덟", "팔"),
    "9": ("아홉", "구"), "10": ("열", "십"),
}
_COUNT_SUFFIX = r"(?:가지|개|종|색|컬러|명|단계)"


def _clean(value) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize(value) -> str:
    return unicodedata.normalize("NFKC", _clean(value)).casefold()


def _fragments(context: dict) -> list[str]:
    """Only textual material that actually accompanied the saved video."""
    result: list[str] = []
    for key in ("title", "summary"):
        value = context.get(key)
        if isinstance(value, str) and value.strip():
            result.append(value)
    for key in ("keywords", "entities", "tags", "unverifiedNotes"):
        items = context.get(key) or []
        if isinstance(items, list):
            result.extend(x for x in items if isinstance(x, str) and x.strip())

    # SAVEON_VIDEO_OBSERVATIONS_V8: quotes are exact excerpts of input
    # channels, explicitly marked with source and claim/mention distinction.
    for item in (context.get("videoObservations") or []):
        if isinstance(item, dict) and isinstance(item.get("quote"), str):
            result.append(item["quote"])

    # Structured claims and source provenance. Don't serialize the whole JSON:
    # otherwise fabricated strings from the model could match arbitrary keys.
    for key in ("claims", "verifiedFacts", "corrections"):
        values = context.get(key) or []
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, str):
                result.append(value)
            if isinstance(value, dict):
                for field in ("text", "claim", "value", "correctedText", "verifiedText", "explanation"):
                    item = value.get(field)
                    if isinstance(item, str) and item.strip():
                        result.append(item)
    return result


def _quote_in_source(quote: str, context: dict) -> bool:
    quote = _normalize(quote)
    if len(quote) < 3:
        return False
    return any(quote in _normalize(fragment) for fragment in _fragments(context))


def _anchored_quote(quote: str, context: dict) -> str | None:
    """Return an actual stored excerpt. Never display a model-paraphrased citation.

    Accept a small wording/spacing drift *only* when a similar stored sentence
    can be retrieved. A separate semantic entailment audit still decides if it
    actually supports the statement. Fabricated numerical evidence is rejected.
    """
    normalized = _normalize(quote)
    if len(normalized) < 3:
        return None
    fragments = _fragments(context)
    for text in fragments:
        if normalized in _normalize(text):
            # Display actual source text, not normalized or reconstructed text.
            if quote in text:
                return quote[:500]
            for part in re.split(r"(?<=[.!?])\s+|[\n]+", text):
                if normalized in _normalize(part):
                    return part[:500]
            return text[:500]

    if len(normalized) < 9:
        return None

    def tokens(s: str) -> set[str]:
        return {x for x in re.findall(r"[가-힣a-z0-9]{2,}", _normalize(s))
                if x not in {"영상", "제품", "관련", "클리오", "쿠션", "리뷰"}}

    query_tokens = tokens(quote)
    if not query_tokens:
        return None
    best: tuple[float, str] | None = None
    for text in fragments:
        for part in re.split(r"(?<=[.!?])\s+|[\n]+", text):
            part = _clean(part)
            if not 9 <= len(part) <= 500:
                continue
            target = _normalize(part)
            if not _numbers(quote).issubset(_numbers(part)):
                continue
            overlap = len(query_tokens & tokens(part))
            similarity = SequenceMatcher(None, normalized, target).ratio()
            # Two distinctive tokens and high textual similarity required.
            if overlap < 2 or similarity < 0.72:
                continue
            if best is None or similarity > best[0]:
                best = (similarity, part)
    return best[1] if best else None


def _numbers(text: str) -> set[str]:
    result: set[str] = set()
    for item in _NUMBER.findall(_normalize(text)):
        token = item.replace(",", "")
        try:
            number = float(token)
            result.add(str(int(number)) if number.is_integer() else str(number))
        except ValueError:
            pass
    return result


def _quantities_supported(statement: str, quote: str) -> bool:
    """Reject '5 colours' when evidence merely says 'all colours'."""
    required = _numbers(statement)
    found = _numbers(quote)
    if required.issubset(found):
        return True

    # Limited Korean count words: '5가지' can be supported by '다섯 가지'.
    normalized_quote = _normalize(quote)
    normalized_statement = _normalize(statement)
    missing = required - found
    for number in missing:
        if number not in _KOREAN_COUNTS:
            return False
        if not re.search(rf"(?<!\d){re.escape(number)}\s*{_COUNT_SUFFIX}", normalized_statement):
            return False
        if not any(re.search(rf"{word}\s*{_COUNT_SUFFIX}", normalized_quote)
                   for word in _KOREAN_COUNTS[number]):
            return False
    return True


def _evaluate_strength(statement: str, quote: str) -> bool:
    # A how-to tip is not by itself evidence that the product is excellent.
    if _STRONG_OPINION.search(statement) and not _OPINION_EVIDENCE.search(quote):
        return False
    return True


def _ground_evidences(raw: dict, contexts: dict[int, dict]) -> list[dict]:
    result: list[dict] = []
    seen: set[int] = set()
    for value in (raw.get("evidences") or [])[:12]:
        if not isinstance(value, dict):
            continue
        content_id = value.get("contentId")
        if type(content_id) is not int or content_id not in contexts or content_id in seen:
            continue
        quote = _anchored_quote(_clean(value.get("quote"))[:500], contexts[content_id])
        if quote is None:
            continue
        seen.add(content_id)
        result.append({
            "contentId": content_id,
            "title": _clean(contexts[content_id].get("title"))[:180],
            "quote": quote,
            # Source context does not carry time-aligned provenance.
            "timestampSeconds": None,
        })
    return result


# SAVEON_QUALITY_GUARD_V9

def _has_review_outcome_evidence(context: dict, finding_topic: str) -> bool:
    """A shared review *topic* isn't a contradiction in evaluation.

    If observations exist, a disagreement requires at least one spoken or
    creator-described DIRECT_STATEMENT of the same topic per video, in addition
    to the semantic auditor's positive judgment. Old records without saved
    observations retain the existing, audited behaviour.
    """
    observations = context.get("videoObservations")
    if not isinstance(observations, list) or not observations:
        return True
    topic = _normalize(finding_topic)
    topic_terms = [x for x in re.split(r"[·/\s,:|]+", topic) if len(x) >= 2]
    for obs in observations:
        if not isinstance(obs, dict):
            continue
        if obs.get("kind") != "DIRECT_STATEMENT" or obs.get("source") not in ("STT", "DESCRIPTION"):
            continue
        obs_topic = _normalize(obs.get("topic"))
        if not _clean(obs.get("quote")):
            continue
        if not topic_terms or any(t in obs_topic or obs_topic in t for t in topic_terms):
            return True
    return False


def _safe_quote_statement(evidence: dict) -> str:
    # NEVER turn raw OCR numbers into a verified product spec or current price.
    quote = evidence["quote"]
    return f'{evidence["contentId"]}번 영상에는 “{quote[:175]}”라고 나옵니다.'


def _finding(topic: str, statement: str, evidence: list[dict]) -> dict:
    return {
        "topic": (topic or "영상별 정보")[:100],
        "statement": statement[:700],
        "evidences": evidence[:8],
    }


def _objective_value_in_quote(value: str, quote: str) -> bool:
    if _numbers(value):
        return _quantities_supported(value, quote)
    return _normalize(value) in _normalize(quote)


# PRICE is a property of an individual product/variant, not of its seller.
# Avoid treating a store or brand as the common price-bearing subject.
_PRICE_AMOUNT = re.compile(
    r"(?:(?:₩|krw)\s*(\d[\d,]*(?:\.\d+)?)|"
    r"(\d[\d,]*(?:\.\d+)?)\s*(?:원|만원|천원)|"
    r"(?:가격|정가|판매가|할인가|price)\s*(?:은|는|이|가|:|：|=)?\s*(\d[\d,]*(?:\.\d+)?))",
    re.IGNORECASE,
)
_VARIANT = re.compile(r"(?<![\d.])\d+(?:\.\d+)?\s*(?:ml|g|kg|l|개입|매입|호)(?![가-힣a-z])", re.IGNORECASE)


def _product_key(value: str) -> str:
    """Strict normalized full product name; never match by shared brand token."""
    return re.sub(r"[^가-힣a-z0-9]+", "", _normalize(value))


def _named_products(context: dict) -> set[str]:
    details = context.get("entityDetails") or []
    if not isinstance(details, list):
        return set()
    # Explicit BRAND classification overrides an ambiguous PRODUCT tag.
    non_products = {
        _product_key(item.get("name")) for item in details
        if isinstance(item, dict)
        and _normalize(item.get("type")) in ("brand", "place", "category", "store")
    }
    source_text = _product_key(" ".join(
        [str(context.get("title") or ""), str(context.get("summary") or "")]
        + [str(x) for x in (context.get("keywords") or []) if isinstance(x, str)]
    ))
    names = set()
    for item in details:
        if not isinstance(item, dict) or _normalize(item.get("type")) != "product":
            continue
        name = _product_key(item.get("name"))
        # Insufficiently specific labels (e.g. '쿠션') are not item identities.
        if (len(name) < 5 or name in non_products or name not in source_text
                or re.search(r"추천템|꿀템|모음|하울|생활용품|아이템|제품추천|상품추천|쇼핑리스트", name)):
            continue
        try:
            if item.get("confidence") is not None and float(item["confidence"]) < 0.45:
                continue
        except (ValueError, TypeError):
            continue
        names.add(name)
    return names


def _product_variants(context: dict) -> set[str]:
    # Only explicit variant quantities are used. Generic numeric values, prices,
    # and dates are not treated as product identities.
    title = _normalize(context.get("title"))
    return {re.sub(r"\s+", "", x.casefold()) for x in _VARIANT.findall(title)}


def _same_product_evidence(evidence: list[dict], contexts: dict[int, dict],
                           entity: str = "") -> list[dict]:
    """Return only videos explicitly naming the same product (and not mismatched variants).

    Fail closed for unknown/missing product identifiers. We deliberately do
    not infer SKU equality from a shared merchant, brand, or category.
    """
    expected = _product_key(entity)
    if entity and len(expected) < 5:
        return []
    eligible = {}
    for ev in evidence:
        cid = ev["contentId"]
        products = _named_products(contexts[cid])
        if expected:
            products &= {expected}
        for product in products:
            eligible.setdefault(product, []).append(ev)
    matches = [(key, evs) for key, evs in eligible.items()
               if len({ev["contentId"] for ev in evs}) >= 2]
    if not matches:
        return []
    # More than one distinct plausible identity means the model's subject is
    # ambiguous; never choose a product by guesswork.
    if len(matches) != 1:
        return []
    selected = matches[0][1]
    compatible = []
    for ev in selected:
        current = _product_variants(contexts[ev["contentId"]])
        if any(current and _product_variants(contexts[x["contentId"]])
               and current.isdisjoint(_product_variants(contexts[x["contentId"]]))
               for x in compatible):
            continue
        compatible.append(ev)
    return compatible if len({ev["contentId"] for ev in compatible}) >= 2 else []


def _price_amounts(text: str) -> set[str]:
    # A quote may contain both "5,000원" and a view count "1,059,439".
    # The price must match a *currency-labelled or price-labelled* amount.
    result = set()
    for match in _PRICE_AMOUNT.finditer(_normalize(text)):
        amount = next((group for group in match.groups() if group), "")
        result.update(_numbers(amount))
    return result


def _supported_price(value: str, quote: str, context: dict) -> bool:
    if not _numbers(value) or not (_numbers(value) & _price_amounts(quote)):
        return False
    observations = context.get("videoObservations")
    if not isinstance(observations, list) or not observations:
        # Legacy content may have only a title or analyzed summary.
        return True
    # When observations exist, OCR_UNVERIFIED or TOPIC_MENTION alone is not
    # evidence of a spoken/creator-described price.
    direct = any(
        isinstance(obs, dict)
        and obs.get("kind") == "DIRECT_STATEMENT"
        and obs.get("source") in ("STT", "DESCRIPTION")
        and bool(_numbers(value) & _price_amounts(_clean(obs.get("quote"))))
        for obs in observations
    )
    if direct:
        return True
    for fact in context.get("verifiedFacts") or []:
        phrase = (fact if isinstance(fact, str) else
                  " ".join(str(v) for v in fact.values() if isinstance(v, (str, int, float)))
                  if isinstance(fact, dict) else "")
        if _numbers(value) & _price_amounts(phrase):
            return True
    return False


def _is_price_disagreement(raw: dict) -> bool:
    return bool(re.search(r"가격|금액|판매가|정가|price|\bkrw\b|\d[\d,]*\s*원",
                          _clean(raw.get("topic")) + " " + _clean(raw.get("statement")),
                          re.IGNORECASE))


def _objective_valid(raw: dict, contexts: dict[int, dict]) -> dict | None:
    if not isinstance(raw, dict):
        return None
    evidence = _ground_evidences(raw, contexts)
    if len(evidence) < 2:
        return None
    field = _normalize(raw.get("field")).upper()
    if field == "PRICE":
        # Product identity must be explicit. A same-brand comparison is not a
        # same-product comparison; do not send its prices for external checking.
        if not _clean(raw.get("entity")):
            return None
        evidence = _same_product_evidence(evidence, contexts, _clean(raw.get("entity")))
        if len(evidence) < 2:
            return None
    values: list[str] = []
    seen_values: set[tuple] = set()
    for item in (raw.get("values") or []):
        value = _clean(item)
        if not value:
            continue
        nums = _numbers(value)
        # Treat 36,000 and 36000 as the same claimed amount.
        canonical = ("numbers", tuple(sorted(nums))) if nums else ("text", _normalize(value))
        if canonical in seen_values:
            continue
        seen_values.add(canonical)
        values.append(value)
        if len(values) >= 6:
            break
    if len(values) < 2:
        return None
    # Each contradictory value must be explicitly present in a different video.
    value_sources: dict[str, set[int]] = {}
    for value in values:
        source_ids = {
            x["contentId"] for x in evidence
            if _objective_value_in_quote(value, x["quote"])
            and (field != "PRICE" or _supported_price(
                value, x["quote"], contexts[x["contentId"]]))
        }
        if source_ids:
            value_sources[value] = source_ids
    if len(value_sources) < 2:
        return None
    entries = list(value_sources.items())
    distinct_videos = any(a != b for i, (_, ids_a) in enumerate(entries)
                          for _, ids_b in entries[i + 1:]
                          for a in ids_a for b in ids_b)
    if not distinct_videos:
        return None
    validated_values = list(value_sources)
    # Do not display unrelated videos as price evidence after filtering.
    retained_ids = set().union(*value_sources.values())
    return {**raw, "values": validated_values,
            "evidences": [ev for ev in evidence if ev["contentId"] in retained_ids]}


def _video_focus(context: dict) -> tuple[str, str]:
    """Deterministic *topic* hint; never infer a product rating or factual claim."""
    text = _normalize((context.get("title") or "") + " " + (context.get("summary") or ""))
    themes = (
        ("지속력·다크닝", ("지속력", "다크닝")),
        ("출시·색상", ("출시", "런칭", "컬러", "발색")),
        ("사용 팁", ("브러시", "레이어링", "사용법", "사용 팁")),
        ("모공·블러", ("모공", "블러")),
    )
    for label, terms in themes:
        hits = [t for t in terms if t in text]
        if len(hits) >= 2:
            return label, f"저장된 분석 내용에서 {', '.join(hits[:2])} 관련 내용을 다룹니다."
    for label, terms in themes:
        if any(t in text for t in terms):
            return label, f"저장된 분석 내용에서 {label} 관련 내용을 다룹니다."
    return "영상별 정보", "저장된 설명의 핵심을 확인할 수 있어요."


def _source_only_highlights(contexts: list[dict], limit: int = 5) -> list[dict]:
    """One short, source-backed card per video. Full excerpt stays in evidence."""
    result: list[dict] = []
    seen_ids: set[int] = set()
    for context in contexts:
        if not isinstance(context, dict):
            continue
        content_id = context.get("contentId")
        if type(content_id) is not int or content_id in seen_ids:
            continue
        seen_ids.add(content_id)
        title = _clean(context.get("title"))
        summary = _clean(context.get("summary"))
        direct = next((x for x in (context.get("videoObservations") or [])
                       if isinstance(x, dict)
                       and x.get("kind") == "DIRECT_STATEMENT"
                       and x.get("source") in ("STT", "DESCRIPTION")
                       and _clean(x.get("quote"))), None)
        if direct:
            quote = _clean(direct["quote"])[:230]
            label = _clean(direct.get("topic")) or "영상별 정보"
            short = f"영상 {content_id}에서 ‘{quote[:90]}’라고 언급해요. (자동 인식·원본 영상 검증 전)"
        else:
            if len(summary) >= 30 and not summary.lower().startswith(("video by ", "instagram 콘텐츠")):
                quote = summary[:350]
            elif len(title) >= 8 and not title.lower().startswith(("video by ", "instagram 콘텐츠")):
                quote = title[:350]
            else:
                continue
            label, short = _video_focus(context)
        ev = {"contentId": content_id, "title": title[:180],
              "quote": quote, "timestampSeconds": None}
        result.append(_finding(label, short + " (원본 영상 검증 전)", [ev]))
        if len(result) >= limit:
            break
    return result


# Shared topics are never treated as agreement on product quality. They are
# used only when no independently supported COMMON CLAIM survives verification.
_TOPIC_IGNORE = {
    "쿠션", "클리오", "킬커버", "영상", "리뷰", "제품", "소개", "정리", "관련",
    "이번", "사용", "이번에", "추천", "이번", "그런", "너무", "되게", "오늘",
    "뷰티", "메이크업", "유튜브", "youtube", "review", "new", "신상",
    "브랜드", "올리브영", "기술", "생활", "정보", "후기", "평가", "비교",
}
_TOPIC_ALIASES = {
    "블러링": "블러", "블러리": "블러", "색상": "컬러", "발색": "컬러",
    "커버력": "커버", "커버링": "커버", "지속": "지속력",
    "다크닝": "다크닝", "모공": "모공",
}


def _topic_term(raw: str, comparison_entity: str = "") -> str:
    value = _normalize(raw).strip("#.,!?()[]'")
    value = _TOPIC_ALIASES.get(value, value)
    if (not 2 <= len(value) <= 14 or value in _TOPIC_IGNORE
            or (comparison_entity and value == _normalize(comparison_entity))
            or value.isdigit()):
        return ""
    return value


def _topic_terms(context: dict, comparison_entity: str) -> set[str]:
    values = set()
    for key in ("keywords", "tags"):
        for item in (context.get(key) or [])[:20]:
            if not isinstance(item, str):
                continue
            # Don't consider long compound marketing phrases a topic without
            # evidence in the title or summary.
            topic = _topic_term(item, comparison_entity)
            if topic:
                values.add(topic)
    # Do not tokenize arbitrary descriptions into topical labels: words like
    # '소개합니다'/'설명' would appear in many unrelated videos. For prose, only
    # use the bounded evidence-oriented anchor vocabulary below.
    # Identify overlapping Korean feature anchors that can be embedded in
    # compounds, without making any subjective performance assertions.
    for topic in ("모공", "블러", "컬러", "지속력", "다크닝", "밀착", "발림", "커버", "광택",
                  "가격", "할인", "성수", "웨이팅", "레시피", "사이즈"):
        if topic in _normalize((context.get("title") or "") + " " + (context.get("summary") or "")):
            values.add(topic)
    return values


def _topic_evidence(context: dict, topic: str) -> dict | None:
    for key in ("summary", "title"):
        text = context.get(key) or ""
        if not isinstance(text, str) or topic not in _normalize(text):
            continue
        pos = _normalize(text).find(topic)
        # Use the full original source if short, otherwise a centered excerpt.
        if len(text) <= 210:
            quote = text
        else:
            start = max(0, pos - 65)
            quote = text[start:start + 190]
        return {"contentId": context["contentId"],
                "title": _clean(context.get("title"))[:180],
                "quote": _clean(quote), "timestampSeconds": None}
    # Metadata-only overlap is not enough to create a topic-based commonality.
    return None


def _shared_topic_findings(contexts: list[dict],
                           comparison_entity: str,
                           max_items: int = 2) -> list[dict]:
    by_term: dict[str, list[dict]] = defaultdict(list)
    for context in contexts:
        if not isinstance(context, dict) or type(context.get("contentId")) is not int:
            continue
        for term in _topic_terms(context, comparison_entity):
            ev = _topic_evidence(context, term)
            if ev:
                by_term[term].append(ev)
    candidates = []
    for term, items in by_term.items():
        distinct = list({x["contentId"]: x for x in items}.values())
        if len(distinct) < 2:
            continue
        priority = 2 if term in ("모공", "블러", "지속력", "다크닝", "컬러", "가격", "발림", "밀착") else 0
        candidates.append((len(distinct), priority, len(term), term, distinct))
    candidates.sort(reverse=True)
    # Merge topics with exactly the same supporting videos; otherwise keep a
    # different pair only when it contributes substantial independent evidence.
    groups: dict[tuple[int, ...], list[tuple[str, list[dict]]]] = {}
    for _, _, _, term, items in candidates:
        signature = tuple(sorted(x["contentId"] for x in items))
        groups.setdefault(signature, []).append((term, items))
    prioritized = sorted(groups.items(), key=lambda group:(len(group[0]), len(group[1])), reverse=True)
    result = []
    for signature, topics in prioritized[:max_items]:
        top_terms = [term for term, _ in topics[:2]]
        evidence = topics[0][1]
        # A supporting video may mention only one of several grouped topics;
        # label as shared *themes*, not as agreement on any factual assertion.
        label = "·".join(top_terms)
        result.append(_finding(
            "공통으로 다루는 주제 (평가 일치 아님)",
            f"{len(signature)}개 영상에서 {label} 관련 내용을 다뤄요. 평가가 같은지는 확인되지 않았어요.",
            evidence,
        ))
    return result


def _dedupe_findings(findings: list[dict], *, shared_topics: bool = False) -> list[dict]:
    """Remove repeated cards without collapsing distinct verified claims."""
    kept: list[dict] = []
    seen: set[tuple] = set()
    for finding in findings:
        ids = tuple(sorted({e["contentId"] for e in finding.get("evidences", [])}))
        normalized_statement = re.sub(r"\s+", "", _normalize(finding.get("statement", "")))
        key = (ids, normalized_statement)
        if shared_topics and "공통으로 다루는 주제" in finding.get("topic", ""):
            # Repeated same-topic cards for the exact same set of videos.
            # Keep different verified factual claims independent.
            key = (ids, _normalize(finding.get("topic", "")))
        if key not in seen:
            seen.add(key)
            kept.append(finding)
    return kept


def ground_comparison_results(
    raw: dict,
    contexts: list[dict],
    *,
    semantic_audit: Callable[[list[dict]], dict[str, bool]] | None = None,
    fallback_when_empty: bool = False,
    comparison_entity: str = "",
) -> dict:
    """Validate sources, numeric support, semantic entailment, and category.

    `semantic_audit` receives {key, statement, quote} checks and returns
    {key: true/false}. Missing/failed checks fail closed for model assertions.
    When explicitly enabled, source-only highlights prevent an empty comparison
    while making no claims beyond the stored title/summary excerpts.
    A statement supported by only one saved video is not a common point.
    """
    source_by_id = {x["contentId"]: x for x in contexts if isinstance(x.get("contentId"), int)}
    candidates: list[dict] = []
    checks: list[dict] = []
    for group in ("commonPoints", "disagreements", "uniqueMentions"):
        for index, value in enumerate((raw.get(group) or [])[:8]):
            if not isinstance(value, dict):
                continue
            statement = _clean(value.get("statement"))[:700]
            if not statement:
                continue
            evidence = _ground_evidences(value, source_by_id)
            if not evidence:
                continue
            c = {"group": group, "topic": _clean(value.get("topic")), "statement": statement,
                 "evidences": evidence, "index": index}
            candidates.append(c)
            if group == "disagreements":
                # A contradiction is a relationship BETWEEN videos; no single
                # quote can independently entail it. Audit the combined pair.
                if len(evidence) >= 2:
                    checks.append({
                        "key": f"{group}:{index}:joint",
                        "statement": statement,
                        "quote": "\n".join(
                            f"영상 {ev['contentId']}: {ev['quote']}" for ev in evidence
                        ),
                    })
                continue
            for ev in evidence:
                # Numeric support & overclaim rule are deterministic gates.
                if not _quantities_supported(statement, ev["quote"]):
                    continue
                if not _evaluate_strength(statement, ev["quote"]):
                    continue
                checks.append({
                    "key": f"{group}:{index}:{ev['contentId']}",
                    "statement": statement,
                    "quote": ev["quote"],
                })

    # Bounded review cost; omitted assertions are not automatically approved.
    checks = checks[:24]
    approved_check_keys = {item["key"] for item in checks}
    audit: dict[str, bool] = {}
    if checks and semantic_audit is not None:
        try:
            response = semantic_audit(checks)
            if isinstance(response, dict):
                audit = response
        except Exception:
            # Never publish unchecked AI assertions during audit outage.
            audit = {}

    common: list[dict] = []
    disagreements: list[dict] = []
    unique: list[dict] = []
    seen_unique: set[tuple[int, str]] = set()

    def add_unique(topic: str, ev: dict) -> None:
        key = (ev["contentId"], _normalize(ev["quote"]))
        if key not in seen_unique and len(unique) < 8:
            unique.append(_finding(topic or "영상별 정보", _safe_quote_statement(ev), [ev]))
            seen_unique.add(key)

    for c in candidates:
        supported = [ev for ev in c["evidences"]
                     if audit.get(f"{c['group']}:{c['index']}:{ev['contentId']}") is True
                     and f"{c['group']}:{c['index']}:{ev['contentId']}" in approved_check_keys]
        group = c["group"]
        if group == "commonPoints":
            if len(supported) >= 2:
                common.append(_finding(c["topic"], c["statement"], supported))
            elif len(supported) == 1:
                # Explicitly downgrade instead of falsely calling it common.
                add_unique(c["topic"], supported[0])
        elif group == "disagreements":
            # v9: an OCR/title topic mention is not itself a conflicting review.
            # Both videos must supply direct creator outcomes when observations
            # are available. Semantic verification still remains mandatory.
            review_checked = all(
                _has_review_outcome_evidence(source_by_id[ev["contentId"]], c["topic"])
                for ev in c["evidences"]
            )
            price_checked = (not _is_price_disagreement(c) or
                             len(_same_product_evidence(c["evidences"], source_by_id)) >= 2)
            if (len(c["evidences"]) >= 2 and review_checked and price_checked and
                    audit.get(f"{group}:{c['index']}:joint") is True):
                disagreements.append(_finding(c["topic"], c["statement"], c["evidences"]))
            # One-sided opinions cannot establish a contradiction.
        else:
            if len(supported) == 1:
                # Safer than asserting a raw OCR value as a current fact.
                add_unique(c["topic"], supported[0])

    objective = []
    seen_objective: set[tuple[str, str]] = set()
    for value in (raw.get("objectiveDisagreements") or [])[:8]:
        verified = _objective_valid(value, source_by_id)
        if verified:
            # One card per concrete product and field, not three overlapping
            # 'same shop has different prices' alerts.
            key = (_normalize(verified.get("field")),
                   _product_key(verified.get("entity")))
            if key not in seen_objective:
                objective.append(verified)
                seen_objective.add(key)

    # If there is no defensible *common claim*, show shared topics separately
    # labelled as topic overlap, never as identical opinions or performance.
    # This deterministic relationship does not depend on a second AI call.
    if fallback_when_empty and not common:
        common = _shared_topic_findings(
            contexts, comparison_entity or _clean(raw.get("comparisonEntity")), max_items=2
        )

    if fallback_when_empty and not unique:
        unique = _source_only_highlights(contexts)
        if unique:
            # Counts only. Do not log private saved-video text.
            print(f"[SAVEON] Showing {len(unique)} source-only video highlights")

    common = _dedupe_findings(common, shared_topics=True)
    disagreements = _dedupe_findings(disagreements)
    unique = _dedupe_findings(unique)

    return {
        **raw,
        "commonPoints": common[:6],
        "disagreements": disagreements[:6],
        "uniqueMentions": unique[:8],
        "objectiveDisagreements": objective[:3],
    }
