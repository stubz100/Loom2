// 17 §3d (D85): the Flow's node vocabulary, shared by the canvas, the panel and the Inspector (a leaf module: no components).
import type { FlowNode } from '../../../api/types'

export const NODE_LABEL: Record<FlowNode['type'], string> = { start: 'Start', hub: 'Hub', choice: 'Choice', condition: 'Condition', action: 'Action', shot: 'Shot', jump: 'Jump', comment: 'Note' }
/** U2 (D157, G5): one Shot node — a Shot with words to speak is what a Dialogue node was (voicing, lip-sync, its speakers, the board's Lines). */
export const hasLines = (n: Pick<FlowNode, 'type' | 'lines'> | null | undefined): boolean => !!n && n.type === 'shot' && n.lines.some((l) => l.text.trim())
export const NODE_TYPES = Object.keys(NODE_LABEL) as FlowNode['type'][]
