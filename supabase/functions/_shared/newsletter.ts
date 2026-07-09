// Tiện ích dùng chung cho các edge function bản tin:
//  - parseRssItems(): đọc RSS feed đã build của NewsHub (đã gộp bài markdown +
//    Supabase) và trả về danh sách bài, không phụ thuộc bài nằm ở nguồn nào.
//  - renderDigestHtml(): dựng email HTML responsive, inline style (bắt buộc với
//    email client), mang thương hiệu NewsHub.

export interface FeedItem {
  title: string;
  link: string; // đã là URL tuyệt đối
  description: string;
  category: string;
  pubDate: Date;
}

const BRAND = {
  dark: '#131b2e',
  purple: '#4648d4',
  purpleSoft: '#6063ee',
  cyan: '#22d3ee',
  muted: '#7c839b',
  paper: '#f4f5f8',
};

/** Bóc nội dung trong CDATA hoặc text thường, đã giải mã entity cơ bản. */
function unwrap(raw: string): string {
  const cdata = raw.match(/<!\[CDATA\[([\s\S]*?)\]\]>/);
  const value = cdata ? cdata[1] : raw;
  return value
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, '&')
    .trim();
}

function tag(itemXml: string, name: string): string {
  const m = itemXml.match(new RegExp(`<${name}[^>]*>([\\s\\S]*?)</${name}>`, 'i'));
  return m ? unwrap(m[1]) : '';
}

/**
 * Parse RSS 2.0 của @astrojs/rss. `link` trong feed là đường dẫn tương đối
 * (/article/...) nên ta ghép với siteUrl thành URL tuyệt đối cho email.
 */
export function parseRssItems(xml: string, siteUrl: string): FeedItem[] {
  const base = siteUrl.replace(/\/$/, '');
  const items: FeedItem[] = [];

  for (const block of xml.matchAll(/<item>([\s\S]*?)<\/item>/g)) {
    const itemXml = block[1];
    const rawLink = tag(itemXml, 'link');
    const link = rawLink.startsWith('http')
      ? rawLink
      : `${base}${rawLink.startsWith('/') ? '' : '/'}${rawLink}`;
    const pub = tag(itemXml, 'pubDate');
    const firstCategory = tag(itemXml, 'category');

    items.push({
      title: tag(itemXml, 'title'),
      link,
      description: tag(itemXml, 'description'),
      category: firstCategory,
      pubDate: pub ? new Date(pub) : new Date(0),
    });
  }

  return items;
}

/** Lọc bài có pubDate trong `days` ngày gần nhất, mới nhất trước. */
export function recentItems(items: FeedItem[], days: number): FeedItem[] {
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  return items
    .filter((it) => it.pubDate.getTime() >= cutoff)
    .sort((a, b) => b.pubDate.getTime() - a.pubDate.getTime());
}

function esc(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export interface DigestOptions {
  items: FeedItem[];
  siteUrl: string;
  unsubscribeUrl: string;
  intro?: string;
}

/** Dựng HTML email digest. Bảng + inline style để tương thích email client. */
export function renderDigestHtml({ items, siteUrl, unsubscribeUrl, intro }: DigestOptions): string {
  const site = siteUrl.replace(/\/$/, '');
  const dateLabel = new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(new Date());

  const articleRows = items
    .map(
      (it) => `
    <tr>
      <td style="padding:0 0 22px;">
        <a href="${esc(it.link)}" style="text-decoration:none;color:inherit;">
          ${
            it.category
              ? `<span style="display:inline-block;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:${BRAND.purple};margin-bottom:6px;">${esc(it.category)}</span><br>`
              : ''
          }
          <span style="font-size:18px;font-weight:800;line-height:1.35;color:${BRAND.dark};">${esc(it.title)}</span>
        </a>
        <p style="margin:8px 0 0;font-size:14px;line-height:1.6;color:#475569;">${esc(it.description)}</p>
        <a href="${esc(it.link)}" style="display:inline-block;margin-top:10px;font-size:13px;font-weight:700;color:${BRAND.purple};text-decoration:none;">Đọc tiếp →</a>
      </td>
    </tr>
    <tr><td style="border-top:1px solid #e6e8ef;font-size:0;line-height:0;">&nbsp;</td></tr>`,
    )
    .join('');

  return `<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>Bản tin NewsHub</title>
</head>
<body style="margin:0;padding:0;background:${BRAND.paper};">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">Tóm tắt tin công nghệ &amp; AI nổi bật tuần qua từ NewsHub.</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:${BRAND.paper};padding:24px 12px;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,${BRAND.purple} 0%,${BRAND.dark} 100%);padding:28px 32px;">
            <a href="${site}" style="text-decoration:none;color:#fff;font-size:22px;font-weight:900;letter-spacing:-.02em;">News<span style="color:${BRAND.cyan};">Hub</span></a>
            <p style="margin:6px 0 0;color:#c7cbe6;font-size:13px;">Bản tin tuần &middot; ${dateLabel}</p>
          </td>
        </tr>

        <!-- Intro -->
        <tr>
          <td style="padding:28px 32px 8px;">
            <h1 style="margin:0 0 6px;font-size:20px;color:${BRAND.dark};">Tin công nghệ &amp; AI nổi bật tuần qua</h1>
            <p style="margin:0;font-size:14px;line-height:1.6;color:#475569;">${esc(intro ?? 'Những bài viết đáng chú ý nhất trên NewsHub trong 7 ngày qua, chọn lọc để bạn không bỏ lỡ.')}</p>
          </td>
        </tr>

        <!-- Articles -->
        <tr>
          <td style="padding:20px 32px 8px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              ${articleRows}
            </table>
          </td>
        </tr>

        <!-- CTA -->
        <tr>
          <td align="center" style="padding:8px 32px 32px;">
            <a href="${site}" style="display:inline-block;background:${BRAND.purple};color:#fff;font-size:14px;font-weight:800;text-decoration:none;padding:12px 24px;border-radius:10px;">Xem tất cả trên NewsHub</a>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:${BRAND.dark};padding:24px 32px;">
            <p style="margin:0 0 8px;color:#c7cbe6;font-size:12px;line-height:1.6;">
              Bạn nhận email này vì đã đăng ký bản tin định kỳ của NewsHub.
            </p>
            <p style="margin:0;color:${BRAND.muted};font-size:12px;line-height:1.6;">
              <a href="${esc(unsubscribeUrl)}" style="color:${BRAND.cyan};text-decoration:underline;">Hủy đăng ký</a>
              &nbsp;&middot;&nbsp; NewsHub &middot; Dự án minh hoạ
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>`;
}

/** Phiên bản text thuần (nhiều email client & anti-spam ưa chuộng có kèm). */
export function renderDigestText({ items, siteUrl, unsubscribeUrl }: DigestOptions): string {
  const lines = [
    'NEWSHUB — Bản tin tuần',
    'Tin công nghệ & AI nổi bật tuần qua:',
    '',
  ];
  for (const it of items) {
    lines.push(`• ${it.title}`);
    lines.push(`  ${it.link}`);
    lines.push('');
  }
  lines.push(`Xem tất cả: ${siteUrl.replace(/\/$/, '')}`);
  lines.push(`Hủy đăng ký: ${unsubscribeUrl}`);
  return lines.join('\n');
}
