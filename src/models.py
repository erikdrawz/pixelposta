"""Shared data structures used across collectors and the rest of the pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class CollectedArticle:
    """An article as it comes out of a collector, before pre-filtering."""

    source: str
    title: str
    url: str
    published_at: datetime | None
    # Short blurb from the RSS entry (description / summary field). May be HTML
    # or plain text. Empty string if the feed didn't include one. Fed to the
    # Haiku pre-filter — we do not fetch the article's full text at this stage.
    summary: str = ""


@dataclass(frozen=True)
class SelectedArticle:
    """An article the editor flagged as Selected, ready for draft generation."""

    page_id: str
    title: str
    source: str
    url: str
    published_at: date | None
    category: str
    relevance_score: int
    hu_summary: str
    filter_reasoning: str
    highlighted: bool
    #: Original feed blurb. The draft falls back to this when the article page
    #: is behind a bot challenge — see scripts/generate_draft.py.
    rss_summary: str = ""


@dataclass(frozen=True)
class ReleaseEntry:
    """A single game release row for the weekly newsletter's release tables."""

    title: str
    platforms: list[str]  # original names, e.g. ["PlayStation 5", "Xbox", "PC"]
    release_date: date


@dataclass(frozen=True)
class CalendarEntry:
    """A game on the site's year-round release calendar (`/naptar/`).

    Separate from `ReleaseEntry` rather than an extension of it: that one is the
    weekly newsletter's contract and always has a real date, while the calendar
    also carries titles confirmed for the year with no date yet.

    `year` is the year the game is filed under, which is why it is not simply
    read off `release_date` — for a "TBC 2026" entry it is the only date signal
    there is.
    """

    title: str
    platforms: list[str]  # short labels, e.g. ["PC", "Xbox", "Switch 2"]
    release_date: date | None
    year: int | None
    early_access: bool = False
