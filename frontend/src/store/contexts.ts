// U1 (D157, proto01_UI2 06 §5.3, seam 4): the singletons' context instances. The Make panel, the open stage and the composition are one each
// today; a layer that works in several contexts (an entity version's Make, a shot's stage, a final's composition) keeps each context's state
// under its key. A slot saves the state when its key is left and restores it when the key is entered again; a key never seen starts from what
// is on screen, as today — so nothing changes until a layer names its contexts.

export interface ContextSlot<T> {
  /** The context entered last, or null. */
  readonly key: string | null
  /** Enter a context: the current one's state is kept under its key, the entered one's restored (a new key keeps what is there). */
  enter(key: string): void
  /** Drop a context's saved state (a deleted entity, a removed shot). */
  forget(key: string): void
  /** A context's saved state, if it has one. */
  saved(key: string): T | undefined
}

/** A slot over a singleton: `read` copies its state out, `write` puts a saved state back. */
export function contextSlot<T>(read: () => T, write: (v: T) => void): ContextSlot<T> {
  const kept = new Map<string, T>()
  let current: string | null = null
  return {
    get key() { return current },
    enter(key) {
      if (key === current) return
      if (current !== null) kept.set(current, read())
      current = key
      const back = kept.get(key)
      if (back !== undefined) write(back)
    },
    forget(key) { kept.delete(key); if (key === current) current = null },
    saved: (key) => kept.get(key),
  }
}
