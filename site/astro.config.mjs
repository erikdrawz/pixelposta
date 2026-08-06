// @ts-check
import { defineConfig } from 'astro/config';

// Static output, no integrations, no SSR. The only client-side JS on the site
// is the theme toggle and the rovat switcher, both inline and hand-written.
export default defineConfig({
  site: 'https://pixelposta.com',
  trailingSlash: 'always',
  build: {
    // /2026/30/index.html — matches the trailing-slash URLs in the brief.
    format: 'directory',
  },
  // Article and cover images are committed as JPGs and optimised to WebP at
  // build time by Astro's <Image>. Steam capsule art is deliberately outside
  // the asset pipeline — it is hotlinked at runtime (see GemCard.astro).
});
