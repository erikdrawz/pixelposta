# Pixelposta

Weekly Hungarian-language gaming newsletter, automated curation pipeline with human-in-the-loop editing.

Two delivery surfaces, independent of each other so a problem with one never blocks the other:

- **Substack** (`pixelposta.substack.com`) — the newsletter, distribution
- **The website** (`pixelposta.com`) — the archive and reading surface, built from [`site/`](site/)

One repo for both, because `weekly-draft.yml` commits the generated issue file with the built-in
`GITHUB_TOKEN` — no cross-repo PAT to create, rotate, or have silently expire.

See [PROJECT_BRIEF.md](PROJECT_BRIEF.md), [NOTION_SCHEMA.md](NOTION_SCHEMA.md) and
[site/README.md](site/README.md) for the full design.

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

**Release table preview** — iterate on the release picker alone without
re-running the 7-minute draft generator:

```bash
python -m scripts.preview_releases                        # for today
python -m scripts.preview_releases --today 2026-05-22     # any reference date
```

## GitHub Actions

Two workflows live in `.github/workflows/`:

- **`weekly-collect.yml`** — runs every Friday at **06:00 UTC** (08:00 Budapest summer / 07:00 winter;
  Thursday 23:00 PDT US west coast — captures the full Thursday US news cycle) and also on manual
  trigger. Pulls from RSS, runs the Haiku pre-filter, writes new articles to Notion.
- **`weekly-draft.yml`** — manual trigger only. Generates both outputs: uploads the
  Substack draft as a downloadable artifact on the run page, and commits the site
  content file straight to `main` (needs `permissions: contents: write`, already set).

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
├── .github/workflows/        # weekly-collect.yml, weekly-draft.yml
├── src/
│   ├── collectors/           # rss_sources.py, vgc_releases.py
│   ├── prompts/              # filter, translator, release_picker, issue_title
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
- [ ] Cloudflare Pages connected + `pixelposta.com` DNS
- [ ] Backfill the five issues already published on Patreon
- [ ] Forbes / Bloomberg collectors (need Google News API or scraping fallback)
- [ ] Weekly sweep (Sunday: Status=New → Archived after 7 days)
- [ ] Monthly cleanup (delete Archived/Passed older than 30 days)
- [ ] Publishing lifecycle (Selected → Published, Issues row create)
