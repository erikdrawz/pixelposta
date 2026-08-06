/**
 * Article images are matched by filename, not declared in frontmatter.
 *
 * The editor drops `<article-slug>.jpg` into the issue folder and that is the
 * entire contract. A missing file means no image — never an error. Cover art
 * is the exception: it goes through the schema's `image()` helper so Astro can
 * type it, and is skipped here.
 */
const modules = import.meta.glob<{ default: ImageMetadata }>(
  '../content/issues/*/*.{jpg,jpeg,png,webp,avif}',
  { eager: true },
);

/** Filename stems that are never article images. */
const RESERVED = new Set(['cover']);

/** Ajánló capsule art is committed as `ajanlo-<appid>.jpg`. */
const AJANLO_PREFIX = 'ajanlo-';

const byIssue = new Map<string, Map<string, ImageMetadata>>();

for (const [path, mod] of Object.entries(modules)) {
  // ../content/issues/2026-30/megjelent-a-scarlet-deer-inn.jpg
  const match = path.match(/\/issues\/([^/]+)\/([^/]+)\.[^.]+$/);
  if (!match) continue;
  const [, issueId, stem] = match as unknown as [string, string, string];
  if (RESERVED.has(stem)) continue;

  let issueImages = byIssue.get(issueId);
  if (!issueImages) {
    issueImages = new Map();
    byIssue.set(issueId, issueImages);
  }
  issueImages.set(stem, mod.default);
}

/** The image for one article, or undefined when the editor didn't add one. */
export function articleImage(issueId: string, slug: string): ImageMetadata | undefined {
  if (slug.startsWith(AJANLO_PREFIX)) return undefined;
  return byIssue.get(issueId)?.get(slug);
}

/**
 * Committed capsule art for an ajánló entry, or undefined.
 *
 * Steam's asset URLs used to be derivable from the appid alone, but newer
 * store items sit behind a per-asset content hash that cannot be guessed —
 * and new indie titles are exactly what this section features. So the art is
 * committed alongside the issue, keyed on appid.
 */
export function gemImage(issueId: string, appid: number): ImageMetadata | undefined {
  return byIssue.get(issueId)?.get(`${AJANLO_PREFIX}${appid}`);
}
