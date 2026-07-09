-- ============================================================
-- NewsHub — Đăng ký bản tin định kỳ (newsletter)
-- Chạy MỘT LẦN trong Supabase SQL Editor (sau 0002).
-- ============================================================

-- Bảng lưu email người đăng ký nhận bản tin.
create table if not exists public.newsletter_subscribers (
  id         bigint generated always as identity primary key,
  email      text not null,
  source     text not null default 'footer',
  created_at timestamptz not null default now()
);

-- Chống trùng, không phân biệt hoa/thường (Alice@x.com == alice@x.com).
create unique index if not exists newsletter_subscribers_email_key
  on public.newsletter_subscribers (lower(email));

alter table public.newsletter_subscribers enable row level security;

-- Ai cũng có thể ĐĂNG KÝ (insert). Email được kiểm định dạng cơ bản ngay
-- trong policy để anon key không thể nhét rác vào bảng.
drop policy if exists newsletter_insert_anon on public.newsletter_subscribers;
create policy newsletter_insert_anon on public.newsletter_subscribers
  for insert
  with check (
    char_length(email) between 3 and 254
    and email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'
  );

-- KHÔNG có policy SELECT/UPDATE/DELETE → danh sách email là riêng tư,
-- anon key không đọc/sửa/xóa được. Quản trị viên xem qua Supabase dashboard
-- (service role) hoặc export thủ công.
