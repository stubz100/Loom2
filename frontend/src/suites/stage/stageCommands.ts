// P13 / ST1 (D81): the Stage suite's verbs — every one has a mouse home (the gizmo bar, the panel, the Inspector, the viewport's
// right-click menu) per D32; G / R / S / W, F, Delete, Ctrl+Z / Ctrl+Shift+Z are accelerators.
import { Box, Camera, Copy, Crosshair, Eye, EyeOff, Focus, Frame, Grid3x3, Lock, LockOpen, Magnet, Move3d, MousePointer2, Plus, Redo2, Rotate3d, Scaling, Trash2, Undo2, User, Video } from 'lucide-react'
import { registerCommands, sep, type Command, type MenuItem } from '../../frame/commands'
import { askConfirm, askText } from '../../store/session'
import { MANNEQUIN_PRESETS, PROP_PRESETS, SET_PRESETS } from './builders'
import { st, useStage, type Kind, type Tool } from './stageStore'

const hasStage = () => !!st().current
const sel = () => st().object(st().selected)
const hasSel = () => !!sel()
/** The viewport engine registers itself so the commands can place, frame and read the free view (engine.ts is not a store). */
export const viewport: { centre?: () => number[]; freePose?: () => { pos: number[]; target: number[] }; frame?: (ids: string[] | null) => void; lookThrough?: () => void } = {}

const tool = (id: Tool, label: string, icon: typeof MousePointer2, key: string): Command => ({
  id: `stage.tool.${id}`, scope: 'stage', label, icon, keys: key, placement: ['toolbar', 'context'], when: hasStage, run: () => st().setTool(id),
})
const addCmd = (kind: Kind, preset: string, label: string, icon: typeof Box): Command => ({
  id: `stage.add.${kind}.${preset}`, scope: 'stage', label, icon, placement: ['panel', 'context'], when: hasStage,
  run: () => { st().addObject(kind, preset, viewport.centre?.() ?? [0, 0, 0]) },
})

registerCommands([
  { id: 'stage.new', scope: 'stage', label: 'New stage…', icon: Plus, placement: ['panel', 'context'],
    run: () => void askText({ title: 'New stage', text: 'A blocking: a set, figures, props and cameras at the project size.', placeholder: 'stage name', initial: 'Stage' }).then((n) => { if (n?.trim()) void st().create(n.trim()) }) },
  { id: 'stage.rename', scope: 'stage', label: 'Rename stage…', icon: Frame, placement: ['inspector', 'context'], when: hasStage,
    run: () => void askText({ title: 'Rename stage', initial: st().current?.name ?? '', placeholder: 'stage name' }).then((n) => { if (n?.trim()) void st().rename(n.trim()) }) },
  { id: 'stage.delete', scope: 'stage', label: 'Delete stage', icon: Trash2, placement: ['inspector', 'context'], when: hasStage,
    run: () => void askConfirm({ title: 'Delete this stage?', text: 'The document goes; assets stay in the Catalogue.', okLabel: 'Delete', danger: true }).then((ok) => { if (ok) void st().destroy() }) },
  tool('select', 'Select', MousePointer2, 'W'), tool('move', 'Move', Move3d, 'G'), tool('rotate', 'Rotate', Rotate3d, 'R'), tool('scale', 'Scale', Scaling, 'S'),
  { id: 'stage.snap', scope: 'stage', label: 'Snap (0.25 m · 15°)', icon: Magnet, keys: 'Q', placement: ['toolbar', 'context'], when: hasStage, run: () => st().setSnap(!st().snap) },
  { id: 'stage.view.free', scope: 'stage', label: 'Free view', icon: Eye, placement: ['strip'], when: hasStage, run: () => st().setView('free') },
  { id: 'stage.view.camera', scope: 'stage', label: 'Camera view (look through)', icon: Video, keys: 'C', placement: ['strip', 'panel'], when: () => hasStage() && !!st().activeCamera(), run: () => st().setView(st().view === 'camera' ? 'free' : 'camera') },
  { id: 'stage.guides', scope: 'stage', label: 'Framing guides', icon: Grid3x3, placement: ['strip'], when: hasStage, run: () => st().setGuides(!st().guides) },
  { id: 'stage.frameAll', scope: 'stage', label: 'Frame everything', icon: Focus, keys: 'Home', placement: ['strip', 'panel', 'context'], when: hasStage, run: () => st().frame(null) },
  { id: 'stage.frameSel', scope: 'stage', label: 'Frame the selection', icon: Crosshair, keys: 'F', placement: ['context', 'inspector'], when: hasSel, run: () => st().frame([st().selected!]) },
  ...Object.entries(MANNEQUIN_PRESETS).map(([p, m]) => addCmd('mannequin', p, `Add figure · ${m.label}`, User)),
  ...SET_PRESETS.map((p) => addCmd('set', p, `Add set · ${p}`, Box)),
  ...PROP_PRESETS.map((p) => addCmd('prop', p, `Add prop · ${p}`, Box)),
  { id: 'stage.object.delete', scope: 'stage', label: 'Delete', icon: Trash2, keys: 'Delete', placement: ['inspector', 'context'], when: () => hasSel() && !sel()!.locked, run: () => st().removeObject(st().selected!) },
  { id: 'stage.object.duplicate', scope: 'stage', label: 'Duplicate', icon: Copy, keys: 'Ctrl+D', placement: ['inspector', 'context'], when: hasSel, run: () => st().duplicateObject(st().selected!) },
  { id: 'stage.object.lock', scope: 'stage', label: 'Lock / unlock', icon: Lock, keys: 'L', placement: ['inspector', 'context'], when: hasSel, run: () => { const o = sel()!; st().updateObject(o.id, { locked: !o.locked }) } },
  { id: 'stage.object.hide', scope: 'stage', label: 'Hide / show', icon: EyeOff, keys: 'H', placement: ['inspector', 'context'], when: hasSel, run: () => { const o = sel()!; st().updateObject(o.id, { visible: !o.visible }) } },
  { id: 'stage.object.reset', scope: 'stage', label: 'Reset transform', icon: LockOpen, placement: ['inspector', 'context'], when: hasSel, run: () => { const o = sel()!; st().setTransform(o.id, { pos: [o.transform.pos[0], 0, o.transform.pos[2]], rot: [0, 0, 0], scale: [1, 1, 1] }) } },
  { id: 'stage.camera.add', scope: 'stage', label: 'Add camera', icon: Camera, placement: ['panel', 'context'], when: hasStage, run: () => st().addCamera() },
  { id: 'stage.camera.setFromView', scope: 'stage', label: 'Set the camera from the view', icon: Video, placement: ['panel', 'inspector', 'context'], when: () => hasStage() && !!st().activeCamera() && st().view === 'free',
    run: () => { const c = st().activeCamera(); const p = viewport.freePose?.(); if (c && p) st().updateCamera(c.id, { pos: p.pos, target: p.target }) } },
  { id: 'stage.camera.delete', scope: 'stage', label: 'Delete camera', icon: Trash2, placement: ['panel', 'inspector'], when: () => (st().current?.cameras.length ?? 0) > 1, run: () => { const c = st().activeCamera(); if (c) st().removeCamera(c.id) } },
  // ST2: posing
  { id: 'stage.pose.mirror', scope: 'stage', label: 'Mirror the pose', icon: Copy, keys: 'M', placement: ['panel', 'inspector', 'context'], when: () => sel()?.kind === 'mannequin', run: () => st().mirrorPose(st().selected!) },
  { id: 'stage.pose.reset', scope: 'stage', label: 'Reset the pose (stand)', icon: LockOpen, placement: ['panel', 'inspector', 'context'], when: () => sel()?.kind === 'mannequin', run: () => st().resetPose(st().selected!) },
  { id: 'stage.pose.save', scope: 'stage', label: 'Save pose…', icon: Plus, placement: ['panel', 'context'], when: () => sel()?.kind === 'mannequin',
    run: () => void askText({ title: 'Save pose', text: "The figure's joints, as a preset of this project.", placeholder: 'pose name' }).then((n) => { if (n?.trim()) void st().savePose(n.trim(), st().selected!) }) },
  { id: 'stage.undo', scope: 'stage', label: 'Undo', icon: Undo2, keys: 'Ctrl+Z', placement: ['toolbar', 'context'], when: () => st().undo.length > 0, run: () => st().undoEdit() },
  { id: 'stage.redo', scope: 'stage', label: 'Redo', icon: Redo2, keys: 'Ctrl+Shift+Z', placement: ['toolbar', 'context'], when: () => st().redo.length > 0, run: () => st().redoEdit() },
])

export const addMenu = (): MenuItem => ({ label: 'Add', icon: Plus, items: [
  ...Object.keys(MANNEQUIN_PRESETS).map((p) => ({ cmd: `stage.add.mannequin.${p}` })), sep,
  ...SET_PRESETS.map((p) => ({ cmd: `stage.add.set.${p}` })), sep,
  ...PROP_PRESETS.map((p) => ({ cmd: `stage.add.prop.${p}` })),
] })

/** Right-click on an object (selected by the caller) or on empty space. */
export function viewportMenu(onObject: boolean): MenuItem[] {
  return onObject
    ? [{ cmd: 'stage.frameSel' }, { cmd: 'stage.object.duplicate' }, { cmd: 'stage.object.lock' }, { cmd: 'stage.object.hide' }, { cmd: 'stage.object.reset' }, sep,
      ...(sel()?.kind === 'mannequin' ? [{ cmd: 'stage.pose.mirror' }, { cmd: 'stage.pose.reset' }, { cmd: 'stage.pose.save' }, sep] : []),
      { cmd: 'stage.object.delete' }, sep, { cmd: 'stage.undo' }, { cmd: 'stage.redo' }]
    : [addMenu(), { cmd: 'stage.camera.add' }, sep, { cmd: 'stage.tool.select' }, { cmd: 'stage.tool.move' }, { cmd: 'stage.tool.rotate' }, { cmd: 'stage.tool.scale' }, { cmd: 'stage.snap' }, sep, { cmd: 'stage.frameAll' }, sep, { cmd: 'stage.undo' }, { cmd: 'stage.redo' }]
}

export { useStage }
