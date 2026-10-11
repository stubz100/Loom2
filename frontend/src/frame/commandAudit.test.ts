// D32 audit as a test (D68, ArtCraft P6): every command any module registers has a mouse placement, a label and a parseable chord,
// ids are unique, each chord matches its own key event, and no two commands of one scope share a chord unless the pair is listed
// below with the reason their `when`s are exclusive (handleKeyFor skips disabled matches, review F3).
//
// The registering modules are found by reading the sources, so a new `registerCommands([...])` anywhere under src/ joins the audit.
import { beforeAll, describe, expect, it, vi } from 'vitest'
import type { Command, Placement, Scope } from './commands'
import { SHARED_KEYS } from './keymap'

const seen = vi.hoisted(() => [] as Command[])
vi.mock('./commands', async (importOriginal) => {
  const real = await importOriginal<typeof import('./commands')>()
  return { ...real, registerCommands: (cmds: Command[]) => { seen.push(...cmds); real.registerCommands(cmds) } }
})

// (import.meta.glob takes literals only, so the two pattern lists are spelled out twice)
const SOURCES = import.meta.glob<string>(['../**/*.ts', '../**/*.tsx', '!../**/*.test.ts', '!../**/*.test.tsx', '!../**/*.d.ts', '!../spikes/**'], { query: '?raw', import: 'default', eager: true })
const MODULES = import.meta.glob(['../**/*.ts', '../**/*.tsx', '!../**/*.test.ts', '!../**/*.test.tsx', '!../**/*.d.ts', '!../spikes/**'])
const REGISTERING = Object.keys(SOURCES).filter((p) => p !== './commands.ts' && /\bregisterCommands\(\s*\[/.test(SOURCES[p]))

const SCOPES: Scope[] = ['global', 'catalogue', 'generate', 'edit', 'animate', 'models']
const PLACEMENTS: Placement[] = ['context', 'toolbar', 'strip', 'panel', 'inspector', 'topbar', 'rail', 'dock']

type Chord = ReturnType<typeof import('./commands').parseChord>
const norm = (c: Chord) => `${c.ctrl ? 'ctrl+' : ''}${c.alt ? 'alt+' : ''}${c.shift ? 'shift+' : ''}${c.key}`
const chordsOf = (c: Command) => [c.keys, ...(c.alt ?? [])].filter((k): k is string => !!k)

/** The ids of commands without a usable mouse placement (D32: a keyboard-only command must not exist). */
function missingPlacement(cmds: Command[]): string[] {
  return cmds.filter((c) => !Array.isArray(c.placement) || c.placement.length === 0 || c.placement.some((p) => !PLACEMENTS.includes(p))).map((c) => c.id)
}
/** Every chord two commands can both answer to — same scope, or either is global (D72) — as `scope chord: id, id` (the suite's scope). */
function sharedChords(cmds: Command[], parse: (s: string) => Chord): { scope: Scope; chord: string; ids: string[] }[] {
  const out = new Map<string, { scope: Scope; chord: string; ids: string[] }>()
  for (const a of cmds) for (const b of cmds) {
    if (a.id >= b.id || !(a.scope === b.scope || a.scope === 'global' || b.scope === 'global')) continue
    const bn = new Set(chordsOf(b).map((k) => norm(parse(k))))
    for (const k of chordsOf(a)) {
      const n = norm(parse(k))
      if (!bn.has(n)) continue
      const scope = a.scope === 'global' ? b.scope : a.scope
      out.set(`${scope} ${n} ${a.id} ${b.id}`, { scope, chord: n, ids: [a.id, b.id] })
    }
  }
  return [...out.values()]
}

let commands: typeof import('./commands')
let all: Command[] = []
beforeAll(async () => {
  for (const p of REGISTERING) await MODULES[p]()
  commands = await import('./commands')
  all = SCOPES.flatMap((s) => commands.commandsFor(s))
})

describe('D32 command audit', () => {
  it('finds the registering modules', () => {
    for (const p of ['./globalCommands.ts', '../suites/catalogue/catalogueCommands.ts', '../suites/generate/GenerateSuite.tsx', '../suites/edit/editCommands.ts', '../suites/animate/animateCommands.ts'])
      expect(REGISTERING).toContain(p)
    expect(all.length).toBeGreaterThan(150)
  })

  it('gives every registered command a mouse placement', () => {
    expect(missingPlacement(seen)).toEqual([])
  })

  it('flags a command registered without a placement (the audit itself)', () => {
    const good = { id: 'x.button', scope: 'edit', label: 'Button', keys: 'Q', placement: ['toolbar'], run: () => undefined } satisfies Command
    const bad = { ...good, id: 'x.keyOnly', placement: [] as unknown as Command['placement'] }
    const unknown = { ...good, id: 'x.nowhere', placement: ['menubar'] as unknown as Command['placement'] }
    expect(missingPlacement([good, bad, unknown])).toEqual(['x.keyOnly', 'x.nowhere'])
  })

  it('registers each id once, with a label and a run function', () => {
    const ids = seen.map((c) => c.id)
    expect(ids.filter((id, i) => ids.indexOf(id) !== i)).toEqual([])
    expect(seen.filter((c) => !c.label.trim() || typeof c.run !== 'function').map((c) => c.id)).toEqual([])
  })

  it('spells every chord with a key, and each chord matches its own key event', () => {
    const bad: string[] = []
    for (const c of all) for (const k of chordsOf(c)) {
      const p = commands.parseChord(k)
      if (!p.key) { bad.push(`${c.id}: '${k}' has no key`); continue }
      const e = new KeyboardEvent('keydown', { key: p.key, ctrlKey: p.ctrl, shiftKey: p.shift, altKey: p.alt })
      if (!commands.matchesCommand(e, c)) bad.push(`${c.id}: '${k}' does not match its own event`)
    }
    expect(bad).toEqual([])
  })

  it('shares no chord within a scope except the listed, `when`-guarded pairs', () => {
    const shared = sharedChords(all, commands.parseChord)
    const listed = (s: { scope: Scope; chord: string; ids: string[] }) => SHARED_KEYS.some((a) => a.scope === s.scope && a.chord === s.chord && a.ids.join() === s.ids.join())
    expect(shared.filter((s) => !listed(s)).map((s) => `${s.scope} ${s.chord}: ${s.ids.join(', ')}`)).toEqual([])
    // the allow-list stays honest: every entry still occurs, has a reason, and names commands whose `when` can disable them
    for (const a of SHARED_KEYS) {
      expect(shared.some((s) => s.scope === a.scope && s.chord === a.chord && s.ids.join() === a.ids.join()), `${a.chord}: ${a.ids.join()} no longer shared`).toBe(true)
      expect(a.why.length).toBeGreaterThan(20)
      if (!a.byDispatch) for (const id of a.ids) expect(commands.command(id)?.when, `${id} needs a when`).toBeTypeOf('function')
    }
  })
})
