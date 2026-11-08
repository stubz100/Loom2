// The editor's tools (10 §4) as data: a leaf module the frame can import without pulling in the editor (D69 lazy suites).
export const TOOL_IDS = ['move', 'marquee', 'lasso', 'wand', 'quick', 'heal', 'ai', 'brush', 'eraser', 'fill', 'text', 'eyedropper', 'crop', 'hand', 'zoom'] as const
export type Tool = (typeof TOOL_IDS)[number]

/** review K116: the canvas's pointer per tool (it was the system arrow for every tool): a box under a free transform answers on its own. */
export function toolCursor(tool: Tool, o: { transform?: boolean; alt?: boolean } = {}): string {
  if (o.transform) return 'default'
  if (tool === 'move') return 'move'
  if (tool === 'hand') return 'grab'
  if (tool === 'zoom') return o.alt ? 'zoom-out' : 'zoom-in'
  if (tool === 'text') return 'text'
  return 'crosshair'
}
/** review K116: the diameter (document px) of the footprint ring the canvas draws at the pointer — the brush and the eraser, Spot Healing
 *  and Quick Selection; 0 for the other tools. */
export function toolFootprint(tool: Tool, s: { brush: { size: number }; healSize: number; quickSize: number }): number {
  if (tool === 'brush' || tool === 'eraser') return s.brush.size
  if (tool === 'heal') return s.healSize
  if (tool === 'quick') return s.quickSize
  return 0
}
