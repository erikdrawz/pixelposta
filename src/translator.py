"""Draft generator: turn Selected articles into Hungarian newsletter prose.

Uses Claude Sonnet 4.6 with prompt caching on the system message and a forced
tool call for structured output. Each Selected article gets its own API call
with the full fetched article text — Sonnet rewrites (not translates) it into
a 90-120 word Hungarian newsletter paragraph.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from anthropic import Anthropic

from src.models import SelectedArticle

logger = logging.getLogger(__name__)

SONNET_MODEL = "claude-sonnet-4-6"
PROMPT_PATH = Path(__file__).parent / "prompts" / "translator_prompt.md"

TOOL_NAME = "submit_rewrite"
REWRITE_TOOL = {
    "name": TOOL_NAME,
    "description": (
        "Submit the Hungarian newsletter rewrite for the article. Call this exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "hu_title": {
                "type": "string",
                "description": (
                    "Hungarian title, sentence case, max ~80 chars. Not clickbait."
                ),
            },
            "hu_rewrite": {
                "type": "string",
                "description": (
                    "Hungarian newsletter paragraph, 60-80 words. Editorial rewrite, "
                    "not a literal translation. Pick the essentials, don't list every detail."
                ),
            },
            "hu_kiemelt_info": {
                "type": ["string", "null"],
                "description": (
                    "Required when the article is highlighted: a 1-2 sentence "
                    "punchy Hungarian takeaway. Must be null otherwise."
                ),
            },
        },
        "required": ["hu_title", "hu_rewrite", "hu_kiemelt_info"],
    },
}


@dataclass(frozen=True)
class RewriteResult:
    hu_title: str
    hu_rewrite: str
    hu_kiemelt_info: str | None


class RewriteParseError(ValueError):
    """Raised when Sonnet's tool input doesn't match the expected shape."""


class SonnetTranslator:
    def __init__(self, api_key: str | None = None) -> None:
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set — put it in .env (see .env.example)"
            )
        self.client = Anthropic(api_key=api_key)
        self.system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    def rewrite(
        self,
        article: SelectedArticle,
        full_text: str,
        *,
        today: date | None = None,
    ) -> RewriteResult:
        if today is None:
            today = date.today()
        response = self.client.messages.create(
            model=SONNET_MODEL,
            max_tokens=1000,
            system=[
                {
                    "type": "text",
                    "text": self.system_prompt,
                    "cache_control": {"type": "ephemeral"},
                },
            ],
            tools=[REWRITE_TOOL],
            tool_choice={"type": "tool", "name": TOOL_NAME},
            messages=[{"role": "user", "content": _format_user_message(article, full_text, today)}],
        )

        usage = response.usage
        logger.debug(
            "sonnet usage: input=%d cache_creation=%d cache_read=%d output=%d",
            usage.input_tokens,
            getattr(usage, "cache_creation_input_tokens", 0) or 0,
            getattr(usage, "cache_read_input_tokens", 0) or 0,
            usage.output_tokens,
        )

        tool_block = next(
            (b for b in response.content if getattr(b, "type", None) == "tool_use"),
            None,
        )
        if tool_block is None:
            raise RewriteParseError(
                f"Sonnet did not call the tool. Stop reason: {response.stop_reason!r}; "
                f"content blocks: {[getattr(b, 'type', '?') for b in response.content]}"
            )
        return _parse_tool_input(tool_block.input, article.highlighted)


def _format_user_message(article: SelectedArticle, full_text: str, today: date) -> str:
    lines = [
        f"Today: {today.isoformat()}",
    ]
    if article.published_at is not None:
        days_ago = (today - article.published_at).days
        if days_ago >= 0:
            lines.append(f"Published: {article.published_at.isoformat()} ({days_ago} nappal ezelőtt)")
        else:
            # Edge case: feed gives a future publish date; just show the raw date.
            lines.append(f"Published: {article.published_at.isoformat()}")
    lines.extend([
        f"Title: {article.title}",
        f"Source: {article.source}",
        f"URL: {article.url}",
        f"highlighted: {'true' if article.highlighted else 'false'}",
        "",
        "Full text:",
        full_text,
    ])
    return "\n".join(lines)


def _parse_tool_input(data: dict, highlighted: bool) -> RewriteResult:
    hu_title = (data.get("hu_title") or "").strip()
    hu_rewrite = (data.get("hu_rewrite") or "").strip()
    hu_kiemelt_info_raw = data.get("hu_kiemelt_info")

    if not hu_title:
        raise RewriteParseError("hu_title is required and was empty")
    if not hu_rewrite:
        raise RewriteParseError("hu_rewrite is required and was empty")

    # Normalise: null OR empty string both mean "no callout". Keep None for None.
    hu_kiemelt_info: str | None
    if hu_kiemelt_info_raw is None or not str(hu_kiemelt_info_raw).strip():
        hu_kiemelt_info = None
    else:
        hu_kiemelt_info = str(hu_kiemelt_info_raw).strip()

    if highlighted and hu_kiemelt_info is None:
        raise RewriteParseError("article is highlighted but Sonnet returned no hu_kiemelt_info")

    return RewriteResult(
        hu_title=hu_title,
        hu_rewrite=hu_rewrite,
        hu_kiemelt_info=hu_kiemelt_info,
    )
