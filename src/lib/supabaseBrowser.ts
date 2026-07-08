import { createClient, type SupabaseClient } from '@supabase/supabase-js';

// Client Supabase dùng ở trình duyệt (auth + comments). PUBLIC_* được Astro
// nội tuyến vào bundle phía client khi build.
const url = import.meta.env.PUBLIC_SUPABASE_URL as string | undefined;
const anonKey = import.meta.env.PUBLIC_SUPABASE_ANON_KEY as string | undefined;

export const supabaseConfigured = Boolean(url && anonKey);

// Một instance duy nhất cho mỗi trang → session tự lưu ở localStorage và được
// chia sẻ giữa các trang (khóa mặc định `sb-<ref>-auth-token`).
export const supabaseBrowser: SupabaseClient = createClient(
  url ?? 'https://placeholder.supabase.co',
  anonKey ?? 'placeholder-anon-key',
);

export const ADMIN_EMAIL = 'admin@newshub.com';

export type UserRole = 'user' | 'moderator' | 'admin';

export interface CurrentUser {
  id: string;
  email: string;
  name: string;
  role: UserRole;
}

/** Lấy user đang đăng nhập kèm role từ bảng profiles; null nếu chưa đăng nhập. */
export async function getCurrentUser(): Promise<CurrentUser | null> {
  const {
    data: { session },
  } = await supabaseBrowser.auth.getSession();
  if (!session) return null;

  const { user } = session;
  const { data: profile } = await supabaseBrowser
    .from('profiles')
    .select('name, role')
    .eq('id', user.id)
    .maybeSingle();

  const role = (profile?.role as UserRole) || 'user';
  const name =
    profile?.name ||
    (user.user_metadata?.name as string | undefined) ||
    (user.email ? user.email.split('@')[0] : 'Người dùng');

  return { id: user.id, email: user.email ?? '', name, role };
}
