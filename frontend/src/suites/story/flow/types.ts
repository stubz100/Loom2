// 17 §3d (D85): the Flow's node vocabulary, shared by the canvas, the panel and the Inspector (a leaf module: no components).
import type { FlowNode } from '../../../api/types'

export const NODE_LABEL: Record<FlowNode['type'], string> = { start: 'Start', hub: 'Hub', dialogue: 'Dialogue', choice: 'Choice', condition: 'Condition', action: 'Action', shot: 'Shot', jump: 'Jump', comment: 'Note' }
export const NODE_TYPES = Object.keys(NODE_LABEL) as FlowNode['type'][]
