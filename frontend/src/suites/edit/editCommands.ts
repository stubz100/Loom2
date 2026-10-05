// Edit commands (10 §4/§6/§10, 07 §3c): one definition each for the strip icons, the Layers toolbar, the
// canvas and layer right-click menus, the keys and the help overlay.
import { ArrowDown, ArrowUp, Copy, Crop, Eraser, Eye, EyeOff, FileDown, FileImage, FolderInput, FolderPlus, Group, Hand, Lasso, Lock, LockOpen, Maximize, Merge, MousePointer2, PaintBucket, Paintbrush, Pencil, Pipette, Plus, Redo2, RotateCcw, Save, Scan, Shuffle, SlidersHorizontal, Sparkles, Square, SquareCheck, SquareDashed, SquareX, Trash, Undo2, Wand2, ZoomIn, ZoomOut } from 'lucide-react'
import { registerCommands, sep, type MenuItem } from '../../frame/commands'
import { setRailTab } from '../../frame/suiteRegistry'
import { useSession } from '../../store/session'
import { ADJUSTMENT_DEFAULTS, FILTER_DEFAULTS, findNode, useEditor, type Node, type Tool } from './editorStore'

const ed = () => useEditor.getState()
const hasDoc = () => !!ed().doc
const active = (): Node | null => findNode(ed().doc, ed().activeId)
const activeRaster = () => { const n = active(); return !!n && n.kind === 'raster' }
const hasSel = () => !!ed().selection
const setTool = (t: Tool) => () => ed().setTool(t)
const TOOLS: [Tool, string, string, typeof Hand][] = [
  ['move', 'Move', 'V', MousePointer2], ['marquee', 'Marquee', 'M', Square], ['lasso', 'Lasso', 'L', Lasso], ['wand', 'Magic wand', 'W', Wand2], ['ai', 'AI select (M5)', 'A', Sparkles],
  ['brush', 'Brush', 'B', Paintbrush], ['eraser', 'Eraser', 'E', Eraser], ['fill', 'Fill', 'G', PaintBucket], ['eyedropper', 'Eyedropper', 'I', Pipette], ['crop', 'Crop / canvas size', 'C', Crop], ['hand', 'Hand', 'H', Hand], ['zoom', 'Zoom', 'Z', ZoomIn],
]

registerCommands([
  // history / files
  { id: 'edit.undo', scope: 'edit', label: 'Undo', icon: Undo2, keys: 'Ctrl+Z', placement: ['strip', 'context'], when: () => ed().history.length > 0, run: () => ed().undo() },
  { id: 'edit.redo', scope: 'edit', label: 'Redo', icon: Redo2, keys: 'Ctrl+Shift+Z', alt: ['Ctrl+Y'], placement: ['strip', 'context'], when: () => ed().future.length > 0, run: () => ed().redo() },
  { id: 'edit.save', scope: 'edit', label: 'Save document', icon: Save, keys: 'Ctrl+S', placement: ['panel', 'context'], when: hasDoc, run: () => void ed().save() },
  { id: 'edit.saveToCatalogue', scope: 'edit', label: 'Save to Catalogue', icon: FolderInput, keys: 'Ctrl+Shift+S', placement: ['panel', 'context'], when: hasDoc, run: () => void ed().saveToCatalogue() },
  { id: 'edit.exportPng', scope: 'edit', label: 'Export PNG', icon: FileImage, keys: 'Ctrl+Shift+E', placement: ['panel', 'context'], when: hasDoc, run: () => void ed().exportPng() },
  { id: 'edit.exportPsd', scope: 'edit', label: 'Export PSD', icon: FileDown, placement: ['panel', 'context'], when: hasDoc, run: () => void ed().exportPsd() },
  { id: 'edit.close', scope: 'edit', label: 'Close document', placement: ['panel', 'context'], when: hasDoc, run: () => { if (!ed().docDirty || window.confirm('Close without saving the latest changes?')) ed().closeDocument() } },
  { id: 'edit.compare', scope: 'edit', label: 'Compare preview with the exact flatten', icon: Scan, placement: ['inspector', 'context'], when: hasDoc, run: () => void ed().compareWithExact() },
  // layers
  { id: 'edit.layer.new', scope: 'edit', label: 'New layer', icon: Plus, keys: 'Ctrl+Shift+N', placement: ['toolbar', 'context'], when: hasDoc, run: () => { ed().addLayer('raster') } },
  { id: 'edit.layer.newGroup', scope: 'edit', label: 'New empty group', icon: FolderPlus, placement: ['toolbar', 'context'], when: hasDoc, run: () => { ed().addLayer('group') } },
  { id: 'edit.layer.group', scope: 'edit', label: 'Group the active layer', icon: Group, keys: 'Ctrl+G', placement: ['toolbar', 'context'], when: () => !!active(), run: () => ed().groupActive() },
  { id: 'edit.layer.duplicate', scope: 'edit', label: 'Duplicate layer', icon: Copy, keys: 'Ctrl+J', placement: ['toolbar', 'context'], when: () => !!active(), run: () => ed().duplicateNode(ed().activeId!) },
  { id: 'edit.layer.mergeDown', scope: 'edit', label: 'Merge down', icon: Merge, keys: 'Ctrl+E', placement: ['toolbar', 'context'], when: activeRaster, run: () => ed().mergeDown(ed().activeId!) },
  { id: 'edit.layer.up', scope: 'edit', label: 'Move layer up', icon: ArrowUp, placement: ['toolbar', 'context'], when: () => !!active(), run: () => ed().moveNode(ed().activeId!, 'up') },
  { id: 'edit.layer.down', scope: 'edit', label: 'Move layer down', icon: ArrowDown, placement: ['toolbar', 'context'], when: () => !!active(), run: () => ed().moveNode(ed().activeId!, 'down') },
  { id: 'edit.layer.rename', scope: 'edit', label: 'Rename…', icon: Pencil, placement: ['context'], when: () => !!active(), hint: 'double-click the layer', run: () => { const n = active(); if (!n) return; const name = window.prompt('Layer name', n.name); if (name && name !== n.name) ed().updateNode(n.id, { name }, 'rename') } },
  { id: 'edit.layer.visibility', scope: 'edit', label: 'Hide / show layer', icon: Eye, placement: ['toolbar', 'context'], when: () => !!active(), run: () => { const n = active(); if (n) ed().updateNode(n.id, { visible: !n.visible }, n.visible ? 'hide layer' : 'show layer') } },
  { id: 'edit.layer.solo', scope: 'edit', label: 'Solo layer (show only this)', icon: EyeOff, placement: ['context'], when: () => !!active(), hint: 'Alt-click the eye', run: () => ed().solo(ed().activeId!) },
  { id: 'edit.layer.lock', scope: 'edit', label: 'Lock / unlock layer', icon: Lock, placement: ['toolbar', 'context'], when: () => !!active(), run: () => { const n = active(); if (n) ed().updateNode(n.id, { locked: !n.locked }) } },
  { id: 'edit.layer.delete', scope: 'edit', label: 'Delete layer', icon: Trash, danger: true, placement: ['toolbar', 'context'], when: () => !!active(), run: () => { const n = active(); if (n && window.confirm(`Delete layer "${n.name}"?`)) ed().deleteNode(n.id) } },
  // masks
  { id: 'edit.mask.add', scope: 'edit', label: 'Add mask', icon: SquareDashed, placement: ['toolbar', 'context'], when: () => !!active() && !active()!.mask, run: () => ed().addMask(ed().activeId!, false) },
  { id: 'edit.mask.fromSelection', scope: 'edit', label: 'Add mask from selection', icon: SquareDashed, placement: ['toolbar', 'context'], when: () => !!active() && !active()!.mask && hasSel(), run: () => ed().addMask(ed().activeId!, true) },
  { id: 'edit.mask.remove', scope: 'edit', label: 'Remove mask', placement: ['toolbar', 'context'], when: () => !!active()?.mask, run: () => ed().removeMask(ed().activeId!) },
  { id: 'edit.mask.toggle', scope: 'edit', label: 'Enable / disable mask', placement: ['context'], when: () => !!active()?.mask, hint: 'Shift-click the mask thumbnail', run: () => { const n = active(); if (n?.mask) ed().updateNode(n.id, { mask: { ...n.mask, enabled: !n.mask.enabled } }, 'toggle mask') } },
  { id: 'edit.mask.edit', scope: 'edit', label: 'Edit mask / edit pixels', placement: ['context'], when: () => !!active()?.mask, hint: 'click the mask thumbnail', run: () => { const st = ed(); st.setActive(st.activeId, !st.editingMask) } },
  { id: 'edit.mask.load', scope: 'edit', label: 'Load mask as selection', placement: ['panel', 'context'], when: () => !!active()?.mask, run: () => ed().loadSelectionFromMask() },
  // selection
  { id: 'edit.sel.all', scope: 'edit', label: 'Select all', icon: SquareCheck, keys: 'Ctrl+A', placement: ['panel', 'context'], when: hasDoc, run: () => ed().selectAll() },
  { id: 'edit.sel.none', scope: 'edit', label: 'Deselect', icon: SquareX, keys: 'Ctrl+D', placement: ['panel', 'context'], when: hasSel, run: () => ed().clearSelection() },
  { id: 'edit.sel.invert', scope: 'edit', label: 'Invert selection', keys: 'Ctrl+Shift+I', placement: ['panel', 'context'], when: hasDoc, run: () => ed().invertSelection() },
  { id: 'edit.sel.feather', scope: 'edit', label: 'Feather…', placement: ['panel', 'context'], when: hasSel, run: () => { setRailTab('edit', 'selection'); useSession.getState().setUi({ panelOpen: true }) } },
  { id: 'edit.sel.quickMask', scope: 'edit', label: 'Quick mask', keys: 'Q', placement: ['strip', 'panel', 'context'], when: hasDoc, run: () => ed().setView({ quickMask: !ed().quickMask }) },
  { id: 'edit.sel.clear', scope: 'edit', label: 'Clear selected pixels', keys: 'Delete', alt: ['Backspace'], placement: ['context'], when: activeRaster, run: () => ed().clearSelected() },
  { id: 'edit.sel.crop', scope: 'edit', label: 'Crop to selection', icon: Crop, placement: ['panel', 'context'], when: hasSel, run: () => ed().cropToSelection() },
  // view
  { id: 'edit.view.zoomIn', scope: 'edit', label: 'Zoom in', icon: ZoomIn, keys: 'Ctrl++', alt: ['Ctrl+='], placement: ['strip', 'context'], when: hasDoc, run: () => ed().zoomTo(ed().zoom * 1.25) },
  { id: 'edit.view.zoomOut', scope: 'edit', label: 'Zoom out', icon: ZoomOut, keys: 'Ctrl+-', placement: ['strip', 'context'], when: hasDoc, run: () => ed().zoomTo(ed().zoom / 1.25) },
  { id: 'edit.view.fit', scope: 'edit', label: 'Fit to window', icon: Maximize, keys: 'Ctrl+0', placement: ['strip', 'context'], when: hasDoc, run: () => ed().requestFit() },
  { id: 'edit.view.100', scope: 'edit', label: 'Zoom 100 %', keys: 'Ctrl+1', placement: ['strip', 'context'], when: hasDoc, run: () => ed().zoomTo(1) },
  { id: 'edit.view.200', scope: 'edit', label: 'Zoom 200 %', keys: 'Ctrl+2', placement: ['context'], when: hasDoc, run: () => ed().zoomTo(2) },
  { id: 'edit.view.grid', scope: 'edit', label: 'Pixel grid', placement: ['strip', 'context'], run: () => ed().setView({ pixelGrid: !ed().pixelGrid }) },
  { id: 'edit.view.overlay', scope: 'edit', label: 'Mask overlay', keys: 'Alt+\\', placement: ['strip', 'context'], run: () => ed().setView({ overlay: !ed().overlay }) },
  { id: 'edit.view.before', scope: 'edit', label: 'Before (hide the active layer)', placement: ['strip'], hint: 'hold \\', when: hasDoc, run: () => ed().setView({ before: !ed().before }) },
  // colours and brush
  { id: 'edit.colour.swap', scope: 'edit', label: 'Swap colours', icon: Shuffle, keys: 'X', placement: ['panel'], run: () => { const b = ed().brush; ed().setBrush({ color: b.background, background: b.color }) } },
  { id: 'edit.colour.default', scope: 'edit', label: 'Default colours', icon: RotateCcw, keys: 'D', placement: ['panel'], run: () => ed().setBrush({ color: '#000000', background: '#ffffff' }) },
  { id: 'edit.brush.larger', scope: 'edit', label: 'Larger brush', icon: ZoomIn, keys: ']', placement: ['panel'], run: () => ed().setBrush({ size: Math.min(512, Math.round(ed().brush.size * 1.2)) }) },
  { id: 'edit.brush.smaller', scope: 'edit', label: 'Smaller brush', icon: ZoomOut, keys: '[', placement: ['panel'], run: () => ed().setBrush({ size: Math.max(1, Math.round(ed().brush.size / 1.2)) }) },
  { id: 'edit.brush.harder', scope: 'edit', label: 'Harder brush', keys: 'Shift+]', alt: ['Shift+}'], placement: ['panel'], run: () => ed().setBrush({ hardness: Math.min(1, Math.round((ed().brush.hardness + 0.1) * 100) / 100) }) },
  { id: 'edit.brush.softer', scope: 'edit', label: 'Softer brush', keys: 'Shift+[', alt: ['Shift+{'], placement: ['panel'], run: () => ed().setBrush({ hardness: Math.max(0, Math.round((ed().brush.hardness - 0.1) * 100) / 100) }) },
  // tools
  ...TOOLS.map(([tool, label, key, icon]) => ({ id: `edit.tool.${tool}`, scope: 'edit' as const, label: `${label} tool`, icon, keys: key, placement: ['toolbar'] as ['toolbar'], run: setTool(tool) })),
  // layers of a kind, by type
  ...Object.keys(ADJUSTMENT_DEFAULTS).map((t) => ({ id: `edit.layer.adjustment.${t}`, scope: 'edit' as const, label: `Add ${t.replace('_', ' ')} adjustment`, icon: SlidersHorizontal, placement: ['toolbar', 'context'] as ['toolbar', 'context'], when: hasDoc, run: () => { ed().addLayer('adjustment', { type: t }) } })),
  ...Object.keys(FILTER_DEFAULTS).map((t) => ({ id: `edit.layer.filter.${t}`, scope: 'edit' as const, label: `Add ${t.replace('_', ' ')} filter`, icon: Sparkles, placement: ['toolbar', 'context'] as ['toolbar', 'context'], when: hasDoc, run: () => { ed().addLayer('filter', { type: t }) } })),
])

export const adjustmentMenu = (): MenuItem[] => Object.keys(ADJUSTMENT_DEFAULTS).map((t) => ({ cmd: `edit.layer.adjustment.${t}`, label: t.replace('_', ' ') }))
export const filterMenu = (): MenuItem[] => Object.keys(FILTER_DEFAULTS).map((t) => ({ cmd: `edit.layer.filter.${t}`, label: t.replace('_', ' ') }))
const lockLabel = () => (active()?.locked ? 'Unlock layer' : 'Lock layer')
const visLabel = () => (active()?.visible ? 'Hide layer' : 'Show layer')
const maskItems = (): MenuItem[] => {
  const n = active()
  if (!n) return []
  if (!n.mask) return [{ cmd: 'edit.mask.add' }, { cmd: 'edit.mask.fromSelection' }]
  return [{ cmd: 'edit.mask.edit', label: ed().editingMask ? 'Edit pixels' : 'Edit mask' }, { cmd: 'edit.mask.toggle', label: n.mask.enabled ? 'Disable mask' : 'Enable mask' }, { cmd: 'edit.mask.load' }, { cmd: 'edit.mask.remove' }]
}

/** Right-click on a layer row (the caller makes it active first). */
export function layerMenu(): MenuItem[] {
  const n = active()
  if (!n) return []
  return [
    { cmd: 'edit.layer.rename' }, sep,
    { cmd: 'edit.layer.visibility', label: visLabel() }, { cmd: 'edit.layer.solo' }, { cmd: 'edit.layer.lock', label: lockLabel() }, sep,
    { cmd: 'edit.layer.duplicate' }, { cmd: 'edit.layer.mergeDown' }, { cmd: 'edit.layer.group' }, { cmd: 'edit.layer.up' }, { cmd: 'edit.layer.down' }, sep,
    { label: 'Mask', icon: SquareDashed, items: maskItems() }, sep,
    { cmd: 'edit.layer.delete' },
  ]
}
/** Right-click on the canvas: tool-aware. */
export function canvasMenu(): MenuItem[] {
  const st = ed()
  const selection: MenuItem[] = [{ cmd: 'edit.sel.all' }, { cmd: 'edit.sel.none' }, { cmd: 'edit.sel.invert' }, { cmd: 'edit.sel.feather' }, { cmd: 'edit.sel.quickMask', label: st.quickMask ? 'Leave quick mask' : 'Quick mask' }, { cmd: 'edit.sel.clear' }, { cmd: 'edit.sel.crop' }, { cmd: 'edit.mask.fromSelection' }]
  const layer: MenuItem[] = [{ cmd: 'edit.layer.new' }, { cmd: 'edit.layer.duplicate' }, { cmd: 'edit.layer.mergeDown' }, { cmd: 'edit.layer.group' }, { label: 'Add adjustment', icon: SlidersHorizontal, items: adjustmentMenu() }, { label: 'Add filter', icon: Sparkles, items: filterMenu() }, { cmd: 'edit.layer.delete' }]
  const view: MenuItem[] = [{ cmd: 'edit.view.zoomIn' }, { cmd: 'edit.view.zoomOut' }, { cmd: 'edit.view.fit' }, { cmd: 'edit.view.100' }, { cmd: 'edit.view.200' }, sep, { label: 'Pixel grid', checked: st.pixelGrid, run: () => st.setView({ pixelGrid: !st.pixelGrid }) }, { label: 'Mask overlay', keys: 'Alt+\\', checked: st.overlay, run: () => st.setView({ overlay: !st.overlay }) }]
  const files: MenuItem[] = [{ cmd: 'edit.save' }, { cmd: 'edit.saveToCatalogue' }, { cmd: 'edit.exportPng' }, { cmd: 'edit.exportPsd' }, sep, { cmd: 'edit.compare' }, { cmd: 'edit.close' }]
  const tools: MenuItem[] = TOOLS.map(([tool, label, , icon]) => ({ label, icon, checked: st.tool === tool, run: setTool(tool) }))
  return [
    { cmd: 'edit.undo' }, { cmd: 'edit.redo' }, sep,
    ...(st.quickMask || hasSel() ? [{ heading: 'selection' }, ...selection, sep] : [{ label: 'Selection', icon: SquareDashed, items: selection }]),
    { label: 'Layer', icon: Copy, items: layer }, { label: 'View', icon: Maximize, items: view }, { label: 'Tool', icon: MousePointer2, items: tools }, { label: 'Document', icon: Save, items: files },
  ]
}
export { LockOpen }
