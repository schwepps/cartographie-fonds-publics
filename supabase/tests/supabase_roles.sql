-- Test/CI compatibility shim — Supabase provides these roles and grants in
-- production. DO NOT apply to a real Supabase project.
--
-- A bare Postgres (the CI service container, or `make up`) has neither the
-- Supabase roles nor their baseline table grants. Without them, RLS can't be the
-- gate: anon would be rejected for lack of a GRANT, not because of a policy — so
-- the RLS check would prove nothing. Apply this BEFORE `make db-migrate` (as a
-- superuser) so tables created by the migration inherit these grants and RLS
-- becomes the access control actually under test.
--
-- Idempotent: safe to re-run.
do $$
begin
  if not exists (select from pg_roles where rolname = 'anon') then
    create role anon nologin noinherit;
  end if;
  if not exists (select from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin noinherit;
  end if;
  if not exists (select from pg_roles where rolname = 'service_role') then
    create role service_role nologin noinherit bypassrls;
  end if;
end $$;

grant usage on schema public to anon, authenticated, service_role;

-- Tables created LATER by the current role (the migration) inherit these.
alter default privileges in schema public
  grant select, insert, update, delete on tables to anon, authenticated, service_role;
alter default privileges in schema public
  grant execute on functions to anon, authenticated, service_role;

-- Tables/functions that already exist (re-run, or shim applied after migrate).
-- A no-op on a fresh database where nothing has been created yet.
grant select, insert, update, delete on all tables in schema public to anon, authenticated, service_role;
grant execute on all functions in schema public to anon, authenticated, service_role;
