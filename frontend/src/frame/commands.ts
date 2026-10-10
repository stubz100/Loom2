// The command registry (07 §3c/§4, D32): every user action is a Command with a label, an optional icon, an
// optional shortcut and at least one mouse placement. Keyboard maps, toolbar buttons, context menus and the help
// overlay all read from here, so a key is only ever an accelerator for something that is also clickable.
// The `placement` tuple is non-empty by type: a command cannot be registered as keyboard-only.
import type { ComponentType } from 'react'

export type Scope = 'global' | 'catalogue' | 'generate' | 'edit' | 'animate' | 'models'
/** Where the command is reachable with the mouse. */
export type Placement = 'context' | 'toolbar' | 'strip' | 'panel' | 'inspector' | 'topbar' | 'rail' | 'dock'
export type IconType = ComponentType<{ size?: number | string; className?: string }>

export interface Command {
  id: string
  scope: Scope
  label: string
  icon?: IconType
  /** Display shortcut, e.g. 'Ctrl+Shift+Z'; `alt` lists other matching chords (layout variants). */
  keys?: string
  alt?: string[]
  placement: [Placement, ...Placement[]]
  /** Enabled predicate; a disabled command still shows (greyed) in menus and toolbars. */
  when?: () => boolean
  run: () => void
  danger?: boolean
  /** Short note shown in the help overlay (e.g. the gesture equivalent). */
  hint?: string
}

const REGISTRY = new Map<string, Command>()
const USED = new Set<string>()

export function registerCommands(cmds: Command[]): void {
  for (const c of cmds) REGISTRY.set(c.id, c)
}
export function command(id: string): Command | undefined { return REGISTRY.get(id) }
export function commandsFor(scope: Scope): Command[] { return [...REGISTRY.values()].filter((c) => c.scope === scope) }
export function isEnabled(c: Command): boolean { try { return c.when ? c.when() : true } catch { return false } }
export function runCommand(id: string): boolean {
  const c = REGISTRY.get(id)
  if (!c || !isEnabled(c)) return false
  c.run()
  return true
}
/** Menus and toolbars call this when they render a command, so the dev audit can list the ones nothing shows. */
export function markUsed(id: string): void { USED.add(id) }
// dev: the headed check (`scripts/edit_headed_check.py tour`) runs every command of a scope through this hook
if (import.meta.env.DEV) (window as unknown as { __loom2Commands?: unknown }).__loom2Commands = { commandsFor, runCommand, isEnabled, command }
export function unusedCommands(scope: Scope): Command[] { return commandsFor(scope).filter((c) => !USED.has(c.id)) }

// ---- shortcuts ---------------------------------------------------------------------------------------------
interface Chord { ctrl: boolean; shift: boolean; alt: boolean; key: string }
const KEY_ALIASES: Record<string, string> = { esc: 'escape', del: 'delete', return: 'enter', space: ' ', plus: '+', minus: '-', up: 'arrowup', down: 'arrowdown', left: 'arrowleft', right: 'arrowright' }

export function parseChord(s: string): Chord {
  const parts = s.split('+').map((p) => p.trim()).filter(Boolean)
  const c: Chord = { ctrl: false, shift: false, alt: false, key: '' }
  // a trailing '+' key (e.g. 'Ctrl++') splits into empty parts; treat it as the '+' key
  if (s.endsWith('++')) c.key = '+'
  for (const p of parts) {
    const l = p.toLowerCase()
    if (l === 'ctrl' || l === 'cmd' || l === 'meta') c.ctrl = true
    else if (l === 'shift') c.shift = true
    else if (l === 'alt' || l === 'option') c.alt = true
    else c.key = KEY_ALIASES[l] ?? l
  }
  return c
}

/** Does the event match the chord? Letters compare case-insensitively; Shift is required only when listed. */
export function matchChord(e: KeyboardEvent, s: string): boolean {
  const c = parseChord(s)
  if ((e.ctrlKey || e.metaKey) !== c.ctrl || e.altKey !== c.alt) return false
  const key = e.key.length === 1 ? e.key.toLowerCase() : e.key.toLowerCase()
  if (c.key.length === 1 && /[a-z0-9]/.test(c.key)) { if (e.shiftKey !== c.shift) return false; return key === c.key }
  // punctuation: Shift may change the produced character ('[' → '{'), so match either the chord or its base
  if (c.key.length === 1) return key === c.key && (c.shift ? e.shiftKey : true)
  if (e.shiftKey !== c.shift) return false
  return key === c.key
}

export function matchesCommand(e: KeyboardEvent, c: Command): boolean {
  if (c.keys && matchChord(e, c.keys)) return true
  return !!c.alt?.some((k) => matchChord(e, k))
}

/** Run the first enabled command of the scope whose shortcut matches; returns true when one ran. Disabled matches are skipped, so two
 * commands can share a key with exclusive `when`s (Enter closes a polygon lasso or applies a transform). */
export function handleKeyFor(scope: Scope, e: KeyboardEvent): boolean {
  for (const c of commandsFor(scope)) {
    if (!c.keys && !c.alt) continue
    if (!matchesCommand(e, c)) continue
    if (!isEnabled(c)) continue
    e.preventDefault()
    c.run()
    return true
  }
  return false
}

/** Compact shortcut text for tooltips and menus. */
export function keyLabel(keys?: string): string {
  if (!keys) return ''
  return keys.replace('Delete', 'Del').replace('Escape', 'Esc').replace('ArrowLeft', '←').replace('ArrowRight', '→').replace('ArrowUp', '↑').replace('ArrowDown', '↓')
}
export function titleFor(c: Command, label = c.label): string { return c.keys ? `${label} (${keyLabel(c.keys)})` : label }

// ---- menus --------------------------------------------------------------------------------------------------
export type MenuItem =
  | { cmd: string; label?: string; checked?: boolean }
  | { label: string; icon?: IconType; keys?: string; run: () => void; disabled?: boolean; danger?: boolean; checked?: boolean }
  | { sep: true }
  | { label: string; icon?: IconType; items: MenuItem[] }
  | { heading: string }

export const sep: MenuItem = { sep: true }
export const cmdItem = (id: string, label?: string): MenuItem => ({ cmd: id, label })
