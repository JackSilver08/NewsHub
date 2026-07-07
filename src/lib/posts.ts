import { getCollection, type CollectionEntry } from 'astro:content';
import type { SectionSlug } from './sections';

export type Post = CollectionEntry<'posts'>;

const isProd = import.meta.env.PROD;

/** Estimate reading time (in minutes) from raw markdown body. */
export function estimateReadingTime(body: string): number {
  const words = body.trim().split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.round(words / 200));
}

/** The routing slug for a post: explicit frontmatter `slug` wins, else the
 *  loader-generated `id` (derived from the filename). */
export function postSlug(post: Post): string {
  return post.data.slug?.trim() || post.id;
}

/** All publishable posts, newest first. Drafts are hidden in production. */
export async function getPublishedPosts(): Promise<Post[]> {
  const posts = await getCollection('posts', ({ data }) => {
    return isProd ? data.draft !== true : true;
  });
  return posts.sort(
    (a, b) => b.data.publishedAt.valueOf() - a.data.publishedAt.valueOf(),
  );
}

export async function getFeaturedPost(): Promise<Post | undefined> {
  const posts = await getPublishedPosts();
  return posts.find((p) => p.data.featured) ?? posts[0];
}

export async function getTrendingPosts(limit = 4): Promise<Post[]> {
  const posts = await getPublishedPosts();
  return posts.filter((p) => p.data.trending).slice(0, limit);
}

export async function getPopularPosts(limit = 5): Promise<Post[]> {
  const posts = await getPublishedPosts();
  return [...posts]
    .sort((a, b) => b.data.popularScore - a.data.popularScore)
    .slice(0, limit);
}

export async function getPostsByCategory(category: string): Promise<Post[]> {
  const posts = await getPublishedPosts();
  return posts.filter((p) => p.data.category === category);
}

export function getPostsForSection(
  posts: Post[],
  section: SectionSlug,
  limit: number,
  fallback: Post[] = [],
): Post[] {
  const selected = posts
    .filter((p) => p.data.sections.includes(section))
    .sort(
      (a, b) =>
        b.data.sectionPriority - a.data.sectionPriority ||
        b.data.publishedAt.valueOf() - a.data.publishedAt.valueOf(),
    );

  const merged = [...selected];
  const used = new Set(merged.map(postSlug));
  for (const post of fallback) {
    const slug = postSlug(post);
    if (!used.has(slug)) {
      merged.push(post);
      used.add(slug);
    }
    if (merged.length >= limit) break;
  }

  return merged.slice(0, limit);
}

/** Related posts: same category first, then shared tags, excluding `current`. */
export function getRelatedPosts(current: Post, all: Post[], limit = 3): Post[] {
  const others = all.filter((p) => postSlug(p) !== postSlug(current));
  const scored = others.map((p) => {
    let score = 0;
    if (p.data.category === current.data.category) score += 3;
    const shared = p.data.tags.filter((t) => current.data.tags.includes(t));
    score += shared.length;
    return { p, score };
  });
  return scored
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score || b.p.data.publishedAt.valueOf() - a.p.data.publishedAt.valueOf())
    .slice(0, limit)
    .map((s) => s.p);
}

/** Format a date as dd/mm/yyyy (Vietnamese convention). */
export function formatDate(date: Date): string {
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(date);
}
