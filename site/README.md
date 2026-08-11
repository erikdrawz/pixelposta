# Pixelposta — site

The archive and reading surface for the newsletter. Astro, static output, no
framework. An issue is one page; articles are blocks within it, not
destinations.

The site and the Substack newsletter are independent delivery surfaces. If one
breaks, the other still ships.

## Local development

```bash
npm install
npm run dev        # http://localhost:4321
npm run build      # static output into dist/
npm run check      # type-check .astro and .ts
```

Requires Node 20+.

## Deployment — Cloudflare Workers

Deployed as a **Workers** project, not Pages. Cloudflare's dashboard steers new
projects to Workers Builds, so that is the path taken. `wrangler.jsonc` in this
folder declares a static-assets-only Worker: no `main` field, no Worker code,
nothing runs per request — Cloudflare just serves the built files.

Live at `pixelposta.com`. Pushing to `main` deploys.

Project settings that matter:

| Setting | Value |
|---|---|
| **Path** | `/site` |
| Build command | `npm run build` |
| Deploy command | `npx wrangler deploy` |
| `NODE_VERSION` env var | `22.12.0` |

**`Path` is the one that breaks things.** It is the Workers equivalent of Pages'
"root directory". Left at `/`, the build runs at the repo root where there is no
`package.json`.

Astro 7 needs Node ≥ 22.12.0, which is newer than Cloudflare's default. Both
`.nvmrc` and the `NODE_VERSION` variable are set, belt and braces.

`not_found_handling: "404-page"` in `wrangler.jsonc` is what makes unknown URLs
serve the Hungarian 404 with a real 404 status rather than Cloudflare's default.

### Web Analytics

Enable it on the Worker in the Cloudflare dashboard — the beacon is injected at
the edge and nothing in this repo changes. Alternatively, set a
`PUBLIC_CF_BEACON_TOKEN` environment variable and `Base.astro` emits the beacon
itself; the token comes from *Analytics & Logs → Web Analytics → Add a site*.

It is cookieless and stores no client-side state, so it needs no consent banner
under GDPR — but confirm that independently if you add anything else that tracks.

## Adding an issue

The pipeline writes `src/content/issues/YYYY-WW/index.md` and commits it with
`draft: true`, so the file lands in the repo **without going live**. It is
invisible on the production site — no page, no archive row, no sitemap entry —
until you say otherwise.

1. `git pull`
2. Drop `cover.jpg` into the issue folder, then **uncomment the `cover:` line**
   in the frontmatter. Pointing `cover:` at a file that does not exist fails
   the build — that is deliberate, a silently missing cover is worse.
3. Drop article images in named `<slug>.jpg`, using the article's own `slug`
   from the frontmatter. No frontmatter change needed. A missing file just
   means no image, never an error. Aim for about three images per ten articles.
4. Write the `outro`. Blank lines separate paragraphs. There is no `intro` on
   the site — the newsletter opens with one, but here the standfirst already
   does that job and a second opener reads as filler.
5. Fill in `ajanlo` — title, genre, description, and the Steam `appid`. Capsule
   art is fetched from Steam by appid; if the appid is wrong the card renders
   without art rather than showing a broken image.
6. Adjust `title` and `standfirst` if you want. Once you change them, later
   pipeline runs leave them alone.
7. Run `npm run dev` and open the issue. Drafts **are** rendered locally, so
   this is where you check the cover, the article images and the ajánló cards
   before anyone else sees them.
8. Set `draft: false`, then commit and push. That one word is the publish
   button.

Re-running the weekly draft on a week you have already published will not pull
it back off the site — `draft` is preserved like `title` and `ajanlo`.

### Editing an issue by hand — the traps

All three of these have broken a build in practice. YAML gives no warning; the
build fails later, sometimes pointing at the wrong line.

**Quote any value containing `: `.** This is the most common one by far:

```yaml
title: Black Ops és Black Ops 2 PS-portok: két hét alatt…      # BREAKS
title: 'Black Ops és Black Ops 2 PS-portok: két hét alatt…'    # correct
```

Same for `imageCredit`, which always contains a colon after `Kép`. The pipeline
quotes automatically, so this only bites on hand-written entries.

**Keep list items at the same indentation.** Articles start at column 0
(`- slug:`), `ajanlo` items at two spaces (`  - title:`). Mixing them nests an
entry inside its neighbour and the parser reports a confusing error.

**`cover: ./cover.jpg` must be uncommented once the file exists.** This one
fails *silently* — the build succeeds and the issue goes live with the generated
placeholder instead of your artwork. It has been missed twice.

After editing, `npm run build` locally before pushing. A broken push means
Cloudflare fails and the issue simply never appears.

### Article and ajánló images

| What | Filename | Notes |
|---|---|---|
| Cover | `cover.jpg` | must also uncomment the `cover:` line |
| Article image | `<slug>.jpg` | slug comes from that article's `slug:` field |
| Ajánló capsule | `ajanlo-<appid>.jpg` | appid from the `ajanlo` entry |

`.jpg`, `.jpeg`, `.png`, `.webp` and `.avif` all work — everything is converted
to responsive WebP at build, so use whatever you have and don't pre-resize.
Article images are cropped to 16:9, capsules to 616×353.

Ajánló art is **committed**, not fetched. Steam's asset URLs used to be
derivable from an appid, but newer store items sit behind a per-asset content
hash that cannot be guessed — and new indie titles are exactly what this section
features. No image simply means the card renders without art.

Images are committed at whatever size you have; Astro crops to 16:9 and emits
responsive WebP at build time. Don't resize by hand.

## Structure

```
src/
├── content.config.ts        # issue schema — the contract with the pipeline
├── content/issues/YYYY-WW/  # index.md + cover.jpg + <slug>.jpg
├── components/              # see the brief's component table
├── layouts/Base.astro       # head, fonts, theme script, nav, footer
├── pages/
│   ├── index.astro          # hero + archive
│   ├── [year]/[week].astro  # one issue, three rovatok
│   └── 404.astro
├── styles/
│   ├── tokens.css           # the design system
│   └── global.css           # base styles and shared atoms
└── utils/
    ├── format.ts            # Hungarian dates, reading time, counts
    └── images.ts            # slug → article image lookup
```

## The release calendar

`/naptar/` renders `src/data/calendar.json`, which is generated and committed by
`python -m scripts.update_calendar` (weekly, via `weekly-calendar.yml`). Nothing
about it is hand-edited — a local edit is overwritten by the next refresh.

The file is validated twice: the Python side refuses to write fewer than 60
dated entries, and `src/utils/calendar.ts` parses it through a zod schema at
build time. A malformed file fails the build rather than rendering a broken
page, the same contract `content.config.ts` has with issue files.

Worth knowing before changing it:

- **Dates are stored ISO and formatted at render.** Unlike the weekly release
  tables, which hold display strings like `"08.14"`, nothing here can be sorted
  as text by accident.
- **Titles already out are dimmed**, computed against the build date. Because the
  calendar refreshes weekly, a game that shipped on Tuesday still reads as
  upcoming until Monday. That is the trade for zero client-side JS.
- **Month anchors are `honap-08`, not `2026-08`.** An id may start with a digit
  in HTML, but `#2026-08` is an invalid CSS selector and `querySelector` throws
  on it.
- **Platform labels are short here** — `Switch 2`, not the newsletter's
  `Nintendo Switch 2`. Two hundred rows do not have room for the long form.
  `PLATFORM_LABELS` in `src/collectors/gamesradar_releases.py` owns the mapping.

## Nav

Above 560px the links sit inline. Below it they collapse into a hamburger, and
the skin picker stays outside it — the picker is the most discoverable thing in
the nav, and nesting a six-item radio menu inside a disclosure would make it a
two-level menu. It sheds its label and rides as a swatch instead.

Two things keep this from being a pile of new CSS:

- **The hamburger is a `<details>`/`<summary>`, not a scripted dropdown.** It
  opens with JavaScript off, which is what keeps the promise further down this
  file that nothing becomes unreachable without JS. The inline script only adds
  Escape, outside-click, and mutual exclusion with the skin picker — all
  enhancements, none of them the mechanism.
- **`<summary>` carries `class="toggle"`,** so all four costume skins already
  style it and none of them needed a new rule. Likewise the dropdown is
  `.navmenu`, which is listed alongside `.skinmenu` in every panel rule in
  `skins.css` so both popovers share one box. Restyle one and you restyle both;
  that is deliberate.

The links are declared once in `LINKS` at the top of `Nav.astro` and rendered
twice — inline and inside the hamburger. That duplication is on purpose: a
`<details>` cannot be reliably forced open to serve as the desktop layout,
because engines hide its contents with `content-visibility` rather than
`display`.

`#hirlevel` is a bare fragment so it scrolls to the subscribe block on the page
you are already on. Every content page ends with one; 404 does not, so the link
does nothing there.

## Skins

Readers can pick a visual style from the nav. Világos and Sötét are the
editorial defaults; Win98, WinXP, Winamp and Nostromo are optional costumes in
`styles/skins.css`.

Two independent axes on `<html>`: `data-theme` (light/dark) is always present,
`data-skin` only for the costumes. Each skin also pins a theme, so anything it
does not explicitly restyle still lands on a coherent palette. The choice is
stored in `localStorage` under `pp-skin` and applied by the no-FOUC script in
`Base.astro` before first paint.

**Every skin rule is prefixed `:root:root[data-skin=…]` and that doubling is
load-bearing.** Astro compiles a component's `.wordmark span` into
`.wordmark[cid] span[cid]` — specificity (0,4,0). A plain `[data-skin] .foo`
rule is (0,3,0) and loses silently; component CSS is also emitted *after* this
file, so it wins ties too. The doubled `:root` buys enough specificity to win
regardless of source order. Drop it and roughly a third of the skin breaks in
ways that are hard to spot.

Skins only change colour, type, borders and chrome — never layout structure.
Anything that changes how the page is built belongs in the components.

## Things worth knowing before changing anything

- **Fonts are self-hosted and Hungarian coverage is a hard constraint.**
  Archivo, Literata and JetBrains Mono carry all of Latin Extended-A. Silkscreen
  does **not** have `ő` or `ű` and will fail silently mid-word, so only its
  Latin subset is loaded and it is used solely for the wordmark and footer mark
  — both pure ASCII. Never set Hungarian text in Silkscreen.
- **The Kiemelt panel is dark in both themes** and is the only place `--mark`
  appears anywhere on the site. That exclusivity is what makes it read as a
  different register.
- **Accent budget is roughly four amber moments per viewport.** Categories
  deliberately get no colour — colour-coding four of them would spend the whole
  budget on taxonomy.
- **Dates are parsed as strings, not `Date`.** `new Date('2026-07-25')` is UTC
  midnight and renders as the 24th west of Greenwich. See `utils/format.ts`.
- **The archive shows `INITIAL_ROWS` issues** (currently 6, in `pages/index.astro`)
  and reveals the rest on one click, so the subscribe block stays about two
  screens down however long the back catalogue gets. Every row is in the HTML
  either way — the button only toggles `hidden`, so nothing is hidden from
  search engines and the no-JS path shows the lot.
- **`[hidden]` is forced with `!important` in `global.css`.** It is a UA style at
  the lowest specificity, so `display: grid` on `.issue-row` or `display: flex`
  on `.year-rule` silently defeats it. Anything toggled by `hidden` — rovat
  panels, archive rows — depends on that rule.
- **The only client-side JS is the theme toggle and the rovat switcher**, both
  inline and hand-written. Astro ships zero JS by default; keep it that way.
  Without JS every rovat panel stays visible, so no content is unreachable.
