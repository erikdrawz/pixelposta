/**
 * Load and validate the release calendar.
 *
 * `src/data/calendar.json` is written by `scripts/update_calendar.py` and
 * committed. Validating it here gives the same guarantee `content.config.ts`
 * gives issue files: a malformed data file fails the build instead of quietly
 * rendering a broken page. The Python side has its own guard against writing a
 * short file (`MIN_DATED_ENTRIES` in `src/calendar_writer.py`), so the contract
 * is enforced from both ends.
 */
import { z } from 'astro/zod';
import raw from '../data/calendar.json';
import { formatHuMonth } from './format';

const entrySchema = z.object({
  title: z.string().min(1),
  platforms: z.array(z.string()),
  earlyAccess: z.boolean(),
});

const datedSchema = entrySchema.extend({
  // ISO, and parsed as a string everywhere downstream. `new Date('2026-07-25')`
  // is UTC midnight and renders as the 24th west of Greenwich — the same trap
  // documented in utils/format.ts.
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'date must be ISO YYYY-MM-DD'),
  // Reserved for the OpenCritic pass; always null for now.
  score: z.number().nullable(),
  openCriticId: z.number().nullable(),
});

const calendarSchema = z.object({
  year: z.number().int(),
  generated: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  dated: z.array(datedSchema),
  tbc: z.array(entrySchema),
});

const calendar = calendarSchema.parse(raw);

export type DatedRelease = z.infer<typeof datedSchema>;
export type UndatedRelease = z.infer<typeof entrySchema>;

export interface CalendarMonth {
  /** 1-based, so it can be handed straight to formatHuMonth. */
  month: number;
  name: string;
  /**
   * Anchor target for the month jump links — "honap-08".
   *
   * Not the bare "2026-08": an id may legally start with a digit in HTML, but
   * `#2026-08` is then an invalid CSS selector and querySelector throws on it.
   */
  id: string;
  releases: DatedRelease[];
}

export const calendarYear = calendar.year;
export const generatedOn = calendar.generated;
export const undatedReleases = calendar.tbc;

/**
 * The year's releases grouped into months.
 *
 * Every month is present even when empty — the jump links at the top of the
 * page are a fixed row of twelve, and a link that scrolls to nothing is worse
 * than one that scrolls to "nincs ismert megjelenés".
 */
export const months: CalendarMonth[] = Array.from({ length: 12 }, (_, i) => {
  const month = i + 1;
  const padded = String(month).padStart(2, '0');
  const prefix = `${calendar.year}-${padded}`;
  return {
    month,
    name: formatHuMonth(month),
    id: `honap-${padded}`,
    // Already sorted by the pipeline, which sorts on real dates before writing.
    releases: calendar.dated.filter((r) => r.date.startsWith(prefix)),
  };
});
