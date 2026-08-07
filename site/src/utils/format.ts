import type { CollectionEntry } from 'astro:content';

type Issue = CollectionEntry<'issues'>;

const HU_MONTHS = [
  'január', 'február', 'március', 'április', 'május', 'június',
  'július', 'augusztus', 'szeptember', 'október', 'november', 'december',
];

/** Words per minute for Hungarian editorial prose. */
const WPM = 180;

/**
 * Split an ISO date without going through `Date`.
 *
 * `new Date('2026-07-25')` parses as UTC midnight, so any reader west of
 * Greenwich renders it as the 24th. The strings are already validated by the
 * schema, so a plain split is both safer and cheaper.
 */
function parseIso(iso: string): { year: number; month: number; day: number } {
  const [year, month, day] = iso.split('-').map(Number);
  return { year: year!, month: month!, day: day! };
}

/** "2026. július 25." — the full form, used in the hero and the byline. */
export function formatHuDate(iso: string): string {
  const { year, month, day } = parseIso(iso);
  return `${year}. ${HU_MONTHS[month - 1]} ${day}.`;
}

/** "Július 18." — the short form for archive rows, where the year is a heading. */
export function formatHuDateShort(iso: string): string {
  const { month, day } = parseIso(iso);
  const name = HU_MONTHS[month - 1]!;
  return `${name[0]!.toUpperCase()}${name.slice(1)} ${day}.`;
}

/** "2026 · 30. hét" */
export function weekLabel(year: number, week: number): string {
  return `${year} · ${week}. hét`;
}

/** Issue permalink. Trailing slash matches astro.config's trailingSlash. */
export function issueUrl(issue: Issue): string {
  return `/${issue.data.year}/${issue.data.week}/`;
}

/** Split editor prose into paragraphs on blank lines. */
export function paragraphs(text: string): string[] {
  return text
    .split(/\n\s*\n/)
    .map((p) => p.trim().replace(/\s*\n\s*/g, ' '))
    .filter(Boolean);
}

function countWords(text: string): number {
  const trimmed = text.trim();
  return trimmed ? trimmed.split(/\s+/).length : 0;
}

/**
 * Reading time over everything in the Gaming rovat plus the ajánló blurbs —
 * the parts a reader actually reads. Release tables are scanned, not read.
 * The editor can override with `readingMinutes` in frontmatter.
 */
export function readingMinutes(issue: Issue): number {
  if (issue.data.readingMinutes !== undefined) return issue.data.readingMinutes;

  const { outro, articles, ajanlo } = issue.data;
  let words = countWords(outro);
  for (const a of articles) {
    words += countWords(a.title) + countWords(a.body) + countWords(a.kiemelt ?? '');
  }
  for (const g of ajanlo) {
    words += countWords(g.title) + countWords(g.description);
  }
  return Math.max(1, Math.round(words / WPM));
}

export interface IssueCounts {
  articles: number;
  releases: number;
  ajanlo: number;
  minutes: number;
}

export function issueCounts(issue: Issue): IssueCounts {
  return {
    articles: issue.data.articles.length,
    releases: issue.data.releases.length,
    ajanlo: issue.data.ajanlo.length,
    minutes: readingMinutes(issue),
  };
}

/** Newest first. Used everywhere issues are listed. */
export function sortIssues(issues: Issue[]): Issue[] {
  return [...issues].sort(
    (a, b) => b.data.year - a.data.year || b.data.week - a.data.week,
  );
}

/**
 * Every issue the site should render, newest first.
 *
 * Drafts are dropped from production builds but kept in `astro dev`, so an
 * issue can be checked with its cover and article images in place before the
 * flag is flipped. This is the single place that decision is made — both the
 * landing page and the issue routes go through it, so a draft cannot leak
 * into one of them by being fetched directly.
 */
export function publishedIssues(issues: Issue[]): Issue[] {
  const visible = import.meta.env.PROD ? issues.filter((i) => !i.data.draft) : issues;
  return sortIssues(visible);
}
