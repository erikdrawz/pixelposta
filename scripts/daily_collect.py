"""Daily collection pipeline: RSS → dedup → Haiku pre-filter → Notion.

This is what GitHub Actions will eventually run on a morning cron, but for
now it's a manually-invoked script so you can vet quality before going live.

Usage:
    python -m scripts.daily_collect --dry-run             # full pipeline, but no Notion writes
    python -m scripts.daily_collect --dry-run --max 20    # cap to 20 new articles
    python -m scripts.daily_collect --max 30              # actually write up to 30 includes to Notion
    python -m scripts.daily_collect                       # full run, everything new goes to Notion

Failure isolation: a single bad article (Haiku error, Notion 400, etc.) is
logged and skipped, not allowed to break the whole run.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date

from dotenv import load_dotenv

from collections import defaultdict

from src.collectors.rss_sources import CollectionError, collect_all
from src.deduplicator import dedupe
from src.filter import FilterParseError, HaikuFilter
from src.models import CollectedArticle
from src.notion_client import ArticlePayload, NotionArticles


logger = logging.getLogger("daily_collect")


def _interleave_by_source(articles: list[CollectedArticle]) -> list[CollectedArticle]:
    """Reorder so consecutive items rotate across sources.

    Without this, the first N articles of a capped run all come from whichever
    source the collector listed first (RPS at 100 entries dominates). Round-robin
    gives a representative sample across every source.
    """
    buckets: dict[str, list[CollectedArticle]] = defaultdict(list)
    for a in articles:
        buckets[a.source].append(a)
    queues = list(buckets.values())
    interleaved: list[CollectedArticle] = []
    while queues:
        next_queues: list[list[CollectedArticle]] = []
        for q in queues:
            interleaved.append(q.pop(0))
            if q:
                next_queues.append(q)
        queues = next_queues
    return interleaved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="run the full pipeline but skip Notion writes (still calls Haiku)",
    )
    parser.add_argument(
        "--max", type=int, default=None, metavar="N",
        help="process at most N new (post-dedup) articles through the filter",
    )
    parser.add_argument(
        "--exclude-source", action="append", default=[], metavar="NAME",
        help="skip articles from this source (e.g. --exclude-source RPS). Repeat for multiple.",
    )
    parser.add_argument(
        "--max-age-days", type=int, default=14, metavar="N",
        help="drop articles whose published date is older than N days (default: 14). 0 disables.",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="show DEBUG logging (incl. Haiku cache stats)",
    )
    args = parser.parse_args()

    load_dotenv(override=True)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    # 1. Collect from RSS.
    logger.info("step 1: collecting from RSS sources")
    max_age = args.max_age_days if args.max_age_days > 0 else None
    try:
        collected = collect_all(max_age_days=max_age)
        failures = []
    except CollectionError as e:
        logger.warning("%d source(s) failed; continuing with %d articles", len(e.failures), len(e.articles))
        collected = e.articles
        failures = e.failures
    logger.info("collected %d total articles", len(collected))

    if args.exclude_source:
        before = len(collected)
        excluded_sources = set(args.exclude_source)
        collected = [a for a in collected if a.source not in excluded_sources]
        logger.info(
            "filtered out %d articles from sources: %s (kept %d)",
            before - len(collected), sorted(excluded_sources), len(collected),
        )

    # 2. Load existing Notion URLs and dedupe.
    logger.info("step 2: loading existing URLs from Notion and deduping")
    notion = NotionArticles()
    existing_urls = notion.get_existing_urls()
    new_articles, dup_count = dedupe(collected, existing_urls)
    logger.info("dedup: %d already in Notion, %d new", dup_count, len(new_articles))

    # 3. Round-robin across sources, then apply --max cap. This makes a capped
    # run a representative cross-section, not just "the first N of the biggest feed".
    new_articles = _interleave_by_source(new_articles)
    if args.max is not None and len(new_articles) > args.max:
        logger.info("capping to %d new articles after round-robin (--max)", args.max)
        new_articles = new_articles[:args.max]

    if not new_articles:
        print("\nNothing new to filter. Done.")
        return 0

    # 4. Pre-filter with Haiku.
    logger.info("step 3: pre-filtering %d articles with Haiku", len(new_articles))
    filter_ = HaikuFilter()
    included: list[tuple[CollectedArticle, object]] = []
    excluded: list[tuple[CollectedArticle, object]] = []
    filter_errors = 0
    started = time.time()
    today = date.today()

    for i, article in enumerate(new_articles, 1):
        try:
            result = filter_.filter_article(article)
        except FilterParseError as e:
            logger.error("filter parse error on %s: %s", article.url, e)
            filter_errors += 1
            continue
        except Exception as e:
            logger.error("filter API error on %s: %s: %s", article.url, type(e).__name__, e)
            filter_errors += 1
            continue

        if result.decision == "exclude":
            excluded.append((article, result))
            logger.debug("[%d/%d] EXCLUDE %s — %s", i, len(new_articles), article.url, result.filter_reasoning)
        else:
            included.append((article, result))
            logger.info(
                "[%d/%d] INCLUDE %s [%s, score=%d] — %s",
                i, len(new_articles), article.title[:60], result.category,
                result.relevance_score, article.url,
            )

    filter_elapsed = time.time() - started
    logger.info(
        "filter done in %.1fs (%.1fs/article): %d include, %d exclude, %d error",
        filter_elapsed, filter_elapsed / max(len(new_articles), 1),
        len(included), len(excluded), filter_errors,
    )

    # In dry-run, surface what the filter excluded so the editor can sanity-check.
    if args.dry_run and excluded:
        print("\n--- Excluded articles (dry run only) ---")
        for article, result in excluded:
            print(f"  [{article.source}] {article.title}")
            print(f"    {article.url}")
            print(f"    Reason: {result.filter_reasoning}")
            print()

    # 5. Write includes to Notion (unless --dry-run).
    written = 0
    notion_errors = 0
    if args.dry_run:
        logger.info("--dry-run: skipping Notion writes (%d would have been written)", len(included))
    else:
        logger.info("step 4: writing %d articles to Notion", len(included))
        for article, result in included:
            payload = ArticlePayload(
                title=article.title,
                source=article.source,
                url=article.url,
                published_at=article.published_at,
                collected_at=today,
                category=result.category,
                relevance_score=result.relevance_score,
                hu_summary=result.hu_summary,
                filter_reasoning=result.filter_reasoning,
            )
            try:
                notion.create_article(payload)
                written += 1
            except Exception as e:
                logger.error("Notion write failed for %s: %s: %s", article.url, type(e).__name__, e)
                notion_errors += 1

    # 6. Final report.
    print("\n--- Daily collection report ---")
    print(f"  Collected:      {len(collected)} articles from RSS")
    print(f"  Source errors:  {len(failures)}")
    print(f"  Dup (skipped):  {dup_count}")
    print(f"  New:            {len(new_articles)} (after --max cap)" if args.max else f"  New:            {len(new_articles)}")
    print(f"  → Include:      {len(included)}")
    print(f"  → Exclude:      {len(excluded)}")
    print(f"  → Filter errs:  {filter_errors}")
    if args.dry_run:
        print(f"  Notion writes:  0 (dry run; would have written {len(included)})")
    else:
        print(f"  Notion writes:  {written}")
        print(f"  Notion errors:  {notion_errors}")

    # Exit non-zero if anything failed, so a CI cron can flag it.
    if failures or filter_errors or notion_errors:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
