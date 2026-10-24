// RC1 (D96, proto01_animate 28): the recipe graph's layout and what a node opens — pure (graph.test.ts). The server builds the graph from
// the records (GET /story/shots/{sid}/graph); here its nodes go in columns by their longest path from a source (W6: the characters on the
// left, the take on the right), each node naming the place where it is made.
import type { components } from '../../../api/schema'

export type ShotGraph = components['schemas']['ShotGraph']
export type GraphNode = components['schemas']['GraphNode']

export const NODE_W = 196, NODE_H = 148
const GAP_X = 64, GAP_Y = 26

/** Each node's column (its longest path from a source) and row (the server's order within the column), and its place on the canvas. */
export function layout(g: Pick<ShotGraph, 'nodes' | 'edges'>): Record<string, { col: number; row: number; x: number; y: number }> {
  const col: Record<string, number> = {}
  for (const n of g.nodes) col[n.id] = Math.max(0, ...g.edges.filter((e) => e.to === n.id && e.from in col).map((e) => col[e.from] + 1))   // the server sends them inputs first
  const rows: Record<number, number> = {}
  const out: Record<string, { col: number; row: number; x: number; y: number }> = {}
  for (const n of g.nodes) {
    const c = col[n.id], r = rows[c] ?? 0
    rows[c] = r + 1
    out[n.id] = { col: c, row: r, x: c * (NODE_W + GAP_X), y: r * (NODE_H + GAP_Y) }
  }
  return out
}

/** Where a node is made: Story › Cast (a character, its animation reference, a place), the Flow (the lines), Animate's modes and their
 *  sections (the stage, a figure's motion, the camera at Clay; the clip, the plate and the layers at Performance; the composition, the
 *  finish and the take at Final), Image (the frame), or the shot's page. */
export type Target =
  | { kind: 'cast'; profileId: string; version: string | null }
  | { kind: 'flow'; nodeId: string }
  | { kind: 'shots' }
  | { kind: 'clay'; section: 'scene' | 'motion' | 'camera'; stageId?: string; objectId?: string; cameraId?: string }
  | { kind: 'performance'; card: 'i2v' | 'clip' | 'final' }
  | { kind: 'final'; section: 'layers' | 'output' }
  | { kind: 'image' }

export function targetOf(n: Pick<GraphNode, 'kind' | 'ref'>, g: Pick<ShotGraph, 'route' | 'final_id'>): Target {
  const r = n.ref
  switch (n.kind) {
    case 'character': case 'prop': case 'anim_ref': case 'place': return { kind: 'cast', profileId: r.profile_id, version: r.version || null }
    case 'lines': return { kind: 'flow', nodeId: r.node_id }
    case 'stage': return { kind: 'clay', section: 'scene', stageId: r.stage_id }
    case 'motion': return { kind: 'clay', section: 'motion', stageId: r.stage_id, objectId: r.object_id }
    case 'camera': return { kind: 'clay', section: 'camera', stageId: r.stage_id, cameraId: r.camera_id }
    case 'frame': return { kind: 'image' }
    case 'clip': return { kind: 'performance', card: g.route === 'stage' ? 'clip' : 'i2v' }
    case 'plate': case 'layer': return { kind: 'performance', card: 'final' }
    case 'composition': case 'finish': return { kind: 'final', section: 'layers' }
    case 'take': return g.final_id ? { kind: 'final', section: 'output' } : { kind: 'shots' }
    default: return { kind: 'shots' }
  }
}

export const STATE_LABEL: Record<GraphNode['state'], string> = { done: 'done', stale: 'stale', owed: 'owed', running: 'running', none: '–' }
