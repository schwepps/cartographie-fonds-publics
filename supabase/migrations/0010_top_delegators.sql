-- Top public buyers by delegated amount — the focus options for the Flux (Sankey) screen, exposed
-- as a PostgREST RPC. The funding-flow (financeur → opérateur) layer has no open-data source yet, so
-- the Flux view surfaces the real money it does have: `delegates` edges (public buyer → DECP
-- supplier). Ministries don't hold contracts directly, so the selector must list the actual buyers
-- (collectivités, hospitals, operators) ranked by total delegated euros — an aggregate PostgREST
-- can't express directly. Client call:
--   supabase.rpc('top_delegators', { p_limit: 30 })
create or replace function public.top_delegators(p_limit int default 30)
returns table (siren text, name text, level text, total_eur numeric, contracts bigint)
language sql stable
set search_path = ''                  -- pin: avoid schema-resolution hijacking (Supabase lint)
as $$
  select e.siren, e.name, e.level, sum(d.amount_eur) as total_eur, count(*) as contracts
  from public.edges d
  join public.entities e on e.siren = d.source_siren
  where d.type = 'delegates' and d.amount_eur is not null
  group by e.siren, e.name, e.level
  order by sum(d.amount_eur) desc nulls last
  limit least(greatest(coalesce(p_limit, 30), 1), 200);
$$;

grant execute on function public.top_delegators(int) to anon, authenticated;
