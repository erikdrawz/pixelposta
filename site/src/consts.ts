/** Site identity. Kept in one place because it appears in the <title>, the
 *  Open Graph tags and the structured data, and those must not drift apart. */

export const SITE_NAME = 'Pixelposta';

/** Landing-page <title> and the name Google shows in results. */
export const SITE_TITLE = 'Pixelposta - A hét videójátékos hírei';

/** Landing-page meta description. Stable on purpose: a homepage description
 *  that changes weekly gives search engines nothing consistent to index. */
export const SITE_DESCRIPTION =
  'Heti válogatás a videójátékok világából, magyarul. Játékhírek, hardver, ' +
  'AI és stúdióhírek, megjelenési naptár és játékajánló, minden hétvégén.';

/** The publication itself. Used as the Organization's `sameAs` in the
 *  structured data, which wants the profile, not a form. */
export const SUBSTACK_URL = 'https://pixelposta.substack.com';

/** Where the Feliratkozom button goes — straight to the signup form. */
export const SUBSTACK_SUBSCRIBE_URL = 'https://pixelposta.substack.com/subscribe';

/** The podcast the site embeds on /podcast/. */
export const PODCAST_NAME = 'Millennial Falcon';

/** Spotify show id, used to build both the embed and the open-in-Spotify link. */
export const PODCAST_SPOTIFY_SHOW_ID = '799nEBrSyVQoiDvID0jyaZ';

/**
 * Where to listen, in the order they are shown under the player.
 *
 * `icon` names an inline SVG in components/PlatformLinks.astro — the site
 * loads no icon font and no third-party script, so every mark is drawn in the
 * markup and inherits the skin's colour through currentColor.
 */
export const PODCAST_PLATFORMS = [
  {
    icon: 'spotify',
    label: 'Spotify',
    href: `https://open.spotify.com/show/${PODCAST_SPOTIFY_SHOW_ID}`,
  },
  {
    icon: 'apple',
    label: 'Apple Podcasts',
    href: 'https://podcasts.apple.com/hu/podcast/millennial-falcon/id1478792312',
  },
  {
    icon: 'youtube',
    label: 'YouTube',
    href: 'https://www.youtube.com/@millennial.falcon/podcasts',
  },
] as const;
