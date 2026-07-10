import rss from '@astrojs/rss';
import type { APIContext } from 'astro';
import { getPublishedPosts, postSlug } from '../lib/posts';

export async function GET(context: APIContext) {
  const posts = await getPublishedPosts();
  return rss({
    title: 'Công Nghệ Thường Nhật — Tin công nghệ và AI',
    description:
      'Cập nhật tin tức công nghệ, AI, startup, thiết bị và an ninh mạng mới nhất.',
    site: context.site ?? 'https://newshub.vercel.app',
    items: posts.map((post) => ({
      title: post.data.title,
      description: post.data.excerpt,
      pubDate: post.data.publishedAt,
      link: `/article/${postSlug(post)}`,
      categories: [post.data.category, ...post.data.tags],
    })),
    customData: `<language>vi-VN</language>`,
  });
}
