"""Generate a weekly newsletter draft from Notion's Selected articles.

Pipeline: Notion read → trafilatura full-text fetch → Sonnet rewrite → VGC
release snapshot → issue headline → two outputs.

Two outputs, deliberately independent so a problem with one cannot take the
other down:

    drafts/draft-YYYY-MM-DD.md                     flat markdown, paste into Substack
    site/src/content/issues/YYYY-WW/index.md       structured, committed for the site

Still PREVIEW mode against Notion: it does NOT update article statuses to
Published and does NOT create an Issues row, so it stays a safe loop you can
re-run against the same Selected set. Re-running also preserves the fields the
editor owns in an existing index.md — see src/site_writer.py.

Usage:
    python -m scripts.generate_draft                       # both outputs
    python -m scripts.generate_draft --no-site             # Substack markdown only
    python -m scripts.generate_draft --out custom.md       # custom markdown path
    python -m scripts.generate_draft --year 2026 --week 30 # backfill a specific week
    python -m scripts.generate_draft --verbose             # cache stats / per-article timing
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from src.collectors.vgc_releases import VgcFetchError, fetch_release_schedule
from src.draft_assembler import DraftEntry, assemble_markdown
from src.issue_title import SonnetIssueTitler, fallback_for
from src.notion_client import NotionArticles
from src.release_picker import HaikuReleasePicker, ReleasePickError, ReleaseSnapshot
from src.site_writer import DEFAULT_SITE_ROOT, write_issue
from src.translator import RewriteParseError, SonnetTranslator
from src.web_fetcher import FetchError, fetch_article_text


logger = logging.getLogger("generate_draft")

DEFAULT_OUT_DIR = Path("drafts")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=None, metavar="PATH",
        help="output markdown file (default: drafts/draft-YYYY-MM-DD.md)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="show DEBUG logging (incl. Sonnet cache stats)",
    )
    parser.add_argument(
        "--site-root", type=Path, default=DEFAULT_SITE_ROOT, metavar="PATH",
        help=f"Astro site root (default: {DEFAULT_SITE_ROOT})",
    )
    parser.add_argument(
        "--no-site", action="store_true",
        help="skip the site content file, only write the Substack markdown",
    )
    parser.add_argument(
        "--week", type=int, default=None, metavar="N",
        help="ISO week to file the issue under (default: this week)",
    )
    parser.add_argument(
        "--year", type=int, default=None, metavar="YYYY",
        help="ISO year to file the issue under (default: this year)",
    )
    args = parser.parse_args()

    load_dotenv(override=True)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    # 1. Read Selected articles from Notion.
    logger.info("step 1: loading Selected articles from Notion")
    notion = NotionArticles()
    selected = notion.get_selected_articles()
    if not selected:
        print("\nNo articles in Status=Selected. Nothing to generate.")
        return 0
    logger.info("found %d Selected articles", len(selected))

    # 2. Fetch full text + Sonnet rewrite for each.
    translator = SonnetTranslator()
    entries: list[DraftEntry] = []
    fetch_failures: list[tuple[str, str]] = []
    rewrite_failures: list[tuple[str, str]] = []
    started = time.time()
    today = date.today()

    for i, article in enumerate(selected, 1):
        logger.info("[%d/%d] %s [%s, score=%d]", i, len(selected), article.title[:70], article.category, article.relevance_score)

        try:
            full_text = fetch_article_text(article.url)
            logger.debug("  fetched %d chars from %s", len(full_text), article.url)
        except FetchError as e:
            logger.error("  fetch failed: %s", e)
            fetch_failures.append((article.url, str(e)))
            continue

        try:
            result = translator.rewrite(article, full_text, today=today)
        except RewriteParseError as e:
            logger.error("  rewrite parse error: %s", e)
            rewrite_failures.append((article.url, str(e)))
            continue
        except Exception as e:
            logger.error("  rewrite API error: %s: %s", type(e).__name__, e)
            rewrite_failures.append((article.url, f"{type(e).__name__}: {e}"))
            continue

        logger.info("  → %s", result.hu_title)
        entries.append(DraftEntry(article=article, rewrite=result))

    elapsed = time.time() - started
    logger.info(
        "rewrites done in %.1fs (%.1fs/article avg): %d ok, %d fetch fail, %d rewrite fail",
        elapsed, elapsed / max(len(selected), 1),
        len(entries), len(fetch_failures), len(rewrite_failures),
    )

    if not entries:
        print("\nNo successful rewrites. Nothing to assemble.")
        return 1

    # 3. Fetch + pick the VGC release snapshot. Failures here are non-fatal:
    # the draft still assembles, just with a placeholder.
    releases: ReleaseSnapshot | None = None
    try:
        logger.info("step 3: fetching VGC release schedule")
        schedule_text = fetch_release_schedule()
        picker = HaikuReleasePicker()
        releases = picker.pick(schedule_text, today=today)
        logger.info(
            "release picker selected %d this-week and %d next-week entries",
            len(releases.this_week), len(releases.next_week),
        )
    except (VgcFetchError, ReleasePickError) as e:
        logger.error("release snapshot failed: %s — falling back to placeholder", e)
    except Exception as e:
        logger.error("release snapshot crashed: %s: %s — falling back to placeholder", type(e).__name__, e)

    iso_year, iso_week, _ = today.isocalendar()
    year = args.year if args.year is not None else iso_year
    week = args.week if args.week is not None else iso_week

    # 4. Assemble the Substack markdown.
    markdown = assemble_markdown(
        entries, today=today, week_number=week, year=year, releases=releases
    )

    out_path = args.out
    if out_path is None:
        DEFAULT_OUT_DIR.mkdir(exist_ok=True)
        out_path = DEFAULT_OUT_DIR / f"draft-{today.isoformat()}.md"
    out_path.write_text(markdown, encoding="utf-8")

    # 5. Headline + site content file. Neither can fail the run: the Substack
    # draft above is already on disk and is the thing that must ship.
    site_path = None
    if not args.no_site:
        logger.info("step 5: generating issue title and site content file")
        try:
            titler = SonnetIssueTitler()
            issue_title = titler.generate(entries, year=year, week=week)
        except Exception as e:
            logger.error(
                "ISSUE TITLE FAILED to initialise (%s: %s) — using fallback headline",
                type(e).__name__, e,
            )
            issue_title = fallback_for(year, week)

        if issue_title.is_fallback:
            logger.error(
                "issue headline is the fallback %r — write a real one in index.md",
                issue_title.title,
            )
        else:
            logger.info("issue title: %s", issue_title.title)

        try:
            site_path = write_issue(
                entries,
                issue_title,
                year=year,
                week=week,
                releases=releases,
                site_root=args.site_root,
            )
        except Exception as e:
            logger.error(
                "SITE FILE FAILED (%s: %s) — the Substack draft at %s is unaffected",
                type(e).__name__, e, out_path,
            )

    print(f"\n--- Draft generation report ---")
    print(f"  Issue:           {year}. {week}. hét")
    print(f"  Selected:        {len(selected)}")
    print(f"  Rewritten:       {len(entries)}")
    print(f"  Fetch failures:  {len(fetch_failures)}")
    print(f"  Rewrite failures:{len(rewrite_failures)}")
    print(f"  Substack draft:  {out_path}")
    if site_path is not None:
        print(f"  Site content:    {site_path}")
    elif not args.no_site:
        print(f"  Site content:    FAILED — see the log above")
    if fetch_failures or rewrite_failures:
        print("\n  Failed URLs:")
        for url, reason in fetch_failures + rewrite_failures:
            print(f"    {url}")
            print(f"      → {reason}")

    return 0 if not (fetch_failures or rewrite_failures) else 1


if __name__ == "__main__":
    sys.exit(main())
