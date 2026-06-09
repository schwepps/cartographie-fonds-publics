/**
 * Tutelle chain (root ministry → … → entity), walked client-side over `parent_siren`. Shared by the
 * search breadcrumbs, the tutelle facet, and the entity sheet. Pure; guarded against cycles.
 */
export interface ChainEntity {
  siren: string;
  parent_siren?: string | null;
}

export function tutelleChain<E extends ChainEntity>(siren: string, bySiren: Map<string, E>): E[] {
  const chain: E[] = [];
  let current = bySiren.get(siren);
  let guard = 0;
  while (current && guard < 10) {
    chain.unshift(current);
    current = current.parent_siren ? bySiren.get(current.parent_siren) : undefined;
    guard += 1;
  }
  return chain;
}
