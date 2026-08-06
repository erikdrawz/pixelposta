// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// Static output, no integrations, no SSR. The only client-side JS on the site
// is the theme toggle and the rovat switcher, both inline and hand-written.
export default defineConfig({
  site: 'https://pixelposta.com',
  trailingSlash: 'always',
  // Emits sitemap-index.xml + sitemap-0.xml, referenced from public/robots.txt.
  // 404 is excluded: it is a real page in the build output but must never be
  // offered to a crawler as content.
  integrations: [
    sitemap({
      filter: (page) => !page.endsWith('/404/') && !page.endsWith('/404.html'),
    }),
  ],
  build: {
    // /2026/30/index.html — matches the trailing-slash URLs in the brief.
    format: 'directory',
  },
  // Article and cover images are committed as JPGs and optimised to WebP at
  // build time by Astro's <Image>. Steam capsule art is deliberately outside
  // the asset pipeline — it is hotlinked at runtime (see GemCard.astro).
});
