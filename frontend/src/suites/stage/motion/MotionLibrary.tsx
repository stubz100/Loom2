// CA1 (proto01_animate 01 step 5): the motion library in Animate's Motion section — the starter set (CC0) and the local folder's files,
// each opened to its clips; a picked clip plays on a dummy in the preview (its own small canvas); trim, speed and in-place; *Apply at the
// playhead* puts it on the selected figure as keys (stage.motion.apply). Presets and keys by hand stay below (PosesTab).
import { applyTemplate, importMotion, removeTemplate, templateToLibrary, useTemplates } from '../blockEdit'
import type { AnimationTemplate } from '../blocks'
import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { CommandButton } from '../../../frame/CommandButton'
import { markUsed } from '../../../frame/commands'
import { useSession } from '../../../store/session'
import { applyPose, clay, mannequin, POSES } from '../builders'
import { useStage } from '../stageStore'
import { retargetClip, type MotionClip, type MotionFile } from './library'
import { singleClip, useMotion, type MotionFilter } from './motionStore'
import type { Retargeted } from './retarget'

const secs = (s: number) => (s ? `${s.toFixed(1)} s` : '')

export function MotionLibrary() {
  const m = useMotion()
  const project = useSession((s) => s.project)
  const fig = useStage((s) => { const o = s.object(s.selected); return o && o.kind === 'mannequin' ? o : null })
  useEffect(() => { if (project?.open && !m.loaded) void m.refresh() }, [project?.path])   // eslint-disable-line react-hooks/exhaustive-deps
  markUsed('stage.motion.apply'); markUsed('stage.motion.refresh')
  const files = useMemo(() => m.files.filter((f) => (m.filter === 'all' || f.source === m.filter) && (!m.q || f.name.toLowerCase().includes(m.q.toLowerCase()) ||
    (Array.isArray(m.clips[f.id]) && (m.clips[f.id] as MotionClip[]).some((c) => c.name.toLowerCase().includes(m.q.toLowerCase()))))), [m.files, m.filter, m.q, m.clips])
  const p = m.picked
  return (
    <div className="stage-panel motion-lib">
      <div className="head"><b>Motion library</b><span className="hint">{m.files.length} file{m.files.length === 1 ? '' : 's'}</span><CommandButton id="stage.motion.refresh" size={13} /></div>
      <div className="motion-bar">
        <span className="segmented" role="group" aria-label="motion source">
          {(['all', 'starter', 'local', 'mine'] as MotionFilter[]).map((k) => <button key={k} type="button" className={m.filter === k ? 'active' : ''} onClick={() => m.set({ filter: k })}>{k === 'starter' ? 'Starter (CC0)' : k === 'local' ? 'Local' : k === 'mine' ? 'Mine' : 'All'}</button>)}
        </span>
        {m.filter === 'local' && <button type="button" className="link" title="Copy a .glb, .gltf or .fbx into the local motion folder (U5)" disabled={!m.localDir} onClick={() => void importMotion(() => m.refresh())}>Import…</button>}
        <input type="search" aria-label="search the motion library" placeholder="search clips" value={m.q} onChange={(e) => m.set({ q: e.target.value })} />
      </div>
      {m.error && <span className="hint error">{m.error}</span>}
      {m.loaded && !m.files.length && <span className="hint">No motion files found — the starter set lives in &lt;models root&gt;/motion; your own clips go in Settings › Motion.</span>}
      {m.loaded && m.filter !== 'starter' && !m.localDir && <span className="hint">No local folder yet: set one in Settings › Motion for your own downloads (Mixamo FBX at 24 fps, without skin).</span>}
      {m.filter === 'mine' ? <MineList q={m.q} fig={fig?.name ?? null} /> : <div className="motion-list" role="list">
        {files.map((f) => <FileRow key={f.id} f={f} />)}
      </div>}
      {p && (
        <div className="motion-picked">
          <MotionPreview clip={p} start={m.start} end={m.end} speed={m.speed} inPlace={m.inPlace} />
          <div className="kv"><span>clip</span><span>{p.name}{p.duration ? ` · ${secs(p.duration)}` : ''} <span className="hint">({p.file.source === 'starter' ? 'CC0' : 'your file'})</span></span></div>
          <div className="kv"><span>trim</span><span>
            <input type="number" aria-label="trim start (s)" min={0} step={0.1} value={m.start} onChange={(e) => m.set({ start: Math.max(0, Number(e.target.value) || 0) })} /> –{' '}
            <input type="number" aria-label="trim end (s)" min={0} step={0.1} value={m.end ?? ''} placeholder="end" onChange={(e) => m.set({ end: e.target.value === '' ? null : Math.max(0, Number(e.target.value)) })} /> s</span></div>
          <div className="kv"><span>speed</span><span><input type="range" aria-label="speed" min={0.25} max={2} step={0.05} value={m.speed} onChange={(e) => m.set({ speed: Number(e.target.value) })} /> ×{m.speed.toFixed(2)}</span></div>
          <label className="hint check"><input type="checkbox" checked={m.lock} onChange={(e) => m.set({ lock: e.target.checked })} /> foot lock (the planted foot stays put; an in-place walk travels)</label>
          <label className="hint check" title="Each step's planted foot set on the floor, a foot still under it bent up — the clip fitted to this figure's legs (D141)"><input type="checkbox" checked={m.ground} onChange={(e) => m.set({ ground: e.target.checked })} /> feet on the floor</label>
          {fig?.path && fig.path.length >= 2
            ? <label className="hint check"><input type="checkbox" checked={m.alongPath} onChange={(e) => m.set({ alongPath: e.target.checked })} /> along {fig.name}'s path ({fig.path.length} points; a loop repeats to its end)</label>
            : <label className="hint check"><input type="checkbox" checked={m.inPlace} onChange={(e) => m.set({ inPlace: e.target.checked })} /> in place (no travel)</label>}
          <div className="kv"><span>blend in</span><span><input type="number" aria-label="blend in frames" min={0} max={24} step={1} value={m.blend} onChange={(e) => m.set({ blend: Math.max(0, Math.min(24, Number(e.target.value) || 0)) })} /> frames from what the figure was doing</span></div>
          {fig && <div className="verbs"><CommandButton id="stage.tool.path" text label={fig.path?.length ? 'Add to the path (click the floor)' : 'Draw a path (click the floor)'} /><CommandButton id="stage.path.clear" text /></div>}
          <div className="verbs"><CommandButton id="stage.motion.apply" text label={m.applying ? 'Applying…' : fig ? `Apply to ${fig.name} at the playhead` : 'Apply at the playhead (select a figure)'} /></div>
        </div>
      )}
    </div>
  )
}

/** U5c (G9): *Mine* — the project's animations and the author's library, each applied as a block to the selected figure at the playhead. */
function MineList({ q, fig }: { q: string; fig: string | null }) {
  const t = useTemplates()
  useEffect(() => { if (!t.loaded) void t.load() }, [])   // eslint-disable-line react-hooks/exhaustive-deps
  const want = q.trim().toLowerCase()
  const shown = (xs: AnimationTemplate[]) => xs.filter((x) => !want || x.name.toLowerCase().includes(want))
  const inLib = new Set(t.library.map((x) => x.id))
  const row = (x: AnimationTemplate, from: 'project' | 'library') => (
    <div key={`${from}:${x.id}`} className="motion-clip mine" role="listitem" data-id={x.id}>
      <span>{x.name}<small> · {(x.frames / Math.max(1, x.fps)).toFixed(1)} s</small></span>
      <span className="verbs">
        <button type="button" className="link" disabled={!fig} title={fig ? `A clip block on ${fig} at the playhead` : 'Select a figure'} onClick={() => void applyTemplate(x)}>Apply</button>
        {from === 'project' && !inLib.has(x.id) && <button type="button" className="link" title="Every project has it under Mine" onClick={() => void templateToLibrary(x)}>To my library</button>}
        <button type="button" className="link danger" title={from === 'project' ? 'Remove it from the project' : 'Remove it from your library'} onClick={() => void removeTemplate(x, from)}>Remove</button>
      </span>
    </div>)
  if (!t.loaded) return <span className="hint">Reading…</span>
  if (!t.items.length && !t.library.length) return <span className="hint">None yet — a clip's or a track's right-click has Save as animation…</span>
  return (
    <div className="motion-list" role="list">
      {shown(t.items).length > 0 && <><b className="motion-sub">This project</b>{shown(t.items).map((x) => row(x, 'project'))}</>}
      {shown(t.library).length > 0 && <><b className="motion-sub">My library</b>{shown(t.library).map((x) => row(x, 'library'))}</>}
    </div>
  )
}

function FileRow({ f }: { f: MotionFile }) {
  const open = useMotion((s) => !!s.open[f.id])
  const clips = useMotion((s) => s.clips[f.id])
  const picked = useMotion((s) => s.picked)
  const isPicked = (c: MotionClip) => picked?.file.id === c.file.id && picked.name === c.name
  if (f.ext === 'fbx') {                                                       // a Mixamo download: one clip, named after its file
    const c = singleClip(f)
    return <button type="button" role="listitem" className={`motion-clip${isPicked(c) ? ' active' : ''}`} onClick={() => useMotion.getState().pick(c)} title={`${f.rel} · ${f.licence}`}>{f.name}<small>local · fbx</small></button>
  }
  return (
    <div className="motion-file" role="listitem">
      <button type="button" className="motion-file-head" aria-expanded={open} onClick={() => useMotion.getState().toggle(f)} title={`${f.rel} · ${f.licence}`}>
        {open ? '▾' : '▸'} {f.name}<small>{f.source === 'starter' ? 'CC0' : 'local'} · {(f.bytes / 2 ** 20).toFixed(1)} MB</small>
      </button>
      {open && (clips === 'loading' || !clips ? <span className="hint">loading…</span>
        : 'error' in (clips as object) ? <span className="hint error">{(clips as { error: string }).error}</span>
        : (clips as MotionClip[]).length === 0 ? <span className="hint">no clips in this file (a mannequin only)</span>
        : <div className="motion-clips">{(clips as MotionClip[]).map((c) => (
          <button key={c.name} type="button" className={`motion-clip${isPicked(c) ? ' active' : ''}`} onClick={() => useMotion.getState().pick(c)} title={c.rig ? `rig: ${c.rig}` : 'an unknown rig'}>
            {c.name}<small>{secs(c.duration)}{c.rootMotion ? ' · moves' : ''}</small>
          </button>))}</div>)}
    </div>
  )
}

/** The picked clip on the default dummy, looping in a small canvas of its own (the stage's viewport is not touched until Apply). */
function MotionPreview({ clip, start, end, speed, inPlace }: { clip: MotionClip; start: number; end: number | null; speed: number; inPlace: boolean }) {
  const host = useRef<HTMLDivElement>(null)
  const [r, setR] = useState<Retargeted | { error: string } | null>(null)
  useEffect(() => {
    let live = true
    retargetClip(clip, { fps: 24, start, end: end ?? undefined, speed, inPlace, hip: 0.91 }).then((x) => { if (live) setR(x) }).catch((e) => { if (live) setR({ error: e instanceof Error ? e.message : String(e) }) })
    return () => { live = false }
  }, [clip, start, end, speed, inPlace])
  useEffect(() => {
    const mount = host.current
    if (!mount || !r || 'error' in r) return
    const canvas = document.createElement('canvas')                                    // U0 (F34): a fresh canvas per mount, as the viewport's — the cleanup force-loses its context
    mount.appendChild(canvas)
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true })
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1))
    renderer.setSize(canvas.clientWidth || 240, canvas.clientHeight || 150, false)
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x2a2a2e)
    scene.add(new THREE.HemisphereLight(0xffffff, 0x555555, 1.6))
    const key = new THREE.DirectionalLight(0xffffff, 1.4); key.position.set(2, 4, 3); scene.add(key)
    scene.add(new THREE.GridHelper(20, 40, 0x555555, 0x3a3a3a))
    const mat = clay()
    const fig = mannequin(mat, POSES.stand)
    const holder = new THREE.Group(); holder.add(fig.root); scene.add(holder)
    const cam = new THREE.PerspectiveCamera(35, (canvas.clientWidth || 240) / (canvas.clientHeight || 150), 0.05, 100)
    let raf = 0, i = 0, last = 0
    const frameMs = 1000 / r.fps
    const tick = (now: number) => {
      raf = requestAnimationFrame(tick)
      if (now - last < frameMs) return
      last = now
      const f = r.frames[i % r.frames.length]
      i++
      applyPose(fig.joints, POSES.stand, f.joints)
      holder.position.set(f.offset[0], f.offset[1], f.offset[2])
      cam.position.set(holder.position.x + 2.2, 1.4, holder.position.z + 3.6)          // a three-quarter view that follows the figure
      cam.lookAt(holder.position.x, 0.9, holder.position.z)
      renderer.render(scene, cam)
    }
    raf = requestAnimationFrame(tick)
    return () => { cancelAnimationFrame(raf); renderer.dispose(); renderer.forceContextLoss(); mat.dispose(); canvas.remove() }
  }, [r])
  return (
    <div className="motion-preview">
      <div ref={host} role="img" aria-label={`preview of ${clip.name}`} />
      {!r && <span className="hint">retargeting…</span>}
      {r && 'error' in r && <span className="hint error">{r.error}</span>}
      {r && !('error' in r) && <span className="hint">{r.frames.length} frames at {r.fps} fps · {r.rig}{r.travel > 0.05 ? ` · ${r.travel.toFixed(2)} m` : ''}</span>}
    </div>
  )
}
