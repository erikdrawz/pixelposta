from datetime import date

import pytest
import yaml

from src.draft_assembler import DraftEntry
from src.issue_title import IssueTitle
from src.models import ReleaseEntry, SelectedArticle
from src.release_picker import ReleaseSnapshot
from src.site_writer import build_frontmatter, read_existing, saturday_of, write_issue
from src.translator import RewriteResult


def make_entry(hu_title, category="Játékhírek", score=4, kiemelt=None, source="VGC"):
    return DraftEntry(
        article=SelectedArticle(
            page_id="p", title="en title", source=source,
            url="https://example.com/a", published_at=date(2026, 7, 20),
            category=category, relevance_score=score,
            hu_summary="Összefoglaló.", filter_reasoning="", highlighted=kiemelt is not None,
        ),
        rewrite=RewriteResult(hu_title=hu_title, hu_rewrite="Törzsszöveg.", hu_kiemelt_info=kiemelt),
    )


def make_releases():
    return ReleaseSnapshot(
        this_week=[
            ReleaseEntry("Later Game", ["PlayStation 5"], date(2026, 7, 30)),
            ReleaseEntry("Earlier Game", ["PC", "Xbox Series X"], date(2026, 7, 28)),
        ],
        next_week=[ReleaseEntry("Next Game", ["Nintendo Switch 2"], date(2026, 8, 4))],
        this_week_range=(date(2026, 7, 27), date(2026, 8, 2)),
        next_week_range=(date(2026, 8, 3), date(2026, 8, 9)),
    )


TITLE = IssueTitle(title="Generált cím", standfirst="Generált standfirst.")


@pytest.mark.parametrize(
    "year,week,expected",
    [
        (2026, 30, date(2026, 7, 25)),
        (2026, 31, date(2026, 8, 1)),
        (2025, 52, date(2025, 12, 27)),
        # ISO week 1 can start in the previous calendar year.
        (2026, 1, date(2026, 1, 3)),
    ],
)
def test_saturday_of_iso_week(year, week, expected):
    assert saturday_of(year, week) == expected


def test_articles_are_ordered_by_category_then_score():
    entries = [
        make_entry("Hardware kicsi", category="Hardware", score=3),
        make_entry("Játékhír nagy", category="Játékhírek", score=5),
        make_entry("Hardware nagy", category="Hardware", score=5),
        make_entry("Játékhír kicsi", category="Játékhírek", score=4),
    ]
    data = build_frontmatter(entries, TITLE, year=2026, week=30)
    assert [a["title"] for a in data["articles"]] == [
        "Játékhír nagy", "Játékhír kicsi", "Hardware nagy", "Hardware kicsi",
    ]


def test_kiemelt_present_only_when_set():
    entries = [make_entry("Van kiemelt", kiemelt="Punchline."), make_entry("Nincs kiemelt")]
    data = build_frontmatter(entries, TITLE, year=2026, week=30)
    assert data["articles"][0]["kiemelt"].strip() == "Punchline."
    assert "kiemelt" not in data["articles"][1]


def test_releases_merge_into_one_date_sorted_list():
    data = build_frontmatter(
        [make_entry("Cikk")], TITLE, year=2026, week=31, releases=make_releases()
    )
    # Both windows flattened into one list, ordered by real date rather than by
    # the "MM.DD" display strings, which would sort wrongly across a year end.
    assert data["releases"] == [
        {"title": "Earlier Game", "platform": "PC, XSX", "date": "07.28"},
        {"title": "Later Game", "platform": "PS5", "date": "07.30"},
        {"title": "Next Game", "platform": "Switch 2", "date": "08.04"},
    ]
    assert "releasesThisWeek" not in data
    assert "releasesNextWeek" not in data


def test_no_releases_gives_an_empty_list():
    data = build_frontmatter([make_entry("Cikk")], TITLE, year=2026, week=30, releases=None)
    assert data["releases"] == []


def test_editor_fields_are_preserved_on_regeneration(tmp_path):
    entries = [make_entry("Első cikk"), make_entry("Második cikk")]
    write_issue(entries, TITLE, year=2026, week=30, site_root=tmp_path)

    path = tmp_path / "src" / "content" / "issues" / "2026-30" / "index.md"
    original = path.read_text(encoding="utf-8")
    edited = (
        original.replace("title: Generált cím", "title: Kézzel írt cím")
        .replace('intro: ""', "intro: |\n  Bevezető.\n")
        .replace("ajanlo: []", "ajanlo:\n- title: Outer Wilds\n  genre: X\n  appid: 1\n  description: Y\n")
    )
    # Attach a credit to the first article by slug.
    first_slug = yaml.safe_load(original.split("---", 2)[1])["articles"][0]["slug"]
    edited = edited.replace(f"- slug: {first_slug}", f"- slug: {first_slug}\n  imageCredit: 'Kép: X'")
    path.write_text(edited, encoding="utf-8")

    # Regenerate with a different generated headline and an extra article.
    write_issue(
        entries + [make_entry("Harmadik cikk")],
        IssueTitle(title="Másik generált cím", standfirst="Másik."),
        year=2026, week=30, site_root=tmp_path,
    )
    data = read_existing(path)

    assert data["title"] == "Kézzel írt cím"        # editor's headline wins
    assert data["intro"].strip() == "Bevezető."
    assert data["ajanlo"][0]["title"] == "Outer Wilds"
    assert data["articles"][0]["imageCredit"] == "Kép: X"
    assert len(data["articles"]) == 3               # machine field refreshed


def test_generated_title_used_when_file_is_new(tmp_path):
    write_issue([make_entry("Cikk")], TITLE, year=2026, week=30, site_root=tmp_path)
    data = read_existing(tmp_path / "src" / "content" / "issues" / "2026-30" / "index.md")
    assert data["title"] == "Generált cím"
    assert data["standfirst"] == "Generált standfirst."


def test_output_is_parseable_yaml_frontmatter(tmp_path):
    path = write_issue(
        [make_entry("Őrült cím ékezetekkel: ű, ő")],
        TITLE, year=2026, week=30, releases=make_releases(), site_root=tmp_path,
    )
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n") and text.rstrip().endswith("---")
    data = yaml.safe_load(text.split("---", 2)[1])
    assert data["date"] == "2026-07-25"
    assert data["articles"][0]["slug"] == "orult-cim-ekezetekkel-u-o"


def test_read_existing_on_missing_file(tmp_path):
    assert read_existing(tmp_path / "nope.md") == {}


def test_read_existing_on_garbage_falls_back(tmp_path):
    bad = tmp_path / "index.md"
    bad.write_text("---\n: : not valid yaml : :\n---\n", encoding="utf-8")
    assert read_existing(bad) == {}
