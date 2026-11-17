"""Evidence-preserving observations from raw saved-video input.

This does not claim that a product works, or that OCR/STT is verified. Each
observation carries its original excerpt and input channel. It is intentionally
pure Python and can be tested without AI models or network access.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict
import re

# Specific review dimensions. Matching a subject is NOT evidence of an outcome.
TOPICS: dict[str, tuple[str, ...]] = OrderedDict([
    ("지속력", ("지속력", "지속돼", "지속되", "지속됐", "8시간", "시간 후", "무너짐", "무너졌", "무너져", "묻어남")),
    ("다크닝", ("다크닝", "어두워지", "칙칙해지")),
    ("모공·블러", ("모공", "블러", "blur", "커버력", "커버해", "커버됩", "커버돼")),
    ("발림·밀착", ("발림", "밀착", "들뜸", "들뜨", "뭉침", "뭉치", "건조", "촉촉", "제형", "레이어링", "퍼프", "브러시")),
    ("색상", ("컬러", "색상", "발색", "호수", "쉐이드", "21n", "23n", "19c", "19n")),
    ("가격", ("가격", "정가", "할인가", "₩", "krw")),
])

_RESULT_CUE = re.compile(
    r"(?:좋았|좋아|좋은|좋다|나빴|별로|만족|불만|없었|없어|없는|있었|있어|있다|"
    r"유지됐|유지되|무너졌|무너져|어두워졌|어두워지|칙칙해졌|들떴|들떠|"
    r"뭉쳤|뭉쳐|커버해|커버돼|커버되|밀착돼|밀착되|밝아졌|발색됐|"
    r"완벽|약했|강했|잘됐|잘되|잘 돼|편했|번졌|묻어났|"
    r"좋습니다|좋아요|됩니다|돼요|되었습니다)", re.IGNORECASE
)

# Questions, experiment names and titles alone cannot establish wear results.
_QUESTION = re.compile(r"[?？]|(?:어떨까|어떤가|될까요|될까|일까요|인가요)")
_SPLIT = re.compile(r"(?<=[.!?。！？])\s+|[\n\r]+")
_SOURCE_RANK = {"STT": 0, "DESCRIPTION": 1, "TITLE": 2, "OCR": 3}


def _clean(text: object) -> str:
    return " ".join(str(text or "").split()).strip()


def _excerpts(text: str, *, max_size: int = 230) -> list[str]:
    """Bounded exact substrings of the supplied text, even without punctuation."""
    if not isinstance(text, str) or not text.strip():
        return []
    snippets: list[str] = []
    all_terms = sorted({term for terms in TOPICS.values() for term in terms}, key=len, reverse=True)
    for section in _SPLIT.split(text):
        section = section.strip()
        if not section:
            continue
        if len(section) <= max_size:
            snippets.append(section)
            continue
        lower = section.lower()
        windows: list[tuple[int, int]] = []
        for term in all_terms:
            start = 0
            while True:
                hit = lower.find(term.lower(), start)
                if hit < 0:
                    break
                left = max(0, hit - 80)
                right = min(len(section), hit + max_size - 80)
                if not any(a <= hit < b for a, b in windows):
                    windows.append((left, right))
                start = hit + len(term)
                if len(windows) >= 30:
                    break
            if len(windows) >= 30:
                break
        for left, right in sorted(windows):
            snippets.append(section[left:right].strip())
    return list(dict.fromkeys(snippets))


def extract_video_observations(
    *,
    transcript: str = "",
    source_title: str = "",
    source_description: str = "",
    ocr_lines: list[str] | None = None,
    max_items: int = 20,
) -> list[dict]:
    """Extract topical excerpts with provenance; do not infer ratings from topics.

    kind = DIRECT_STATEMENT only for actual creator language with an outcome cue.
    A title, an experiment mention and standalone OCR are never product verdicts.
    """
    sources = (
        ("STT", [transcript]),
        ("DESCRIPTION", [source_description]),
        ("TITLE", [source_title]),
        ("OCR", ocr_lines or []),
    )
    candidates: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for source, source_values in sources:
        for value in source_values:
            for quote in _excerpts(value):
                if not quote:
                    continue
                # Standalone OCR is often misrecognized; keep only legible text.
                if source == "OCR":
                    useful = len(re.findall(r"[가-힣a-zA-Z0-9]", quote))
                    if useful < 8 or useful < len(quote) * 0.45:
                        continue
                lowered = quote.lower()
                for topic, words in TOPICS.items():
                    if not any(word.lower() in lowered for word in words):
                        continue
                    key = (topic, source, lowered)
                    if key in seen:
                        continue
                    seen.add(key)
                    direct = (source in ("STT", "DESCRIPTION")
                              and bool(_RESULT_CUE.search(quote))
                              and not bool(_QUESTION.search(quote)))
                    candidates.append({
                        "topic": topic,
                        "kind": ("DIRECT_STATEMENT" if direct else
                                 "OCR_UNVERIFIED" if source == "OCR" else "TOPIC_MENTION"),
                        "source": source,
                        "quote": quote[:230],
                    })
    # Prefer an explicit spoken evaluation over a broad video title.
    rank = {"DIRECT_STATEMENT": 0, "TOPIC_MENTION": 1, "OCR_UNVERIFIED": 2}
    candidates.sort(key=lambda item: (
        rank[item["kind"]], _SOURCE_RANK[item["source"]],
        list(TOPICS).index(item["topic"]),
    ))
    result: list[dict] = []
    counts: dict[str, int] = defaultdict(int)
    for item in candidates:
        if counts[item["topic"]] >= 4:
            continue
        result.append(item)
        counts[item["topic"]] += 1
        if len(result) >= max_items:
            break
    return result


def review_excerpt_lines(observations: list[dict], max_items: int = 9) -> list[str]:
    """Extra excerpts for Gemini when the first 3,500 transcript chars omit a result."""
    lines: list[str] = []
    for item in observations:
        source = item.get("source")
        if source not in ("STT", "DESCRIPTION"):
            continue
        quote = _clean(item.get("quote"))
        if not quote:
            continue
        line = f'[{source}/{item.get("topic")}/{item.get("kind")}] {quote[:220]}'
        if line not in lines:
            lines.append(line)
        if len(lines) >= max_items:
            break
    return lines
