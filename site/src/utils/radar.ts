/**
 * The Indie Radar: every ajánló recommendation, gathered across all issues.
 *
 * There is no separate data file. The radar is a view over the issues that
 * already exist — each one's `ajanlo` block is the source, and the capsule art
 * is the same committed `ajanlo-<appid>.jpg` the issue page uses. Publishing an
 * issue therefore adds its games here with no second place to update, which is
 * the whole point: the list grows by itself.
 *
 * Draft issues are excluded in production by `publishedIssues`, so a game
 * cannot reach the radar before the issue that recommends it goes live.
 */
import type { CollectionEntry } from 'astro:content';
import { gemImage } from './images';
import { issueUrl, publishedIssues, weekLabel } from './format';

type Issue = CollectionEntry<'issues'>;

export interface RadarEntry {
  title: string;
  genre: string;
  description: string;
  appid: number;
  /** Committed capsule art, or undefined on the older issues that predate it. */
  image?: ImageMetadata;
  /** "2026 · 43. hét" — where the recommendation first appeared. */
  issueLabel: string;
  issueUrl: string;
}

/**
 * Every recommendation, newest issue first.
 *
 * Within one issue the games keep the order the editor wrote them in, which is
 * the same order the issue page shows — a reader following a link from an issue
 * finds them arranged the way they remember.
 *
 * An appid is listed once. No game has been recommended twice so far, but the
 * radar is cumulative and a repeat would otherwise show up as a duplicate card
 * rather than as the one entry a reader expects. The first occurrence wins,
 * which is the newest issue, so a re-recommendation surfaces at the top with
 * its most recent write-up.
 */
export function radarEntries(issues: Issue[]): RadarEntry[] {
  const out: RadarEntry[] = [];
  const seen = new Set<number>();

  for (const issue of publishedIssues(issues)) {
    const label = weekLabel(issue.data.year, issue.data.week, issue.data.weekFrom);
    const url = issueUrl(issue);

    for (const g of issue.data.ajanlo) {
      if (seen.has(g.appid)) continue;
      seen.add(g.appid);
      out.push({
        title: g.title,
        genre: g.genre,
        description: g.description,
        appid: g.appid,
        image: gemImage(issue.id, g.appid),
        issueLabel: label,
        issueUrl: url,
      });
    }
  }

  return out;
}
