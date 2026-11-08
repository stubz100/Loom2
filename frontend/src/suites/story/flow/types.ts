// 17 §3d (D85): the Flow's node vocabulary, shared by the canvas, the panel and the Inspector (a leaf module: no components).
import type { FlowNode } from '../../../api/types'

export const NODE_LABEL: Record<FlowNode['type'], string> = { start: 'Start', hub: 'Hub', choice: 'Choice', condition: 'Condition', action: 'Action', shot: 'Shot', jump: 'Jump', comment: 'Note' }
/** U2 (D157, G5): one Shot node — a Shot with words to speak is what a Dialogue node was (voicing, lip-sync, its speakers, the board's Lines). */
export const hasLines = (n: Pick<FlowNode, 'type' | 'lines'> | null | undefined): boolean => !!n && n.type === 'shot' && n.lines.some((l) => l.text.trim())
export const NODE_TYPES = Object.keys(NODE_LABEL) as FlowNode['type'][]
/** K116: which nodes the canvas shows selected — its own selection (several: a Ctrl-click, a Shift-drag) while that holds the Story store's
 *  node; else the store's node alone (picked in the outline, by its shot, or none). The store keeps one node, and every rebuild of the
 *  canvas's nodes made it the only one selected. */
export function canvasSelection(own: ReadonlySet<string>, nodeId: string | null): (id: string) => boolean {
  return nodeId && own.has(nodeId) ? (id) => own.has(id) : (id) => id === nodeId
}
