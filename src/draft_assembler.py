"""Assemble the weekly newsletter draft as Markdown.

Reads the editor's Selected articles plus the Sonnet rewrites and the
release snapshot, produces a copy-paste-ready Markdown file. Intro, outro
and images are still hand-written by the editor.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from src.models import ReleaseEntry, SelectedArticle
from src.release_picker import ReleaseSnapshot
from src.translator import RewriteResult


# Display order — categories appear in this order in the newsletter.
CATEGORY_ORDER = ["Játékhírek", "Hardware", "AI & Gaming", "Stúdió & Üzlet"]

# Magyar hónapnevek (1-12). A nominativusz formát használjuk az "X. hónap Y."
# dátumformulához: "május 19.".
_HU_MONTHS = [
    "", "január", "február", "március", "április", "május", "június",
    "július", "augusztus", "szeptember", "október", "november", "december",
]


@dataclass(frozen=True)
class DraftEntry:
    article: SelectedArticle
    rewrite: RewriteResult


def assemble_markdown(
    entries: list[DraftEntry],
    *,
    today: date,
    week_number: int | None = None,
    year: int | None = None,
    releases: ReleaseSnapshot | None = None,
) -> str:
    """Return the full Markdown draft for the issue covering `today`'s week."""
    if week_number is None:
        # ISO week — matches what the brief shows ("2026. 22. hét").
        year, week_number, _ = today.isocalendar()
    elif year is None:
        year = today.year

    by_category: dict[str, list[DraftEntry]] = defaultdict(list)
    for e in entries:
        by_category[e.article.category].append(e)

    # Within a category, sort by relevance score descending so the editor sees
    # the heaviest hitters first.
    for cat in by_category:
        by_category[cat].sort(key=lambda e: e.article.relevance_score, reverse=True)

    lines: list[str] = []
    lines.append(f"# {year}. {week_number}. hét")
    lines.append("")
    lines.append("> _[INTRO: a szerkesztő írja kézzel, 3-4 mondatos heti bevezető.]_")
    lines.append("")

    for category in CATEGORY_ORDER:
        cat_entries = by_category.get(category, [])
        if not cat_entries:
            continue
        lines.append(f"## {category}")
        lines.append("")
        for entry in cat_entries:
            lines.extend(_format_article_block(entry))
            lines.append("---")
            lines.append("")
        # Trim trailing separator inside category
        if lines and lines[-2] == "---":
            lines.pop()
            lines.pop()
        lines.append("")

    # A single combined list — the newsletter and the site both stopped
    # splitting these into current and next week.
    lines.append("## Megjelenések")
    lines.append("")
    if releases is None:
        lines.append("> _[PLACEHOLDER: release snapshot nem futott le.]_")
    else:
        lines.extend(_format_release_list([*releases.this_week, *releases.next_week]))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("> _[OUTRO: a szerkesztő írja kézzel, záró gondolatok.]_")
    lines.append("")
    lines.append("– _Pixelposta_")
    lines.append("")
    return "\n".join(lines)


def _format_release_list(releases: list[ReleaseEntry]) -> list[str]:
    if not releases:
        return ["> _Ezen a héten nincs kiemelt megjelenés._"]
    lines: list[str] = []
    for i, r in enumerate(sorted(releases, key=lambda x: x.release_date)):
        if i > 0:
            lines.append("")
        platforms = ", ".join(r.platforms)
        # Standalone line — start with capital month. `_format_hu_date` returns
        # lowercase ("július 7.") which is correct inside a sentence but reads
        # oddly on its own row.
        date_str = _format_hu_date(r.release_date).capitalize()
        lines.append(r.title)
        lines.append(f"{date_str} - {platforms}")
    return lines


def _format_hu_date(d: date) -> str:
    return f"{_HU_MONTHS[d.month]} {d.day}."


def _format_article_block(entry: DraftEntry) -> list[str]:
    a = entry.article
    r = entry.rewrite
    block: list[str] = []
    block.append(f"### {r.hu_title}")
    block.append("")
    block.append(r.hu_rewrite)
    block.append("")
    if r.hu_kiemelt_info:
        block.append(f"> ⚡ **Kiemelt info:** {r.hu_kiemelt_info}")
        block.append("")
    block.append(f"[Eredeti cikk → {a.source}]({a.url})")
    block.append("")
    return block
