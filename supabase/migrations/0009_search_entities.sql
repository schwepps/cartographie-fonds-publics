-- Accent-insensitive institution search in-database, exposed to the frontend as a PostgREST RPC
-- (no bespoke API server). The full perimeter is ~150k entities — far past PostgREST's default
-- 1000-row page — so the frontend must search server-side, not fetch-then-filter. Plain `ilike` is
-- accent-sensitive ("hérault" misses "HERAULT"), so we fold accents with `unaccent` on both sides.
-- Client call:
--   supabase.rpc('search_entities', { p_query: 'hérault', p_limit: 200 })
create extension if not exists unaccent;

create or replace function public.search_entities(p_query text, p_limit int default 200)
returns table (siren text, name text, level text, category text, parent_siren text)
language sql stable
set search_path = ''                  -- pin: avoid schema-resolution hijacking (Supabase lint)
as $$
  select e.siren, e.name, e.level, e.category, e.parent_siren
  from public.entities e
  where length(btrim(coalesce(p_query, ''))) > 0
    and (
      public.unaccent(e.name) ilike public.unaccent('%' || p_query || '%')
      or e.siren ilike '%' || p_query || '%'
    )
  order by
    -- prefix matches first (a name that starts with the query beats a mid-string hit), then the
    -- shortest name (the most specific match), then alphabetical for a stable order.
    case when public.unaccent(e.name) ilike public.unaccent(p_query || '%') then 0 else 1 end,
    length(e.name),
    e.name
  limit least(greatest(coalesce(p_limit, 200), 1), 500);
$$;

grant execute on function public.search_entities(text, int) to anon, authenticated;
