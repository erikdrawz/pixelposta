# Notion schema

Two databases manage the entire newsletter workflow: **Articles** (the main work surface) and **Issues** (weekly publication records).

## Database 1: Articles

The central pool. Every article ever collected lives here, with status driving its lifecycle.

### Fields

| Field name | Type | Purpose | Set by |
|---|---|---|---|
| `Title` | Title | Original article title (English) | Collector |
| `Source` | Select | Source name — see options below | Collector |
| `URL` | URL | Original article URL (used for dedup) | Collector |
| `Published date` | Date | When article was published at source | Collector |
| `Collected date` | Date | When system ingested it (used for sweeps) | Collector |
| `Category` | Select | Játékhírek / Hardware / AI & Gaming / Stúdió & Üzlet | Pre-filter (Haiku) |
| `Relevance score` | Number | 1-5 relevance rating | Pre-filter (Haiku) |
| `HU summary` | Text | 2-sentence Hungarian summary for quick scanning | Pre-filter (Haiku) |
| `RSS summary` | Text | Original feed blurb, kept as a fallback when the article page is behind a bot challenge at draft time | Collector |
| `Status` | Select | New / Selected / Published / Passed / Archived | Editor + system |
| `Issue` | Relation → Issues | Which issue this went into (set when Published) | Draft generator |
| `Highlighted` | Checkbox | Editor flag: should get "Kiemelt info" callout | Editor |
| `Full HU translation` | Text | Full 90-120 word Hungarian rewrite | Draft generator (Sonnet) |
| `Kiemelt info HU` | Text | The 1-2 sentence callout content (only when Highlighted) | Draft generator (Sonnet) |
| `Filter reasoning` | Text | Brief note from Haiku on why this score/category — for editor visibility | Pre-filter (Haiku) |

### Source options

- `RPS` (Rock Paper Shotgun)
- `NintendoLife`
- `VGC` (VideoGamesChronicle)
- `GameDiscover`
- `TheGameBusiness`
- `Forbes`
- `Bloomberg`
- `DigitalFoundry`
- `TheVerge`
- `ThisWeekInVideoGames`
- `WindowsCentral`

### Category options

- `Játékhírek`
- `Hardware`
- `AI & Gaming`
- `Stúdió & Üzlet`

(`Megjelenések` is handled in a separate flow — not stored in Articles. See section below.)

### Status options and lifecycle

| Status | Meaning | Set by | Transitions to |
|---|---|---|---|
| `New` | Just collected, in active pool, awaiting curation | Collector | `Selected` (editor) / `Passed` (editor) / `Archived` (weekly sweep) |
| `Selected` | Editor marked for inclusion in next issue | Editor (Thursday) | `Published` (after draft generation) |
| `Published` | Went out in an issue. `Issue` relation is set. | Draft generator | Terminal (never deleted) |
| `Passed` | Editor reviewed and actively skipped | Editor | `Archived` (monthly, after 14+ days) → deleted (after 30+ days) |
| `Archived` | Aged out without editor action | Weekly sweep | Deleted (monthly, after 30+ days) |

The dual `Passed` / `Archived` distinction: kept intentionally to allow future analysis of editor patterns (e.g., what does the editor consistently skip?). May be consolidated later if it adds no value.

## Database 2: Issues

One row per weekly newsletter. Small, simple, mostly for history browsing.

### Fields

| Field name | Type | Purpose | Set by |
|---|---|---|---|
| `Issue name` | Title | e.g., "2026. 22. hét" | Draft generator |
| `Year` | Number | 2026 | Draft generator |
| `Week number` | Number | 22 | Draft generator |
| `Publish date` | Date | When it went out on Substack | Editor (manual) |
| `Substack URL` | URL | Link to the published newsletter | Editor (manual) |
| `Articles` | Relation → Articles | All articles included (typically 15-20) | Draft generator |
| `Releases this week` | Text | Snapshot table for current week | Draft generator |
| `Releases next week` | Text | Snapshot table for next week | Draft generator |
| `Status` | Select | Draft / Published | Editor |
| `Notes` | Text | Editor notes about this issue | Editor (optional) |

Note: intro and outro are **not stored here** — the editor writes them directly in Substack.

## Notion views

All views are on the Articles database unless noted otherwise.

### 1. 🎯 Active pool (default view)

Thursday curation surface.

- **Filter**: `Status = New OR Status = Selected` AND `Collected date` within last 7 days AND `Relevance score >= 3`
- **Group by**: `Category`
- **Sort**: `Relevance score` descending, then `Published date` descending
- **Visible properties**: Title, Source, HU summary, Relevance score, Highlighted, Status

### 2. ✅ This week's selection

Review what's currently selected, check category balance.

- **Filter**: `Status = Selected`
- **Group by**: `Category`
- **Sort**: `Relevance score` descending
- **Visible properties**: Title, Source, HU summary, Highlighted

### 3. 📦 Recently passed

Articles the editor skipped — kept in case a topic blows up later.

- **Filter**: `Status = Passed` AND `Collected date` within last 14 days
- **Sort**: `Collected date` descending
- **Visible properties**: Title, Source, Category, HU summary

### 4. 📚 History (on Issues database)

Browse past issues.

- **Layout**: Gallery view, sorted by `Publish date` descending
- **Card preview**: Issue name, Publish date, article count, Substack URL

### 5. 🔍 All articles (search/admin)

Catch-all view.

- **Filter**: none
- **Sort**: `Collected date` descending
- **Use case**: full-text search, debugging

### 6. 🗑️ Cleanup candidates (admin)

Visible only when needed.

- **Filter**: `(Status = Archived OR Status = Passed)` AND `Collected date` older than 30 days
- **Sort**: `Collected date` ascending
- **Use case**: monthly cleanup check (system auto-deletes these anyway)

## Automated lifecycle rules

These run via GitHub Actions workflows.

### Daily collection (every morning 8:00 Budapest)

- Fetch new articles from all sources
- Deduplicate against existing URLs in Articles
- For each new article, run pre-filter (Haiku):
  - Assign `Category` (or drop if it doesn't fit any)
  - Assign `Relevance score` (1-5)
  - Generate `HU summary` (2 sentences)
  - Generate `Filter reasoning` (brief note)
- Write to Articles with `Status = New`

### Weekly draft generation (manual trigger, Friday)

- Read all articles where `Status = Selected`
- Fetch full text for each (web fetch on URL)
- For each, run Sonnet rewrite:
  - Generate `Full HU translation` (90-120 words, newsletter voice)
  - If `Highlighted = true`, generate `Kiemelt info HU` (1-2 sentence callout)
- Create new Issues row, link selected articles
- Fetch VGC release schedule, generate `Releases this week` + `Releases next week` tables
- Update Articles: `Status = Selected` → `Status = Published`, set `Issue` relation
- Output a copy-paste-ready Markdown draft (intro and outro are placeholders the editor fills in)

### Weekly sweep (Sunday night 23:00 Budapest)

- Find all articles where `Status = New` AND `Collected date` older than 7 days
- Update them to `Status = Archived`
- This clears stale items from the active pool, keeping the Thursday curation surface focused on the current week.

### Monthly cleanup (1st of each month, 03:00 Budapest)

- Find all articles where `(Status = Archived OR Status = Passed)` AND `Collected date` older than 30 days
- **Hard delete** them from Notion
- `Status = Published` articles are NEVER deleted — they are the permanent history.

## Release snapshot handling

The VGC release schedule is fetched separately from the article flow.

- **When**: Thursday morning (before editor curation), as part of daily collection on Thursdays specifically
- **Where stored**: Not in Articles. Either ephemeral (regenerated each Friday for the draft) or in a small `Releases` cache table — implementation detail, decide during build.
- **Processing**: From the raw schedule, select top 8-10 releases per week based on:
  - Major publisher backing
  - Recognizable IP
  - Cross-platform availability
  - Notable indie titles when prominent
- **Output format**: Markdown tables with columns Title / Platform / Date — embedded directly in the draft.

## Hungarian language conventions

For all fields containing Hungarian content (`HU summary`, `Full HU translation`, `Kiemelt info HU`):

- Game titles stay in original language (e.g., "The Last of Us Part III", not "Az utolsó belőlünk")
- Studio and publisher names stay in original ("Bethesda", "FromSoftware")
- Platform names stay in original ("PlayStation 5", "Xbox Series X", "Steam Deck")
- Hungarian-language standard tech terms used naturally ("játékfejlesztő", "kiadó", "konzol", "kontroller")
- Sentence case for titles, never Title Case
