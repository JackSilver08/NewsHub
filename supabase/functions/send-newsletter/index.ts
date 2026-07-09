// ────────────────────────────────────────────────────────────────────────────
// Edge Function: send-newsletter
//
// Chạy định kỳ (pg_cron) hoặc gọi tay để gửi digest hàng tuần:
//   1. Tải RSS đã build của NewsHub → danh sách bài (gộp markdown + Supabase).
//   2. Lọc bài trong N ngày gần nhất (mặc định 7).
//   3. Lấy subscriber đã xác nhận & chưa hủy.
//   4. Render email HTML + text, gửi hàng loạt qua Resend (kèm link hủy riêng).
//   5. Ghi log vào newsletter_sends.
//
// Bảo vệ bằng header  x-cron-secret: <CRON_SECRET>.
//
// Gọi tay để test (chỉ gửi tới email của bạn ở bản test chưa có domain):
//   POST … { "testEmail": "you@gmail.com", "days": 3650, "dryRun": false }
//   - testEmail: ghi đè người nhận (bỏ qua bảng subscribers).
//   - days:      nới cửa sổ thời gian để bài demo cũ vẫn lọt vào.
//   - dryRun:    true → không gửi, chỉ trả về những gì SẼ gửi.
// ────────────────────────────────────────────────────────────────────────────

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';
import { parseRssItems, recentItems, renderDigestHtml, renderDigestText } from '../_shared/newsletter.ts';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const RESEND_API_KEY = Deno.env.get('RESEND_API_KEY') ?? '';
const CRON_SECRET = Deno.env.get('CRON_SECRET') ?? '';
const FROM = Deno.env.get('NEWSLETTER_FROM') ?? 'NewsHub <onboarding@resend.dev>';
const SITE_URL = (Deno.env.get('SITE_URL') ?? 'https://newshub-jack.netlify.app').replace(/\/$/, '');
const DEFAULT_DAYS = Number(Deno.env.get('DIGEST_DAYS') ?? '7');

const UNSUB_BASE = `${SUPABASE_URL}/functions/v1/unsubscribe`;

interface Recipient {
  email: string;
  token: string;
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8' },
  });
}

async function sendResendBatch(
  emails: Array<Record<string, unknown>>,
): Promise<{ ok: number; error: number; detail: unknown }> {
  const res = await fetch('https://api.resend.com/emails/batch', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${RESEND_API_KEY}`,
      'content-type': 'application/json',
    },
    body: JSON.stringify(emails),
  });
  const detail = await res.json().catch(() => ({}));
  if (!res.ok) return { ok: 0, error: emails.length, detail };
  const sent = Array.isArray((detail as any)?.data) ? (detail as any).data.length : emails.length;
  return { ok: sent, error: emails.length - sent, detail };
}

Deno.serve(async (req) => {
  if (req.method !== 'POST') return json({ error: 'Chỉ chấp nhận POST' }, 405);

  // Xác thực secret (cron & gọi tay đều phải kèm header này).
  if (!CRON_SECRET || req.headers.get('x-cron-secret') !== CRON_SECRET) {
    return json({ error: 'Không được phép' }, 401);
  }
  if (!RESEND_API_KEY) return json({ error: 'Thiếu RESEND_API_KEY' }, 500);

  const body = await req.json().catch(() => ({} as any));
  const days = Number(body.days ?? DEFAULT_DAYS);
  const dryRun = Boolean(body.dryRun);
  const testEmail: string | undefined = body.testEmail;

  // 1. Tải & lọc bài.
  const rssRes = await fetch(`${SITE_URL}/rss.xml`, { headers: { accept: 'application/xml' } });
  if (!rssRes.ok) return json({ error: `Không tải được RSS (${rssRes.status})` }, 502);
  const xml = await rssRes.text();
  const all = parseRssItems(xml, SITE_URL);
  let items = recentItems(all, days);

  // Khi gọi tay để test mà cửa sổ không có bài nào → lấy tạm 5 bài mới nhất
  // để bạn vẫn xem được email mẫu.
  if (items.length === 0 && testEmail) {
    items = all.sort((a, b) => b.pubDate.getTime() - a.pubDate.getTime()).slice(0, 5);
  }

  if (items.length === 0) {
    return json({ skipped: true, reason: 'Không có bài mới trong cửa sổ thời gian', days });
  }

  const supabase = createClient(SUPABASE_URL, SERVICE_ROLE);

  // 2. Danh sách người nhận.
  let recipients: Recipient[];
  if (testEmail) {
    recipients = [{ email: testEmail, token: '00000000-0000-0000-0000-000000000000' }];
  } else {
    const { data, error } = await supabase
      .from('newsletter_subscribers')
      .select('email, unsubscribe_token')
      .eq('confirmed', true)
      .is('unsubscribed_at', null);
    if (error) return json({ error: 'Không đọc được subscribers: ' + error.message }, 500);
    recipients = (data ?? []).map((r: any) => ({ email: r.email, token: r.unsubscribe_token }));
  }

  if (recipients.length === 0) {
    return json({ skipped: true, reason: 'Không có người nhận đã xác nhận' });
  }

  const subject = `NewsHub tuần này: ${items[0].title}`;

  if (dryRun) {
    return json({
      dryRun: true,
      subject,
      articleCount: items.length,
      recipientCount: recipients.length,
      articles: items.map((i) => ({ title: i.title, link: i.link, pubDate: i.pubDate })),
    });
  }

  // 3. Dựng & gửi theo lô 100 (giới hạn Resend batch).
  let ok = 0;
  let error = 0;
  let lastDetail: unknown = null;

  for (let i = 0; i < recipients.length; i += 100) {
    const chunk = recipients.slice(i, i + 100);
    const emails = chunk.map((r) => {
      const unsubscribeUrl = `${UNSUB_BASE}?token=${r.token}`;
      return {
        from: FROM,
        to: r.email,
        subject,
        html: renderDigestHtml({ items, siteUrl: SITE_URL, unsubscribeUrl }),
        text: renderDigestText({ items, siteUrl: SITE_URL, unsubscribeUrl }),
        headers: {
          'List-Unsubscribe': `<${unsubscribeUrl}>`,
          'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
        },
      };
    });
    const r = await sendResendBatch(emails);
    ok += r.ok;
    error += r.error;
    lastDetail = r.detail;
  }

  // 4. Ghi log (bỏ qua khi chỉ test tới 1 email).
  if (!testEmail) {
    await supabase.from('newsletter_sends').insert({
      subject,
      article_count: items.length,
      recipient_count: recipients.length,
      ok_count: ok,
      error_count: error,
      window_end: new Date().toISOString(),
      detail: error > 0 ? lastDetail : null,
    });
  }

  return json({ sent: true, subject, articleCount: items.length, ok, error });
});
