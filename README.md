# NewsHub

Static news portal về công nghệ / AI, xây bằng **Astro + Content Collections + Decap CMS**, deploy trên **Vercel**. Không cần backend/database ở v1 — tất cả bài viết là file Markdown trong repo.

## Tính năng

- Trang chủ render bài viết từ Markdown (Hero, Breaking ticker, Cập nhật mới nhất, Xu hướng, Đọc nhiều, AI Daily Brief).
- Trang chi tiết bài viết `/article/[slug]` với ảnh, tags, bài liên quan, nút **Copy link** và **Lưu bài** (localStorage), JSON-LD `NewsArticle`.
- Trang chuyên mục `/category/[slug]`.
- Trang tìm kiếm/lọc phía client `/search` (theo tiêu đề, tóm tắt, chuyên mục, tags — không dấu vẫn tìm được).
- Admin CMS tại `/admin` (Decap CMS) để thêm/sửa/xóa bài.
- SEO: meta + Open Graph theo từng trang, canonical, sitemap (`/sitemap-index.xml`), RSS (`/rss.xml`), semantic HTML.
- Responsive, chỉ một `<h1>` mỗi trang, card dùng `h2/h3`.

## Cấu trúc

```
src/
  pages/       index, article/[slug], category/[slug], search, 404, rss.xml
    api/       newsletter.ts.example  (khung serverless cho sau này)
  layouts/     BaseLayout.astro, ArticleLayout.astro
  components/  Header, Footer, ArticleCard, HeroNews, BreakingTicker,
               PopularList, CategoryNav, SearchBox
  content/     posts/*.md
  content.config.ts (schema)
  lib/         posts.ts, categories.ts, sections.ts
  styles/      global.css
public/
  admin/       index.html + config.yml (Decap CMS)
  assets/      logo + ảnh bài viết
  uploads/     nơi CMS lưu ảnh tải lên
astro.config.mjs · vercel.json
```

## Chạy local

```bash
npm install
npm run dev        # http://localhost:4321
```

Các lệnh khác: `npm run build` (xuất ra `dist/`), `npm run preview` (xem thử bản build).

### Sửa bài bằng CMS ở local (không cần GitHub)

`local_backend: true` đã bật sẵn. Mở **2 terminal**:

```bash
# terminal 1
npm run dev
# terminal 2
npx decap-server
```

Rồi mở `http://localhost:4321/admin/`. Thay đổi được ghi thẳng vào `src/content/posts`.

## Content model (frontmatter)

Mỗi bài là `src/content/posts/<slug>.md`:

```yaml
title, slug, excerpt, category, tags, author,
publishedAt, updatedAt?, readingTime?, image, imageAlt,
featured, trending, sections, sectionPriority, popularScore, draft
```

Chuyên mục hợp lệ: `ai`, `thiet-bi`, `startup`, `an-ninh-mang`, `lap-trinh`, `cloud`, `danh-gia`
(khai báo tại `src/lib/categories.ts` và `src/content.config.ts` — giữ đồng bộ khi thêm mới).
Bài có `draft: true` bị ẩn khi build production, vẫn hiện khi chạy `npm run dev`.

## Khu vực hiển thị trên trang chủ

Admin có thể chọn trường `Khu vực hiển thị` trong Decap CMS để đưa một bài vào đúng vùng biên tập. Một bài có thể xuất hiện ở nhiều vùng, và `Ưu tiên trong khu vực` càng cao thì bài càng được xếp trước.

Các vùng hiện có:

- `home-hero`: Hero chính đầu trang.
- `home-side`: Cột tin bên phải hero.
- `breaking-news`: Thanh Tin nóng.
- `latest-news`: Lưới Cập nhật mới nhất.
- `popular-sidebar`: Sidebar Đọc nhiều.
- `ai-daily-brief`: Section AI Daily Brief.
- `tech-trends`: Lưới Xu hướng công nghệ.

Nếu không chọn vùng nào, trang chủ vẫn tự lấy bài theo fallback hiện tại như ngày đăng, chuyên mục, `featured`, `trending` và `popularScore`.

## Deploy lên Vercel

1. Push project lên GitHub (`git init`, commit, push).
2. Trên Vercel: **New Project → Import** repo. Vercel tự nhận framework **Astro**
   (Build `npm run build`, Output `dist`). Không cần chỉnh gì thêm.
3. Sau khi có domain, cập nhật `site` trong `astro.config.mjs` (dùng cho canonical/OG/sitemap)
   và URL sitemap trong `public/robots.txt`.

## Cấu hình Decap CMS với GitHub

`public/admin/config.yml` dùng `backend: github`. Cần một OAuth client để đăng nhập trên production:

1. Sửa `repo: your-username/newshub` thành repo thật của bạn (và `branch` nếu khác `main`).
2. Tạo **GitHub OAuth App** (Settings → Developer settings → OAuth Apps):
   - Homepage URL: domain Vercel của bạn.
   - Authorization callback URL: URL của OAuth proxy (bước 3).
3. Deploy một OAuth proxy cho Decap. Cách nhanh nhất là dùng
   [`decap-proxy`](https://github.com/sterris/decap-proxy) hoặc
   [`netlify-cms-oauth-provider`](https://github.com/ublabs/netlify-cms-github-oauth-provider)
   (chạy được trên Vercel/Cloudflare). Điền `Client ID`/`Client Secret` của OAuth App vào proxy.
4. Thêm dòng trỏ tới proxy trong `config.yml` dưới `backend`:
   ```yaml
   base_url: https://<oauth-proxy-của-bạn>
   auth_endpoint: /auth
   ```
5. Mở `https://<domain>/admin/` → **Login with GitHub**.

> Đang bật `publish_mode: editorial_workflow` → CMS tạo Pull Request cho mỗi bài (nháp → duyệt → publish).
> Muốn commit thẳng, xoá dòng đó trong `config.yml`.

## Mở rộng serverless sau này

Xem `src/pages/api/newsletter.ts.example` — hướng dẫn bật `@astrojs/vercel`, chuyển
`output: 'server'` và thêm route `/api/newsletter` khi cần xử lý form/động.
