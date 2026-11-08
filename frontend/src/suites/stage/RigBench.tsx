// RG3 (D187 R4, D188 F4; proto01_rig 00): the rigging screen's Hands and Feet & legs views — the skeleton bench's other two parts.
//   the hand picture   SDPose's 21 points over the character's hand picture, each dragged where the finger really is; let go, the hand is
//                      fitted to them on the CPU and kept (D191; the count, claws and widths stay); a hidden finger's points dimmed.
//   the clay hand      the character's own hand built on its bones (clayHand.ts), the guide's 21 points on it, tried with the presets.
//   the feet picture   the foot's big toe, small toe and heel and its ankle over the feet picture (or the A-pose side view), dragged — fitted
//                      and kept when let go (D191).
//   the shoe           the shell's foot from the side, the rig's heel, ball and toe on it: dragged onto the shoe they place it by hand (F4) —
//                      the shoe is then rigged whatever the shell's geometry (a robe, a trouser hem); tried bent at the ankle and the ball.
// The Inspector's parts: the count, the claws, each finger (Q4, Q5); the stiff sole (D189) and the foot's numbers; Unlink (Q2).
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../../api/client'
import type { Profile } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { showMenu } from '../../frame/ContextMenu'
import { Help } from '../../frame/Help'
import { useStory } from '../story/storyStore'
import type { Body } from './body'
import { mannequin, POSES, type Mannequin } from './builders'
import { FINGERS, HIDDEN, type FingerName, type HandShapes } from './clayHand'
import { HAND_PRESETS, makeDetailed, type HandPreset } from './detailed'
import { HAND_EDGES } from './passes'
import { bindProxy, FOOT_REACH, stanceOf, type FootShapes, type Proxy } from './proxy'
import { clearContent, loadOnce } from './gpu'
import { footOf, handOf, linked, moveAnkle, placeOffset, setClaw, setCount, setFinger, setFoot, type Side } from './rigEdit'
import { setUi, useUi } from './benchState'

type Version = Profile['versions'][number]
const saveBody = (b: Body) => useStory.getState().setSheet({ body: b as never })
const handsOf = (b: Body) => (b.hand_shape as HandShapes | null | undefined) ?? null
const feetOf = (b: Body) => (b.foot_shape as FootShapes | null | undefined) ?? null
const hue = (k: number) => `hsl(${Math.round((k / HAND_EDGES.length) * 360)} 95% 55%)`
const FINGER_OF = (k: number): FingerName | null => (k === 0 ? null : FINGERS[Math.floor((k - 1) / 4)])

/** D191: how many of a read's points the author moved — apart from SDPose's own by more than half a pixel. */
const apart = (pts: number[][], sd: number[][]): number => pts.filter((q, k) => sd[k] && (q[2] ?? 0) > 0 && Math.hypot(q[0] - sd[k][0], q[1] - sd[k][1]) > 0.5).length
/** D191: what the picture's foot says is kept — the points SDPose read, or how many the author moved; and how sure the read was. */
const kept = (moved: number, conf: number | undefined): string =>
  `${moved ? `${moved} point${moved === 1 ? '' : 's'} moved by hand · kept` : "SDPose's points"}${conf ? ` · read ${conf.toFixed(2)} sure` : ''}`

/** The crop of a picture around some points, padded by `pad` of their extent (at least `min` pixels a side). */
function around(pts: number[][], w: number, h: number, pad: number, min = 120): [number, number, number, number] {
  const ok = pts.filter((q) => (q[2] ?? 0) > 0)
  if (!ok.length) return [0, 0, w, h]
  const xs = ok.map((q) => q[0]), ys = ok.map((q) => q[1])
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys)
  const s = Math.max(min, x1 - x0, y1 - y0) * (1 + 2 * pad)
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2
  return [cx - s / 2, cy - s / 2, s, s]
}

/** Points dragged over a picture: an SVG in the picture's pixels, each point a circle; `onDrop` gets the moved point's index and place. */
function DragPicture({ src, w, h, view, points, edges, dim, onDrop, children, label }: { src: string; w: number; h: number; view: [number, number, number, number]; points: number[][];
  edges: [number, number, string][]; dim?: (k: number) => boolean; onDrop: (k: number, at: [number, number]) => void; children?: React.ReactNode; label: (k: number) => string }) {
  const svg = useRef<SVGSVGElement>(null)
  const [drag, setDrag] = useState<{ k: number; at: [number, number]; c0: [number, number]; moved: boolean } | null>(null)   // viewport check: a click is no drop
  const at = (e: React.PointerEvent): [number, number] => { const m = svg.current!.getScreenCTM()!.inverse(); const q = new DOMPoint(e.clientX, e.clientY).matrixTransform(m); return [q.x, q.y] }
  const r = Math.max(2, view[2] / 90)
  const pos = (k: number): number[] => (drag?.k === k ? drag.at : points[k])
  return (
    <svg ref={svg} viewBox={view.join(' ')} className="rig-pic" onPointerMove={(e) => { if (drag) setDrag({ ...drag, at: at(e), moved: drag.moved || Math.hypot(e.clientX - drag.c0[0], e.clientY - drag.c0[1]) > 3 }) }}
      onPointerUp={() => { if (drag?.moved) onDrop(drag.k, drag.at); setDrag(null) }} onPointerLeave={() => { if (drag?.moved) onDrop(drag.k, drag.at); setDrag(null) }}>
      <image href={src} x={0} y={0} width={w} height={h} />
      {children}
      {edges.map(([a, b, colour]) => points[a] && points[b] && (points[a][2] ?? 0) > 0 && (points[b][2] ?? 0) > 0
        ? <line key={`${a}-${b}`} x1={pos(a)[0]} y1={pos(a)[1]} x2={pos(b)[0]} y2={pos(b)[1]} stroke={colour} strokeWidth={r * 0.45} opacity={dim?.(b) ? 0.3 : 0.9} /> : null)}
      {points.map((q, k) => (q[2] ?? 0) > 0 && (
        <circle key={k} cx={pos(k)[0]} cy={pos(k)[1]} r={r} className={`white${dim?.(k) ? ' off' : ''}`} data-k={k}
          onPointerDown={(e) => { if (e.button !== 0) return; (e.target as Element).setPointerCapture?.(e.pointerId); setDrag({ k, at: at(e), c0: [e.clientX, e.clientY], moved: false }) }}><title>{label(k)}</title></circle>))}
    </svg>
  )
}

// ------------------------------------------------------------------ the hands
export function HandsPanes({ v, body }: { v: Version; body: Body }) {
  const u = useUi()
  const hp = v.hand_points as { hand?: number[][]; canvas?: number[]; from?: string; report?: { conf?: number }; sdpose?: number[][] } | null
  const shape = handsOf(body)
  const pts = u.handPts ?? hp?.hand ?? null
  const pic = v.hand_ref_asset_id
  const [w, h] = (hp?.canvas?.length === 2 ? hp.canvas : [1024, 1024]) as [number, number]
  const view = useMemo(() => (pts ? around(pts, w, h, 0.25) : [0, 0, w, h] as [number, number, number, number]), [pts, w, h])
  const hidden = shape ? HIDDEN[handOf(shape, 'r').count ?? 5] : []
  const edges = HAND_EDGES.map(([a, b], k) => [a, b, hue(k)] as [number, number, string])
  const stale = !!pic && hp?.from !== pic
  const moved = hp?.hand && hp.sdpose ? apart(hp.hand, hp.sdpose) : 0
  const drop = (k: number, at: [number, number]) => {                       // D191: fitted and kept as it is let go — no step to find
    if (!pts || v.state !== 'open') return
    const next = pts.map((q) => [...q]); next[k] = [Math.round(at[0] * 10) / 10, Math.round(at[1] * 10) / 10, 1]
    setUi({ handPts: next })
    void useStory.getState().refitPart('hand', { hand: next }).then((ok) => { if (!ok) setUi({ handPts: null }) })   // kept: the new read clears it
  }
  return (
    <div className="skel-panes" data-part="hands">
      <div className="skel-pane ref" aria-label="the hand picture" data-testid="rig-hand-picture"
        onContextMenu={(e) => { e.preventDefault(); showMenu(e, [{ cmd: 'cast.rig.handSdpose' }, { cmd: 'story.cast.readHand' }]) }}>
        <span className="lab">the hand picture · SDPose's points</span>
        {!pic ? <div className="hint rig-none">No hand picture — pick or make one in the panel</div>
          : !pts || stale ? <div className="hint rig-none">{stale ? 'The hand picture is not read yet' : 'No hand read'} <CommandButton id="story.cast.readHand" text /></div>
          : <div className="skel-ref"><DragPicture src={api.assetUrl(pic)} w={w} h={h} view={view} points={pts} edges={edges} dim={(k) => { const f = FINGER_OF(k); return !!f && hidden.includes(f) }}
              onDrop={drop} label={(k) => `${k === 0 ? 'the wrist' : `${FINGER_OF(k)} ${((k - 1) % 4) + 1}`} — drag where it is: the hand is fitted and kept when you let go`} /></div>}
        <div className="rig-foot">
          <CommandButton id="cast.rig.handSdpose" text />
          <span className="spacer" />
          <span className="muted" data-testid="rig-hand-kept">{u.handPts ? 'fitting…' : pts && !stale ? kept(moved, hp?.report?.conf) : ''}</span>
        </div>
      </div>
      <div className="skel-pane guide" aria-label="the clay hand" data-testid="rig-clay-hand">
        <span className="lab">{shape ? 'the clay hand · the guide\'s points' : 'the mannequin\'s hand · the guide\'s points'}</span>
        <ClayHandView body={body} side={u.side} preset={u.preset as HandPreset} />
        <div className="skel-motions" role="group" aria-label="the hand to try">
          {HAND_PRESETS.map((p) => <button key={p} type="button" className={u.preset === p ? 'active' : ''} onClick={() => setUi({ preset: p })}>{p}</button>)}
          <span className="sep" />
          {(['r', 'l'] as const).map((s) => <button key={s} type="button" className={u.side === s ? 'active' : ''} onClick={() => setUi({ side: s })} title={s === 'r' ? 'the right hand' : 'the left hand'}>{s === 'r' ? 'right' : 'left'}</button>)}
        </div>
      </div>
    </div>
  )
}

/** The character's hand in 3D: the Detailed figure in its reference's stance, its own clay hand (or the mannequin's without a shape), the
 *  guide's 21 points and their chains, from the palm; orbited with the mouse. */
function ClayHandView({ body, side, preset }: { body: Body; side: Side; preset: HandPreset }) {
  const host = useRef<HTMLDivElement>(null)
  const world = useRef<{ r: THREE.WebGLRenderer; scene: THREE.Scene; cam: THREE.PerspectiveCamera; orbit: OrbitControls; content: THREE.Group } | null>(null)
  const points = useStory((s) => s.version()?.body_points ?? null)
  useEffect(() => {
    const el = host.current!
    const r = new THREE.WebGLRenderer({ antialias: true }); r.setPixelRatio(Math.min(2, window.devicePixelRatio || 1)); el.appendChild(r.domElement)
    const scene = new THREE.Scene(); scene.background = new THREE.Color(0x1d1e22)
    scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.5)); const key = new THREE.DirectionalLight(0xffffff, 1.3); key.position.set(1, 2, 3); scene.add(key)
    const cam = new THREE.PerspectiveCamera(30, 1, 0.01, 20), orbit = new OrbitControls(cam, r.domElement), content = new THREE.Group(); scene.add(content)
    world.current = { r, scene, cam, orbit, content }
    let raf = 0
    const loop = () => { raf = requestAnimationFrame(loop); r.render(scene, cam) }
    const fit = () => { const b = el.getBoundingClientRect(); r.setSize(b.width, b.height); cam.aspect = b.width / Math.max(1, b.height); cam.updateProjectionMatrix() }
    const ro = new ResizeObserver(fit); ro.observe(el); fit(); loop()
    return () => { cancelAnimationFrame(raf); ro.disconnect(); clearContent(content); orbit.dispose(); r.dispose(); r.forceContextLoss(); r.domElement.remove(); world.current = null }   // review K61 (V82)
  }, [])
  useEffect(() => {
    const w = world.current
    if (!w) return
    let live = true
    const t = window.setTimeout(() => void (async () => {
      const { mannequinClone } = await import('./motion/mannequins')
      const clay = new THREE.MeshLambertMaterial({ color: 0xb4b4b8 })
      const stance = stanceOf(points as never)
      const fig = mannequin(clay, POSES.stand, stance, body)
      const g = new THREE.Group(); g.add(fig.root); g.updateMatrixWorld(true)
      fig.root.traverse((o) => { if ((o as THREE.Mesh).isMesh) o.visible = false })
      const { root, rig } = await mannequinClone(body.figure ?? 'female', clay)
      if (!live) return
      const d = makeDetailed(root, rig, fig.joints.root.parent!, fig.joints, fig.limbs, { hands: body.hands, feet: body.feet, head: body.head, handRest: body.hand_rest, feetOut: body.feet_out, handShape: handsOf(body) })
      d.handsOnly(true)
      d.follow(fig.joints, { ...d.handPreset('r', preset), ...d.handPreset('l', preset) }); g.updateMatrixWorld(true)
      const marks = side === 'r' ? d.wholebody?.right : d.wholebody?.left
      clearContent(w.content); w.content.add(g)                                 // review K61: the last hand, its points and chains freed
      if (!marks) return
      const pts = marks.map((m) => m.getWorldPosition(new THREE.Vector3()))
      const dotMat = new THREE.MeshBasicMaterial({ color: 0x3a8bff, depthTest: false }), offMat = new THREE.MeshBasicMaterial({ color: 0x666b77, depthTest: false })
      pts.forEach((p, i) => { const s = new THREE.Mesh(new THREE.SphereGeometry(0.003, 8, 6), marks[i].userData.hidden ? offMat : dotMat); s.position.copy(p); s.renderOrder = 10; w.content.add(s) })
      const seg: number[] = []; for (const [a, b] of HAND_EDGES) if (!marks[b].userData.hidden) seg.push(...pts[a].toArray(), ...pts[b].toArray())
      const lines = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(seg, 3)), new THREE.LineBasicMaterial({ color: 0xffc94a, depthTest: false })); lines.renderOrder = 9; w.content.add(lines)
      // D191: framed on the palm — the wrist and the knuckles, which no preset moves (a fist had pulled the camera into the fingers)
      const palm = pts[0].distanceTo(pts[9])
      const centre = pts[0].clone().lerp(pts[9], 0.9)
      const normal = pts[5].clone().sub(pts[17]).cross(pts[9].clone().sub(pts[0])).normalize()
      if (side === 'l') normal.negate()
      const reach = Math.max(0.2, palm * 4.6)
      w.cam.position.copy(centre).addScaledVector(normal, reach); w.cam.up.set(0, 1, 0); w.orbit.target.copy(centre); w.orbit.update()
    })().catch(() => undefined), 120)
    return () => { live = false; window.clearTimeout(t) }
  }, [body, side, preset, points])
  return <div ref={host} className="skel-3d" data-testid="rig-hand-3d" />
}

export function HandParts({ v }: { v: Version }) {
  const u = useUi()
  const b = useMemo(() => ({ ...(v.body ?? {}) }) as Body, [v.body])
  const open = v.state === 'open'
  const shape = handsOf(b)
  const side: Side = shape && !linked(shape) ? u.side : 'r'
  const save = (next: HandShapes) => { if (open) saveBody({ ...b, hand_shape: next as never }) }
  if (!shape) return (
    <div className="skel-group" data-group="hands">
      <div className="grp">The hands <Help text="No hand of its own: its figures and the guide take the mannequin's human hand. Read one from a hand picture (picked or made in the panel on the left), or start from a human hand and shape it here — a ghoul's long fingers, a dwarf's thick ones, a goblin's four." /></div>
      <div className="hands"><CommandButton id="cast.rig.handHuman" text /></div>
    </div>
  )
  const hand = handOf(shape, side)
  return (
    <div className="skel-group" data-group="hands" onContextMenu={(e) => { e.preventDefault(); showMenu(e, [{ cmd: 'cast.rig.handUnlink' }, { cmd: 'cast.rig.handLink' }, { sep: true }, { cmd: 'cast.rig.handClear' }]) }}>
      <div className="grp">The hands <Help text="The character's own hand, in palm lengths (the wrist to the middle finger's knuckle; its size is the body's hands factor). A finger's length is its three segments together; its width its thickness; its claw a cone past the tip (blank: the hand's). The left is the right mirrored until it is unlinked." /></div>
      {!linked(shape) && <div className="kv"><span>editing</span><span className="segmented" role="group" aria-label="which hand">{(['r', 'l'] as const).map((s) =>
        <button key={s} type="button" className={side === s ? 'active' : ''} onClick={() => setUi({ side: s })}>{s === 'r' ? 'right' : 'left'}</button>)}</span></div>}
      <div className="kv"><span>fingers</span><span className="segmented" role="group" aria-label="the finger count" data-testid="rig-count">{([5, 4, 3] as const).map((n) =>
        <button key={n} type="button" disabled={!open} className={hand.count === n ? 'active' : ''} onClick={() => save(setCount(shape, side, n))}
          title={n === 5 ? 'five: a thumb and four fingers' : n === 4 ? 'four: the pinky hidden (three fingers and a thumb)' : 'three: the ring finger and the pinky hidden'}>{n}</button>)}</span></div>
      <div className="skel-row" data-row="claw"><span>claws</span>
        <input type="range" min={0} max={0.6} step={0.01} value={hand.claw} disabled={!open} aria-label="the hand's claws" onChange={(e) => save(setClaw(shape, side, Number(e.target.value)))} />
        <span className="mono">{hand.claw ? `${hand.claw.toFixed(2)} ×` : 'none'}</span><span /></div>
      {FINGERS.filter((f) => !HIDDEN[hand.count ?? 5].includes(f)).map((f) => {
        const x = hand.fingers[f]
        if (!x) return null
        const len = x.lengths.reduce((a, s) => a + s, 0)
        return (
          <div key={f} className="rig-finger" data-finger={f}>
            <div className="skel-row"><span>{f}</span>
              <input type="range" min={0.2} max={1.6} step={0.01} value={len} disabled={!open} aria-label={`the ${f}'s length`} onChange={(e) => save(setFinger(shape, side, f, { length: Number(e.target.value) }))} />
              <span className="mono">{len.toFixed(2)} ×</span><span /></div>
            <div className="skel-row sub"><span>width</span>
              <input type="range" min={0.05} max={0.45} step={0.005} value={x.width} disabled={!open} aria-label={`the ${f}'s width`} onChange={(e) => save(setFinger(shape, side, f, { width: Number(e.target.value) }))} />
              <span className="mono">{x.width.toFixed(2)} ×</span><span /></div>
            <div className="skel-row sub" onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); save(setFinger(shape, side, f, { claw: null })) }} title="right-click: the hand's claw again"><span>claw</span>
              <input type="range" min={0} max={0.6} step={0.01} value={x.claw ?? hand.claw} disabled={!open} aria-label={`the ${f}'s claw`} onChange={(e) => save(setFinger(shape, side, f, { claw: Number(e.target.value) }))} />
              <span className="mono">{x.claw === null ? 'the hand\'s' : `${x.claw.toFixed(2)} ×`}</span><span /></div>
          </div>)
      })}
      <div className="hands"><CommandButton id="cast.rig.handUnlink" text /><CommandButton id="cast.rig.handLink" text /></div>
    </div>
  )
}

// ------------------------------------------------------------------ the feet & legs
const FOOT_EDGES: [number, number, string][] = [[2, 0, '#ffc94a'], [0, 1, '#4ad08a'], [3, 2, '#ff5ad0']]   // heel → big toe, big → small, ankle → heel

export function FeetPanes({ v, body }: { v: Version; body: Body }) {
  const u = useUi()
  const fp = v.feet_points as { foot?: number[][]; ankle?: number[] | null; leg?: number[][] | null; floor?: number | null; canvas?: number[]; from?: string; report?: { conf?: number; pitch?: number }
    sdpose?: { foot?: number[][]; ankle?: number[] | null } } | null
  const pic = v.feet_ref_asset_id ?? null                                    // D190: only the picture picked (the side view when picked as it)
  const dragged = u.footPts
  const cur = useMemo(() => dragged ?? (fp?.foot ? { foot: fp.foot, ankle: fp.ankle ?? null, leg: fp.leg ?? null, floor: fp.floor ?? null } : null), [dragged, fp])
  const pts = useMemo(() => (cur ? [...cur.foot, cur.ankle ?? [0, 0, 0]] : null), [cur])   // big toe, small toe, heel, the ankle
  const [w, h] = (fp?.canvas?.length === 2 ? fp.canvas : [1024, 1024]) as [number, number]
  const view = useMemo(() => (pts ? around(pts, w, h, 0.45, 160) : [0, 0, w, h] as [number, number, number, number]), [pts, w, h])
  const stale = !!pic && fp?.from !== pic
  const moved = fp?.foot && fp.sdpose?.foot ? apart([...fp.foot, fp.ankle ?? [0, 0, 0]], [...fp.sdpose.foot, fp.sdpose.ankle ?? [0, 0, 0]]) : 0
  const drop = (k: number, at: [number, number]) => {                       // D191: fitted and kept as it is let go
    if (!cur || v.state !== 'open') return
    const q = [Math.round(at[0] * 10) / 10, Math.round(at[1] * 10) / 10, 1]
    const next = k < 3 ? { ...cur, foot: cur.foot.map((x, i) => (i === k ? q : x)) } : { ...cur, ankle: q }
    setUi({ footPts: next })
    void useStory.getState().refitPart('feet', next as Record<string, unknown>).then((ok) => { if (!ok) setUi({ footPts: null }) })
  }
  return (
    <div className="skel-panes" data-part="feet">
      <div className="skel-pane ref" aria-label="the feet picture" data-testid="rig-feet-picture"
        onContextMenu={(e) => { e.preventDefault(); showMenu(e, [{ cmd: 'cast.rig.feetSdpose' }, { cmd: 'story.cast.readFeet' }]) }}>
        <span className="lab">{pic && pic === v.anim_ref_side_asset_id ? 'the A-pose side view' : 'the feet picture'} · SDPose's points</span>
        {!pic ? <div className="hint rig-none">No feet picture — pick or make one in the panel</div>
          : !pts || stale ? <div className="hint rig-none">{stale ? 'The feet picture is not read yet' : 'No foot read'} <CommandButton id="story.cast.readFeet" text /></div>
          : <div className="skel-ref"><DragPicture src={api.assetUrl(pic)} w={w} h={h} view={view} points={pts} edges={FOOT_EDGES}
              onDrop={drop} label={(k) => `${['the big toe', 'the small toe', 'the heel', 'the ankle'][k]} — drag where it is: the foot is fitted and kept when you let go`}>
              {cur?.floor != null && <line x1={view[0]} x2={view[0] + view[2]} y1={cur.floor} y2={cur.floor} className="rig-floor"><title>the floor the read took</title></line>}
            </DragPicture></div>}
        <div className="rig-foot">
          <CommandButton id="cast.rig.feetSdpose" text />
          <span className="spacer" />
          <span className="muted" data-testid="rig-feet-kept">{u.footPts ? 'fitting…' : pts && !stale ? `${kept(moved, fp?.report?.conf)}${fp?.report?.pitch != null ? ` · pitch ${Math.round(fp.report.pitch)}°` : ''}` : ''}</span>
        </div>
      </div>
      <div className="skel-pane guide" aria-label="the shoe on the shell" data-testid="rig-shoe">
        <span className="lab">the shoe on the shell · its heel, ball and toe</span>
        <ShoeView v={v} body={body} side={u.side} />
      </div>
    </div>
  )
}

type Bend = 'flat' | 'down' | 'up' | 'push'
const BENDS: Record<Bend, [number, number]> = { flat: [0, 0], down: [30, 0], up: [-20, 0], push: [0, 30] }

/** The shell's foot from the side: its rig's ankle, heel, ball and toe (draggable onto the shoe — a placement by hand, F4; the ankle is the
 *  skeleton's own, placed by hand as Body › side places it, D191), the shoe bent to try it; says whether the shoe is rigged and by how much
 *  the foot misses it. */
function ShoeView({ v, body, side }: { v: Version; body: Body; side: Side }) {
  const host = useRef<HTMLDivElement>(null)
  const [bend, setBend] = useState<Bend>('flat')
  const [state, setState] = useState<{ rigged: boolean; missed: number; placed: boolean; ankle: boolean } | null>(null)
  const world = useRef<{ r: THREE.WebGLRenderer; scene: THREE.Scene; cam: THREE.PerspectiveCamera; orbit: OrbitControls; content: THREE.Group; balls: Map<string, THREE.Mesh>;
    ankle: THREE.Vector3 | null; fig: Mannequin | null; feet: ((extra: Record<string, number[]> | null) => void) | null; px: Proxy | null } | null>(null)
  const glb = useRef<{ id: string; p: Promise<THREE.Object3D> } | null>(null)            // review K61: the shell parsed once, not on every rebuild
  const bodyRef = useRef(body); useEffect(() => { bodyRef.current = body }, [body])
  const sideRef = useRef(side); useEffect(() => { sideRef.current = side }, [side])
  const shell = v.shell_asset_id ?? null
  const points = v.body_points ?? null
  useEffect(() => {
    const el = host.current!
    const r = new THREE.WebGLRenderer({ antialias: true }); r.setPixelRatio(Math.min(2, window.devicePixelRatio || 1)); el.appendChild(r.domElement)
    const scene = new THREE.Scene(); scene.background = new THREE.Color(0x1d1e22)
    scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.5)); const key = new THREE.DirectionalLight(0xffffff, 1.3); key.position.set(-2, 3, 1); scene.add(key)
    scene.add(new THREE.GridHelper(2, 20, 0x555a66, 0x33363d))
    const cam = new THREE.PerspectiveCamera(30, 1, 0.01, 20), orbit = new OrbitControls(cam, r.domElement), content = new THREE.Group(); scene.add(content)
    const w: NonNullable<typeof world.current> = { r, scene, cam, orbit, content, balls: new Map(), ankle: null, fig: null, feet: null, px: null }
    world.current = w
    let raf = 0
    const loop = () => { raf = requestAnimationFrame(loop); r.render(scene, cam) }
    const fit = () => { const b = el.getBoundingClientRect(); r.setSize(b.width, b.height); cam.aspect = b.width / Math.max(1, b.height); cam.updateProjectionMatrix() }
    const ro = new ResizeObserver(fit); ro.observe(el); fit(); loop()
    // F4: a heel, ball or toe dragged on the view's plane — the three written as the foot's placement by hand, metres from the ankle
    const ray = new THREE.Raycaster(), plane = new THREE.Plane(), hit = new THREE.Vector3()
    let drag: { ball: THREE.Mesh; moved: boolean; start: [number, number] } | null = null
    const ndc = (e: PointerEvent) => { const b = r.domElement.getBoundingClientRect(); return new THREE.Vector2(((e.clientX - b.left) / b.width) * 2 - 1, -((e.clientY - b.top) / b.height) * 2 + 1) }
    const down = (e: PointerEvent) => {
      if (e.button !== 0) return
      ray.setFromCamera(ndc(e), cam)
      const got = ray.intersectObjects([...w.balls.values()], false)[0]
      if (!got) return
      drag = { ball: got.object as THREE.Mesh, moved: false, start: [e.clientX, e.clientY] }
      plane.setFromNormalAndCoplanarPoint(cam.getWorldDirection(new THREE.Vector3()), got.object.position)
      orbit.enabled = false; r.domElement.setPointerCapture(e.pointerId)
    }
    const move = (e: PointerEvent) => {
      if (!drag) return
      if (!drag.moved && Math.hypot(e.clientX - drag.start[0], e.clientY - drag.start[1]) < 3) return
      drag.moved = true; ray.setFromCamera(ndc(e), cam)
      if (ray.ray.intersectPlane(plane, hit)) drag.ball.position.copy(hit)
    }
    const up = (e: PointerEvent) => {
      if (!drag) return
      const d = drag; drag = null; orbit.enabled = true
      if (r.domElement.hasPointerCapture(e.pointerId)) r.domElement.releasePointerCapture(e.pointerId)
      const f = feetOf(bodyRef.current), A = w.ankle
      if (!d.moved || !A) return
      const s = sideRef.current, a = A.toArray() as [number, number, number]
      if (d.ball.userData.key === 'ankle') {                                   // D191: the skeleton's ankle placed by hand
        const fig = w.fig
        if (!fig) return
        const toLocal = (k: Side, move: number[]) => { const m = fig.markers[k === 'r' ? 10 : 13], at = m.getWorldPosition(new THREE.Vector3())
          return m.parent!.worldToLocal(at.clone().add(new THREE.Vector3(...move))).sub(m.parent!.worldToLocal(at.clone())).toArray() }
        saveBody(moveAnkle(bodyRef.current, s, d.ball.position.clone().sub(A).toArray(), toLocal)); return
      }
      if (!f) return
      const place = Object.fromEntries((['heel', 'ball', 'toe'] as const).map((k) => [k, placeOffset(w.balls.get(k)!.position.toArray() as [number, number, number], a, s, linked(f))]))
      saveBody({ ...bodyRef.current, foot_shape: setFoot(f, s, { place: place as never }) as never })
    }
    r.domElement.addEventListener('pointerdown', down); r.domElement.addEventListener('pointermove', move); r.domElement.addEventListener('pointerup', up)
    return () => { cancelAnimationFrame(raf); ro.disconnect(); r.domElement.removeEventListener('pointerdown', down); r.domElement.removeEventListener('pointermove', move); r.domElement.removeEventListener('pointerup', up)
      w.px?.dispose(); clearContent(content); orbit.dispose(); r.dispose(); r.forceContextLoss(); r.domElement.remove(); world.current = null }   // review K61 (V82)
  }, [])
  useEffect(() => {
    const w = world.current
    if (!w || !shell) return
    let live = true
    const t = window.setTimeout(() => void (async () => {
      const model = await loadOnce(glb, shell, (id) => new GLTFLoader().loadAsync(api.assetUrl(id)).then((gltf) => gltf.scene))   // review K61: parsed once
      if (!live) return
      const clay = new THREE.MeshLambertMaterial({ color: 0xb4b4b8, transparent: true, opacity: 0.5, depthWrite: false })   // see-through: a hem or a robe hides no shoe
      const stance = stanceOf(points as never)
      const fig = mannequin(clay, POSES.stand, stance, body)
      const g = new THREE.Group(); g.add(fig.root); g.updateMatrixWorld(true)
      fig.root.traverse((o) => { if ((o as THREE.Mesh).isMesh) o.visible = false })
      const f = feetOf(body)
      const px = bindProxy(model, fig.joints, fig.limbs, g, { preset: 'stand', joints: stance }, { stance, visible: true, hands: true, points: points as never, markers: fig.markers, feet: f ? { shape: f, size: body.feet } : null })
      w.px?.dispose(); clearContent(w.content); w.balls.clear(); w.content.add(g)   // review K61: the last mannequin, shell and balls freed
      w.px = px
      for (const m of px.meshes) { m.material = clay; w.content.add(m) }
      w.feet = px.feet; w.fig = fig
      const fpt = px.footPoints[side]
      const A = (fpt?.ankle ?? fig.markers[side === 'r' ? 10 : 13].getWorldPosition(new THREE.Vector3())).clone()
      w.ankle = A
      const ball = (key: string, at: THREE.Vector3, colour: number, size = 0.012) => { const m = new THREE.Mesh(new THREE.SphereGeometry(size, 12, 8), new THREE.MeshBasicMaterial({ color: colour, depthTest: false })); m.position.copy(at); m.renderOrder = 5; m.userData.key = key; w.content.add(m); return m }
      w.balls.set('ankle', ball('ankle', A, body.joint_offsets?.[`${side}_ankle`] ? 0xe8c46a : 0x8fd3a8, 0.01))   // D191: dragged too (D183's colours)
      if (fpt) for (const [k, colour] of [['heel', 0xff5ad0], ['ball', 0xffc94a], ['toe', 0x3a8bff]] as const) { const at = k === 'ball' ? fpt.ball ?? fpt.heel.clone().lerp(fpt.toe, 0.72) : fpt[k]; w.balls.set(k, ball(k, at, colour)) }
      ;(window as unknown as { __loom2RigShoe?: unknown }).__loom2RigShoe = { screen: (key: string): [number, number] | null => {   // the driver's: a point's place on the page
        const o = w.balls.get(key)
        if (!o) return null
        const b = w.r.domElement.getBoundingClientRect(), q = o.position.clone().project(w.cam)
        return [b.left + ((q.x + 1) / 2) * b.width, b.top + ((1 - q.y) / 2) * b.height] } }
      const [ea, eb] = BENDS[bend]
      px.feet({ [`${side}_ankle`]: [ea, 0, 0], [`${side}_ball`]: [eb, 0, 0] }); g.updateMatrixWorld(true)
      const toeAt = fpt?.toe ?? A.clone().add(new THREE.Vector3(0, -A.y, 0.2))
      const target = A.clone().lerp(toeAt, 0.5).setY(Math.max(0.03, A.y * 0.6))      // the foot's middle
      const out = side === 'r' ? -1 : 1                                          // from the foot's own side, a little ahead: its sideways place shows
      w.cam.position.copy(target).add(new THREE.Vector3(out * 0.85, 0.22, 0.4)); w.cam.up.set(0, 1, 0); w.orbit.target.copy(target); w.orbit.update()
      const own = f ? footOf(f, side) : null
      setState(fpt ? { rigged: fpt.rigged, missed: fpt.missed, placed: !!own?.place, ankle: !!body.joint_offsets?.[`${side}_ankle`] } : null)
    })().catch(() => undefined), 150)
    return () => { live = false; window.clearTimeout(t) }
  }, [body, side, shell, points, bend])
  if (!shell) return <div className="hint rig-none">No shell yet — the shoe is the shell's own <CommandButton id="cast.shell.make" text /></div>
  const f = feetOf(body)
  return (
    <>
      <div ref={host} className="skel-3d" data-testid="rig-shoe-3d" />
      <div className="skel-motions" role="group" aria-label="the shoe bent">
        {(['flat', 'down', 'up', 'push'] as const).map((k) => <button key={k} type="button" className={bend === k ? 'active' : ''} onClick={() => setBend(k)}
          title={k === 'flat' ? 'as it stands' : k === 'down' ? 'toes down 30° at the ankle' : k === 'up' ? 'toes up 20° at the ankle' : 'the toes bent up 30° at the ball (a step\'s push-off)'}>{k === 'push' ? 'push-off' : k === 'down' ? 'toes down' : k === 'up' ? 'toes up' : 'flat'}</button>)}
        <span className="sep" />
        {(['r', 'l'] as const).map((s) => <button key={s} type="button" className={side === s ? 'active' : ''} onClick={() => setUi({ side: s })}>{s === 'r' ? 'right' : 'left'}</button>)}
      </div>
      <span className={`hint${state && (!state.rigged || (state.placed && state.missed > FOOT_REACH)) ? ' warn' : ''}`} data-testid="rig-shoe-state" data-rigged={state?.rigged ? '1' : '0'}>
        {!f ? 'no foot of its own — the shoe rides on the shin' : !state ? 'binding…'
          : state.rigged ? (state.placed ? (state.missed > FOOT_REACH ? `placed by hand ${Math.round(state.missed * 100)} cm off the shoe — drag them onto it or Find the foot again` : 'rigged · placed by hand') : 'rigged')
          : `the foot misses the shoe by ${Math.round(state.missed * 100)} cm — drag its heel, ball and toe onto it`}{state?.ankle ? ' · the ankle placed by hand' : ''}
      </span>
    </>
  )
}

export function FeetParts({ v }: { v: Version }) {
  const u = useUi()
  const b = useMemo(() => ({ ...(v.body ?? {}) }) as Body, [v.body])
  const open = v.state === 'open'
  const shape = feetOf(b)
  const side: Side = shape && !linked(shape) ? u.side : 'r'
  if (!shape) return (
    <div className="skel-group" data-group="feet">
      <div className="grp">The feet <Help text="No foot of its own: the shoe rides on the shin and the guide's feet are the mannequin's. Read one from a feet picture (picked or made in the panel on the left — the A-pose side view may be picked as one), or start from a plain foot and place it on the shoe by hand." /></div>
      <div className="hands"><CommandButton id="cast.rig.feetPlain" text /></div>
    </div>
  )
  const foot = footOf(shape, side)
  const save = (patch: Parameters<typeof setFoot>[2]) => { if (open) saveBody({ ...b, foot_shape: setFoot(shape, side, patch) as never }) }
  return (
    <div className="skel-group" data-group="feet" onContextMenu={(e) => { e.preventDefault(); showMenu(e, [{ cmd: 'cast.rig.feetUnlink' }, { cmd: 'cast.rig.feetLink' }, { cmd: 'cast.rig.placeReset' }, { sep: true }, { cmd: 'cast.rig.feetClear' }]) }}>
      <div className="grp">The feet <Help text="The character's own foot, in foot lengths (the heel to the toe), seen from the side. A stiff sole (a boot, a clog) bends at the ankle only. Placed by hand, the heel, ball and toe sit where you dragged them on the shoe; otherwise they are found from these numbers and the shell. The left is the right mirrored until it is unlinked." /></div>
      {!linked(shape) && <div className="kv"><span>editing</span><span className="segmented" role="group" aria-label="which foot">{(['r', 'l'] as const).map((s) =>
        <button key={s} type="button" className={side === s ? 'active' : ''} onClick={() => setUi({ side: s })}>{s === 'r' ? 'right' : 'left'}</button>)}</span></div>}
      <div className="kv"><span>sole</span><span className="segmented" role="group" aria-label="the sole" data-testid="rig-sole">
        <button type="button" disabled={!open} className={!foot.stiff ? 'active' : ''} onClick={() => save({ stiff: false })} title="it bends at the ankle and rolls on the ball">bends</button>
        <button type="button" disabled={!open} className={foot.stiff ? 'active' : ''} onClick={() => save({ stiff: true })} title="a stiff sole (a boot, a clog): it bends at the ankle only">stiff</button></span></div>
      {([['ankle_at', 'ankle along', -0.2, 0.6], ['heel_up', 'heel up', 0, 1], ['toe_up', 'toe up', 0, 0.6], ['ball_at', 'ball along', 0.5, 0.9]] as const).map(([k, label, lo, hi]) => (
        <div key={k} className="skel-row" data-row={k}><span>{label}</span>
          <input type="range" min={lo} max={hi} step={0.01} value={Number(foot[k])} disabled={!open || !!foot.place} aria-label={`the foot's ${label}`} onChange={(e) => save({ [k]: Number(e.target.value) })} />
          <span className="mono">{Number(foot[k]).toFixed(2)} ×</span><span /></div>))}
      <div className="kv"><span>placed</span><span>{foot.place ? 'by hand on the shoe' : 'from these and the shell'}</span></div>
      <div className="hands"><CommandButton id="cast.rig.placeReset" text /><CommandButton id="cast.rig.feetUnlink" text /><CommandButton id="cast.rig.feetLink" text /></div>
    </div>
  )
}
