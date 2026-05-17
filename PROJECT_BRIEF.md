# Pixelposta

Automated weekly Hungarian-language gaming newsletter, built around a human-in-the-loop curation workflow.

## Project goal

Generate a weekly Hungarian-language gaming newsletter for Substack, modeled on the "Heti Vágólap" format (https://kopapirctrlx.substack.com), but with a gaming focus. The system collects news from 11 international sources daily, pre-filters with AI, lets the editor curate via Notion, then generates a publication-ready Hungarian draft.

**Target audience**: Casual Hungarian gamers — people who play games but don't follow industry minutiae.

**Editor time budget**: 1-2 hours per week total.

## Workflow

| Day | Who | Activity | Time |
|---|---|---|---|
| Mon-Thu, daily 8:00 | System | Collect new articles from 11 sources, deduplicate, pre-filter, write to Notion | Automated |
| Thursday evening | Editor | Curate in Notion: review ~50-80 pre-filtered articles, select 15-20 for the issue, mark "highlighted" ones | 30-40 min |
| Friday morning | System | Generate full Hungarian translation/rewrite for selected articles, assemble draft | Automated |
| Friday/Saturday | Editor | Write intro and outro by hand, review and edit generated content | 30-40 min |
| Friday/Saturday | Editor | Copy-paste to Substack, add images, schedule | 10-15 min |
| Sunday night | System | Sweep: unselected `New` articles become `Archived` | Automated |
| Monthly | System | Hard-delete `Archived` and `Passed` articles older than 30 days | Automated |

## Architecture

- **Hosting**: GitHub Actions (cron-scheduled for daily collection, `workflow_dispatch` for manual draft trigger)
- **Database**: Notion (curation workbench + issue history) — see `NOTION_SCHEMA.md`
- **AI models**:
  - Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) for pre-filtering (relevance scoring + 2-sentence Hungarian summary)
  - Claude Sonnet 4.6 (`claude-sonnet-4-6`) for full Hungarian rewriting of selected articles
- **Language**: Code and code comments in English; prompts and all output in Hungarian.
- **Cost target**: < $25/month total (Anthropic API + any infrastructure).

## Repository layout

```
heti-vagolap-gaming/
├── .github/
│   └── workflows/
│       ├── daily-collect.yml      # daily cron — collect + pre-filter
│       ├── weekly-draft.yml       # manual trigger — generate full draft
│       └── weekly-sweep.yml       # Sunday cron — archive untouched articles
├── src/
│   ├── collectors/                # one module per source type
│   │   ├── rss_sources.py         # RSS-based sources (most of them)
│   │   ├── vgc_releases.py        # VGC upcoming releases snapshot
│   │   └── ...
│   ├── filter.py                  # Haiku pre-filter (relevance + category + HU summary)
│   ├── translator.py              # Sonnet draft generator (full HU rewrite)
│   ├── notion_client.py           # Notion read/write
│   ├── deduplicator.py            # URL + semantic dedup
│   └── prompts/
│       ├── filter_prompt.md       # Hungarian pre-filter prompt for Haiku
│       └── translator_prompt.md   # Hungarian rewrite prompt for Sonnet
├── tests/
├── requirements.txt
├── PROJECT_BRIEF.md               # this file
├── NOTION_SCHEMA.md               # Notion database specs
└── README.md
```

## Sources (11 total)

### News sources (10 — flow into the article pool)

1. https://thisweekinvideogames.com/news/
2. https://www.videogameschronicle.com
3. https://www.nintendolife.com
4. https://newsletter.gamediscover.co
5. https://www.thegamebusiness.com
6. https://www.forbes.com/gaming/
7. https://www.bloomberg.com/latest/gaming
8. https://www.digitalfoundry.net/news
9. https://www.theverge.com/notepad-microsoft-newsletter
10. https://www.rockpapershotgun.com/news

Most expose RSS feeds; Bloomberg and Forbes may require alternative ingestion (Google News API or scraping fallback).

### Snapshot source (1 — separate treatment)

11. https://www.videogameschronicle.com/guide/upcoming-game-release-dates-schedule/

Pulled once per week (Thursday morning), filtered to ~8-10 most relevant releases for the upcoming two weeks. Stored separately from the article pool — fed directly into the draft as two tables: **Heti megjelenések** and **Jövő heti megjelenések**.

## Categories

Each article gets exactly one category from the pre-filter:

1. **Játékhírek** — game announcements, updates, esports highlights, controversies, retro gaming, new releases of mainstream titles
2. **Hardware** — gaming consoles, gaming handhelds (Steam Deck, ROG Ally, AYANEO line), retro hardware (Analogue Pocket-style devices, mini consoles), gaming-relevant PC hardware (new GPUs, game-relevant CPU benchmarks, DLSS/FSR updates), gaming-fókuszú VR/AR, gaming controllers, foldable phones with gaming relevance
3. **AI & Gaming** — AI tools in game development, AI-generated content controversies, AI use in games (NPCs, procedural generation), AI policy affecting gaming
4. **Stúdió & Üzlet** — studio acquisitions, closures, layoffs (especially when known IP is involved), publisher strategy shifts, executive changes that materially affect game development
5. **Megjelenések** — release snapshot data (handled separately, see above)

Articles that don't fit are filtered out, not assigned to a fallback category.

## Pre-filter criteria

### Include

- Game announcements, release news, updates for known titles
- Hardware launches relevant to gaming (see Hardware category above)
- Industry events: layoffs at known studios, acquisitions, closures
- Retro gaming: handheld clones, mini-consoles, classic remasters, emulation legal news
- Innovative mobile devices when relevant to gaming (gaming handhelds, foldables with gaming angle)
- AI in gaming: dev tools, controversies, policy
- Esports highlights (major tournaments only, not weekly match results)
- Mature-rated (M / 17+) mainstream games are fine

### Exclude

- Adult-only (AO / 18+) game content, explicit sexual content, pornographic gaming news
- Pure financial analysis (stock prices, quarterly earnings without product implication)
- B2B SaaS tools for developers
- Marketing industry trends without direct game relevance
- Non-gaming PC hardware (enterprise, general productivity components, non-gaming monitors)
- Generic mobile phone news without gaming angle
- Weekly esports match results (only major tournament outcomes qualify)
- Crypto/NFT gaming news unless tied to a major mainstream development

### Relevance scoring (1-5)

- **5** — Headline-tier news, broad gamer interest (major release, major studio event, major hardware launch)
- **4** — Strong interest for the casual gamer, clearly newsletter-worthy
- **3** — Genuine interest but borderline (could go either way)
- **2** — Niche, only relevant to specific communities
- **1** — Likely uninteresting to casual gamers

Default Notion view filters to score ≥ 3.

## Newsletter format (Heti Vágólap-style)

- **Header**: week number (e.g., "2026. 22. hét")
- **Intro**: 3-4 sentence editorial intro **written by the editor each week** — NOT AI-generated
- **Categorized news sections**: 4-5 categories, each with 2-4 articles
- **Per-article block**:
  - Title (Hungarian)
  - 90-120 word Hungarian rewrite (not a translation — full editorial rewrite in newsletter voice)
  - Optional "⚡ Kiemelt info" callout box with 1-2 sentence punchy takeaway (only when editor marks `Highlighted = true`)
  - Link to original article
- **Heti megjelenések**: small table of 8-10 releases for the current week
- **Jövő heti megjelenések**: small table of 8-10 releases for next week
- **Outro**: closing thoughts **written by the editor each week** — NOT AI-generated
- **Signature**: editor's name

## Tone

- Friendly, direct, conversational ("vágjunk is bele", "könyvjelzőre érdemes")
- Technically accurate but accessible — no jargon dump
- Hungarian, written for a Hungarian audience (don't over-translate English gaming terminology; "Steam Deck" stays "Steam Deck")
- Not sensationalized; avoid clickbait phrasing in rewrites

## Operational principles

- **Human-in-the-loop is non-negotiable.** AI never publishes directly. Every issue passes through editor review.
- **Fail loud, not silent.** If a source breaks or the API errors, a GitHub Action notification is fine, but the system never silently drops articles.
- **Idempotent runs.** Re-running daily collection on the same day should not create duplicates.
- **Logs over magic.** Every AI decision (relevance score, category) is stored in Notion alongside the article, so editor can see why something was scored a certain way.
