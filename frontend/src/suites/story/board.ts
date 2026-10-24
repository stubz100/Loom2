// D125 (proto01_UIcomp 04 §2.4, §3.1; SP3): the Shots board — every shot in the Flow's order against its steps, each step's state read from
// records that exist (the shot version, its node, its clips, the finals made for it, the cuts). Pure: board.test.ts.
import type { Final, FlowGraph, FlowNode, SceneOut, Shot, ShotCard, ShotVersion } from '../../api/types'

export type Step = 'lines' | 'voice' | 'frame' | 'stage' | 'clip' | 'final' | 'lipsync' | 'approved' | 'cut'
export const STEPS: { id: Step; label: string }[] = [
  { id: 'lines', label: 'Lines' }, { id: 'voice', label: 'Voice' }, { id: 'frame', label: 'Frame' }, { id: 'stage', label: 'Stage' }, { id: 'clip', label: 'Clip' },
  { id: 'final', label: 'Final' }, { id: 'lipsync', label: 'Lip-sync' }, { id: 'approved', label: 'Approved' }, { id: 'cut', label: 'In cut' },
]
/** done ✓ · owed ○ (a click does it) · running ◐ · stale ! (its input changed) · na – (not on this shot's route). */
export type CellState = 'done' | 'owed' | 'running' | 'stale' | 'na'
export interface Cell { state: CellState; text?: string }

/** The shot's route — its recipe template (RC0), else the default RC0 picks: a stage camera's shot is `stage`, any other `i2v`. */
export const routeOf = (v: Pick<ShotVersion, 'recipe' | 'stage_id'>, madeFinal = false): string => v.recipe?.template ?? (madeFinal ? 'clay1' : v.stage_id ? 'stage' : 'i2v')
/** RC1: a final shot made for the shot puts a version without a template on the clay route (a final made before RC1 did not set it). */
export const madeFinal = (shotId: string, finals: Pick<Final, 'shot_id'>[]): boolean => finals.some((f) => f.shot_id === shotId)
export const ROUTE_LABEL: Record<string, string> = { i2v: 'image to video', stage: 'stage clip', clay1: 'clay final shot', clay2: 'clay final shot', dialogue: 'dialogue + lip-sync' }
/** The steps a route owes (04 §2.4); every route also owes Approved and In cut, a Dialogue node's shot its Lines and Voice. */
const OWED: Record<string, Step[]> = { i2v: ['frame', 'clip'], stage: ['stage', 'frame', 'clip'], clay1: ['stage', 'final'], clay2: ['stage', 'final'], dialogue: ['voice', 'frame', 'clip', 'lipsync'] }
export const owes = (route: string, node: Pick<FlowNode, 'type'> | null, step: Step): boolean =>
  step === 'approved' || step === 'cut' || ((step === 'lines' || step === 'voice') && node?.type === 'dialogue') || (OWED[route] ?? OWED.i2v).includes(step)

export interface Row { shot: Shot; node: FlowNode | null; group: string | null }

/** RC2a (proto01_animate 31 §3b): a Shot node that is nothing but its shot — outside the routes (no edge, not the start), no lines, text,
 *  beat, place or board. A shot made elsewhere (*New shot from this camera…*, *Make a shot from this clip…*) is one; another node can take
 *  its shot (bind), and then it goes. The server's `_bare`. */
export const bareNode = (n: Pick<FlowNode, 'id' | 'type' | 'lines' | 'text' | 'beat_id' | 'place_id' | 'board_group_id'>, graph: Pick<FlowGraph, 'start' | 'edges'> | null): boolean =>
  n.type === 'shot' && !n.lines.length && !n.text.trim() && !n.beat_id && !n.place_id && !n.board_group_id && graph?.start !== n.id
  && !(graph?.edges ?? []).some((e) => e.from === n.id || e.to === n.id)
/** RC2a: a shot with something in it (a second version, a source, a frame, a clip, a take, a run) — moved to a node of its own, never
 *  dropped, when its node changes. The server's `ShotPart.untouched`, negated. */
export const hasWork = (s: Pick<Shot, 'versions'>): boolean =>
  s.versions.length > 1 || s.versions.some((v) => v.state === 'final' || !!(v.stage_id || v.frame_asset_id || v.clip_id || v.takes.length || v.recipe?.steps.some((x) => x.runs.length)))

/** The shots in the Flow's order: a walk from the Start along the edges (a node's ports in their order — out, then / else, a Choice's options
 *  as it lists them), each visual node's shot at its first visit; a Choice's or a Condition's branch names the rows under it (the latest
 *  branch wins). Then the shots of nodes off the routes (RC2a: a shot made elsewhere is a Shot node there); a shot without a node (before
 *  RC2a's merge) last. */
export function flowOrder(graph: Pick<FlowGraph, 'start' | 'edges'> | null, nodes: Record<string, FlowNode>, shots: Shot[]): Row[] {
  const byShot = new Map(shots.map((s) => [s.id, s]))
  const out: Row[] = []
  const seen = new Set<string>(), placed = new Set<string>()
  const portRank = (n: FlowNode, port: string): number => {
    if (port === 'out' || port === 'then') return 0
    if (port === 'else') return 1
    const i = n.options.findIndex((o) => `opt:${o.id}` === port)
    return i < 0 ? 99 : i
  }
  const branchName = (n: FlowNode, port: string): string | null => {
    if (n.type === 'choice') { const o = n.options.find((x) => `opt:${x.id}` === port); return `${n.title || 'Choice'} ▸ ${o?.label || 'option'}` }
    if (n.type === 'condition') return `${n.title || 'Condition'} ▸ ${port}`
    return null
  }
  const visit = (id: string, group: string | null): void => {
    if (seen.has(id)) return
    seen.add(id)
    const n = nodes[id]
    if (!n) return
    const s = n.shot_id ? byShot.get(n.shot_id) : undefined
    if (s && (n.type === 'dialogue' || n.type === 'shot') && !placed.has(s.id)) { out.push({ shot: s, node: n, group }); placed.add(s.id) }
    const next = (graph?.edges ?? []).filter((e) => e.from === id).sort((a, b) => portRank(n, a.port) - portRank(n, b.port))
    for (const e of next) visit(e.to, branchName(n, e.port) ?? group)
    if (n.type === 'jump' && n.target) visit(n.target, group)
  }
  if (graph?.start) visit(graph.start, null)
  const rest = shots.filter((s) => !placed.has(s.id)).map((s) => ({ shot: s, node: s.owner_node ? nodes[s.owner_node] ?? null : null }))
  for (const r of rest) if (r.node) out.push({ ...r, group: 'Not on a route' })
  for (const r of rest) if (!r.node) out.push({ ...r, group: 'Unbound' })
  return out
}

export interface CellInput {
  clipAudio: (clipId: string) => boolean | undefined       // the clip carries a line's audio (a lip-sync take); undefined: not loaded
  finals: Pick<Final, 'shot_id' | 'stage_id' | 'camera_id' | 'clip_id' | 'layers'>[]
  cuts: { clips: { shot_id: string | null; shot_version: string | null; clip_id: string }[] }[]
  busy: (shotId: string) => Set<Step>                     // the steps a queued or running job of this shot is making
}

/** Every step's cell for a shot's version (04 §2.4). */
export function cellsOf(s: Shot, v: ShotVersion, node: FlowNode | null, x: CellInput): Record<Step, Cell> {
  const route = routeOf(v, madeFinal(s.id, x.finals))
  const busy = x.busy(s.id)
  const owed = (step: Step): Cell => (busy.has(step) ? { state: 'running' } : owes(route, node, step) ? { state: 'owed' } : { state: 'na' })
  const cells = {} as Record<Step, Cell>
  // lines and voice: a Dialogue node's
  if (node?.type === 'dialogue') {
    const lines = node.lines.filter((l) => l.text.trim())
    cells.lines = lines.length ? { state: 'done', text: String(lines.length) } : { state: 'owed', text: 'none' }
    const voiced = lines.filter((l) => l.audio_asset_id), changed = voiced.filter((l) => l.audio_text !== l.text)
    cells.voice = !lines.length ? { state: 'na' } : busy.has('voice') ? { state: 'running' } : changed.length ? { state: 'stale', text: `${changed.length} changed` }
      : voiced.length === lines.length ? { state: 'done' } : { state: 'owed', text: `${voiced.length} of ${lines.length}` }
  } else { cells.lines = { state: 'na' }; cells.voice = { state: 'na' } }
  cells.frame = v.frame_asset_id ? { state: 'done' } : owed('frame')
  cells.stage = v.stage_id ? { state: 'done' } : owed('stage')
  cells.clip = v.clip_id ? { state: 'done' } : owed('clip')
  const mine = x.finals.filter((f) => f.shot_id === s.id || (!f.shot_id && !!v.stage_id && f.stage_id === v.stage_id && f.camera_id === v.camera_id))
  if (mine.length) {
    const f = mine.find((y) => y.clip_id) ?? mine[0]
    const done = f.layers.filter((l) => l.status === 'done').length
    cells.final = f.clip_id ? { state: 'done', text: 'assembled' } : busy.has('final') ? { state: 'running', text: `${done}/${f.layers.length} layers` } : { state: 'owed', text: `${done}/${f.layers.length} layers` }
  } else cells.final = owed('final')
  cells.lipsync = v.clip_id && x.clipAudio(v.clip_id) ? { state: 'done' } : owed('lipsync')
  cells.approved = v.state === 'final' ? { state: 'done' } : { state: 'owed' }
  const onLane = x.cuts.flatMap((c) => c.clips).filter((c) => c.shot_id === s.id)
  cells.cut = !onLane.length ? { state: 'owed' } : onLane.some((c) => c.shot_version === v.id && c.clip_id === v.clip_id) ? { state: 'done' } : { state: 'stale', text: 'changed' }
  return cells
}

export type BoardSort = 'story' | 'scene' | 'name' | 'length' | 'stale'
export const SORT_LABEL: Record<BoardSort, string> = { story: 'story order', scene: 'by scene', name: 'by name', length: 'longest first', stale: 'most stale first' }

/** RC2d (05 §5: "the Shots tab as a list of Shot nodes — search, sort, state"): the board's rows found by a word (the shot's name, its node's
 *  lines and line, its scene) and put in an order — the story's (the Flow's walk, its branches as headings), by scene (the scenes as
 *  headings, in the story's order of their first Shot; none last), by name, by length (the card's) or by the stale count. */
export function arrange<R extends Row>(rows: R[], q: string, sort: BoardSort, scenes: Pick<SceneOut, 'id' | 'name'>[], cards: Record<string, Pick<ShotCard, 'length_s' | 'stale'>>): R[] {
  const want = q.trim().toLowerCase()
  const sceneName = (r: Row) => (r.node?.scene_id ? scenes.find((s) => s.id === r.node!.scene_id)?.name ?? null : null)
  const found = want ? rows.filter((r) => [r.shot.name, r.node?.title, r.node?.text, sceneName(r), ...(r.node?.lines.map((l) => l.text) ?? [])].some((t) => t?.toLowerCase().includes(want))) : rows
  if (sort === 'story') return found
  if (sort === 'scene') {
    const first = new Map<string, number>()
    found.forEach((r, i) => { const s = sceneName(r) ?? ''; if (!first.has(s)) first.set(s, i) })
    const rank = (r: Row) => { const s = sceneName(r); return s === null ? Infinity : first.get(s)! }
    return found.map((r, i) => ({ r, i })).sort((a, b) => rank(a.r) - rank(b.r) || a.i - b.i).map(({ r }) => ({ ...r, group: sceneName(r) ?? 'No scene' }))
  }
  const key = (r: Row): number | string => sort === 'name' ? r.shot.name.toLowerCase() : sort === 'length' ? -(cards[r.shot.id]?.length_s ?? -1) : -(cards[r.shot.id]?.stale ?? 0)
  return found.map((r, i) => ({ r, i })).sort((a, b) => { const x = key(a.r), y = key(b.r); return x < y ? -1 : x > y ? 1 : a.i - b.i }).map(({ r }) => ({ ...r, group: null }))
}

/** RC2b (D96): a Shot card's length line — seconds to one decimal under a minute, with where it comes from; past the guide (about 30 s) it
 *  warns. Null when nothing gives the shot a length yet. */
export function lengthLine(c: Pick<ShotCard, 'length_s' | 'length_from'> | undefined, guide: number): { text: string; over: boolean; title: string } | null {
  if (!c || c.length_s == null) return null
  const s = c.length_s
  const text = s < 60 ? `${s.toFixed(1)} s` : `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`
  const from = c.length_from === 'clip' ? 'its clip' : c.length_from === 'final' ? 'its final shot' : 'its voiced lines'
  const over = s > guide
  return { text, over, title: over ? `${text} (${from}) — past about ${guide} s: two Shots joined by a transition read better (a guideline, D96)` : `${text} (${from})` }
}

/** The first owed step of a row, in the board's order (Approved and In cut last) — the foot's next step. */
export function nextStep(cells: Record<Step, Cell>): Step | null {
  return STEPS.map((x) => x.id).find((id) => cells[id].state === 'owed' || cells[id].state === 'stale') ?? null
}
