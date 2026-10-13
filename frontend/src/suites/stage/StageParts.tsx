// P13 / ST1 (D81): the Stage suite's parts (16; StageSuite.ts registers them) — Panel (Library · Outliner · Cameras), Strip (view, guides, frame), the viewport Stage with
// its floating gizmo bar and the framing rectangle, the Inspector (object · camera · stage). Mouse-first (D32): every verb is a
// button or a menu entry; keys are accelerators. Keep-alive (D69): the engine pauses while the suite is hidden and keeps its view.
import { Camera, Eye, EyeOff, Lock, LockOpen } from 'lucide-react'
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { CommandButton, CommandRow } from '../../frame/CommandButton'
import { handleKeyFor, markUsed, runCommand } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { onlyAssets, useDropTarget } from '../../frame/drag'
import { shotRefDrop } from '../../frame/dropRules'
import { api } from '../../api/client'
import { DEV_HOOKS } from '../../devHooks'
import { useStageActive } from '../../frame/stageKeep'
import { useSuiteRail } from '../../frame/suiteRegistry'
import { askConfirm, askText, useSession } from '../../store/session'
import type { Asset, StageCamera } from '../../api/types'
import { clipFrames, keyedFrames as keyedFramesOf, keyframesOf, sampleDoc } from './anim'
import { JOINTS, MANNEQUIN_PRESETS, POSE_NAMES, PROP_PRESETS, SET_PRESETS, type Joint } from './builders'
import { StageEngine } from './engine'
import { viewport, viewportMenu } from './stageCommands'
import { effectiveJoints, st, useStage, type ShotState } from './stageStore'
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
    frameAll: () => st().frameView(null) }
  return w.__loom2Stage
}
if (DEV_HOOKS) devHook()

// ------------------------------------------------------------------ Panel
function LibraryTab() {
  const current = useStage((s) => s.current)
  const stages = useStage((s) => s.stages)
  const meshes = useStage((s) => s.meshes)
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
      {current && <>
        <h4>Figures</h4>
        <div className="lib-grid">{Object.entries(MANNEQUIN_PRESETS).map(([p, m]) => <CommandButton key={p} id={`stage.add.mannequin.${p}`} text label={m.label} />)}</div>
        <h4>Sets</h4>
        <div className="lib-grid">{SET_PRESETS.map((p) => <CommandButton key={p} id={`stage.add.set.${p}`} text label={p} />)}</div>
        <h4>Props</h4>
        <div className="lib-grid">{PROP_PRESETS.map((p) => <CommandButton key={p} id={`stage.add.prop.${p}`} text label={p} />)}</div>
        <h4>Meshes{meshes.length ? ` · ${meshes.length}` : ''}</h4>
        {!meshes.length && <span className="hint">None yet — a Catalogue image's "Make a 3D prop…" (Pixal3D) lands here (P18).</span>}
        <div className="lib-grid">{meshes.slice(0, 24).map((m) => (
          <button key={m.id} className="mesh-card" title={`${m.id} · add to the stage at the viewport's centre`} onClick={() => st().addObject('mesh', null, viewport.centre?.() ?? [0, 0, 0], m.id)}>
            <img src={api.thumbUrl(m.id, 256)} alt="" /><span>prop {m.id.slice(-6)}</span>
          </button>))}</div>
        <p className="hint">Image planes: drop a Catalogue tile on the viewport (it lands where the pointer is). Each card adds at the viewport's centre.</p>
      </>}
    </div>
  )
}

function OutlinerTab() {
  const current = useStage((s) => s.current)
  const selected = useStage((s) => s.selected)
  if (!current) return <span className="hint">Open or make a stage in the Library tab.</span>
  const rename = (id: string, name: string) => void askText({ title: 'Rename', initial: name, placeholder: 'name' }).then((n) => { if (n?.trim()) st().updateObject(id, { name: n.trim() }) })
  return (
    <div className="stage-panel">
      <div className="head"><b>Outliner</b><span className="hint">{current.objects.length} object{current.objects.length === 1 ? '' : 's'}</span></div>
      {!current.objects.length && <span className="hint">Nothing on the stage — add from the Library.</span>}
      {current.objects.map((o) => (
        <div key={o.id} className={`outl-row${selected === o.id ? ' active' : ''}${o.visible ? '' : ' hidden'}`} onClick={() => st().select(o.id)} onDoubleClick={() => st().frameView([o.id])}
          onContextMenu={(e) => { e.preventDefault(); st().select(o.id); showMenu(e, viewportMenu(true)) }}>
          <span className="swatch" style={{ background: `hsl(${(o.colour_id * 137) % 360} 55% 50%)` }} />
          <span className="kind">{o.kind}</span>
          <span className="name" onDoubleClick={(e) => { e.stopPropagation(); rename(o.id, o.name) }}>{o.name}</span>
          <button className="quiet" title={o.visible ? 'Hide' : 'Show'} onClick={(e) => { e.stopPropagation(); st().updateObject(o.id, { visible: !o.visible }) }}>{o.visible ? <Eye size={13} /> : <EyeOff size={13} />}</button>
          <button className="quiet" title={o.locked ? 'Unlock' : 'Lock'} onClick={(e) => { e.stopPropagation(); st().updateObject(o.id, { locked: !o.locked }) }}>{o.locked ? <Lock size={13} /> : <LockOpen size={13} />}</button>
        </div>
      ))}
      <h4>Cameras</h4>
      {current.cameras.map((c) => (
        <div key={c.id} className={`outl-row${current.active_camera === c.id ? ' active' : ''}`} onClick={() => st().setActiveCamera(c.id)}>
          <Camera size={13} /><span className="name">{c.name}</span><span className="meta">{c.focal_mm} mm</span>
        </div>
      ))}
    </div>
  )
}

function CamerasTab() {
  const current = useStage((s) => s.current)
  const view = useStage((s) => s.view)
  const cam = useStage((s) => s.activeCamera())
  if (!current) return <span className="hint">Open or make a stage in the Library tab.</span>
  markUsed('stage.camera.add'); markUsed('stage.camera.setFromView'); markUsed('stage.camera.delete'); markUsed('stage.view.camera'); markUsed('stage.frameAll')
  return (
    <div className="stage-panel">
      <div className="head"><b>Cameras</b><CommandButton id="stage.camera.add" /></div>
      {current.cameras.map((c) => (
        <div key={c.id} className={`outl-row${current.active_camera === c.id ? ' active' : ''}`} onClick={() => st().setActiveCamera(c.id)}
          onDoubleClick={() => void askText({ title: 'Rename camera', initial: c.name }).then((n) => { if (n?.trim()) st().updateCamera(c.id, { name: n.trim() }) })}>
          <Camera size={13} /><span className="name">{c.name}</span><span className="meta">{c.focal_mm} mm</span>
        </div>
      ))}
      {cam && <>
        <h4>{cam.name}</h4>
        <div className="kv"><span>focal</span>
          <span className="focals">{FOCALS.map((f) => <button key={f} className={cam.focal_mm === f ? 'active' : ''} onClick={() => st().updateCamera(cam.id, { focal_mm: f })}>{f}</button>)}
            <input type="number" min={8} max={400} step={1} value={cam.focal_mm} onChange={(e) => st().updateCamera(cam.id, { focal_mm: Math.max(8, Math.min(400, Number(e.target.value) || 35)) })} /> mm</span></div>
        <div className="kv"><span>sensor</span><span>{cam.sensor_mm} mm · frame {current.size.w}×{current.size.h}</span></div>
        <div className="kv"><span>roll</span><input type="number" step={1} value={cam.roll} onChange={(e) => st().updateCamera(cam.id, { roll: Number(e.target.value) || 0 })} /></div>
        <div className="verbs">
          <CommandButton id="stage.view.camera" text label={view === 'camera' ? 'Back to the free view' : 'Look through'} active={view === 'camera'} />
          <CommandButton id="stage.camera.setFromView" text label="Set from view" />
          <CommandButton id="stage.frameAll" text label="Frame all" />
          <CommandButton id="stage.camera.delete" />
        </div>
      </>}
    </div>
  )
}

// ST2 (16 §3d): presets (built-in + the project's saved ones), the pose verbs, the selected joint's angles. While this tab is open the
// viewport shows the joint pickers: click a joint for the rotate gizmo, click a hand / foot handle and drag it (two-bone IK).
function PosesTab() {
  const current = useStage((s) => s.current)
  const o = useStage((s) => s.object(s.selected))
  const joint = useStage((s) => s.selectedJoint)
  const userPoses = useStage((s) => s.userPoses)
  if (!current) return <span className="hint">Open or make a stage in the Library tab.</span>
  markUsed('stage.pose.mirror'); markUsed('stage.pose.reset'); markUsed('stage.pose.save')
  if (!o || o.kind !== 'mannequin') return <div className="stage-panel"><div className="head"><b>Poses</b></div><span className="hint">Select a figure — then click a joint for the rotate gizmo, or drag a hand / foot handle.</span></div>
  const joints = effectiveJoints(o)
  const v = joint ? (joints[joint] ?? [0, 0, 0]) : null
  const setJoint = (nv: number[]) => { if (joint) st().setJoints(o.id, { ...joints, [joint]: nv }) }
  return (
    <div className="stage-panel">
      <div className="head"><b>{o.name}</b><span className="hint">pose · {o.pose?.preset ?? 'stand'}{Object.keys(o.pose?.joints ?? {}).length ? ' (edited)' : ''}</span></div>
      <h4>Presets</h4>
      <div className="lib-grid">{POSE_NAMES.map((p) => <button key={p} className={o.pose?.preset === p && !Object.keys(o.pose?.joints ?? {}).length ? 'active' : ''} onClick={() => st().applyPose(o.id, p)}>{p}</button>)}</div>
      <h4>Saved in this project</h4>
      {!Object.keys(userPoses).length && <span className="hint">None yet — pose the figure and Save pose….</span>}
      <div className="lib-grid">{Object.entries(userPoses).map(([name, def]) => (
        <span key={name} className="pose-card"><button onClick={() => st().applyPose(o.id, def.preset ?? 'stand', def.joints)}>{name}</button>
          <button className="quiet" title="Delete this pose" onClick={() => void askConfirm({ title: `Delete the pose "${name}"?`, okLabel: 'Delete', danger: true }).then((ok) => { if (ok) void st().deletePose(name) })}>×</button></span>
      ))}</div>
      <div className="verbs"><CommandButton id="stage.pose.mirror" text /><CommandButton id="stage.pose.reset" text label="Reset" /><CommandButton id="stage.pose.save" text /></div>
      <h4>Joint</h4>
      <div className="kv"><span>joint</span><select value={joint ?? ''} onChange={(e) => st().selectJoint(e.target.value || null)}><option value="">— click one in the viewport —</option>{JOINTS.map((j) => <option key={j} value={j}>{j}</option>)}</select></div>
      {v && <Vec label="x · y · z °" v={v} onChange={setJoint} step={5} />}
      <p className="hint">Orange spheres are joints (rotate), blue cubes are hands and feet (drag; elbow and shoulder follow). The figure's own transform stays on the Move / Rotate tools.</p>
    </div>
  )
}

// ST3 (16 §3e / §7): the generation form for the blocking — the method (D78: clay reference by default, exact pose as the switch), image 1
// locked to the pass the method takes, the reference deck (D73), the prompt, the size tier and the candidates; the passes render on
// Generate when stale (or by the button), the results land below with lineage to the passes.
function ShotTab() {
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
  const { ref: dropRef, over } = useDropTarget((d) => onlyAssets(d) && shotRefDrop(d, room).ok,
    (d) => { d.items.filter((i) => i.kind === 'asset' && i.media !== 'video').slice(0, room).forEach((i) => st().addShotRef(i.id)) }, (d) => shotRefDrop(d, room))
  markUsed('stage.shot.generate'); markUsed('stage.shot.passes'); markUsed('stage.shot.clearRefs')
  if (!current) return <span className="hint">Open or make a stage in the Library tab.</span>
  const image1 = method?.image1 ?? 'clay'
  const passId = entry?.assets[image1]
  return (
    <div className="stage-panel shot-tab">
      <div className="head"><b>Shot</b><span className="hint">{cam ? `${cam.name} · ${cam.focal_mm} mm` : 'no camera'}</span></div>
      <h4>Method</h4>
      <div className="method-list">
        {caps && Object.entries(caps.methods).map(([id, m]) => (
          <button key={id} className={`method${sh.method === id ? ' active' : ''}`} onClick={() => st().setShot({ method: id })} title={m.hint ?? m.label}>
            <b>{id === 'clay' ? 'Clay reference' : id === 'refcontrol' ? 'Exact pose' : m.label}</b>
            <span>{m.short} · {m.seconds != null ? `≈ ${Math.round(m.seconds)} s` : 'unmeasured'}{m.health === 'missing' ? ' · weights missing' : ''}</span>
            <small>{m.hint}</small>
          </button>
        ))}
        {!caps && <span className="hint">No Stage method in this build.</span>}
      </div>
      <h4>Image 1 · the {image1} pass</h4>
      <div className="pass-row">
        <div className="ref-slot source locked" title={passId ? `the ${image1} pass, rendered at revision ${entry?.revision}` : 'render the passes first'}>
          {passId ? <img src={api.thumbUrl(passId, 256)} alt="" /> : <span className="empty">{image1}</span>}
          <span className="n">1</span>
        </div>
        <div className="pass-side">
          {entry ? <span className="hint">{Object.keys(entry.assets).length} passes · {entry.size.w}×{entry.size.h}{stale ? ` · from revision ${entry.revision}, the scene moved on — re-rendered on Generate` : ' · current'}</span>
            : <span className="hint">No passes yet for this camera — Generate renders them, or:</span>}
          <div className="verbs"><CommandButton id="stage.shot.passes" text label={rendering ? 'Rendering…' : 'Render passes'} /></div>
          {entry && stale && <label className="hint check"><input type="checkbox" checked={sh.use_as_is} onChange={(e) => st().setShot({ use_as_is: e.target.checked })} /> use as is</label>}
        </div>
      </div>
      <h4>References{method ? ` · up to ${method.max_refs}` : ''}</h4>
      <div ref={dropRef} className={`ref-slots shot-refs${over ? ' over' : ''}`}>
        {sh.refs.map((r, i) => (
          <div key={r.asset_id} className="ref-slot" title={`reference image ${i + 2}`}>
            <img src={api.thumbUrl(r.asset_id, 256)} alt="" /><span className="n">{i + 2}</span>
            <button className="quiet x" title="Remove" onClick={() => st().removeShotRef(r.asset_id)}>✕</button>
          </div>
        ))}
        {room > 0 && <div className="ref-slot" title="drop a Catalogue tile here"><span className="empty">{sh.refs.length + 2}</span></div>}
      </div>
      {sh.refs.map((r, i) => <div key={r.asset_id} className="kv"><span>image {i + 2}</span><input value={r.note ?? ''} placeholder="shows … (one phrase)" onChange={(e) => st().setShot({ refs: sh.refs.map((x) => (x.asset_id === r.asset_id ? { ...x, note: e.target.value } : x)) })} /></div>)}
      {sh.method === 'refcontrol' && !sh.refs.length && <p className="disabled-why">Exact pose needs one reference image (image 2): drop a Catalogue tile on the deck.</p>}
      <h4>Prompt</h4>
      <textarea className="shot-prompt" rows={3} value={sh.prompt_text} placeholder="what the scene is — after the method's own sentence about image 1" onChange={(e) => st().setShot({ prompt_text: e.target.value })} />
      <div className="kv"><span>size</span><span className="segmented"><button className={sh.tier === 'draft' ? 'active' : ''} onClick={() => st().setShot({ tier: 'draft' })}>Draft</button><button className={sh.tier === 'full' ? 'active' : ''} onClick={() => st().setShot({ tier: 'full' })}>Full</button><span className="hint"> {w}×{h}</span></span></div>
      <div className="kv"><span>candidates</span><span className="angle-count"><button onClick={() => st().setShot({ count: Math.max(1, sh.count - 1) })} disabled={sh.count <= 1}>−</button><span>{sh.count}</span><button onClick={() => st().setShot({ count: Math.min(4, sh.count + 1) })} disabled={sh.count >= 4}>+</button></span></div>
      {pv?.params?.prompt ? <p className="hint prompt-preview">{String(pv.params.prompt)}</p> : null}
      {err && <p className="disabled-why">{err}</p>}
      {pv && pv.missing.length > 0 && <p className="disabled-why">Weights missing for this method: {pv.missing.map((m) => m.model_id).join(', ')} — Models › Fetch.</p>}
      <h4>Results{stills.length ? ` · ${stills.length}` : ''}</h4>
      {!stills.length && <span className="hint">None yet — the shots of this stage land here and in the Catalogue (lineage: the pass and the references).</span>}
      <div className="shot-results">{stills.slice(0, 12).map((a) => <img key={a.id} className={`shot-thumb${shotStart === a.id ? ' start' : ''}`} src={api.thumbUrl(a.id, 256)} alt="" title={`${a.model_id ?? ''} · seed ${a.seed ?? ''} — click: the clip starts from this shot`} onClick={() => st().setShotStart(shotStart === a.id ? null : a.id)} />)}</div>
      <ClipSection clips={clips} />
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
  const clipCap = useSession((s) => s.capabilities?.stage?.clip)
  const [gw, gh] = st().guideSize()
  const n = clipFrames(current.range.start, current.range.end, clipCap?.frame_step ?? 8)
  const stale = !!g && (g.range.start !== current.range.start || g.frames !== n || current.revision > g.revision + 1)
  markUsed('stage.clip.guide'); markUsed('stage.clip.animate')
  return (
    <div className="clip-section">
      <h4>Clip · frames {current.range.start}–{current.range.end}</h4>
      {!clipCap && <span className="hint">No clip model in this build (LTX-2.3 with its IC-LoRA is full-variant).</span>}
      <div className="kv"><span>guide</span><span className="segmented"><button className={kind === 'depth' ? 'active' : ''} onClick={() => st().setGuideKind('depth')} title="the depth sequence (E11: the pose followed 4/5)">Depth</button><button className={kind === 'pose' ? 'active' : ''} onClick={() => st().setGuideKind('pose')} title="the pose sequence (E11: 3/5)">Pose</button></span></div>
      <div className="guide-state">
        {rendering && rendered ? `rendering ${rendered.done} / ${rendered.total || n}…` : g ? `${kind} sequence · ${g.frames} frames · ${g.size.w}×${g.size.h} · ${g.fps} fps${stale ? ' · from an earlier range or revision — render again' : ' · current'}` : `no ${kind} sequence yet · ${n} frames at ${gw}×${gh} (8n + 1 for the clip model)`}
      </div>
      <div className="verbs"><CommandButton id="stage.clip.guide" text label={rendering ? 'Rendering…' : 'Render sequence'} /><CommandButton id="stage.clip.animate" text label="Animate ▶" /></div>
      {!shotStart && <p className="disabled-why">Click one of the results above to start the clip from it.</p>}
      {clipCap && <p className="hint">{clipCap.label} · ≈ {clipCap.seconds != null ? Math.round(clipCap.seconds) : '?'} s for 121 frames (E11){clipCap.health === 'missing' ? ' · weights missing — Models › Fetch' : ''}</p>}
      {clips.length > 0 && <><h4>Clips · {clips.length}</h4>
        <div className="clip-results">{clips.slice(0, 9).map((a) => <span key={a.id} className="clip-thumb"><img className="shot-thumb" src={api.thumbUrl(a.id, 256)} alt="" title={`${a.frames ?? '?'} frames · ${a.model_id ?? ''}`} /><span className="n">{a.frames ?? '?'} f</span></span>)}</div></>}
    </div>
  )
}

export function Panel({ tab }: { tab: string }) {
  const project = useSession((s) => s.project)
  useEffect(() => { if (project?.open) { void st().load(); void st().loadPoses(); void st().loadMeshes() } }, [project?.path]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!project?.open) return <span className="hint">Open or create a project to begin.</span>
  if (tab === 'outliner') return <OutlinerTab />
  if (tab === 'cameras') return <CamerasTab />
  if (tab === 'poses') return <PosesTab />
  if (tab === 'shot') return <ShotTab />
  return <LibraryTab />
}

export function PrimaryAction() {
  const saving = useStage((s) => s.saving)
  const current = useStage((s) => s.current)
  const rendering = useStage((s) => s.rendering)
  const pv = useStage((s) => s.shotPreview)
  const err = useStage((s) => s.shotPreviewError)
  const count = useStage((s) => s.shot.count)
  const cam = useStage((s) => s.activeCamera())
  const { active: tab } = useSuiteRail()
  markUsed('stage.new')
  if (!current) return <div><button className="primary" onClick={() => runCommand('stage.new')}>New stage…</button></div>
  if (tab === 'shot') {                                                                                       // ST3: the verb and its estimate
    const missing = pv?.missing ?? []
    const reason = !cam ? 'no camera' : rendering ? 'rendering the passes…' : err ? err : !pv ? 'preparing…' : missing.length ? `weights missing: ${missing.map((m) => m.model_id).join(', ')}` : pv.estimate.vram_fit === 'over' ? 'VRAM estimate exceeds the budget' : null
    return (
      <div>
        <button className="primary" disabled={!!reason} onClick={() => runCommand('stage.shot.generate')} title="Render the passes if they are stale, then queue the shot (Ctrl+Enter)">Generate{count > 1 ? ` ×${count}` : ''} ▶</button>
        <div className="estimate">{reason ? <span style={{ color: 'var(--fg3)' }}>{reason}</span> : <><span className={`dot ${pv?.estimate.vram_fit ?? 'ok'}`} />≈ {Math.round((pv?.estimate.seconds ?? 0) * count)} s · {String(pv?.params?.label ?? '')}</>}</div>
      </div>
    )
  }
  return <div className="estimate"><span className={`dot ${saving ? 'tight' : 'ok'}`} />{saving ? 'saving…' : `saved · revision ${current.revision}`}</div>
}

// ------------------------------------------------------------------ Strip
export function Strip() {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (useSession.getState().ui.suite === 'stage') handleKeyFor('stage', e) }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [])
  const view = useStage((s) => s.view)
  const guides = useStage((s) => s.guides)
  const current = useStage((s) => s.current)
  if (!current) return null
  return (
    <div className="stage-strip-wrap">
      <div className="stage-strip">
        <CommandRow ids={['stage.view.free', 'stage.view.camera']} active={view === 'camera' ? 'stage.view.camera' : 'stage.view.free'} labels={{ 'stage.view.free': 'free', 'stage.view.camera': 'camera' }} />
        <CommandButton id="stage.guides" active={guides} />
        <CommandButton id="stage.frameAll" />
        <span className="spacer" />
        <span className="hint">{current.name} · {current.size.w}×{current.size.h}</span>
      </div>
      <Timeline />
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
  markUsed('stage.anim.play'); markUsed('stage.anim.prev'); markUsed('stage.anim.next'); markUsed('stage.anim.prevKey'); markUsed('stage.anim.nextKey'); markUsed('stage.anim.keyCamera'); markUsed('stage.anim.keyObject'); markUsed('stage.anim.removeKey'); markUsed('stage.anim.setStart'); markUsed('stage.anim.setEnd')
  return (
    <div className="stage-timeline" onPointerDown={(e) => e.stopPropagation()}>
      <CommandRow ids={['stage.anim.prevKey', 'stage.anim.prev', 'stage.anim.play', 'stage.anim.next', 'stage.anim.nextKey']} active={playing ? 'stage.anim.play' : undefined} />
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
  const poseMode = useSuiteRail().active === 'poses'                                   // ST2: the Poses tab shows the joint pickers
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
      onPosed: (id, joints) => st().setJoints(id, joints),
      onMeshThumb: (assetId, view) => void st().uploadMeshThumbnail(assetId, view),
    })
    engineRef.current = engine
    viewport.centre = () => engine.centre(); viewport.freePose = () => engine.freePose(); viewport.frame = (ids) => engine.frame(ids)
    useStage.setState({ passRenderer: (cam, w, h) => engine.renderPasses(cam, w, h), sequenceRenderer: (fr, w, h, kind, restore, on) => engine.renderSequence(fr, w, h, kind, restore, on) })   // ST3 / ST4
    if (DEV_HOOKS) Object.assign(devHook(), { screenOf: (at: string) => engine.screenOf(at as Joint), meshes: () => ({ loaded: [...engine.meshesLoaded], failed: Object.fromEntries(engine.meshesFailed) }) })   // the smoke test aims the mouse at joints and handles; P18 asks which props loaded
    const ro = new ResizeObserver(() => { const r = host.getBoundingClientRect(); engine.resize(Math.round(r.width), Math.round(r.height)); setRect({ ...engine.frameRect() }) })
    ro.observe(host)
    engine.start()
    return () => { ro.disconnect(); engine.dispose(); engineRef.current = null; viewport.centre = undefined; viewport.freePose = undefined; viewport.frame = undefined; useStage.setState({ passRenderer: null, sequenceRenderer: null }) }
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
  useEffect(() => { engineRef.current?.select(selected) }, [selected])
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
    const p = eng.pick(e.clientX, e.clientY)
    if (p.joint && p.id) { st().selectJoint(p.joint) }                                 // the rotate gizmo moves to the joint (FK)
    else if (p.ik && p.id) { st().selectJoint(null); eng.startIk(p.id, p.ik) }         // a translate handle on the hand / foot (IK)
    else st().select(p.id)
  }
  const onMenu = (e: React.MouseEvent) => {
    e.preventDefault()
    const eng = engineRef.current
    const id = eng ? eng.pick(e.clientX, e.clientY).id : null
    if (id) st().select(id)
    showMenu(e, viewportMenu(!!id))
  }
  markUsed('stage.tool.select'); markUsed('stage.tool.move'); markUsed('stage.tool.rotate'); markUsed('stage.tool.scale'); markUsed('stage.snap'); markUsed('stage.undo'); markUsed('stage.redo')
  return (
    <div ref={(el) => { (hostRef as React.MutableRefObject<HTMLDivElement | null>).current = el; dropRef(el) }} className={`stage-host${over ? ' over' : ''}`}
      onPointerDown={onDown} onPointerUp={onUp} onPointerMove={(e) => { lastPointer.current = { x: e.clientX, y: e.clientY } }} onContextMenu={onMenu}>
      <canvas ref={canvasRef} className="stage-canvas" />
      {current && <div className="gizmo-bar" onPointerDown={(e) => e.stopPropagation()} onPointerUp={(e) => e.stopPropagation()}>
        <CommandRow ids={['stage.tool.select', 'stage.tool.move', 'stage.tool.rotate', 'stage.tool.scale', 'gap', 'stage.snap', 'gap', 'stage.undo', 'stage.redo']} active={`stage.tool.${tool}`} />
        {snap && <span className="hint">snap</span>}
      </div>}
      {current && view === 'camera' && rect && guides && <div className="frame-guides" style={{ left: rect.x, top: rect.y, width: rect.w, height: rect.h }}><i className="thirds" /><i className="centre" /></div>}
      {current && view === 'camera' && <div className="view-tag">camera view · {st().activeCamera()?.name} · {st().activeCamera()?.focal_mm} mm</div>}
      {current && !current.objects.length && <div className="stage-empty"><div>Empty stage — add a set and a figure from the Library, or drop a Catalogue image.<div className="quick-cards"><CommandButton id="stage.add.set.room" text /><CommandButton id="stage.add.mannequin.adult" text /></div></div></div>}
    </div>
  )
}

export function Stage() {
  const project = useSession((s) => s.project)
  const current = useStage((s) => s.current)
  if (!project?.open) return <div className="placeholder"><div><h2>Stage</h2>open or create a project to begin</div></div>
  if (!current) return <div className="placeholder"><div><h2>Stage</h2>a blocking in 3D: a set, figures, props and cameras at the project size<div className="quick-cards"><CommandButton id="stage.new" text label="New stage…" /></div></div></div>
  return <Viewport />
}

// ------------------------------------------------------------------ Inspector
function Vec({ label, v, onChange, step = 0.05 }: { label: string; v: number[]; onChange: (v: number[]) => void; step?: number }) {
  return (
    <div className="kv"><span>{label}</span><span className="vec">{v.map((x, i) => <input key={i} type="number" step={step} value={num(x)} onChange={(e) => { const n = [...v]; n[i] = Number(e.target.value) || 0; onChange(n) }} />)}</span></div>
  )
}

export function Inspector() {
  const current = useStage((s) => s.current)
  const o = useStage((s) => s.object(s.selected))
  const cam = useStage((s) => s.activeCamera())
  const saving = useStage((s) => s.saving)
  const { active: tab } = useSuiteRail()
  if (!current) return <span className="hint">No stage open.</span>
  if (o) {
    const t = o.transform
    return (
      <div className="stage-insp">
        <h4>{o.name} <span className="hint">· {o.kind}{o.preset ? ` · ${o.preset}` : ''}</span></h4>
        <Vec label="position" v={t.pos} onChange={(pos) => st().setTransform(o.id, { ...t, pos })} />
        <Vec label="rotation" v={t.rot} onChange={(rot) => st().setTransform(o.id, { ...t, rot })} step={1} />
        <Vec label="scale" v={t.scale} onChange={(scale) => st().setTransform(o.id, { ...t, scale })} step={0.05} />
        {o.kind === 'mannequin' && <div className="kv"><span>pose</span><span><select value={o.pose?.preset ?? 'stand'} onChange={(e) => st().applyPose(o.id, e.target.value)}>{POSE_NAMES.map((p) => <option key={p} value={p}>{p}</option>)}</select>{Object.keys(o.pose?.joints ?? {}).length ? <span className="hint"> edited</span> : null}</span></div>}
        {o.kind === 'plane' && <div className="kv"><span>faces camera</span><input type="checkbox" checked={o.billboard} onChange={(e) => st().updateObject(o.id, { billboard: e.target.checked })} /></div>}
        <div className="kv"><span>parent</span><select value={o.parent ?? ''} onChange={(e) => st().updateObject(o.id, { parent: e.target.value || null })}><option value="">— none —</option>{current.objects.filter((x) => x.id !== o.id).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></div>
        <div className="verbs"><CommandRow ids={['stage.object.duplicate', 'stage.object.lock', 'stage.object.hide', 'stage.frameSel', 'stage.object.reset', 'stage.object.delete']} /></div>
      </div>
    )
  }
  if (tab === 'cameras' && cam) return <div className="stage-insp"><h4>{cam.name}</h4><Vec label="position" v={cam.pos} onChange={(pos) => st().updateCamera(cam.id, { pos })} /><Vec label="target" v={cam.target} onChange={(target) => st().updateCamera(cam.id, { target })} /><div className="kv"><span>focal</span><span>{cam.focal_mm} mm on {cam.sensor_mm} mm</span></div><div className="verbs"><CommandRow ids={['stage.camera.setFromView', 'stage.view.camera']} /></div></div>
  return (
    <div className="stage-insp">
      <h4>{current.name} <span className="hint">{saving ? '· saving…' : `· revision ${current.revision}`}</span></h4>
      <div className="kv"><span>frame</span><span>{current.size.w}×{current.size.h} @ {current.size.fps} fps (the project format)</span></div>
      <div className="kv"><span>contents</span><span>{current.objects.length} objects · {current.cameras.length} cameras</span></div>
      <div className="verbs"><CommandRow ids={['stage.rename', 'stage.delete']} /></div>
      <p className="hint">Select an object in the viewport or the Outliner to edit it. Add from the Library tab or the viewport's right-click menu.</p>
    </div>
  )
}

