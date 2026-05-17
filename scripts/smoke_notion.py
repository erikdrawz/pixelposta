"""End-to-end smoke test for the Notion client.

Inserts one fake article into the Articles database, then reads it back
via get_existing_urls() to verify the round trip works. Cleans up
nothing — delete the test row manually in Notion when done.

Usage:
    python -m scripts.smoke_notion
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timezone

from dotenv import load_dotenv

from src.notion_client import ArticlePayload, NotionArticles


TEST_URL = "https://example.com/heti-vagolap-smoke-test"


def main() -> int:
    load_dotenv(override=True)

    notion = NotionArticles()
    payload = ArticlePayload(
        title="[SMOKE TEST] Pixelposta pipeline check",
        source="RPS",
        url=TEST_URL,
        published_at=datetime(2026, 5, 17, 10, 0, tzinfo=timezone.utc),
        collected_at=date.today(),
        category="Játékhírek",
        relevance_score=3,
        hu_summary="Ez egy automatikusan generált tesztcikk a Notion integráció ellenőrzéséhez.",
        filter_reasoning="smoke test — not a real article",
    )

    print("Inserting test article...")
    page_id = notion.create_article(payload)
    print(f"  page_id: {page_id}")

    print("Reading back URLs...")
    urls = notion.get_existing_urls()
    print(f"  total URLs in DB: {len(urls)}")

    if TEST_URL not in urls:
        print(f"ERROR: round-trip failed — {TEST_URL!r} not found in database after insert")
        return 1

    print("\nOK. The test row is in Notion as '[SMOKE TEST] ...' — delete it manually when done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
