// D72 (ArtCraft P16): remappable keys. An override replaces a command's chord(s) (`null` removes its key); it is refused when the command's
// key is fixed, when the chord is one of the fixed gesture keys, or when another command that can fire in the same place (same scope, or
// either is global) already answers to it — unless the pair is declared below as never firing together. Mouse placements stay mandatory
// (D32): a key is only ever an accelerator.
import { create } from 'zustand'
import { allCommands, applyKeyOverrides, command, defaultKeysOf, isFixedChord, parseChord, type Command, type Scope } from './commands'
import { loadOverrides, saveOverrides, type Overrides } from './keyStore'

/** Chords two commands may share, each with the reason they never fire together. Sorted ids, normalised chord. The D32 audit test
 *  (commandAudit.test.ts) fails on any other shared chord, and a remap that would create one is refused. */
export const SHARED_KEYS: { scope: Scope; chord: string; ids: [string, string]; why: string; byDispatch?: boolean }[] = [
  { scope: 'edit', chord: 'enter', ids: ['edit.sel.polyClose', 'edit.transform.apply'], why: 'Enter closes an open polygon / magnetic border, else applies an open transform; both are `when`-guarded and the first enabled one runs (F3)' },
  { scope: 'edit', chord: 'escape', ids: ['edit.sel.polyCancel', 'edit.transform.cancel'], why: 'useEditKeys resolves Esc itself (lasso first, then transform) before the registry; the registry entries carry the accelerator for menus' },
  { scope: 'edit', chord: 'delete', ids: ['edit.sel.clear', 'edit.sel.magBack'], why: 'useEditKeys sends Delete to the magnetic lasso while it is active (D59) before handleKeyFor; otherwise only Clear is enabled' },
  { scope: 'edit', chord: 'backspace', ids: ['edit.sel.clear', 'edit.sel.magBack'], why: 'as Delete: the magnetic lasso takes Backspace first while it is active (D59)' },
  // byDispatch: settled by which handler sees the key first, not by `when`
  // D72: keys that lived outside the registry until now
  { scope: 'edit', chord: 'enter', ids: ['edit.cand.keep', 'edit.sel.polyClose'], why: 'with AI candidates showing, Enter keeps the visible one (it is registered first, as useEditKeys did before D72); else it closes an open polygon' },
  { scope: 'edit', chord: 'enter', ids: ['edit.cand.keep', 'edit.transform.apply'], why: 'Use the shown candidate is disabled while a transform is open, Apply only while one is' },
  // D90 (B9): Apply crop needs the Crop tool and a selection, no open transform, polygon or magnetic border
  { scope: 'edit', chord: 'enter', ids: ['edit.cand.keep', 'edit.crop.apply'], why: 'with AI candidates showing, Enter keeps the visible one first (registered first); the next Enter applies the crop' },
  { scope: 'edit', chord: 'enter', ids: ['edit.crop.apply', 'edit.sel.polyClose'], why: 'Apply crop is disabled while a polygon or magnetic border is open, and needs the Crop tool, which never has one' },
  { scope: 'edit', chord: 'enter', ids: ['edit.crop.apply', 'edit.transform.apply'], why: 'Apply crop is disabled while a transform is open, Apply transform only while one is' },
  ...([1, 2, 3, 4] as const).map((n) => ({ scope: 'edit' as const, chord: String(n), ids: [`edit.brush.opacity.${n}`, `edit.cand.${n}`] as [string, string], why: `${n} keeps candidate ${n} while AI candidates show (10 §10), and sets the brush opacity otherwise — the two whens exclude each other` })),
  { scope: 'story', chord: 'delete', ids: ['story.flow.deleteEdge', 'story.world.remove'], byDispatch: true, why: 'each Story tab dispatches only its own commands (storyKeys.ts, D90 B2): Delete removes a World row on World, a connection on Flow' },
  { scope: 'story', chord: 'ctrl+enter', ids: ['story.cast.expand', 'story.shot.next'], byDispatch: true, why: "each Story tab dispatches only its own commands (storyKeys.ts): Ctrl+Enter is Cast's Expand on Cast and the shot's next step on Shots (D125)" },
  { scope: 'animate', chord: 'ctrl+enter', ids: ['anim.final.render', 'anim.run'], why: "D121: each level's primary on Ctrl+Enter — the Final level's render needs the final suite, the Performance card's verb the animate suite (and the Final's key hook dispatches only anim.final.*)" },
  { scope: 'catalogue', chord: 'tab', ids: ['cat.compare.swap', 'global.focus'], byDispatch: true, why: 'Compare listens in the capture phase and stops Tab while it is open (swap); elsewhere Tab is focus mode' },
]

export const normChord = (s: string): string => { const c = parseChord(s); return `${c.ctrl ? 'ctrl+' : ''}${c.alt ? 'alt+' : ''}${c.shift ? 'shift+' : ''}${c.key}` }
export const chordsOf = (c: Pick<Command, 'keys' | 'alt'>): string[] => [c.keys, ...(c.alt ?? [])].filter((k): k is string => !!k)
const overlaps = (a: Scope, b: Scope) => a === b || a === 'global' || b === 'global'
const declared = (a: string, b: string, chord: string) => SHARED_KEYS.some((x) => x.chord === chord && x.ids.includes(a) && x.ids.includes(b))

/** Commands other than `id` that would answer to `chord` where `id` can fire (undeclared pairs only). */
export function conflictsFor(id: string, chord: string, cmds: Command[] = allCommands()): Command[] {
  const me = cmds.find((c) => c.id === id)
  if (!me) return []
  const n = normChord(chord)
  return cmds.filter((c) => c.id !== id && overlaps(c.scope, me.scope) && chordsOf(c).some((k) => normChord(k) === n) && !declared(id, c.id, n))
}

/** A KeyboardEvent as a chord string ('Ctrl+Shift+K', 'G', 'F2', '['), or null for a lone modifier. Punctuation is recorded as the
 *  character it produced (Shift is part of it), letters and named keys with their modifiers. */
export function chordFromEvent(e: Pick<KeyboardEvent, 'key' | 'ctrlKey' | 'metaKey' | 'altKey' | 'shiftKey'>): string | null {
  if (['Control', 'Shift', 'Alt', 'Meta', 'AltGraph', 'CapsLock', 'Dead', 'Unidentified'].includes(e.key)) return null
  const one = e.key.length === 1
  const letter = one && /[a-z0-9]/i.test(e.key)
  const key = e.key === ' ' ? 'Space' : one ? (letter ? e.key.toUpperCase() : e.key) : e.key
  const mods = [e.ctrlKey || e.metaKey ? 'Ctrl' : '', e.altKey ? 'Alt' : '', e.shiftKey && (letter || !one) ? 'Shift' : ''].filter(Boolean)
  return [...mods, key].join('+')
}

interface KeymapState { overrides: Overrides; version: number }
/** The overrides in force; `version` moves on every change so mounted buttons re-render their tooltips. */
export const useKeymap = create<KeymapState>()(() => ({ overrides: loadOverrides(), version: 0 }))

function commit(o: Overrides): void {
  saveOverrides(o)
  applyKeyOverrides(o)
  useKeymap.setState({ overrides: o, version: useKeymap.getState().version + 1 })
}

export type RemapResult = { ok: true } | { ok: false; reason: string; conflict?: Command }

/** Give `id` the chord (`null`: no key). Refused with the reason — the other command's name on a conflict. */
export function remap(id: string, chord: string | null): RemapResult {
  const c = command(id)
  if (!c) return { ok: false, reason: `No command ${id}` }
  if (c.fixed) return { ok: false, reason: `${c.label} keeps its key (${c.keys})` }
  if (chord !== null) {
    if (!parseChord(chord).key) return { ok: false, reason: 'Not a key' }
    if (isFixedChord(chord)) return { ok: false, reason: 'Arrows, Esc, Space and Tab are fixed keys' }
    const other = conflictsFor(id, chord)[0]
    if (other) return { ok: false, reason: `${chord} already does “${other.label}”`, conflict: other }
  }
  const d = defaultKeysOf(id)
  const o = { ...useKeymap.getState().overrides }
  if (chord !== null && d?.keys && !d.alt?.length && normChord(d.keys) === normChord(chord)) delete o[id]   // back to its own key
  else o[id] = chord
  commit(o)
  return { ok: true }
}

export function resetKey(id: string): void { const o = { ...useKeymap.getState().overrides }; delete o[id]; commit(o) }
export function resetAllKeys(): void { commit({}) }
