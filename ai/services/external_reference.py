"""Limited, explicitly attributed Wikimedia background references.

This is not claim verification: a matching article can still be unrelated to
the video's claims. Product, health, pricing and location claims are excluded.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen


@lru_cache(maxsize=128)
def _lookup_exact_title(title: str) -> dict | None:
    params = urlencode({"action": "query", "prop": "extracts", "exintro": "1", "explaintext": "1",
                        "exsentences": "1", "titles": title, "format": "json", "formatversion": "2"})
    request = Request("https://ko.wikipedia.org/w/api.php?" + params, headers={
        "User-Agent": "SaveOn/0.1 (https://github.com/yewongim156-source/saveon)",
        "Accept": "application/json",
    })
    with urlopen(request, timeout=5) as response:
        body = json.load(response)
    pages = body.get("query", {}).get("pages", [])
    if not pages or "missing" in pages[0]:
        return None
    page = pages[0]
    canonical = str(page.get("title", "")).strip()
    # Do not guess among similar names or follow redirects to unrelated pages.
    normalize = lambda value: re.sub(r"\s+", "", value).casefold()
    if normalize(canonical) != normalize(title):
        return None
    extract = " ".join(str(page.get("extract", "")).split())
    if not extract or len(extract) > 250 or "동음이의" in extract:
        return None
    return {"title": canonical, "text": extract, "url": "https://ko.wikipedia.org/wiki/" + quote(canonical.replace(" ", "_")),
            "source": "한국어 위키백과", "status": "BACKGROUND_NOT_VERIFIED"}


def add_educational_reference(result: dict) -> dict:
    if os.getenv("WIKIPEDIA_REFERENCE_ENABLED", "true").lower() not in {"1", "true", "yes", "on"}:
        return result
    structured = result.get("structured") or {}
    if structured.get("contentType") != "EDUCATIONAL":
        return result
    targets = structured.get("targets") or []
    # Only a clearly named, evidence-linked target; never derive from a claim.
    name = next((str(target.get("name", "")).strip() for target in targets
                 if isinstance(target, dict) and target.get("nameEvidenceIds") and 2 <= len(str(target.get("name", "")).strip()) <= 60), "")
    if not name:
        return result
    try:
        reference = _lookup_exact_title(name)
    except Exception:
        return result
    if reference:
        structured["externalReferences"] = [reference]
        result["structured"] = structured
        result["summary"] = (str(result.get("summary", "")) + "\n\n관련 참고 · " + reference["source"] + "\n" + reference["text"] + "\n" + reference["url"])[:4000]
    return result
