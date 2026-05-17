"""Deduplicate freshly collected articles against what's already in Notion.

URL-based for now: same canonical URL → duplicate. Semantic dedup
(near-duplicate titles across sources) can come later if it turns out to
matter; the editor catches the obvious cases during curation.
"""
from __future__ import annotations

from src.models import CollectedArticle


def dedupe(
    articles: list[CollectedArticle],
    existing_urls: set[str],
) -> tuple[list[CollectedArticle], int]:
    """Return (new_articles, dup_count). Order of new_articles is preserved.

    Also dedupes within the input batch itself — if two feeds happen to surface
    the same URL today, we only keep the first.
    """
    seen: set[str] = set(existing_urls)
    new: list[CollectedArticle] = []
    dup_count = 0
    for a in articles:
        if a.url in seen:
            dup_count += 1
            continue
        seen.add(a.url)
        new.append(a)
    return new, dup_count
