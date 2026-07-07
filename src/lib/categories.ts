export interface Category {
  slug: string;
  label: string;
  description: string;
}

// Ordered list used for the main navigation and category pages.
export const CATEGORIES: Category[] = [
  { slug: 'ai', label: 'AI', description: 'Trí tuệ nhân tạo, mô hình ngôn ngữ, ứng dụng AI' },
  { slug: 'thiet-bi', label: 'Thiết bị', description: 'Laptop, điện thoại, phần cứng và gadget' },
  { slug: 'startup', label: 'Startup', description: 'Khởi nghiệp công nghệ, gọi vốn, mô hình mới' },
  { slug: 'an-ninh-mang', label: 'An ninh mạng', description: 'Bảo mật, mã độc, quyền riêng tư dữ liệu' },
  { slug: 'lap-trinh', label: 'Lập trình', description: 'Ngôn ngữ, framework, công cụ cho developer' },
  { slug: 'cloud', label: 'Cloud', description: 'Điện toán đám mây, hạ tầng và DevOps' },
  { slug: 'danh-gia', label: 'Đánh giá', description: 'Trải nghiệm và đánh giá sản phẩm công nghệ' },
];

const BY_SLUG = new Map(CATEGORIES.map((c) => [c.slug, c]));

export function categoryLabel(slug: string): string {
  return BY_SLUG.get(slug)?.label ?? slug;
}

export function getCategory(slug: string): Category | undefined {
  return BY_SLUG.get(slug);
}
