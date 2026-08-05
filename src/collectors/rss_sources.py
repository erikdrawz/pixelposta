"""Collect articles from the RSS-based sources.

Forbes and Bloomberg do not expose a clean gaming-only RSS feed and are
handled by separate collectors (see PROJECT_BRIEF.md).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable

import feedparser
from bs4 import BeautifulSoup

from src.models import CollectedArticle

logger = logging.getLogger(__name__)


# Source name → RSS feed URL. The source name MUST match a value in the Notion
# `Source` select (see NOTION_SCHEMA.md), otherwise the Notion write will fail.
RSS_FEEDS: dict[str, str] = {
    "RPS": "https://www.rockpapershotgun.com/feed",
    "NintendoLife": "https://www.nintendolife.com/feeds/news",
    "VGC": "https://www.videogameschronicle.com/feed/",
    "GameDiscover": "https://newsletter.gamediscover.co/feed",
    "TheGameBusiness": "https://www.thegamebusiness.com/feed",
    "DigitalFoundry": "https://www.digitalfoundry.net/feed",
    "TheVerge": "https://www.theverge.com/rss/notepad-microsoft-newsletter/index.xml",
    "ThisWeekInVideoGames": "https://thisweekinvideogames.com/feed/",
    # Main feed carries Windows/Microsoft + gaming mixed; Haiku pre-filter drops
    # the non-gaming items. Section-specific gaming feed does not exist.
    "WindowsCentral": "https://www.windowscentral.com/feeds.xml",
}

# Several sites (e.g., ThisWeekInVideoGames behind Cloudflare) reject feedparser's
# default User-Agent. Use a plain browser UA across the board for consistency.
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class CollectionError(RuntimeError):
    """Raised at the end of a run if one or more sources failed.

    Carries the successfully collected articles so the caller can still
    persist them — we never silently drop articles on a partial failure.
    """

    def __init__(
        self,
        message: str,
        *,
        articles: list[CollectedArticle],
        failures: list[tuple[str, Exception]],
    ) -> None:
        super().__init__(message)
        self.articles = articles
        self.failures = failures


def collect_all(max_age_days: int | None = 14) -> list[CollectedArticle]:
    """Pull every configured RSS feed and return a flat list of articles.

    Args:
        max_age_days: Drop articles whose `published_at` is older than this
            many days. Articles without a published date are kept regardless.
            Pass None to disable the filter.

    On per-source failure: log, continue with the other sources, and raise
    CollectionError at the end (with the partial result attached). On
    full success: return the list normally.
    """
    cutoff_dt: datetime | None = None
    if max_age_days is not None:
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    articles: list[CollectedArticle] = []
    failures: list[tuple[str, Exception]] = []
    dropped_too_old = 0

    for source, feed_url in RSS_FEEDS.items():
        try:
            raw = list(_collect_one(source, feed_url))
        except Exception as exc:
            logger.exception("collector failed for source=%s", source)
            failures.append((source, exc))
            continue

        if cutoff_dt is None:
            kept = raw
        else:
            kept = [a for a in raw if a.published_at is None or a.published_at >= cutoff_dt]
            dropped_too_old += len(raw) - len(kept)

        logger.info("collected %d articles from %s (kept after age filter)", len(kept), source)
        articles.extend(kept)

    if dropped_too_old:
        logger.info("age filter dropped %d articles older than %d days", dropped_too_old, max_age_days)

    if failures:
        names = ", ".join(name for name, _ in failures)
        raise CollectionError(
            f"some collectors failed: {names}",
            articles=articles,
            failures=failures,
        )
    return articles


def _collect_one(source: str, feed_url: str) -> Iterable[CollectedArticle]:
    parsed = feedparser.parse(feed_url, agent=_USER_AGENT)

    # feedparser sets `bozo` on any parse anomaly. Many feeds are technically
    # malformed but still yield entries — only treat it as fatal if we got nothing.
    if parsed.bozo and not parsed.entries:
        raise RuntimeError(f"failed to parse feed: {parsed.bozo_exception!r}")

    for entry in parsed.entries:
        url = (entry.get("link") or "").strip()
        title = (entry.get("title") or "").strip()
        if not url or not title:
            continue
        yield CollectedArticle(
            source=source,
            title=title,
            url=url,
            published_at=_parse_date(entry),
            summary=_extract_summary(entry),
        )


def _extract_summary(entry) -> str:
    """Plain-text blurb from an RSS entry, capped at a few hundred chars.

    Feeds vary: some use 'summary', some 'description', and many wrap content
    in HTML. We strip tags and collapse whitespace so the Haiku pre-filter
    gets clean text and we don't waste tokens on markup.
    """
    raw = entry.get("summary") or entry.get("description") or ""
    if not raw:
        return ""
    text = BeautifulSoup(raw, "html.parser").get_text(separator=" ", strip=True)
    # Cap at ~1500 chars so a single very chatty feed entry can't blow up
    # token usage in the pre-filter. ~1500 chars ≈ 250 words, plenty of signal.
    return text[:1500]


def _parse_date(entry) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime(*parsed[:6], tzinfo=timezone.utc)
