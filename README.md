# Pixelposta

Weekly Hungarian-language gaming newsletter, automated curation pipeline with human-in-the-loop editing.

See [PROJECT_BRIEF.md](PROJECT_BRIEF.md) and [NOTION_SCHEMA.md](NOTION_SCHEMA.md) for the full design.

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

**Daily collection** — RSS → dedup → Haiku pre-filter → Notion. Default age cutoff
is 14 days, default reads every source:

```bash
python -m scripts.daily_collect                          # full live run
python -m scripts.daily_collect --dry-run --max 30       # safe preview
python -m scripts.daily_collect --exclude-source RPS     # skip a source
```

**Weekly draft** — reads Status=Selected from Notion, fetches each article
in full, Sonnet rewrites it in Hungarian, assembles a Markdown draft including
the VGC release tables. Does not modify Notion (preview mode):

```bash
python -m scripts.generate_draft                          # writes drafts/draft-YYYY-MM-DD.md
```

**Release table preview** — iterate on the release picker alone without
re-running the 7-minute draft generator:

```bash
python -m scripts.preview_releases                        # for today
python -m scripts.preview_releases --today 2026-05-22     # any reference date
```

## GitHub Actions

Two workflows live in `.github/workflows/`:

- **`daily-collect.yml`** — runs every day at **06:00 UTC** (08:00 Budapest summer / 07:00 winter)
  and also on manual trigger. Pulls from RSS, runs the Haiku pre-filter, writes
  new articles to Notion.
- **`weekly-draft.yml`** — manual trigger only. Generates the weekly Markdown
  draft and uploads it as a downloadable artifact on the run page.

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
├── .github/workflows/        # daily-collect.yml, weekly-draft.yml
├── src/
│   ├── collectors/           # rss_sources.py, vgc_releases.py
│   ├── prompts/              # filter_prompt.md, translator_prompt.md, release_picker_prompt.md
│   ├── deduplicator.py       # URL dedup
│   ├── draft_assembler.py    # markdown assembly
│   ├── filter.py             # Haiku pre-filter
│   ├── models.py             # CollectedArticle / SelectedArticle / ReleaseEntry
│   ├── notion_client.py      # Articles DB read/write (2025 data-sources API)
│   ├── release_picker.py     # Haiku release table picker
│   ├── translator.py         # Sonnet HU rewrite
│   └── web_fetcher.py        # trafilatura article-body extraction
├── scripts/
│   ├── daily_collect.py      # end-to-end daily pipeline
│   ├── generate_draft.py     # weekly draft generator
│   ├── preview_releases.py   # release-table iteration helper
│   ├── smoke_collect.py
│   ├── smoke_filter.py
│   ├── smoke_notion.py
│   ├── check_notion_schema.py
│   └── debug_notion_ids.py
├── drafts/                   # gitignored — generated drafts live here
└── tests/
```

## Status

- [x] Repo skeleton + RSS collectors (8 of 10 news sources)
- [x] VGC release snapshot collector
- [x] Notion client (Articles + Issues; 2025 data-sources API)
- [x] URL deduplicator + age filter
- [x] Pre-filter (Haiku 4.5) with Hungarian prompt + tool-use structured output
- [x] Draft generator (Sonnet 4.6) with temporal awareness
- [x] Release picker (Haiku) + Markdown tables in the draft
- [x] GitHub Actions: daily collect (cron) + weekly draft (manual)
- [ ] Forbes / Bloomberg collectors (need Google News API or scraping fallback)
- [ ] Weekly sweep (Sunday: Status=New → Archived after 7 days)
- [ ] Monthly cleanup (delete Archived/Passed older than 30 days)
- [ ] Publishing lifecycle (Selected → Published, Issues row create)
