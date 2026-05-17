"""Pre-filter pipeline: decide which collected articles are worth showing to the editor.

Uses Claude Haiku 4.5 with prompt caching on the system message. Each article
gets its own API call. The classification is returned via a forced tool call
(`submit_classification`) — the SDK encodes the JSON, so Hungarian quotation
marks inside `hu_summary` can't break parsing the way they did with text JSON.
With caching, every call after the first in a daily run reads the system
prompt at ~10% of normal input cost.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from anthropic import Anthropic

from src.models import CollectedArticle

logger = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5-20251001"
PROMPT_PATH = Path(__file__).parent / "prompts" / "filter_prompt.md"

Category = Literal["Játékhírek", "Hardware", "AI & Gaming", "Stúdió & Üzlet"]
Decision = Literal["include", "exclude"]

VALID_CATEGORIES = {"Játékhírek", "Hardware", "AI & Gaming", "Stúdió & Üzlet"}

TOOL_NAME = "submit_classification"
CLASSIFICATION_TOOL = {
    "name": TOOL_NAME,
    "description": (
        "Submit the pre-filter classification for the article. Call this exactly "
        "once per article."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "decision": {
                "type": "string",
                "enum": ["include", "exclude"],
                "description": "Whether the article should reach the editor's curation list.",
            },
            "category": {
                "type": ["string", "null"],
                "enum": [
                    "Játékhírek", "Hardware", "AI & Gaming", "Stúdió & Üzlet", None,
                ],
                "description": "Exactly one category, or null when decision is 'exclude'.",
            },
            "relevance_score": {
                "type": ["integer", "null"],
                "minimum": 1,
                "maximum": 5,
                "description": "1-5 relevance score, or null when decision is 'exclude'.",
            },
            "hu_summary": {
                "type": "string",
                "description": (
                    "Two-sentence Hungarian summary. Empty string when decision is "
                    "'exclude'."
                ),
            },
            "filter_reasoning": {
                "type": "string",
                "description": "One-sentence Hungarian justification. Always required.",
            },
        },
        "required": ["decision", "category", "relevance_score", "hu_summary", "filter_reasoning"],
    },
}


@dataclass(frozen=True)
class FilterResult:
    decision: Decision
    category: Category | None
    relevance_score: int | None
    hu_summary: str
    filter_reasoning: str


class FilterParseError(ValueError):
    """Raised when Haiku's tool input doesn't match the expected shape."""


class HaikuFilter:
    def __init__(self, api_key: str | None = None) -> None:
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set — put it in .env (see .env.example)"
            )
        self.client = Anthropic(api_key=api_key)
        self.system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    def filter_article(self, article: CollectedArticle) -> FilterResult:
        response = self.client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=500,
            system=[
                {
                    "type": "text",
                    "text": self.system_prompt,
                    "cache_control": {"type": "ephemeral"},
                },
            ],
            tools=[CLASSIFICATION_TOOL],
            tool_choice={"type": "tool", "name": TOOL_NAME},
            messages=[{"role": "user", "content": _format_article(article)}],
        )

        usage = response.usage
        logger.debug(
            "haiku usage: input=%d cache_creation=%d cache_read=%d output=%d",
            usage.input_tokens,
            getattr(usage, "cache_creation_input_tokens", 0) or 0,
            getattr(usage, "cache_read_input_tokens", 0) or 0,
            usage.output_tokens,
        )

        tool_block = next(
            (block for block in response.content if getattr(block, "type", None) == "tool_use"),
            None,
        )
        if tool_block is None:
            raise FilterParseError(
                f"Haiku did not call the tool. Stop reason: {response.stop_reason!r}; "
                f"content blocks: {[getattr(b, 'type', '?') for b in response.content]}"
            )
        return _parse_tool_input(tool_block.input)


def _format_article(article: CollectedArticle) -> str:
    return (
        f"Title: {article.title}\n"
        f"Source: {article.source}\n"
        f"URL: {article.url}\n"
        f"Summary (RSS blurb): {article.summary or '(none)'}"
    )


def _parse_tool_input(data: dict) -> FilterResult:
    decision = data.get("decision")
    if decision not in {"include", "exclude"}:
        raise FilterParseError(f"unknown decision: {decision!r}")

    category = data.get("category")
    score = data.get("relevance_score")
    hu_summary = data.get("hu_summary") or ""
    reasoning = data.get("filter_reasoning") or ""

    if not reasoning:
        raise FilterParseError("filter_reasoning is required and was empty")

    if decision == "include":
        if category not in VALID_CATEGORIES:
            raise FilterParseError(
                f"include decision needs a valid category, got {category!r}"
            )
        if not isinstance(score, int) or not 1 <= score <= 5:
            raise FilterParseError(f"relevance_score must be 1-5, got {score!r}")
        if not hu_summary:
            raise FilterParseError("include decision needs a non-empty hu_summary")
    else:  # exclude
        category = None
        score = None
        hu_summary = ""

    return FilterResult(
        decision=decision,
        category=category,
        relevance_score=score,
        hu_summary=hu_summary,
        filter_reasoning=reasoning,
    )
