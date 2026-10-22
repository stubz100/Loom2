// P13 / ST1 (D81): the Stage suite's parts (16; StageSuite.ts registers them) — Panel (Library · Outliner · Cameras), Strip (view, guides, frame), the viewport Stage with
// its floating gizmo bar and the framing rectangle, the Inspector (object · camera · stage). Mouse-first (D32): every verb is a
// button or a menu entry; keys are accelerators. Keep-alive (D69): the engine pauses while the suite is hidden and keeps its view. D93 (C8):
// a figure is bound to a Cast character (the Inspector's tiles, "Bind to a character ▸"); the Outliner shows who; the Render tab's deck shows
// which images are a figure's (the preview's `ref_list`) and how each figure is said in the prompt.
import { AnimateLevels } from '../../frame/AnimateLevels'
import { Help } from '../../frame/Help'
import { Bookmark, Box, Camera, Eye, EyeOff, Frame, LayoutTemplate, Lock, LockOpen, PersonStanding, User } from 'lucide-react'
import { PresetPanel } from '../../frame/PresetPanel'
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { CommandButton, CommandRow } from '../../frame/CommandButton'
import { handleKeyFor, markUsed, runCommand } from '../../frame/commands'
import { inField, primaryInField } from '../../frame/fieldKeys'
import { showMenu } from '../../frame/ContextMenu'
import { onlyAssets, useDropTarget } from '../../frame/drag'
import { shotRefDrop } from '../../frame/dropRules'
import { api } from '../../api/client'
import { DEV_HOOKS } from '../../devHooks'
import { BoundTag, FigureCharacter, LibraryProps, MeshProp } from './FigureBinding'
import { AmbientControl, LightControls } from './LightControls'
import { FinalSection } from './FinalPanel'
import { assembling, readyToAssemble, rendering as compRendering, useFinals } from './finalShot'
import { MotionLibrary } from './motion/MotionLibrary'
import { HAND_PRESETS, type HandPreset } from './detailed'
import { useStageActive } from '../../frame/stageKeep'
import { useSuiteRail } from '../../frame/suiteRegistry'
import { askConfirm, askText, useSession } from '../../store/session'
import type { Asset, StageCamera, StageObject } from '../../api/types'
import { keyedFrames as keyedFramesOf, keyframesOf, sampleDoc } from './anim'
import { JOINTS, MANNEQUIN_PRESETS, POSE_NAMES, PROP_PRESETS, SET_PRESETS, type Joint } from './builders'
import { StageEngine } from './engine'
import { viewport, viewportMenu, cameraMenu } from './stageCommands'
import { effectiveJoints, st, TEMPLATE_KINDS, useStage, type ShotState } from './stageStore'
import './stage.css'

const FOCALS = [24, 35, 50, 85]
const num = (v: number) => +v.toFixed(2)

/** Dev hook (`window.__loom2Stage`, DEV_HOOKS only): the smoke test and scripts/st_acceptance.py drive the suite through the store — present as
 *  soon as the suite's code loads; the viewport adds `screenOf` when it mounts. */
function devHook(): Record<string, unknown> {
  const w = window as unknown as { __loom2Stage?: Record<string, unknown> }
  w.__loom2Stage ??= { open: (id: string) => st().open(id), setShot: (p: Partial<ShotState>) => st().setShot(p), renderPasses: () => st().renderPasses(),
    generateShot: () => st().generateShot(), state: () => ({ current: st().current, shot: st().shot, passes: st().passesEntry(), guide: st().guideEntry(), frame: st().frame }), screenOf: () => null,
    // ST4: the clip path
    setFrame: (f: number) => st().setFrame(f), keyCamera: () => st().keyCamera(), setRange: (a: number, b: number) => st().setRange(a, b), setGuideKind: (k: 'depth' | 'pose') => st().setGuideKind(k),
    renderGuide: () => st().renderGuide(), setShotStart: (id: string | null) => st().setShotStart(id), animateShot: () => st().animateShot(),
    updateCamera: (id: string, patch: Partial<StageCamera>) => st().updateCamera(id, patch), setTransform: (id: string, t: { pos: number[]; rot: number[]; scale: number[] }) => st().setTransform(id, t),
    frameAll: () => st().frameView(null),
    bindFigure: (id: string, pid: string | null, v?: string | null) => st().bindFigure(id, pid, v ?? null), select: (id: string | null) => st().select(id),   // D93 (C8)
    selectCamera: (id: string | null) => st().selectCamera(id) }   // D119 (SC1)
  return w.__loom2Stage
}
if (DEV_HOOKS) devHook()

// ------------------------------------------------------------------ Panel
/** D95 (AN1): the project's stages — Animate's Shot section. */
export function StageList() {
  const current = useStage((s) => s.current)
  const stages = useStage((s) => s.stages)
  return (
    <div className="stage-panel">
      <div className="stage-list">
        <div className="head"><b>Stages</b><CommandButton id="stage.new" /></div>
        {!stages.length && <span className="hint">None yet.</span>}
        {stages.map((s) => (
          <button key={s.id} className={`stage-row${current?.id === s.id ? ' active' : ''}`} onClick={() => void st().open(s.id)} title={`${s.size.w}×${s.size.h} @ ${s.size.fps} · revision ${s.revision}`}>
            <span className="name">{s.name}</span><span className="meta">{s.objects.length} object{s.objects.length === 1 ? '' : 's'} · {s.cameras.length} cam</span>
          </button>
        ))}
      </div>
    </div>
  )
}

/** D95 (AN1): what can be put on the stage — Animate's Scene section (with the Outliner). D119 (SC2): the preset groups (figures, sets,
 *  stand-ins) and the author's templates sit behind a + each, as Image's fields; Cast props and meshes keep their picture cards. */
export function LibraryAdd() {
  const current = useStage((s) => s.current)
  const meshes = useStage((s) => s.meshes)
  const templates = useStage((s) => s.templates)
  if (!current) return <span className="hint">Open or make a stage in the Shot section.</span>
  const figures = Object.entries(MANNEQUIN_PRESETS).map(([p, m]) => ({ id: p, label: m.label, icon: <User size={18} /> }))
  const sets = SET_PRESETS.map((p) => ({ id: p, label: p, icon: <Box size={18} />, hint: 'architecture only (D108)' }))
  const standins = PROP_PRESETS.map((p) => ({ id: p, label: p, icon: <Box size={18} />, hint: 'a grey stand-in shape (D109)' }))
  const tmpl = templates.map((t) => ({ id: t.name, label: t.name, icon: <LayoutTemplate size={18} />, hint: `${t.objects.length} object${t.objects.length === 1 ? '' : 's'}`, img: t.thumb_asset_id ? api.thumbUrl(t.thumb_asset_id, 256) : null }))
  const holds = current.objects.filter((o) => TEMPLATE_KINDS.has(o.kind)).length
  return (
    <div className="stage-panel library">
      <>
        <div className="lib-row" data-group="figures"><span className="lib-label">Figures</span>
          <PresetPanel label="figure presets" items={figures} showText onPick={(id) => runCommand(`stage.add.mannequin.${id}`)} title="A figure at the viewport's centre: a mannequin to pose and bind to a character" /></div>
        <div className="lib-row" data-group="sets"><span className="lib-label">Sets</span>
          <PresetPanel label="set presets" items={sets} showText onPick={(id) => runCommand(`stage.add.set.${id}`)} title="A set at the viewport's centre: architecture only — room, street, deck, empty (D108)" /></div>
        <div className="lib-row" data-group="templates"><span className="lib-label">Templates <Help text="An arrangement of this level — the set with its props, meshes, planes and lights, not the figures or the cameras — saved under a name from the stage you have, and added to any stage by a click. The author's own library beside the presets." /></span>
          <PresetPanel label="stage templates" items={tmpl} showText onPick={(id) => st().applyTemplate(id)} empty="No templates yet — arrange a set with its props and lights, then save it here."
            title="Your templates: an arrangement saved under a name; a click adds it to this stage" saveLabel="Save this arrangement as a template…" canSave={holds > 0} saveWhy="the stage has no set, prop, plane or light to save yet"
            onSave={(name) => st().saveTemplate(name || `Template ${templates.length + 1}`)}
            verbs={(f) => (f ? <button type="button" className="quiet danger" onClick={() => void askConfirm({ title: `Delete the template "${f}"?`, okLabel: 'Delete', danger: true }).then((ok) => { if (ok) void st().deleteTemplate(f) })}>Delete “{f}”</button>
              : <span className="hint">Click a template: it is added to the stage; it can be deleted here.</span>)} /></div>
        <h4>Props</h4>{/* D110 (PS3): Story · Props, each its 3D model bound to the prop */}
        <LibraryProps centre={() => viewport.centre?.() ?? [0, 0, 0]} />
        <div className="lib-row" data-group="standins"><span className="lib-label">Stand-ins <Help text="Grey shapes for blocking (D109)." /></span>
          <PresetPanel label="stand-in presets" items={standins} showText onPick={(id) => runCommand(`stage.add.prop.${id}`)} title="A grey stand-in shape at the viewport's centre" /></div>
        <h4>Meshes{meshes.length ? ` · ${meshes.length}` : ''}</h4>
        {!meshes.length && <span className="hint">None yet. <Help text={`A Catalogue image's "Make a 3D prop…" (Pixal3D) lands here.`} /></span>}
        <div className="lib-grid">{meshes.slice(0, 24).map((m) => (
          <button key={m.id} className="mesh-card" title={`${m.id} · add to the stage at the viewport's centre`} onClick={() => st().addObject('mesh', null, viewport.centre?.() ?? [0, 0, 0], m.id)}>
            <img src={api.thumbUrl(m.id, 256)} alt="" /><span>prop {m.id.slice(-6)}</span>
          </button>))}</div>
        <div className="lib-row" data-group="lights"><span className="lib-label">Lights</span><CommandButton id="stage.add.light" text /></div>{/* D110 (PS4): a sun aimed at the viewport's centre; its settings under its row */}
        <div className="lib-row" data-group="planes"><span className="lib-label">Image planes</span><CommandButton id="stage.add.plane" text label="Add image plane…" /></div>
        <p className="hint">From the Bin <Help text="Drag an image onto the viewport (it lands where the pointer is), or double-click it there (the viewport's centre). Each card above adds at the centre." /></p>
      </>
    </div>
  )
}

/** D95 (AN1, UX0 #16): the active camera's passes at a glance in Scene — rendered or not, current or behind the scene — and Render passes. */
export function PassesRow() {
  const current = useStage((s) => s.current)
  const cam = useStage((s) => s.activeCamera())
  const entry = useStage((s) => s.passesEntry())
  const stale = useStage((s) => s.passesStale())
  const rendering = useStage((s) => s.rendering)
  if (!current || !cam) return null
  return (
    <div className="stage-panel passes-row">
      <span className="hint">{entry ? `Passes · ${cam.name} · ${Object.keys(entry.assets).length} at ${entry.size.w}×${entry.size.h} · ${stale ? `revision ${entry.revision}, the scene moved on` : 'current'}` : `No passes yet for ${cam.name}`}</span>
      <CommandButton id="stage.shot.passes" text label={rendering ? 'Rendering…' : entry && !stale ? 'Render again' : 'Render passes'} />
    </div>
  )
}

/** D119 (SC1): the scene outliner — every thing of the stage as a row (the stage itself, the objects, the cameras); the selected row's
 *  editor opens under it (UX9 U1's pattern), so nothing is edited far from its row. A camera row selects the camera as an object (its
 *  body takes the gizmo in the viewport) and makes it the active one. */
export function OutlinerTab() {
  const current = useStage((s) => s.current)
  const selected = useStage((s) => s.selected)
  const selectedCamera = useStage((s) => s.selectedCamera)
  const stageSelected = useStage((s) => s.stageSelected)
  const saving = useStage((s) => s.saving)
  if (!current) return null
  const rename = (id: string, name: string) => void askText({ title: 'Rename', initial: name, placeholder: 'name' }).then((n) => { if (n?.trim()) st().updateObject(id, { name: n.trim() }) })
  const renameCam = (c: StageCamera) => void askText({ title: 'Rename camera', initial: c.name }).then((n) => { if (n?.trim()) st().updateCamera(c.id, { name: n.trim() }) })
  return (
    <div className="stage-panel outliner" aria-label="the scene outliner">
      <div className="head"><b>Outliner</b><span className="hint">{current.objects.length} object{current.objects.length === 1 ? '' : 's'} · {current.cameras.length} camera{current.cameras.length === 1 ? '' : 's'}</span>
        <Help text="Everything on the stage, one row each: the stage, its objects and its cameras. Click a row to edit the thing under it — its transform, its own settings, its verbs; click again to close. A camera's row selects its body in the viewport too (drag it there; double-click looks through it)." /></div>
      <div className={`outl-row${stageSelected ? ' active' : ''}`} data-row="stage" onClick={() => (stageSelected ? st().select(null) : st().selectStage())}
        onDoubleClick={() => st().frameView(null)}>
        <Frame size={13} /><span className="name">{current.name}</span><span className="meta">{current.size.w}×{current.size.h} @ {current.size.fps}{saving ? ' · saving…' : ''}</span>
        {stageSelected && <StageEditor />}
      </div>
      {!current.objects.length && <span className="hint">Nothing on the stage yet. <Help text="Add from the Library above, or drop a Catalogue image or model on the viewport." /></span>}
      {current.objects.map((o) => (
        <div key={o.id} className={`outl-row${selected === o.id ? ' active' : ''}${o.visible ? '' : ' hidden'}`} data-row="object" data-kind={o.kind} onClick={() => st().select(selected === o.id ? null : o.id)}
          onDoubleClick={() => st().frameView([o.id])} onContextMenu={(e) => { e.preventDefault(); st().select(o.id); showMenu(e, viewportMenu(true)) }}>
          <span className="swatch" style={{ background: `hsl(${(o.colour_id * 137) % 360} 55% 50%)` }} />
          <span className="kind">{o.kind}</span>
          <span className="name" onDoubleClick={(e) => { e.stopPropagation(); rename(o.id, o.name) }}>{o.name}</span>
          {(o.kind === 'mannequin' || o.kind === 'mesh') && o.profile_id && <BoundTag o={o} />}
          <button className="quiet" title={o.visible ? 'Hide' : 'Show'} onClick={(e) => { e.stopPropagation(); st().updateObject(o.id, { visible: !o.visible }) }}>{o.visible ? <Eye size={13} /> : <EyeOff size={13} />}</button>
          <button className="quiet" title={o.locked ? 'Unlock' : 'Lock'} onClick={(e) => { e.stopPropagation(); st().updateObject(o.id, { locked: !o.locked }) }}>{o.locked ? <Lock size={13} /> : <LockOpen size={13} />}</button>
          {selected === o.id && <ObjectEditor o={o} />}
        </div>
      ))}
      {current.cameras.map((c) => (
        <div key={c.id} className={`outl-row${selectedCamera === c.id ? ' active' : ''}${current.active_camera === c.id ? ' cam-active' : ''}`} data-row="camera"
          onClick={() => st().selectCamera(selectedCamera === c.id ? null : c.id)} onDoubleClick={() => { st().selectCamera(c.id); st().setView('camera') }}
          onContextMenu={(e) => { e.preventDefault(); st().selectCamera(c.id); showMenu(e, cameraMenu()) }}>
          <Camera size={13} /><span className="kind">camera</span>
          <span className="name" onDoubleClick={(e) => { e.stopPropagation(); renameCam(c) }}>{c.name}</span>
          {current.active_camera === c.id && <span className="meta" title="The active camera: the one the shot renders through">★</span>}
          <span className="meta">{c.focal_mm} mm</span>
          {selectedCamera === c.id && <CameraEditor c={c} />}
        </div>
      ))}
    </div>
  )
}

/** D119 (SC1): the stage's own editor under its row — the frame, the contents, the ambient (D110), rename / delete. */
function StageEditor() {
  const current = useStage((s) => s.current)
  if (!current) return null
  return (
    <div className="row-editor stage-insp" onClick={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()}>
      <h4>{current.name} <span className="hint">· revision {current.revision}</span></h4>
      <div className="kv"><span>frame</span><span>{current.size.w}×{current.size.h} @ {current.size.fps} fps (the project format)</span></div>
      <div className="kv"><span>contents</span><span>{current.objects.length} objects · {current.cameras.length} cameras</span></div>
      <AmbientControl />{/* D110 (PS4): the sky under the lights */}
      <div className="verbs"><CommandRow ids={['stage.frameAll', 'stage.rename', 'stage.delete']} /></div>
    </div>
  )
}

/** D119 (SC1): an object's editor under its row — the transform, the kind's own fields, the parent, the object verbs (the Selection section of before). */
function ObjectEditor({ o }: { o: StageObject }) {
  const current = useStage((s) => s.current)
  const t = o.transform
  if (!current) return null
  return (
    <div className="row-editor stage-insp" onClick={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()}>
      <h4>{o.name} <span className="hint">· {o.kind}{o.preset ? ` · ${o.preset}` : ''}</span></h4>
      <Vec label="position" v={t.pos} onChange={(pos) => st().setTransform(o.id, { ...t, pos })} />
      <Vec label="rotation" v={t.rot} onChange={(rot) => st().setTransform(o.id, { ...t, rot })} step={1} />
      <Vec label="scale" v={t.scale} onChange={(scale) => st().setTransform(o.id, { ...t, scale })} step={0.05} />
      {o.kind === 'mannequin' && <FigureCharacter o={o} />}
      {o.kind === 'mesh' && <MeshProp o={o} />}
      {o.kind === 'light' && <LightControls o={o} />}
      {o.kind === 'mannequin' && <div className="kv"><span>pose</span><span><select value={o.pose?.preset ?? 'stand'} onChange={(e) => st().applyPose(o.id, e.target.value)}>{POSE_NAMES.map((p) => <option key={p} value={p}>{p}</option>)}</select> <span className="hint">(the Motion section poses the joints)</span></span></div>}
      {o.kind === 'plane' && <div className="kv"><span>faces camera</span><input type="checkbox" checked={o.billboard} onChange={(e) => st().updateObject(o.id, { billboard: e.target.checked })} /></div>}
      <div className="kv"><span>parent</span><select value={o.parent ?? ''} onChange={(e) => st().updateObject(o.id, { parent: e.target.value || null })}><option value="">— none —</option>{current.objects.filter((x) => x.id !== o.id).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></div>
      <div className="verbs"><CommandRow ids={['stage.object.duplicate', 'stage.object.lock', 'stage.object.hide', 'stage.frameSel', 'stage.object.reset', 'stage.object.delete']} /></div>
    </div>
  )
}

/** D119 (SC1): a camera's editor under its row — the lens, the roll, where it stands and what it looks at, and its verbs (Look through,
 *  Set from view, To shot, Key camera, rename, delete). In the viewport the camera's body takes the gizmo while its row is selected. */
function CameraEditor({ c }: { c: StageCamera }) {
  const current = useStage((s) => s.current)
  const view = useStage((s) => s.view)
  if (!current) return null
  markUsed('stage.camera.setFromView'); markUsed('stage.camera.delete'); markUsed('stage.view.camera'); markUsed('stage.camera.rename'); markUsed('stage.anim.keyCamera')
  return (
    <div className="row-editor stage-insp" onClick={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()}>
      <h4>{c.name} <span className="hint">· camera{current.active_camera === c.id ? ' · active' : ''}</span></h4>
      <Vec label="position" v={c.pos} onChange={(pos) => st().updateCamera(c.id, { pos })} />
      <Vec label="target" v={c.target} onChange={(target) => st().updateCamera(c.id, { target })} />
      <div className="kv"><span>focal</span>
        <span className="focals">{FOCALS.map((f) => <button key={f} className={c.focal_mm === f ? 'active' : ''} onClick={() => st().updateCamera(c.id, { focal_mm: f })}>{f}</button>)}
          <input type="number" min={8} max={400} step={1} value={c.focal_mm} onChange={(e) => st().updateCamera(c.id, { focal_mm: Math.max(8, Math.min(400, Number(e.target.value) || 35)) })} /> mm</span></div>
      <div className="kv"><span>sensor</span><span>{c.sensor_mm} mm · frame {current.size.w}×{current.size.h}</span></div>
      <div className="kv"><span>roll</span><input type="number" step={1} value={c.roll} onChange={(e) => st().updateCamera(c.id, { roll: Number(e.target.value) || 0 })} /></div>
      <div className="verbs">
        <CommandButton id="stage.view.camera" text label={view === 'camera' ? 'Back to the free view' : 'Look through'} active={view === 'camera'} />
        <CommandButton id="stage.camera.setFromView" text label="Set from view" />
        <CommandButton id="stage.anim.keyCamera" text />
        <CommandButton id="stage.camera.toShot" text />
        <CommandButton id="stage.camera.rename" />
        <CommandButton id="stage.camera.delete" />
      </div>
      <Help text="Position and target are metres on the stage; drag the camera's body in the free view to move both together. Set from view puts the camera where the free view is. Look through shows the frame it renders; Key camera keeps this placement at the playhead (ST4)." />
    </div>
  )
}

/** D119 (SC1): the Camera section is the shot's camera — the active one at a glance and the verbs that act on it; each camera's own
 *  fields are under its row in the Scene's outliner (CameraEditor). */
export function CamerasTab() {
  const current = useStage((s) => s.current)
  const view = useStage((s) => s.view)
  const cam = useStage((s) => s.activeCamera())
  if (!current) return <span className="hint">Open or make a stage in the Shot section.</span>
  markUsed('stage.camera.add'); markUsed('stage.frameAll')
  return (
    <div className="stage-panel">
      <div className="head"><b>Cameras</b><span className="hint">{current.cameras.length}</span><CommandButton id="stage.camera.add" /></div>
      {cam && <>
        <div className="kv"><span>active</span><span><button className="quiet" title="Its row in the Scene's outliner: the lens, the roll, where it stands" onClick={() => { st().selectCamera(cam.id); document.getElementById('anim-sec-scene')?.scrollIntoView({ block: 'start', behavior: 'smooth' }) }}>{cam.name}</button> <span className="hint">· {cam.focal_mm} mm</span></span></div>
        <div className="verbs">
          <CommandButton id="stage.view.camera" text label={view === 'camera' ? 'Back to the free view' : 'Look through'} active={view === 'camera'} />
          <CommandButton id="stage.camera.setFromView" text label="Set from view" />
          <CommandButton id="stage.frameAll" text label="Frame all" />
        </div>
        <div className="verbs"><CommandButton id="stage.camera.toShot" text /></div>
        <Help text="The shot renders through the active camera (★ in the outliner). To move it: drag its body in the free view, or type where it stands under its row; Set from view puts it where the free view is." />
      </>}
    </div>
  )
}

// ST2 (16 §3d): presets (built-in + the project's saved ones), the pose verbs, the selected joint's angles. While this tab is open the
// viewport shows the joint pickers: click a joint for the rotate gizmo, click a hand / foot handle and drag it (two-bone IK).
/** CA1 (01 §9a): the figure's level — Simple blocks, Detailed refines (the starter set's mannequin follows the same joints: keys, clips and
 *  the pose pass are unchanged) — and, at the Detailed level, the hands' presets as turns of its finger bones (keyed with the pose). */
function DetailLevel({ o }: { o: StageObject }) {
  const detail = o.detail ?? null
  const hand = (side: 'r' | 'l', preset: HandPreset) => {
    const extra = viewport.handPreset?.(o.id, side, preset)
    if (!extra) { useSession.getState().toast('The Detailed mannequin is not on screen yet (it loads from the starter set)', 'info'); return }
    st().setExtra(o.id, extra, `${side === 'r' ? 'right' : 'left'} hand · ${preset}`)
  }
  return (
    <div className="detail-level">
      <div className="kv"><span>level</span>
        <span className="segmented" role="group" aria-label="figure level">
          {([[null, 'Simple'], ['male', 'Detailed ♂'], ['female', 'Detailed ♀']] as const).map(([k, label]) => (
            <button key={label} type="button" className={detail === k ? 'active' : ''} aria-pressed={detail === k} title={k ? 'the starter set\'s skinned mannequin (fingers, feet, a spine of three) follows this figure' : 'the 12-joint dummy (blocking)'}
              onClick={() => st().setDetail(o.id, k)}>{label}</button>))}
        </span>
      </div>
      {detail && (['r', 'l'] as const).map((side) => (
        <div key={side} className="kv"><span>{side === 'r' ? 'right hand' : 'left hand'}</span>
          <span className="lib-grid hands">{HAND_PRESETS.map((p) => <button key={p} type="button" onClick={() => hand(side, p)} title={`${p} — the ${side === 'r' ? 'right' : 'left'} hand's fingers`}>{p}</button>)}</span>
        </div>
      ))}
    </div>
  )
}

export function PosesTab() {
  const current = useStage((s) => s.current)
  const o = useStage((s) => s.object(s.selected))
  const joint = useStage((s) => s.selectedJoint)
  const userPoses = useStage((s) => s.userPoses)
  if (!current) return <span className="hint">Open or make a stage in the Shot section.</span>
  markUsed('stage.pose.mirror'); markUsed('stage.pose.reset'); markUsed('stage.pose.save')
  if (!o || o.kind !== 'mannequin') return <><MotionLibrary /><div className="stage-panel"><div className="head"><b>Poses</b></div><span className="hint">No figure selected. <Help text="Select a figure, then click a joint for the rotate gizmo, or drag a hand / foot handle." /></span></div></>
  const joints = effectiveJoints(o)
  const v = joint ? (joints[joint] ?? [0, 0, 0]) : null
  const setJoint = (nv: number[]) => { if (joint) st().setJoints(o.id, { ...joints, [joint]: nv }) }
  return (
    <>
    <MotionLibrary />{/* CA1: clips from the library first; presets and keys by hand below */}
    <div className="stage-panel">
      <div className="head"><b>{o.name}</b><span className="hint">pose · {o.pose?.preset ?? 'stand'}{Object.keys(o.pose?.joints ?? {}).length ? ' (edited)' : ''}</span></div>
      <DetailLevel o={o} />
      {(() => {                                                          // D119 (SC2): the poses behind a + — the built-in ones and the project's saved ones
        const edited = Object.keys(o.pose?.joints ?? {}).length > 0
        const built = POSE_NAMES.map((p) => ({ id: `preset:${p}`, label: p, icon: <PersonStanding size={18} />, hint: 'built in' }))
        const saved = Object.entries(userPoses).map(([name, def]) => ({ id: `saved:${name}`, label: name, icon: <Bookmark size={18} />, hint: `saved in this project · from ${def.preset ?? 'stand'}` }))
        const items = [...built, ...saved]
        const cur = o.pose?.preset && !edited ? `preset:${o.pose.preset}` : null
        return (
          <div className="lib-row" data-group="poses"><span className="lib-label">Poses</span>
            <PresetPanel label="pose presets" items={items} showText selected={cur} chosen={items.filter((i) => i.id === cur)}
              title="The poses: the built-in ones and the ones saved in this project; a click poses the figure" saveLabel="Save this pose…"
              onSave={(name) => void st().savePose(name || `Pose ${saved.length + 1}`, o.id)}
              onPick={(id) => { const k = id.slice(0, id.indexOf(':')), n = id.slice(id.indexOf(':') + 1); if (k === 'preset') st().applyPose(o.id, n); else { const d = userPoses[n]; if (d) st().applyPose(o.id, d.preset ?? 'stand', d.joints) } }}
              verbs={(f) => {
                if (!f?.startsWith('saved:')) return <span className="hint">Click a pose: the figure takes it; one saved here can be deleted.</span>
                const n = f.slice(6)
                return <button type="button" className="quiet danger" onClick={() => void askConfirm({ title: `Delete the pose "${n}"?`, okLabel: 'Delete', danger: true }).then((ok) => { if (ok) void st().deletePose(n) })}>Delete “{n}”</button>
              }} />
            {edited && <span className="hint">edited</span>}
          </div>)
      })()}
      <div className="verbs"><CommandButton id="stage.pose.mirror" text /><CommandButton id="stage.pose.reset" text label="Reset" /><CommandButton id="stage.pose.save" text /></div>
      <h4>Joint</h4>
      <div className="kv"><span>joint</span><select value={joint ?? ''} onChange={(e) => st().selectJoint(e.target.value || null)}><option value="">— click one in the viewport —</option>{JOINTS.map((j) => <option key={j} value={j}>{j}</option>)}</select></div>
      {v && <Vec label="x · y · z °" v={v} onChange={setJoint} step={5} />}
      <p className="hint">Gizmos <Help text="Orange spheres are joints (rotate), blue cubes are hands and feet (drag; elbow and shoulder follow). The figure's own transform stays on the Move / Rotate tools." /></p>
    </div>
    </>
  )
}

// ST3 (16 §3e / §7): the generation form for the blocking — the method (D78: clay reference by default, exact pose as the switch), image 1
// locked to the pass the method takes, the reference deck (D73), the prompt, the size tier and the candidates; the passes render on
// Generate when stale (or by the button), the results land below with lineage to the passes.
/** `stillsOnly` (D95, Image's From a stage): the stills without the clip fold, which belongs to Animate. */
/** D116: one step of the shot as a tree node — folded by its summary; the step's state and verb on the summary line (the verb's click
 *  does not fold it). */
function Step({ id, title, state, verb, children }: { id: string; title: string; state?: React.ReactNode; verb?: React.ReactNode; children: React.ReactNode }) {
  return (
    <details className="step" data-step={id} open>
      <summary><span className="tw" aria-hidden="true">▸</span><b>{title}</b>{state != null && <span className="state hint">{state}</span>}
        {verb != null && <span className="verb" onClick={(e) => e.preventDefault()}>{verb}</span>}</summary>
      <div className="step-body">{children}</div>
    </details>
  )
}

export function ShotTab({ stillsOnly = false }: { stillsOnly?: boolean } = {}) {
  const current = useStage((s) => s.current)
  const cam = useStage((s) => s.activeCamera())
  const sh = useStage((s) => s.shot)
  const pv = useStage((s) => s.shotPreview)
  const err = useStage((s) => s.shotPreviewError)
  const rendering = useStage((s) => s.rendering)
  const shots = useStage((s) => s.shots)
  const shotStart = useStage((s) => s.shotStart)
  const stills = shots.filter((a) => a.kind !== 'video')
  const clips = shots.filter((a) => a.kind === 'video')
  const entry = useStage((s) => s.passesEntry())
  const stale = useStage((s) => s.passesStale())
  const caps = useSession((s) => s.capabilities?.stage)
  const [w, h] = st().shotSize()                                   // derived from `shot.tier` and `current`, both subscribed above (a selector must not return a fresh tuple)
  const method = caps?.methods[sh.method]
  const room = Math.max(0, (method?.max_refs ?? 3) - sh.refs.length)
  const figs = (pv?.params?.figures ?? []) as { figure: number; name?: string | null; refs: number[]; span?: string | null; skipped: number }[]   // D93 (C8): the server's resolution
  const figSlots = ((pv?.params?.ref_list ?? []) as { image: number; asset_id?: string | null; figure?: number | null }[]).filter((x) => x.figure)
    .map((x) => ({ ...x, figure: x.figure!, name: figs.find((f) => f.figure === x.figure)?.name ?? 'a character' }))
  const figLines = figs.map((f) => `figure ${f.figure} · ${f.name ?? 'a character'} → ${f.span ? f.span.replace('reference ', '') : 'no images (the sheet only)'}${f.skipped ? ` · ${f.skipped} of its set left out` : ''}`)
  const { ref: dropRef, over } = useDropTarget((d) => onlyAssets(d) && shotRefDrop(d, room).ok,
    (d) => { d.items.filter((i) => i.kind === 'asset' && i.media !== 'video').slice(0, room).forEach((i) => st().addShotRef(i.id)) }, (d) => shotRefDrop(d, room))
  markUsed('stage.shot.generate'); markUsed('stage.shot.passes')
  if (!current) return <span className="hint">Open or make a stage in the Shot section.</span>
  const image1 = method?.image1 ?? 'clay'
  const passId = entry?.assets[image1]
  return (
    <div className="stage-panel shot-tab tree">
      <div className="head"><b>Render</b><span className="hint">{cam ? `${cam.name} · ${cam.focal_mm} mm` : 'no camera'}</span><CommandButton id="stage.camera.toShot" />
        <Help text="The shot's steps, top to bottom: the frame (a Stage shot of the scene from the passes), the clip (the pass sequence animated), the final shot (the scene split into layers, performed, assembled and finished). Each step folds by its title; its verb sits on the title line and in the foot." /></div>
      <Step id="frame" title="Frame" state={stills.length ? `${stills.length} rendered` : entry ? 'passes ready' : 'no passes'}
        verb={<CommandButton id="stage.shot.passes" text label={rendering ? 'Rendering…' : 'Render passes'} />}>
        <div className="kv tall"><span>method</span>
          <div className="method-list">
            {caps && Object.entries(caps.methods).map(([id, m]) => (
              <button key={id} className={`method${sh.method === id ? ' active' : ''}`} onClick={() => st().setShot({ method: id })} title={m.hint ?? m.label}>
                <b>{id === 'clay' ? 'Clay reference' : id === 'refcontrol' ? 'Exact pose' : m.label}</b>
                <span>{m.short} · {m.seconds != null ? `≈ ${Math.round(m.seconds)} s` : 'unmeasured'}{m.health === 'missing' ? ' · weights missing' : ''}</span>
              </button>
            ))}
            {!caps && <span className="hint">No Stage method in this build.</span>}
          </div></div>
        <div className="kv tall"><span>image 1 <Help text={`The ${image1} pass of this camera is the shot's first image: the method reads the scene from it.`} /></span>
          <div className="pass-row">
            <div className="ref-slot source locked" title={passId ? `the ${image1} pass, rendered at revision ${entry?.revision}` : 'render the passes first'}>
              {passId ? <img src={api.thumbUrl(passId, 256)} alt="" /> : <span className="empty">{image1}</span>}
              <span className="n">1</span>
            </div>
            <div className="pass-side">
              {entry ? <span className="hint">{Object.keys(entry.assets).length} passes · {entry.size.w}×{entry.size.h}{stale ? ` · from revision ${entry.revision}, the scene moved on — re-rendered on Generate` : ' · current'}</span>
                : <span className="hint">No passes yet. <Help text="Render frame renders them first; Render passes renders them alone." /></span>}
              {entry && stale && <label className="hint check"><input type="checkbox" checked={sh.use_as_is} onChange={(e) => st().setShot({ use_as_is: e.target.checked })} /> use as is</label>}
            </div>
          </div></div>
        <div className="kv tall"><span>references{method ? <span className="hint"> · {method.max_refs}</span> : null}{sh.refs.length > 0 && <CommandButton id="stage.shot.clearRefs" size={13} />}</span>
          <div>
            <div ref={dropRef} className={`ref-slots shot-refs${over ? ' over' : ''}`}>
              {sh.refs.map((r, i) => (
                <div key={r.asset_id} className="ref-slot" title={`reference image ${i + 2}`}>
                  <img src={api.thumbUrl(r.asset_id, 256)} alt="" /><span className="n">{i + 2}</span>
                  <button className="quiet x" title="Remove" onClick={() => st().removeShotRef(r.asset_id)}>✕</button>
                </div>
              ))}
              {figSlots.map((x) => (
                <div key={x.image} className="ref-slot figure-slot" title={`image ${x.image}: ${x.name}'s reference — bound to figure ${x.figure} (the Cast's set, not the deck's)`}>
                  {x.asset_id ? <img src={api.thumbUrl(x.asset_id, 256)} alt="" /> : null}<span className="n">{x.image}</span><span className="fig-badge">fig {x.figure} · {x.name}</span>
                </div>
              ))}
              {room - figSlots.length > 0 && <div className="ref-slot" title="drop a Catalogue tile here"><span className="empty">{sh.refs.length + figSlots.length + 2}</span></div>}
            </div>
            {figLines.length > 0 && <ul className="figure-lines" aria-label="the figures and their reference images">{figLines.map((t) => <li key={t}>{t}</li>)}
              {pv?.params?.bind_refs === false && <li className="muted">this method reads the figures' images by their notes — not bound in its prompt</li>}
              {/* journal 2026-10-17 18:03: exact pose (one reference slot) drew both figures as figure 1's character; clay carried each one's images */}
              {figs.length > 1 && figs.some((f) => !f.refs?.length) && <li className="warn">this method has room for {method?.max_refs ?? 1} reference image{(method?.max_refs ?? 1) === 1 ? '' : 's'}: {figs.filter((f) => !f.refs?.length).map((f) => `figure ${f.figure}`).join(', ')} only get{figs.filter((f) => !f.refs?.length).length === 1 ? 's' : ''} words — for several characters use a method with more room (Clay reference)</li>}</ul>}
            {!figLines.length && current.objects.some((o) => o.kind === 'mannequin') && <p className="hint">Figures not bound <Help text="Bind a figure to a Cast character (Inspector › character, or right-click ▸ Bind to a character): its reference images and sheet go into the frame, figure by figure, left to right." /></p>}
            {sh.method === 'refcontrol' && !sh.refs.length && <p className="disabled-why">Exact pose needs one reference image (image 2): drop a Catalogue tile on the deck.</p>}
          </div></div>
        {sh.refs.map((r, i) => <div key={r.asset_id} className="kv"><span>image {i + 2}</span><input value={r.note ?? ''} placeholder="shows … (one phrase)" onChange={(e) => st().setShot({ refs: sh.refs.map((x) => (x.asset_id === r.asset_id ? { ...x, note: e.target.value } : x)) })} /></div>)}
        <div className="kv tall"><span>prompt</span><textarea className="shot-prompt" rows={3} value={sh.prompt_text} placeholder="what the scene is — after the method's own sentence about image 1" onChange={(e) => st().setShot({ prompt_text: e.target.value })} /></div>
        <div className="kv"><span>size</span><span className="segmented"><button className={sh.tier === 'draft' ? 'active' : ''} onClick={() => st().setShot({ tier: 'draft' })}>Draft</button><button className={sh.tier === 'full' ? 'active' : ''} onClick={() => st().setShot({ tier: 'full' })}>Full</button><span className="hint"> {w}×{h}</span></span></div>
        <div className="kv"><span>count</span><span className="angle-count"><button onClick={() => st().setShot({ count: Math.max(1, sh.count - 1) })} disabled={sh.count <= 1}>−</button><span>{sh.count}</span><button onClick={() => st().setShot({ count: Math.min(4, sh.count + 1) })} disabled={sh.count >= 4}>+</button></span></div>
        {pv?.params?.prompt ? <div className="kv tall"><span>reads <Help text="The prompt as the method sends it: its own sentence about image 1, then yours." /></span><p className="hint prompt-preview">{String(pv.params.prompt)}</p></div> : null}
        {err && <p className="disabled-why">{err}</p>}
        {pv && pv.missing.length > 0 && <p className="disabled-why">Weights missing for this method: {pv.missing.map((m) => m.model_id).join(', ')} — Models › Fetch.</p>}
        <div className="kv tall"><span>results{stills.length ? <span className="hint"> · {stills.length}</span> : null}</span>
          <div>
            {!stills.length && <span className="hint">None yet. <Help text="The frames of this stage land here and in the Catalogue (lineage: the pass and the references). Click one: the clip starts from it." /></span>}
            <div className="shot-results">{stills.slice(0, 12).map((a) => <img key={a.id} className={`shot-thumb${shotStart === a.id ? ' start' : ''}`} src={api.thumbUrl(a.id, 256)} alt="" title={`${a.model_id ?? ''} · seed ${a.seed ?? ''} — click: the clip starts from this frame`} onClick={() => st().setShotStart(shotStart === a.id ? null : a.id)} />)}</div>
          </div></div>
      </Step>
      {!stillsOnly && <Step id="clip" title="Clip" state={`frames ${current.range.start}–${current.range.end}${clips.length ? ` · ${clips.length} rendered` : ''}`}
        verb={<CommandButton id="stage.clip.animate" text label="Render clip ▶" />}><ClipSection clips={clips} /></Step>}
      {!stillsOnly && <FinalSection />}{/* D111 (PS5): its own step */}
    </div>
  )
}

// ST4 (16 §8): the clip — the pass sequence over the range (depth by default, pose as the weaker second, D76) rendered by the viewport,
// the start frame picked among the shots, Animate ▶ through LTX-2.3's IC-LoRA; the stage's clips land here and in Animate.
function ClipSection({ clips }: { clips: Asset[] }) {
  const current = useStage((s) => s.current)!
  const kind = useStage((s) => s.guideKind)
  const g = useStage((s) => s.guideEntry())
  const rendering = useStage((s) => s.rendering)
  const rendered = useStage((s) => s.rendered)
  const shotStart = useStage((s) => s.shotStart)
  const method = useStage((s) => s.clipMethod)
  const caps = useSession((s) => s.capabilities?.stage)
  const clipCap = method === 'animate' ? caps?.animate : caps?.clip
  const [gw, gh] = st().guideSize()
  const n = st().guideFrames()
  const stale = !!g && (g.range.start !== current.range.start || g.frames !== n || current.revision > g.revision + 1)
  markUsed('stage.clip.guide'); markUsed('stage.clip.animate')
  return (
    <div className="clip-section">
      <div className="kv"><span>method</span><span className="segmented">
        <button className={method === 'guided' ? 'active' : ''} aria-label="clip method guided" disabled={!caps?.clip} onClick={() => st().setClipMethod('guided')} title={caps?.clip ? `${caps.clip.label}: the IC-LoRA follows the depth or pose sequence from the picked frame (ST4)` : 'not in this build (LTX-2.3 with its IC-LoRA is full-variant)'}>IC-LoRA</button>
        <button className={method === 'animate' ? 'active' : ''} aria-label="clip method animate" disabled={!caps?.animate} onClick={() => st().setClipMethod('animate')} title={caps?.animate ? `${caps.animate.label}: the picked character performs the pose sequence — one figure, up to ${caps.animate.frames_max ?? 77} frames (E19)` : 'not in this build'}>Wan Animate</button>
      </span></div>
      {!clipCap && <span className="hint">{method === 'animate' ? 'No pose-driven clip model in this build.' : 'No clip model in this build (LTX-2.3 with its IC-LoRA is full-variant).'}</span>}
      <div className="kv"><span>guide</span><span className="segmented"><button className={kind === 'depth' ? 'active' : ''} disabled={method === 'animate'} onClick={() => st().setGuideKind('depth')} title={method === 'animate' ? 'Animate performs the pose sequence' : 'the depth sequence (E11: the pose followed 4/5)'}>Depth</button><button className={kind === 'pose' ? 'active' : ''} onClick={() => st().setGuideKind('pose')} title="the pose sequence (E11: 3/5)">Pose</button></span></div>
      <div className="guide-state">
        {rendering && rendered ? `rendering ${rendered.done} / ${rendered.total || n}…` : g ? `${kind} sequence · ${g.frames} frames · ${g.size.w}×${g.size.h} · ${g.fps} fps${stale ? ' · from an earlier range or revision — render again' : ' · current'}` : `no ${kind} sequence yet · ${n} frames at ${gw}×${gh} (8n + 1 for the clip model)`}
      </div>
      <div className="verbs"><CommandButton id="stage.clip.guide" text label={rendering ? 'Rendering…' : 'Render sequence'} /></div>
      {!shotStart && <p className="disabled-why">Click one of the results above to start the clip from it.</p>}
      {clipCap && <p className="hint">{clipCap.label} · ≈ {clipCap.seconds != null ? Math.round(clipCap.seconds) : '?'} s for {method === 'animate' ? '77 frames' : '121 frames'}{clipCap.health === 'missing' ? ' · weights missing — Models › Fetch' : ''}<Help text={method === 'animate' ? 'Wan Animate (E19): one figure in the camera; the picked result is the character.' : 'LTX-2.3 with its IC-LoRA (E11): the depth or pose sequence from the picked frame.'} /></p>}
      {clips.length > 0 && <><h4>Clips · {clips.length}</h4>
        <div className="clip-results">{clips.slice(0, 9).map((a) => <span key={a.id} className="clip-thumb"><img className="shot-thumb" src={api.thumbUrl(a.id, 256)} alt="" title={`${a.frames ?? '?'} frames · ${a.model_id ?? ''}`} /><span className="n">{a.frames ?? '?'} f</span></span>)}</div></>}
    </div>
  )
}

/** The project's stages, poses and meshes, loaded when a project opens (Animate's column mounts it, D95 AN1). */
export function useStageLoad(): void {
  const project = useSession((s) => s.project)
  useEffect(() => { if (project?.open) { void st().load(); void st().loadPoses(); void st().loadMeshes(); void st().loadTemplates() } }, [project?.path]) // eslint-disable-line react-hooks/exhaustive-deps
}

/** D116: the shot's steps as one strip in the foot — the passes, the guide sequence, the clip, the final shot and (for the stage's newest final)
 *  its assembly, composition, Final level and render; the author's "rig", at hand whatever the column shows. */
function RigStrip() {
  const current = useStage((s) => s.current)
  const passesBusy = useStage((s) => s.rendering)
  const finals = useFinals((s) => s.finals)
  const comps = useFinals((s) => s.compositions)
  if (!current) return null
  const f = finals.filter((x) => x.stage_id === current.id).at(-1) ?? null
  const comp = f ? comps[f.id] ?? null : null
  const busy = f ? assembling(f.id) : false
  const renders = f ? compRendering(f.id) : false
  return (
    <div className="rig-strip" aria-label="the shot's steps" data-rig-strip>
      <CommandButton id="stage.shot.passes" text label={passesBusy ? 'Passes…' : 'Passes'} />
      <CommandButton id="stage.clip.guide" text label="Sequence" />
      <CommandButton id="stage.clip.animate" text label="Clip ▶" />
      <CommandButton id="stage.final.make" text label="Final…" />
      {f && <>
        <button className="quiet" disabled={!readyToAssemble(f) || busy} onClick={() => void useFinals.getState().assemble(f.id)} title={`${f.name}: composite the layers into the shot`}>{busy ? 'Assembling…' : 'Assemble'}</button>
        {f.assembled_at && <button className="quiet" disabled={busy} onClick={() => void useFinals.getState().compose(f.id)} title={comp ? `${f.name}: the composition written afresh (the edits are dropped)` : `${f.name}: an EffectCraft composition to finish by hand`}>{comp ? 'Composition ↻' : 'Composition'}</button>}
        {comp && <button className="quiet" onClick={() => useFinals.getState().openFinal(f.id)} title={`${f.name} at Animate's Final level`}>Open in Final</button>}
        {comp && <button className="quiet" disabled={renders} onClick={() => void useFinals.getState().render(f.id)} title={`${f.name}: the finished shot rendered on the CPU`}>{renders ? 'Rendering…' : comp.clip_id ? 'Render ↻' : 'Render'}</button>}
      </>}
      <Help text="The shot's steps in order: the passes of the scene, the frame (Render frame below), the guide sequence, the clip, the final shot split into layers, its assembly, the composition to finish by hand at the Final level, the finished render. The Performance section has each step in full." />
    </div>
  )
}

/** The foot while Animate's Performance card is From the stage (D95 AN1): New stage, else Render frame ×n with its estimate. */
export function StageFoot() {
  const current = useStage((s) => s.current)
  const rendering = useStage((s) => s.rendering)
  const pv = useStage((s) => s.shotPreview)
  const err = useStage((s) => s.shotPreviewError)
  const count = useStage((s) => s.shot.count)
  const cam = useStage((s) => s.activeCamera())
  markUsed('stage.new')
  if (!current) return <div><button className="primary" onClick={() => runCommand('stage.new')}>New stage…</button></div>
  const missing = pv?.missing ?? []                                                                            // ST3: the verb and its estimate
  const reason = !cam ? 'no camera' : rendering ? 'rendering the passes…' : err ? err : !pv ? 'preparing…' : missing.length ? `weights missing: ${missing.map((m) => m.model_id).join(', ')}` : pv.estimate.vram_fit === 'over' ? 'VRAM estimate exceeds the budget' : null
  return (
    <div>
      <RigStrip />{/* D116: the shot's steps at hand, above the primary */}
      <button className="primary" disabled={!!reason} onClick={() => runCommand('stage.shot.generate')} title="Render the passes if they are stale, then queue the frame (Ctrl+Enter)">Render frame{count > 1 ? ` ×${count}` : ''} ▶</button>
      <div className="estimate">{reason ? <span style={{ color: 'var(--fg3)' }}>{reason}</span> : <><span className={`dot ${pv?.estimate.vram_fit ?? 'ok'}`} />≈ {Math.round((pv?.estimate.seconds ?? 0) * count)} s · {String(pv?.params?.label ?? '')}</>}</div>
    </div>
  )
}

// ------------------------------------------------------------------ Strip
export function Strip() {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (useSession.getState().ui.suite !== 'stage') return
      if (document.querySelector('.ctx-menu')) return                     // D90: an open menu owns the arrows, Space and Enter
      if (inField(e)) { primaryInField(e, ['stage.shot.generate']); return }   // D90 (B1): a key typed into a field never reaches the tools (Delete deleted the object)
      handleKeyFor('stage', e)
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [])
  const view = useStage((s) => s.view)
  const guides = useStage((s) => s.guides)
  const current = useStage((s) => s.current)
  if (!current) return <div className="stage-strip-wrap"><div className="stage-strip"><AnimateLevels /></div></div>
  return (
    <div className="stage-strip-wrap">
      <div className="stage-strip">
        <AnimateLevels />{/* D95 (AN1): Animate's viewer levels */}
        <CommandRow ids={['stage.view.free', 'stage.view.camera']} active={view === 'camera' ? 'stage.view.camera' : 'stage.view.free'} labels={{ 'stage.view.free': 'free', 'stage.view.camera': 'camera' }} />
        <CommandButton id="stage.guides" active={guides} />
        <CommandButton id="stage.frameAll" />
        <span className="spacer" />
        <span className="hint">{current.name} · {current.size.w}×{current.size.h}</span>
      </div>
    </div>
  )
}

// ST4 (16 §8): the frame scrubber with the key markers, the range, play and step, Key camera / object — every verb a button (D32).
function Timeline() {
  const current = useStage((s) => s.current)!
  const frame = useStage((s) => s.frame)
  const playing = useStage((s) => s.playing)
  const selected = useStage((s) => s.selected)
  const keyed = keyedFramesOf(keyframesOf(current), current.active_camera)        // derived from `current` (subscribed): a selector must not return a fresh array
  const { start, end } = current.range
  const span = Math.max(1, end - start)
  markUsed('stage.anim.keyCamera'); markUsed('stage.anim.keyObject'); markUsed('stage.anim.removeKey'); markUsed('stage.anim.setStart'); markUsed('stage.anim.setEnd')
  return (
    <div className="stage-timeline" onPointerDown={(e) => e.stopPropagation()}>
      <CommandRow ids={['stage.anim.first', 'stage.anim.prevKey', 'stage.anim.back10', 'stage.anim.prev', 'stage.anim.play', 'stage.anim.next', 'stage.anim.fwd10', 'stage.anim.nextKey', 'stage.anim.last']} active={playing ? 'stage.anim.play' : undefined} />
      <input className="frame-field" type="number" min={0} value={frame} onChange={(e) => st().setFrame(Number(e.target.value) || 0)} title="the frame the viewport shows" />
      <div className="scrub-wrap">
        <div className="key-marks">{keyed.filter((f) => f >= start && f <= end).map((f) => <i key={f} className={`key-mark${f === frame ? ' here' : ''}`} style={{ left: `${((f - start) / span) * 100}%` }} title={`key at frame ${f}`} />)}</div>
        <input className="scrub" type="range" min={start} max={end} step={1} value={Math.min(end, Math.max(start, frame))} onChange={(e) => st().setFrame(Number(e.target.value))} />
      </div>
      <span className="range-field" title="the clip's range (frames, inclusive) at the project's fps">
        <input type="number" min={0} value={start} onChange={(e) => st().setRange(Number(e.target.value) || 0, end)} />–<input type="number" min={1} value={end} onChange={(e) => st().setRange(start, Number(e.target.value) || 1)} /> · {current.size.fps} fps
      </span>
      <CommandRow ids={['stage.anim.setStart', 'stage.anim.setEnd']} />
      <span className="sep" />
      <CommandButton id="stage.anim.keyCamera" text label="Key camera" active={keyed.includes(frame) && !!(st().keys().camera[current.active_camera ?? ''] ?? []).some((k) => k.frame === frame)} />
      <CommandButton id="stage.anim.keyObject" text label={selected ? 'Key object' : 'Key object (select one)'} />
      <CommandButton id="stage.anim.removeKey" />
    </div>
  )
}

// ------------------------------------------------------------------ Stage · the viewport
function Viewport() {
  const hostRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const engineRef = useRef<StageEngine | null>(null)
  const lastPointer = useRef<{ x: number; y: number } | null>(null)
  const active = useStageActive()
  const current = useStage((s) => s.current)
  const selected = useStage((s) => s.selected)
  const tool = useStage((s) => s.tool)
  const snap = useStage((s) => s.snap)
  const view = useStage((s) => s.view)
  const guides = useStage((s) => s.guides)
  const frameReq = useStage((s) => s.frameRequest)
  const selectedJoint = useStage((s) => s.selectedJoint)
  const poseMode = useSuiteRail().active === 'motion'                                  // ST2 → D95 (AN1): the Motion section shows the joint pickers
  const [rect, setRect] = useState<{ x: number; y: number; w: number; h: number } | null>(null)
  const { ref: dropRef, over } = useDropTarget((d) => onlyAssets(d) && d.items.some((i) => i.media !== 'video') && !!useStage.getState().current,
    (d) => { const it = d.items.find((i) => i.kind === 'asset' && i.media !== 'video'); const e = engineRef.current; const p = lastPointer.current
      if (it && e) st().addObject(it.media === 'mesh' ? 'mesh' : 'plane', null, (p ? e.place(p.x, p.y) : null) ?? e.centre(), it.id) },         // P18: a mesh lands as a prop
    (d) => { const it = d.items.find((i) => i.kind === 'asset' && i.media !== 'video'); return it ? { ok: true, label: it.media === 'mesh' ? 'Place the prop here' : 'Place as an image plane' } : { ok: false, reason: 'Only images and meshes go on the stage' } })
  // the engine: one per mounted viewport (kept alive with the suite, D69)
  useEffect(() => {
    const canvas = canvasRef.current, host = hostRef.current
    if (!canvas || !host) return
    const engine = new StageEngine(canvas, {
      onPick: (id) => st().select(id),
      onTransformed: (id, t) => st().setTransform(id, t),
      onPickCamera: (id) => st().selectCamera(id),
      onCameraMoved: (id, pos) => st().moveCamera(id, pos),                                                // D119 (SC1): the camera's body dragged
      onPosed: (id, joints) => st().setJoints(id, joints),
      onDetailError: (_id, message) => useSession.getState().toast(`The Detailed mannequin did not load — the figure stays Simple: ${message}`, 'error'),   // CA1
      onMeshThumb: (assetId, view) => void st().uploadMeshThumbnail(assetId, view),
    })
    engineRef.current = engine
    viewport.centre = () => engine.centre(); viewport.freePose = () => engine.freePose(); viewport.frame = (ids) => engine.frame(ids)
    useStage.setState({ passRenderer: (cam, w, h) => engine.renderPasses(cam, w, h), sequenceRenderer: (fr, w, h, kind, restore, on) => engine.renderSequence(fr, w, h, kind, restore, on),
      plateProjector: (fr, w, h, plate, proj, aspect, restore, on) => engine.renderProjected(fr, w, h, plate, proj, aspect, restore, on) })   // ST3 / ST4, D111
    viewport.handPreset = (id, side, preset) => engine.handPreset(id, side, preset)                                   // CA1
    if (DEV_HOOKS) Object.assign(devHook(), { screenOf: (at: string) => engine.screenOf(at as Joint), cameraScreen: (id: string) => engine.cameraScreen(id), meshes: () => ({ loaded: [...engine.meshesLoaded], failed: Object.fromEntries(engine.meshesFailed) }) })   // the smoke test aims the mouse at joints and handles; P18 asks which props loaded
    const ro = new ResizeObserver(() => { const r = host.getBoundingClientRect(); engine.resize(Math.round(r.width), Math.round(r.height)); setRect({ ...engine.frameRect() }) })
    ro.observe(host)
    engine.start()
    return () => { ro.disconnect(); engine.dispose(); engineRef.current = null; viewport.centre = undefined; viewport.freePose = undefined; viewport.frame = undefined; viewport.handPreset = undefined; useStage.setState({ passRenderer: null, sequenceRenderer: null, plateProjector: null }) }
  }, [])
  useEffect(() => { const e = engineRef.current; if (!e) return; if (active) e.start(); else e.stop() }, [active])
  const frame = useStage((s) => s.frame)
  const playing = useStage((s) => s.playing)
  useEffect(() => { const e = engineRef.current; if (e && current) { e.setAspect(current.size.w / current.size.h); e.sync(sampleDoc(current, frame)); setRect({ ...e.frameRect() }) } }, [current, frame])   // ST4: the document at the frame
  useEffect(() => {                                                                                                     // ST4: playback loops over the range at the project's fps
    if (!playing || !current) return
    const t = window.setInterval(() => { const s = st(); const cur = s.current; if (!cur) return; s.setFrame(s.frame + 1 > cur.range.end ? cur.range.start : s.frame + 1) }, 1000 / Math.max(1, current.size.fps))
    return () => window.clearInterval(t)
  }, [playing, current?.size.fps]) // eslint-disable-line react-hooks/exhaustive-deps
  const selectedCamera = useStage((s) => s.selectedCamera)
  useEffect(() => { engineRef.current?.select(selected) }, [selected])
  useEffect(() => { engineRef.current?.selectCamera(selectedCamera) }, [selectedCamera])                   // D119 (SC1)
  useEffect(() => { engineRef.current?.setTool(tool, snap) }, [tool, snap])
  useEffect(() => { const e = engineRef.current; if (!e) return; e.setView(view); if (view === 'camera' && current) e.sync(current) }, [view]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (frameReq.n) engineRef.current?.frame(frameReq.ids) }, [frameReq])
  useEffect(() => { engineRef.current?.setPoseMode(poseMode); if (!poseMode) st().selectJoint(null) }, [poseMode])
  useEffect(() => { const e = engineRef.current; if (e && selected) e.selectJoint(selected, selectedJoint as Joint | null) }, [selectedJoint]) // eslint-disable-line react-hooks/exhaustive-deps
  const down = useRef<{ x: number; y: number; t: number } | null>(null)
  const onDown = (e: ReactPointerEvent) => { if (e.button === 0) down.current = { x: e.clientX, y: e.clientY, t: Date.now() } }
  const onUp = (e: ReactPointerEvent) => {
    const d = down.current; down.current = null
    const eng = engineRef.current
    if (!d || !eng || e.button !== 0 || Math.hypot(e.clientX - d.x, e.clientY - d.y) > 4 || eng.gizmo.dragging) return
    const s = st()
    const fig = s.object(s.selected)
    if (s.tool === 'path' && fig?.kind === 'mannequin') {                             // CA1: a click on the floor adds to the figure's path
      const at = eng.place(e.clientX, e.clientY)
      if (at) s.addPathPoint(fig.id, [at[0], at[2]])
      return
    }
    const p = eng.pick(e.clientX, e.clientY)
    if (p.joint && p.id) { st().selectJoint(p.joint) }                                 // the rotate gizmo moves to the joint (FK)
    else if (p.ik && p.id) { st().selectJoint(null); eng.startIk(p.id, p.ik) }         // a translate handle on the hand / foot (IK)
    else if (p.camera) st().selectCamera(p.camera)                                      // D119 (SC1): a camera's body — the camera as the selection
    else st().select(p.id)
  }
  const onDouble = (e: React.MouseEvent) => {                                           // D119 (SC1): a double-click on a camera's body looks through it
    const eng = engineRef.current
    const p = eng ? eng.pick(e.clientX, e.clientY) : null
    if (p?.camera) { st().selectCamera(p.camera); st().setView('camera') }
  }
  const onMenu = (e: React.MouseEvent) => {
    e.preventDefault()
    const eng = engineRef.current
    const p = eng ? eng.pick(e.clientX, e.clientY) : { id: null }
    if (p.camera) { st().selectCamera(p.camera); showMenu(e, cameraMenu()); return }
    if (p.id) st().select(p.id)
    showMenu(e, viewportMenu(!!p.id))
  }
  markUsed('stage.tool.select'); markUsed('stage.tool.move'); markUsed('stage.tool.rotate'); markUsed('stage.tool.scale'); markUsed('stage.snap'); markUsed('stage.undo'); markUsed('stage.redo')
  return (
    <div ref={(el) => { (hostRef as React.MutableRefObject<HTMLDivElement | null>).current = el; dropRef(el) }} className={`stage-host${over ? ' over' : ''}`}
      onPointerDown={onDown} onPointerUp={onUp} onPointerMove={(e) => { lastPointer.current = { x: e.clientX, y: e.clientY } }} onContextMenu={onMenu} onDoubleClick={onDouble}>
      <canvas ref={canvasRef} className="stage-canvas" />
      {current && <div className="gizmo-bar" onPointerDown={(e) => e.stopPropagation()} onPointerUp={(e) => e.stopPropagation()}>
        <CommandRow ids={['stage.tool.select', 'stage.tool.move', 'stage.tool.rotate', 'stage.tool.scale', 'stage.tool.path', 'gap', 'stage.snap', 'gap', 'stage.undo', 'stage.redo']} active={`stage.tool.${tool}`} />
        {snap && <span className="hint">snap</span>}
      </div>}
      {current && view === 'camera' && rect && guides && <div className="frame-guides" style={{ left: rect.x, top: rect.y, width: rect.w, height: rect.h }}><i className="thirds" /><i className="centre" /></div>}
      {current && view === 'camera' && <div className="view-tag">camera view · {st().activeCamera()?.name} · {st().activeCamera()?.focal_mm} mm</div>}
      {current && !current.objects.length && <div className="stage-empty"><div>Empty stage — add a set and a figure from the Scene section, or drop a Catalogue image.<div className="quick-cards"><CommandButton id="stage.add.set.room" text /><CommandButton id="stage.add.mannequin.adult" text /></div></div></div>}
    </div>
  )
}

export function Stage() {
  const project = useSession((s) => s.project)
  const current = useStage((s) => s.current)
  if (!project?.open) return <div className="placeholder"><div><h2>Stage</h2>open or create a project to begin</div></div>
  if (!current) return <div className="placeholder"><div><h2>Stage</h2>a blocking in 3D: a set, figures, props and cameras at the project size<div className="quick-cards"><CommandButton id="stage.new" text label="New stage…" /></div></div></div>
  return <div className="stage-col"><Viewport /><Timeline /></div>   // D95 (AN1): the transport under the viewer, as at the Performance level
}

// ------------------------------------------------------------------ Inspector
function Vec({ label, v, onChange, step = 0.05 }: { label: string; v: number[]; onChange: (v: number[]) => void; step?: number }) {
  return (
    <div className="kv"><span>{label}</span><span className="vec">{v.map((x, i) => <input key={i} type="number" step={step} value={num(x)} onChange={(e) => { const n = [...v]; n[i] = Number(e.target.value) || 0; onChange(n) }} />)}</span></div>
  )
}

/** D95 (AN1): the stage's selection — an object, else the stage and its active camera — in Animate's Selection section. */

