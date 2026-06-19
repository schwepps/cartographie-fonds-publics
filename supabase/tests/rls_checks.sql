-- RLS verification (FSC-17). Proves the public-read posture holds: anon can
-- SELECT every curated table and call graph_neighbors, but cannot write.
-- Run via `make db-verify`. Everything happens in one rolled-back transaction,
-- so no rows persist. Any failed assertion raises -> psql exits non-zero -> CI red.
--
-- Expects a Supabase-like database: the anon role and its baseline table grants
-- must exist (Supabase provides them; for a bare Postgres, first apply
-- supabase/tests/supabase_roles.sql).
\set ON_ERROR_STOP on
begin;

-- Seed one throwaway row as the privileged (migration) role, which owns the
-- tables and bypasses RLS, so anon has a real row to (fail to) tamper with.
insert into entities (siren, name, level) values ('000000001', 'RLS probe', 'state');

set local role anon;

do $$
declare
  t text;
  n int;
begin
  -- 1. anon can SELECT every curated table (public-read policy present).
  foreach t in array array['entities','edges','budget_facts','contracts','attributions','mentions']
  loop
    execute format('select count(*) from %I', t);
  end loop;

  -- 2. anon can call the graph RPC (execute granted in 0002_graph_functions.sql).
  perform * from public.graph_neighbors('000000001', 1);

  -- 2b. anon can call the search RPC (execute granted in 0009_search_entities.sql).
  perform * from public.search_entities('probe', 10);

  -- 3. anon cannot INSERT: no write policy, so WITH CHECK fails (SQLSTATE 42501).
  begin
    insert into entities (siren, name, level) values ('000000002', 'should fail', 'state');
    raise exception 'RLS FAIL: anon INSERT into entities succeeded';
  exception
    when insufficient_privilege then null;  -- expected
  end;

  -- 4. anon UPDATE matches zero rows: the SELECT-only policy's USING filters the
  --    seeded row out, so the write is a silent no-op rather than an error.
  update entities set name = 'tampered' where siren = '000000001';
  get diagnostics n = row_count;
  if n <> 0 then
    raise exception 'RLS FAIL: anon UPDATE modified % row(s)', n;
  end if;

  -- 5. anon DELETE matches zero rows, for the same reason.
  delete from entities where siren = '000000001';
  get diagnostics n = row_count;
  if n <> 0 then
    raise exception 'RLS FAIL: anon DELETE removed % row(s)', n;
  end if;

  raise notice 'RLS OK: anon read + graph_neighbors allowed; INSERT/UPDATE/DELETE blocked.';
end $$;

reset role;
rollback;
