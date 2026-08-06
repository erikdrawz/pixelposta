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
  return byIssue.get(issueId)?.get(slug);
}
