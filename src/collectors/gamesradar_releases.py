"""Fetch and parse GamesRadar's release-date schedule.

Returns structured `CalendarEntry` rows directly, with no LLM in the loop — the
page's markup is regular enough to parse, so the release calendar costs nothing
per refresh and gives the same answer every time.

That is the opposite trade-off from `vgc_releases.py`, which hands raw text to
Haiku (`src/release_picker.py`) so a layout change cannot break the weekly
newsletter. Here the output feeds a whole page rather than one table, so a
silent LLM misread is worse than a loud parse failure — callers get an explicit
count to check, and anything unparseable is logged rather than guessed at.

Page shape:

    <h3>BIGGEST GAMES OF JANUARY 2026</h3>
    <ul>
      <li>Code Vein 2 (PC, XSX, PS5) - January 30</li>
      <li>Slay the Spire 2 (PC) - March 5 [Early Access]</li>
    </ul>

The heading supplies the year; the entry supplies month and day. Headings also
come in `TBC 2026` (confirmed for the year, no date), bare `2027`, and plain
`TBC` (no year at all) forms.
"""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import Iterator, Optional

import httpx
from bs4 import BeautifulSoup

from src.models import CalendarEntry

logger = logging.getLogger(__name__)

GAMESRADAR_RELEASES_URL = "https://www.gamesradar.com/video-game-release-dates/"

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_TIMEOUT = httpx.Timeout(20.0, connect=10.0)

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

#: Source abbreviation -> the short label used on the calendar page.
#:
#: Deliberately shorter than the newsletter's convention in
#: `src/prompts/release_picker_prompt.md`, which expands these to
#: "Nintendo Switch 2" and "PlayStation 5". A ten-row weekly table can afford
#: the long form; a two-hundred-row calendar cannot without wrapping every row.
#:
#: `XBX` and `XO` are not real abbreviations — they are typos that appear in the
#: live page ("American Truck Simulator ... (XBX, PS5)", "Tanuki Pon's Summer
#: (PC, XSX, XO, NS)"). Mapped rather than reported, because they are the
#: source's mistake and stable.
PLATFORM_LABELS = {
    "PC": "PC",
    "PS5": "PS5",
    "PS4": "PS4",
    "XSX": "Xbox",
    "XBX": "Xbox",
    "XBO": "Xbox One",
    "XO": "Xbox One",
    "NS": "Switch",
    "NS2": "Switch 2",
}

#: Placeholders the source uses when the platform is not known yet. Dropped
#: rather than rendered — "TBC" in a platform column tells a reader nothing.
_PLATFORM_PLACEHOLDERS = {"TBC", "TBA", "N/A"}

# Headings: "BIGGEST GAMES OF JANUARY 2026" / "NEW GAMES OF AUGUST 2026".
_HEAD_MONTH = re.compile(
    r"^(?:BIGGEST|NEW)\s+GAMES\s+OF\s+([A-Z]+)\s+(\d{4})$", re.I
)
# "TBC 2026" -- confirmed for that year, no date. Bare "2027" -- entries carry
# their own year. Plain "TBC" -- no year at all, so nothing to file it under.
_HEAD_TBC_YEAR = re.compile(r"^TBC\s+(\d{4})$", re.I)
_HEAD_YEAR = re.compile(r"^(\d{4})$")

# A trailing bracketed note: "... - March 5 [Early Access]".
_NOTE = re.compile(r"\s*\[([^\]]*)\]\s*$")

_MONTH_NAMES = "|".join(MONTHS)

# The date is matched at the END of the line rather than by splitting on the
# separator, because the separator is not dependable: most entries use an en
# dash, roughly thirty use a plain hyphen ("Killer Inn (PC) - February 12"),
# one has no separator at all ("Empulse (PS5) TBC 2026"), and some omit the
# space on one side or the other ("(PC)- April 30", "(PC, XSX) -TBC 2026").
#
# Splitting on a plain hyphen would also cut titles that contain one in half --
# "Little Nightmares 3 - The Backstage", "Human Fall Flat - Nintendo Switch 2
# Edition". Anchoring on the date sidesteps the whole question.
_TRAILING_WHEN = re.compile(
    r"(?P<when>"
    r"(?:" + _MONTH_NAMES + r")\s+\d{1,2}(?:\s*,\s*\d{4})?"
    r"|(?:" + _MONTH_NAMES + r")\s+\d{4}"
    r"|TB[CAD](?:\s+\d{4})?"
    r")\s*$",
    re.I,
)

#: Dash characters that may sit between the title and the date, stripped off the
#: left-hand side once the date has been located.
_TRAILING_SEPARATOR = re.compile(r"[\s\-–—]+$")

# "Title (PC, PS5)" -- the platform group is the last parenthesis on the line,
# so a title containing its own parentheses survives.
_TITLE_PLATFORMS = re.compile(r"^(?P<title>.*?)\s*\((?P<plats>[^()]*)\)\s*$")

_WHEN_FULL = re.compile(
    r"^(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2})(?:\s*,\s*(?P<year>\d{4}))?$"
)
_WHEN_MONTH_YEAR = re.compile(r"^(?P<month>[A-Za-z]+)\s+(?P<year>\d{4})$")
_WHEN_TBC = re.compile(r"^TB[CAD](?:\s+(?P<year>\d{4}))?$", re.I)


class GamesRadarFetchError(RuntimeError):
    pass


def fetch_release_page() -> str:
    """Download the GamesRadar release-dates page and return its HTML.

    Raises GamesRadarFetchError on any HTTP error or an empty body.
    """
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        with httpx.Client(headers=headers, timeout=_TIMEOUT, follow_redirects=True) as client:
            response = client.get(GAMESRADAR_RELEASES_URL)
            response.raise_for_status()
            html = response.text
    except httpx.HTTPError as e:
        raise GamesRadarFetchError(f"HTTP error fetching GamesRadar releases: {e}") from e

    if not html.strip():
        raise GamesRadarFetchError("GamesRadar returned an empty body")

    logger.info("fetched GamesRadar releases (%d chars)", len(html))
    return html


def parse_platforms(raw: str) -> list[str]:
    """Turn "PC, XSX, NS2" into ["PC", "Xbox", "Switch 2"].

    Unknown tokens are kept verbatim and logged. A new console appearing in the
    source should show up on the page looking odd, not vanish from it.
    """
    labels: list[str] = []
    for chunk in re.split(r"[,/]", raw):
        chunk = chunk.strip()
        if not chunk:
            continue
        # A whole chunk may be a known abbreviation, or -- where the source
        # dropped a comma, as in "(PC, PS5, XSX NS2)" -- several of them.
        tokens = [chunk] if chunk.upper() in PLATFORM_LABELS else chunk.split()
        for token in tokens:
            key = token.strip().upper()
            if not key or key in _PLATFORM_PLACEHOLDERS:
                continue
            label = PLATFORM_LABELS.get(key)
            if label is None:
                label = token.strip()
                logger.warning("unknown platform token %r -- kept verbatim", label)
            if label not in labels:
                labels.append(label)
    return labels


def parse_entry(line: str, heading_year: Optional[int]) -> Optional[CalendarEntry]:
    """Parse one list item. Returns None if the line has no usable date part.

    `heading_year` is the year from the enclosing heading, used when the entry
    itself does not spell one out (which is the normal case).
    """
    text = " ".join(line.split())
    if not text:
        return None

    early_access = False
    note = _NOTE.search(text)
    if note:
        early_access = "early access" in note.group(1).lower()
        text = text[: note.start()].strip()

    found = _TRAILING_WHEN.search(text)
    if not found:
        logger.warning("no date found at end of entry: %r", text)
        return None
    when = found.group("when").strip()
    left = _TRAILING_SEPARATOR.sub("", text[: found.start()])

    match = _TITLE_PLATFORMS.match(left)
    if match:
        title = match.group("title").strip()
        platforms = parse_platforms(match.group("plats"))
    else:
        # No parenthesised platform list at all, e.g. "The Witcher 3: Songs of
        # the Past expansion - TBC 2027".
        title, platforms = left, []

    if not title:
        logger.warning("entry has no title: %r", text)
        return None

    release_date, year = _parse_when(when, heading_year)
    if release_date is None and year is None:
        # The page's final "TBC" section has no year in the heading and none in
        # the entries, so there is nothing to file these under. Expected, and
        # far too numerous to warn about -- the calendar only shows one year.
        level = logging.DEBUG if _WHEN_TBC.match(when) else logging.WARNING
        logger.log(level, "no year for %r in entry: %r", when, text)
        return None

    return CalendarEntry(
        title=title,
        platforms=platforms,
        release_date=release_date,
        year=year,
        early_access=early_access,
    )


def _parse_when(when: str, heading_year: Optional[int]):
    """Return (date_or_None, year_or_None) for the right-hand side of an entry."""
    match = _WHEN_FULL.match(when)
    if match:
        month = MONTHS.get(match.group("month").lower())
        if month:
            year = int(match.group("year")) if match.group("year") else heading_year
            if year:
                try:
                    return date(year, month, int(match.group("day"))), year
                except ValueError:
                    # e.g. "February 30" -- a source typo. Keep the year so the
                    # game still appears, just without a day.
                    logger.warning("invalid date %r -- keeping year only", when)
                    return None, year
            return None, None

    match = _WHEN_MONTH_YEAR.match(when)
    if match and match.group("month").lower() in MONTHS:
        return None, int(match.group("year"))

    match = _WHEN_TBC.match(when)
    if match:
        year = int(match.group("year")) if match.group("year") else heading_year
        return None, year

    return None, None


def _heading_year(text: str) -> Optional[int]:
    """The year a heading files its entries under, or None for a bare "TBC"."""
    text = " ".join(text.split())
    for pattern in (_HEAD_MONTH, _HEAD_TBC_YEAR, _HEAD_YEAR):
        match = pattern.match(text)
        if match:
            return int(match.groups()[-1])
    return None


def _sections(soup: BeautifulSoup) -> Iterator:
    """Yield (heading_year, <li> element) for every entry on the page.

    Walks forward from each heading rather than assuming the list is its
    immediate next sibling -- the live page puts a <figure> between them.
    """
    for heading in soup.find_all("h3"):
        year = _heading_year(heading.get_text())
        for sibling in heading.next_siblings:
            if getattr(sibling, "name", None) == "h3":
                break
            if getattr(sibling, "name", None) in ("ul", "ol"):
                for item in sibling.find_all("li"):
                    yield year, item


def parse_release_page(html: str) -> list[CalendarEntry]:
    """Parse the whole page into entries, newest heading order preserved."""
    soup = BeautifulSoup(html, "html.parser")

    entries: list[CalendarEntry] = []
    skipped = 0
    for year, item in _sections(soup):
        entry = parse_entry(item.get_text(" ", strip=True), year)
        if entry is None:
            skipped += 1
            continue
        entries.append(entry)

    logger.info("parsed %d GamesRadar entries (%d skipped)", len(entries), skipped)
    return entries


def entries_for_year(entries: list[CalendarEntry], year: int):
    """Split entries into (dated, undated) for one year, dated ones sorted.

    Sorting happens here, on real `date` objects, so nothing downstream is ever
    tempted to sort the formatted display strings -- see the release-date note
    in STATUS.md.
    """
    dated = sorted(
        (e for e in entries if e.release_date is not None and e.release_date.year == year),
        key=lambda e: (e.release_date, e.title.lower()),
    )
    undated = sorted(
        (e for e in entries if e.release_date is None and e.year == year),
        key=lambda e: e.title.lower(),
    )
    return dated, undated
