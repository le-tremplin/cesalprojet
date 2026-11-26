-- Le Tremplin · base de données des fiches (Supabase / PostgreSQL)
-- À coller une seule fois dans Supabase : SQL Editor → New query → Run.
-- Rôles : lecteur (consultation), admin (droits accordés par le propriétaire : fiches, budget, photos),
--         proprietaire (tous les droits, gère les rôles). Le contenu prérempli est dans le dépôt (data/fiches/) ;
--         la base ne contient que les corrections faites par les comptes autorisés.

-- ---------------------------------------------------------------- profils (rôle de chaque compte)
create table if not exists public.profils (
  id uuid primary key references auth.users(id) on delete cascade,
  nom text,
  role text not null default 'lecteur'
);
alter table public.profils add column if not exists email text;
alter table public.profils add column if not exists permissions jsonb not null default '{}'::jsonb;
alter table public.profils drop constraint if exists profils_role_check;
update public.profils set role = 'admin', permissions = '{"fiches": true}' where role = 'editeur';
alter table public.profils add constraint profils_role_check check (role in ('lecteur', 'admin', 'proprietaire'));
alter table public.profils enable row level security;

-- chaque compte créé reçoit un profil « lecteur »
create or replace function public.nouveau_profil() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.profils (id, email) values (new.id, new.email) on conflict (id) do update set email = excluded.email;
  return new;
end $$;
drop trigger if exists nouveau_profil on auth.users;
create trigger nouveau_profil after insert on auth.users for each row execute function public.nouveau_profil();
insert into public.profils (id, email) select id, email from auth.users on conflict (id) do update set email = excluded.email;

create or replace function public.role_courant() returns text
language sql stable security definer set search_path = public as $$
  select coalesce((select role from public.profils where id = auth.uid()), 'lecteur')
$$;

create or replace function public.a_droit(droit text) returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce((select role = 'proprietaire' or (role = 'admin' and coalesce((permissions ->> droit)::boolean, false))
                   from public.profils where id = auth.uid()), false)
$$;

drop policy if exists "profil lisible par son titulaire" on public.profils;
create policy "profil lisible par son titulaire" on public.profils
  for select using (id = auth.uid() or public.role_courant() = 'proprietaire');
drop policy if exists "profils gérés par l'admin" on public.profils;
drop policy if exists "profils gérés par le propriétaire" on public.profils;
create policy "profils gérés par le propriétaire" on public.profils
  for update using (public.role_courant() = 'proprietaire') with check (public.role_courant() = 'proprietaire');

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
  for select using (public.role_courant() = 'proprietaire');

create or replace function public.fiches_avant_maj() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if not public.a_droit('budget')
     and coalesce(new.contenu -> 'budget', 'null'::jsonb) is distinct from coalesce(old.contenu -> 'budget', 'null'::jsonb) then
    raise exception 'Modification du budget non autorisée pour ce compte';
  end if;
  if not public.a_droit('fiches') and (new.contenu - 'budget') is distinct from (old.contenu - 'budget') then
    raise exception 'Modification des fiches non autorisée pour ce compte';
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
  if not public.a_droit('budget') and coalesce((new.contenu -> 'budget' ->> 'modifie')::boolean, false) then
    raise exception 'Modification du budget non autorisée pour ce compte';
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
  for insert with check (public.a_droit('fiches') or public.a_droit('budget'));
drop policy if exists "fiches mises à jour par éditeurs et admins" on public.fiches;
create policy "fiches mises à jour par éditeurs et admins" on public.fiches
  for update using (public.a_droit('fiches') or public.a_droit('budget')) with check (public.a_droit('fiches') or public.a_droit('budget'));
drop policy if exists "fiches supprimées par l'admin" on public.fiches;
create policy "fiches supprimées par l'admin" on public.fiches
  for delete using (public.role_courant() = 'proprietaire');

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
  for all using (public.a_droit('photos')) with check (public.a_droit('photos'));

-- stockage des fichiers : lecture publique, écriture réservée à l'admin
insert into storage.buckets (id, name, public) values ('photos', 'photos', true)
  on conflict (id) do nothing;
drop policy if exists "photos : envoi admin" on storage.objects;
create policy "photos : envoi admin" on storage.objects
  for insert with check (bucket_id = 'photos' and public.a_droit('photos'));
drop policy if exists "photos : modification admin" on storage.objects;
create policy "photos : modification admin" on storage.objects
  for update using (bucket_id = 'photos' and public.a_droit('photos'));
drop policy if exists "photos : suppression admin" on storage.objects;
create policy "photos : suppression admin" on storage.objects
  for delete using (bucket_id = 'photos' and public.a_droit('photos'));

-- ---------------------------------------------------------------- propriétaire du projet
-- 1. Authentication → Users → Add user (e-mail + mot de passe, « Auto confirm ») pour chaque membre.
-- 2. Désigner le propriétaire (une seule fois, remplacer l'e-mail) :
--    update public.profils set role = 'proprietaire', nom = 'Prénom Nom' where email = 'adresse@exemple.fr';
-- 3. Ensuite, le propriétaire gère les rôles et les droits depuis le site (bouton « Utilisateurs » d'une fiche).
