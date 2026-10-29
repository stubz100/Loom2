// D125 (S4, S8; proto01_UIcomp 04 §3.6, §4; SP7): the verbs that work on the episode — *Make the Flow from the spine…* (a Start, then one
// Shot node per beat not yet made, laid out in a row, connected in the spine's order) and *Voice all lines (N)* (every Dialogue line not
// voiced yet or changed since). Pure: episodeVerbs.test.ts.
import type { FlowGraph, FlowNode, StoryBeat } from '../../api/types'

/** The beats with no node made from them (a node keeps its `beat_id`), in the spine's order. */
export const spineTodo = (spine: StoryBeat[], nodes: FlowNode[]): StoryBeat[] => spine.filter((b) => !nodes.some((n) => n.beat_id === b.id))

const STEP = 280, ROW = 200

/** Where the new nodes go: a row under what the Flow already holds — the Start first when it needs one, then the beats left to right. */
export function spineRow(placed: FlowGraph['nodes'], beats: number, withStart: boolean): { start: { x: number; y: number } | null; beats: { x: number; y: number }[] } {
  const y = placed.length ? Math.max(...placed.map((p) => p.y)) + ROW : 0
  return { start: withStart ? { x: 0, y } : null, beats: Array.from({ length: beats }, (_, i) => ({ x: STEP * (i + 1), y })) }
}

/** How the beats' nodes connect: each made now follows the node of the beat before it (the first beat the Start), and leads into the next
 *  beat's node made before — only where the out-port is free and the next node has no way in yet. `made`: a beat id → its node id. */
export function spineEdges(spine: StoryBeat[], todo: StoryBeat[], edges: FlowGraph['edges'], made: Record<string, string>, start: string | null): { from: string; port: string; to: string }[] {
  const used = new Set(edges.map((e) => `${e.from}:${e.port}`))
  const entered = new Set(edges.map((e) => e.to))
  const out: { from: string; port: string; to: string }[] = []
  const link = (from: string | null | undefined, to: string | undefined) => {
    if (!from || !to || used.has(`${from}:out`) || entered.has(to)) return
    out.push({ from, port: 'out', to }); used.add(`${from}:out`); entered.add(to)
  }
  for (const b of todo) {
    const k = spine.indexOf(b)
    link(k === 0 ? start : made[spine[k - 1].id], made[b.id])
    link(made[b.id], spine[k + 1] ? made[spine[k + 1].id] : undefined)
  }
  return out
}

/** A line not voiced yet, or changed since (the stamp is the stripped text the job spoke). */
export const lineOwesVoice = (l: FlowNode['lines'][number]): boolean => !!l.text.trim() && (!l.audio_asset_id || l.audio_text !== l.text.trim())
/** *Voice all lines (N)*: the episode's lines (its Shots', U2) that owe their voice. */
export const linesToVoice = (nodes: FlowNode[]): number => nodes.filter((n) => n.type === 'shot').reduce((k, n) => k + n.lines.filter(lineOwesVoice).length, 0)
