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

export const SUBSTACK_URL = 'https://pixelposta.substack.com';
