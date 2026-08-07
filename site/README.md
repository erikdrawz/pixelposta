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

## Cloudflare Pages

Connect the `erikdrawz/pixelposta` repo and set:

| Setting | Value |
|---|---|
| Root directory | `site` |
| Build command | `npm run build` |
| Output directory | `dist` |
| Node version | `20` or later |

Pushing to `main` deploys.

### Web Analytics

Two ways, and the first is easier:

1. **Automatic** — Cloudflare dashboard → your Pages project → *Settings* →
   *Web Analytics* → enable. Cloudflare injects the beacon at the edge and
   nothing in this repo changes. Prefer this.
2. **Manual** — dashboard → *Analytics & Logs* → *Web Analytics* → *Add a
   site* → `pixelposta.com`. The snippet it hands back contains
   `data-cf-beacon='{"token": "…"}'`. Put that token in a `PUBLIC_CF_BEACON_TOKEN`
   environment variable in the Pages project settings and the layout will emit
   the beacon itself.

It is cookieless and stores no client-side state, so it needs no consent
banner under GDPR — but confirm that independently before launch if you add
anything else that tracks.

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
