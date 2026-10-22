// P13 / ST1 (D81): the Stage suite's verbs — every one has a mouse home (the gizmo bar, the panel, the Inspector, the viewport's
// right-click menu) per D32; G / R / S / W, F, Delete, Ctrl+Z / Ctrl+Shift+Z are accelerators.
import { Aperture, Box, PersonStanding, Sun, UserRound, UserX, Camera, ChevronFirst, ChevronLast, ChevronLeft, ChevronRight, Clapperboard, Copy, Crosshair, Diamond, Eye, EyeOff, Focus, Frame, Grid3x3, ImagePlus, Layers, Pencil, Lock, LockOpen, Magnet, Move3d, MousePointer2, Play, Plus, Redo2, Rotate3d, Route, Scaling, SkipBack, SkipForward, StepBack, StepForward, Trash2, Undo2, User, Video, X } from 'lucide-react'
import { registerCommands, sep, type Command, type MenuItem } from '../../frame/commands'
import { askConfirm, askText, useSession } from '../../store/session'
import { neighbourKey } from './anim'
import { MANNEQUIN_PRESETS, PROP_PRESETS, SET_PRESETS } from './builders'
import { st, useStage, type Kind, type Tool } from './stageStore'
import { nextFinalStep, useFinals } from './finalShot'
import type { HandPreset } from './detailed'
import { profilesForMentions } from '../story/storyStore'
import { useMotion } from './motion/motionStore'

const hasStage = () => !!st().current
const sel = () => st().object(st().selected)
const hasSel = () => !!sel()
/** The viewport engine registers itself so the commands can place, frame and read the free view (engine.ts is not a store). */
export const viewport: { centre?: () => number[]; freePose?: () => { pos: number[]; target: number[] }; frame?: (ids: string[] | null) => void; lookThrough?: () => void
  handPreset?: (id: string, side: 'r' | 'l', preset: HandPreset) => Record<string, number[]> | null } = {}   // CA1: the mounted viewport's Detailed figures

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
  tool('path', 'Path (click the floor to add to the figure\'s path)', Route, 'P'),                                           // CA1
  { id: 'stage.path.clear', scope: 'stage', label: 'Clear the path', icon: X, placement: ['panel', 'context'], when: () => !!sel()?.path?.length, run: () => st().clearPath(sel()!.id) },
  { id: 'stage.snap', scope: 'stage', label: 'Snap (0.25 m · 15°)', icon: Magnet, keys: 'Q', placement: ['toolbar', 'context'], when: hasStage, run: () => st().setSnap(!st().snap) },
  { id: 'stage.view.free', scope: 'stage', label: 'Free view', icon: Eye, placement: ['strip'], when: hasStage, run: () => st().setView('free') },
  { id: 'stage.view.camera', scope: 'stage', label: 'Camera view (look through)', icon: Video, keys: '0', placement: ['strip', 'panel', 'context'], when: () => hasStage() && !!st().activeCamera(), run: () => st().setView(st().view === 'camera' ? 'free' : 'camera') },
  { id: 'stage.guides', scope: 'stage', label: 'Framing guides', icon: Grid3x3, placement: ['strip'], when: hasStage, run: () => st().setGuides(!st().guides) },
  // D90 (02 §8.2): Shift+F, off Home (the transport's first frame) — beside F (frame the selection)
  { id: 'stage.frameAll', scope: 'stage', label: 'Frame everything', icon: Focus, keys: 'Shift+F', hint: 'F frames the selection; Home is the timeline\'s first frame',placement: ['strip', 'panel', 'context'], when: hasStage, run: () => st().frameView(null) },
  { id: 'stage.frameSel', scope: 'stage', label: 'Frame the selection', icon: Crosshair, keys: 'F', placement: ['context', 'inspector'], when: hasSel, run: () => st().frameView([st().selected!]) },
  ...Object.entries(MANNEQUIN_PRESETS).map(([p, m]) => addCmd('mannequin', p, `Add figure · ${m.label}`, User)),
  ...SET_PRESETS.map((p) => addCmd('set', p, `Add set · ${p}`, Box)),
  ...PROP_PRESETS.map((p) => addCmd('prop', p, `Add prop · ${p}`, Box)),
  // D110 (PS4): a light of the scene — a sun from the upper front-left, aimed at the viewport's centre; its strength, colour, softness
  // and aim in the Inspector
  { id: 'stage.add.light', scope: 'stage', label: 'Add light', icon: Sun, placement: ['panel', 'context'], when: hasStage, run: () => { st().addLight(viewport.centre?.() ?? [0, 0, 0]) } },
  { id: 'stage.object.delete', scope: 'stage', label: 'Delete', icon: Trash2, keys: 'Delete', placement: ['inspector', 'context'], when: () => hasSel() && !sel()!.locked, run: () => st().removeObject(st().selected!) },
  // D95 (AN1, UX0 #18): renaming was a double-click only (D32: every action has a mouse placement)
  { id: 'stage.object.rename', scope: 'stage', label: 'Rename…', icon: Pencil, placement: ['inspector', 'context'], when: hasSel,
    run: () => { const o = sel()!; void askText({ title: 'Rename', initial: o.name, placeholder: 'name' }).then((n) => { if (n?.trim()) st().updateObject(o.id, { name: n.trim() }) }) } },
  { id: 'stage.add.set.image', scope: 'stage', label: 'Set from an image…', icon: ImagePlus, hint: 'a picture of a place as a relief the camera can move in a little (MoGe, D120) — pick the picture in the Bin', placement: ['panel', 'context'], when: hasStage,
    run: () => { useSession.getState().setUi({ dockTab: 'bin', dockOpen: true, pick: { verb: 'stage.set', cmd: 'stage.add.set.image', label: 'Add to the stage (a set from this image)' } }); useSession.getState().toast('Pick a picture in the Bin: its corner button makes the set (or right-click it)', 'info') } },
  { id: 'stage.add.plane', scope: 'stage', label: 'Add image plane…', icon: ImagePlus, placement: ['panel', 'context'], when: hasStage,
    run: () => { useSession.getState().setUi({ dockTab: 'bin', dockOpen: true, pick: { verb: 'stage.plane', cmd: 'stage.add.plane', label: 'Add to the stage (image plane)' } }); useSession.getState().toast('Pick an image in the Bin: its corner button adds the plane — or drag it onto the viewport, or double-click it (right-click › Add to the stage)', 'info') } },
  // CA1 (proto01_animate 01 step 5): the motion library
  { id: 'stage.motion.apply', scope: 'stage', label: 'Apply the clip at the playhead', icon: Play, hint: 'the picked library clip on the selected figure, as keys from the playhead (one undo step)', placement: ['panel', 'context'],
    when: () => sel()?.kind === 'mannequin' && !!useMotion.getState().picked && !useMotion.getState().applying, run: () => void useMotion.getState().apply() },
  { id: 'stage.motion.refresh', scope: 'stage', label: 'List the motion files again', icon: Redo2, placement: ['panel'], when: hasStage, run: () => void useMotion.getState().refresh() },
  { id: 'stage.object.duplicate', scope: 'stage', label: 'Duplicate', icon: Copy, keys: 'Ctrl+D', placement: ['inspector', 'context'], when: hasSel, run: () => st().duplicateObject(st().selected!) },
  { id: 'stage.object.lock', scope: 'stage', label: 'Lock / unlock', icon: Lock, keys: 'Ctrl+L', placement: ['inspector', 'context'], when: hasSel, run: () => { const o = sel()!; st().updateObject(o.id, { locked: !o.locked }) } },
  { id: 'stage.object.hide', scope: 'stage', label: 'Hide / show', icon: EyeOff, keys: 'H', placement: ['inspector', 'context'], when: hasSel, run: () => { const o = sel()!; st().updateObject(o.id, { visible: !o.visible }) } },
  { id: 'stage.object.reset', scope: 'stage', label: 'Reset transform', icon: LockOpen, placement: ['inspector', 'context'], when: hasSel, run: () => { const o = sel()!; st().setTransform(o.id, { pos: [o.transform.pos[0], 0, o.transform.pos[2]], rot: [0, 0, 0], scale: [1, 1, 1] }) } },
  { id: 'stage.camera.add', scope: 'stage', label: 'Add camera', icon: Camera, placement: ['panel', 'context'], when: hasStage, run: () => st().addCamera() },
  { id: 'stage.camera.setFromView', scope: 'stage', label: 'Set the camera from the view', icon: Video, placement: ['panel', 'inspector', 'context'], when: () => hasStage() && !!st().activeCamera() && st().view === 'free',
    run: () => { const c = st().activeCamera(); const p = viewport.freePose?.(); if (c && p) st().updateCamera(c.id, { pos: p.pos, target: p.target }) } },
  // 17 SY2 (D85): the camera becomes a Story shot's source — its ST3 frame and ST4 clip arrive on the shot as takes
  { id: 'stage.camera.toShot', scope: 'stage', label: 'New shot from this camera…', icon: Clapperboard, placement: ['panel', 'inspector', 'context'], when: () => hasStage() && !!st().activeCamera(),
    run: () => { const cur = st().current; const cam = st().activeCamera(); if (!cur || !cam) return
      void askText({ title: 'New shot from this camera', text: 'A Story shot pointing at this camera: the frames and clips you generate here become its takes; the first fills the slot.', initial: `${cur.name} · ${cam.name}`, placeholder: 'shot name' })
        .then((n) => { if (n?.trim()) void import('../story/storyStore').then((m) => m.makeShotAndOpen(n.trim(), { stage_id: cur.id, camera_id: cam.id })) }) } },
  { id: 'stage.camera.rename', scope: 'stage', label: 'Rename camera…', icon: Pencil, placement: ['panel', 'context'], when: () => !!st().activeCamera(),
    run: () => { const c = st().activeCamera()!; void askText({ title: 'Rename camera', initial: c.name }).then((n) => { if (n?.trim()) st().updateCamera(c.id, { name: n.trim() }) }) } },
  { id: 'stage.camera.delete', scope: 'stage', label: 'Delete camera', icon: Trash2, placement: ['panel', 'inspector', 'context'], when: () => (st().current?.cameras.length ?? 0) > 1, run: () => { const c = st().activeCamera(); if (c) st().removeCamera(c.id) } },
  // ST2: posing
  { id: 'stage.pose.mirror', scope: 'stage', label: 'Mirror the pose', icon: Copy, keys: 'M', placement: ['panel', 'inspector', 'context'], when: () => sel()?.kind === 'mannequin', run: () => st().mirrorPose(st().selected!) },
  { id: 'stage.pose.reset', scope: 'stage', label: 'Reset the pose (stand)', icon: LockOpen, placement: ['panel', 'inspector', 'context'], when: () => sel()?.kind === 'mannequin', run: () => st().resetPose(st().selected!) },
  { id: 'stage.pose.save', scope: 'stage', label: 'Save pose…', icon: Plus, placement: ['panel', 'context'], when: () => sel()?.kind === 'mannequin',
    run: () => void askText({ title: 'Save pose', text: "The figure's joints, as a preset of this project.", placeholder: 'pose name' }).then((n) => { if (n?.trim()) void st().savePose(n.trim(), st().selected!) }) },
  // D93 (C8): a figure bound to a Cast character (the Inspector's tiles, "Bind to a character ▸" pick it; these end it or open the character)
  { id: 'stage.figure.unbind', scope: 'stage', label: 'Unbind the character', icon: UserX, placement: ['inspector', 'context'], when: () => !!sel()?.profile_id, run: () => st().bindFigure(st().selected!, null) },
  { id: 'stage.figure.openInCast', scope: 'stage', label: 'Open the character in Story · Cast', icon: UserRound, placement: ['inspector', 'context'], when: () => !!sel()?.profile_id,
    run: () => { const o = sel(); if (o?.profile_id) void import('../../store/origin').then((m) => m.goToStory({ tab: 'cast', id: o.profile_id!, ...(o.version ? { version: o.version } : {}) })) } },
  // ST3: the frame (the Render tab; D90 02 §8.1: a shot is a Story shot)
  { id: 'stage.shot.generate', scope: 'stage', label: 'Render frame', icon: Aperture, placement: ['panel', 'context'], when: () => hasStage() && !!st().activeCamera() && !st().rendering,
    run: () => void st().generateShot() },
  { id: 'stage.shot.passes', scope: 'stage', label: 'Render the passes', icon: Layers, keys: 'Ctrl+Enter', placement: ['panel', 'context'], when: () => hasStage() && !!st().activeCamera() && !st().rendering, run: () => void st().renderPasses() },
  { id: 'stage.shot.clearRefs', scope: 'stage', label: 'Clear the references', icon: X, placement: ['panel'], when: () => st().shot.refs.length > 0, run: () => st().setShot({ refs: [] }) },
  // ST4: keyframes and the clip — D90 (02 §8.2): the transport keys of Animate and the Episode lane; the previous / next key moved to Alt+← / →
  // D99 (UX0 #19): the viewer levels by number — 2 goes to Performance from here (1, Clay, is this level); the strip's switch is their mouse home
  { id: 'stage.level.performance', scope: 'stage', label: 'Animate · Performance', keys: '2', placement: ['strip'], run: () => useSession.getState().setSuite('animate') },
  { id: 'stage.level.final', scope: 'stage', label: 'Animate · Final', keys: '3', placement: ['strip'], run: () => useSession.getState().setSuite('final') },   // AE1 / AP1 (D114) → D121: a suite of its own
  { id: 'stage.anim.play', scope: 'stage', label: 'Play / pause', icon: Play, keys: 'Space', placement: ['strip'], when: hasStage, run: () => st().setPlaying(!st().playing) },
  { id: 'stage.anim.prev', scope: 'stage', label: 'Previous frame', icon: StepBack, keys: 'ArrowLeft', placement: ['strip'], when: hasStage, run: () => st().setFrame(st().frame - 1) },
  { id: 'stage.anim.next', scope: 'stage', label: 'Next frame', icon: StepForward, keys: 'ArrowRight', placement: ['strip'], when: hasStage, run: () => st().setFrame(st().frame + 1) },
  { id: 'stage.anim.prevKey', scope: 'stage', label: 'Previous key', icon: SkipBack, keys: 'Alt+ArrowLeft', placement: ['strip'], when: hasStage, run: () => { const f = neighbourKey(st().keyedFrames(), st().frame, -1); if (f != null) st().setFrame(f) } },
  { id: 'stage.anim.nextKey', scope: 'stage', label: 'Next key', icon: SkipForward, keys: 'Alt+ArrowRight', placement: ['strip'], when: hasStage, run: () => { const f = neighbourKey(st().keyedFrames(), st().frame, 1); if (f != null) st().setFrame(f) } },
  { id: 'stage.anim.back10', scope: 'stage', label: 'Back 10 frames', icon: ChevronLeft, keys: 'Shift+ArrowLeft', placement: ['strip'], when: hasStage, run: () => st().setFrame(st().frame - 10) },
  { id: 'stage.anim.fwd10', scope: 'stage', label: 'Forward 10 frames', icon: ChevronRight, keys: 'Shift+ArrowRight', placement: ['strip'], when: hasStage, run: () => st().setFrame(st().frame + 10) },
  { id: 'stage.anim.first', scope: 'stage', label: 'First frame (range start)', icon: ChevronFirst, keys: 'Home', placement: ['strip'], when: hasStage, run: () => { st().setPlaying(false); st().setFrame(st().current!.range.start) } },
  { id: 'stage.anim.last', scope: 'stage', label: 'Last frame (range end)', icon: ChevronLast, keys: 'End', placement: ['strip'], when: hasStage, run: () => { st().setPlaying(false); st().setFrame(st().current!.range.end) } },
  { id: 'stage.anim.keyCamera', scope: 'stage', label: 'Key the camera here', icon: Diamond, placement: ['strip', 'context'], when: () => hasStage() && !!st().activeCamera(), run: () => st().keyCamera() },
  { id: 'stage.anim.keyObject', scope: 'stage', label: 'Key the selection here (the object; nothing selected: the camera)', icon: Diamond, keys: 'Shift+K', placement: ['strip', 'inspector', 'context'], when: () => hasStage() && (!!st().selected || !!st().activeCamera()),
    run: () => { const id = st().selected; if (id) st().keyObject(id); else st().keyCamera() } },   // D99 (UX0 #19): Shift+K keys the selection, else the camera
  { id: 'stage.anim.removeKey', scope: 'stage', label: 'Remove the keys at this frame', icon: X, keys: 'Alt+Shift+K', placement: ['strip', 'context'], when: () => hasStage() && st().keyedFrames().includes(st().frame), run: () => st().removeKeyAt(st().frame) },
  { id: 'stage.anim.setStart', scope: 'stage', label: 'Range starts here (in)', icon: Diamond, keys: 'I', placement: ['strip'], when: hasStage, run: () => st().setRange(st().frame, Math.max(st().frame + 1, st().current!.range.end)) },
  { id: 'stage.anim.setEnd', scope: 'stage', label: 'Range ends here (out)', icon: Diamond, keys: 'O', placement: ['strip'], when: hasStage, run: () => st().setRange(Math.min(st().frame - 1, st().current!.range.start), st().frame) },
  { id: 'stage.clip.guide', scope: 'stage', label: 'Render the sequence', icon: Layers, placement: ['panel', 'context'], when: () => hasStage() && !!st().activeCamera() && !st().rendering, run: () => void st().renderGuide() },
  { id: 'stage.clip.animate', scope: 'stage', label: 'Render clip', icon: Clapperboard, placement: ['panel', 'context'], when: () => hasStage() && !!st().activeCamera() && !!st().shotStart && !st().rendering && !!st().clipCaps(),
    run: () => void (async () => { if ((!st().guideEntry() || st().guideStale()) && !(await st().renderGuide())) return; await st().animateShot() })() },   // D121: the sequence first when missing or stale
  // D121: the stills of a stage are made in Image (D95) — the stage clip's start picker sends there; pose mode by the figure, not by the column
  { id: 'stage.frame.make', scope: 'stage', label: 'Make a frame (Image · From a stage)', icon: Aperture, placement: ['panel'], when: hasStage,
    run: () => { void import('../generate/generateStore').then((g) => g.useGenerate.setState({ source: 'stage' })); useSession.getState().setSuite('generate') } },
  { id: 'stage.pose.mode', scope: 'stage', label: 'Pose the figure', hint: 'its joints and hands in the viewport; again (Done) to stop', icon: PersonStanding, placement: ['toolbar', 'context'],
    when: () => sel()?.kind === 'mannequin', run: () => st().setPosing(!st().posing) },
  // D111 (PS5): the finished scene split into layers (the passes rendered here; the layers are made from them on the queue)
  { id: 'stage.final.make', scope: 'stage', label: 'Make the final shot…', icon: Layers, hint: 'the scene through the active camera, split into layers: the plate, each character, each prop, the shadows',
    placement: ['panel'], when: () => hasStage() && !!st().activeCamera() && !useFinals.getState().making && !st().rendering, run: () => void useFinals.getState().make(16) },
  // D121: Performance › Final shot's foot — the newest final's next step (make it, the plate, each character, assemble, compose, open in Final)
  { id: 'stage.final.next', scope: 'stage', label: "The final shot's next step", icon: Layers, placement: ['panel'], when: () => !!nextFinalStep(st().current?.id ?? null).run,
    run: () => nextFinalStep(st().current?.id ?? null).run?.() },
  { id: 'stage.undo', scope: 'stage', label: 'Undo', icon: Undo2, keys: 'Ctrl+Z', placement: ['toolbar', 'context'], when: () => st().undo.length > 0, run: () => st().undoEdit() },
  { id: 'stage.redo', scope: 'stage', label: 'Redo', icon: Redo2, keys: 'Ctrl+Shift+Z', placement: ['toolbar', 'context'], when: () => st().redo.length > 0, run: () => st().redoEdit() },
])

export const addMenu = (): MenuItem => ({ label: 'Add', icon: Plus, items: [
  ...Object.keys(MANNEQUIN_PRESETS).map((p) => ({ cmd: `stage.add.mannequin.${p}` })), sep,
  ...SET_PRESETS.map((p) => ({ cmd: `stage.add.set.${p}` })), { cmd: 'stage.add.set.image' }, sep,
  ...PROP_PRESETS.map((p) => ({ cmd: `stage.add.prop.${p}` })), sep,
  { cmd: 'stage.add.light' },
] })

/** D93 (C8): "Bind to a character ▸" — the right-click submenu of a figure (the viewport, the Outliner row): the Cast's characters (the one
 *  bound checked), then unbind and open it in Cast. */
export function bindItems(): MenuItem[] {
  const o = sel()
  if (!o || o.kind !== 'mannequin') return []
  const chars = profilesForMentions().filter((p) => p.cls === 'character')
  return [{ label: 'Bind to a character', icon: UserRound, items: [
    ...(chars.length ? chars.map((p): MenuItem => ({ label: p.name, checked: o.profile_id === p.id, run: () => st().bindFigure(o.id, p.id) })) : [{ label: 'no characters in the Cast yet', disabled: true, run: () => {} }]),
    sep, { cmd: 'stage.figure.unbind' }, { cmd: 'stage.figure.openInCast' }] }]
}

/** Right-click on an object (selected by the caller) or on empty space. */
export function viewportMenu(onObject: boolean): MenuItem[] {
  return onObject
    ? [{ cmd: 'stage.frameSel' }, { cmd: 'stage.object.rename' }, { cmd: 'stage.object.duplicate' }, { cmd: 'stage.object.lock' }, { cmd: 'stage.object.hide' }, { cmd: 'stage.object.reset' }, sep,
      ...(sel()?.kind === 'mannequin' ? [...bindItems(), { cmd: 'stage.pose.mode' }, { cmd: 'stage.pose.mirror' }, { cmd: 'stage.pose.reset' }, { cmd: 'stage.pose.save' }, { cmd: 'stage.motion.apply' }, { cmd: 'stage.path.clear' }, sep] : []),
      { cmd: 'stage.anim.keyObject' }, sep, { cmd: 'stage.object.delete' }, sep, { cmd: 'stage.undo' }, { cmd: 'stage.redo' }]
    : [addMenu(), { cmd: 'stage.add.plane' }, { cmd: 'stage.camera.add' }, { cmd: 'stage.camera.setFromView' }, { cmd: 'stage.camera.toShot' }, sep, { cmd: 'stage.tool.select' }, { cmd: 'stage.tool.move' }, { cmd: 'stage.tool.rotate' }, { cmd: 'stage.tool.scale' }, { cmd: 'stage.tool.path' }, { cmd: 'stage.snap' }, sep, { cmd: 'stage.frameAll' }, sep,
      { cmd: 'stage.shot.passes' }, { cmd: 'stage.shot.generate' }, sep, { cmd: 'stage.anim.keyCamera' }, { cmd: 'stage.anim.removeKey' }, { cmd: 'stage.clip.guide' }, { cmd: 'stage.clip.animate' }, sep,
      { cmd: 'stage.undo' }, { cmd: 'stage.redo' }, sep, { label: 'Stage', icon: Frame, items: [{ cmd: 'stage.rename' }, { cmd: 'stage.delete' }, sep, { cmd: 'stage.new' }] }]
}

/** The right-click menu of a camera row (the camera is made active first). */
export function cameraMenu(): MenuItem[] {
  return [{ cmd: 'stage.view.camera' }, { cmd: 'stage.camera.setFromView' }, { cmd: 'stage.camera.toShot' }, sep, { cmd: 'stage.camera.rename' }, { cmd: 'stage.camera.add' }, sep, { cmd: 'stage.camera.delete' }]
}

export { useStage }
