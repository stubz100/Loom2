// U4 (D157, proto01_UI2 04 §2): the storyboard's cards — the route's shots in the Flow's order, each numbered, named after its node, with
// its picture and three level dots read from the board's cells (D125's records). Pure: shots.test.ts.
import type { Clip, Final, FlowGraph, FlowNode, Shot, ShotCard, ShotVersion } from '../../api/types'
import { cellsOf, flowOrder, staleFrom, type CellState, type Row } from '../../suites/story/board'
import type { ShotLevel } from './shotsStore'

export const DOT: Record<CellState, string> = { done: '●', owed: '○', stale: '!', running: '◐', na: '·' }

export interface Dots { clay: CellState; performance: CellState; final: CellState }
export interface RouteRow extends Row { n: number; label: string; v: ShotVersion; thumb: string | null; dots: Dots }

export interface RouteInput {
  flowGraph: Pick<FlowGraph, 'start' | 'edges'> | null
  flowNodes: Record<string, FlowNode>
  shots: Shot[]
  finals: Final[]
  cuts: { clips: { shot_id: string | null; shot_version: string | null; clip_id: string }[] }[]
  clipsById: Record<string, Clip>
  cards: Record<string, ShotCard>
}

/** The shots the route reaches (an unbound shot is left to the old board), in order: Clay is the stage, Performance the clip (else the
 *  frame, on a route that makes one), Final the assembled final shot. */
export function routeRows(x: RouteInput): RouteRow[] {
  const stale = staleFrom(x.cards)
  return flowOrder(x.flowGraph, x.flowNodes, x.shots).filter((r) => r.group !== 'Unbound').map((r, i) => {
    const v = r.shot.versions.find((y) => y.id === r.shot.current) ?? r.shot.versions[0]
    const c = cellsOf(r.shot, v, r.node, { clipAudio: (id) => (x.clipsById[id] ? !!x.clipsById[id].audio_asset_id : undefined), finals: x.finals, cuts: x.cuts, busy: () => new Set(), stale })
    const thumb = v.frame_asset_id ?? (v.clip_id ? x.clipsById[v.clip_id]?.asset_id ?? null : null)
    return { ...r, n: i + 1, label: r.node?.title || r.shot.name, v, thumb, dots: { clay: c.stage.state, performance: (c.clip.state !== 'na' ? c.clip : c.frame).state, final: c.final.state } }
  })
}

/** The level a shot opens on from the storyboard: the first one it still owes (Clay first), else its Final. */
export const nextLevel = (d: Dots): ShotLevel => d.clay !== 'done' ? 'clay' : d.performance !== 'done' && d.performance !== 'na' ? 'performance' : 'final'
