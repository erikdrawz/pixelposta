"""Iterate on the release picker without re-running the full draft.

Fetches the VGC schedule, runs the Haiku picker, prints the resulting
this-week / next-week tables as Markdown. No Notion access, no Sonnet calls.

Usage:
    python -m scripts.preview_releases                    # today as reference
    python -m scripts.preview_releases --today 2026-05-22 # override reference date
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from dotenv import load_dotenv

from src.collectors.vgc_releases import fetch_release_schedule
from src.draft_assembler import _format_hu_date, _format_release_list
from src.release_picker import HaikuReleasePicker


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--today", type=date.fromisoformat, default=None, metavar="YYYY-MM-DD",
                        help="override the reference date (default: today)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    load_dotenv(override=True)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    today = args.today or date.today()
    print(f"Reference date: {today.isoformat()}\n")

    schedule_text = fetch_release_schedule()
    picker = HaikuReleasePicker()
    snapshot = picker.pick(schedule_text, today=today)

    print(f"## Heti megjelenések ({_format_hu_date(snapshot.this_week_range[0])} – {_format_hu_date(snapshot.this_week_range[1])})\n")
    for line in _format_release_list(snapshot.this_week):
        print(line)
    print()

    print(f"## Jövő heti megjelenések ({_format_hu_date(snapshot.next_week_range[0])} – {_format_hu_date(snapshot.next_week_range[1])})\n")
    for line in _format_release_list(snapshot.next_week):
        print(line)
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
