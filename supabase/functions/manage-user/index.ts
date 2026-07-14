import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const ANON_KEY = Deno.env.get('SUPABASE_ANON_KEY')!;
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;

const corsHeaders = {
  'access-control-allow-origin': 'https://newshub-jack.netlify.app',
  'access-control-allow-headers': 'authorization, x-client-info, apikey, content-type',
  'access-control-allow-methods': 'POST, OPTIONS',
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, 'content-type': 'application/json; charset=utf-8' },
  });
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: corsHeaders });
  if (req.method !== 'POST') return json({ error: 'Chỉ chấp nhận POST.' }, 405);

  const authorization = req.headers.get('authorization') ?? '';
  const token = authorization.replace(/^Bearer\s+/i, '');
  if (!token) return json({ error: 'Bạn chưa đăng nhập.' }, 401);

  const authClient = createClient(SUPABASE_URL, ANON_KEY);
  const { data: callerData, error: callerError } = await authClient.auth.getUser(token);
  if (callerError || !callerData.user) return json({ error: 'Phiên đăng nhập không hợp lệ.' }, 401);

  const adminClient = createClient(SUPABASE_URL, SERVICE_ROLE, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  const { data: callerProfile } = await adminClient
    .from('profiles')
    .select('role')
    .eq('id', callerData.user.id)
    .maybeSingle();
  if (callerProfile?.role !== 'admin') return json({ error: 'Chỉ admin được quản lý tài khoản.' }, 403);

  const body = await req.json().catch(() => ({}));
  const action = String(body.action ?? '');
  const userId = String(body.userId ?? '');
  if (!/^[0-9a-f-]{36}$/i.test(userId)) return json({ error: 'Tài khoản không hợp lệ.' }, 400);

  const { data: targetProfile, error: targetError } = await adminClient
    .from('profiles')
    .select('role, email')
    .eq('id', userId)
    .maybeSingle();
  if (targetError || !targetProfile) return json({ error: 'Không tìm thấy tài khoản.' }, 404);

  if (action === 'password') {
    const password = String(body.password ?? '');
    if (password.length < 8 || password.length > 72) {
      return json({ error: 'Mật khẩu phải có từ 8 đến 72 ký tự.' }, 400);
    }
    const { error } = await adminClient.auth.admin.updateUserById(userId, { password });
    if (error) return json({ error: error.message }, 400);
    return json({ ok: true, message: `Đã đổi mật khẩu cho ${targetProfile.email ?? 'tài khoản'}.` });
  }

  if (action === 'delete') {
    if (targetProfile.role === 'admin') return json({ error: 'Không thể xóa tài khoản admin.' }, 403);
    const { error } = await adminClient.auth.admin.deleteUser(userId);
    if (error) return json({ error: error.message }, 400);
    return json({ ok: true, message: 'Đã xóa tài khoản.' });
  }

  return json({ error: 'Thao tác không được hỗ trợ.' }, 400);
});
