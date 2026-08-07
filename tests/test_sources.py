"""Keep the collector's sources and Notion's allowed values in step.

These two lists live apart for good reasons — one is "where do we fetch from",
the other is "what will Notion accept" — but nothing connected them, so adding
a feed without adding the matching Notion option produced a ValueError eight
minutes into a live run, after the Haiku filtering had already been paid for
and part of the batch written. Cheap to catch here instead.
"""
from src.collectors.rss_sources import RSS_FEEDS
from src.notion_client import SOURCE_OPTIONS


def test_every_rss_feed_has_a_notion_source_option():
    missing = sorted(set(RSS_FEEDS) - SOURCE_OPTIONS)
    assert not missing, (
        f"these feeds would be rejected by ArticlePayload: {missing}. "
        f"Add them to SOURCE_OPTIONS in src/notion_client.py *and* to the "
        f"Source select in Notion."
    )


def test_source_options_are_documented():
    """Anything Notion accepts should appear in NOTION_SCHEMA.md."""
    import pathlib

    schema = pathlib.Path(__file__).resolve().parents[1] / "NOTION_SCHEMA.md"
    text = schema.read_text(encoding="utf-8")
    undocumented = sorted(s for s in SOURCE_OPTIONS if f"`{s}`" not in text)
    assert not undocumented, f"missing from NOTION_SCHEMA.md source list: {undocumented}"
