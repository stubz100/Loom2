// P13 / ST1 (D81): the Stage suite's parts (16; StageSuite.ts registers them) — Panel (Library · Outliner · Cameras), Strip (view, guides, frame), the viewport Stage with
// its floating gizmo bar and the framing rectangle, the Inspector (object · camera · stage). Mouse-first (D32): every verb is a
// button or a menu entry; keys are accelerators. Keep-alive (D69): the engine pauses while the suite is hidden and keeps its view.
import { Camera, Eye, EyeOff, Lock, LockOpen } from 'lucide-react'
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { CommandButton, CommandRow } from '../../frame/CommandButton'
import { handleKeyFor, markUsed, runCommand } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { onlyAssets, useDropTarget } from '../../frame/drag'
import { useStageActive } from '../../frame/stageKeep'
import { useSuiteRail } from '../../frame/suiteRegistry'
import { askText, useSession } from '../../store/session'
import { MANNEQUIN_PRESETS, POSE_NAMES, PROP_PRESETS, SET_PRESETS } from './builders'
import { StageEngine } from './engine'
import { viewport, viewportMenu } from './stageCommands'
import { st, useStage } from './stageStore'
import './stage.css'

const FOCALS = [24, 35, 50, 85]
const num = (v: number) => +v.toFixed(2)

// ------------------------------------------------------------------ Panel
function LibraryTab() {
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
      {current && <>
        <h4>Figures</h4>
        <div className="lib-grid">{Object.entries(MANNEQUIN_PRESETS).map(([p, m]) => <CommandButton key={p} id={`stage.add.mannequin.${p}`} text label={m.label} />)}</div>
        <h4>Sets</h4>
        <div className="lib-grid">{SET_PRESETS.map((p) => <CommandButton key={p} id={`stage.add.set.${p}`} text label={p} />)}</div>
        <h4>Props</h4>
        <div className="lib-grid">{PROP_PRESETS.map((p) => <CommandButton key={p} id={`stage.add.prop.${p}`} text label={p} />)}</div>
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
        <div key={o.id} className={`outl-row${selected === o.id ? ' active' : ''}${o.visible ? '' : ' hidden'}`} onClick={() => st().select(o.id)} onDoubleClick={() => st().frame([o.id])}
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

export function Panel({ tab }: { tab: string }) {
  const project = useSession((s) => s.project)
  useEffect(() => { if (project?.open) void st().load() }, [project?.path]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!project?.open) return <span className="hint">Open or create a project to begin.</span>
  if (tab === 'outliner') return <OutlinerTab />
  if (tab === 'cameras') return <CamerasTab />
  return <LibraryTab />
}

export function PrimaryAction() {
  const saving = useStage((s) => s.saving)
  const current = useStage((s) => s.current)
  markUsed('stage.new')
  if (!current) return <div><button className="primary" onClick={() => runCommand('stage.new')}>New stage…</button></div>
  return <div className="estimate"><span className={`dot ${saving ? 'tight' : 'ok'}`} />{saving ? 'saving…' : `saved · revision ${current.revision}`} · passes come with ST3</div>
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
    <div className="stage-strip">
      <CommandRow ids={['stage.view.free', 'stage.view.camera']} active={view === 'camera' ? 'stage.view.camera' : 'stage.view.free'} labels={{ 'stage.view.free': 'free', 'stage.view.camera': 'camera' }} />
      <CommandButton id="stage.guides" active={guides} />
      <CommandButton id="stage.frameAll" />
      <span className="spacer" />
      <span className="hint">{current.name} · {current.size.w}×{current.size.h}</span>
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
  const [rect, setRect] = useState<{ x: number; y: number; w: number; h: number } | null>(null)
  const { ref: dropRef, over } = useDropTarget((d) => onlyAssets(d) && d.items.some((i) => i.media !== 'video') && !!useStage.getState().current,
    (d) => { const id = d.items.find((i) => i.kind === 'asset' && i.media !== 'video')?.id; const e = engineRef.current; const p = lastPointer.current; if (id && e) st().addObject('plane', null, (p ? e.place(p.x, p.y) : null) ?? e.centre(), id) },
    (d) => (d.items.some((i) => i.kind === 'asset' && i.media !== 'video') ? { ok: true, label: 'Place as an image plane' } : { ok: false, reason: 'Only images become planes' }))
  // the engine: one per mounted viewport (kept alive with the suite, D69)
  useEffect(() => {
    const canvas = canvasRef.current, host = hostRef.current
    if (!canvas || !host) return
    const engine = new StageEngine(canvas, {
      onPick: (id) => st().select(id),
      onTransformed: (id, t) => st().setTransform(id, t),
    })
    engineRef.current = engine
    viewport.centre = () => engine.centre(); viewport.freePose = () => engine.freePose(); viewport.frame = (ids) => engine.frame(ids)
    const ro = new ResizeObserver(() => { const r = host.getBoundingClientRect(); engine.resize(Math.round(r.width), Math.round(r.height)); setRect({ ...engine.frameRect() }) })
    ro.observe(host)
    engine.start()
    return () => { ro.disconnect(); engine.dispose(); engineRef.current = null; viewport.centre = undefined; viewport.freePose = undefined; viewport.frame = undefined }
  }, [])
  useEffect(() => { const e = engineRef.current; if (!e) return; if (active) e.start(); else e.stop() }, [active])
  useEffect(() => { const e = engineRef.current; if (e && current) { e.setAspect(current.size.w / current.size.h); e.sync(current); setRect({ ...e.frameRect() }) } }, [current])
  useEffect(() => { engineRef.current?.select(selected) }, [selected])
  useEffect(() => { engineRef.current?.setTool(tool, snap) }, [tool, snap])
  useEffect(() => { const e = engineRef.current; if (!e) return; e.setView(view); if (view === 'camera' && current) e.sync(current) }, [view]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (frameReq.n) engineRef.current?.frame(frameReq.ids) }, [frameReq])
  const down = useRef<{ x: number; y: number; t: number } | null>(null)
  const onDown = (e: ReactPointerEvent) => { if (e.button === 0) down.current = { x: e.clientX, y: e.clientY, t: Date.now() } }
  const onUp = (e: ReactPointerEvent) => {
    const d = down.current; down.current = null
    const eng = engineRef.current
    if (!d || !eng || e.button !== 0 || Math.hypot(e.clientX - d.x, e.clientY - d.y) > 4 || eng.gizmo.dragging) return
    st().select(eng.pick(e.clientX, e.clientY))
  }
  const onMenu = (e: React.MouseEvent) => {
    e.preventDefault()
    const eng = engineRef.current
    const id = eng ? eng.pick(e.clientX, e.clientY) : null
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
        {o.kind === 'mannequin' && <div className="kv"><span>pose</span><select value={o.pose?.preset ?? 'stand'} onChange={(e) => st().updateObject(o.id, { pose: { preset: e.target.value, joints: {} } })}>{POSE_NAMES.map((p) => <option key={p} value={p}>{p}</option>)}</select></div>}
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

