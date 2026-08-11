"""Refresh the site's release calendar from GamesRadar.

Fetches the release-dates page, parses it, and writes
`site/src/data/calendar.json` for the `/naptar/` page. No Notion access, no API
keys, no LLM calls — the page's markup is regular enough to parse outright.

Run weekly by `.github/workflows/weekly-calendar.yml`, which commits the result.

Usage:
    python -m scripts.update_calendar                  # current year
    python -m scripts.update_calendar --dry-run        # parse and report only
    python -m scripts.update_calendar --year 2027      # a different year
"""
from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from src.calendar_writer import (
    DEFAULT_OUT,
    CalendarTooSmallError,
    build_payload,
    write_calendar,
)
from src.collectors.gamesradar_releases import (
    GamesRadarFetchError,
    fetch_release_page,
    parse_release_page,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=date.today().year,
                        help="calendar year to write (default: current year)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help=f"output path (default: {DEFAULT_OUT})")
    parser.add_argument("--from-file", type=Path, default=None, metavar="PATH",
                        help="parse saved HTML instead of fetching (for debugging)")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be written, write nothing")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.from_file:
        html = args.from_file.read_text(encoding="utf-8")
    else:
        try:
            html = fetch_release_page()
        except GamesRadarFetchError as e:
            # Worth being explicit: the page has been reachable in testing, but
            # the sources README documents Cloudflare challenges on other
            # gaming sites, and this is the failure that would look like one.
            print(f"error: could not fetch GamesRadar: {e}", file=sys.stderr)
            return 1

    entries = parse_release_page(html)

    try:
        payload = build_payload(entries, args.year)
    except CalendarTooSmallError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    months = Counter(e["date"][5:7] for e in payload["dated"])
    print(f"{args.year}: {len(payload['dated'])} dated, {len(payload['tbc'])} TBC")
    print("  per month: " + "  ".join(f"{m}:{n}" for m, n in sorted(months.items())))

    if args.dry_run:
        print(f"dry run — {args.out} not written")
        return 0

    write_calendar(payload, args.out)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
