"""Fetch and extract the readable body of an article URL.

Uses `trafilatura`, which is purpose-built for article body extraction and
handles most news sites without per-source tweaking. Returns plain text
suitable for feeding to a Sonnet rewrite — paywalls, cookie banners, ads,
nav menus all stripped.
"""
from __future__ import annotations

import logging

import httpx
import trafilatura

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_TIMEOUT = httpx.Timeout(20.0, connect=10.0)
# Trim very long articles so a single bad page doesn't blow up token usage.
# ~8000 chars ≈ 1500 tokens of English prose; plenty for a 90-120 word rewrite.
_MAX_CHARS = 8000


class FetchError(RuntimeError):
    pass


def fetch_article_text(url: str) -> str:
    """Download the page at `url` and return its main article text.

    Raises FetchError on HTTP errors or empty extraction. The caller decides
    whether to skip the article or surface the failure.
    """
    try:
        with httpx.Client(headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            html = response.text
    except httpx.HTTPError as e:
        raise FetchError(f"HTTP error fetching {url}: {e}") from e

    text = trafilatura.extract(
        html,
        favor_recall=False,  # prefer precision: skip sidebars / related-articles blocks
        include_comments=False,
        include_tables=False,
        no_fallback=False,
    )
    if not text or not text.strip():
        raise FetchError(f"trafilatura extracted no text from {url}")

    return text.strip()[:_MAX_CHARS]
