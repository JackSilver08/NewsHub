import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';
import { SECTION_SLUGS } from './lib/sections';

// Category slugs allowed across the site. Keep in sync with:
//  - src/lib/categories.ts (labels + nav)
//  - public/admin/config.yml (CMS select options)
const CATEGORIES = [
  'ai',
  'thiet-bi',
  'startup',
  'an-ninh-mang',
  'lap-trinh',
  'cloud',
  'danh-gia',
] as const;

const posts = defineCollection({
  // Content Layer API (Astro v6+): load markdown files via the glob loader.
  loader: glob({ pattern: '**/*.md', base: './src/content/posts' }),
  // Images are stored as public paths (e.g. /assets/... or /uploads/...) so we
  // validate them as plain strings rather than using the astro:assets helper.
  schema: z.object({
    title: z.string(),
    // `slug` is optional in frontmatter; the routing slug falls back to the
    // loader-generated `id` (derived from the filename).
    slug: z.string().optional(),
    excerpt: z.string(),
    category: z.enum(CATEGORIES),
    tags: z.array(z.string()).default([]),
    author: z.string().default('Ban Biên tập Công Nghệ Thường Nhật'),
    publishedAt: z.coerce.date(),
    updatedAt: z.coerce.date().optional(),
    readingTime: z.number().int().positive().optional(),
    image: z.string().optional(),
    imageAlt: z.string().default(''),
    featured: z.boolean().default(false),
    trending: z.boolean().default(false),
    sections: z.array(z.enum(SECTION_SLUGS)).default([]),
    sectionPriority: z.number().default(0),
    popularScore: z.number().default(0),
    draft: z.boolean().default(false),
  }),
});

export const collections = { posts };
