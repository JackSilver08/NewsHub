// ────────────────────────────────────────────────────────────────────────────
// Edge Function: unsubscribe   (CÔNG KHAI — deploy với --no-verify-jwt)
//
// Link trong mỗi email: …/functions/v1/unsubscribe?token=<uuid>
//   - GET  → hủy đăng ký rồi hiện trang xác nhận (người dùng bấm từ email).
//   - POST → hỗ trợ "one-click unsubscribe" (RFC 8058) của Gmail/Outlook.
// Dùng hàm SQL newsletter_unsubscribe() nên chỉ đụng đúng 1 dòng theo token.
// ────────────────────────────────────────────────────────────────────────────

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function page(title: string, message: string, status = 200) {
  const html = `<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title} — NewsHub</title></head>
<body style="margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;background:#f4f5f8;">
  <div style="max-width:460px;margin:12vh auto;background:#fff;border-radius:16px;padding:40px 32px;text-align:center;">
    <div style="font-size:22px;font-weight:900;color:#131b2e;margin-bottom:20px;">News<span style="color:#22d3ee;">Hub</span></div>
    <h1 style="font-size:20px;color:#131b2e;margin:0 0 10px;">${title}</h1>
    <p style="font-size:14px;line-height:1.6;color:#475569;margin:0 0 24px;">${message}</p>
    <a href="https://newshub-jack.netlify.app" style="display:inline-block;background:#4648d4;color:#fff;font-weight:800;text-decoration:none;padding:12px 24px;border-radius:10px;font-size:14px;">Về trang chủ NewsHub</a>
  </div>
</body></html>`;
  return new Response(html, {
    status,
    headers: { 'content-type': 'text/html; charset=utf-8' },
  });
}

Deno.serve(async (req) => {
  const url = new URL(req.url);
  const token = url.searchParams.get('token') ?? '';

  if (!UUID_RE.test(token)) {
    return page('Liên kết không hợp lệ', 'Đường link hủy đăng ký không đúng hoặc đã hết hạn.', 400);
  }

  const supabase = createClient(SUPABASE_URL, SERVICE_ROLE);
  const { data, error } = await supabase.rpc('newsletter_unsubscribe', { p_token: token });

  // POST one-click (RFC 8058): client email chỉ cần HTTP 200, không đọc body.
  if (req.method === 'POST') {
    return new Response(null, { status: error ? 500 : 200 });
  }

  if (error) {
    return page('Có lỗi xảy ra', 'Không thể xử lý yêu cầu lúc này, bạn thử lại sau nhé.', 500);
  }
  if (data === true) {
    return page('Đã hủy đăng ký', 'Bạn sẽ không nhận bản tin NewsHub nữa. Cảm ơn bạn đã đồng hành!');
  }
  return page('Bạn đã hủy trước đó', 'Email này không còn trong danh sách nhận bản tin.');
});
