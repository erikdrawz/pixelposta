"""Fetch and clean the VGC upcoming releases schedule page.

Returns the schedule as plain text — the LLM-based picker (src/release_picker.py)
turns that into structured ReleaseEntry rows. Going through an LLM rather than
custom HTML parsing means a VGC layout change doesn't break the pipeline; only
the prompt may need a tweak.
"""
from __future__ import annotations

import logging

import httpx
import trafilatura

logger = logging.getLogger(__name__)

VGC_RELEASES_URL = (
    "https://www.videogameschronicle.com/guide/upcoming-game-release-dates-schedule/"
)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_TIMEOUT = httpx.Timeout(20.0, connect=10.0)


class VgcFetchError(RuntimeError):
    pass


def fetch_release_schedule() -> str:
    """Download the VGC release page and return its readable text content.

    Raises VgcFetchError on HTTP errors or empty extraction.
    """
    try:
        with httpx.Client(headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT, follow_redirects=True) as client:
            response = client.get(VGC_RELEASES_URL)
            response.raise_for_status()
            html = response.text
    except httpx.HTTPError as e:
        raise VgcFetchError(f"HTTP error fetching VGC releases: {e}") from e

    # favor_recall + include_tables: keep all the list entries; some are inside
    # table-ish markup on the source page.
    text = trafilatura.extract(
        html,
        favor_recall=True,
        include_tables=True,
        include_comments=False,
        no_fallback=False,
    )
    if not text or not text.strip():
        raise VgcFetchError("trafilatura extracted no text from VGC releases page")

    logger.info("fetched VGC releases (%d chars)", len(text))
    return text.strip()
