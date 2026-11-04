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
    const clipThumb = v.clip_id ? x.clipsById[v.clip_id]?.asset_id : undefined
    const thumb = v.frame_asset_id || clipThumb || x.cards[r.shot.id]?.take_asset_id || null   // W52: the board's take when this shot's clips are not loaded
    return { ...r, n: i + 1, label: r.node?.title || r.shot.name, v, thumb, dots: { clay: c.stage.state, performance: (c.clip.state !== 'na' ? c.clip : c.frame).state, final: c.final.state } }
  })
}

export interface PlayItem { shot: string; n: number; label: string; kind: 'final' | 'performance' | 'animatic' | 'still' | 'none'; asset: string | null; seconds: number }

/** C4 (04 §4.4, "the storyboard plays"): each card's current picture in the route's order — the final's render where there is one (the
 *  version's clip when it is a composition's render), else the performance's take, else the animatic, else the frame still — for the
 *  shot's length (the card's, else the picture's own, else two seconds). ArtCraft's filmstrip on loom2's records: the animatic cut before
 *  Episode has anything. */
export function boardPlaylist(rows: RouteRow[], clipsById: Record<string, Pick<Clip, 'asset_id' | 'frames' | 'fps' | 'model_id'>>, cards: Record<string, Pick<ShotCard, 'length_s'>>): PlayItem[] {
  return rows.map((r) => {
    const v = r.v
    const clip = v.clip_id ? clipsById[v.clip_id] : undefined
    const a = (v as { animatic?: { asset_id: string | null; frames: number; fps: number } | null }).animatic
    const length = cards[r.shot.id]?.length_s ?? null
    const secs = (own: number | null) => Math.max(0.5, length ?? own ?? 2)
    if (clip?.asset_id) return { shot: r.shot.id, n: r.n, label: r.label, kind: clip.model_id === 'composition' ? 'final' : 'performance', asset: clip.asset_id, seconds: secs(clip.fps ? clip.frames / clip.fps : null) }
    if (a?.asset_id) return { shot: r.shot.id, n: r.n, label: r.label, kind: 'animatic', asset: a.asset_id, seconds: secs(a.fps ? a.frames / a.fps : null) }
    if (v.frame_asset_id) return { shot: r.shot.id, n: r.n, label: r.label, kind: 'still', asset: v.frame_asset_id, seconds: secs(null) }
    return { shot: r.shot.id, n: r.n, label: r.label, kind: 'none', asset: null, seconds: secs(null) }
  })
}

/** The level a shot opens on from the storyboard: the first one it still owes (Clay first), else its Final. */
export const nextLevel = (d: Dots): ShotLevel => d.clay !== 'done' ? 'clay' : d.performance !== 'done' && d.performance !== 'na' ? 'performance' : 'final'
