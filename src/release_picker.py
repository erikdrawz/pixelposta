"""Pick the weekly newsletter's release table contents using Haiku.

Takes the raw VGC schedule text plus this/next week date ranges, asks Haiku
to filter and structure the relevant entries via a forced tool call.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from anthropic import Anthropic

from src.models import ReleaseEntry

logger = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5-20251001"
PROMPT_PATH = Path(__file__).parent / "prompts" / "release_picker_prompt.md"

TOOL_NAME = "submit_releases"
PICKER_TOOL = {
    "name": TOOL_NAME,
    "description": "Submit the curated release lists for this week and next week.",
    "input_schema": {
        "type": "object",
        "properties": {
            "this_week": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "platforms": {"type": "array", "items": {"type": "string"}},
                        "release_date": {"type": "string", "description": "YYYY-MM-DD"},
                    },
                    "required": ["title", "platforms", "release_date"],
                },
            },
            "next_week": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "platforms": {"type": "array", "items": {"type": "string"}},
                        "release_date": {"type": "string", "description": "YYYY-MM-DD"},
                    },
                    "required": ["title", "platforms", "release_date"],
                },
            },
        },
        "required": ["this_week", "next_week"],
    },
}


@dataclass(frozen=True)
class ReleaseSnapshot:
    this_week: list[ReleaseEntry]
    next_week: list[ReleaseEntry]
    this_week_range: tuple[date, date]
    next_week_range: tuple[date, date]


class ReleasePickError(ValueError):
    pass


def week_ranges_for(today: date) -> tuple[tuple[date, date], tuple[date, date]]:
    """Return ((this_week_start, this_week_end), (next_week_start, next_week_end)).

    Uses fixed 7-day windows anchored on `today` rather than ISO weeks. This
    keeps the tables sensibly populated regardless of which weekday the draft
    is generated on — running on a Friday, Saturday, or Sunday all yield a
    sane "this week" (today + 6 days) and "next week" (the 7 days after that).
    """
    this_week_start = today
    this_week_end = today + timedelta(days=6)
    next_week_start = today + timedelta(days=7)
    next_week_end = today + timedelta(days=13)
    return (this_week_start, this_week_end), (next_week_start, next_week_end)


class HaikuReleasePicker:
    def __init__(self, api_key: str | None = None) -> None:
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set — put it in .env (see .env.example)"
            )
        self.client = Anthropic(api_key=api_key)
        self.system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    def pick(self, schedule_text: str, today: date) -> ReleaseSnapshot:
        this_range, next_range = week_ranges_for(today)

        user_message = (
            f"Today: {today.isoformat()}\n"
            f"This week range: {this_range[0].isoformat()} to {this_range[1].isoformat()}\n"
            f"Next week range: {next_range[0].isoformat()} to {next_range[1].isoformat()}\n"
            f"\n"
            f"VGC release schedule:\n"
            f"{schedule_text}"
        )

        response = self.client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=2000,
            system=[
                {
                    "type": "text",
                    "text": self.system_prompt,
                    "cache_control": {"type": "ephemeral"},
                },
            ],
            tools=[PICKER_TOOL],
            tool_choice={"type": "tool", "name": TOOL_NAME},
            messages=[{"role": "user", "content": user_message}],
        )

        usage = response.usage
        logger.debug(
            "haiku release picker usage: input=%d cache_creation=%d cache_read=%d output=%d",
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
            raise ReleasePickError(
                f"Haiku did not call the tool. Stop reason: {response.stop_reason!r}"
            )

        data = tool_block.input
        logger.debug("release picker raw tool input: %r", data)
        return ReleaseSnapshot(
            this_week=_parse_releases(data.get("this_week", []), this_range),
            next_week=_parse_releases(data.get("next_week", []), next_range),
            this_week_range=this_range,
            next_week_range=next_range,
        )


def _parse_releases(items: list, window: tuple[date, date]) -> list[ReleaseEntry]:
    out: list[ReleaseEntry] = []
    win_start, win_end = window
    for item in items:
        if not isinstance(item, dict):
            logger.warning("dropping non-object release entry: %r", item)
            continue
        title = (item.get("title") or "").strip()
        platforms = [p.strip() for p in (item.get("platforms") or []) if p and p.strip()]
        date_str = (item.get("release_date") or "").strip()
        if not title or not platforms or not date_str:
            continue
        try:
            rd = date.fromisoformat(date_str)
        except ValueError:
            logger.warning("dropping release %r: bad date %r", title, date_str)
            continue
        if not (win_start <= rd <= win_end):
            # Belt-and-braces: the prompt asks Haiku to stay in-window, but if
            # something sneaks in (e.g., date drift), drop it rather than
            # mis-label the table.
            logger.warning("dropping release %r: %s outside window %s..%s", title, rd, win_start, win_end)
            continue
        out.append(ReleaseEntry(title=title, platforms=platforms, release_date=rd))
    return out
