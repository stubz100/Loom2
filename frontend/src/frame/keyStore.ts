// D72 (ArtCraft P16): the user's key overrides, `{commandId: chord | null}` (null = no key), kept on this machine under `loom2.keys`
// with a schema version. A leaf module: the registry applies the overrides as commands register, `keymap.ts` edits them.
// Browser storage can be missing or throw (a private window, a blocked profile): every access is guarded, and no overrides is the default.

export const KEYS_STORAGE = 'loom2.keys'
export const KEYS_SCHEMA = 1
export type Overrides = Record<string, string | null>

interface Stored { schema_version: number; keys: Overrides }

/** Parse what is stored: the current shape, or a bare `{id: chord}` map (written before the schema version existed). Anything else is
 *  dropped, and so is any entry that is not a string or null. */
export function migrateOverrides(raw: unknown): Overrides {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {}
  const r = raw as Partial<Stored> & Record<string, unknown>
  const map = typeof r.schema_version === 'number' ? (r.keys ?? {}) : (r as Record<string, unknown>)
  if (!map || typeof map !== 'object' || Array.isArray(map)) return {}
  const out: Overrides = {}
  for (const [id, v] of Object.entries(map)) if (typeof v === 'string' || v === null) out[id] = v
  return out
}

export function loadOverrides(): Overrides {
  try { const s = localStorage.getItem(KEYS_STORAGE); return s ? migrateOverrides(JSON.parse(s)) : {} } catch { return {} }
}

export function saveOverrides(o: Overrides): void {
  try {
    if (Object.keys(o).length) localStorage.setItem(KEYS_STORAGE, JSON.stringify({ schema_version: KEYS_SCHEMA, keys: o } satisfies Stored))
    else localStorage.removeItem(KEYS_STORAGE)
  } catch { /* not persisted: the override still applies for this session */ }
}
