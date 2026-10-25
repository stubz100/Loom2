// CS2 (proto01_UIcast 03 §3.2, 06 §2.4; D136 U6/U7/U17): the skeleton bench — Cast's Skeleton view of a character, lazily loaded with the
// stage's code. Two panes (D140: the figure pane folded into the reference's — the shell is made front-on from this picture):
//   the reference   SDPose's points (white rings) and the figure's markers (blue dots) over the animation reference, a red tick where they
//                   part by more than 3 % of the height; a white point dragged corrects what SDPose read (*Fit again* refits), a blue one
//                   sets the part it ends there and locks it. Under them the shell (or the Detailed figure) in x-ray and the skeleton, a
//                   joint the shell's volume does not hold in red, a joint clicked picks its row; *side* turns the pane to the figure in
//                   3D, from the side, orbited;
//   the guide       what Wan Animate gets — the pose pass, hands and feet, on a short motion; the reference under its first frame.
// The parts are the Inspector's (SkeletonParts): each a length in centimetres with an adult's range and a lock, the head's carriage, the
// shoulders' drop, the feet turned out, the hands at rest (*From a picture ▾* reads one of the reference set's pictures and picks the
// preset nearest SDPose's hands — D140: the fitting picture's are always open and spread).
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Lock, LockOpen, Trash2 } from 'lucide-react'
import { api } from '../../api/client'
import type { Profile, StageCamera, StageDoc, StageObject } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { Help } from '../../frame/Help'
import { askConfirm, useSession } from '../../store/session'
import { shellBlocked, shellFromArmsDown, useStory, versionPointsOfShell } from '../story/storyStore'
import { DEFAULT_BODY, type Body } from './body'
import { JOINTS, mannequin, POSE_NAMES, POSES, type Joint } from './builders'
import { HAND_PRESETS, makeDetailed } from './detailed'
import { bindProxy, insideShell, setShellPoints, stanceOf } from './proxy'
import { COCO, cropOf, defaultOf, disagreements, dragFactor, lengthCm, outside, pictureMap, ROWS, seen, setLocked, unlock, type Points, type RowKey, type XY } from './skeleton'
import { handFromPicture, readPicture, setUi, ui, useUi } from './benchState'
import { showMenu } from '../../frame/ContextMenu'
import { cellOf } from '../story/coverage'

setShellPoints(versionPointsOfShell)                                          // CS3: a shell binds in its reference's stance here too (the stage's store may not be loaded)

type Motion = 'stance' | 'walk' | 'sit' | 'point' | 'wave' | 'turn'
const MOTIONS: Motion[] = ['stance', 'walk', 'sit', 'point', 'wave', 'turn']
const JOINT_ROW: Partial<Record<Joint, RowKey>> = { head: 'head', neck: 'neck', spine: 'torso', root: 'hips', r_shoulder: 'shoulders', l_shoulder: 'shoulders',
  r_elbow: 'upper_arm', l_elbow: 'upper_arm', r_hip: 'hips', l_hip: 'hips', r_knee: 'thigh', l_knee: 'thigh' }
const ROW_JOINTS: Partial<Record<RowKey, Joint[]>> = { head: ['head'], neck: ['neck'], torso: ['spine'], shoulders: ['r_shoulder', 'l_shoulder'], hips: ['r_hip', 'l_hip'],
  upper_arm: ['r_elbow', 'l_elbow'], forearm: ['r_elbow', 'l_elbow'], thigh: ['r_knee', 'l_knee'], shin: ['r_knee', 'l_knee'] }

const bodyOf = (v: Profile['versions'][number] | undefined): Body => ({ ...DEFAULT_BODY, ...((v?.body ?? {}) as Partial<Body>), hand_rest: { ...DEFAULT_BODY.hand_rest, ...((v?.body?.hand_rest ?? {}) as object) } }) as Body
const saveBody = (b: Body) => useStory.getState().setSheet({ body: b as never })

type Look = 'shell' | 'figure' | 'none'
const BONES: [Joint, Joint | number][] = [['root', 'spine'], ['spine', 'neck'], ['neck', 'head'], ['spine', 'r_shoulder'], ['spine', 'l_shoulder'], ['r_shoulder', 'r_elbow'],
  ['l_shoulder', 'l_elbow'], ['r_elbow', 4], ['l_elbow', 7], ['root', 'r_hip'], ['root', 'l_hip'], ['r_hip', 'r_knee'], ['l_hip', 'l_knee'], ['r_knee', 10], ['l_knee', 13]]   // a number: the marker that ends it

/** The figure's joints on its front plane (and the wrists' and ankles' markers that end the forearms and shins), in the reference's stance. */
function figureJoints(body: Body, stance: Record<string, number[]>): { joints: Record<Joint, XY>; markers: XY[] } {
  const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, stance, body)
  const g = new THREE.Group(); g.add(fig.root); g.updateMatrixWorld(true)
  const xy = (o: THREE.Object3D): XY => { const p = o.getWorldPosition(new THREE.Vector3()); return [p.x, p.y] }
  return { joints: Object.fromEntries(JOINTS.map((j) => [j, xy(fig.joints[j])])) as Record<Joint, XY>, markers: fig.markers.map(xy) }
}

/** D140: the shell (or the Detailed figure) in x-ray over the picture — rendered offscreen through an orthographic camera fitted to the
 *  picture by the nose and the ankles (the shell is made front-on from it), as an image under the points — and the joints the shell's
 *  volume does not hold. Nothing while the look is none or there is no map. */
function useOverlay(body: Body, stance: Record<string, number[]>, look: Look, shell: string | null, map: ReturnType<typeof pictureMap>, w: number, h: number, points: Points | null): { url: string | null; outside: Joint[] } {
  const [state, setState] = useState<{ url: string | null; outside: Joint[]; key: string }>({ url: null, outside: [], key: '' })
  const active = !!map && (look === 'figure' || (look === 'shell' && !!shell))
  const key = active ? `${look}/${shell}/${w}x${h}` : ''
  useEffect(() => {
    if (!active || !map) return
    let live = true
    const t = window.setTimeout(() => void (async () => {
      const scale = Math.min(1, 1024 / w), W = Math.round(w * scale), H = Math.round(h * scale)
      const r = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true })
      try {
        r.setSize(W, H, false); r.setClearColor(0x000000, 0)
        const scene = new THREE.Scene()
        scene.add(new THREE.HemisphereLight(0xffffff, 0x666666, 1.8)); const sun = new THREE.DirectionalLight(0xffffff, 1.2); sun.position.set(1, 2, 3); scene.add(sun)
        const clay = new THREE.MeshLambertMaterial({ color: 0xd8dce4, transparent: true, opacity: 0.5, depthWrite: false })
        const fig = mannequin(clay, POSES.stand, stance, body)
        const g = new THREE.Group(); g.add(fig.root); scene.add(g); g.updateMatrixWorld(true)
        fig.root.traverse((o) => { if ((o as THREE.Mesh).isMesh) o.visible = false })
        let outside: Joint[] = []
        if (look === 'shell' && shell) {
          const gltf = await new GLTFLoader().loadAsync(api.assetUrl(shell))
          const px = bindProxy(gltf.scene, fig.joints, fig.limbs, g, { preset: 'stand', joints: stance }, { stance, visible: true, points, markers: fig.markers })
          for (const m of px.meshes) { m.material = clay; scene.add(m) }
          const plain = px.meshes.map((m) => new THREE.Mesh(m.geometry, new THREE.MeshBasicMaterial({ side: THREE.DoubleSide })))
          plain.forEach((m) => m.updateMatrixWorld(true))
          outside = JOINTS.filter((j) => !insideShell(plain, fig.joints[j].getWorldPosition(new THREE.Vector3())))
        } else {
          const { mannequinClone } = await import('./motion/mannequins')
          const { root, rig } = await mannequinClone(body.figure ?? 'female', clay)
          const d = makeDetailed(root, rig, fig.joints.root.parent!, fig.joints, fig.limbs, { hands: body.hands, feet: body.feet, head: body.head, handRest: body.hand_rest, feetOut: body.feet_out })
          d.follow(fig.joints, null)
        }
        const tl = map.toFig([0, 0]), br = map.toFig([w, h])
        const cam = new THREE.OrthographicCamera(tl[0], br[0], tl[1], br[1], 0.01, 100)
        cam.position.set(0, 0, 10); cam.updateProjectionMatrix()
        r.render(scene, cam)
        const blob: Blob = await new Promise((res) => r.domElement.toBlob((b) => res(b!), 'image/png'))
        if (!live) return
        const url = URL.createObjectURL(blob)
        setState((old) => { if (old.url) URL.revokeObjectURL(old.url); return { url, outside, key } })
      } catch { /* no shell or no starter set: the points alone */ } finally { r.dispose(); r.forceContextLoss() }
    })(), 150)
    return () => { live = false; window.clearTimeout(t) }
  }, [active, key, body, stance, look, shell, map, w, h, points])
  return active && state.key === key ? { url: state.url, outside: state.outside } : { url: null, outside: [] }
}

/** The figure's 18 markers on its front plane, in the reference's stance. */
function figureMarkers(body: Body, stance: Record<string, number[]>): XY[] {
  const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, stance, body)
  const g = new THREE.Group(); g.add(fig.root); g.updateMatrixWorld(true)
  return fig.markers.map((m) => { const p = m.getWorldPosition(new THREE.Vector3()); return [p.x, p.y] as XY })
}

// ------------------------------------------------------------------ the view
export default function SkeletonBench() {
  const p = useStory((s) => s.profile())
  const v = useStory((s) => s.version())
  const u = useUi()
  const [side, setSide] = useState<'front' | 'back'>('front')
  const key = p && v ? `${p.id}/${v.id}` : null
  const fitted = v?.body_points ?? null
  useEffect(() => {                                                          // another character or version, or a new fit: its points
    if (key) setUi({ pts: fitted ? JSON.parse(JSON.stringify(fitted)) : null, forVersion: key, moved: [] })
  }, [key, fitted])
  const body = useMemo(() => bodyOf(v), [v])
  const stance = useMemo(() => stanceOf((u.pts ?? fitted) as never), [u.pts, fitted])
  if (!p || !v) return <div className="story-empty"><div>Pick a character on the left.</div></div>
  const vp = (v.body_points ?? null) as Points | null
  return (
    <div className="skel-bench" data-profile={p.id}>
      <div className="skel-strip">
        <b>{p.name}</b><span className="muted">· {v.id} · skeleton</span>
        <span className="segmented" role="group" aria-label="the reference's side">
          {(['front', 'back'] as const).map((k) => <button key={k} type="button" className={side === k ? 'active' : ''} disabled={k === 'back' && !v.anim_ref_back_asset_id} onClick={() => setSide(k)}>{k}</button>)}
        </span>
        <span className="spacer" />
        <CommandButton id="cast.skeleton.close" text size={13} />
      </div>
      <div className="skel-panes">
        <RefPane key={`${p.id}/${v.id}`} v={v} body={body} stance={stance} side={side} />
        <GuidePane body={body} stance={stance} refId={v.anim_ref_asset_id ?? null} points={u.pts ?? vp} shell={v.shell_asset_id ?? null} />
      </div>
      <div className="skel-foot">
        <CommandButton id="cast.skeleton.fit" text />
        <CommandButton id="cast.skeleton.sdpose" text />
        <CommandButton id="cast.skeleton.mirror" text />
        <CommandButton id="cast.skeleton.test" text />
        <CommandButton id="cast.shell.make" text />
        <span className="spacer" />
        <span className="muted">{u.moved.length ? `${u.moved.length} point${u.moved.length === 1 ? '' : 's'} moved` : 'SDPose\'s points'}{body.locks?.length ? ` · ${body.locks.length} locked` : ''}</span>
        <ShellState v={v} />
      </div>
    </div>
  )
}

/** D139: the shell's state in the foot — made, fused (made from an arms-down picture), or why it waits (the tooltip says the whole). */
function ShellState({ v }: { v: Profile['versions'][number] }) {
  if (shellFromArmsDown(v)) return <span className="hint warn" data-shell="arms-down" title="Made from a reference whose arms touch the body: Pixal3D made them part of it. Draw the reference again in the A-pose (Cast's animation reference), fit, then make the shell again (D139)">· the shell's arms are fused</span>
  if (v.shell_asset_id) return <span className="muted" data-shell="made">· shell</span>
  const why = shellBlocked(v)
  return why && v.anim_ref_asset_id ? <span className="muted" data-shell="blocked" title={why}>· {v.anim_ref_note === 'arms_close' ? 'the shell needs the A-pose' : 'the shell after the fit'}</span> : null
}

// ------------------------------------------------------------------ the reference
function RefPane({ v, body, stance, side }: { v: Profile['versions'][number]; body: Body; stance: Record<string, number[]>; side: 'front' | 'back' }) {
  const u = useUi()
  const svg = useRef<SVGSVGElement>(null)
  const [drag, setDrag] = useState<{ kind: 'white' | 'blue'; key: string; k: number; at: XY } | null>(null)
  const shell = v.shell_asset_id ?? null
  const [look, setLook] = useState<Look>(shell ? 'shell' : 'figure')
  const [view, setView] = useState<'front' | 'side'>('front')
  const fig = useMemo(() => figureMarkers(body, stance), [body, stance])
  const skel = useMemo(() => figureJoints(body, stance), [body, stance])
  const pts = u.pts
  const id = side === 'back' ? v.anim_ref_back_asset_id : v.anim_ref_asset_id
  const [w, h] = (pts?.canvas?.length === 2 ? pts.canvas : [1280, 720]) as [number, number]
  const map = useMemo(() => (pts && side === 'front' ? pictureMap(pts.pose, fig) : null), [pts, side, fig])
  const over = useOverlay(body, stance, look, shell, view === 'front' ? map : null, w, h, (v.body_points ?? null) as Points | null)
  if (!id) return <div className="skel-pane"><span className="hint">No animation reference yet — Cast's *Make an animation reference*.</span></div>
  const crop = pts && side === 'front' ? cropOf(pts, w, h) ?? [0, 0, w, h] : null      // the figure fills the pane (the SVG letterboxes it)
  const at = (e: React.PointerEvent): XY => { const m = svg.current!.getScreenCTM()!.inverse(); const q = new DOMPoint(e.clientX, e.clientY).matrixTransform(m); return [q.x, q.y] }
  const r = Math.max(3, (crop?.[3] ?? h) / 110)
  const rows = (key: 'pose' | 'hand_left' | 'hand_right' | 'feet') => (pts?.[key] ?? []) as number[][]
  const move = (e: React.PointerEvent) => { if (drag) setDrag({ ...drag, at: at(e) }) }
  const drop = () => {
    if (!drag || !pts) { setDrag(null); return }
    if (drag.kind === 'white') {
      const next = JSON.parse(JSON.stringify(pts)) as Points
      const list = (next as unknown as Record<string, number[][]>)[drag.key]
      list[drag.k] = [Math.round(drag.at[0] * 10) / 10, Math.round(drag.at[1] * 10) / 10, list[drag.k]?.[2] ?? 1]
      setUi({ pts: next, moved: drag.key === 'pose' && !ui.moved.includes(drag.k) ? [...ui.moved, drag.k] : ui.moved })
    } else if (map) {
      const f = dragFactor(body, fig, drag.k, map.toFig(drag.at))
      if (f) { saveBody(setLocked(body, f.factor, f.value)); useSession.getState().toast(`${f.factor} set to ×${f.value.toFixed(2)} and locked — Fit again keeps it`, 'info') }
    }
    setDrag(null)
  }
  const ticks = pts && side === 'front' ? disagreements(pts.pose, fig) : []
  const toPic = (p: XY): XY => map!.toPic(p)
  const end = (b: Joint | number): XY => toPic(typeof b === 'number' ? skel.markers[b] : skel.joints[b])
  const tools = (
    <div className="tools">
      <span className="segmented" role="group" aria-label="over the picture">
        {(['shell', 'figure', 'none'] as const).map((k) => <button key={k} type="button" className={look === k ? 'active' : ''} disabled={k === 'shell' && !shell}
          title={k === 'shell' ? (shell ? 'the shell in x-ray, the skeleton inside' : 'no shell yet — Make the shell ▶') : k === 'figure' ? 'the Detailed figure in x-ray, the skeleton inside' : 'the points alone'}
          onClick={() => setLook(k)}>{k === 'none' ? 'points' : k}</button>)}
      </span>
      <span className="segmented" role="group" aria-label="the view">
        {(['front', 'side'] as const).map((k) => <button key={k} type="button" className={view === k ? 'active' : ''} onClick={() => setView(k)}
          title={k === 'side' ? 'the figure in 3D from the side, orbited with the mouse' : 'the picture, the figure over it'}>{k}</button>)}
      </span>
    </div>
  )
  if (view === 'side') return (
    <div className="skel-pane ref" aria-label="the reference">
      <span className="lab">the figure · side</span>
      {tools}
      <FigurePane body={body} stance={stance} shell={shell} look={look} points={(v.body_points ?? null) as Points | null} />
    </div>
  )
  return (
    <div className="skel-pane ref" aria-label="the reference" onContextMenu={(e) => { e.preventDefault(); showMenu(e, [{ cmd: 'cast.skeleton.fit' }, { cmd: 'cast.skeleton.sdpose' }, { cmd: 'cast.skeleton.mirror' }, { cmd: 'cast.shell.make' }]) }}>
      <span className="lab">the reference · SDPose's points ○ · the figure's ●</span>
      {tools}
      <div className="skel-ref">
        {!crop && <img src={api.assetUrl(id)} alt="the animation reference" draggable={false} />}
        {crop && <svg ref={svg} viewBox={crop.join(' ')} onPointerMove={move} onPointerUp={drop} onPointerLeave={drop}>
          <image href={api.assetUrl(id)} x={0} y={0} width={w} height={h}><title>the animation reference</title></image>
          {over.url && <image href={over.url} x={0} y={0} width={w} height={h} className="xray" />}
          {map && look !== 'none' && BONES.map(([a, b]) => { const p = end(a), q = end(b)
            return <line key={`${a}-${b}`} x1={p[0]} y1={p[1]} x2={q[0]} y2={q[1]} className="bone" /> })}
          {map && look !== 'none' && JOINTS.map((j) => { const p = toPic(skel.joints[j]), out = over.outside.includes(j), sel = (ROW_JOINTS[u.row as RowKey] ?? []).includes(j)
            return <circle key={j} cx={p[0]} cy={p[1]} r={r * (out ? 0.75 : 0.45)} className={`joint${out ? ' out' : ''}${sel ? ' sel' : ''}`} data-joint={j}
              onClick={() => { if (JOINT_ROW[j]) setUi({ row: JOINT_ROW[j]! }) }}><title>{`${j}${out ? ' — outside the shell' : ''}: click for its row`}</title></circle> })}
          {ticks.map((t) => <line key={`t${t.k}`} x1={t.at[0]} y1={t.at[1]} x2={t.fig[0]} y2={t.fig[1]} className="tick" />)}
          {(['pose', 'hand_left', 'hand_right', 'feet'] as const).flatMap((key) => rows(key).map((pt, k) => {
            if (!seen(pt)) return null
            const q = drag?.kind === 'white' && drag.key === key && drag.k === k ? drag.at : [pt[0], pt[1]]
            return <circle key={`${key}${k}`} cx={q[0]} cy={q[1]} r={key === 'pose' ? r : r * 0.55} className={`white${key === 'pose' && ui.moved.includes(k) ? ' moved' : ''}`} data-k={k}
              onPointerDown={(e) => { (e.target as Element).setPointerCapture?.(e.pointerId); setDrag({ kind: 'white', key, k, at: at(e) }) }}><title>{`${key === 'pose' ? COCO[k] : key} — SDPose's: drag where it is, then Fit again`}</title></circle>
          }))}
          {map && fig.map((f, k) => { const q = drag?.kind === 'blue' && drag.k === k ? drag.at : map.toPic(f)
            return <circle key={`b${k}`} cx={q[0]} cy={q[1]} r={r * 0.5} className="blue" data-k={k}
              onPointerDown={(e) => { (e.target as Element).setPointerCapture?.(e.pointerId); setDrag({ kind: 'blue', key: 'pose', k, at: at(e) }) }}><title>{`${COCO[k]} — the figure's: drag to set the part it ends (locked)`}</title></circle> })}
        </svg>}
      </div>
      {!pts && <span className="hint">Fit the body first: its points come from the reference (Cast's body section).</span>}
      {ticks.length > 0 && <span className="hint warn">{ticks.length} point{ticks.length === 1 ? '' : 's'} apart from the figure's</span>}
      {look === 'shell' && over.outside.length > 0 && <span className="hint warn" title={over.outside.join(', ')}>{over.outside.length} joint{over.outside.length === 1 ? '' : 's'} outside the shell</span>}
    </div>
  )
}

// ------------------------------------------------------------------ the figure from the side (the reference pane's *side*)
function FigurePane({ body, stance, shell, look, points }: { body: Body; stance: Record<string, number[]>; shell: string | null; look: Look; points: Points | null }) {
  const host = useRef<HTMLDivElement>(null)
  const [outside, setOutside] = useState<Joint[]>([])                       // the joints the shell's volume does not hold (ringed)
  const u = useUi()
  const world = useRef<{ r: THREE.WebGLRenderer; scene: THREE.Scene; cam: THREE.PerspectiveCamera; orbit: OrbitControls; content: THREE.Group; balls: Map<Joint, THREE.Mesh> } | null>(null)
  useEffect(() => {                                                          // the viewer, once
    const el = host.current!
    const r = new THREE.WebGLRenderer({ antialias: true })
    r.setPixelRatio(Math.min(2, window.devicePixelRatio || 1))
    el.appendChild(r.domElement)
    const scene = new THREE.Scene(); scene.background = new THREE.Color(0x1d1e22)
    scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.6)); const key = new THREE.DirectionalLight(0xffffff, 1.4); key.position.set(2, 4, 3); scene.add(key)
    const grid = new THREE.GridHelper(4, 8, 0x555a66, 0x33363d); scene.add(grid)
    const cam = new THREE.PerspectiveCamera(30, 1, 0.05, 50)
    const orbit = new OrbitControls(cam, r.domElement)
    const content = new THREE.Group(); scene.add(content)
    const w = { r, scene, cam, orbit, content, balls: new Map<Joint, THREE.Mesh>() }
    world.current = w
    let raf = 0
    const loop = () => { raf = requestAnimationFrame(loop); r.render(scene, cam) }
    const fit = () => { const b = el.getBoundingClientRect(); r.setSize(b.width, b.height); cam.aspect = b.width / Math.max(1, b.height); cam.updateProjectionMatrix() }
    const ro = new ResizeObserver(fit); ro.observe(el); fit(); loop()
    const click = (e: MouseEvent) => {
      const b = r.domElement.getBoundingClientRect()
      const ray = new THREE.Raycaster(); ray.setFromCamera(new THREE.Vector2(((e.clientX - b.left) / b.width) * 2 - 1, -((e.clientY - b.top) / b.height) * 2 + 1), cam)
      const hit = ray.intersectObjects([...w.balls.values()], false)[0]
      const j = hit?.object.userData.joint as Joint | undefined
      if (j && JOINT_ROW[j]) setUi({ row: JOINT_ROW[j]! })
    }
    r.domElement.addEventListener('click', click)
    return () => { cancelAnimationFrame(raf); ro.disconnect(); r.domElement.removeEventListener('click', click); orbit.dispose(); r.dispose(); r.domElement.remove(); world.current = null }
  }, [])
  useEffect(() => {                                                          // the figure, whenever the body, the stance or the look change
    const w = world.current
    if (!w) return
    let live = true
    const t = window.setTimeout(() => {
      w.content.clear(); w.balls.clear()
      const clay = new THREE.MeshLambertMaterial({ color: 0xb4b4b8 })
      const fig = mannequin(clay, POSES.stand, stance, body)
      const g = new THREE.Group(); g.add(fig.root); w.content.add(g); g.updateMatrixWorld(true)
      const H = body.height_m
      // the skeleton: a ball per joint, a line along each part
      const pts: THREE.Vector3[] = []
      for (const j of JOINTS) {
        const at = fig.joints[j].getWorldPosition(new THREE.Vector3())
        const on = (ROW_JOINTS[ui.row as RowKey] ?? []).includes(j)
        const ball = new THREE.Mesh(new THREE.SphereGeometry(0.022 * H / 1.75, 12, 8), new THREE.MeshBasicMaterial({ color: on ? 0xf0a030 : 0x2f9be8, depthTest: false }))
        ball.position.copy(at); ball.renderOrder = 3; ball.userData.joint = j; w.content.add(ball); w.balls.set(j, ball)
      }
      const link = (a: Joint, b: Joint | THREE.Object3D) => pts.push(fig.joints[a].getWorldPosition(new THREE.Vector3()), b instanceof THREE.Object3D ? b.getWorldPosition(new THREE.Vector3()) : fig.joints[b].getWorldPosition(new THREE.Vector3()))
      link('root', 'spine'); link('spine', 'neck'); link('neck', 'head'); link('spine', 'r_shoulder'); link('spine', 'l_shoulder'); link('r_shoulder', 'r_elbow'); link('l_shoulder', 'l_elbow')
      link('r_elbow', fig.markers[4]); link('l_elbow', fig.markers[7]); link('root', 'r_hip'); link('root', 'l_hip'); link('r_hip', 'r_knee'); link('l_hip', 'l_knee'); link('r_knee', fig.markers[10]); link('l_knee', fig.markers[13])
      const lines = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: 0x2f9be8, depthTest: false })); lines.renderOrder = 2; w.content.add(lines)
      fig.root.traverse((o) => { if ((o as THREE.Mesh).isMesh) o.visible = false })                     // the Simple boxes: the Detailed figure or the shell instead
      if (look === 'none') setOutside([])
      else if (look === 'shell' && shell) {
        void new GLTFLoader().loadAsync(api.assetUrl(shell)).then((gltf) => {
          if (!live) return
          const px = bindProxy(gltf.scene, fig.joints, fig.limbs, g, { preset: 'stand', joints: stance }, { stance, visible: true, points, markers: fig.markers })
          for (const m of px.meshes) { const mat = m.material as THREE.MeshLambertMaterial; mat.transparent = true; mat.opacity = 0.42; mat.depthWrite = false; w.content.add(m) }
          const plain = px.meshes.map((m) => new THREE.Mesh(m.geometry, new THREE.MeshBasicMaterial({ side: THREE.DoubleSide })))
          plain.forEach((m) => m.updateMatrixWorld(true))
          const out = [...w.balls].filter(([, ball]) => !insideShell(plain, ball.position)).map(([j]) => j)
          for (const j of out) { const ball = w.balls.get(j)!; (ball.material as THREE.MeshBasicMaterial).color.set(0xe5484d); ball.scale.setScalar(1.6) }
          setOutside(out)
        }).catch(() => undefined)
      } else {
        setOutside([])
        void import('./motion/mannequins').then((m) => m.mannequinClone(body.figure ?? 'female', clay)).then(({ root, rig }) => {
          if (!live) return
          const d = makeDetailed(root, rig, fig.joints.root.parent!, fig.joints, fig.limbs, { hands: body.hands, feet: body.feet, head: body.head, handRest: body.hand_rest, feetOut: body.feet_out })
          d.follow(fig.joints, null)
          d.object.traverse((o) => { const m = o as THREE.Mesh; if (m.isMesh) { (m.material as THREE.MeshLambertMaterial).transparent = true; (m.material as THREE.MeshLambertMaterial).opacity = 0.55 } })
        }).catch(() => { fig.root.traverse((o) => { if ((o as THREE.Mesh).isMesh && !o.userData.joint) o.visible = true }) })   // no starter set: the boxes
      }
      const half = THREE.MathUtils.degToRad(w.cam.fov / 2), halfW = Math.atan(Math.tan(half) * w.cam.aspect)
      const d = Math.max((0.6 * H) / Math.tan(half), (0.56 * H) / Math.tan(halfW))   // the figure whole, arms out, in a narrow pane too
      w.cam.position.set(d, H * 0.5, 0)                                     // from the side: the depth the picture cannot show
      w.orbit.target.set(0, H * 0.5, 0); w.orbit.update()
    }, 120)
    return () => { live = false; window.clearTimeout(t) }
  }, [body, stance, shell, look, u.row, points])
  return (
    <>
      <div ref={host} className="skel-3d" />
      {look === 'shell' && outside.length > 0 && <span className="hint warn" title={outside.join(', ')}>{outside.length} joint{outside.length === 1 ? '' : 's'} outside the shell</span>}
    </>
  )
}

// ------------------------------------------------------------------ the guide
function GuidePane({ body, stance, refId, points, shell }: { body: Body; stance: Record<string, number[]>; refId: string | null; points: Points | null; shell: string | null }) {
  const [motion, setMotion] = useState<Motion>('stance')
  const [ghost, setGhost] = useState(true)
  const [frames, setFrames] = useState<{ urls: string[]; kp: number[][] | null } | null>(null)
  const [i, setI] = useState(0)
  useEffect(() => {
    let live = true
    const t = window.setTimeout(() => {
      void (async () => {
        const [w, h] = [360, 540]
        let blobs: Blob[] = [], kp: number[][] | null = null
        if (motion === 'turn') {
          const { renderTurn } = await import('./turnTest')
          blobs = (await renderTurn(body, 24, 12, w, h, undefined, points as never, shell)).blobs
        } else {
          const { StageEngine } = await import('./engine')
          const H = body.height_m, vfov = 2 * Math.atan((36 / (w / h)) / 2 / 35), dist = H / (0.7 * 2 * Math.tan(vfov / 2))
          const cam: StageCamera = { id: 'cam', name: 'Guide', pos: [0, H * 0.55, dist], target: [0, H * 0.5, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }
          const joints = motion === 'stance' ? stance : (POSES[motion].j as Record<string, number[]>)
          const fig = { id: 'fig', kind: 'mannequin', name: 'figure', preset: 'adult', asset_id: null, transform: { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] }, parent: null, parent_joint: null,
            locked: false, visible: true, colour_id: 1, pose: { preset: motion === 'stance' ? 'stand' : motion, joints, extra: {} }, billboard: false, profile_id: null, version: null, body: body as never,
            detail: body.figure ?? 'female', path: null, shadow_proxy: shell, light: null, lens_deg: null, plate_asset_id: null, floor_y: null, plate_camera_id: null, level: null, things: [], things_document_id: null } as unknown as StageObject
          const doc = { schema_version: 3, id: 'guide', name: 'guide', size: { w, h, fps: 12 }, objects: [fig], cameras: [cam], active_camera: 'cam', keyframes: { camera: {}, objects: {} },
            range: { start: 0, end: 0 }, passes: [], group_id: null, revision: 0, created_at: '', updated_at: '' } as unknown as StageDoc
          const e = new StageEngine(document.createElement('canvas'), { onPick: () => undefined, onTransformed: () => undefined, onPosed: () => undefined })
          try { e.sync(doc); const r = await e.renderSequence([{ cam, doc }], w, h, 'pose', doc); blobs = r.blobs; kp = (r.keypoints[0]?.[0] ?? null) as number[][] | null } finally { e.dispose() }
        }
        if (!live) return
        setFrames((old) => { old?.urls.forEach((x) => URL.revokeObjectURL(x)); return { urls: blobs.map((b) => URL.createObjectURL(b)), kp } }); setI(0)
      })()
    }, 250)
    return () => { live = false; window.clearTimeout(t) }
  }, [body, stance, motion, points, shell])
  useEffect(() => { if (motion !== 'turn' || !frames || frames.urls.length < 2) return; const t = window.setInterval(() => setI((n) => (n + 1) % frames.urls.length), 1000 / 12); return () => window.clearInterval(t) }, [motion, frames])
  // the reference under the stance's frame: its nose and ankles onto the guide's
  const under = useMemo(() => {
    const kp = frames?.kp, pose = points?.pose
    if (!ghost || motion !== 'stance' || !kp || !pose || !seen(pose[0]) || !seen(pose[10]) || !seen(pose[13]) || !refId) return null
    const aG = [(kp[10][0] + kp[13][0]) / 2, (kp[10][1] + kp[13][1]) / 2], aP = [(pose[10][0] + pose[13][0]) / 2, (pose[10][1] + pose[13][1]) / 2]
    const s = Math.hypot(kp[0][0] - aG[0], kp[0][1] - aG[1]) / Math.max(1e-6, Math.hypot(pose[0][0] - aP[0], pose[0][1] - aP[1]))
    const [cw, ch] = (points?.canvas ?? [1280, 720]) as number[]
    return { left: aG[0] - aP[0] * s, top: aG[1] - aP[1] * s, width: cw * s, height: ch * s }
  }, [frames, points, ghost, motion, refId])
  return (
    <div className="skel-pane guide" aria-label="the guide">
      <span className="lab">the guide · what Wan Animate gets</span>
      <div className="skel-guide">
        <div className="frame" style={{ aspectRatio: '360 / 540' }}>
          {under && <img className="under" src={api.assetUrl(refId!)} alt="" style={{ left: `${(under.left / 360) * 100}%`, top: `${(under.top / 540) * 100}%`, width: `${(under.width / 360) * 100}%`, height: `${(under.height / 540) * 100}%` }} />}
          {frames?.urls[i] && <img className="pose" src={frames.urls[i]} alt="the pose guide" />}
        </div>
      </div>
      <div className="skel-motions" role="group" aria-label="the motion">
        {MOTIONS.map((m) => <button key={m} type="button" className={motion === m ? 'active' : ''} onClick={() => setMotion(m)}>{m === 'stance' ? 'A-pose' : m}</button>)}
        <button type="button" className={ghost ? 'active' : ''} aria-pressed={ghost} disabled={motion !== 'stance'} onClick={() => setGhost(!ghost)} title="The reference under the A-pose's frame">onion skin</button>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ the parts (the Inspector)
const BOUNDS: Partial<Record<keyof Body, [number, number]>> = { head: [0.5, 2.5], neck: [0.5, 3], torso: [0.6, 1.6], shoulders: [0.6, 1.8], hips: [0.6, 1.6], elbow: [0.35, 0.65],
  arms: [0.6, 1.6], knee: [0.35, 0.65], legs: [0.5, 1.6], hands: [0.5, 1.6], feet: [0.5, 1.6] }

export function SkeletonParts() {
  const p = useStory((s) => s.profile())
  const v = useStory((s) => s.version())
  const profiles = useStory((s) => s.profiles)
  const u = useUi()
  const [busy, setBusy] = useState(false)
  const refPage = useStory((s) => s.refPage)
  if (!p || !v) return null
  const b = bodyOf(v)
  const open = v.state === 'open'
  const set = (patch: Partial<Body>) => { if (open) saveBody({ ...b, ...patch }) }
  const first = ROWS.find((r) => outside(b, r))
  const groups = [...new Set(ROWS.map((r) => r.group))]
  const others = profiles.filter((x) => x.cls === 'character' && x.id !== p.id && x.versions.some((y) => y.body))
  const fromPicture = async (assetId: string) => {                         // D140: a picture of the character's — the fitting picture's hands are always open
    setBusy(true)
    try {
      const r = await handFromPicture(b, await readPicture(assetId))
      if (r) set({ hand_rest: { ...b.hand_rest, preset: r.preset, curl: r.curl } })
      else useSession.getState().toast('No hands found in that picture — pick one that shows them', 'info')
    } finally { setBusy(false) }
  }
  const pictures = Object.values(refPage?.assets ?? {}).sort((x, y) => (x.id === v.hero_asset_id ? -1 : y.id === v.hero_asset_id ? 1 : x.created_at < y.created_at ? -1 : 1))
  const pictureMenu = (e: React.MouseEvent) => showMenu(e, pictures.length
    ? pictures.slice(0, 20).map((a) => { const c = cellOf(a); return { label: a.id === v.hero_asset_id ? 'the hero' : c ? `${c.shot} · ${c.angle}` : `a reference (${a.created_at.slice(0, 10)})`, run: () => void fromPicture(a.id) } })
    : [{ label: 'no pictures in the reference set yet', disabled: true, run: () => undefined }])
  return (
    <div className="story-insp skel-parts">
      <h4>{p.name}'s skeleton <Help text={"Each part as a length at the figure's height, the factor of the default adult in its tooltip. The grey band is an adult's range: outside it the row turns amber — a child or a creature is yours to decide. A lock keeps a part through Fit again."} /></h4>
      <div className="kv">
        <span>height</span><span className="mono">{b.height_m.toFixed(2)} m</span>
        <span>figure</span><span className="segmented" role="group" aria-label="figure">{(['female', 'male'] as const).map((k) => <button key={k} type="button" disabled={!open} className={b.figure === k ? 'active' : ''} onClick={() => set({ figure: k })}>{k === 'female' ? '♀' : '♂'}</button>)}</span>
      </div>
      {groups.map((g) => (
        <div key={g} className="skel-group">
          <div className="grp">{g}</div>
          {ROWS.filter((r) => r.group === g).map((r) => {
            const val = Number(b[r.factor] ?? defaultOf(r.factor)), [lo, hi] = BOUNDS[r.factor] ?? [0.5, 1.6], locked = (b.locks ?? []).includes(r.factor as string)
            const pct = (x: number) => `${((x - lo) / (hi - lo)) * 100}%`
            return (
              <div key={r.key} className={`skel-row${outside(b, r) ? ' amber' : ''}${u.row === r.key ? ' sel' : ''}`} data-row={r.key} onClick={() => setUi({ row: r.key })}
                onContextMenu={(e) => { e.preventDefault(); if (open) saveBody({ ...unlock(b, r.factor), [r.factor]: defaultOf(r.factor) }) }} title={`×${val.toFixed(3)} · right-click: back to the adult's (unlocked)`}>
                <span>{r.label}</span>
                <input type="range" min={lo} max={hi} step={0.005} value={val} disabled={!open} aria-label={r.label}
                  style={{ ['--band-lo' as string]: pct(r.band[0]), ['--band-hi' as string]: pct(r.band[1]) }}
                  onChange={(e) => saveBody(setLocked(b, r.factor, Number(e.target.value)))} />
                <span className="mono">{lengthCm(b, r.key).toFixed(1)} cm</span>
                <button type="button" className="quiet lock" aria-pressed={locked} disabled={!open} title={locked ? 'Locked: Fit again leaves it' : 'Fit again sets it'}
                  onClick={(e) => { e.stopPropagation(); saveBody(locked ? unlock(b, r.factor) : setLocked(b, r.factor, val)) }}>{locked ? <Lock size={12} /> : <LockOpen size={12} />}</button>
              </div>
            )
          })}
        </div>
      ))}
      <div className="skel-group">
        <div className="grp">Carriage</div>
        {([['head_forward', 'head forward', -30, 40, '°'], ['shoulder_drop', 'shoulder drop', 0, 3, '×'], ['feet_out', 'feet turned out', -20, 45, '°']] as const).map(([k, label, lo, hi, unit]) => (
          <div key={k} className="skel-row" data-row={k}><span>{label}</span>
            <input type="range" min={lo} max={hi} step={unit === '×' ? 0.05 : 1} value={Number(b[k] ?? (k === 'shoulder_drop' ? 1 : 0))} disabled={!open} aria-label={label} onChange={(e) => set({ [k]: Number(e.target.value) } as Partial<Body>)} />
            <span className="mono">{unit === '×' ? `×${Number(b[k] ?? 1).toFixed(2)}` : `${Math.round(Number(b[k] ?? 0))}°`}</span><span /></div>))}
      </div>
      <div className="skel-group">
        <div className="grp">Hands at rest <Help text={"How the hands are held where a pose turns no finger — every figure of this character starts from it. From a picture reads one of the reference set's pictures — pick one that shows the hands (the animation reference's are always open and spread) — and picks the preset and curl nearest them."} /></div>
        <div className="hands">
          <button type="button" className="quiet" disabled={!open || busy} onClick={pictureMenu} title="read the hands of one of the character's pictures (SDPose, a short job)">{busy ? 'reading the hands…' : 'From a picture ▾'}</button>
          {HAND_PRESETS.map((h) => <button key={h} type="button" disabled={!open} className={b.hand_rest.preset === h ? 'active' : ''} onClick={() => set({ hand_rest: { ...b.hand_rest, preset: h } })}>{h}</button>)}
        </div>
        {([['curl', 0, 1.6, 0.05, '×'], ['spread', -10, 30, 1, '°'], ['thumb', -30, 40, 1, '°']] as const).map(([k, lo, hi, step, unit]) => (
          <div key={k} className="skel-row"><span>{k}</span>
            <input type="range" min={lo} max={hi} step={step} value={b.hand_rest[k]} disabled={!open} aria-label={`the hand's ${k}`} onChange={(e) => set({ hand_rest: { ...b.hand_rest, [k]: Number(e.target.value) } })} />
            <span className="mono">{unit === '×' ? `×${b.hand_rest[k].toFixed(2)}` : `${Math.round(b.hand_rest[k])}°`}</span><span /></div>))}
      </div>
      <div className="skel-group" data-group="poses">
        <div className="grp">Poses <Help text={`${p.name}'s own poses, fitted to this body in Animate › Clay: Pose the figure, pin what must stay, then Save for ${p.name}… One named as a starter pose (crouch, sit …) stands in for it on ${p.name}'s figures.`} /></div>
        {Object.keys(v.poses ?? {}).length ? Object.entries(v.poses).map(([n, x]) => {
          const pinned = Object.keys(x.pins ?? {}).length
          return (
            <div key={n} className="skel-row" data-pose={n}><span>{n}</span>
              <span className="hint">{POSE_NAMES.includes(n) ? 'its starter pose' : `from ${x.preset ?? 'stand'}`}{pinned ? ` · ${pinned} pinned` : ''}</span><span />
              <button type="button" className="quiet danger" title={`Delete ${p.name}'s "${n}"`}
                onClick={() => void askConfirm({ title: `Delete ${p.name}'s "${n}"?`, okLabel: 'Delete', danger: true }).then((ok) => { if (ok) void useStory.getState().deleteCharacterPose(p.id, v.id, n) })}><Trash2 size={12} /></button>
            </div>)
        }) : <div className="hint">none yet</div>}
      </div>
      {first ? <div className="skel-status warn">{first.label} {Number(b[first.factor]) > first.band[1] ? 'long' : 'short'} for an adult — check its points</div> : <div className="skel-status">every part in an adult's range</div>}
      {others.length > 0 && open && <div className="kv"><span>copy from</span>
        <select aria-label="copy the skeleton from" value="" onChange={(e) => { const o = others.find((x) => x.id === e.target.value); const ob = o?.versions.find((y) => y.id === o.current)?.body
          if (ob) set({ ...Object.fromEntries((['head', 'neck', 'torso', 'shoulders', 'hips', 'arms', 'elbow', 'legs', 'knee', 'hands', 'feet', 'head_forward', 'shoulder_drop', 'feet_out'] as const).map((k) => [k, (ob as Body)[k]])), hand_rest: { ...b.hand_rest, ...(ob as Body).hand_rest } } as Partial<Body>) }}>
          <option value="">another character…</option>{others.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></div>}
    </div>
  )
}
