-- ============================================================
-- NewsHub — Supabase Auth (profiles) + Comments
-- Chạy MỘT LẦN trong Supabase SQL Editor.
-- ============================================================

-- 1. PROFILES --------------------------------------------------
-- Mỗi user trong auth.users có 1 dòng profile chứa tên hiển thị + role.
create table if not exists public.profiles (
  id         uuid primary key references auth.users (id) on delete cascade,
  email      text,
  name       text,
  role       text not null default 'user' check (role in ('user', 'moderator', 'admin')),
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

-- Helper: role của user hiện tại. SECURITY DEFINER để bỏ qua RLS,
-- tránh đệ quy khi policy của chính bảng profiles cần đọc role.
create or replace function public.current_user_role()
returns text
language sql
stable
security definer
set search_path = public
as $$
  select role from public.profiles where id = auth.uid();
$$;

-- Ai cũng đọc được profile (để hiển thị tên người bình luận).
drop policy if exists profiles_select_all on public.profiles;
create policy profiles_select_all on public.profiles
  for select using (true);

-- User tự sửa profile của mình (đổi tên). Không cho tự đổi role.
drop policy if exists profiles_update_own on public.profiles;
create policy profiles_update_own on public.profiles
  for update using (auth.uid() = id)
  with check (auth.uid() = id and role = public.current_user_role());

-- Admin sửa được mọi profile (kể cả role, để phong moderator).
drop policy if exists profiles_admin_update on public.profiles;
create policy profiles_admin_update on public.profiles
  for update using (public.current_user_role() = 'admin')
  with check (public.current_user_role() = 'admin');

-- 2. Tự tạo profile khi có user mới ---------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, name, role)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data ->> 'name', split_part(new.email, '@', 1)),
    case when new.email = 'admin@newshub.com' then 'admin' else 'user' end
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- 3. COMMENTS -------------------------------------------------
create table if not exists public.comments (
  id          uuid primary key default gen_random_uuid(),
  post_slug   text not null,
  parent_id   uuid references public.comments (id) on delete cascade,
  user_id     uuid not null references auth.users (id) on delete cascade,
  author_name text not null,
  content     text not null check (char_length(content) between 1 and 4000),
  created_at  timestamptz not null default now()
);

create index if not exists comments_post_slug_idx on public.comments (post_slug, created_at);
create index if not exists comments_parent_idx on public.comments (parent_id);

alter table public.comments enable row level security;

-- Ai cũng đọc được bình luận.
drop policy if exists comments_select_all on public.comments;
create policy comments_select_all on public.comments
  for select using (true);

-- User đã đăng nhập chỉ chèn được bình luận đứng tên chính mình.
drop policy if exists comments_insert_own on public.comments;
create policy comments_insert_own on public.comments
  for insert with check (auth.uid() = user_id);

-- Tác giả xóa bình luận của mình; admin/moderator xóa được mọi bình luận.
drop policy if exists comments_delete_own_or_admin on public.comments;
create policy comments_delete_own_or_admin on public.comments
  for delete using (
    auth.uid() = user_id
    or public.current_user_role() in ('admin', 'moderator')
  );
