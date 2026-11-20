"""Extra reading for a saved video: blog posts, shop pages and place links.

The search uses the same title and keywords the app shows for the video, so what comes
back is about the same subject. Links are suggestions, not verification: a page that
mentions the subject is not proof of anything the video said.
"""
from __future__ import annotations

import os
import re
from urllib.parse import urlparse

from services import search_verification as sv

MAX_LINKS = 5

BLOG_HOSTS = ("blog.naver.com", "m.blog.naver.com", "tistory.com", "brunch.co.kr", "velog.io",
              "medium.com", "post.naver.com", "cafe.naver.com")
SHOP_HOSTS = ("zigzag.kr", "musinsa.com", "oliveyoung.co.kr", "coupang.com", "29cm.co.kr", "a-bly.com",
              "daiso.co.kr", "kurly.com", "smartstore.naver.com", "brand.naver.com", "shopping.naver.com",
              "11st.co.kr", "gmarket.co.kr", "wconcept.co.kr", "ssg.com")
PLACE_HOSTS = ("map.naver.com", "place.map.kakao.com", "map.kakao.com", "naver.me", "kko.to")
SKIP_HOSTS = ("youtube.com", "youtu.be", "investing.com", "tradingkey.com", "namu.wiki")

KIND_ORDER = {"장소": 0, "쇼핑": 1, "블로그": 2, "기타": 3}


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _matches(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def classify(url: str) -> str | None:
    """블로그/쇼핑/장소 for useful pages, 기타 for the rest, None for pages to skip."""
    host = _host(url)
    if not host or _matches(host, SKIP_HOSTS):
        return None
    if _matches(host, PLACE_HOSTS):
        return "장소"
    if _matches(host, SHOP_HOSTS):
        return "쇼핑"
    if _matches(host, BLOG_HOSTS):
        return "블로그"
    return "기타"


def build_query(title: str, keywords: list[str] | None, max_chars: int = 90) -> str:
    """The video's title plus up to two keywords the title does not already contain."""
    clean_title = re.sub(r"#\S+|[^\w\s가-힣·\-]", " ", str(title or ""))
    clean_title = " ".join(clean_title.split())
    extra = [k for k in (keywords or []) if isinstance(k, str) and k.strip() and k.strip() not in clean_title][:2]
    return " ".join([clean_title, *extra]).strip()[:max_chars]


def enabled() -> bool:
    return (
        os.getenv("RELATED_LINKS_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
        and "tavily" in sv.available_providers()
    )


def verified_source_links(fact_checks: list[dict] | None) -> list[dict]:
    """Pages that confirmed a claim, offered as further reading (shop or place pages)."""
    links = []
    for check in fact_checks or []:
        if not isinstance(check, dict) or str(check.get("verdict", "")).upper() != "SUPPORTED":
            continue
        for source in check.get("sources") or []:
            url = str(source.get("url", "")) if isinstance(source, dict) else ""
            kind = classify(url)
            if kind and kind != "기타":
                links.append({"title": str(source.get("title", "") or url)[:120], "url": url, "kind": kind,
                              "origin": "VERIFICATION"})
    return links


def find_related_links(title: str, keywords: list[str] | None, fact_checks: list[dict] | None = None,
                       limit: int = MAX_LINKS) -> list[dict]:
    links = verified_source_links(fact_checks)
    if enabled():
        query = build_query(title, keywords)
        if query:
            try:
                found = sv._search_tavily(query)
            except Exception as exc:  # related links are optional
                print(f"[RELATED LINKS] 검색 건너뜀: {type(exc).__name__}")
                found = []
            for item in found:
                kind = classify(str(item.get("url", "")))
                if kind:
                    links.append({"title": str(item.get("title", "") or item["url"])[:120], "url": item["url"],
                                  "kind": kind, "origin": "SEARCH"})
    unique: dict[str, dict] = {}
    for link in links:
        unique.setdefault(link["url"], link)
    ranked = sorted(unique.values(), key=lambda link: (KIND_ORDER.get(link["kind"], 9), link["origin"] != "VERIFICATION"))
    return ranked[:limit]
