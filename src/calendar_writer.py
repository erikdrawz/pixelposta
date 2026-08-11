"""Build the site's release-calendar data file.

Writes `site/src/data/calendar.json`, the single input to `/naptar/`. The site
validates it again at build time (`site/src/utils/calendar.ts`), so the contract
between these two files is enforced from both ends.

Dates are written as real ISO strings and formatted in the browser layer, never
here. STATUS.md records why: the weekly newsletter's release rows are display
strings like "08.14", and sorting those as text goes wrong across a year
boundary. The calendar never has to think about that.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any, Optional

from src.collectors.gamesradar_releases import entries_for_year
from src.models import CalendarEntry

logger = logging.getLogger(__name__)

DEFAULT_OUT = Path("site/src/data/calendar.json")

#: Refuse to write a calendar with fewer dated entries than this.
#:
#: A full year runs to roughly 180 dated entries. If a GamesRadar layout change
#: breaks the parser, the honest outcome is a failed Action and a stale-but-
#: correct page, not a silently emptied calendar — the same reasoning as the
#: loud fallback in `src/issue_title.py`. Set well below the real figure so
#: normal year-end thinning (December has two) never trips it.
MIN_DATED_ENTRIES = 60


class CalendarTooSmallError(RuntimeError):
    """The parse produced too few entries to be believable."""


def _entry_json(entry: CalendarEntry, with_date: bool) -> dict:
    payload: dict[str, Any] = {
        "title": entry.title,
        "platforms": list(entry.platforms),
        "earlyAccess": entry.early_access,
    }
    if with_date:
        assert entry.release_date is not None
        payload["date"] = entry.release_date.isoformat()
        # Reserved for the OpenCritic pass. Written as null from the start so
        # adding scores later is a data refresh, not a file migration.
        payload["score"] = None
        payload["openCriticId"] = None
    return payload


def build_payload(
    entries: list[CalendarEntry],
    year: int,
    generated: Optional[date] = None,
) -> dict:
    """Filter to one year and shape the JSON. Raises if the parse looks broken."""
    dated, undated = entries_for_year(entries, year)

    if len(dated) < MIN_DATED_ENTRIES:
        raise CalendarTooSmallError(
            f"only {len(dated)} dated {year} entries (expected at least "
            f"{MIN_DATED_ENTRIES}). GamesRadar's markup has probably changed — "
            f"check src/collectors/gamesradar_releases.py before rerunning. "
            f"The existing calendar.json has been left untouched."
        )

    return {
        "year": year,
        "generated": (generated or date.today()).isoformat(),
        "dated": [_entry_json(e, with_date=True) for e in dated],
        "tbc": [_entry_json(e, with_date=False) for e in undated],
    }


def write_calendar(payload: dict, out_path: Path = DEFAULT_OUT) -> Path:
    """Write the payload as pretty-printed JSON and return the path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # ensure_ascii=False keeps accented titles readable in the committed diff;
    # the trailing newline keeps git from reporting "no newline at end of file".
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    logger.info(
        "wrote %s (%d dated, %d TBC)",
        out_path, len(payload["dated"]), len(payload["tbc"]),
    )
    return out_path
