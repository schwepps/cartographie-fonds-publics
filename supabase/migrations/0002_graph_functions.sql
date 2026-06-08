-- Graph traversal in-database, exposed to the frontend as a PostgREST RPC
-- (no bespoke API server). Client call:
--   supabase.rpc('graph_neighbors', { p_siren: '180089013', p_depth: 1 })
create or replace function public.graph_neighbors(p_siren text, p_depth int default 1)
returns table (source_siren text, target_siren text, type text, amount_eur numeric, hop int)
language sql stable
set search_path = ''                  -- pin: avoid schema-resolution hijacking (Supabase lint)
as $$
  with recursive walk as (
    select e.source_siren, e.target_siren, e.type, e.amount_eur, 1 as hop,
           array[e.source_siren, e.target_siren] as visited
    from public.edges e
    where e.source_siren = p_siren or e.target_siren = p_siren
    union all
    select e.source_siren, e.target_siren, e.type, e.amount_eur, w.hop + 1,
           w.visited || array[e.source_siren, e.target_siren]
    from public.edges e
    join walk w on (e.source_siren = w.target_siren or e.target_siren = w.source_siren)
    where w.hop < least(p_depth, 4)   -- cap recursion depth
      -- cycle guard: skip edges already traversed (both endpoints seen) so an
      -- undirected pair A<->B can't re-enter via the reverse join condition.
      and not (e.source_siren = any(w.visited) and e.target_siren = any(w.visited))
  )
  select distinct source_siren, target_siren, type, amount_eur, hop from walk;
$$;
grant execute on function public.graph_neighbors(text, int) to anon, authenticated;
