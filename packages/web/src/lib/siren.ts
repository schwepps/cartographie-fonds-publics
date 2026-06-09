/** SIREN is exactly 9 digits — the canonical join key across every layer. */
export const SIREN_RE = /^\d{9}$/;

/**
 * Trust-boundary guard for a SIREN before it reaches a Supabase filter/RPC. Beyond validation, this
 * stops a raw URL param from being interpolated into a PostgREST `.or(...)` filter string (filter
 * injection). Shared by the entity and graph features so the rule lives in one place.
 */
export function isSiren(value: string): boolean {
  return SIREN_RE.test(value);
}
