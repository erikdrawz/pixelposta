"""Hungarian-aware slugs for article identifiers and image filenames.

The slug is the contract between the pipeline and the editor: it goes into
`index.md` as `articles[].slug`, and the editor names the article's image
`<slug>.jpg`. That means it has to survive being typed by hand and being
committed on a case-insensitive filesystem, so the output is strictly
lowercase ASCII.

`unicodedata.normalize('NFKD', ...)` handles most of this, but it leaves ő and
ű intact on some platforms because their decomposition uses a double acute
that not every normalisation path strips. They are mapped explicitly.
"""
from __future__ import annotations

import re
import unicodedata

# Explicit first, so ő/ű never depend on normalisation behaviour.
_HU_MAP = str.maketrans({
    "á": "a", "é": "e", "í": "i", "ó": "o", "ö": "o", "ő": "o",
    "ú": "u", "ü": "u", "ű": "u",
    "Á": "a", "É": "e", "Í": "i", "Ó": "o", "Ö": "o", "Ő": "o",
    "Ú": "u", "Ü": "u", "Ű": "u",
})

# Long titles make unwieldy filenames; the editor has to type these.
MAX_LENGTH = 60


def slugify(text: str, *, max_length: int = MAX_LENGTH) -> str:
    """Return a lowercase ASCII slug, truncated on a word boundary."""
    s = text.strip().lower().translate(_HU_MAP)
    # Strip any remaining diacritics (foreign game titles, borrowed names).
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.encode("ascii", "ignore").decode("ascii")

    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")

    if len(s) > max_length:
        s = s[:max_length].rsplit("-", 1)[0].strip("-") or s[:max_length].strip("-")
    return s


def unique_slugs(titles: list[str]) -> list[str]:
    """Slugify a list of titles, suffixing collisions as -2, -3, …

    Two articles in one issue can slugify identically (truncation makes this
    more likely). Collisions would silently attach the same image to both, so
    they are broken here rather than discovered by the editor later.
    """
    seen: dict[str, int] = {}
    out: list[str] = []
    for title in titles:
        base = slugify(title) or "cikk"
        count = seen.get(base, 0) + 1
        seen[base] = count
        out.append(base if count == 1 else f"{base}-{count}")
    return out
