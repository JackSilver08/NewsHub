export const SECTION_OPTIONS = [
  {
    slug: 'home-hero',
    label: 'Trang chủ - Hero chính',
    description: 'Bài lớn nhất ở đầu trang chủ.',
  },
  {
    slug: 'home-side',
    label: 'Trang chủ - Cột tin bên phải hero',
    description: 'Ba bài nhỏ cạnh hero chính.',
  },
  {
    slug: 'breaking-news',
    label: 'Trang chủ - Tin nóng',
    description: 'Dòng ticker chạy ngang dưới hero.',
  },
  {
    slug: 'latest-news',
    label: 'Trang chủ - Cập nhật mới nhất',
    description: 'Lưới bài mới ở khu vực nội dung chính.',
  },
  {
    slug: 'popular-sidebar',
    label: 'Trang chủ - Đọc nhiều',
    description: 'Danh sách đọc nhiều ở sidebar.',
  },
  {
    slug: 'ai-daily-brief',
    label: 'Trang chủ - AI Daily Brief',
    description: 'Khối tóm tắt AI nổi bật.',
  },
  {
    slug: 'tech-trends',
    label: 'Trang chủ - Xu hướng công nghệ',
    description: 'Lưới xu hướng phía dưới AI Daily Brief.',
  },
] as const;

export const SECTION_SLUGS = SECTION_OPTIONS.map((section) => section.slug) as [
  (typeof SECTION_OPTIONS)[number]['slug'],
  ...(typeof SECTION_OPTIONS)[number]['slug'][],
];

export type SectionSlug = (typeof SECTION_OPTIONS)[number]['slug'];
