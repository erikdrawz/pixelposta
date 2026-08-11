# Where things stand

Working notes for picking the project back up. Last updated 2026-08-10.

For design and architecture see [PROJECT_BRIEF.md](PROJECT_BRIEF.md),
[NOTION_SCHEMA.md](NOTION_SCHEMA.md), [README.md](README.md) and
[site/README.md](site/README.md). This file is only the *current state* —
what is live, what is half-finished, and what is deliberately undecided.

## Live

- **pixelposta.com** — Cloudflare Workers, deploys on push to `main`
- **Week 32 is the first real issue on the site.** Weeks 29, 30 and 2025-52 are
  samples left `draft: true`; week 31 was backfilled by hand from the e-mail
  edition
- Collection, drafting, sitemap, structured data and the reader-facing skins all
  working end to end
- **`/naptar/` — the year's release calendar**, parsed from GamesRadar and
  refreshed every Monday by `weekly-calendar.yml`. 180 dated 2026 titles plus 58
  confirmed-for-the-year without a date. No API keys and no LLM call: the page
  is parsed outright, so a refresh costs nothing
- **The nav collapses into a hamburger below 560px.** The skin picker stays
  outside it and sheds its label — see the nav section in `site/README.md`

## Half-finished, in rough priority order

**1. `scripts/check_issue.py` — not built.** Agreed in principle, deferred.
Would validate a hand-edited issue: YAML parses, `cover:` matches whether
`cover.jpg` exists, every `ajanlo` appid has its image, no orphaned image files,
no duplicate slugs, required fields present. Motivation: hand-edits broke the
build **twice in one session**, both times discovered from a failed Cloudflare
deploy rather than locally. See the traps section in `site/README.md`.

Related idea, not done: have the pipeline write `cover: ./cover.jpg` already
active and let the validator report the missing file, inverting that failure
from silent to loud.

**2. The weekly release table still depends on a blocked page.** See the
bot-challenge section in `README.md`. The GamesRadar parser this needs now
**exists** — `src/collectors/gamesradar_releases.py`, built for the calendar and
covered by `tests/test_gamesradar.py`. What is left is rewiring
`generate_draft.py` to pick the weekly table from it instead of from the VGC
text via Haiku, which would also drop an LLM call from the weekly run. Kept
separate deliberately: the calendar was worth shipping without changing the
newsletter pipeline in the same week.

**2b. `/info/` is a shell.** `site/src/pages/info.astro` has the structure and
TODOs where the Hungarian copy goes. It is not linked and not in the sitemap.
Publishing it is two lines: uncomment the `Infó` entry in `LINKS` in
`components/Nav.astro`, and drop the `/info/` clause from the sitemap filter in
`astro.config.mjs`.

**3. Filter output has cross-language artifacts.** Haiku occasionally drops
Russian, German or French words into the Hungarian `HU summary` and
`Filter reasoning` — e.g. `официален`, `entwickelésen`, `malgré`. These are what
the editor reads while curating, so it is a real quality-of-life issue. Likely a
small addition to `src/prompts/filter_prompt.md`. Not attempted.

**4. OpenCritic scores on the calendar.** Agreed as the calendar's second pass,
not started. `calendar.json` already carries `score` and `openCriticId` as
`null` on every dated entry, so this is a data refresh rather than a file
migration. The API is RapidAPI-gated: the free tier allows 25 *searches* and 200
requests a day, which only works if the title→id mapping is cached in the repo
and never re-searched. Two known snags — GamesRadar writes `GTA 6` where
OpenCritic has `Grand Theft Auto VI`, so expect a hand-maintained override file;
and a game three days old has too few reviews to show a meaningful score.
Confirm their attribution requirements before it goes live.

**5. Backfill.** Four more Patreon issues to bring over. Week 31 still has
inferred categories (the e-mail edition has no category headings) and no images.

## Deliberately undecided

**The hidden-issue-title trial.** Issue titles are currently switched off
everywhere on screen — landing hero, archive rows, prev-issue block and the
issue masthead — leaving the cover and standfirst to carry it. Metadata
(`<title>`, Open Graph, JSON-LD) still carries the title, and a
`.visually-hidden` `<h1>` keeps each page's heading structure valid.

Find every spot with `grep -rn "TRIAL:" site/src`. Reverting is uncommenting
four lines and deleting the hidden headings.

Open question: whether the archive list holds up without headlines once there
are more rows. With five issues it is not yet a fair test.

## Conventions that are easy to get wrong

- **Issue `date` is the Saturday of the ISO week** — `date.fromisocalendar(y, w, 6)`
- **Dates are parsed as strings, never `Date`** in the site — `new Date('2026-07-25')`
  is UTC midnight and renders as the 24th west of Greenwich
- **`[hidden]` is forced with `!important`** in `global.css`; rovat panels and
  archive rows depend on it
- **Release `date` values are display strings** (`"08.14"`) and must never be
  sorted as text — the pipeline sorts by real dates before formatting
- **Kiemelt is unused.** The editor does not use the feature; the component and
  schema field remain but nothing populates them
- **The calendar's platform labels are deliberately shorter than the
  newsletter's** — `Switch 2`, not `Nintendo Switch 2`. Two hundred rows cannot
  carry the long form without wrapping. `PLATFORM_LABELS` in the collector owns
  that mapping; `src/prompts/release_picker_prompt.md` owns the newsletter's
- **`update_calendar.py` refuses to write a short file.** Under 60 dated entries
  it exits non-zero and leaves the old `calendar.json` in place, so a GamesRadar
  layout change fails the Action instead of emptying the page
- **The site has no `intro`** — the newsletter opens with one, the site does not

## Editor's working preferences

- Prefers fixing the existing process before reaching for a new tool
- Wants to be told plainly when a change of ours caused a problem, rather than
  having it argued away — and was right to push on that
- Owns the Hungarian copy; title and standfirst are editorial calls, not ours
