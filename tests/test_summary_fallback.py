"""The feed-summary fallback used when an article page is bot-challenged."""
from datetime import date

from scripts.generate_draft import MIN_FALLBACK_CHARS
from scripts.news_collector import _plain_text
from src.models import SelectedArticle
from src.translator import _format_user_message


def make_article(rss_summary=""):
    return SelectedArticle(
        page_id="p", title="Switch 2 sales", source="NintendoLife",
        url="https://example.com/a", published_at=date(2026, 8, 5),
        category="Hardware", relevance_score=4, hu_summary="hu",
        filter_reasoning="", highlighted=False, rss_summary=rss_summary,
    )


def test_plain_text_strips_feed_html():
    raw = '<p>Nintendo &amp; Sony</p><script>evil()</script><a href="#">more</a>'
    assert _plain_text(raw) == "Nintendo & Sony more"


def test_plain_text_handles_empty():
    assert _plain_text("") == ""
    assert _plain_text(None) == ""


def test_full_text_prompt_does_not_mention_the_summary_caveat():
    msg = _format_user_message(make_article(), "FULL BODY", date(2026, 8, 7), False)
    assert "Full text:" in msg
    assert "FIGYELEM" not in msg


def test_fallback_prompt_warns_against_inventing():
    msg = _format_user_message(make_article("blurb"), "blurb", date(2026, 8, 7), True)
    # Sonnet must know it is working from a blurb, be told to stay inside it,
    # and be given permission to write short rather than pad.
    assert "FIGYELEM" in msg
    assert "RSS-összefoglaló" in msg
    assert "Full text:" not in msg


def test_threshold_sits_between_the_measured_feeds():
    """Guards the constant against being nudged either way by accident.

    Measured live: NintendoLife blurbs run ~540 chars and produce an honest
    rewrite; VGC runs ~78 ("Dawn of the Machine is available now") and cannot.
    """
    nintendolife_typical = 540
    vgc_typical = 78
    assert vgc_typical < MIN_FALLBACK_CHARS < nintendolife_typical
