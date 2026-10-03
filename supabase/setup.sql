-- IRTC member database: one table holds every member-feature document.
-- Paste this whole file into Supabase > SQL Editor and click Run.

create table if not exists public.docs (
  coll       text        not null check (coll in ('members','projects','posts','meetings','rsvps','dm','likes','connections','private')),
  id         text        not null,
  data       jsonb       not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (coll, id)
);

alter table public.docs enable row level security;

-- The webmaster (site owner) can tidy up other members' shared posts, projects and meetings.
create or replace function public.irtc_is_admin() returns boolean
language sql stable as $$
  select coalesce(auth.jwt() ->> 'email', '') = 'douggarceau@gmail.com'
$$;

-- Who may touch a document: its owner, or the webmaster for shared documents.
-- Private documents (encryption keys, saved items, read receipts) belong to one member only.
create or replace function public.irtc_can_write(c text, i text) returns boolean
language sql stable as $$
  select case
    when c = 'private' then split_part(i, '/', 1) = auth.uid()::text
    else i = auth.uid()::text or public.irtc_is_admin()
  end
$$;

drop policy if exists irtc_read   on public.docs;
drop policy if exists irtc_insert on public.docs;
drop policy if exists irtc_update on public.docs;
drop policy if exists irtc_delete on public.docs;

-- Signed-in members can read shared documents; private ones only by their owner.
create policy irtc_read on public.docs for select to authenticated
  using (coll <> 'private' or split_part(id, '/', 1) = auth.uid()::text);
create policy irtc_insert on public.docs for insert to authenticated
  with check (public.irtc_can_write(coll, id));
create policy irtc_update on public.docs for update to authenticated
  using (public.irtc_can_write(coll, id)) with check (public.irtc_can_write(coll, id));
create policy irtc_delete on public.docs for delete to authenticated
  using (public.irtc_can_write(coll, id));

-- Visitors who are not signed in get nothing.
revoke all on public.docs from anon;
grant select, insert, update, delete on public.docs to authenticated;

-- Live updates (new messages, friend requests, posts) without reloading.
do $$ begin
  alter publication supabase_realtime add table public.docs;
exception when duplicate_object then null; end $$;
