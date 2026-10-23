// D125 (proto01_UIcomp 04 §2.4, §3.1; SP3): the Shots board — every shot in the Flow's order against its steps, each step's state read from
// records that exist (the shot version, its node, its clips, the finals made for it, the cuts). Pure: board.test.ts.
import type { Final, FlowGraph, FlowNode, Shot, ShotVersion } from '../../api/types'

export type Step = 'lines' | 'voice' | 'frame' | 'stage' | 'clip' | 'final' | 'lipsync' | 'approved' | 'cut'
export const STEPS: { id: Step; label: string }[] = [
  { id: 'lines', label: 'Lines' }, { id: 'voice', label: 'Voice' }, { id: 'frame', label: 'Frame' }, { id: 'stage', label: 'Stage' }, { id: 'clip', label: 'Clip' },
  { id: 'final', label: 'Final' }, { id: 'lipsync', label: 'Lip-sync' }, { id: 'approved', label: 'Approved' }, { id: 'cut', label: 'In cut' },
]
/** done ✓ · owed ○ (a click does it) · running ◐ · stale ! (its input changed) · na – (not on this shot's route). */
export type CellState = 'done' | 'owed' | 'running' | 'stale' | 'na'
export interface Cell { state: CellState; text?: string }

/** The shot's route — its recipe template (RC0), else the default RC0 picks: a stage camera's shot is `stage`, any other `i2v`. */
export const routeOf = (v: Pick<ShotVersion, 'recipe' | 'stage_id'>): string => v.recipe?.template ?? (v.stage_id ? 'stage' : 'i2v')
export const ROUTE_LABEL: Record<string, string> = { i2v: 'image to video', stage: 'stage clip', clay1: 'clay final shot', clay2: 'clay final shot', dialogue: 'dialogue + lip-sync' }
/** The steps a route owes (04 §2.4); every route also owes Approved and In cut, a Dialogue node's shot its Lines and Voice. */
const OWED: Record<string, Step[]> = { i2v: ['frame', 'clip'], stage: ['stage', 'frame', 'clip'], clay1: ['stage', 'final'], clay2: ['stage', 'final'], dialogue: ['voice', 'frame', 'clip', 'lipsync'] }
export const owes = (route: string, node: Pick<FlowNode, 'type'> | null, step: Step): boolean =>
  step === 'approved' || step === 'cut' || ((step === 'lines' || step === 'voice') && node?.type === 'dialogue') || (OWED[route] ?? OWED.i2v).includes(step)

export interface Row { shot: Shot; node: FlowNode | null; group: string | null }

/** The shots in the Flow's order: a walk from the Start along the edges (a node's ports in their order — out, then / else, a Choice's options
 *  as it lists them), each visual node's shot at its first visit; a Choice's or a Condition's branch names the rows under it (the latest
 *  branch wins). Then the shots of nodes off the routes, then the unbound ones. */
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
  const route = routeOf(v)
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

/** The first owed step of a row, in the board's order (Approved and In cut last) — the foot's next step. */
export function nextStep(cells: Record<Step, Cell>): Step | null {
  return STEPS.map((x) => x.id).find((id) => cells[id].state === 'owed' || cells[id].state === 'stale') ?? null
}
