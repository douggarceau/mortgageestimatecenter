-- Request-to-join: new people ask, the webmaster approves, and only approved members can see member content.
create table if not exists public.join_requests (
  uid         uuid primary key default auth.uid() references auth.users(id) on delete cascade,
  email       text,
  name        text,
  org         text,
  note        text,
  status      text not null default 'pending' check (status in ('pending','approved','denied')),
  created_at  timestamptz not null default now(),
  decided_at  timestamptz
);
alter table public.join_requests enable row level security;

create or replace function public.irtc_is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from auth.users where id = auth.uid() and lower(email) = 'douggarceau@gmail.com')
$$;
create or replace function public.irtc_is_approved() returns boolean
language sql stable security definer set search_path = public as $$
  select public.irtc_is_admin()
      or exists (select 1 from public.join_requests where uid = auth.uid() and status = 'approved')
$$;
create or replace function public.irtc_can_write(c text, i text) returns boolean
language sql stable as $$
  select public.irtc_is_approved() and case
    when c = 'private' then split_part(i, '/', 1) = auth.uid()::text
    else i = auth.uid()::text or public.irtc_is_admin()
  end
$$;

drop policy if exists irtc_read on public.docs;
create policy irtc_read on public.docs for select to authenticated
  using (public.irtc_is_approved() and (coll <> 'private' or split_part(id, '/', 1) = auth.uid()::text));

drop policy if exists jr_read   on public.join_requests;
drop policy if exists jr_insert on public.join_requests;
drop policy if exists jr_update on public.join_requests;
drop policy if exists jr_delete on public.join_requests;
create policy jr_read   on public.join_requests for select to authenticated using (uid = auth.uid() or public.irtc_is_admin());
create policy jr_insert on public.join_requests for insert to authenticated with check (uid = auth.uid() and status = 'pending');
create policy jr_update on public.join_requests for update to authenticated using (public.irtc_is_admin()) with check (public.irtc_is_admin());
create policy jr_delete on public.join_requests for delete to authenticated using (public.irtc_is_admin());
revoke all on public.join_requests from anon;
grant select, insert, update, delete on public.join_requests to authenticated;

-- Everyone who already has an account is approved.
insert into public.join_requests (uid, email, status, decided_at)
  select id, email, 'approved', now() from auth.users
  on conflict (uid) do update set status = 'approved', decided_at = now();
