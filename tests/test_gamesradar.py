"""Parse checks for the GamesRadar release-schedule collector.

Runs against a trimmed copy of the live page (`tests/fixtures/gamesradar.html`)
so CI never touches the network. The fixture keeps the headings and list items
verbatim and stubs out the images; regenerate it from a fresh download if the
page's structure changes.

Most of these cases are transcribed from real irregularities in the live page,
not invented — the source mixes en dashes with hyphens, drops separators and
commas, and contains a couple of platform typos.
"""
from datetime import date
from pathlib import Path

import pytest

from src.calendar_writer import CalendarTooSmallError, build_payload
from src.collectors.gamesradar_releases import (
    entries_for_year,
    parse_entry,
    parse_platforms,
    parse_release_page,
)

FIXTURE = Path(__file__).parent / "fixtures" / "gamesradar.html"

# Recorded from the fixture. They are assertions about the *parser*, not about
# GamesRadar's editorial choices: if the fixture is refreshed these move, but a
# sudden drop means the parser stopped understanding the markup.
EXPECTED_DATED_2026 = 180
EXPECTED_TBC_2026 = 58


@pytest.fixture(scope="module")
def entries():
    return parse_release_page(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_yields_every_month_of_the_year(entries):
    dated, _ = entries_for_year(entries, 2026)
    months = {e.release_date.month for e in dated}
    assert months == set(range(1, 13))


def test_fixture_entry_counts(entries):
    dated, tbc = entries_for_year(entries, 2026)
    assert len(dated) == EXPECTED_DATED_2026
    assert len(tbc) == EXPECTED_TBC_2026


def test_dated_entries_are_sorted_by_real_date(entries):
    dated, _ = entries_for_year(entries, 2026)
    assert dated == sorted(dated, key=lambda e: (e.release_date, e.title.lower()))


def test_tbc_entries_have_a_year_but_no_date(entries):
    _, tbc = entries_for_year(entries, 2026)
    assert tbc, "expected some TBC 2026 entries"
    assert all(e.release_date is None and e.year == 2026 for e in tbc)


def test_undated_section_without_a_year_is_dropped(entries):
    """The page's final bare "TBC" block has no year to file entries under."""
    titles = {e.title for e in entries}
    assert "The Elder Scrolls 6" not in titles  # lives under plain "TBC"
    assert "Witchbrook" in titles  # lives under "TBC 2026"


def test_a_later_year_is_kept_separate(entries):
    dated_2027, _ = entries_for_year(entries, 2027)
    titles = {e.title for e in dated_2027}
    assert "Stranger than Heaven" in titles
    assert all(e.release_date.year == 2027 for e in dated_2027)


# --------------------------------------------------------------------------
# Line-level parsing. Each of these is a real line from the page.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "line,expected_title,expected_date",
    [
        # The ordinary case: en dash, spaces both sides.
        ("Code Vein 2 (PC, XSX, PS5) – January 30", "Code Vein 2", date(2026, 1, 30)),
        # Plain hyphen instead of an en dash — roughly thirty entries do this.
        ("Killer Inn (PC) - February 12", "Killer Inn", date(2026, 2, 12)),
        # No space before the dash.
        ("Heroes of Might and Magic: Olden Era (PC)– April 30",
         "Heroes of Might and Magic: Olden Era", date(2026, 4, 30)),
        # A hyphen inside the title must not be mistaken for the separator.
        ("Little Nightmares 3 - The Backstage (PC, NS2, NS) – June 11",
         "Little Nightmares 3 - The Backstage", date(2026, 6, 11)),
        ("Human Fall Flat - Nintendo Switch 2 Edition (NS2) – March 19",
         "Human Fall Flat - Nintendo Switch 2 Edition", date(2026, 3, 19)),
        # An explicit year on the entry overrides the heading's.
        ("Stranger than Heaven (PC, PS5, XSX) – January 15, 2027",
         "Stranger than Heaven", date(2027, 1, 15)),
    ],
)
def test_dated_lines(line, expected_title, expected_date):
    entry = parse_entry(line, heading_year=2026)
    assert entry is not None
    assert entry.title == expected_title
    assert entry.release_date == expected_date


@pytest.mark.parametrize(
    "line,expected_title",
    [
        # No space after the dash.
        ("Aniimo (PC, XSX) –TBC 2026", "Aniimo"),
        # No separator at all.
        ("Empulse (PS5) TBC 2026", "Empulse"),
        # No parenthesised platform list at all.
        ("The Witcher 3: Songs of the Past expansion – TBC 2026",
         "The Witcher 3: Songs of the Past expansion"),
    ],
)
def test_undated_lines(line, expected_title):
    entry = parse_entry(line, heading_year=2026)
    assert entry is not None
    assert entry.title == expected_title
    assert entry.release_date is None
    assert entry.year == 2026


def test_early_access_note_is_captured_and_stripped():
    entry = parse_entry("Slay the Spire 2 (PC) – March 5 [Early Access]", 2026)
    assert entry.title == "Slay the Spire 2"
    assert entry.release_date == date(2026, 3, 5)
    assert entry.early_access is True


def test_line_without_a_date_is_skipped():
    assert parse_entry("Some Game (PC)", 2026) is None


def test_bare_tbc_without_any_year_is_skipped():
    assert parse_entry("The Elder Scrolls 6 (PC, XSX) – TBC", None) is None


# --------------------------------------------------------------------------
# Platforms
# --------------------------------------------------------------------------

def test_abbreviations_map_to_short_labels():
    assert parse_platforms("PC, XSX, PS5, NS2, NS, PS4, XBO") == [
        "PC", "Xbox", "PS5", "Switch 2", "Switch", "PS4", "Xbox One",
    ]


def test_source_typos_are_mapped():
    """XBX and XO are the source's typos for XSX and XBO."""
    assert parse_platforms("XBX, PS5") == ["Xbox", "PS5"]
    assert parse_platforms("PC, XSX, XO, NS") == ["PC", "Xbox", "Xbox One", "Switch"]


def test_missing_comma_between_platforms():
    """"(PC, PS5, XSX NS2)" — a dropped comma must not swallow a platform."""
    assert parse_platforms("PC, PS5, XSX NS2") == ["PC", "PS5", "Xbox", "Switch 2"]


def test_placeholder_platform_is_dropped():
    assert parse_platforms("TBC") == []


def test_unknown_platform_is_kept_verbatim():
    """A new console should look odd on the page, not silently vanish."""
    assert parse_platforms("PC, PS6") == ["PC", "PS6"]


def test_duplicate_platforms_are_collapsed():
    assert parse_platforms("PC, XSX, XBX") == ["PC", "Xbox"]


# --------------------------------------------------------------------------
# The write guard
# --------------------------------------------------------------------------

def test_payload_shape(entries):
    payload = build_payload(entries, 2026, generated=date(2026, 8, 10))
    assert payload["year"] == 2026
    assert payload["generated"] == "2026-08-10"
    assert len(payload["dated"]) == EXPECTED_DATED_2026

    first = payload["dated"][0]
    assert set(first) == {"title", "platforms", "earlyAccess", "date", "score", "openCriticId"}
    assert first["date"] == "2026-01-12"
    # Reserved for the OpenCritic pass — present from the start so adding
    # scores never needs a file migration.
    assert first["score"] is None

    assert set(payload["tbc"][0]) == {"title", "platforms", "earlyAccess"}


def test_guard_rejects_a_truncated_parse(entries):
    """A broken parse must fail loudly rather than blank the page."""
    with pytest.raises(CalendarTooSmallError, match="markup has probably changed"):
        build_payload(entries[:5], 2026)


def test_guard_does_not_fire_on_a_healthy_parse(entries):
    build_payload(entries, 2026)  # must not raise
