// Edit commands (10 §4/§6/§10, 07 §3c): one definition each for the strip icons, the Layers toolbar, the
// canvas and layer right-click menus, the keys and the help overlay.
import { ArrowDown, ArrowUp, Check, Circle, CircleDashed, ClipboardPaste, Copy, Crop, Eraser, Eye, EyeOff, FileDown, FileImage, FlipHorizontal, FlipVertical, FolderInput, FolderPlus, Group, Hand, Lasso, Link, Lock, LockOpen, Maximize, Merge, Minus, MousePointer2, Paintbrush, PaintBucket, Pencil, Pipette, Plus, Redo2, RotateCcw, RotateCw, Save, Scan, Scissors, Shuffle, SlidersHorizontal, Sparkles, Square, SquareCheck, SquareDashed, SquareX, Trash, Undo2, Wand2, X, ZoomIn, ZoomOut } from 'lucide-react'
import { registerCommands, sep, type MenuItem } from '../../frame/commands'
import { askConfirm, askText, useSession } from '../../store/session'
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
  { id: 'edit.close', scope: 'edit', label: 'Close document', placement: ['panel', 'context'], when: hasDoc, run: () => { if (!ed().docDirty) { ed().closeDocument(); return } void askConfirm({ title: 'Close without saving?', text: 'The latest changes are not saved. Cancel and press Ctrl+S to keep them, or close and lose them.', okLabel: 'Close without saving', danger: true }).then((ok) => { if (ok) ed().closeDocument() }) } },
  { id: 'edit.compare', scope: 'edit', label: 'Compare preview with the exact flatten', icon: Scan, placement: ['inspector', 'context'], when: hasDoc, run: () => void ed().compareWithExact() },
  // layers
  { id: 'edit.layer.new', scope: 'edit', label: 'New layer', icon: Plus, keys: 'Ctrl+Shift+N', placement: ['toolbar', 'context'], when: hasDoc, run: () => { ed().addLayer('raster') } },
  { id: 'edit.layer.newGroup', scope: 'edit', label: 'New empty group', icon: FolderPlus, placement: ['toolbar', 'context'], when: hasDoc, run: () => { ed().addLayer('group') } },
  { id: 'edit.layer.group', scope: 'edit', label: 'Group the active layer', icon: Group, keys: 'Ctrl+G', placement: ['toolbar', 'context'], when: () => !!active(), run: () => ed().groupActive() },
  { id: 'edit.layer.duplicate', scope: 'edit', label: 'Duplicate layer', icon: Copy, keys: 'Ctrl+J', placement: ['toolbar', 'context'], when: () => !!active(), run: () => ed().duplicateNode(ed().activeId!) },
  { id: 'edit.layer.mergeDown', scope: 'edit', label: 'Merge down', icon: Merge, keys: 'Ctrl+E', placement: ['toolbar', 'context'], when: activeRaster, run: () => ed().mergeDown(ed().activeId!) },
  { id: 'edit.layer.up', scope: 'edit', label: 'Move layer up', icon: ArrowUp, placement: ['toolbar', 'context'], when: () => !!active(), run: () => ed().moveNode(ed().activeId!, 'up') },
  { id: 'edit.layer.down', scope: 'edit', label: 'Move layer down', icon: ArrowDown, placement: ['toolbar', 'context'], when: () => !!active(), run: () => ed().moveNode(ed().activeId!, 'down') },
  { id: 'edit.layer.rename', scope: 'edit', label: 'Rename…', icon: Pencil, placement: ['context'], when: () => !!active(), hint: 'double-click the layer', run: () => { const n = active(); if (!n) return; void askText({ title: 'Layer name', initial: n.name }).then((name) => { if (name && name !== n.name) ed().updateNode(n.id, { name }, 'rename') }) } },
  { id: 'edit.layer.visibility', scope: 'edit', label: 'Hide / show layer', icon: Eye, placement: ['toolbar', 'context'], when: () => !!active(), run: () => { const n = active(); if (n) ed().updateNode(n.id, { visible: !n.visible }, n.visible ? 'hide layer' : 'show layer') } },
  { id: 'edit.layer.solo', scope: 'edit', label: 'Solo layer (show only this)', icon: EyeOff, placement: ['context'], when: () => !!active(), hint: 'Alt-click the eye', run: () => ed().solo(ed().activeId!) },
  { id: 'edit.layer.lock', scope: 'edit', label: 'Lock / unlock layer', icon: Lock, placement: ['toolbar', 'context'], when: () => !!active(), run: () => { const n = active(); if (n) ed().updateNode(n.id, { locked: !n.locked }) } },
  { id: 'edit.layer.delete', scope: 'edit', label: 'Delete layer', icon: Trash, danger: true, placement: ['toolbar', 'context'], when: () => !!active(), run: () => { const n = active(); if (!n) return
      if (ed().editingMask && n.mask) { ed().removeMask(n.id); return }                     // D52: Delete follows the target — the mask while it is edited
      ed().deleteNode(n.id); const depth = ed().history.length                        // undoable, so no confirm: the toast offers Undo while nothing else happened since
      useSession.getState().toast(`Deleted layer "${n.name}"`, 'info', () => { const s = ed(); if (s.history.length === depth && s.history[depth - 1]?.label === 'delete layer') s.undo() }) } },
  // masks
  { id: 'edit.mask.add', scope: 'edit', label: 'Add mask', icon: SquareDashed, placement: ['toolbar', 'context'], when: () => !!active() && !active()!.mask, run: () => ed().addMask(ed().activeId!, false) },
  { id: 'edit.mask.fromSelection', scope: 'edit', label: 'Add mask from selection', icon: SquareDashed, placement: ['toolbar', 'context'], when: () => !!active() && !active()!.mask && hasSel(), run: () => ed().addMask(ed().activeId!, true) },
  { id: 'edit.mask.remove', scope: 'edit', label: 'Remove mask', placement: ['toolbar', 'context'], when: () => !!active()?.mask, run: () => ed().removeMask(ed().activeId!) },
  { id: 'edit.mask.toggle', scope: 'edit', label: 'Enable / disable mask', placement: ['context'], when: () => !!active()?.mask, hint: 'Shift-click the mask thumbnail', run: () => { const n = active(); if (n?.mask) ed().updateNode(n.id, { mask: { ...n.mask, enabled: !n.mask.enabled } }, 'toggle mask') } },
  { id: 'edit.mask.edit', scope: 'edit', label: 'Edit mask / edit pixels', placement: ['context'], when: () => !!active()?.mask, hint: 'click the mask thumbnail', run: () => { const st = ed(); st.setActive(st.activeId, !st.editingMask) } },
  { id: 'edit.mask.link', scope: 'edit', label: 'Link / unlink mask', icon: Link, placement: ['context'], when: () => !!active()?.mask, hint: 'click the chain left of the mask thumbnail', run: () => ed().toggleMaskLink(ed().activeId!) },
  { id: 'edit.mask.apply', scope: 'edit', label: 'Apply mask', placement: ['panel', 'context'], when: () => active()?.kind === 'raster' && !!active()?.mask, run: () => ed().applyMask(ed().activeId!) },
  { id: 'edit.mask.fromTransparency', scope: 'edit', label: 'Mask from transparency', placement: ['context'], when: () => active()?.kind === 'raster' && !active()?.mask, run: () => ed().maskFromTransparency(ed().activeId!) },
  { id: 'edit.mask.load', scope: 'edit', label: 'Load mask as selection', placement: ['panel', 'context'], when: () => !!active()?.mask, run: () => ed().loadSelectionFromMask() },
  // selection
  { id: 'edit.sel.all', scope: 'edit', label: 'Select all', icon: SquareCheck, keys: 'Ctrl+A', placement: ['panel', 'context'], when: hasDoc, run: () => ed().selectAll() },
  { id: 'edit.sel.none', scope: 'edit', label: 'Deselect', icon: SquareX, keys: 'Ctrl+D', placement: ['panel', 'context'], when: hasSel, run: () => ed().deselect() },
  { id: 'edit.sel.invert', scope: 'edit', label: 'Invert selection', keys: 'Ctrl+Shift+I', placement: ['panel', 'context'], when: hasDoc, run: () => ed().invertSelection() },
  // D44: modify by the Selection panel's amount (px); every one is a single undo step
  ...(['expand', 'contract', 'border', 'smooth', 'feather'] as const).map((op) => ({
    id: `edit.sel.${op}`, scope: 'edit' as const, label: `${op[0].toUpperCase()}${op.slice(1)} selection`, placement: ['panel', 'context'] as ['panel', 'context'], when: hasSel,
    hint: 'by the amount set in the Selection panel', run: () => { const st = ed(); st.modifySelection(op, st.selModifyPx) },
  })),
  // D46 clipboard: Ctrl+V reaches the editor as the browser's paste event (it carries images from other apps without a permission prompt)
  { id: 'edit.copy', scope: 'edit', label: 'Copy', icon: Copy, keys: 'Ctrl+C', placement: ['panel', 'context'], when: activeRaster, hint: 'the selected pixels of the active layer (all of it without a selection)', run: () => { ed().copySelection() } },
  { id: 'edit.cut', scope: 'edit', label: 'Cut', icon: Scissors, keys: 'Ctrl+X', placement: ['panel', 'context'], when: () => activeRaster() && hasSel(), run: () => { ed().copySelection({ cut: true }) } },
  { id: 'edit.copyMerged', scope: 'edit', label: 'Copy merged', icon: Copy, keys: 'Ctrl+Shift+C', placement: ['panel', 'context'], when: hasDoc, hint: 'the selected part of the visible composite', run: () => { ed().copySelection({ merged: true }) } },
  { id: 'edit.paste', scope: 'edit', label: 'Paste', icon: ClipboardPaste, keys: 'Ctrl+V', placement: ['panel', 'context'], when: hasDoc, hint: 'as a new layer — an image copied in another app, or the last copy', run: () => void ed().pasteClipboard(false) },
  { id: 'edit.pasteInPlace', scope: 'edit', label: 'Paste in place', icon: ClipboardPaste, keys: 'Ctrl+Shift+V', placement: ['panel', 'context'], when: () => hasDoc() && !!ed().clipboard, hint: 'as a new layer where it was copied from', run: () => void ed().pasteClipboard(true) },
  { id: 'edit.layer.viaCopy', scope: 'edit', label: 'Layer via copy', icon: Copy, keys: 'Ctrl+Alt+J', placement: ['panel', 'context'], when: () => activeRaster() && hasSel(), run: () => ed().layerVia(false) },
  { id: 'edit.layer.viaCut', scope: 'edit', label: 'Layer via cut', icon: Scissors, keys: 'Ctrl+Shift+J', placement: ['panel', 'context'], when: () => activeRaster() && hasSel(), run: () => ed().layerVia(true) },
  // D51 painting modifiers with a mouse path; D50 lock transparency
  { id: 'edit.brush.line', scope: 'edit', label: 'Straight lines', icon: Minus, placement: ['panel'], when: hasDoc, hint: 'drag draws a straight line (or Shift-click from the last stroke)', run: () => ed().setView({ brushLine: !ed().brushLine }) },
  { id: 'edit.brush.pick', scope: 'edit', label: 'Pick colour', icon: Pipette, placement: ['panel', 'context'], when: hasDoc, hint: 'the next click on the canvas picks the colour (or Alt-click while painting)', run: () => ed().setView({ pickOnce: !ed().pickOnce }) },
  { id: 'edit.layer.lockAlpha', scope: 'edit', label: 'Lock transparency', icon: Lock, placement: ['panel', 'context'], when: activeRaster, hint: 'painting changes the colour but keeps the layer\'s transparency', run: () => { const n = active(); if (n) ed().updateNode(n.id, { lock_alpha: !n.lock_alpha }, n.lock_alpha ? 'unlock transparency' : 'lock transparency') } },
  { id: 'edit.layer.inkFromWhite', scope: 'edit', label: 'Ink from white', icon: Sparkles, placement: ['panel', 'context'], when: activeRaster, hint: 'Colour to Alpha with white: line art on paper becomes transparent ink (D49)', run: () => ed().inkFromWhite() },
  { id: 'edit.sel.refine', scope: 'edit', label: 'Refine edge', icon: Sparkles, placement: ['panel', 'context'], when: hasSel, hint: 'soft, image-aware edges with the Selection panel\'s settings (D45)', run: () => void ed().refineSelection() },
  { id: 'edit.sel.fromLayer', scope: 'edit', label: 'Select layer transparency', icon: SquareDashed, placement: ['panel', 'context'], when: activeRaster, hint: 'or Ctrl-click the layer thumbnail', run: () => ed().selectLayerAlpha(ed().activeId!) },
  { id: 'edit.sel.polyClose', scope: 'edit', label: 'Close polygon', icon: Check, keys: 'Enter', placement: ['panel', 'context'], when: () => (ed().lassoPoly?.length ?? 0) >= 3, hint: 'or click the first corner, or double-click', run: () => ed().closeLassoPoly() },
  { id: 'edit.sel.polyCancel', scope: 'edit', label: 'Cancel polygon', icon: X, keys: 'Escape', placement: ['panel', 'context'], when: () => !!ed().lassoPoly, run: () => ed().setLassoPoly(null) },
  { id: 'edit.sel.quickMask', scope: 'edit', label: 'Quick mask', keys: 'Q', placement: ['strip', 'panel', 'context'], when: hasDoc, run: () => ed().setView({ quickMask: !ed().quickMask }) },
  { id: 'edit.sel.clear', scope: 'edit', label: 'Clear selected pixels', keys: 'Delete', alt: ['Backspace'], placement: ['context'], when: activeRaster, run: () => ed().clearSelected() },
  { id: 'edit.sel.crop', scope: 'edit', label: 'Crop to selection', icon: Crop, placement: ['panel', 'context'], when: hasSel, run: () => ed().cropToSelection() },
  // free transform (10 §4)
  { id: 'edit.transform', scope: 'edit', label: 'Free transform', icon: Scan, keys: 'Ctrl+T', placement: ['panel', 'context', 'strip'], when: () => activeRaster() && !ed().transform, run: () => ed().beginTransform() },
  { id: 'edit.transform.apply', scope: 'edit', label: 'Apply transform', icon: Check, keys: 'Enter', placement: ['strip', 'context'], when: () => !!ed().transform, hint: 'or double-click inside the box', run: () => ed().applyTransform() },
  { id: 'edit.transform.cancel', scope: 'edit', label: 'Cancel transform', icon: X, keys: 'Escape', placement: ['strip', 'context'], when: () => !!ed().transform, run: () => ed().cancelTransform() },
  { id: 'edit.layer.flipH', scope: 'edit', label: 'Flip horizontal', icon: FlipHorizontal, placement: ['panel', 'context'], when: activeRaster, run: () => ed().flipLayer('h') },
  { id: 'edit.layer.flipV', scope: 'edit', label: 'Flip vertical', icon: FlipVertical, placement: ['panel', 'context'], when: activeRaster, run: () => ed().flipLayer('v') },
  { id: 'edit.layer.rot90', scope: 'edit', label: 'Rotate 90° clockwise', icon: RotateCw, placement: ['panel', 'context'], when: activeRaster, run: () => ed().rotateLayer(90) },
  { id: 'edit.layer.rot270', scope: 'edit', label: 'Rotate 90° counter-clockwise', icon: RotateCcw, placement: ['panel', 'context'], when: activeRaster, run: () => ed().rotateLayer(-90) },
  { id: 'edit.layer.rot180', scope: 'edit', label: 'Rotate 180°', icon: RotateCw, placement: ['context'], when: activeRaster, run: () => ed().rotateLayer(180) },
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
  { id: 'edit.brush.larger', scope: 'edit', label: 'Larger brush', icon: Plus, keys: ']', placement: ['panel'], run: () => ed().setBrush({ size: Math.min(1024, Math.round(ed().brush.size * 1.2)) }) },
  { id: 'edit.brush.smaller', scope: 'edit', label: 'Smaller brush', icon: Minus, keys: '[', placement: ['panel'], run: () => ed().setBrush({ size: Math.max(1, Math.round(ed().brush.size / 1.2)) }) },
  { id: 'edit.brush.harder', scope: 'edit', label: 'Harder brush', icon: Circle, keys: 'Shift+]', alt: ['Shift+}'], placement: ['panel'], run: () => ed().setBrush({ hardness: Math.min(1, Math.round((ed().brush.hardness + 0.1) * 100) / 100) }) },
  { id: 'edit.brush.softer', scope: 'edit', label: 'Softer brush', icon: CircleDashed, keys: 'Shift+[', alt: ['Shift+{'], placement: ['panel'], run: () => ed().setBrush({ hardness: Math.max(0, Math.round((ed().brush.hardness - 0.1) * 100) / 100) }) },
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
  if (!n.mask) return [{ cmd: 'edit.mask.add' }, { cmd: 'edit.mask.fromSelection' }, { cmd: 'edit.mask.fromTransparency' }]
  return [{ cmd: 'edit.mask.edit', label: ed().editingMask ? 'Edit pixels' : 'Edit mask' }, { cmd: 'edit.mask.toggle', label: n.mask.enabled ? 'Disable mask' : 'Enable mask' }, { cmd: 'edit.mask.link', label: n.mask.linked ? 'Unlink mask' : 'Link mask' }, { cmd: 'edit.mask.load' }, { cmd: 'edit.mask.apply' }, { cmd: 'edit.mask.remove' }]
}

/** Right-click on a layer row (the caller makes it active first). */
export function layerMenu(): MenuItem[] {
  const n = active()
  if (!n) return []
  return [
    { cmd: 'edit.layer.rename' }, sep,
    { cmd: 'edit.layer.visibility', label: visLabel() }, { cmd: 'edit.layer.solo' }, { cmd: 'edit.layer.lock', label: lockLabel() }, sep,
    { cmd: 'edit.layer.duplicate' }, { cmd: 'edit.layer.mergeDown' }, { cmd: 'edit.layer.group' }, { cmd: 'edit.layer.up' }, { cmd: 'edit.layer.down' }, sep,
    { cmd: 'edit.sel.fromLayer' }, { cmd: 'edit.layer.inkFromWhite' }, { cmd: 'edit.layer.lockAlpha', label: active()?.lock_alpha ? 'Unlock transparency' : 'Lock transparency' },
    { label: 'Transform', icon: Scan, items: transformItems() },
    { label: 'Mask', icon: SquareDashed, items: maskItems() }, sep,
    { cmd: 'edit.layer.delete', label: ed().editingMask && n.mask ? 'Delete layer mask' : undefined },
  ]
}
const transformItems = (): MenuItem[] => [{ cmd: 'edit.transform' }, { cmd: 'edit.transform.apply' }, { cmd: 'edit.transform.cancel' }, sep, { cmd: 'edit.layer.flipH' }, { cmd: 'edit.layer.flipV' }, { cmd: 'edit.layer.rot90' }, { cmd: 'edit.layer.rot270' }, { cmd: 'edit.layer.rot180' }]
/** Right-click on the canvas: tool-aware. */
export function canvasMenu(): MenuItem[] {
  const st = ed()
  const px = st.selModifyPx
  const modify: MenuItem[] = (['expand', 'contract', 'border', 'smooth', 'feather'] as const).map((op) => ({ cmd: `edit.sel.${op}`, label: `${op[0].toUpperCase()}${op.slice(1)} by ${px} px` }))
  const selection: MenuItem[] = [{ cmd: 'edit.sel.all' }, { cmd: 'edit.sel.none' }, { cmd: 'edit.sel.invert' }, { label: 'Modify', icon: SquareDashed, items: modify }, { cmd: 'edit.sel.refine' }, { cmd: 'edit.sel.fromLayer' }, { cmd: 'edit.sel.quickMask', label: st.quickMask ? 'Leave quick mask' : 'Quick mask' }, { cmd: 'edit.sel.clear' }, { cmd: 'edit.sel.crop' }, { cmd: 'edit.mask.fromSelection' }]
  const layer: MenuItem[] = [{ cmd: 'edit.layer.new' }, { cmd: 'edit.layer.duplicate' }, { cmd: 'edit.layer.mergeDown' }, { cmd: 'edit.layer.group' }, { label: 'Add adjustment', icon: SlidersHorizontal, items: adjustmentMenu() }, { label: 'Add filter', icon: Sparkles, items: filterMenu() }, { label: 'Transform', icon: Scan, items: transformItems() }, { cmd: 'edit.layer.delete' }]
  const view: MenuItem[] = [{ cmd: 'edit.view.zoomIn' }, { cmd: 'edit.view.zoomOut' }, { cmd: 'edit.view.fit' }, { cmd: 'edit.view.100' }, { cmd: 'edit.view.200' }, sep, { label: 'Pixel grid', checked: st.pixelGrid, run: () => st.setView({ pixelGrid: !st.pixelGrid }) }, { label: 'Mask overlay', keys: 'Alt+\\', checked: st.overlay, run: () => st.setView({ overlay: !st.overlay }) }]
  const files: MenuItem[] = [{ cmd: 'edit.save' }, { cmd: 'edit.saveToCatalogue' }, { cmd: 'edit.exportPng' }, { cmd: 'edit.exportPsd' }, sep, { cmd: 'edit.compare' }, { cmd: 'edit.close' }]
  const tools: MenuItem[] = TOOLS.map(([tool, label, , icon]) => ({ label, icon, checked: st.tool === tool, run: setTool(tool) }))
  return [
    ...(st.transform ? [{ heading: 'free transform' }, { cmd: 'edit.transform.apply' }, { cmd: 'edit.transform.cancel' }, sep] : []),
    ...(st.lassoPoly ? [{ heading: 'polygonal lasso' }, { cmd: 'edit.sel.polyClose' }, { cmd: 'edit.sel.polyCancel' }, sep] : []),
    { cmd: 'edit.undo' }, { cmd: 'edit.redo' }, sep,
    ...(st.quickMask || hasSel() ? [{ heading: 'selection' }, ...selection, sep] : [{ label: 'Selection', icon: SquareDashed, items: selection }]),
    ...(hasSel() ? [{ heading: 'clipboard' }, { cmd: 'edit.layer.viaCopy' }, { cmd: 'edit.layer.viaCut' }, { cmd: 'edit.copy' }, { cmd: 'edit.cut' }, { cmd: 'edit.copyMerged' }, { cmd: 'edit.paste' }, { cmd: 'edit.pasteInPlace' }, sep]
      : [{ label: 'Clipboard', icon: ClipboardPaste, items: [{ cmd: 'edit.copy' }, { cmd: 'edit.copyMerged' }, { cmd: 'edit.paste' }, { cmd: 'edit.pasteInPlace' }] }]),
    { label: 'Layer', icon: Copy, items: layer }, { label: 'View', icon: Maximize, items: view }, { label: 'Tool', icon: MousePointer2, items: tools }, { label: 'Document', icon: Save, items: files },
  ]
}
export { LockOpen }
