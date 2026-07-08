-- ============================================================
-- NewsHub — Siết bảo mật posts + Lưu bài (bookmark) + Badge bình luận
-- Chạy MỘT LẦN trong Supabase SQL Editor (sau 0001).
-- ============================================================

-- 1. SIẾT QUYỀN GHI BẢNG posts ---------------------------------
-- Trước đây RLS tắt → ai có anon key cũng ghi được. Bật RLS và chỉ
-- cho admin/moderator ghi; đọc thì bài published ai cũng xem, nháp
-- chỉ admin/moderator thấy.
alter table public.posts enable row level security;

drop policy if exists posts_select on public.posts;
create policy posts_select on public.posts
  for select using (
    status = 'published' or public.current_user_role() in ('admin', 'moderator')
  );

drop policy if exists posts_insert_staff on public.posts;
create policy posts_insert_staff on public.posts
  for insert with check (public.current_user_role() in ('admin', 'moderator'));

drop policy if exists posts_update_staff on public.posts;
create policy posts_update_staff on public.posts
  for update using (public.current_user_role() in ('admin', 'moderator'))
  with check (public.current_user_role() in ('admin', 'moderator'));

drop policy if exists posts_delete_staff on public.posts;
create policy posts_delete_staff on public.posts
  for delete using (public.current_user_role() in ('admin', 'moderator'));

-- 2. LƯU BÀI (bookmark) ----------------------------------------
create table if not exists public.saved_posts (
  user_id    uuid not null references auth.users (id) on delete cascade,
  post_slug  text not null,
  post_title text,
  created_at timestamptz not null default now(),
  primary key (user_id, post_slug)
);

alter table public.saved_posts enable row level security;

-- Mỗi người chỉ thấy/lưu/xóa bài đã lưu của chính mình.
drop policy if exists saved_select_own on public.saved_posts;
create policy saved_select_own on public.saved_posts
  for select using (auth.uid() = user_id);

drop policy if exists saved_insert_own on public.saved_posts;
create policy saved_insert_own on public.saved_posts
  for insert with check (auth.uid() = user_id);

drop policy if exists saved_delete_own on public.saved_posts;
create policy saved_delete_own on public.saved_posts
  for delete using (auth.uid() = user_id);

-- 3. BADGE VAI TRÒ CHO BÌNH LUẬN -------------------------------
-- Lưu role của người bình luận tại thời điểm gửi để hiển thị nhãn
-- Admin/Moderator cạnh tên.
alter table public.comments
  add column if not exists author_role text not null default 'user';
