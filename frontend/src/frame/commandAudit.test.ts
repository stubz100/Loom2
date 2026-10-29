// D32 audit as a test (D68, ArtCraft P6): every command any module registers has a mouse placement, a label and a parseable chord,
// ids are unique, each chord matches its own key event, and no two commands of one scope share a chord unless the pair is listed
// below with the reason their `when`s are exclusive (handleKeyFor skips disabled matches, review F3).
//
// The registering modules are found by reading the sources, so a new `registerCommands([...])` anywhere under src/ joins the audit.
import { beforeAll, describe, expect, it, vi } from 'vitest'
import type { Suite } from '../api/types'
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
const REGISTERING = Object.keys(SOURCES).filter((p) => p !== './commands.ts' && /\bregisterCommands\(\s*[[\w]/.test(SOURCES[p]))   // D90: also `registerCommands(cmds)` (storyCommands.ts was missed)

const SCOPES: Scope[] = ['global', 'catalogue', 'generate', 'edit', 'animate', 'stage', 'story', 'models', 'world', 'shots']   // D90 (01 §11.7): Stage and Story joined
const PLACEMENTS: Placement[] = ['context', 'toolbar', 'strip', 'panel', 'inspector', 'topbar', 'rail', 'dock']

type Chord = ReturnType<typeof import('./commands').parseChord>
const norm = (c: Chord) => `${c.ctrl ? 'ctrl+' : ''}${c.alt ? 'alt+' : ''}${c.shift ? 'shift+' : ''}${c.key}`
const chordsOf = (c: Command) => [c.keys, ...(c.alt ?? [])].filter((k): k is string => !!k)

/** The ids of commands without a usable mouse placement (D32: a keyboard-only command must not exist). */
function missingPlacement(cmds: Command[]): string[] {
  return cmds.filter((c) => !Array.isArray(c.placement) || c.placement.length === 0 || c.placement.some((p) => !PLACEMENTS.includes(p))).map((c) => c.id)
}
// D90 (01 §11.3, 02 §8.3): declared placements against the sources. A right-click menu names its entries as `{ cmd: 'id' }` /
// `cmdItem('id')` (or a template such as `edit.tool.${t}`), so a command that declares `context` must be named so somewhere. This is a
// static check — it cannot tell whether the menu is reachable in some state — but it is exact about what it checks and never flaky.
// The other placements are not checked here: buttons render ids from tables and templates (`global.suite.${id}`, `edit.ai.${op}`) that
// a source scan cannot resolve honestly; the dev build's `unusedCommands` covers them at run time.
/** Commands a context menu cannot name, each with the reason. */
const NO_MENU: Record<string, string> = {
  'global.contextMenu': 'it is the key that opens the focused element\'s context menu (Shift+F10 / the Menu key), not an entry in one',
}
/** The command ids the sources name as menu entries: literals, and the prefixes of template ids. */
function menuRefs(text: string): { ids: Set<string>; prefixes: string[] } {
  return { ids: new Set([...text.matchAll(/(?:\bcmd:\s*|\bcmdItem\(\s*)'([^']+)'/g)].map((m) => m[1])),
    prefixes: [...text.matchAll(/(?:\bcmd:\s*|\bcmdItem\(\s*)`([^`$]+)\$\{/g)].map((m) => m[1]).filter((p) => p.length > 3) }
}
/** Commands that declare `context` but no menu names (minus NO_MENU). */
function contextOrphans(cmds: Command[], refs: ReturnType<typeof menuRefs>): string[] {
  return cmds.filter((c) => c.placement.includes('context') && !NO_MENU[c.id] && !refs.ids.has(c.id) && !refs.prefixes.some((p) => c.id.startsWith(p))).map((c) => c.id)
}
/** `markUsed('id')` by hand in a file that never renders, runs or lists that id itself — a placement claimed, not made (01 §11.3: Story
 *  and Stage marked commands used that nothing showed). The id must occur in the same file as a literal outside the markUsed call. */
function handMarks(sources: Record<string, string>): string[] {
  const out: string[] = []
  for (const [path, s] of Object.entries(sources)) for (const m of s.matchAll(/\bmarkUsed\('([^']+)'\)/g)) {
    const lit = (re: string) => [...s.matchAll(new RegExp(re, 'g'))].length
    const esc = m[1].replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    if (lit(`['"\`]${esc}['"\`]`) - lit(`\\bmarkUsed\\('${esc}'\\)`) < 1) out.push(`${path}: ${m[1]}`)
  }
  return [...new Set(out)]
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

  it('names every command that declares `context` in some right-click menu (D90, 01 §11.3)', () => {
    expect(contextOrphans(all, menuRefs(Object.values(SOURCES).join('\n')))).toEqual([])
    for (const [id, why] of Object.entries(NO_MENU)) { expect(commands.command(id)?.placement, `${id} is not registered`).toContain('context'); expect(why.length).toBeGreaterThan(20) }
  })

  it('flags a declared context home no menu names (the check itself)', () => {
    const cmd = (id: string, placement: Command['placement']) => ({ id, scope: 'edit', label: id, placement, run: () => undefined }) satisfies Command
    const refs = menuRefs("[{ cmd: 'x.listed' }, cmdItem('x.item'), { cmd: `x.tool.${t}` }, cmd('x.notAMenu')]")
    expect(contextOrphans([cmd('x.listed', ['context']), cmd('x.item', ['context']), cmd('x.tool.brush', ['context']), cmd('x.notAMenu', ['context']), cmd('x.button', ['toolbar'])], refs)).toEqual(['x.notAMenu'])
  })

  it('gives Animate one transport and the Episode lane the same keys (D90 02 §8.2 → D121 AW2: Clay, Performance and Final share one set)', () => {
    const TRANSPORT: Record<string, [string, string]> = {                      // normalised chord (' ' is Space): Animate's three levels · the Episode lane
      ' ': ['anim.play', 'story.episode.play'],
      'arrowleft': ['anim.stepBack', 'story.episode.stepBack'], 'arrowright': ['anim.stepForward', 'story.episode.stepForward'],
      'shift+arrowleft': ['anim.back10', 'story.episode.back10'], 'shift+arrowright': ['anim.fwd10', 'story.episode.fwd10'],
      'home': ['anim.home', 'story.episode.home'], 'end': ['anim.end', 'story.episode.end'],
    }
    const own = (id: string) => commands.defaultKeysOf(id)
    for (const [chord, ids] of Object.entries(TRANSPORT)) for (const id of ids) expect(norm(commands.parseChord(own(id)?.keys ?? '')), id).toBe(chord)
    for (const [id, chord] of [['anim.setIn', 'i'], ['anim.setOut', 'o'], ['anim.prevKey', 'alt+arrowleft'], ['anim.nextKey', 'alt+arrowright']]) expect(norm(commands.parseChord(own(id)?.keys ?? '')), id).toBe(chord)
    // the levels' own transports are gone: one command per verb
    const retired = ['stage.anim.play', 'stage.anim.prev', 'stage.anim.next', 'stage.anim.back10', 'stage.anim.fwd10', 'stage.anim.first', 'stage.anim.last', 'stage.anim.setStart', 'stage.anim.setEnd',
      'stage.anim.prevKey', 'stage.anim.nextKey', 'anim.final.play', 'anim.final.stepBack', 'anim.final.stepForward', 'anim.final.home', 'anim.final.end']
    expect(retired.filter((id) => commands.command(id))).toEqual([])
  })

  it("lists at each Animate mode what its keys reach, and no two scopes a mode joins share a chord (D121)", async () => {
    const { TRANSPORT_IDS } = await import('../suites/animate/transport')
    const at = (suite: Suite) => commands.commandsAt(suite).map((c) => c.id)
    const shared = (id: string) => TRANSPORT_IDS.has(id) || /^anim\.(level|step|for)\./.test(id)
    // Final: its own commands, the mode keys, the Shot head's and the one transport, nothing of Performance's
    expect(at('final')).toEqual(expect.arrayContaining(['anim.final.render', 'anim.play', 'anim.prevKey', 'anim.level.clay', 'anim.step.passes', 'anim.for.back']))
    expect(at('final').filter((id) => !id.startsWith('anim.final.') && !shared(id))).toEqual([])
    // Clay: the stage's own, then the shared ones of the animate scope
    expect(at('stage')).toEqual(expect.arrayContaining(['stage.shot.passes', 'anim.play', 'anim.setIn', 'anim.nextKey', 'anim.level.performance', 'anim.level.final']))
    expect(at('stage').filter((id) => !id.startsWith('stage.') && !shared(id))).toEqual([])
    // Performance: the animate scope but Final's
    expect(at('animate')).toEqual(expect.arrayContaining(['anim.run', 'anim.play', 'anim.variations', 'anim.level.final']))
    expect(at('animate').filter((id) => id.startsWith('anim.final.'))).toEqual([])
    expect(at('generate')).toEqual(commands.commandsFor('generate').map((c) => c.id))   // a suite without a reach: its own scope
    // a reach joins scopes, and its key hook answers with the first match: a chord two of them shared would hide the second
    const clash: string[] = []
    for (const suite of ['stage', 'animate', 'final'] as Suite[]) {
      const cmds = commands.commandsAt(suite)
      for (const a of cmds) for (const b of cmds) {
        if (a.id >= b.id || a.scope === b.scope) continue
        const bn = new Set(chordsOf(b).map((k) => norm(commands.parseChord(k))))
        for (const k of chordsOf(a)) if (bn.has(norm(commands.parseChord(k)))) clash.push(`${suite} ${k}: ${a.id}, ${b.id}`)
      }
    }
    expect(clash).toEqual([])
    // the stage's own mode keys are gone: anim.level.* reach every mode
    expect(['stage.level.performance', 'stage.level.final'].filter((id) => commands.command(id))).toEqual([])
  })

  it('marks a command used by hand only where the same file renders, runs or lists it (D90, 01 §11.3)', () => {
    expect(handMarks(SOURCES)).toEqual([])
    expect(handMarks({ 'a.tsx': "markUsed('x.shown'); <CommandButton id=\"x.shown\" /> markUsed('x.claimed')", 'b.tsx': "markUsed('y.run'); runCommand('y.run')" })).toEqual(['a.tsx: x.claimed'])
  })
})
