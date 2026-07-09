# Bản tin định kỳ NewsHub — Hướng dẫn cài đặt

Pipeline gửi digest **hàng tuần** tự động, tất cả trên free-tier:

```
pg_cron (Thứ 2, 7:00 VN)  →  Edge Function send-newsletter
   → đọc /rss.xml (bài mới 7 ngày) → render email → gửi qua Resend → ghi log
Email  →  link "Hủy đăng ký"  →  Edge Function unsubscribe (token)
```

Các file liên quan:

| File | Vai trò |
|------|---------|
| `supabase/migrations/0003_newsletter.sql` | Bảng `newsletter_subscribers` + form footer |
| `supabase/migrations/0004_newsletter_pipeline.sql` | Token hủy, cờ `confirmed`, bảng log `newsletter_sends` |
| `supabase/functions/send-newsletter/` | Gửi digest |
| `supabase/functions/unsubscribe/` | Endpoint hủy đăng ký công khai |
| `supabase/functions/_shared/newsletter.ts` | Parse RSS + template email |
| `supabase/migrations/0005_newsletter_cron.sql.template` | Lịch pg_cron (điền secret rồi chạy tay) |

---

## ⚠️ Trạng thái hiện tại: BẢN TEST (chưa có domain)

Resend chưa xác thực domain nên chỉ gửi được tới **chính email tài khoản Resend của bạn**
(dùng địa chỉ gửi `onboarding@resend.dev`). Đủ để dựng & kiểm thử toàn bộ pipeline.
Khi có domain riêng → xem mục [Lên production](#lên-production), chỉ đổi cấu hình, không sửa code.

---

## Bước 1 — Chạy migration

Trong **Supabase → SQL Editor**, chạy lần lượt (nếu chưa):

1. `0003_newsletter.sql` (đã chạy ✓)
2. `0004_newsletter_pipeline.sql`

## Bước 2 — Tạo tài khoản Resend + API key

1. Đăng ký tại https://resend.com (free 3.000 email/tháng).
2. Vào **API Keys → Create** → copy key `re_...`.
3. Ở bản test, người nhận **bắt buộc** là email bạn đã dùng đăng ký Resend.

## Bước 3 — Cài Supabase CLI & đăng nhập

```powershell
npm install -g supabase        # hoặc dùng "npx supabase ..." ở mọi lệnh
supabase login                 # dán access token từ dashboard
supabase link --project-ref mfwnayxisdsmlppywjir
```

## Bước 4 — Đặt secrets cho Edge Function

`SUPABASE_URL` và `SUPABASE_SERVICE_ROLE_KEY` được Supabase tự inject — **không cần đặt**.
Chỉ đặt các biến sau (thay giá trị của bạn):

```powershell
supabase secrets set `
  RESEND_API_KEY="re_xxx" `
  CRON_SECRET="$(python -c 'import secrets;print(secrets.token_hex(24))')" `
  NEWSLETTER_FROM="NewsHub <onboarding@resend.dev>" `
  SITE_URL="https://newshub-jack.netlify.app" `
  DIGEST_DAYS="7"
```

> Lưu lại `CRON_SECRET` — Bước 6 (pg_cron) cần dùng lại đúng chuỗi này.
> Nếu không có `python`, tự tạo một chuỗi ngẫu nhiên dài ≥ 32 ký tự.

## Bước 5 — Deploy 2 Edge Function

```powershell
supabase functions deploy send-newsletter
supabase functions deploy unsubscribe
```

(`verify_jwt = false` đã khai trong `supabase/config.toml`.)

## Bước 6 — Gửi thử (quan trọng)

Thay `<CRON_SECRET>` và email của bạn. `days` để lớn để bài demo cũ vẫn lọt vào:

```powershell
# a) Dry-run: xem SẼ gửi gì, chưa gửi thật
curl -X POST "https://mfwnayxisdsmlppywjir.supabase.co/functions/v1/send-newsletter" `
  -H "x-cron-secret: <CRON_SECRET>" -H "content-type: application/json" `
  -d '{ "testEmail": "ban@gmail.com", "days": 3650, "dryRun": true }'

# b) Gửi thật tới hộp thư của bạn
curl -X POST "https://mfwnayxisdsmlppywjir.supabase.co/functions/v1/send-newsletter" `
  -H "x-cron-secret: <CRON_SECRET>" -H "content-type: application/json" `
  -d '{ "testEmail": "ban@gmail.com", "days": 3650 }'
```

Mở email → bấm **Hủy đăng ký** để kiểm tra function `unsubscribe` (sẽ đánh dấu dòng
tương ứng, nhưng với `testEmail` thì token là số 0 nên chỉ để xem trang xác nhận).

## Bước 7 — Bật lịch tự động hàng tuần

1. Mở `supabase/migrations/0005_newsletter_cron.sql.template`.
2. Thay `<PROJECT_REF>` = `mfwnayxisdsmlppywjir` và `<CRON_SECRET>` = chuỗi ở Bước 4.
3. Dán vào **SQL Editor** → Run. (Bản đã điền bị `.gitignore` chặn commit.)
4. Kiểm tra: `select jobname, schedule, active from cron.job;`

Xong! Mỗi sáng Thứ Hai hệ thống tự gửi digest nếu có bài mới trong 7 ngày.

---

## Lên production

Khi đã có domain riêng (vd `newshub.io`):

1. **Resend → Domains → Add** domain, thêm bản ghi **DKIM + SPF + DMARC** vào DNS
   (Cloudflare/Namecheap…). Đợi verify xanh.
2. Đổi secret địa chỉ gửi sang domain đã verify:
   ```powershell
   supabase secrets set NEWSLETTER_FROM="NewsHub <bantin@newshub.io>"
   ```
3. **Bật double opt-in** (khuyến nghị, tránh spam trap): sửa default cột `confirmed`
   về `false` và thêm email xác nhận khi đăng ký (một bước nâng cấp riêng).
4. Không cần sửa code gửi — pipeline giữ nguyên, giờ gửi được tới subscriber thật.

## Vận hành

- **Xem log gửi:** `select * from public.newsletter_sends order by created_at desc;`
- **Đếm subscriber đang nhận:**
  `select count(*) from newsletter_subscribers where confirmed and unsubscribed_at is null;`
- **Lịch sử cron:** `select * from cron.job_run_details order by start_time desc limit 10;`
- **Đổi tần suất:** chỉnh biểu thức cron ở Bước 7 (vd `'0 0 * * *'` = mỗi ngày).
