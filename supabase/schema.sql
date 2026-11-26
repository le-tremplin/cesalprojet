-- Le Tremplin · base de données des fiches (Supabase / PostgreSQL)
-- À coller une seule fois dans Supabase : SQL Editor → New query → Run.
-- Rôles : lecteur (sans compte ou compte sans rôle), editeur (textes des fiches), admin (tout).

-- ---------------------------------------------------------------- profils (rôle de chaque compte)
create table if not exists public.profils (
  id uuid primary key references auth.users(id) on delete cascade,
  nom text,
  role text not null default 'lecteur' check (role in ('lecteur', 'editeur', 'admin'))
);
alter table public.profils enable row level security;

create or replace function public.role_courant() returns text
language sql stable security definer set search_path = public as $$
  select coalesce((select role from public.profils where id = auth.uid()), 'lecteur')
$$;

drop policy if exists "profil lisible par son titulaire" on public.profils;
create policy "profil lisible par son titulaire" on public.profils
  for select using (id = auth.uid() or public.role_courant() = 'admin');
drop policy if exists "profils gérés par l'admin" on public.profils;
create policy "profils gérés par l'admin" on public.profils
  for all using (public.role_courant() = 'admin') with check (public.role_courant() = 'admin');

-- ---------------------------------------------------------------- fiches (un document JSON par local)
create table if not exists public.fiches (
  local_id text primary key,                 -- identifiant stable du local (data/donnees.json)
  contenu jsonb not null default '{}'::jsonb, -- essentiel, actuel, futur, budget
  maj_par text,
  updated_at timestamptz not null default now()
);
alter table public.fiches enable row level security;

-- historique : chaque version remplacée est conservée (rien n'est écrasé sans sauvegarde)
create table if not exists public.fiches_historique (
  id bigint generated always as identity primary key,
  local_id text not null,
  contenu jsonb not null,
  maj_par text,
  version_du timestamptz not null,
  archive_le timestamptz not null default now(),
  archive_par uuid default auth.uid()
);
alter table public.fiches_historique enable row level security;
drop policy if exists "historique lisible par l'admin" on public.fiches_historique;
create policy "historique lisible par l'admin" on public.fiches_historique
  for select using (public.role_courant() = 'admin');

create or replace function public.fiches_avant_maj() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  -- un éditeur ne peut pas modifier le budget
  if public.role_courant() <> 'admin'
     and coalesce(new.contenu -> 'budget', 'null'::jsonb) is distinct from coalesce(old.contenu -> 'budget', 'null'::jsonb) then
    raise exception 'Seul un administrateur peut modifier le budget';
  end if;
  insert into public.fiches_historique (local_id, contenu, maj_par, version_du)
    values (old.local_id, old.contenu, old.maj_par, old.updated_at);
  new.updated_at := now();
  return new;
end $$;
drop trigger if exists fiches_avant_maj on public.fiches;
create trigger fiches_avant_maj before update on public.fiches
  for each row execute function public.fiches_avant_maj();

create or replace function public.fiches_avant_ajout() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if public.role_courant() <> 'admin' and jsonb_array_length(coalesce(new.contenu -> 'budget' -> 'lignes', '[]'::jsonb)) > 0 then
    raise exception 'Seul un administrateur peut saisir un budget';
  end if;
  new.updated_at := now();
  return new;
end $$;
drop trigger if exists fiches_avant_ajout on public.fiches;
create trigger fiches_avant_ajout before insert on public.fiches
  for each row execute function public.fiches_avant_ajout();

drop policy if exists "fiches lisibles par tous" on public.fiches;
create policy "fiches lisibles par tous" on public.fiches for select using (true);
drop policy if exists "fiches modifiables par éditeurs et admins" on public.fiches;
create policy "fiches modifiables par éditeurs et admins" on public.fiches
  for insert with check (public.role_courant() in ('editeur', 'admin'));
drop policy if exists "fiches mises à jour par éditeurs et admins" on public.fiches;
create policy "fiches mises à jour par éditeurs et admins" on public.fiches
  for update using (public.role_courant() in ('editeur', 'admin')) with check (public.role_courant() in ('editeur', 'admin'));
drop policy if exists "fiches supprimées par l'admin" on public.fiches;
create policy "fiches supprimées par l'admin" on public.fiches
  for delete using (public.role_courant() = 'admin');

-- ---------------------------------------------------------------- photos
create table if not exists public.photos (
  id uuid primary key default gen_random_uuid(),
  local_id text not null,
  categorie text not null default 'existant' check (categorie in ('existant', 'futur', 'travaux', 'references', 'autres')),
  legende text,
  date_prise date,
  chemin text not null,                      -- chemin dans le stockage « photos »
  created_at timestamptz not null default now(),
  created_by uuid default auth.uid()
);
create index if not exists photos_local on public.photos (local_id);
alter table public.photos enable row level security;
drop policy if exists "photos lisibles par tous" on public.photos;
create policy "photos lisibles par tous" on public.photos for select using (true);
drop policy if exists "photos gérées par l'admin" on public.photos;
create policy "photos gérées par l'admin" on public.photos
  for all using (public.role_courant() = 'admin') with check (public.role_courant() = 'admin');

-- stockage des fichiers : lecture publique, écriture réservée à l'admin
insert into storage.buckets (id, name, public) values ('photos', 'photos', true)
  on conflict (id) do nothing;
drop policy if exists "photos : envoi admin" on storage.objects;
create policy "photos : envoi admin" on storage.objects
  for insert with check (bucket_id = 'photos' and public.role_courant() = 'admin');
drop policy if exists "photos : modification admin" on storage.objects;
create policy "photos : modification admin" on storage.objects
  for update using (bucket_id = 'photos' and public.role_courant() = 'admin');
drop policy if exists "photos : suppression admin" on storage.objects;
create policy "photos : suppression admin" on storage.objects
  for delete using (bucket_id = 'photos' and public.role_courant() = 'admin');

-- ---------------------------------------------------------------- premier administrateur
-- 1. Authentication → Users → Add user (e-mail + mot de passe), pour chaque membre du groupe.
-- 2. Puis, pour chacun (remplacer l'e-mail et le rôle) :
--    insert into public.profils (id, nom, role)
--      select id, 'Prénom Nom', 'admin' from auth.users where email = 'adresse@exemple.fr'
--      on conflict (id) do update set role = excluded.role, nom = excluded.nom;
