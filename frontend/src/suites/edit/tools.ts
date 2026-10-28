// The editor's tools (10 §4) as data: a leaf module the frame can import without pulling in the editor (D69 lazy suites).
export const TOOL_IDS = ['move', 'marquee', 'lasso', 'wand', 'quick', 'heal', 'ai', 'brush', 'eraser', 'fill', 'text', 'eyedropper', 'crop', 'hand', 'zoom'] as const
export type Tool = (typeof TOOL_IDS)[number]
