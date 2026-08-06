"""Write a fake issue to the site content tree, with no API calls.

Exercises the slug generation, the frontmatter shape and the editor-field
preservation, so the Astro build can be pointed at the result to confirm the
pipeline's output actually satisfies the content schema.

    python -m scripts.smoke_site_writer                # writes site/src/content/issues/2026-31/
    python -m scripts.smoke_site_writer --clean        # removes it again
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from datetime import date
from pathlib import Path

from src.draft_assembler import DraftEntry
from src.issue_title import IssueTitle
from src.models import ReleaseEntry, SelectedArticle
from src.release_picker import ReleaseSnapshot, week_ranges_for
from src.site_writer import issue_dir, write_issue
from src.translator import RewriteResult

YEAR, WEEK = 2026, 31


def _entry(title_hu, category, score, source, url, kiemelt=None):
    return DraftEntry(
        article=SelectedArticle(
            page_id="fake",
            title="original english title",
            source=source,
            url=url,
            published_at=date(2026, 7, 28),
            category=category,
            relevance_score=score,
            hu_summary="Két mondatos magyar összefoglaló a szűrőből.",
            filter_reasoning="smoke test",
            highlighted=kiemelt is not None,
        ),
        rewrite=RewriteResult(
            hu_title=title_hu,
            hu_rewrite=(
                "Ez egy smoke teszt bekezdés, ami elég hosszú ahhoz, hogy a "
                "tördelést is lehessen rajta nézni. Tartalmaz ékezetes "
                "karaktereket: őrült, űrhajó, tükörfúrógép."
            ),
            hu_kiemelt_info=kiemelt,
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", action="store_true", help="delete the fake issue and exit")
    parser.add_argument("--site-root", type=Path, default=Path("site"))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    directory = issue_dir(YEAR, WEEK, args.site_root)

    if args.clean:
        if directory.exists():
            shutil.rmtree(directory)
            print(f"removed {directory}")
        else:
            print(f"nothing to remove at {directory}")
        return 0

    entries = [
        _entry(
            "A Bethesda megerősítette: jön az új Fallout, és őrült ütemben",
            "Játékhírek", 5, "VGC", "https://www.videogameschronicle.com",
            kiemelt="Ez a kiemelt info, ékezetekkel: ő, ű, á, é.",
        ),
        _entry(
            "Megjelent a Scarlet Deer Inn, hímzett karakterekkel",
            "Játékhírek", 4, "RPS", "https://www.rockpapershotgun.com/news",
        ),
        _entry(
            "Új Steam Deck firmware érkezett",
            "Hardware", 4, "DigitalFoundry", "https://www.digitalfoundry.net/news",
        ),
        # Same first 60 characters as the entry above once slugified — proves
        # the collision suffix works.
        _entry(
            "Új Steam Deck firmware érkezett, most már a régi modellekre is",
            "Hardware", 3, "TheVerge", "https://www.theverge.com",
        ),
    ]

    this_range, next_range = week_ranges_for(date(2026, 7, 27))
    releases = ReleaseSnapshot(
        this_week=[
            ReleaseEntry("Grounded 2", ["PC", "Xbox Series X"], date(2026, 7, 29)),
            ReleaseEntry("Shadow Labyrinth", ["PC", "PlayStation 5", "Nintendo Switch 2"], date(2026, 7, 30)),
        ],
        next_week=[
            ReleaseEntry("Mafia: The Old Country", ["PC", "PlayStation 5"], date(2026, 8, 4)),
        ],
        this_week_range=this_range,
        next_week_range=next_range,
    )

    title = IssueTitle(
        title="Fallout mindenhol, és egy hímzett szláv népmese",
        standfirst=(
            "A Bethesda egyszerre több nagy bejelentést tett a Fallout körül, a hét "
            "legkülönösebb játéka viszont egy kézzel hímzett szláv népmese-platformer."
        ),
    )

    path = write_issue(
        entries, title, year=YEAR, week=WEEK, releases=releases, site_root=args.site_root
    )
    print(f"\nwrote {path}")
    print(path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
