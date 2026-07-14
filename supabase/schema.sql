-- NewsHub Supabase schema
-- Run this file in Supabase SQL Editor.

create extension if not exists "pgcrypto";

do $$
begin
  if not exists (select 1 from pg_type where typname = 'post_status') then
    create type public.post_status as enum ('draft', 'published', 'archived');
  end if;
end
$$;

create table if not exists public.posts (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  slug text not null unique,
  excerpt text not null default '',
  content text not null default '',
  category text not null,
  tags text[] not null default '{}',
  author text not null default 'NewsHub Admin',
  status public.post_status not null default 'draft',
  image_url text,
  image_alt text not null default '',
  sections text[] not null default '{}',
  section_priority integer not null default 0,
  popular_score integer not null default 0,
  featured boolean not null default false,
  trending boolean not null default false,
  published_at timestamptz,
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists posts_status_published_at_idx
  on public.posts (status, published_at desc);

create index if not exists posts_category_idx
  on public.posts (category);

create index if not exists posts_sections_gin_idx
  on public.posts using gin (sections);

create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists posts_touch_updated_at on public.posts;
create trigger posts_touch_updated_at
before update on public.posts
for each row execute function public.touch_updated_at();

alter table public.posts enable row level security;

drop policy if exists "Published posts are public" on public.posts;
create policy "Published posts are public"
on public.posts for select
using (status = 'published');

-- Development policy for the current hard-coded admin screen.
-- This keeps the static admin working with the public anon key.
-- Before production, replace it with Supabase Auth based policies.
drop policy if exists "Anon admin can manage posts during development" on public.posts;
create policy "Anon admin can manage posts during development"
on public.posts for all
to anon
using (true)
with check (true);

insert into storage.buckets (id, name, public)
values ('post-images', 'post-images', true)
on conflict (id) do update set public = excluded.public;

drop policy if exists "Post images are public" on storage.objects;
create policy "Post images are public"
on storage.objects for select
using (bucket_id = 'post-images');

drop policy if exists "Anon admin can upload post images during development" on storage.objects;
create policy "Anon admin can upload post images during development"
on storage.objects for insert
to anon
with check (bucket_id = 'post-images');

drop policy if exists "Anon admin can update post images during development" on storage.objects;
create policy "Anon admin can update post images during development"
on storage.objects for update
to anon
using (bucket_id = 'post-images')
with check (bucket_id = 'post-images');

drop policy if exists post_images_insert_staff on storage.objects;
create policy post_images_insert_staff on storage.objects
for insert to authenticated
with check (
  bucket_id = 'post-images'
  and public.current_user_role() in ('admin', 'moderator')
);

drop policy if exists post_images_update_staff on storage.objects;
create policy post_images_update_staff on storage.objects
for update to authenticated
using (
  bucket_id = 'post-images'
  and public.current_user_role() in ('admin', 'moderator')
)
with check (
  bucket_id = 'post-images'
  and public.current_user_role() in ('admin', 'moderator')
);

drop policy if exists post_images_delete_staff on storage.objects;
create policy post_images_delete_staff on storage.objects
for delete to authenticated
using (
  bucket_id = 'post-images'
  and public.current_user_role() in ('admin', 'moderator')
);
