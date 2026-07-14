-- Allow authenticated NewsHub staff to manage article images.
-- The old bootstrap policy targeted only `anon`, so uploads made after signing
-- in were rejected by Storage RLS even when the user was an admin.

insert into storage.buckets (id, name, public)
values ('post-images', 'post-images', true)
on conflict (id) do update set public = excluded.public;

drop policy if exists post_images_insert_staff on storage.objects;
create policy post_images_insert_staff on storage.objects
  for insert
  to authenticated
  with check (
    bucket_id = 'post-images'
    and public.current_user_role() in ('admin', 'moderator')
  );

drop policy if exists post_images_update_staff on storage.objects;
create policy post_images_update_staff on storage.objects
  for update
  to authenticated
  using (
    bucket_id = 'post-images'
    and public.current_user_role() in ('admin', 'moderator')
  )
  with check (
    bucket_id = 'post-images'
    and public.current_user_role() in ('admin', 'moderator')
  );

drop policy if exists post_images_delete_staff on storage.objects;
create policy post_images_delete_staff on storage.objects
  for delete
  to authenticated
  using (
    bucket_id = 'post-images'
    and public.current_user_role() in ('admin', 'moderator')
  );
