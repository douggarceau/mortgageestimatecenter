-- Photo and video storage for posts: private, approved members only, 50 MB per file.
insert into storage.buckets (id, name, public, file_size_limit)
values ('media', 'media', false, 52428800)
on conflict (id) do update set public = false, file_size_limit = 52428800;
drop policy if exists irtc_media_read   on storage.objects;
drop policy if exists irtc_media_insert on storage.objects;
drop policy if exists irtc_media_delete on storage.objects;
create policy irtc_media_read on storage.objects for select to authenticated
  using (bucket_id = 'media' and public.irtc_is_approved());
create policy irtc_media_insert on storage.objects for insert to authenticated
  with check (bucket_id = 'media' and public.irtc_is_approved() and (storage.foldername(name))[1] = auth.uid()::text);
create policy irtc_media_delete on storage.objects for delete to authenticated
  using (bucket_id = 'media' and ((storage.foldername(name))[1] = auth.uid()::text or public.irtc_is_admin()));
