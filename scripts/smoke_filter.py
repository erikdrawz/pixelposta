"""Smoke test for the Haiku pre-filter.

Collects articles from RSS, picks a varied sample (one per distinct source),
runs the Haiku pre-filter on each, and prints the classification. Does NOT
write to Notion — this is for prompt quality review.

Usage:
    python -m scripts.smoke_filter             # default: 8 articles, one per source
    python -m scripts.smoke_filter --count 15  # take more articles per run
"""
from __future__ import annotations

import argparse
import logging
import sys
import textwrap
import time

from dotenv import load_dotenv

from src.collectors.rss_sources import CollectionError, collect_all
from src.filter import FilterParseError, HaikuFilter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--count", type=int, default=8,
        help="how many articles to classify (default: 8, one per source)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="show DEBUG logging (incl. Haiku cache stats)",
    )
    args = parser.parse_args()

    load_dotenv(override=True)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    print("Collecting articles from RSS sources...")
    try:
        articles = collect_all()
    except CollectionError as e:
        print(f"WARNING: {len(e.failures)} source(s) failed; continuing with {len(e.articles)} articles")
        articles = e.articles

    if not articles:
        print("ERROR: no articles collected")
        return 1

    # Pick a varied sample: first article per source, then fill from the top.
    seen: set[str] = set()
    sample: list = []
    for a in articles:
        if a.source not in seen:
            seen.add(a.source)
            sample.append(a)
    for a in articles:
        if len(sample) >= args.count:
            break
        if a not in sample:
            sample.append(a)
    sample = sample[:args.count]

    filter_ = HaikuFilter()
    print(f"\nClassifying {len(sample)} articles with Haiku 4.5...\n")

    include_count = 0
    exclude_count = 0
    error_count = 0
    started = time.time()

    for i, article in enumerate(sample, 1):
        print(f"=== {i}/{len(sample)} ===")
        print(f"  Source: {article.source}")
        print(f"  Title:  {article.title}")
        print(f"  URL:    {article.url}")
        summary_preview = article.summary[:240] + ("..." if len(article.summary) > 240 else "")
        print(f"  Blurb:  {summary_preview or '(no RSS blurb)'}")
        try:
            result = filter_.filter_article(article)
        except FilterParseError as e:
            print(f"  PARSE ERROR: {e}")
            error_count += 1
            continue
        except Exception as e:
            print(f"  API ERROR: {type(e).__name__}: {e}")
            error_count += 1
            continue

        if result.decision == "include":
            include_count += 1
            print(f"  → INCLUDE  [{result.category}] score={result.relevance_score}")
            print(f"    HU summary: {textwrap.fill(result.hu_summary, width=88, subsequent_indent='                ')}")
        else:
            exclude_count += 1
            print(f"  → EXCLUDE")
        print(f"    Reasoning:  {result.filter_reasoning}")
        print()

    elapsed = time.time() - started
    print(f"--- Summary ---")
    print(f"  Total:    {len(sample)} articles in {elapsed:.1f}s ({elapsed / max(len(sample), 1):.1f}s/article)")
    print(f"  Include:  {include_count}")
    print(f"  Exclude:  {exclude_count}")
    if error_count:
        print(f"  Errors:   {error_count}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
