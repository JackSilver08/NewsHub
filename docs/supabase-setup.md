# NewsHub Supabase setup

NewsHub keeps the public site static, while the admin screen can write posts and upload images to Supabase.

## 1. Create Supabase project

Create a project in Supabase, then copy:

- Project URL
- anon public key

## 2. Run database schema

Open Supabase SQL Editor and run:

```sql
-- paste the contents of supabase/schema.sql
```

This creates:

- `public.posts`
- public storage bucket `post-images`
- development RLS policies for the current hard-coded admin screen

## 3. Configure local admin

Edit `public/admin/supabase-config.js` or reuse the values from `docs/supabase-project.md`:

```js
window.NEWSHUB_SUPABASE = {
  url: 'https://YOUR_PROJECT.supabase.co',
  anonKey: 'YOUR_PUBLIC_ANON_KEY',
  imageBucket: 'post-images',
};
```

For Astro code that fetches Supabase data during build/runtime, copy `.env.example` to `.env` and fill:

```txt
PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
PUBLIC_SUPABASE_ANON_KEY=YOUR_PUBLIC_ANON_KEY
```

## 4. Admin fields

Admin posts save these homepage placement fields:

- `home-hero`: hero chính
- `home-side`: cột tin cạnh hero
- `breaking-news`: tin nóng
- `latest-news`: cập nhật mới nhất
- `popular-sidebar`: đọc nhiều
- `ai-daily-brief`: AI Daily Brief
- `tech-trends`: xu hướng công nghệ

Use `section_priority` to order posts inside each area.

## Production note

The current SQL includes permissive anon write policies so the static admin can work with the existing hard-coded login. Before publishing publicly, replace those policies with Supabase Auth based admin policies or move writes behind a serverless API.
