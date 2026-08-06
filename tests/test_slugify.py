from src.slugify import slugify, unique_slugs


def test_hungarian_vowels_become_ascii():
    # ő and ű are the ones that survive naive normalisation, so they matter most.
    assert slugify("Őrült űrhajó és tükörfúrógép") == "orult-urhajo-es-tukorfurogep"


def test_all_accented_vowels():
    assert slugify("áéíóöőúüű ÁÉÍÓÖŐÚÜŰ") == "aeiooouuu-aeiooouuu"


def test_punctuation_and_case():
    assert slugify("A Bethesda megerősítette: jön a Fallout 5!") == (
        "a-bethesda-megerositette-jon-a-fallout-5"
    )


def test_truncates_on_a_word_boundary():
    slug = slugify("Megjelent a Scarlet Deer Inn szláv népmese platformer hímzett karakterekkel")
    assert len(slug) <= 60
    assert not slug.endswith("-")
    # Truncation must not leave a half word.
    assert slug == "megjelent-a-scarlet-deer-inn-szlav-nepmese-platformer"


def test_single_overlong_word_is_still_truncated():
    slug = slugify("a" * 100)
    assert len(slug) <= 60


def test_empty_input():
    assert slugify("!!!") == ""


def test_unique_slugs_suffixes_collisions():
    # These differ only past the truncation point.
    titles = [
        "Új Steam Deck firmware érkezett a régebbi modellekre is, mérésekkel",
        "Új Steam Deck firmware érkezett a régebbi modellekre is, videóval",
    ]
    slugs = unique_slugs(titles)
    assert slugs[0] != slugs[1]
    assert slugs[1].endswith("-2")


def test_unique_slugs_handles_unsluggable_titles():
    assert unique_slugs(["???", "!!!"]) == ["cikk", "cikk-2"]
