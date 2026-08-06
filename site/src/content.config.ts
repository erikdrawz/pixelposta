import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
// astro:content still re-exports `z`, but it is deprecated in Astro 7 —
// astro/zod is the same instance without the deprecation.
import { z } from 'astro/zod';

/** Category order is fixed — it drives section order on the issue page. */
export const CATEGORIES = ['Játékhírek', 'Hardware', 'AI & Gaming', 'Stúdió & Üzlet'] as const;

const releaseSchema = z.object({
  title: z.string(),
  platform: z.string(),
  date: z.string(), // "07.24" — display-only, already formatted by the pipeline
});

const issues = defineCollection({
  // One folder per issue: issues/2026-30/{index.md, cover.jpg, <slug>.jpg}.
  // The id is the folder name, which is also the URL pair (year/week).
  loader: glob({
    pattern: '*/index.md',
    base: './src/content/issues',
    generateId: ({ entry }) => entry.split('/')[0],
  }),
  schema: ({ image }) =>
    z.object({
      year: z.number().int(),
      week: z.number().int().min(1).max(53),

      // ISO date — the Saturday of this ISO week. Kept as a string and parsed
      // by hand in utils/format.ts: `new Date('2026-07-25')` is UTC midnight
      // and would render as the 24th for anyone west of Greenwich.
      date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'date must be ISO YYYY-MM-DD'),

      title: z.string(),
      standfirst: z.string(),
      cover: image().optional(),

      // Computed at build from the prose when absent. Present only if the
      // editor wants to override it.
      readingMinutes: z.number().optional(),

      // Editor-written, Hírek rovat only. Blank lines separate paragraphs.
      // There is deliberately no `intro`: the newsletter opens with one, the
      // site does not — the standfirst already does that job here.
      outro: z.string().default(''),
      signature: z.string().default('— Erik · Pixelposta'),

      articles: z.array(
        z.object({
          slug: z.string(), // also the article image filename stem
          category: z.enum(CATEGORIES),
          title: z.string(),
          body: z.string(),
          source: z.string(),
          url: z.url(),
          kiemelt: z.string().optional(),
          imageCredit: z.string().optional(),
        }),
      ),

      // One flat list, rendered in the order written. Deliberately not sorted
      // here: the values are display strings like "08.04", which sort wrongly
      // across a year boundary. The pipeline sorts by real dates before
      // formatting, so authored order is already correct.
      releases: z.array(releaseSchema).default([]),

      ajanlo: z
        .array(
          z.object({
            title: z.string(),
            genre: z.string(),
            description: z.string(),
            appid: z.number().int().positive(),
          }),
        )
        .default([]),
    }),
});

export const collections = { issues };
