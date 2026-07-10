import { getCollection, type CollectionEntry } from 'astro:content';
import type { SectionSlug } from './sections';
import { supabase } from './supabase';

export type LocalPost = CollectionEntry<'posts'>;

export interface SupabasePost {
  id: string;
  source: 'supabase';
  body: string;
  data: {
    title: string;
    slug: string;
    excerpt: string;
    category: string;
    tags: string[];
    author: string;
    publishedAt: Date;
    updatedAt?: Date;
    readingTime?: number;
    image?: string;
    imageAlt: string;
    featured: boolean;
    trending: boolean;
    sections: SectionSlug[];
    sectionPriority: number;
    popularScore: number;
    draft: boolean;
  };
}

export type Post = LocalPost | SupabasePost;

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

export function isSupabasePost(post: Post): post is SupabasePost {
  return 'source' in post && post.source === 'supabase';
}

function normalizeSectionSlugs(value: unknown): SectionSlug[] {
  return Array.isArray(value) ? (value.filter(Boolean) as SectionSlug[]) : [];
}

function toDate(value: unknown, fallback = new Date()): Date {
  return value ? new Date(String(value)) : fallback;
}

async function getSupabasePublishedPosts(): Promise<SupabasePost[]> {
  if (!supabase) return [];

  const { data, error } = await supabase
    .from('posts')
    .select(
      [
        'id',
        'title',
        'slug',
        'excerpt',
        'content',
        'category',
        'tags',
        'author',
        'status',
        'image_url',
        'image_alt',
        'sections',
        'section_priority',
        'popular_score',
        'featured',
        'trending',
        'published_at',
        'updated_at',
        'created_at',
      ].join(','),
    )
    .eq('status', 'published')
    .order('published_at', { ascending: false, nullsFirst: false });

  if (error || !data) {
    if (error) console.warn('Supabase posts unavailable:', error.message);
    return [];
  }

  return data.map((row: any) => {
    const publishedAt = toDate(row.published_at, toDate(row.created_at));
    const body = String(row.content || '');

    return {
      id: row.slug || row.id,
      source: 'supabase',
      body,
      data: {
        title: String(row.title || ''),
        slug: String(row.slug || row.id),
        excerpt: String(row.excerpt || ''),
        category: String(row.category || 'ai'),
        tags: Array.isArray(row.tags) ? row.tags : [],
        author: String(row.author || 'Thường Nhật Admin'),
        publishedAt,
        updatedAt: row.updated_at ? toDate(row.updated_at) : undefined,
        readingTime: estimateReadingTime(body),
        image: row.image_url || undefined,
        imageAlt: String(row.image_alt || ''),
        featured: Boolean(row.featured),
        trending: Boolean(row.trending),
        sections: normalizeSectionSlugs(row.sections),
        sectionPriority: Number(row.section_priority || 0),
        popularScore: Number(row.popular_score || 0),
        draft: false,
      },
    };
  });
}

/** All publishable posts, newest first. Drafts are hidden in production. */
export async function getPublishedPosts(): Promise<Post[]> {
  const localPosts = await getCollection('posts', ({ data }) => {
    return isProd ? data.draft !== true : true;
  });
  const supabasePosts = await getSupabasePublishedPosts();
  const merged: Post[] = [];
  const used = new Set<string>();

  for (const post of [...supabasePosts, ...localPosts]) {
    const slug = postSlug(post);
    if (!used.has(slug)) {
      merged.push(post);
      used.add(slug);
    }
  }

  return merged.sort(
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
