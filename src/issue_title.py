"""Generate the issue's editorial headline and standfirst.

These drive the site's landing hero, the archive list, the <title> tag and the
Open Graph metadata. One Sonnet call per issue, run after the article rewrites
so the model sees the Hungarian titles the reader will actually see.

This step never blocks a draft. Any failure falls back to "YYYY. WW. hét" with
an empty standfirst and logs at ERROR — the editor can write a better headline
by hand in `index.md`, but they cannot recover a draft that refused to build.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from anthropic import Anthropic

from src.draft_assembler import CATEGORY_ORDER, DraftEntry

logger = logging.getLogger(__name__)

SONNET_MODEL = "claude-sonnet-4-6"
PROMPT_PATH = Path(__file__).parent / "prompts" / "issue_title_prompt.md"

TITLE_MAX_CHARS = 60

TOOL_NAME = "submit_issue_title"
TITLE_TOOL = {
    "name": TOOL_NAME,
    "description": "Submit the issue headline and standfirst. Call this exactly once.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": (
                    "Hungarian issue headline, sentence case, max 60 characters. "
                    "Names two concrete things from the selected articles. No colon "
                    "subtitle, no week number, no clickbait."
                ),
            },
            "standfirst": {
                "type": "string",
                "description": (
                    "One Hungarian sentence, 120-180 characters, expanding the title "
                    "with specifics rather than restating it."
                ),
            },
        },
        "required": ["title", "standfirst"],
    },
}


@dataclass(frozen=True)
class IssueTitle:
    title: str
    standfirst: str
    #: True when generation failed and the caller is looking at the fallback.
    is_fallback: bool = False


def fallback_for(year: int, week: int) -> IssueTitle:
    return IssueTitle(title=f"{year}. {week}. hét", standfirst="", is_fallback=True)


class SonnetIssueTitler:
    def __init__(self, api_key: str | None = None) -> None:
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set — put it in .env (see .env.example)"
            )
        self.client = Anthropic(api_key=api_key)
        self.system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    def generate(self, entries: list[DraftEntry], *, year: int, week: int) -> IssueTitle:
        """Return the headline for this issue. Never raises."""
        if not entries:
            logger.error("issue title: no entries to summarise — using fallback")
            return fallback_for(year, week)

        try:
            response = self.client.messages.create(
                model=SONNET_MODEL,
                max_tokens=500,
                system=[
                    {
                        "type": "text",
                        "text": self.system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    },
                ],
                tools=[TITLE_TOOL],
                tool_choice={"type": "tool", "name": TOOL_NAME},
                messages=[{"role": "user", "content": _format_user_message(entries)}],
            )
        except Exception as e:
            logger.error(
                "ISSUE TITLE FAILED (%s: %s) — falling back to '%s. %s. hét'. "
                "Write a headline by hand in index.md.",
                type(e).__name__, e, year, week,
            )
            return fallback_for(year, week)

        usage = response.usage
        logger.debug(
            "issue title usage: input=%d cache_read=%d output=%d",
            usage.input_tokens,
            getattr(usage, "cache_read_input_tokens", 0) or 0,
            usage.output_tokens,
        )

        tool_block = next(
            (b for b in response.content if getattr(b, "type", None) == "tool_use"),
            None,
        )
        if tool_block is None:
            logger.error(
                "ISSUE TITLE FAILED: Sonnet did not call the tool (stop_reason=%r) — "
                "falling back to '%s. %s. hét'.",
                response.stop_reason, year, week,
            )
            return fallback_for(year, week)

        data = tool_block.input if isinstance(tool_block.input, dict) else {}
        title = str(data.get("title") or "").strip()
        standfirst = str(data.get("standfirst") or "").strip()

        if not title:
            logger.error(
                "ISSUE TITLE FAILED: empty title in tool input %r — falling back.", data
            )
            return fallback_for(year, week)

        # Over-length is a layout problem, not a correctness one. Keep the text
        # and let the editor trim it — truncating mid-sentence would be worse.
        if len(title) > TITLE_MAX_CHARS:
            logger.warning(
                "issue title is %d chars (max %d), may wrap to three lines: %r",
                len(title), TITLE_MAX_CHARS, title,
            )
        if not standfirst:
            logger.warning("issue standfirst came back empty — the archive row will be bare")

        return IssueTitle(title=title, standfirst=standfirst)


def _format_user_message(entries: list[DraftEntry]) -> str:
    order = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    ordered = sorted(
        entries,
        key=lambda e: (order.get(e.article.category, 99), -e.article.relevance_score),
    )

    lines = [f"A szám {len(ordered)} kiválasztott cikke:", ""]
    for e in ordered:
        lines.append(f"- Cím: {e.rewrite.hu_title}")
        lines.append(f"  Kategória: {e.article.category}")
        lines.append(f"  Relevancia: {e.article.relevance_score}")
        if e.article.hu_summary:
            lines.append(f"  Összefoglaló: {e.article.hu_summary}")
        lines.append("")
    return "\n".join(lines)
