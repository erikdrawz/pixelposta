"""Manual smoke test: pull every RSS source and print a per-source count.

Run from the repo root:

    python -m scripts.smoke_collect

Exits 1 if any source failed, but always prints what it did manage to collect.
"""
from __future__ import annotations

import logging
import sys
from collections import Counter

from src.collectors.rss_sources import CollectionError, collect_all


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        articles = collect_all()
        failures: list[tuple[str, Exception]] = []
    except CollectionError as err:
        articles = err.articles
        failures = err.failures

    by_source = Counter(a.source for a in articles)
    print(f"\nCollected {len(articles)} articles total:")
    for source, count in sorted(by_source.items()):
        print(f"  {source:<22} {count}")

    if failures:
        print("\nFailures:")
        for source, exc in failures:
            print(f"  {source:<22} {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
