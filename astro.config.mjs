// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// Update `site` to your real production domain before deploying.
// It is used for canonical URLs, sitemap, RSS and Open Graph tags.
export default defineConfig({
  site: 'https://newshub.vercel.app',
  trailingSlash: 'ignore',
  integrations: [sitemap()],
  markdown: {
    shikiConfig: {
      theme: 'github-dark',
      wrap: true,
    },
  },
});
