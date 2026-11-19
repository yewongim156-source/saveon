"""Fail-closed validation of SaveOn saved-content conflict alerts.

This module has no AI/network dependency. It rejects a price contradiction unless
its original source claims give explicit, different currency values and a
sufficiently specific shared product identity. Brands/shops alone are not SKUs.
"""
from __future__ import annotations

import re
import unicodedata

_PRICE_WORDS = re.compile(r"가격|금액|판매가|정가|할인가|\bprice\b|\bkrw\b", re.I)
_PRICE = re.compile(
    r"(?:₩|krw)\s*(\d[\d,]*)|"
    r"(\d[\d,]*)\s*(만원|천원|원)", re.I
)
_TOKENS = re.compile(r"[가-힣a-z0-9]{2,}", re.I)
# Generic context words do NOT identify a concrete product or variant.
_GENERIC = {
    "가격", "판매가", "정가", "할인가", "금액", "제품", "상품", "물건", "아이템",
    "생활용품", "화장품", "생활", "쇼핑", "리뷰", "추천", "추천템", "꿀템", "가성비",
    "모음", "하울", "후기", "리스트", "매장", "브랜드", "세일", "할인", "신상",
    "구매", "구입", "영상", "정보", "다이소", "올리브영", "쿠팡", "무신사",
    "온라인", "매장가", "판매", "원", "기본", "사용", "종류", "상품명",
    "수납함", "립밤", "쿠션", "바구니", "팩", "세트", "개입", "용품",
    "원래", "서로", "다른", "같은", "천원", "만원", "크기", "사이즈",
    "추천상품", "추천제품", "아이템추천", "상품추천", "제품추천",
    "daiso", "price", "sale", "shopping", "product", "review",
}


def _norm(value) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).casefold().split())


def _product_tokens(value) -> set[str]:
    s = _PRICE.sub(" ", _norm(value))
    result = set()
    for token in _TOKENS.findall(s):
        stem = re.sub(r"(?:에서는|에서|에게|에도|에는|으로|의|은|는|이|가|을|를)$", "", token)
        if (len(stem) >= 2 and stem not in _GENERIC
                and not stem.isdigit()
                and not re.fullmatch(r"\d{1,6}(?:원|호)", stem)):
            result.add(stem)
    return result


def _amounts(text) -> set[int]:
    values: set[int] = set()
    for match in _PRICE.finditer(_norm(text)):
        amount = match.group(1) or match.group(2)
        unit = match.group(3) or "원"
        try:
            number = int(amount.replace(",", ""))
            multiplier = 10000 if unit == "만원" else 1000 if unit == "천원" else 1
            values.add(number * multiplier)
        except ValueError:
            continue
    return values


def _source_claim(evidence: dict, claims: list[dict]) -> dict | None:
    cid = evidence.get("contentId")
    quote = _norm(evidence.get("claimText"))
    if type(cid) is not int or not quote:
        return None
    # Never trust an AI-rewritten assertion as a genuine extracted input claim.
    for claim in claims:
        if claim.get("contentId") == cid and _norm(claim.get("claimText")) == quote:
            return claim
    return None


def _is_price_alert(item: dict, source_claims: list[dict]) -> bool:
    fields = [item.get("claimType"), item.get("title"), item.get("description")]
    fields.extend(c.get("claimType") for c in source_claims)
    return any(_PRICE_WORDS.search(_norm(s)) for s in fields)


def _has_same_product(claims: list[dict]) -> bool:
    subjects = [_norm(c.get("subject")) for c in claims]
    if len(set(subjects)) == 1 and subjects[0]:
        # Subject alone is insufficient if only a retailer, a category,
        # or an ambiguous product class (e.g. 'Daiso' or 'cushion').
        if len(_product_tokens(subjects[0])) >= 2:
            return True
    # Fall back to distinct named item descriptors present in both original
    # claim texts (not merely in the Gemini-generated output text).
    texts = [_product_tokens(c.get("claimText")) for c in claims]
    if not texts:
        return False
    return len(set.intersection(*texts)) >= 2


def _accept_price_alert(item: dict, claims: list[dict]) -> bool:
    originals = []
    for e in item.get("evidences", []):
        if not isinstance(e, dict):
            continue
        claim = _source_claim(e, claims)
        if claim is not None:
            originals.append(claim)
    ids = {c.get("contentId") for c in originals}
    if len(ids) < 2:
        return False
    if not _has_same_product(originals):
        return False
    # Ambiguous multi-price claims can't support a direct pairwise conflict.
    amounts = [_amounts(c.get("claimText")) for c in originals]
    return all(len(v) == 1 for v in amounts) and len(set.union(*amounts)) >= 2


def filter_detected_conflicts(items: list, source_claims: list[dict]) -> list[dict]:
    """Gate only price contradictions; preserve other existing alert categories."""
    result = []
    seen_prices: set[tuple] = set()
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        evidence = [e for e in item.get("evidences", []) if isinstance(e, dict)]
        if len({e.get("contentId") for e in evidence if type(e.get("contentId")) is int}) < 2:
            continue
        matched = [c for e in evidence if (c := _source_claim(e, source_claims)) is not None]
        if _is_price_alert(item, matched):
            if not _accept_price_alert(item, source_claims):
                continue
            key = (tuple(sorted(str(e.get("contentId")) for e in evidence)),
                   tuple(sorted(_norm(c.get("subject")) for c in matched)),
                   tuple(sorted({next(iter(_amounts(c.get("claimText")))) for c in matched})))
            if key in seen_prices:
                continue
            seen_prices.add(key)
        result.append(item)
    return result
