// Shell-fit check (the author on char01, 2026-11-08: "the clay shell is still disproportionate to the original model … distorted hands
// and feet"): how the fitted skeleton sits in the shell it bends. The shell is placed by its picture (D140) and bound in the reference's
// stance (S4, stanceOf); the skeleton is fitted to the same picture's SDPose points by ratios (body.py fit_body). For each COCO-18 point the
// skeleton's marker against the picture's point in the figure's frame (cm); the stretch of the shell's triangles once posed (stand, walk);
// two drawings on a 2D canvas (headless Edge draws no WebGL): the bind over the picture, and the posed shell coloured by stretch. The
// browser half of engine/spikes/shell_fit.cjs (the GLB and the picture handed over as base64).
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { DEFAULT_BODY, type Body } from '../suites/stage/body'
import { applyPose, mannequin, POSES } from '../suites/stage/builders'
import { bindProxy, stanceOf, type FootShapes } from '../suites/stage/proxy'

export interface ShellFitInput { body: Body; points: { pose?: number[][]; canvas?: number[] } & Record<string, unknown>; glb: string; picture: string; stance?: Record<string, number[]> | null }

const NAMES = ['nose', 'neck', 'r_shoulder', 'r_elbow', 'r_wrist', 'l_shoulder', 'l_elbow', 'l_wrist', 'r_hip', 'r_knee', 'r_ankle', 'l_hip', 'l_knee', 'l_ankle']
const BONES: [number, number][] = [[1, 2], [2, 3], [3, 4], [1, 5], [5, 6], [6, 7], [1, 8], [8, 9], [9, 10], [1, 11], [11, 12], [12, 13], [0, 1]]

export async function shellFit(input: ShellFitInput): Promise<Record<string, unknown>> {
  const body = { ...DEFAULT_BODY, ...input.body } as Body
  const bin = Uint8Array.from(atob(input.glb), (c) => c.charCodeAt(0)).buffer
  const gltf = await new GLTFLoader().parseAsync(bin, '')
  const fb = (gltf.scene.userData?.loom2 as { figure_box?: number[] } | undefined)?.figure_box ?? null
  const stance = input.stance ?? stanceOf(input.points as never)
  const clay = new THREE.MeshLambertMaterial({ color: 0xb4b4b8 })
  const fig = mannequin(clay, POSES.stand, stance, body)
  const g = new THREE.Group(); g.add(fig.root); g.updateMatrixWorld(true)
  const feet = (body as { foot_shape?: FootShapes | null }).foot_shape
  const px = bindProxy(gltf.scene, fig.joints, fig.limbs, g, { preset: 'stand', joints: stance }, { stance, visible: true, hands: true, points: input.points as never, markers: fig.markers,
    feet: feet ? { shape: feet, size: body.feet } : null })
  g.updateMatrixWorld(true)
  const at = (o: THREE.Object3D) => o.getWorldPosition(new THREE.Vector3())
  // the picture's frame as bindProxy's pictureFrame has it: the nose on the nose marker, the soles (the figure box's bottom) on the floor
  const pose = input.points.pose ?? []
  const nose = pose[0], n = at(fig.markers[0])
  const cv = input.points.canvas, ky = fb && cv?.length === 2 ? cv[1] / fb[5] : 1
  const y1 = fb ? fb[3] * ky : NaN
  const k = n.y / (y1 - nose[1])
  const toFig = (x: number, y: number) => new THREE.Vector2(n.x + (x - nose[0]) * k, (y1 - y) * k)
  const toPic = (v: THREE.Vector3) => [nose[0] + (v.x - n.x) / k, y1 - v.y / k]
  const offsets: Record<string, unknown> = {}
  NAMES.forEach((name, i) => {
    const p = pose[i]
    if (!p || (p[2] ?? 0) < 0.3) { offsets[name] = 'not seen'; return }
    const want = toFig(p[0], p[1]), got = at(fig.markers[i])
    offsets[name] = { dx_cm: +((got.x - want.x) * 100).toFixed(1), dy_cm: +((got.y - want.y) * 100).toFixed(1), off_cm: +(Math.hypot(got.x - want.x, got.y - want.y) * 100).toFixed(1) }
  })
  // the bind's geometry (after the hands' fold), the drawing over the picture
  const bindPos = px.meshes.map((m) => (m.geometry.attributes.position as THREE.BufferAttribute).clone())
  const markersBind = fig.markers.slice(0, 14).map(at)
  const img = await createImageBitmap(await (await fetch(`data:image/png;base64,${input.picture}`)).blob())
  const S = 0.5
  const c1 = new OffscreenCanvas(Math.round(img.width * S), Math.round(img.height * S)), x1 = c1.getContext('2d')!
  x1.drawImage(img, 0, 0, c1.width, c1.height)
  x1.fillStyle = 'rgba(255,255,255,0.45)'; x1.fillRect(0, 0, c1.width, c1.height)
  x1.fillStyle = 'rgba(120,120,135,0.55)'
  for (const a of bindPos) for (let i = 0; i + 2 < a.count; i += 3) {
    x1.beginPath()
    for (let q = 0; q < 3; q++) { const [u, v] = toPic(new THREE.Vector3().fromBufferAttribute(a, i + q)); if (q) x1.lineTo(u * S, v * S); else x1.moveTo(u * S, v * S) }
    x1.fill()
  }
  const line = (ctx: OffscreenCanvasRenderingContext2D, pts: number[][], col: string, w: number) => { ctx.strokeStyle = col; ctx.lineWidth = w; for (const [a, b] of BONES) { if (!pts[a] || !pts[b]) continue; ctx.beginPath(); ctx.moveTo(pts[a][0], pts[a][1]); ctx.lineTo(pts[b][0], pts[b][1]); ctx.stroke() } }
  line(x1, pose.map((p) => (p && (p[2] ?? 0) >= 0.3 ? [p[0] * S, p[1] * S] : null)) as number[][], 'rgba(0,160,60,0.95)', 3)
  line(x1, markersBind.map((m) => toPic(m).map((v) => v * S)), 'rgba(220,30,30,0.95)', 3)
  for (const m of markersBind) { const [u, v] = toPic(m); x1.fillStyle = '#d00'; x1.beginPath(); x1.arc(u * S, v * S, 4, 0, 7); x1.fill() }
  for (const p of pose.slice(0, 14)) if (p && (p[2] ?? 0) >= 0.3) { x1.fillStyle = '#0a4'; x1.beginPath(); x1.arc(p[0] * S, p[1] * S, 4, 0, 7); x1.fill() }
  // posed: the stretch of every triangle against the bind, front and side, for stand and walk
  const stretchOf = (preset: 'stand' | 'walk') => {
    applyPose(fig.joints, POSES[preset]); px.feet(null); g.updateMatrixWorld(true)
    const tris: { p: THREE.Vector3[]; s: number; zone: string }[] = []
    const r = { hands: [] as number[], feet: [] as number[], rest: [] as number[] }
    const wristR = markersBind[4], wristL = markersBind[7], ankR = markersBind[10], ankL = markersBind[13]
    px.meshes.forEach((m, mi) => {
      const a = bindPos[mi], v = new THREE.Vector3()
      const posed: THREE.Vector3[] = []
      for (let i = 0; i < a.count; i++) { v.fromBufferAttribute(a, i); posed.push(m.applyBoneTransform(i, v.clone())) }
      for (let i = 0; i + 2 < a.count; i += 3) {
        let s = 0
        for (const [p, q] of [[i, i + 1], [i + 1, i + 2], [i + 2, i]]) {
          const b0 = new THREE.Vector3().fromBufferAttribute(a, p).distanceTo(new THREE.Vector3().fromBufferAttribute(a, q))
          if (b0 < 1e-4) continue
          s = Math.max(s, posed[p].distanceTo(posed[q]) / b0)
        }
        const c = new THREE.Vector3().fromBufferAttribute(a, i)
        const zone = Math.min(c.distanceTo(wristR), c.distanceTo(wristL)) < 0.15 ? 'hands' : Math.min(c.distanceTo(ankR), c.distanceTo(ankL)) < 0.2 || c.y < 0.15 ? 'feet' : 'rest'
        r[zone as keyof typeof r].push(s)
        tris.push({ p: [posed[i], posed[i + 1], posed[i + 2]], s, zone })
      }
    })
    const stat = (xs: number[]) => { const s = [...xs].sort((p, q) => p - q); return { n: s.length, over_1_5: +(100 * s.filter((x) => x > 1.5).length / Math.max(1, s.length)).toFixed(1), over_2: +(100 * s.filter((x) => x > 2).length / Math.max(1, s.length)).toFixed(1), p99: +(s[Math.floor(0.99 * (s.length - 1))] ?? 0).toFixed(2) } }
    return { tris, stats: { hands: stat(r.hands), feet: stat(r.feet), rest: stat(r.rest) }, marks: fig.markers.slice(0, 14).map(at) }
  }
  const W = 420, H = 560, M = H / 2.0                                        // 2 m tall in each view
  const c2 = new OffscreenCanvas(W * 4, H), x2 = c2.getContext('2d')!
  x2.fillStyle = '#fff'; x2.fillRect(0, 0, c2.width, c2.height)
  const stats: Record<string, unknown> = {}
  ;(['stand', 'walk'] as const).forEach((preset, pi) => {
    const { tris, stats: st, marks } = stretchOf(preset)
    stats[preset] = st
    for (const view of [0, 1]) {
      const ox = (pi * 2 + view) * W + W / 2, oy = H - 20
      const proj = (p: THREE.Vector3) => (view === 0 ? [ox + p.x * M, oy - p.y * M] : [ox + p.z * M, oy - p.y * M])
      const depthKey = (t: { p: THREE.Vector3[] }) => (view === 0 ? t.p[0].z : -t.p[0].x)
      for (const t of [...tris].sort((a, b) => depthKey(a) - depthKey(b))) {
        x2.fillStyle = t.s > 2 ? '#e0201a' : t.s > 1.5 ? '#f59a1a' : '#9a9aa4'
        x2.beginPath(); t.p.forEach((p, q) => { const [u, v] = proj(p); if (q) x2.lineTo(u, v); else x2.moveTo(u, v) }); x2.fill()
      }
      x2.strokeStyle = 'rgba(30,60,220,0.9)'; x2.lineWidth = 2
      for (const [a, b] of BONES) { const [u0, v0] = proj(marks[a]), [u1, v1] = proj(marks[b]); x2.beginPath(); x2.moveTo(u0, v0); x2.lineTo(u1, v1); x2.stroke() }
      x2.fillStyle = '#000'; x2.font = '16px sans-serif'; x2.fillText(`${preset} · ${view === 0 ? 'front' : 'side'}`, ox - W / 2 + 8, 20)
    }
  })
  const url = async (c: OffscreenCanvas) => { const b = await c.convertToBlob({ type: 'image/png' }); const r = new FileReader(); return await new Promise<string>((ok) => { r.onload = () => ok(String(r.result)); r.readAsDataURL(b) }) }
  return { k_mm_per_px: +(k * 1000).toFixed(3), figure_box: fb, depth_cm: +(px.depth * 100).toFixed(1), stance, offsets, stretch: stats,
    feet: Object.fromEntries(Object.entries(px.footPoints).map(([s, f]) => [s, { rigged: f!.rigged, missed_cm: +(f!.missed * 100).toFixed(1) }])),
    bind_png: await url(c1), posed_png: await url(c2) }
}
