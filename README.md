# Pixelposta

Weekly Hungarian-language gaming newsletter, automated curation pipeline with human-in-the-loop editing.

Two delivery surfaces, independent of each other so a problem with one never blocks the other:

- **Substack** (`pixelposta.substack.com`) — the newsletter, distribution
- **The website** (`pixelposta.com`) — the archive and reading surface, built from [`site/`](site/)

One repo for both, because `weekly-draft.yml` commits the generated issue file with the built-in
`GITHUB_TOKEN` — no cross-repo PAT to create, rotate, or have silently expire.

See [PROJECT_BRIEF.md](PROJECT_BRIEF.md), [NOTION_SCHEMA.md](NOTION_SCHEMA.md) and
[site/README.md](site/README.md) for the full design, and
**[STATUS.md](STATUS.md) for where things currently stand** — what is live, what
is half-finished, and what is deliberately undecided.

## Setup

Requires Python 3.12+.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:

- **`ANTHROPIC_API_KEY`** — get one at <https://console.anthropic.com>. Add a few dollars of credit under Settings → Billing (cost target for the whole project is < $25/month).
- **`NOTION_TOKEN`** — create an internal integration at <https://www.notion.so/profile/integrations>, then share both databases with that integration from inside Notion.
- **`NOTION_ARTICLES_DB_ID`** and **`NOTION_ISSUES_DB_ID`** — open each database as a page; the ID is the 32-char string in the URL before `?v=`.

## Notion setup

Create two databases manually in your workspace following the field tables in
[NOTION_SCHEMA.md](NOTION_SCHEMA.md). Then create an internal integration at
<https://www.notion.so/profile/integrations> with read/insert/update content
permissions, and share both databases with it (database page → ••• → Connections).

Put the integration token in `.env` as `NOTION_TOKEN`, and the 32-char database
IDs (from each database's URL, before `?v=`) as `NOTION_ARTICLES_DB_ID` and
`NOTION_ISSUES_DB_ID`.

## Smoke tests

**RSS collectors** — verify the 8 RSS-based sources are reachable (no Notion or API key needed):

```bash
python -m scripts.smoke_collect
```

**Notion schema** — verify your manually-created databases have the expected
field names, types, and select options:

```bash
python -m scripts.check_notion_schema
```

**Notion round trip** — insert one fake article and read it back. Leaves a row
titled `[SMOKE TEST] ...` in your Articles database for you to delete manually:

```bash
python -m scripts.smoke_notion
```

## Running the pipeline

**News collection** — RSS → dedup → Haiku pre-filter → Notion. Default age cutoff
is 7 days, default reads every source:

```bash
python -m scripts.news_collector                          # full live run
python -m scripts.news_collector --dry-run --max 30       # safe preview
python -m scripts.news_collector --exclude-source RPS     # skip a source
```

**Weekly draft** — reads Status=Selected from Notion, fetches each article
in full, Sonnet rewrites it in Hungarian, picks the VGC release tables, generates
the issue headline, and writes **two** outputs. Does not modify Notion (preview mode):

```bash
python -m scripts.generate_draft
```

| Output | Purpose |
|---|---|
| `drafts/draft-YYYY-MM-DD.md` | flat prose, paste into Substack |
| `site/src/content/issues/YYYY-WW/index.md` | structured, committed for the website |

Useful flags: `--no-site` (Substack markdown only), `--year 2026 --week 30`
(backfill a specific week), `--out PATH`, `--verbose`.

Re-running on the same week is safe. The pipeline refreshes the fields it owns
(`articles`, release tables, `date`) and preserves everything the editor writes
by hand — `intro`, `outro`, `signature`, `ajanlo`, `cover`, per-article
`imageCredit`, and `title`/`standfirst` once they have been edited. See
[`src/site_writer.py`](src/site_writer.py).

**Site writer smoke test** — exercise the content file without any API calls,
then point the Astro build at the result:

```bash
python -m scripts.smoke_site_writer            # writes a fake issue to site/
python -m scripts.smoke_site_writer --clean    # removes it again
```

**Release calendar** — refresh the year's release calendar for the website's
`/naptar/` page from GamesRadar. No API keys and no LLM calls; the page is
parsed outright. Writes `site/src/data/calendar.json`:

```bash
python -m scripts.update_calendar                  # current year
python -m scripts.update_calendar --dry-run        # parse and report only
python -m scripts.update_calendar --year 2027      # a different year
```

It refuses to write fewer than 60 dated entries and exits non-zero instead, so a
GamesRadar layout change fails loudly rather than emptying the page. Use
`--from-file PATH` to re-parse a saved copy while debugging.

**Release table preview** — iterate on the release picker alone without
re-running the 7-minute draft generator:

```bash
python -m scripts.preview_releases                        # for today
python -m scripts.preview_releases --today 2026-05-22     # any reference date
```

## GitHub Actions

Three workflows live in `.github/workflows/`:

- **`weekly-collect.yml`** — runs every Friday at **06:00 UTC** (08:00 Budapest summer / 07:00 winter;
  Thursday 23:00 PDT US west coast — captures the full Thursday US news cycle) and also on manual
  trigger. Pulls from RSS, runs the Haiku pre-filter, writes new articles to Notion.
- **`weekly-draft.yml`** — manual trigger only. Generates both outputs: uploads the
  Substack draft as a downloadable artifact on the run page, and commits the site
  content file straight to `main` (needs `permissions: contents: write`, already set).
- **`weekly-calendar.yml`** — Mondays at **05:00 UTC**, and on manual trigger.
  Refreshes the release calendar and commits `site/src/data/calendar.json`,
  which is what redeploys `/naptar/`. Deliberately away from the Friday
  collect/draft flow so a calendar commit never lands mid-publish. Needs no
  secrets — it makes no API calls.

Required GitHub Secrets (Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `ANTHROPIC_API_KEY` | from <https://console.anthropic.com> |
| `NOTION_TOKEN` | from your Notion integration page |
| `NOTION_ARTICLES_DB_ID` | from the Articles DB page URL |
| `NOTION_ISSUES_DB_ID` | from the Issues DB page URL |

## Repository layout

```
.
├── .github/workflows/        # weekly-collect.yml, weekly-draft.yml, weekly-calendar.yml
├── src/
│   ├── collectors/           # rss_sources.py, vgc_releases.py, gamesradar_releases.py
│   ├── prompts/              # filter, translator, release_picker, issue_title
│   ├── calendar_writer.py    # site/src/data/calendar.json + the short-file guard
│   ├── deduplicator.py       # URL dedup
│   ├── draft_assembler.py    # Substack markdown assembly
│   ├── filter.py             # Haiku pre-filter
│   ├── issue_title.py        # Sonnet issue headline + standfirst
│   ├── models.py             # CollectedArticle / SelectedArticle / ReleaseEntry
│   ├── notion_client.py      # Articles DB read/write (2025 data-sources API)
│   ├── release_picker.py     # Haiku release table picker
│   ├── site_writer.py        # site/src/content/issues/YYYY-WW/index.md
│   ├── slugify.py            # Hungarian-aware slugs (ő→o, ű→u)
│   ├── translator.py         # Sonnet HU rewrite
│   └── web_fetcher.py        # trafilatura article-body extraction
├── scripts/
│   ├── news_collector.py     # end-to-end collection pipeline
│   ├── generate_draft.py     # weekly draft generator (both outputs)
│   ├── update_calendar.py    # release calendar refresh (no API keys)
│   ├── preview_releases.py   # release-table iteration helper
│   ├── smoke_collect.py
│   ├── smoke_filter.py
│   ├── smoke_notion.py
│   ├── smoke_site_writer.py  # site content file, no API calls
│   ├── check_notion_schema.py
│   └── debug_notion_ids.py
├── site/                     # Astro website — Cloudflare Pages builds from here
├── drafts/                   # gitignored — generated drafts live here
└── tests/
```

The brief calls the Python half `pipeline/`; it stayed `src/` so the rename would not
churn every import and both workflows for no behavioural gain.

## Sources behind a bot challenge

**NintendoLife, VGC and DigitalFoundry** sit behind Cloudflare's JavaScript bot
challenge. Their article pages return `403` with `cf-mitigated: challenge` — no
combination of headers passes it, by design. This started around 2026-08-06;
those three yielded 6 articles in week 31 and 0 in week 32.

Key facts, each established by measurement rather than assumption:

- **It is intermittent, not permanent.** A given IP gets through sometimes and
  not others. Week 32's second run fetched all three sources in full. Do not
  conclude a source is "dead" from one failed request — that mistake was made
  twice while diagnosing this.
- **Their RSS feeds still work.** Collection is unaffected; only the draft-time
  page fetch fails.
- **The fallback:** `RSS summary` is stored in Notion at collect time, and
  `generate_draft.py` rewrites from it when the page is blocked, above
  `MIN_FALLBACK_CHARS` (350). Below that the article is dropped rather than
  handed to Sonnet to pad — NintendoLife blurbs run ~540 chars and work; VGC
  runs ~78 and cannot.
- **Do not try to defeat the challenge.** Feeds are the publishers' own
  syndication channel and the legitimate route.

The VGC release-schedule page is behind the same challenge, so `Megjelenések`
is empty whenever it fires.

**GamesRadar's release-dates page is the replacement, and the parser now
exists** — `src/collectors/gamesradar_releases.py`, built for the website's
`/naptar/` calendar and covered by `tests/test_gamesradar.py`. It is reachable
with ordinary browser headers, cleanly structured (month `<h3>`s over `<li>`
entries), and parsed with BeautifulSoup, so it needs no AI call at all.

The weekly `Megjelenések` table has **not** been moved over to it yet — that
means changing `generate_draft.py` and retiring the Haiku release picker, and it
was kept out of the calendar's change on purpose. See STATUS.md item 2.

One thing to know if you touch the parser: the source is inconsistent in ways
that are easy to reintroduce a bug around. Most entries separate title from date
with an en dash, but roughly thirty use a plain hyphen, a few omit the space on
one side, and one has no separator at all. Several titles *contain* a hyphen
("Little Nightmares 3 - The Backstage"), so the parser anchors on the date at
the end of the line rather than splitting on the separator. There are also two
platform typos in the live data (`XBX`, `XO`) that are mapped rather than
reported.

## Status

- [x] Repo skeleton + RSS collectors (8 of 10 news sources)
- [x] VGC release snapshot collector
- [x] Notion client (Articles + Issues; 2025 data-sources API)
- [x] URL deduplicator + age filter
- [x] Pre-filter (Haiku 4.5) with Hungarian prompt + tool-use structured output
- [x] Draft generator (Sonnet 4.6) with temporal awareness
- [x] Release picker (Haiku) + Markdown tables in the draft
- [x] GitHub Actions: daily collect (cron) + weekly draft (manual)
- [x] Issue title + standfirst generator (Sonnet 4.6, loud fallback)
- [x] Site content writer with Hungarian-aware slugs and editor-field preservation
- [x] Astro website in `site/` — landing, issue pages, three rovatok, light/dark
- [x] Cloudflare deploy + `pixelposta.com` DNS (Workers, not Pages — see `site/README.md`)
- [x] Release calendar at `/naptar/` — GamesRadar parser, weekly refresh, no LLM call
- [ ] OpenCritic scores on the calendar (see STATUS.md item 4)
- [ ] Move the weekly `Megjelenések` table onto the GamesRadar parser
- [ ] Backfill the five issues already published on Patreon
- [ ] Forbes / Bloomberg collectors (need Google News API or scraping fallback)
- [ ] Weekly sweep (Sunday: Status=New → Archived after 7 days)
- [ ] Monthly cleanup (delete Archived/Passed older than 30 days)
- [ ] Publishing lifecycle (Selected → Published, Issues row create)
