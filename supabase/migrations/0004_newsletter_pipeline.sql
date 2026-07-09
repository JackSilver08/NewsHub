-- ============================================================
-- NewsHub — Pipeline gửi bản tin: token hủy, xác nhận, log gửi
-- Chạy MỘT LẦN trong Supabase SQL Editor (sau 0003).
-- ============================================================

-- 1. NÂNG CẤP BẢNG SUBSCRIBERS ---------------------------------
alter table public.newsletter_subscribers
  -- Token bí mật đưa vào link "Hủy đăng ký" trong mỗi email.
  add column if not exists unsubscribe_token uuid not null default gen_random_uuid(),
  -- Double opt-in: chỉ người đã xác nhận mới nhận digest.
  -- Ở BẢN TEST (chưa có domain) mặc định TRUE để nhận ngay; khi bật
  -- double opt-in thật thì đổi default về FALSE (xem runbook).
  add column if not exists confirmed boolean not null default true,
  add column if not exists confirmed_at timestamptz,
  -- Khác NULL nghĩa là đã hủy đăng ký → không gửi nữa.
  add column if not exists unsubscribed_at timestamptz;

-- Mỗi token là duy nhất để tra cứu khi hủy.
create unique index if not exists newsletter_subscribers_token_key
  on public.newsletter_subscribers (unsubscribe_token);

-- 2. LOG CÁC LẦN GỬI -------------------------------------------
create table if not exists public.newsletter_sends (
  id              bigint generated always as identity primary key,
  subject         text not null,
  article_count   int  not null default 0,
  recipient_count int  not null default 0,
  ok_count        int  not null default 0,
  error_count     int  not null default 0,
  window_start    timestamptz,
  window_end      timestamptz,
  detail          jsonb,
  created_at      timestamptz not null default now()
);

alter table public.newsletter_sends enable row level security;
-- Không có policy → chỉ service_role (edge function) ghi/đọc được;
-- anon key hoàn toàn không đụng tới bảng log.

-- 3. HÀM HỦY ĐĂNG KÝ THEO TOKEN ---------------------------------
-- Gọi bằng service_role trong edge function `unsubscribe`. SECURITY DEFINER
-- để chạy dưới quyền chủ sở hữu, bỏ qua RLS một cách có kiểm soát.
create or replace function public.newsletter_unsubscribe(p_token uuid)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  v_found boolean;
begin
  update public.newsletter_subscribers
     set unsubscribed_at = now()
   where unsubscribe_token = p_token
     and unsubscribed_at is null;
  get diagnostics v_found = row_count;
  return v_found > 0;
end;
$$;
