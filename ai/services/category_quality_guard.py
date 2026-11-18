"""Conservative category cleanup. Does not infer new labels or rewrite saved content."""
from __future__ import annotations

from copy import deepcopy
import re

_ALLOWED_RECIPE_TEXT = re.compile(r"레시피|볶음밥|계란밥|비빔밥|조리법|요리법|만드는\s*법|만들기|조리\s*과정", re.I)


def clean_category_labels(categories, *, content_type: str = "", source_title: str = "") -> list[str]:
    """Keep the model's specific categories. Remove only demonstrably redundant ones.

    '생활정보' can be a legitimate second category, except for an explicit
    recipe with a strong recipe title or contentType=RECIPE. Never infer
    '음식/레시피' merely from keywords or remove an unrelated valid category.
    """
    if not isinstance(categories, list):
        return []
    kept = []
    for value in categories:
        if not isinstance(value, str) or not value.strip():
            continue
        cleaned = value.strip()
        if cleaned not in kept:
            kept.append(cleaned)
    specific = [x for x in kept if x != "기타"]
    if specific:
        kept = specific
    is_explicit_recipe = (
        content_type.strip().upper() == "RECIPE" or
        bool(_ALLOWED_RECIPE_TEXT.search(source_title or ""))
    )
    if "음식/레시피" in kept and is_explicit_recipe:
        kept = [x for x in kept if x != "생활정보"]
    return kept[:3] or ["기타"]


def refine_analysis_categories(result: dict, *, source_title: str = "") -> dict:
    """Shallow external API contract unchanged; return a copy, don't mutate input."""
    if not isinstance(result, dict):
        return result
    updated = dict(result)
    structured = updated.get("structured")
    structured = dict(structured) if isinstance(structured, dict) else {}
    old = updated.get("categories")
    content_type = str(structured.get("contentType") or "")
    effective_title = source_title or str(updated.get("title") or "")
    # Retain intact non-list malformed upstream results; upstream validation handles them.
    if not isinstance(old, list):
        return result
    new = clean_category_labels(old, content_type=content_type, source_title=effective_title)
    if new == old:
        return result
    updated["categories"] = new
    primary = structured.get("primaryCategory")
    if primary not in new:
        structured["primaryCategory"] = new[0]
    updated["structured"] = structured
    return updated
