"""The filter's one retry, and the collector's tolerance for a few flakes.

Haiku occasionally returns a tool call with an empty `filter_reasoning` —
roughly one article in two hundred. That used to fail the whole weekly collect
run even though the other ~190 articles reached Notion untouched.
"""
import os
from datetime import datetime, timezone

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-never-used")

from scripts.news_collector import FILTER_ERROR_FLOOR, FILTER_ERROR_RATE
from src.filter import FILTER_ATTEMPTS, FilterParseError, HaikuFilter, _parse_tool_input
from src.models import CollectedArticle

GOOD = {
    "decision": "exclude", "category": None, "relevance_score": None,
    "hu_summary": "", "filter_reasoning": "nem releváns",
}
# The exact shape that failed CI on 2026-10-16.
EMPTY_REASONING = dict(GOOD, filter_reasoning="")


def make_article():
    return CollectedArticle(
        title="t", url="https://example.com/a", source="RPS",
        summary="s", published_at=datetime.now(timezone.utc),
    )


def filter_returning(payloads):
    """A HaikuFilter whose Nth classification attempt yields payloads[N]."""
    f = HaikuFilter.__new__(HaikuFilter)  # no API key, no client
    calls = []

    def _classify_once(article):
        payload = payloads[len(calls)]
        calls.append(payload)
        if not payload.get("filter_reasoning"):
            raise FilterParseError("filter_reasoning is required and was empty")
        return _parse_tool_input(payload)

    f._classify_once = _classify_once
    return f, calls


def test_retries_once_past_a_flake():
    f, calls = filter_returning([EMPTY_REASONING, GOOD])
    assert f.filter_article(make_article()).decision == "exclude"
    assert len(calls) == 2


def test_clean_call_is_not_retried():
    f, calls = filter_returning([GOOD])
    f.filter_article(make_article())
    assert len(calls) == 1


def test_persistent_failure_still_raises():
    f, calls = filter_returning([EMPTY_REASONING] * (FILTER_ATTEMPTS + 2))
    with pytest.raises(FilterParseError):
        f.filter_article(make_article())
    assert len(calls) == FILTER_ATTEMPTS


def tolerated(article_count):
    return max(FILTER_ERROR_FLOOR, int(article_count * FILTER_ERROR_RATE))


def test_a_handful_of_flakes_does_not_fail_a_full_run():
    # The 2026-10-09 and 2026-10-16 runs: one bad article out of ~190.
    assert 1 <= tolerated(189)


def test_systematic_breakage_still_fails():
    assert 40 > tolerated(189)


def test_small_runs_keep_a_floor():
    # --max 10 must not fail on a single flake just because 2% rounds to zero.
    assert 1 <= tolerated(10)
