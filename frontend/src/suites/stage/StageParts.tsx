// P13 / ST1 (D81): the Stage suite's parts (16; StageSuite.ts registers them) — Panel (Library · Outliner · Cameras), Strip (view, guides, frame), the viewport Stage with
// its floating gizmo bar and the framing rectangle, the Inspector (object · camera · stage). Mouse-first (D32): every verb is a
// button or a menu entry; keys are accelerators. Keep-alive (D69): the engine pauses while the suite is hidden and keeps its view. D93 (C8):
// a figure is bound to a Cast character (the Inspector's tiles, "Bind to a character ▸"); the Outliner shows who; the Render tab's deck shows
// which images are a figure's (the preview's `ref_list`) and how each figure is said in the prompt.
// D121 (proto01_animate 26 §5.2): the Clay level is a mode of its own — its column (Shot · Scene · Motion · Camera), its foot (Render passes ▶),
// the viewport with the pose pill; the stage's frame form (`ShotTab`) is Image › From a stage's, the stage clip (`StageClipCard`) Performance's.
import { Help } from '../../frame/Help'
import { Aperture, Bookmark, Box, Camera, Eye, EyeOff, Frame, LayoutTemplate, Lock, LockOpen, MapPin, PersonStanding, User, UserRound, Video } from 'lucide-react'
import { PresetPanel } from '../../frame/PresetPanel'
import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { CommandButton, CommandRow, MenuButton } from '../../frame/CommandButton'
import { useMakeFor } from '../../store/origin'
import { useStory } from '../story/storyStore'
import { handleKeysAt, markUsed, runCommand, sep, type MenuItem } from '../../frame/commands'
import { inField, primaryInField } from '../../frame/fieldKeys'
import { showMenu } from '../../frame/ContextMenu'
import { navigate } from '../../frame/router'
import { onlyAssets, useDropTarget } from '../../frame/drag'
import { shotRefDrop } from '../../frame/dropRules'
import { api } from '../../api/client'
import { DEV_HOOKS } from '../../devHooks'
import { BoundTag, FigureCharacter, LibraryProps, MeshProp } from './FigureBinding'
import { AmbientControl, LightControls } from './LightControls'
import { MotionLibrary } from './motion/MotionLibrary'
import { HAND_PRESETS, type HandPreset } from './detailed'
import { useStageActive } from '../../frame/stageKeep'
import { askConfirm, askText, useSession } from '../../store/session'
import { ShotHead } from './ShotStepper'
import { AnimColumn, Sec } from '../animate/column'
import type { StageCamera, StageDoc, StageObject } from '../../api/types'
import { keyedFrames as keyedFramesOf, keyframesOf, sampleCamera, sampleDoc } from './anim'
import { blockMenu, dragBlock, saveRangeAsAnimation } from './blockEdit'
import { blocksReady, useBlocks, type MotionBlock } from './blocks'
import { awayStretches, lineSpans } from './tracks'
import { Timeline as TimelineView, TransportBar, type TLRow } from '../animate/Timeline'
import { keyRuns, stageSpan } from '../animate/timelineMath'
import { JOINTS, MANNEQUIN_PRESETS, POSE_NAMES, PROP_PRESETS, SET_PRESETS, type Joint } from './builders'
import { ThingsSheet } from './ThingsSheet'
import { useThings } from './thingsStore'
import { StageEngine } from './engine'
import { viewport, viewportMenu, cameraMenu } from './stageCommands'
import { descendsFrom, HAND_LABEL } from './held'
import { meshLabel, propMeshes } from './meshes'
import { castPoses, effectiveJoints, st, TEMPLATE_KINDS, useStage, type ShotState, imageSetBudget } from './stageStore'
import { ENDS, type End } from './motion/contact'
import { contactChoices, SELF, type Contact, type Contacts } from './motion/contacts'
import './stage.css'
import { registerKeyHost } from '../../frame/keyHosts'

const FOCALS = [24, 35, 50, 85]
const num = (v: number) => +v.toFixed(2)

/** Dev hook (`window.__loom2Stage`, DEV_HOOKS only): the smoke test and scripts/st_acceptance.py drive the suite through the store — present as
 *  soon as the suite's code loads; the viewport adds `screenOf` when it mounts. */
function devHook(): Record<string, unknown> {
  const w = window as unknown as { __loom2Stage?: Record<string, unknown> }
  w.__loom2Stage ??= { open: (id: string) => st().open(id), setShot: (p: Partial<ShotState>) => st().setShot(p), renderPasses: () => st().renderPasses(),
    generateShot: () => st().generateShot(), state: () => ({ current: st().current, shot: st().shot, passes: st().passesEntry(), guide: st().guideEntry(), frame: st().frame, selected: st().selected }), screenOf: () => null,
    // ST4: the clip path
    setFrame: (f: number) => st().setFrame(f), keyCamera: () => st().keyCamera(),
    sampleAt: async (f: number) => { const d = st().current; if (!d) return null; await blocksReady(d); return sampleDoc(d, f) },   /* U5: the document at a frame, its clip blocks evaluated */
    setRange: (a: number, b: number) => st().setRange(a, b), setGuideKind: (k: 'depth' | 'pose') => st().setGuideKind(k),
    renderGuide: () => st().renderGuide(), setShotStart: (id: string | null) => st().setShotStart(id), animateShot: () => st().animateShot(),
    updateCamera: (id: string, patch: Partial<StageCamera>) => st().updateCamera(id, patch), setTransform: (id: string, t: { pos: number[]; rot: number[]; scale: number[] }) => st().setTransform(id, t),
    frameAll: () => st().frameView(null),
    bindFigure: (id: string, pid: string | null, v?: string | null) => st().bindFigure(id, pid, v ?? null), select: (id: string | null) => st().select(id),   // D93 (C8)
    selectCamera: (id: string | null) => st().selectCamera(id) }   // D119 (SC1)
  return w.__loom2Stage
}
if (DEV_HOOKS) devHook()

// ------------------------------------------------------------------ Panel
/** D95 (AN1): what can be put on the stage — Animate's Scene section (with the Outliner). D119 (SC2): the preset groups (figures, sets,
 *  stand-ins) and the author's templates sit behind a + each, as Image's fields; Cast props and meshes keep their picture cards. */
/** One Scene (the author, 2026-10-22: "merge Scene and Outliner — they are essentially the same"): every kind of thing is a group —
 *  its words, the count, its + (the SC2 panel of presets) or its add button, then the rows of what is on the stage of that kind; the
 *  stage's own row first, the cameras last with Add camera, the templates at the end. A row opens its editor under it (UX9 U1); a camera
 *  row selects the camera as an object and makes it the active one. */
export function SceneTab() {
  const current = useStage((s) => s.current)
  const selected = useStage((s) => s.selected)
  const selectedCamera = useStage((s) => s.selectedCamera)
  const stageSelected = useStage((s) => s.stageSelected)
  const saving = useStage((s) => s.saving)
  const meshes = useStage((s) => s.meshes)
  const templates = useStage((s) => s.templates)
  const profiles = useStory((s) => s.profiles)
  if (!current) return <span className="hint">Open or make a stage in the Shot section.</span>
  // CW3 (02 §9): Cast's characters first — a click adds the character's figure (its body and shell follow Cast), then the presets
  const castFigures = profiles.filter((p) => p.cls === 'character').map((p) => { const v = p.versions.find((x) => x.id === p.current)
    return { id: `char:${p.id}`, label: p.name, icon: <UserRound size={18} />, img: v?.hero_asset_id ? api.thumbUrl(v.hero_asset_id, 256) : null,
      hint: current.objects.some((o) => o.kind === 'mannequin' && o.profile_id === p.id) ? 'on the stage — a click selects it' : `${p.name}'s figure, bound: its body${v?.shell_asset_id ? ' and shell' : ''} follow Cast` } })
  const figures = [...castFigures, ...Object.entries(MANNEQUIN_PRESETS).map(([p, m]) => ({ id: p, label: m.label, icon: <User size={18} />, hint: 'a mannequin, free' }))]
  // CW7 (02 §9): Cast's places with a set first — a click adds the place's set, bound (it follows Cast), then the presets
  const castSets = profiles.filter((p) => p.cls === 'place').flatMap((p) => { const v = p.versions.find((x) => x.id === p.current); const ps = v?.place_set
    if (!ps) return []
    const pic = ps.sources[0]?.asset_id ?? v?.hero_asset_id
    return [{ id: `place:${p.id}`, label: p.name, icon: <MapPin size={18} />, img: pic ? api.thumbUrl(pic, 256) : null,
      hint: current.objects.some((o) => o.kind === 'set' && o.profile_id === p.id) ? 'on the stage — a click selects it' : `${p.name}'s set (a ${ps.kind}), bound: it follows Cast` }] })
  const sets = [...castSets, ...SET_PRESETS.map((p) => ({ id: p, label: p, icon: <Box size={18} />, hint: 'architecture only (D108)' }))]
  const standins = PROP_PRESETS.map((p) => ({ id: p, label: p, icon: <Box size={18} />, hint: 'a grey stand-in shape (D109)' }))
  const names = new Map(current.objects.filter((o) => o.kind === 'mesh' && o.asset_id).reverse().map((o) => [o.asset_id!, o.name]))   // a thing keeps its name on its stage (the first object that shows it)
  const meshItems = propMeshes(meshes).slice(0, 48).map((m) => { const l = meshLabel(m, profiles, names); return { id: m.id, label: l.label, icon: <Box size={18} />, img: api.thumbUrl(m.id, 256), hint: l.hint } })   // proto01_UIcast CF9: named by source
  const tmpl = templates.map((t) => ({ id: t.name, label: t.name, icon: <LayoutTemplate size={18} />, hint: `${t.objects.length} object${t.objects.length === 1 ? '' : 's'}`, img: t.thumb_asset_id ? api.thumbUrl(t.thumb_asset_id, 256) : null }))
  const holds = current.objects.filter((o) => TEMPLATE_KINDS.has(o.kind)).length
  const centre = () => viewport.centre?.() ?? [0, 0, 0]
  const renameCam = (cam: StageCamera) => void askText({ title: 'Rename camera', initial: cam.name }).then((n) => { if (n?.trim()) st().updateCamera(cam.id, { name: n.trim() }) })
  const groups: { key: string; label: string; of: (o: StageObject) => boolean; add: React.ReactNode; help?: string }[] = [
    { key: 'figures', label: 'Figures', of: (o) => o.kind === 'mannequin',
      add: <PresetPanel label="figure presets" items={figures} showText onPick={(id) => (id.startsWith('char:') ? st().placeCharacter(id.slice(5), centre()) : runCommand(`stage.add.mannequin.${id}`))}
        title="A figure at the viewport's centre: a Cast character's (bound, it follows Cast) or a mannequin to pose" /> },
    { key: 'sets', label: 'Sets', of: (o) => o.kind === 'set',
      add: <><PresetPanel label="set presets" items={sets} showText onPick={(id) => (id.startsWith('place:') ? void st().placePlace(id.slice(6)) : runCommand(`stage.add.set.${id}`))}
        title="A set: a Cast place's (bound, it follows Cast) or architecture only — room, street, deck, empty (D108)" />
        <CommandButton id="stage.add.set.image" text label="From an image…" /></> },                                       /* SC3 (D120) */
    { key: 'props', label: 'Props', of: (o) => o.kind === 'mesh' && !!o.profile_id, add: <LibraryProps centre={centre} /> },      /* D110 (PS3): Story · Props, each its 3D model bound to the prop */
    { key: 'standins', label: 'Stand-ins', of: (o) => o.kind === 'prop', help: 'Grey shapes for blocking (D109).',
      add: <PresetPanel label="stand-in presets" items={standins} showText onPick={(id) => runCommand(`stage.add.prop.${id}`)} title="A grey stand-in shape at the viewport's centre" /> },
    { key: 'meshes', label: 'Meshes', of: (o) => o.kind === 'mesh' && !o.profile_id, help: `3D models not bound to a Cast prop, named by where they came from: a picture's "Make a 3D prop…", a picture set's thing, an imported GLB. A mesh's editor makes it a Cast prop.`,
      add: <PresetPanel label="mesh models" items={meshItems} showText onPick={(id) => st().addObject('mesh', null, centre(), id)} empty="None yet — a picture's Make a 3D prop… lands here." title="A 3D model from the Bin at the viewport's centre" /> },
    { key: 'lights', label: 'Lights', of: (o) => o.kind === 'light', add: <CommandButton id="stage.add.light" text /> },           /* D110 (PS4) */
    { key: 'planes', label: 'Image planes', of: (o) => o.kind === 'plane', help: "A picture from the Bin standing in the scene, facing the camera. Also from the Bin: drag an image onto the viewport (it lands where the pointer is), or double-click it there (the viewport's centre).",
      add: <CommandButton id="stage.add.plane" text label="Add image plane…" /> },
  ]
  return (
    <div className="stage-panel outliner scene" aria-label="the scene">
      <div className="head"><span className="hint">{current.objects.length} object{current.objects.length === 1 ? '' : 's'} · {current.cameras.length} camera{current.cameras.length === 1 ? '' : 's'}</span>
        <Help text="Everything on the stage, one row each under its kind — the stage, the figures, the sets, the props, the lights, the cameras. Each kind's + adds one (its presets as tiles); click a row to edit the thing under it, again to close. A camera's row selects its body in the viewport and makes it the active camera; double-click looks through it." /></div>
      <div className={`outl-row${stageSelected ? ' active' : ''}`} data-row="stage" onClick={() => (stageSelected ? st().select(null) : st().selectStage())}
        onDoubleClick={() => st().frameView(null)}>
        <Frame size={13} /><span className="name">{current.name}</span><span className="meta">{current.size.w}×{current.size.h} @ {current.size.fps}{saving ? ' · saving…' : ''}</span>
        {stageSelected && <StageEditor />}
      </div>
      {groups.map((g) => {
        const rows = current.objects.filter(g.of)
        return (
          <div key={g.key} className="outl-group" data-group-rows={g.key}>
            <div className="lib-row" data-group={g.key}><span className="lib-label">{g.label}{rows.length ? <span className="meta"> · {rows.length}</span> : null}{g.help && <Help text={g.help} />}</span>{g.add}</div>
            {rows.map((o) => <ObjectRow key={o.id} o={o} selected={selected === o.id} />)}
          </div>
        )
      })}
      <div className="outl-group" data-group-rows="cameras">
        <div className="lib-row" data-group="cameras"><span className="lib-label">Cameras{current.cameras.length ? <span className="meta"> · {current.cameras.length}</span> : null}</span><CommandButton id="stage.camera.add" text /></div>
        {current.cameras.map((cam) => (
          <div key={cam.id} className={`outl-row${selectedCamera === cam.id ? ' active' : ''}${current.active_camera === cam.id ? ' cam-active' : ''}`} data-row="camera"
            onClick={() => st().selectCamera(selectedCamera === cam.id ? null : cam.id)} onDoubleClick={() => { st().selectCamera(cam.id); st().setView('camera') }}
            onContextMenu={(e) => { e.preventDefault(); st().selectCamera(cam.id); showMenu(e, cameraMenu()) }}>
            <Camera size={13} /><span className="kind">camera</span>
            <span className="name" onDoubleClick={(e) => { e.stopPropagation(); renameCam(cam) }}>{cam.name}</span>
            {current.active_camera === cam.id && <span className="meta" title="The active camera: the one the shot renders through">★</span>}
            <span className="meta">{cam.focal_mm} mm</span>
            {selectedCamera === cam.id && <CameraEditor c={cam} />}
          </div>
        ))}
      </div>
      <div className="lib-row" data-group="templates"><span className="lib-label">Templates <Help text="An arrangement of this level — the set with its props, meshes, planes and lights, not the figures or the cameras — saved under a name from the stage as it is; a click adds it to this stage." /></span>
        <PresetPanel label="stage templates" items={tmpl} showText onPick={(id) => st().applyTemplate(id)} empty="No templates yet — arrange a set with its props and lights, then save it here."
          title="Your templates: an arrangement saved under a name; a click adds it to this stage" saveLabel="Save this arrangement as a template…" canSave={holds > 0} saveWhy="the stage has no set, prop, plane or light to save yet"
          onSave={(name) => st().saveTemplate(name || `Template ${templates.length + 1}`)}
          verbs={(f) => (f ? <button type="button" className="quiet danger" onClick={() => void askConfirm({ title: `Delete the template "${f}"?`, okLabel: 'Delete', danger: true }).then((ok) => { if (ok) void st().deleteTemplate(f) })}>Delete</button>
            : <span className="hint">Click a template: it is added to the stage; it can be deleted here.</span>)} /></div>
    </div>
  )
}
export const OutlinerTab = SceneTab                                   // the name the tests and the old Stage suite know

/** An object's row: the swatch, the kind, the name (double-click renames), who it is bound to, hide and lock, its editor when selected. */
function ObjectRow({ o, selected }: { o: StageObject; selected: boolean }) {
  const rename = () => void askText({ title: 'Rename', initial: o.name, placeholder: 'name' }).then((n) => { if (n?.trim()) st().updateObject(o.id, { name: n.trim() }) })
  return (
    <div className={`outl-row${selected ? ' active' : ''}${o.visible ? '' : ' hidden'}`} data-row="object" data-kind={o.kind} data-id={o.id} onClick={() => st().select(selected ? null : o.id)}
      onDoubleClick={() => st().frameView([o.id])} onContextMenu={(e) => { e.preventDefault(); st().select(o.id); showMenu(e, viewportMenu(true)) }}>
      <span className="swatch" style={{ background: `hsl(${(o.colour_id * 137) % 360} 55% 50%)` }} />
      <span className="kind">{o.kind}</span>
      <span className="name" onDoubleClick={(e) => { e.stopPropagation(); rename() }}>{o.name}</span>
      {(o.kind === 'mannequin' || o.kind === 'mesh' || o.kind === 'set') && o.profile_id && <BoundTag o={o} />}
      <button className="quiet" title={o.visible ? 'Hide' : 'Show'} onClick={(e) => { e.stopPropagation(); st().updateObject(o.id, { visible: !o.visible }) }}>{o.visible ? <Eye size={13} /> : <EyeOff size={13} />}</button>
      <button className="quiet" title={o.locked ? 'Unlock' : 'Lock'} onClick={(e) => { e.stopPropagation(); st().updateObject(o.id, { locked: !o.locked }) }}>{o.locked ? <Lock size={13} /> : <LockOpen size={13} />}</button>
      {selected && <ObjectEditor o={o} />}
    </div>
  )
}

// ------------------------------------------------------------------ D121: the Clay level's column and foot
const CLAY_SECTIONS = ['shot', 'scene', 'motion', 'camera'] as const

/** D121 (26 §5.2): the Clay level's column — the shot (its For chip, the stages), what stands on the stage, its motion, its camera. */
export function ClayColumn({ tab }: { tab: string }) {
  const project = useSession((s) => s.project)
  useStageLoad()
  if (!project?.open) return <span className="hint">Open or create a project to begin.</span>
  return (
    <AnimColumn suite="stage" sections={CLAY_SECTIONS} tab={tab}>
      <ThingsSheet />{/* D123 (SC3c-2): over everything while it is open */}
      <Sec id="shot" title="Shot"><ShotHead /></Sec>
      <Sec id="scene" title="Scene"><SceneTab /></Sec>
      <Sec id="motion" title="Motion"><PosesTab /></Sec>
      <Sec id="camera" title="Camera"><CamerasTab /></Sec>
    </AnimColumn>
  )
}

/** D121: the Clay level's foot — Render passes ▶ (Ctrl+Enter) for the active camera, with their state at a glance (D95 UX0 #16's row);
 *  New stage… while none is open. The frame and the clip are made from these passes at the other levels (Image · From a stage, Performance). */
export function ClayFoot() {
  const current = useStage((s) => s.current)
  const cam = useStage((s) => s.activeCamera())
  const entry = useStage((s) => s.passesEntry())
  const stale = useStage((s) => s.passesStale())
  const rendering = useStage((s) => s.rendering)
  markUsed('stage.new'); markUsed('stage.shot.passes')
  if (!current) return <div><button className="primary" onClick={() => runCommand('stage.new')}>New stage…</button></div>
  const reason = !cam ? 'no camera' : rendering ? 'rendering…' : null
  return (
    <div>
      <button className="primary" disabled={!!reason} onClick={() => runCommand('stage.shot.passes')} title="The active camera's passes — clay, depth, normals, pose, masks — rendered as the stage's assets (Ctrl+Enter)">
        {rendering ? 'Rendering…' : entry && !stale ? 'Render the passes again ▶' : 'Render passes ▶'}</button>
      <div className="estimate" data-passes-state>{reason ?? (entry ? `${cam!.name} · ${Object.keys(entry.assets).length} passes at ${entry.size.w}×${entry.size.h} · ${stale ? `revision ${entry.revision}, the scene moved on` : 'current'}` : `No passes yet for ${cam!.name}`)}</div>
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

/** SC3 (D120): an image set's own fields — the lens MoGe read from the picture (E30: it wobbles, so it is shown), the picture's camera, and
 *  whether the active camera is still within the budget E30 measured. */
function ImageSetFields({ o }: { o: StageObject }) {
  const current = useStage((s) => s.current)
  const pending = useStage((s) => s.pendingSet)
  const [lens, setLens] = useState(o.lens_deg != null ? String(o.lens_deg) : '')     // keyed by the lens (ObjectEditor): a rebuild resets it
  if (!current) return null
  const cam = current.cameras.find((c) => c.id === o.plate_camera_id)
  const b = imageSetBudget(current, o)
  const v = Number(lens)
  const ok = lens.trim() !== '' && Number.isFinite(v) && v >= 20 && v <= 150
  return (
    <>
      <div className="kv"><span>lens</span><span className="lens-field">
        <input type="number" min={20} max={150} step={0.5} value={lens} aria-label="the picture's lens" onChange={(e) => setLens(e.target.value)} />° wide · {cam?.name ?? 'no picture camera'}
        <Help text="The horizontal field of view the relief is built with: MoGe reads it from the picture, and the reading wobbles by a few degrees (E30: 75° from a PNG, 69° from its JPEG). When you know the lens, type it and Rebuild — seconds; the set and its camera take the new relief, the old one stays in the Bin." /></span></div>
      <div className="kv"><span>level</span><span data-level={o.level ? 'laid' : 'as-it-came'}>{o.level ? `laid level · the camera ${Math.abs(o.level.pitch_deg) < 0.05 ? 'level' : `${Math.abs(o.level.pitch_deg).toFixed(1)}° ${o.level.pitch_deg < 0 ? 'down' : 'up'}`}${Math.abs(o.level.roll_deg ?? 0) >= 0.1 ? `, ${Math.abs(o.level.roll_deg).toFixed(1)}° askew` : ''}` : 'as it came'}
        <Help text="SC3d / SC3f: the floor fitted to the picture's lowest rows (the walls and the things standing there left out) tells how the photograph's camera was held — tilted up or down, and askew. The set is turned so that floor is the stage floor, where the figures stand, and the picture's camera is tilted and rolled to match, so the picture still lines up through it. The things made on it follow when the set is rebuilt (unless you moved them). 'As it came' when the picture shows too little floor, or a slope steeper than 25°." /></span></div>
      <div className="kv"><span>budget</span><span className={b.within ? 'ok' : 'warn'} data-budget={b.within ? 'within' : 'beyond'}>{b.text} <Help text="E30 (D120): a relief holds for small moves. Within ±0.25 m and ±5° of the picture's camera, or an orbit of ±10° about the picture's depth, nothing tears inside the picture and its edge stays under a tenth of the frame. Beyond, the edge comes into the frame (the plate shows it) and what was hidden behind things opens up." /></span></div>
      <div className="verbs">
        <button type="button" disabled={!ok || v === o.lens_deg || !!pending} onClick={() => void st().rebuildImageSet(o.id, Math.round(v * 2) / 2)} title="Rebuild the relief with this lens (a job of seconds)">{pending ? 'Rebuilding…' : 'Rebuild with this lens'}</button>
        <button type="button" disabled={!cam} onClick={() => { if (cam) { st().selectCamera(cam.id); st().setView('camera') } }}>Look through the picture's camera</button>
      </div>
      <SetThings o={o} />
    </>
  )
}

/** D123 (SC3c): the things the author picked on the picture — each a row (renamed, removed), *Things in the picture…* to pick more, and
 *  *Make the things ▶*: the plate cleaned under them, the relief rebuilt from it, each a Pixal3D model standing where it stood. */
function SetThings({ o }: { o: StageObject }) {
  const making = useThings((s) => s.making)
  const mesh = useSession((s) => s.capabilities?.mesh?.model_id)
  const things = o.things ?? []
  const todo = things.filter((t) => !t.mesh_asset_id).length
  const why = !mesh ? "the 3D models need Pixal3D, which this variant does not carry" : !todo ? (things.length ? 'every thing is made' : 'pick a thing first') : making.length ? 'making…' : ''
  return (
    <div className="set-things" aria-label="the set's things">
      <div className="kv"><span>things</span><span>{things.length ? `${things.length} · ${things.length - todo} made` : 'none picked'}
        <Help text="The things standing in the place (D123): pick each on the picture, then Make the things — the plate is cleaned under them (a Fill), the relief rebuilt from the clean plate at the set's lens, and each becomes a 3D model (Pixal3D, ≈ 5 min a thing) standing where it stood. Nothing is cut that you did not pick." /></span></div>
      {things.map((t) => (
        <div key={t.id} className="thing-row" data-thing={t.id}>
          <span className="name">{t.name}</span>
          <span className="hint">{t.object_id ? 'made' : 'to make'}</span>
          <span className="spacer" />
          <button type="button" className="quiet" title="Rename" aria-label={`Rename ${t.name}`} onClick={() => void useThings.getState().rename(o.id, t.id)}>✎</button>
          <button type="button" className="quiet" title="Remove from the list (its prop, if made, stays)" aria-label={`Remove ${t.name}`} onClick={() => void useThings.getState().remove(o.id, t.id)}>✕</button>
        </div>
      ))}
      <div className="verbs">
        <button type="button" onClick={() => void useThings.getState().open(o.id)}>Things in the picture…</button>
        <button type="button" className="primary" disabled={!!why} title={why || `≈ ${todo * 5 + 1} min: the clean plate, then a model of each`} onClick={() => void useThings.getState().make(o.id)}>
          {making.length ? 'Making…' : `Make the things ▶`}</button>
      </div>
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
      {o.parent_joint && <div className="kv held" data-held><span>held</span><span>in {current.objects.find((x) => x.id === o.parent)?.name ?? 'a figure'}'s {HAND_LABEL[o.parent_joint]} <Help text="It moves with the hand; its position and rotation below are its place on the hand (the wrist)." /> <CommandButton id="stage.object.letGo" text /></span></div>}
      <Vec label="position" v={t.pos} onChange={(pos) => st().setTransform(o.id, { ...t, pos })} />
      <Vec label="rotation" v={t.rot} onChange={(rot) => st().setTransform(o.id, { ...t, rot })} step={1} />
      <Vec label="scale" v={t.scale} onChange={(scale) => st().setTransform(o.id, { ...t, scale })} step={0.05} />
      {o.kind === 'mannequin' && <FigureCharacter o={o} />}
      {o.kind === 'mesh' && <MeshProp o={o} />}
      {o.kind === 'light' && <LightControls o={o} />}
      {o.kind === 'set' && o.preset === 'image' && <ImageSetFields key={`${o.id}:${o.lens_deg}`} o={o} />}
      {o.kind === 'mannequin' && <div className="kv"><span>pose</span><span><select value={o.pose?.preset ?? 'stand'} onChange={(e) => st().applyPose(o.id, e.target.value)}>{POSE_NAMES.map((p) => <option key={p} value={p}>{p}</option>)}</select> <span className="hint">(Pose, over the viewport, poses the joints)</span></span></div>}
      {o.kind === 'plane' && <div className="kv"><span>faces camera</span><input type="checkbox" checked={o.billboard} onChange={(e) => st().updateObject(o.id, { billboard: e.target.checked })} /></div>}
      {!o.parent_joint && <div className="kv"><span>parent <Help text="It moves with its parent and stays where it stands when you pick one; its transform below is then its place on the parent." /></span><select value={o.parent ?? ''} onChange={(e) => st().setParent(o.id, e.target.value || null)}><option value="">— none —</option>{current.objects.filter((x) => x.id !== o.id && !descendsFrom(current.objects, x.id, o.id)).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></div>}
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
        <CameraShotVerb />
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
  const guides = useStage((s) => s.guides)
  const cam = useStage((s) => s.activeCamera())
  if (!current) return <span className="hint">Open or make a stage in the Shot section.</span>
  markUsed('stage.camera.add')
  return (
    <div className="stage-panel">
      <div className="head"><b>Cameras</b><span className="hint">{current.cameras.length}</span><CommandButton id="stage.camera.add" /></div>
      {cam && <>
        <div className="kv"><span>active</span><span>★ {cam.name}</span></div>
        <div className="kv"><span>lens</span><span className="focals">{FOCALS.map((f) => <button key={f} type="button" className={cam.focal_mm === f ? 'active' : ''} onClick={() => st().updateCamera(cam.id, { focal_mm: f })} title={`${f} mm on ${cam.name}`}>{f}</button>)} mm</span></div>
        <div className="verbs">
          <CommandButton id="stage.camera.setFromView" text label="Set from view" />
          <CommandButton id="stage.anim.keyCamera" text label="Key camera" />
          <CommandButton id="stage.guides" text label="Guides" active={guides} />
        </div>
        <div className="verbs"><CameraShotVerb /></div>
        <Help text="The shot renders through the active camera (★). The pill over the viewport looks through it and picks another; drag its body in the free view to move it, or type where it stands under its row in Scene; Set from view puts it where the free view is. D121 (AW4)." />
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
      <div className="kv"><span>figure</span>
        <span className="segmented" role="group" aria-label="figure">
          {([['female', '♀'], ['male', '♂']] as const).map(([k, label]) => (
            <button key={k} type="button" className={detail === k ? 'active' : ''} aria-pressed={detail === k} title={`the starter set's skinned mannequin, ${k} (fingers, feet, a spine of three) — it follows this figure's joints${o.profile_id ? '; a bound character\'s is set in Cast' : ''}`}
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
  const posing = useStage((s) => s.posing)
  const userPoses = useStage((s) => s.userPoses)
  const frame = useStage((s) => s.frame)
  const profiles = useStory((s) => s.profiles)
  const shown = useMemo(() => (o && current ? sampleDoc(current, frame).objects.find((x) => x.id === o.id) ?? o : null), [current, frame, o])   // AP1b: the pins at the playhead
  if (!current) return <span className="hint">Open or make a stage in the Shot section.</span>
  markUsed('stage.pose.mirror'); markUsed('stage.pose.reset'); markUsed('stage.pose.save'); markUsed('stage.pose.unpin'); markUsed('stage.pose.saveForCharacter')
  if (!o || o.kind !== 'mannequin') return <><MotionLibrary /><div className="stage-panel"><div className="head"><b>Poses</b></div><span className="hint">No figure selected. <Help text="Select a figure, then Pose (over the viewport, or its right-click): click a joint for the rotate gizmo, or drag a hand / foot handle." /></span></div></>
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
        // AP1b (D141): a bound figure's character's own poses too; a starter pose it has its own version of takes that
        const own = castPoses(o), who = profiles.find((p) => p.id === o.profile_id)?.name ?? 'the character'
        const built = POSE_NAMES.map((p) => ({ id: `preset:${p}`, label: p, icon: <PersonStanding size={18} />, hint: own[p] ? `built in · ${who}'s own version` : 'built in' }))
        const mine = Object.keys(own).filter((n) => !POSE_NAMES.includes(n)).map((n) => ({ id: `own:${n}`, label: n, icon: <UserRound size={18} />, hint: `${who}'s own · fitted to the body` }))
        const saved = Object.entries(userPoses).map(([name, def]) => ({ id: `saved:${name}`, label: name, icon: <Bookmark size={18} />, hint: `saved in this project · from ${def.preset ?? 'stand'}` }))
        const items = [...built, ...mine, ...saved]
        const cur = o.pose?.preset && !edited ? `preset:${o.pose.preset}` : null
        return (
          <div className="lib-row" data-group="poses"><span className="lib-label">Poses</span>
            <PresetPanel label="pose presets" items={items} showText selected={cur} chosen={items.filter((i) => i.id === cur)}
              title="The poses: the built-in ones and the ones saved in this project; a click poses the figure" saveLabel="Save this pose…"
              onSave={(name) => void st().savePose(name || `Pose ${saved.length + 1}`, o.id)}
              onPick={(id) => { const k = id.slice(0, id.indexOf(':')), n = id.slice(id.indexOf(':') + 1); if (k === 'preset') st().applyPose(o.id, n); else if (k === 'own') st().applyCharacterPose(o.id, n); else { const d = userPoses[n]; if (d) st().applyPose(o.id, d.preset ?? 'stand', d.joints) } }}
              verbs={(f) => {
                const n0 = f?.slice(f.indexOf(':') + 1) ?? ''
                if ((f?.startsWith('own:') || (f?.startsWith('preset:') && own[n0])) && o.profile_id) {
                  const p = profiles.find((x) => x.id === o.profile_id)
                  return <button type="button" className="quiet danger" onClick={() => void askConfirm({ title: `Delete ${who}'s "${n0}"?`, okLabel: 'Delete', danger: true }).then((ok) => { if (ok && p) void useStory.getState().deleteCharacterPose(p.id, o.version ?? p.current, n0) })}>Delete {who}'s “{n0}”</button>
                }
                if (!f?.startsWith('saved:')) return <span className="hint">Click a pose: the figure takes it; one saved here can be deleted.</span>
                const n = f.slice(6)
                return <button type="button" className="quiet danger" onClick={() => void askConfirm({ title: `Delete the pose "${n}"?`, okLabel: 'Delete', danger: true }).then((ok) => { if (ok) void st().deletePose(n) })}>Delete “{n}”</button>
              }} />
            {edited && <span className="hint">edited</span>}
          </div>)
      })()}
      <div className="verbs"><CommandButton id="stage.pose.mirror" text /><CommandButton id="stage.pose.reset" text label="Reset" /><CommandButton id="stage.pose.save" text />
        {o.profile_id && <CommandButton id="stage.pose.saveForCharacter" text label={`Save for ${profiles.find((p) => p.id === o.profile_id)?.name ?? 'the character'}…`} />}</div>
      <Pins id={o.id} pose={shown?.pose ?? null} doc={current} />
      <h4>Joint <CommandButton id="stage.pose.mode" text label={posing ? 'Done posing' : 'Pose'} active={posing} /></h4>
      <div className="kv"><span>joint</span><select value={joint ?? ''} onChange={(e) => st().selectJoint(e.target.value || null)}><option value="">— click one in the viewport —</option>{JOINTS.map((j) => <option key={j} value={j}>{j}</option>)}</select></div>
      {v && <Vec label="x · y · z °" v={v} onChange={setJoint} step={5} />}
      <p className="hint">Gizmos <Help text="Pose shows them on the figure: orange spheres are joints (rotate), blue cubes are hands and feet (drag; elbow and shoulder follow). The figure's own transform stays on the Move / Rotate tools." /></p>
    </div>
    </>
  )
}

const END_LABEL: Record<End, string> = { r_hand: 'right hand', l_hand: 'left hand', r_foot: 'right foot', l_foot: 'left foot' }
const JOINT_LABEL: Record<string, string> = { head: 'head', spine: 'chest', root: 'hips', r_shoulder: 'right shoulder', l_shoulder: 'left shoulder', r_elbow: 'right hand', l_elbow: 'left hand',
  r_hip: 'right hip', l_hip: 'left hip', r_knee: 'right knee', l_knee: 'left knee' }
const short = (s: string) => s.replace('right ', 'R ').replace('left ', 'L ')
/** AP1b (D141): the figure's pins — a toggle per hand and foot (pinned where it is now), the commands for both feet / both hands / none;
 *  the rest: each pinned end held to a thing or a joint (a select per pin — the frame the pin is read in), and what the figure looks at. */
function Pins({ id, pose, doc }: { id: string; pose: StageObject['pose'] | null; doc: StageDoc | null }) {
  const pins = (pose?.pins ?? {}) as Partial<Record<End, number[]>>, contacts = (pose?.contacts ?? {}) as Contacts, gaze = pose?.gaze ?? null
  const n = ENDS.filter((e) => pins[e]).length
  const choices = useMemo(() => (doc ? contactChoices(doc, id) : []), [doc, id])
  const key = (c: { object_id?: string | null; joint?: string | null } | null | undefined) => (c?.object_id ? `${c.object_id}:${c.joint ?? ''}` : '')
  const parse = (v: string): Contact | null => { if (!v) return null; const at = v.indexOf(':'); return { object_id: v.slice(0, at), joint: (v.slice(at + 1) || null) as Contact['joint'] } }
  const held = choices.flatMap((c) => (c.joints.length ? c.joints.map((j) => <option key={`${c.object_id}:${j}`} value={`${c.object_id}:${j}`}>{c.name} · {JOINT_LABEL[j] ?? j}</option>)
    : [<option key={c.object_id} value={`${c.object_id}:`}>{c.name}</option>]))
  const looked = choices.filter((c) => c.object_id !== SELF).map((c) => <option key={c.object_id} value={c.joints.length ? `${c.object_id}:head` : `${c.object_id}:`}>{c.name}</option>)
  return (
    <>
    <div className="lib-row" data-group="pins"><span className="lib-label">Pins</span>
      <span className="segmented" role="group" aria-label="pins">{ENDS.map((e) => (
        <button key={e} type="button" className={pins[e] ? 'active' : ''} aria-pressed={!!pins[e]} data-end={e}
          title={pins[e] ? `Unpin the ${END_LABEL[e]}` : `Pin the ${END_LABEL[e]} where it is`}
          onClick={() => (pins[e] ? st().unpinEnds(id, [e]) : st().pinEnds(id, [e]))}>{short(END_LABEL[e])}</button>))}</span>
      <CommandButton id="stage.pose.unpin" />
      <span className="hint">{n ? `${n} pinned` : 'none'}</span>
      <Help text="A pinned hand or foot stays where it is while the hips, the spine or the other limbs turn: its arm or leg bends to keep it there (red rings in Pose). Turn or drag that limb itself and the pin goes with it." />
    </div>
    {n > 0 && <div className="lib-row" data-group="contacts"><span className="lib-label">Held to</span>
      {ENDS.filter((e) => pins[e]).map((e) => (
        <span key={e} className="kv"><span>{short(END_LABEL[e])}</span>
          <select value={key(contacts[e])} data-end={e} aria-label={`the ${END_LABEL[e]} held to`} onChange={(ev) => st().setContact(id, e, parse(ev.target.value))}>
            <option value="">the figure's own space</option>{held}</select></span>))}
      <Help text="A pinned hand or foot held to a thing goes with it (a hand on a prop that is then moved); held to another figure's joint it follows that limb (a hand on a shoulder); held to one of the figure's own joints it stays on it (a hand on the hip through a walk). It is read in that frame from now on — through keys and clips too. A pose saved for a character keeps the holds to its own joints; the others become plain pins." />
    </div>}
    <div className="lib-row" data-group="gaze"><span className="lib-label">Looks at</span>
      <select value={gaze?.camera ? 'camera' : key(gaze)} aria-label="looks at" onChange={(ev) => { const v = ev.target.value; st().setGaze(id, v === 'camera' ? { camera: true, object_id: null, joint: null } : v ? { ...parse(v)!, camera: false } : null) }}>
        <option value="">— the pose's own head —</option><option value="camera">the camera</option>{looked}</select>
      <CommandButton id="stage.pose.lookAtCamera" /><CommandButton id="stage.pose.lookAway" />
      <Help text="The head turns to what the figure looks at — the active camera, a thing, or another figure's face — a third of the turn on the neck, as far as a neck goes, and keeps looking through keys and clips. A preset keeps it; Stop looking gives the head back to the pose. A pose saved for a character keeps only a look at the camera." />
    </div>
    </>
  )
}

// ST3 (16 §3e / §7): the generation form for the blocking — the method (D78: clay reference by default, exact pose as the switch), image 1
// locked to the pass the method takes, the reference deck (D73), the prompt, the size tier and the candidates; the passes render on
// Generate when stale (or by the button), the results land below with lineage to the passes.
// D121: the form is Image › From a stage's alone (D95: stills are made in Image); the clip is Performance's Stage clip card, the final shot
// its Final shot card. A still clicked here is the stage clip's start there.
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

export function ShotTab() {
  const current = useStage((s) => s.current)
  const cam = useStage((s) => s.activeCamera())
  const sh = useStage((s) => s.shot)
  const pv = useStage((s) => s.shotPreview)
  const err = useStage((s) => s.shotPreviewError)
  const rendering = useStage((s) => s.rendering)
  const shots = useStage((s) => s.shots)
  const shotStart = useStage((s) => s.shotStart)
  const stills = shots.filter((a) => a.kind !== 'video')
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
      <div className="head"><b>Render</b><span className="hint">{cam ? `${cam.name} · ${cam.focal_mm} mm` : 'no camera'}</span><CameraShotVerb text={false} />
        <Help text="A frame of the stage through its active camera: the method reads the scene from the pass (image 1); the references and the figures' characters give the look. The stage's clip and its final shot are made in Animate › Performance (D121)." /></div>
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
              {room - figSlots.length > 0 && <div className="ref-slot" title="drop a picture from the Bin here"><span className="empty">{sh.refs.length + figSlots.length + 2}</span></div>}
            </div>
            {figLines.length > 0 && <ul className="figure-lines" aria-label="the figures and their reference images">{figLines.map((t) => <li key={t}>{t}</li>)}
              {pv?.params?.bind_refs === false && <li className="muted">this method reads the figures' images by their notes — not bound in its prompt</li>}
              {/* journal 2026-10-17 18:03: exact pose (one reference slot) drew both figures as figure 1's character; clay carried each one's images */}
              {figs.length > 1 && figs.some((f) => !f.refs?.length) && <li className="warn">this method has room for {method?.max_refs ?? 1} reference image{(method?.max_refs ?? 1) === 1 ? '' : 's'}: {figs.filter((f) => !f.refs?.length).map((f) => `figure ${f.figure}`).join(', ')} only get{figs.filter((f) => !f.refs?.length).length === 1 ? 's' : ''} words — for several characters use a method with more room (Clay reference)</li>}</ul>}
            {!figLines.length && current.objects.some((o) => o.kind === 'mannequin') && <p className="hint">Figures not bound <Help text="Bind a figure to a Cast character (Inspector › character, or right-click ▸ Bind to a character): its reference images and sheet go into the frame, figure by figure, left to right." /></p>}
            {sh.method === 'refcontrol' && !sh.refs.length && <p className="disabled-why">Exact pose needs one reference image (image 2): drop a picture from the Bin on the deck.</p>}
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
            {!stills.length && <span className="hint">None yet. <Help text="The frames of this stage land here and in the Bin (lineage: the pass and the references). Click one: it is the start of the stage's clip (Animate › Performance › Stage clip)." /></span>}
            <div className="shot-results">{stills.slice(0, 12).map((a) => <img key={a.id} className={`shot-thumb${shotStart === a.id ? ' start' : ''}`} src={api.thumbUrl(a.id, 256)} alt="" title={`${a.model_id ?? ''} · seed ${a.seed ?? ''} — click: the stage clip starts from this frame`} onClick={() => st().setShotStart(shotStart === a.id ? null : a.id)} />)}</div>
          </div></div>
      </Step>
    </div>
  )
}

// ST4 (16 §8): the clip — the pass sequence over the range (depth by default, pose as the weaker second, D76) rendered by the viewport,
// the start frame picked among the shots, Animate ▶ through LTX-2.3's IC-LoRA; the stage's clips land in the card and in Animate.
function ClipSection() {
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
  const stale = useStage((s) => s.guideStale())
  markUsed('stage.clip.guide')
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
      {!shotStart && <p className="disabled-why">Pick the start above.</p>}
      {clipCap && <p className="hint">{clipCap.label} · ≈ {clipCap.seconds != null ? Math.round(clipCap.seconds) : '?'} s for {method === 'animate' ? '77 frames' : '121 frames'}{clipCap.health === 'missing' ? ' · weights missing — Models › Fetch' : ''}<Help text={method === 'animate' ? 'Wan Animate (E19): one figure in the camera; the picked result is the character.' : 'LTX-2.3 with its IC-LoRA (E11): the depth or pose sequence from the picked frame.'} /></p>}
    </div>
  )
}

/** D121 (26 §5.3): Performance's Stage clip card — the stage's start frame (picked among its stills, made in Image › From a stage), what the
 *  scene is (the prompt the clip shares with the frame), the clip's method and guide, and the stage's clips. Render clip ▶ is the foot's. */
export function StageClipCard() {
  const current = useStage((s) => s.current)
  const shots = useStage((s) => s.shots)
  const shotStart = useStage((s) => s.shotStart)
  const prompt = useStage((s) => s.shot.prompt_text)
  if (!current) return <span className="hint">Open a stage in Clay first.</span>
  const stills = shots.filter((a) => a.kind !== 'video')
  const clips = shots.filter((a) => a.kind === 'video')
  return (
    <div className="stage-panel stage-clip" data-card="clip">
      <div className="kv tall"><span>start <Help text="The clip starts from one of the stage's frames — the stills made from it in Image › From a stage. With Wan Animate the picked frame is the character who performs." /></span>
        <div>
          <div className="shot-results start-stills">{stills.slice(0, 12).map((a) => <img key={a.id} className={`shot-thumb${shotStart === a.id ? ' start' : ''}`} src={api.thumbUrl(a.id, 256)} alt="" title={`${a.model_id ?? ''} · seed ${a.seed ?? ''} — click: the clip starts from this frame`} onClick={() => st().setShotStart(shotStart === a.id ? null : a.id)} />)}</div>
          {!stills.length && <span className="hint">No frame of this stage yet.</span>}
          <div className="verbs"><CommandButton id="stage.frame.make" text label="Make a frame ▸" /></div>
        </div></div>
      <div className="kv tall"><span>prompt</span><textarea className="shot-prompt" rows={2} value={prompt} placeholder="what the scene is (the frame's prompt)" onChange={(e) => st().setShot({ prompt_text: e.target.value })} /></div>
      <ClipSection />
      {clips.length > 0 && <><h4>Clips · {clips.length}</h4>
        <div className="clip-results">{clips.slice(0, 9).map((a) => <span key={a.id} className="clip-thumb"><img className="shot-thumb" src={api.thumbUrl(a.id, 256)} alt="" title={`${a.frames ?? '?'} frames · ${a.model_id ?? ''}`} /><span className="n">{a.frames ?? '?'} f</span></span>)}</div></>}
    </div>
  )
}

/** D121: the Stage clip card's foot — Render clip ▶ (the sequence rendered first when it is missing or stale), with the model's estimate. */
export function ClipFoot() {
  const current = useStage((s) => s.current)
  const shotStart = useStage((s) => s.shotStart)
  const rendering = useStage((s) => s.rendering)
  const method = useStage((s) => s.clipMethod)
  const caps = useSession((s) => s.capabilities?.stage)
  markUsed('stage.clip.animate')
  const cap = method === 'animate' ? caps?.animate : caps?.clip
  const reason = !current ? 'open a stage in Clay' : !cap ? 'no clip model in this build' : !shotStart ? 'pick the start' : rendering ? 'rendering the sequence…' : null
  return (
    <div>
      <button className="primary" disabled={!!reason} onClick={() => runCommand('stage.clip.animate')} title="The stage's sequence animated from the start frame — the sequence is rendered first when it is missing or stale (Ctrl+Enter)">Render clip ▶</button>
      <div className="estimate">{reason ? <span style={{ color: 'var(--fg3)' }}>{reason}</span> : <span>{cap!.label} · ≈ {cap!.seconds != null ? Math.round(cap!.seconds) : '?'} s</span>}</div>
    </div>
  )
}

/** The project's stages, poses and meshes, loaded when a project opens (Animate's column mounts it, D95 AN1). */
export function useStageLoad(): void {
  const project = useSession((s) => s.project)
  useEffect(() => { if (project?.open) { void st().load(); void st().loadPoses(); void st().loadMeshes(); void st().loadTemplates() } }, [project?.path]) // eslint-disable-line react-hooks/exhaustive-deps
}

/** Image › From a stage's foot (D95 AN1): New stage, else Render frame ×n with its estimate. */
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
      <button className="primary" disabled={!!reason} onClick={() => runCommand('stage.shot.generate')} title="Render the passes if they are stale, then queue the frame (Ctrl+Enter)">Render frame{count > 1 ? ` ×${count}` : ''} ▶</button>
      <div className="estimate">{reason ? <span style={{ color: 'var(--fg3)' }}>{reason}</span> : <><span className={`dot ${pv?.estimate.vram_fit ?? 'ok'}`} />≈ {Math.round((pv?.estimate.seconds ?? 0) * count)} s · {String(pv?.params?.label ?? '')}</>}</div>
    </div>
  )
}

// ------------------------------------------------------------------ keys (U1, D157: the shell's, frame/keyHosts.tsx — not the Strip's)
function useStageKeys(): void {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (useSession.getState().ui.suite !== 'stage') return
      if (document.querySelector('.ctx-menu')) return                     // D90: an open menu owns the arrows, Space and Enter
      if (inField(e)) { primaryInField(e, ['stage.shot.passes']); return }   // D90 (B1): a key typed into a field never reaches the tools (Delete deleted the object)
      handleKeysAt('stage', e)                                           // D121: Clay's reach — the stage's keys, then the one transport and the mode keys (animateCommands.ts)
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [])
}
registerKeyHost('stage', function StageKeys() { useStageKeys(); return null })

// ------------------------------------------------------------------ Strip
export function Strip() {
  const guides = useStage((s) => s.guides)
  const pip = useStage((s) => s.pip)
  const current = useStage((s) => s.current)
  if (!current) return <div className="stage-strip-wrap"><div className="stage-strip"></div></div>
  return (
    <div className="stage-strip-wrap">
      <div className="stage-strip">
        
        <CommandButton id="stage.guides" active={guides} />
        <CommandButton id="stage.view.pip" active={pip} />{/* D121 (AW4); the view switch is the camera pill over the viewport */}
        <CommandButton id="stage.frameAll" />
        <span className="spacer" />
        <span className="hint">{current.name} · {current.size.w}×{current.size.h}</span>
      </div>
    </div>
  )
}

// ST4 (16 §8) → D121 (AW2): Clay's timeline — the one transport (anim.*: play, step, the range's ends, previous / next key) with the frame
// field, the range and the stage's key verbs; then the one timeline: the range as the work area (its ends dragged), a row for the active
// camera and one for each keyed object — a motion clip's bake as a bar, single keys as diamonds (drag one to move it, right-click to remove
// it, click to go to it). Nothing keyed: the ruler alone (the bar), as ArtCraft's collapsed timeline.
/** U5d: the shot this stage camera is for — the Story store's open shot when it is, else the first whose current version looks through it. */
function useLineShot(stageId: string, cameraId: string | null) {
  const shots = useStory((s) => s.shots)
  const sel = useStory((s) => s.shotId)
  return useMemo(() => {
    const mine = (x: (typeof shots)[number]) => { const v = x.versions.find((y) => y.id === x.current) ?? x.versions[0]; return !!cameraId && v?.stage_id === stageId && v.camera_id === cameraId }
    return shots.find((x) => x.id === sel && mine(x)) ?? shots.find(mine) ?? null
  }, [shots, sel, stageId, cameraId])
}

/** U5d: the timeline's read-only rows — the shot's lines (each as long as its voice) and each bound figure's stretches with its back to
 *  the active camera, saying when its character has no back view (right-click: make it in World). */
function useReadOnlyRows(current: StageDoc, cam: StageCamera | null, start: number, end: number): TLRow[] {
  const shot = useLineShot(current.id, cam?.id ?? null)
  const node = useStory((s) => (shot?.owner_node ? s.flowNodes[shot.owner_node] : undefined))
  const secs = useStory((s) => s.audioSecs)
  const profiles = useStory((s) => s.profiles)
  const version = useBlocks((s) => s.version)
  useEffect(() => { const ids = (node?.lines ?? []).map((l) => l.audio_asset_id).filter((x): x is string => !!x); if (ids.length) void useStory.getState().loadAudioSecs(ids) }, [node])
  const away = useMemo(() => (cam ? current.objects.filter((o) => o.kind === 'mannequin' && o.visible).map((o) => ({ o, at: awayStretches(current, o.id, cam.id, start, end) })).filter((x) => x.at.length) : []),
    [current, cam, start, end, version])   // eslint-disable-line react-hooks/exhaustive-deps
  const out: TLRow[] = []
  const v = shot ? shot.versions.find((x) => x.id === shot.current) ?? shot.versions[0] : null
  const spans = node ? lineSpans(node.lines, secs, v?.range?.start ?? start, current.size.fps || 24) : []
  const who = (id: string | null) => (id ? profiles.find((p) => p.id === id)?.name ?? 'someone' : 'narrator')
  if (spans.length) out.push({ id: 'lines', label: 'Lines', data: { kind: 'lin' }, title: `${shot?.name}'s lines, one after another from the shot's start, each as long as its voice`,
    bars: spans.map((l) => ({ id: `ln${l.index}`, from: l.from, to: l.to, className: `line${l.estimated ? ' estimated' : ''}`, label: `${who(l.speaker)}: ${l.text}`,
      title: `${who(l.speaker)}: “${l.text}” — ${l.seconds.toFixed(1)} s${l.estimated ? ' (not voiced yet: timed by its words)' : ''}` })) })
  for (const { o, at } of away) {
    const p = o.profile_id ? profiles.find((x) => x.id === o.profile_id) : undefined
    const pv = p ? p.versions.find((x) => x.id === (o.version ?? p.current)) ?? p.versions[0] : undefined
    const noBack = !!p && p.cls === 'character' && !pv?.anim_ref_back_asset_id
    out.push({ id: `away:${o.id}`, label: `${o.name} · back to camera`, data: { kind: 'away' },
      bars: at.map(([a, b]) => ({ id: `aw${a}`, from: a, to: b, className: `away${noBack ? ' warn' : ''}`, label: noBack ? 'no back view' : 'back to camera',
        title: `${p?.name ?? o.name} faces away from ${cam!.name} here${noBack ? `, and has no back view — right-click: make it in World` : ''}` })),
      onMenu: (e) => { e.preventDefault(); showMenu(e, [{ label: `Make ${p?.name ?? o.name}'s back view in World ▸`, disabled: !p || p.cls !== 'character',
        run: () => { if (!p) return; useStory.getState().selectProfile(p.id, pv?.id ?? null); navigate({ suite: 'story', tab: 'cast' }) } }]) } })
  }
  return out
}

function Timeline() {
  const current = useStage((s) => s.current)!
  const frame = useStage((s) => s.frame)
  const playing = useStage((s) => s.playing)
  const selected = useStage((s) => s.selected)
  const selectedCamera = useStage((s) => s.selectedCamera)
  const k = keyframesOf(current)                                                  // derived from `current` (subscribed): a selector must not return a fresh object
  const keyed = keyedFramesOf(k, current.active_camera)
  const { start, end } = current.range
  const cam = current.cameras.find((c) => c.id === current.active_camera) ?? null
  const camKeys = cam ? (k.camera[cam.id] ?? []).map((x) => x.frame) : []
  const tracks = current.tracks ?? {}
  const blockErrors = useBlocks((s) => s.errors)
  // U5e (04 §3.2): a thing held in a figure's hand has a track too — carried, it goes where the hand goes
  const objects = current.objects.filter((o) => (k.objects[o.id] ?? []).length > 0 || (tracks[o.id] ?? []).length > 0 || (!!o.parent_joint && !!o.parent))
  const skeletons = current.objects.filter((o) => (k.skeleton?.[o.id] ?? []).length > 0)        // CS3: the figures with skeleton keys
  const blockEnd = (b: MotionBlock) => b.start + Math.max(1, b.length) - 1
  const span = stageSpan(end, [...camKeys, ...objects.flatMap((o) => (k.objects[o.id] ?? []).map((x) => x.frame)), ...objects.flatMap((o) => (tracks[o.id] ?? []).map(blockEnd)),
    ...skeletons.flatMap((o) => k.skeleton![o.id].map((x) => x.frame + x.transition))])
  markUsed('stage.anim.keyCamera'); markUsed('stage.anim.keyObject'); markUsed('stage.anim.removeKey')
  const row = (id: string, label: string, frames: number[], sel: boolean, onSelect: () => void): TLRow => {
    const { runs, singles } = keyRuns(frames)
    return { id, label, selected: sel, onSelect, data: { kind: id.slice(0, 3) },
      bars: runs.map(([a, b]) => ({ id: `${a}`, from: a, to: b, label: `motion · ${b - a + 1}`, className: 'motion', title: `${b - a + 1} keys frame by frame (a motion clip), frames ${a}–${b}` })),
      keys: singles.map((f) => ({ frame: f, title: `key at frame ${f} — click: go there; drag: move it; right-click: move it to the playhead or remove it` })) }
  }
  const rows: TLRow[] = []
  const extraRows = useReadOnlyRows(current, cam, start, end)
  if (cam) rows.push(row(`cam:${cam.id}`, `camera · ${cam.name}`, camKeys, selectedCamera === cam.id, () => st().selectCamera(cam.id)))   // U5e (04 §3.2): the camera's track, keyed or not
  for (const o of objects) {
    const r = row(`obj:${o.id}`, o.name, (k.objects[o.id] ?? []).map((x) => x.frame), selected === o.id, () => st().select(o.id))
    // U5 (G8): the figure's clip blocks — the clip and its loops, past the range's end when longer than the shot (the range never moves by itself)
    r.onMenu = (e) => {                                                           // U5c: a block's own menu, else the track's
      e.preventDefault()
      const bid = (e.target as HTMLElement).closest('[data-block]')?.getAttribute('data-block')
      showMenu(e, bid ? blockMenu(o.id, bid) : [{ label: `Save ${o.name}'s motion in the shot's range as an animation…`, run: () => void saveRangeAsAnimation(o.id) }])
    }
    r.bars = [...(tracks[o.id] ?? []).map((b) => ({ id: `blk:${b.id}`, from: b.start, to: blockEnd(b), className: `block${blockErrors[b.id] ? ' failed' : ''}`, drag: true, data: { block: b.id },
      label: `${b.source.clip || 'animation'}${b.loops > 1 ? ` ×${b.loops}` : b.loops === 0 ? ' · along its path' : ''}`,
      title: blockErrors[b.id] ? `${b.source.clip}: ${blockErrors[b.id]}` : `${b.source.clip || 'an animation'}: frames ${b.start}–${blockEnd(b)}${blockEnd(b) > end ? " (past the shot's range)" : ''} — drag to move it, its edges to trim or loop it (Alt: slide the clip in it); right-click: speed, loops, blend, bake, save` })), ...(r.bars ?? [])]
    const holder = o.parent_joint && o.parent ? current.objects.find((x) => x.id === o.parent) : undefined
    if (holder) r.bars = [...(r.bars ?? []), { id: 'held', from: start, to: end, className: 'held', label: `in ${holder.name}'s ${o.parent_joint === 'r_hand' ? 'right' : 'left'} hand`,
      title: `${o.name} is held by ${holder.name} — it moves with the hand (its right-click on the stage: put it down)` }]
    rows.push(r)
  }
  for (const o of skeletons) {                                                    // CS3: a skeleton key a diamond, its transition a bar after it
    const ks = k.skeleton![o.id]
    const what = (x: { body: unknown; transition: number }) => `${x.body ? 'the body held as it was keyed' : "Cast's skeleton"}${x.transition ? `, reached over ${x.transition} frames` : ', a cut'}`
    rows.push({ id: `skl:${o.id}`, label: `${o.name} · skeleton`, selected: selected === o.id, onSelect: () => st().select(o.id), data: { kind: 'skl' },
      bars: ks.filter((x) => x.transition > 0).map((x) => ({ id: `t${x.frame}`, from: x.frame, to: x.frame + x.transition, label: x.body ? '→ held' : '→ Cast', className: 'transition', title: `frames ${x.frame}–${x.frame + x.transition}: ${what(x)}` })),
      keys: ks.map((x) => ({ frame: x.frame, title: `skeleton key at frame ${x.frame}: ${what(x)} — right-click: its transition, held or Cast's, remove it` })) })
  }
  // U5d (04 §3.2): the open shot's lines, read-only, at their place on the scene's timeline; F42: a figure's back to the camera, marked
  for (const r of extraRows) rows.push(r)
  const keyMenu = (e: React.MouseEvent, r: string, f: number) => {
    const skl = r.startsWith('skl:') ? (k.skeleton?.[r.slice(4)] ?? []).find((x) => x.frame === f) : undefined
    const id = r.slice(4)
    showMenu(e, [{ label: `Go to frame ${f}`, run: () => { st().setPlaying(false); st().setFrame(f) } },
      { label: `Move this key to the playhead (frame ${frame})`, disabled: frame === f, run: () => st().moveKey(r, f, frame) },   // D32: the drag's menu equivalent
      ...(skl ? [sep, ...[0, 12, 24, 48].map((n) => ({ label: n ? `Reached over ${n} frames` : 'A cut', checked: skl.transition === n, run: () => st().setSkeletonKey(id, { ...skl, transition: n }) })), sep,
        { label: "Cast's skeleton from here", checked: !skl.body, run: () => st().setSkeletonKey(id, { ...skl, body: null }) },
        { label: 'Hold the body it has here', checked: !!skl.body, disabled: !!skl.body, run: () => { const b = sampleDoc(current, f).objects.find((o) => o.id === id)?.body; if (b) st().setSkeletonKey(id, { ...skl, body: JSON.parse(JSON.stringify(b)) }) } }] : []),
      sep, { label: 'Remove this key', danger: true, run: () => st().removeRowKey(r, f) }])
  }
  return (
    <div className="stage-timeline" onPointerDown={(e) => e.stopPropagation()}>
      <TransportBar frame={frame} last={span[1]} playing={playing} onFrame={(f) => st().setFrame(f)} counter={`${(frame / Math.max(1, current.size.fps)).toFixed(2)} s`}>
        <span className="range-field" title="the clip's range (frames, inclusive) at the project's fps — or drag its ends on the ruler">
          <input type="number" min={0} value={start} onChange={(e) => st().setRange(Number(e.target.value) || 0, end)} />–<input type="number" min={1} value={end} onChange={(e) => st().setRange(start, Number(e.target.value) || 1)} /> · {current.size.fps} fps
        </span>
        <CommandRow ids={['anim.setIn', 'anim.setOut']} />
        <span className="sep" />
        <CommandButton id="stage.anim.keyCamera" text label="Key camera" active={keyed.includes(frame) && !!(st().keys().camera[current.active_camera ?? ''] ?? []).some((x) => x.frame === frame)} />
        <CommandButton id="stage.anim.keyObject" text label={selected ? 'Key object' : 'Key object (select one)'} />
        <CommandButton id="stage.anim.removeKey" />
      </TransportBar>
      <TimelineView className="stage-tl" span={span} fps={current.size.fps} frame={frame} onSeek={(f) => { st().setPlaying(false); st().setFrame(f) }}
        work={{ from: start, to: end, title: "the clip's range", onChange: (a, b) => st().setRange(a, b) }} rows={rows}
        onKeyDrag={(r, from, to) => st().moveKey(r, from, to)} onKeyMenu={keyMenu}
        onBarDrag={(r, bar, mode, delta) => { if (r.startsWith('obj:') && bar.startsWith('blk:')) dragBlock(r.slice(4), bar.slice(4), mode, delta) }} />
    </div>
  )
}

// ------------------------------------------------------------------ D121 (AW4): the viewport's camera chrome
/** The active camera as the viewport shows it — sampled at the playhead (a keyed camera's lens and place are its keys'), T8. */
function useShotCamera(): StageCamera | null {
  const current = useStage((s) => s.current)
  const frame = useStage((s) => s.frame)
  return useMemo(() => { const cam = current?.cameras.find((c) => c.id === current.active_camera); return current && cam ? sampleCamera(cam, keyframesOf(current).camera[cam.id], frame) : null }, [current, frame])
}

/** The camera pill over the viewport's top right — the camera the shot renders through and its lens; a click looks through it (again: back
 *  to the free view); its menu picks another camera, sets the lens, sets the camera from the view, adds one, toggles the PiP and guides. */
function CameraPill() {
  const current = useStage((s) => s.current)
  const view = useStage((s) => s.view)
  const pip = useStage((s) => s.pip)
  const guides = useStage((s) => s.guides)
  const cam = useShotCamera()
  markUsed('stage.view.camera'); markUsed('stage.view.free')
  if (!current || !cam) return null
  const through = view === 'camera'
  const items = (): MenuItem[] => [
    ...current.cameras.map((c) => ({ label: `${c.id === current.active_camera ? '★ ' : ''}${c.name} · ${c.focal_mm} mm`, run: () => st().selectCamera(c.id) })), sep,
    ...FOCALS.map((f) => ({ label: `${f} mm`, checked: cam.focal_mm === f, run: () => st().updateCamera(cam.id, { focal_mm: f }) })), sep,
    { cmd: 'stage.camera.setFromView' }, { cmd: 'stage.camera.add' }, sep, { cmd: 'stage.view.pip', checked: pip }, { cmd: 'stage.guides', checked: guides }]
  return (
    <div className="cam-pill" onPointerDown={(e) => e.stopPropagation()} onPointerUp={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()}>
      <button type="button" className={`cam-pill-main${through ? ' active' : ''}`} aria-pressed={through} onClick={() => runCommand(through ? 'stage.view.free' : 'stage.view.camera')}
        title={through ? `Looking through ${cam.name} — a click goes back to the free view (0)` : `The shot renders through ${cam.name} — a click looks through it (0)`}>
        <Video size={14} /> {through ? `${cam.name} · ${cam.focal_mm} mm` : `Free view · ★ ${cam.name} · ${cam.focal_mm} mm`}
      </button>
      <MenuButton label="Cameras and lens" icon={Aperture} items={items} />
    </div>
  )
}

/** The lens in large type over the viewport for a moment after it changes (the pill's menu, the camera's row, a key) — ArtCraft's focal display. */
function LensReadout() {
  const cam = useShotCamera()
  const playing = useStage((s) => s.playing)
  const [shown, setShown] = useState<number | null>(null)
  const last = useRef<{ id: string; focal: number } | null>(null)
  useEffect(() => {
    if (!cam) return
    const prev = last.current
    last.current = { id: cam.id, focal: cam.focal_mm }
    if (!prev || (prev.id === cam.id && prev.focal === cam.focal_mm) || playing) return  // the first sight of a camera is no change; a zoom played is not shown
    setShown(cam.focal_mm)
    const t = window.setTimeout(() => setShown(null), 1200)
    return () => window.clearTimeout(t)
  }, [cam?.id, cam?.focal_mm]) // eslint-disable-line react-hooks/exhaustive-deps
  return shown === null ? null : <div className="lens-readout" aria-live="polite">{shown} mm</div>
}

// ------------------------------------------------------------------ Stage · the viewport
function Viewport() {
  const hostRef = useRef<HTMLDivElement>(null)
  const canvasHolderRef = useRef<HTMLDivElement>(null)
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
  const poseMode = useStage((s) => s.posing)                                           // D121: the pose pill (not the Motion section on screen) shows the joint pickers
  const figure = useStage((s) => { const o = s.object(s.selected); return o?.kind === 'mannequin' ? o : null })
  const [rect, setRect] = useState<{ x: number; y: number; w: number; h: number } | null>(null)
  const [pipRect, setPipRect] = useState<{ x: number; y: number; w: number; h: number } | null>(null)   // D121 (AW4): where the PiP sits
  const pip = useStage((s) => s.pip)
  const shotCam = useShotCamera()
  const { ref: dropRef, over } = useDropTarget((d) => onlyAssets(d) && d.items.some((i) => i.media !== 'video') && !!useStage.getState().current,
    (d) => { const it = d.items.find((i) => i.kind === 'asset' && i.media !== 'video'); const e = engineRef.current; const p = lastPointer.current
      if (it && e) st().addObject(it.media === 'mesh' ? 'mesh' : 'plane', null, (p ? e.place(p.x, p.y) : null) ?? e.centre(), it.id) },         // P18: a mesh lands as a prop
    (d) => { const it = d.items.find((i) => i.kind === 'asset' && i.media !== 'video'); return it ? { ok: true, label: it.media === 'mesh' ? 'Place the prop here' : 'Place as an image plane' } : { ok: false, reason: 'Only images and meshes go on the stage' } })
  // the engine: one per mounted viewport (kept alive with the suite, D69). U0 (F34): the canvas is made here, a fresh one per mount — dispose()
  // force-loses its GL context (V82), and StrictMode's mount → cleanup → mount in a dev build would hand the second engine that dead context
  useEffect(() => {
    const holder = canvasHolderRef.current, host = hostRef.current
    if (!holder || !host) return
    const canvas = document.createElement('canvas')
    canvas.className = 'stage-canvas'
    holder.appendChild(canvas)
    const engine = new StageEngine(canvas, {
      onPick: (id) => st().select(id),
      onTransformed: (id, t) => st().setTransform(id, t),
      onPickCamera: (id) => st().selectCamera(id),
      onCameraMoved: (id, pos) => st().moveCamera(id, pos),                                                // D119 (SC1): the camera's body dragged
      onCameraTurned: (id, target, roll) => st().updateCamera(id, { target, roll }),                      // the body turned with the rotate tool
      onPosed: (id, joints, moved) => st().setJoints(id, joints, moved),
      onDetailError: (_id, message) => useSession.getState().toast(`The Detailed mannequin did not load — the figure stays Simple: ${message}`, 'error'),   // CA1
      onMeshThumb: (assetId, view) => void st().uploadMeshThumbnail(assetId, view),
    })
    engineRef.current = engine
    viewport.centre = () => engine.centre(); viewport.freePose = () => engine.freePose(); viewport.frame = (ids) => engine.frame(ids); viewport.snapshot = (id) => engine.snapshotOf(id); useStage.setState({ worldOf: (id) => engine.worldOf(id) })
    useStage.setState({ passRenderer: (cam, w, h) => { const s = st(); if (s.current) engine.sync(sampleDoc(s.current, s.frame)); return engine.renderPasses(cam, w, h) },   // U5: the document at the playhead, its blocks evaluated sequenceRenderer: (fr, w, h, kind, restore, on) => engine.renderSequence(fr, w, h, kind, restore, on),
      plateProjector: (fr, w, h, plate, proj, aspect, restore, on, coverage) => engine.renderProjected(fr, w, h, plate, proj, aspect, restore, on, coverage) })   // ST3 / ST4, D111; D132: coverage
    viewport.handPreset = (id, side, preset) => engine.handPreset(id, side, preset)                                   // CA1
    if (DEV_HOOKS) Object.assign(devHook(), { worldOf: (id: string) => engine.worldOf(id), heightOf: (id: string) => engine.heightOf(id), screenOf: (at: string) => engine.screenOf(at as Joint), cameraScreen: (id: string) => engine.cameraScreen(id), gizmoMode: () => engine.gizmoMode(), pipRect: () => engine.pipRect(), imageSetLayers: (id: string) => engine.imageSetLayers(id),
      frameTime: (n: number, on: boolean) => { const was = useStage.getState().pip; engine.setPip(on); const t = engine.measureFrame(n); engine.setPip(was); return t }, meshes: () => ({ loaded: [...engine.meshesLoaded], failed: Object.fromEntries(engine.meshesFailed) }) })   // the smoke test aims the mouse at joints and handles; P18 asks which props loaded
    const ro = new ResizeObserver(() => { const r = host.getBoundingClientRect(); engine.resize(Math.round(r.width), Math.round(r.height)); setRect({ ...engine.frameRect() }); setPipRect(engine.pipRect()) })
    ro.observe(host)
    engine.start()
    return () => { ro.disconnect(); engine.dispose(); canvas.remove(); engineRef.current = null; viewport.centre = undefined; viewport.freePose = undefined; viewport.frame = undefined; viewport.handPreset = undefined; viewport.snapshot = undefined; useStage.setState({ worldOf: null }); useStage.setState({ passRenderer: null, sequenceRenderer: null, plateProjector: null }) }
  }, [])
  useEffect(() => { const e = engineRef.current; if (!e) return; if (active) e.start(); else e.stop() }, [active])
  const frame = useStage((s) => s.frame)
  const playing = useStage((s) => s.playing)
  const blocksVersion = useBlocks((s) => s.version)                                                                 // U5: a clip block evaluated — sync again
  useEffect(() => { const e = engineRef.current; if (e && current) { e.setAspect(current.size.w / current.size.h); e.sync(sampleDoc(current, frame)); setRect({ ...e.frameRect() }); setPipRect(e.pipRect()) } }, [current, frame, blocksVersion])   // ST4: the document at the frame
  useEffect(() => {                                                                                                     // ST4: playback loops over the range at the project's fps
    if (!playing || !current || !active) return                                                                         // V87 (D69): hidden, the loop rests; it goes on when the level is back
    const t = window.setInterval(() => { const s = st(); const cur = s.current; if (!cur) return; s.setFrame(s.frame + 1 > cur.range.end ? cur.range.start : s.frame + 1) }, 1000 / Math.max(1, current.size.fps))
    return () => window.clearInterval(t)
  }, [playing, active, current?.size.fps]) // eslint-disable-line react-hooks/exhaustive-deps
  const selectedCamera = useStage((s) => s.selectedCamera)
  useEffect(() => { engineRef.current?.select(selected) }, [selected])
  useEffect(() => { engineRef.current?.selectCamera(selectedCamera) }, [selectedCamera])                   // D119 (SC1)
  useEffect(() => { engineRef.current?.setTool(tool, snap) }, [tool, snap])
  useEffect(() => { const e = engineRef.current; if (!e) return; e.setView(view); if (view === 'camera' && current) e.sync(current); setPipRect(e.pipRect()) }, [view]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { const e = engineRef.current; if (!e) return; e.setPip(pip); setPipRect(e.pipRect()) }, [pip])   // D121 (AW4)
  useEffect(() => { if (frameReq.n) engineRef.current?.frame(frameReq.ids) }, [frameReq])
  useEffect(() => { engineRef.current?.setPoseMode(poseMode); if (!poseMode) st().selectJoint(null) }, [poseMode])
  useEffect(() => { const e = engineRef.current; if (e && selected) e.selectJoint(selected, selectedJoint as Joint | null) }, [selectedJoint]) // eslint-disable-line react-hooks/exhaustive-deps
  const down = useRef<{ x: number; y: number; t: number; hot: boolean } | null>(null)
  const onDown = (e: ReactPointerEvent) => { if (e.button === 0) down.current = { x: e.clientX, y: e.clientY, t: Date.now(), hot: !!engineRef.current?.gizmo.axis } }   // on a gizmo handle: the click is the gizmo's
  const onUp = (e: ReactPointerEvent) => {
    const d = down.current; down.current = null
    const eng = engineRef.current
    if (!d || !eng || e.button !== 0 || d.hot || Math.hypot(e.clientX - d.x, e.clientY - d.y) > 4 || eng.gizmo.dragging) return
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
      <div ref={canvasHolderRef} className="stage-canvas-holder" />
      {current && <div className="gizmo-bar" onPointerDown={(e) => e.stopPropagation()} onPointerUp={(e) => e.stopPropagation()}>
        <CommandRow ids={['stage.tool.select', 'stage.tool.move', 'stage.tool.rotate', 'stage.tool.scale', 'stage.tool.path', 'gap', 'stage.snap', 'gap', 'stage.undo', 'stage.redo']} active={`stage.tool.${tool}`} />
        {snap && <span className="hint">snap</span>}
      </div>}
      {current && figure && <div className="pose-pill" onPointerDown={(e) => e.stopPropagation()} onPointerUp={(e) => e.stopPropagation()}>{/* D121: pose mode by the figure, ArtCraft's Enter Pose Mode / Done */}
        <CommandButton id="stage.pose.mode" text active={poseMode} label={poseMode ? `Done posing ${figure.name}` : `Pose ${figure.name}`} />
        {poseMode && <Help text="Orange spheres are joints: click one for its rotate gizmo. Blue cubes are hands and feet: drag one and the elbow or knee follows. Done (or a click on the floor) ends pose mode." />}
      </div>}
      {current && view === 'camera' && rect && guides && <div className="frame-guides" style={{ left: rect.x, top: rect.y, width: rect.w, height: rect.h }}><i className="thirds" /><i className="centre" /></div>}
      {current && <CameraPill />}{/* D121 (AW4): which camera, its lens, look through — ArtCraft's camera pill */}
      <LensReadout />
      {current && pipRect && view === 'free' && <button type="button" className="pip-frame" style={{ left: pipRect.x, top: pipRect.y, width: pipRect.w, height: pipRect.h }}
        onPointerDown={(e) => e.stopPropagation()} onPointerUp={(e) => e.stopPropagation()} onClick={() => runCommand('stage.view.camera')}
        title="The active camera's picture — a click looks through it"><span>{shotCam?.name} · {shotCam?.focal_mm} mm</span></button>}
      {current && !current.objects.length && <div className="stage-empty"><div>Empty stage — add a set and a figure from the Scene section, or drop a picture from the Bin.<div className="quick-cards"><CommandButton id="stage.add.set.room" text /><CommandButton id="stage.add.mannequin.adult" text /></div></div></div>}
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

/** D125 (A3): the camera's Story verb — with Animate's For chip it is used for that shot (no second shot), without one a new shot is made from it. */
function CameraShotVerb({ text = true }: { text?: boolean }) {
  const f = useMakeFor((s) => s.animate)
  useStory((s) => s.shots)                                            // linked meanwhile: the verb's state follows
  return f ? <CommandButton id="stage.camera.useForShot" text={text} label={`Use this camera for ${f.name}`} /> : <CommandButton id="stage.camera.toShot" text={text} />
}
