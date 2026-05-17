"""Notion read/write for Articles and Issues.

Thin wrapper around `notion_client.Client` that speaks our domain
(CollectedArticle, ArticlePayload) and centralises the property-name
constants so a Notion schema rename only touches this file.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from notion_client import Client

from src.models import SelectedArticle

logger = logging.getLogger(__name__)


# Property names — must match the Articles database exactly (case-sensitive).
# See NOTION_SCHEMA.md and the manual setup section in README.md.
class ArticleProp:
    TITLE = "Title"
    SOURCE = "Source"
    URL = "URL"
    PUBLISHED_DATE = "Published date"
    COLLECTED_DATE = "Collected date"
    CATEGORY = "Category"
    RELEVANCE_SCORE = "Relevance score"
    HU_SUMMARY = "HU summary"
    STATUS = "Status"
    HIGHLIGHTED = "Highlighted"
    FULL_HU_TRANSLATION = "Full HU translation"
    KIEMELT_INFO_HU = "Kiemelt info HU"
    FILTER_REASONING = "Filter reasoning"
    ISSUE = "Issue"


# Valid select option values — kept in code so we fail at the boundary, not at
# Notion's API with a vaguer error.
SOURCE_OPTIONS = frozenset({
    "RPS", "NintendoLife", "VGC", "GameDiscover", "TheGameBusiness",
    "Forbes", "Bloomberg", "DigitalFoundry", "TheVerge", "ThisWeekInVideoGames",
})
CATEGORY_OPTIONS = frozenset({"Játékhírek", "Hardware", "AI & Gaming", "Stúdió & Üzlet"})
STATUS_OPTIONS = frozenset({"New", "Selected", "Published", "Passed", "Archived"})

Category = Literal["Játékhírek", "Hardware", "AI & Gaming", "Stúdió & Üzlet"]
Status = Literal["New", "Selected", "Published", "Passed", "Archived"]


@dataclass(frozen=True)
class ArticlePayload:
    """Full article record ready to be written to Notion.

    All fields are required because the brief specifies that articles are only
    written to Notion AFTER pre-filtering — at which point Haiku has supplied
    category, score, summary, and reasoning.
    """

    title: str
    source: str
    url: str
    published_at: datetime | None
    collected_at: date
    category: Category
    relevance_score: int
    hu_summary: str
    filter_reasoning: str

    def __post_init__(self) -> None:
        if self.source not in SOURCE_OPTIONS:
            raise ValueError(f"unknown source {self.source!r}; must be one of {sorted(SOURCE_OPTIONS)}")
        if self.category not in CATEGORY_OPTIONS:
            raise ValueError(f"unknown category {self.category!r}; must be one of {sorted(CATEGORY_OPTIONS)}")
        if not 1 <= self.relevance_score <= 5:
            raise ValueError(f"relevance_score must be 1-5, got {self.relevance_score}")


class NotionArticles:
    """Articles-database operations.

    Built against the Notion 2025 data-sources API model: a database is a
    container that holds one or more data sources, and properties / queries /
    inserts all operate on a data source, not directly on the database.
    """

    def __init__(self, token: str | None = None, database_id: str | None = None) -> None:
        token = token or os.environ["NOTION_TOKEN"]
        self.database_id = database_id or os.environ["NOTION_ARTICLES_DB_ID"]
        self.client = Client(auth=token)
        self.data_source_id = self._resolve_data_source_id()

    def _resolve_data_source_id(self) -> str:
        """Resolve the (single) data source ID inside the Articles database."""
        db = self.client.databases.retrieve(database_id=self.database_id)
        sources = db.get("data_sources", [])
        if not sources:
            raise RuntimeError(
                f"database {self.database_id} reports no data sources — "
                "the integration may lack access, or the workspace is on an "
                "older API model than this code targets"
            )
        if len(sources) > 1:
            names = [s.get("name") for s in sources]
            raise RuntimeError(
                f"database {self.database_id} has {len(sources)} data sources "
                f"({names}); this code assumes exactly one"
            )
        return sources[0]["id"]

    def get_existing_urls(self) -> set[str]:
        """Return every URL currently in the Articles data source.

        Used by the deduplicator before inserting newly collected articles.
        Paginates through the full table — cheap because the only property
        we read is URL, and the dataset stays in the low thousands of rows
        thanks to monthly cleanup.
        """
        urls: set[str] = set()
        cursor: str | None = None
        while True:
            kwargs = {"data_source_id": self.data_source_id, "page_size": 100}
            if cursor:
                kwargs["start_cursor"] = cursor
            response = self.client.data_sources.query(**kwargs)
            for page in response["results"]:
                url = _read_url(page["properties"].get(ArticleProp.URL))
                if url:
                    urls.add(url)
            if not response.get("has_more"):
                break
            cursor = response["next_cursor"]
        logger.info("loaded %d existing URLs from Notion", len(urls))
        return urls

    def create_article(self, payload: ArticlePayload) -> str:
        """Insert a new article row with Status=New. Returns the new page ID."""
        properties = {
            ArticleProp.TITLE: {"title": [{"text": {"content": payload.title[:2000]}}]},
            ArticleProp.SOURCE: {"select": {"name": payload.source}},
            ArticleProp.URL: {"url": payload.url},
            ArticleProp.COLLECTED_DATE: {"date": {"start": payload.collected_at.isoformat()}},
            ArticleProp.CATEGORY: {"select": {"name": payload.category}},
            ArticleProp.RELEVANCE_SCORE: {"number": payload.relevance_score},
            ArticleProp.HU_SUMMARY: _rich_text(payload.hu_summary),
            ArticleProp.FILTER_REASONING: _rich_text(payload.filter_reasoning),
            ArticleProp.STATUS: {"select": {"name": "New"}},
        }
        if payload.published_at is not None:
            properties[ArticleProp.PUBLISHED_DATE] = {
                "date": {"start": payload.published_at.date().isoformat()}
            }

        page = self.client.pages.create(
            parent={"type": "data_source_id", "data_source_id": self.data_source_id},
            properties=properties,
        )
        return page["id"]

    def get_selected_articles(self) -> list[SelectedArticle]:
        """Fetch every article currently marked Status=Selected.

        The draft generator reads these on Fridays. Filtered server-side so we
        only download the rows we care about; ordered by category then score so
        the editor's eventual draft layout has a predictable shape.
        """
        articles: list[SelectedArticle] = []
        cursor: str | None = None
        while True:
            kwargs = {
                "data_source_id": self.data_source_id,
                "page_size": 100,
                "filter": {
                    "property": ArticleProp.STATUS,
                    "select": {"equals": "Selected"},
                },
                "sorts": [
                    {"property": ArticleProp.CATEGORY, "direction": "ascending"},
                    {"property": ArticleProp.RELEVANCE_SCORE, "direction": "descending"},
                ],
            }
            if cursor:
                kwargs["start_cursor"] = cursor
            response = self.client.data_sources.query(**kwargs)
            for page in response["results"]:
                articles.append(_parse_selected(page))
            if not response.get("has_more"):
                break
            cursor = response["next_cursor"]
        logger.info("loaded %d Selected articles from Notion", len(articles))
        return articles


def _parse_selected(page: dict) -> SelectedArticle:
    props = page["properties"]
    return SelectedArticle(
        page_id=page["id"],
        title=_read_title(props.get(ArticleProp.TITLE)),
        source=_read_select(props.get(ArticleProp.SOURCE)) or "",
        url=_read_url(props.get(ArticleProp.URL)) or "",
        published_at=_read_date(props.get(ArticleProp.PUBLISHED_DATE)),
        category=_read_select(props.get(ArticleProp.CATEGORY)) or "",
        relevance_score=_read_number(props.get(ArticleProp.RELEVANCE_SCORE)) or 0,
        hu_summary=_read_rich_text(props.get(ArticleProp.HU_SUMMARY)),
        filter_reasoning=_read_rich_text(props.get(ArticleProp.FILTER_REASONING)),
        highlighted=bool((props.get(ArticleProp.HIGHLIGHTED) or {}).get("checkbox", False)),
    )


def _read_url(prop: dict | None) -> str | None:
    if not prop:
        return None
    return (prop.get("url") or "").strip() or None


def _read_title(prop: dict | None) -> str:
    if not prop:
        return ""
    return "".join(t.get("plain_text", "") for t in prop.get("title", []))


def _read_rich_text(prop: dict | None) -> str:
    if not prop:
        return ""
    return "".join(t.get("plain_text", "") for t in prop.get("rich_text", []))


def _read_select(prop: dict | None) -> str | None:
    if not prop:
        return None
    sel = prop.get("select") or {}
    return sel.get("name")


def _read_number(prop: dict | None) -> int | None:
    if not prop:
        return None
    n = prop.get("number")
    return int(n) if n is not None else None


def _read_date(prop: dict | None) -> date | None:
    if not prop:
        return None
    d = prop.get("date") or {}
    start = d.get("start")
    if not start:
        return None
    # Notion may return "YYYY-MM-DD" or full ISO timestamps; date.fromisoformat
    # handles the former; for the latter we slice off the date portion.
    try:
        return date.fromisoformat(start[:10])
    except ValueError:
        return None


def _rich_text(content: str) -> dict:
    # Notion caps individual rich_text blocks at 2000 chars. For everything we
    # write today (summary ~2 sentences, reasoning ~1 line, full translation
    # ~120 words ≈ 700 chars), one block is plenty.
    return {"rich_text": [{"text": {"content": content[:2000]}}]}
