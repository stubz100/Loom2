// P13 / ST3 (D81, 16 §7): the pure parts of the passes a camera renders — the COCO-18 projection (OpenPose order), the skeleton drawing
// as the ControlNet preprocessors draw it, the per-image depth range (linear disparity around the subject, as E10 measured), the flat
// mask colours with their legend. The engine renders with them (engine.ts renderPasses); the maths is tested here (passes.test.ts).
import * as THREE from 'three'

export const PASS_NAMES = ['clay', 'depth', 'normal', 'pose', 'mask'] as const
export type PassName = (typeof PASS_NAMES)[number]
/** One keypoint: x, y in pass pixels and 1 when it is in front of the camera and inside the frame. */
export type Keypoint = [number, number, number]

export const COCO = ['nose', 'neck', 'r_shoulder', 'r_elbow', 'r_wrist', 'l_shoulder', 'l_elbow', 'l_wrist', 'r_hip', 'r_knee', 'r_ankle', 'l_hip', 'l_knee', 'l_ankle', 'r_eye', 'l_eye', 'r_ear', 'l_ear'] as const
export const LIMBS: [number, number][] = [[1, 2], [1, 5], [2, 3], [3, 4], [5, 6], [6, 7], [1, 8], [8, 9], [9, 10], [1, 11], [11, 12], [12, 13], [1, 0], [0, 14], [14, 16], [0, 15], [15, 17]]
export const COLOURS: [number, number, number][] = [[255, 0, 0], [255, 85, 0], [255, 170, 0], [255, 255, 0], [170, 255, 0], [85, 255, 0], [0, 255, 0], [0, 255, 85], [0, 255, 170], [0, 255, 255], [0, 170, 255], [0, 85, 255], [0, 0, 255], [85, 0, 255], [170, 0, 255], [255, 0, 255], [255, 0, 170], [255, 0, 85]]

/** Linear disparity (1/z) between near and far, white near — what the depth ControlNets were trained on. */
export function depthMaterial(): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: { near: { value: 1.0 }, far: { value: 20.0 } },
    // CA1: three's skinning chunks, so a skinned figure (the Detailed dummy) is drawn as posed, not in its bind pose; inert for plain meshes
    vertexShader: `#include <common>
#include <skinning_pars_vertex>
varying float vZ;
void main(){
#include <skinbase_vertex>
#include <begin_vertex>
#include <skinning_vertex>
#include <project_vertex>
vZ = -mvPosition.z;
}`,
    fragmentShader: 'uniform float near; uniform float far; varying float vZ; void main(){ float d = clamp((1.0 / max(vZ, near) - 1.0 / far) / (1.0 / near - 1.0 / far), 0.0, 1.0); gl_FragColor = vec4(vec3(d), 1.0); }',
  })
}

/** The depth range for a camera at `dist` from its target: the subject mid-grey, the foreground bright (E10's per-scene normalisation). */
export function depthRange(dist: number): { near: number; far: number } {
  return { near: Math.max(0.3, dist * 0.6), far: Math.max(1, dist * 3) }
}

/** World points → pass pixels through a camera; visible when in front of it and inside the frame. */
export function projectPoints(points: THREE.Vector3[][], cam: THREE.Camera, w: number, h: number): Keypoint[][] {
  return points.map((ps) => ps.map((p) => {
    const v = p.clone().project(cam)
    const x = ((v.x + 1) / 2) * w, y = ((1 - v.y) / 2) * h
    return [Math.round(x * 10) / 10, Math.round(y * 10) / 10, v.z < 1 && v.z > -1 && x >= 0 && x < w && y >= 0 && y < h ? 1 : 0]
  }))
}

/** Each figure's 18 markers (world positions after updateMatrixWorld) projected. */
export function projectMarkers(markers: THREE.Object3D[][], cam: THREE.Camera, w: number, h: number): Keypoint[][] {
  return projectPoints(markers.map((ms) => ms.map((m) => m.getWorldPosition(new THREE.Vector3()))), cam, w, h)
}

/** OpenPose COCO-18 as the ControlNet preprocessors draw it: limbs as soft ellipses, joints as dots, on black. */
/** D101 (spike E25): a Detailed figure's hands and feet for the pose pass — COCO-WholeBody's feet (left big toe, small toe, heel, then the
 *  right's) and OpenPose's 21 hand points per hand (wrist; thumb, index, middle, ring, pinky from the knuckle to the tip). */
export interface WholeBody { feet: Keypoint[]; left: Keypoint[]; right: Keypoint[] }
export const HAND_EDGES: [number, number][] = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [0, 9], [9, 10], [10, 11], [11, 12],
  [0, 13], [13, 14], [14, 15], [15, 16], [0, 17], [17, 18], [18, 19], [19, 20]]
/** HSV (h in 0–1, full saturation and value) as RGB — DWPose's hand edge colours. */
const hue = (h: number): [number, number, number] => {
  const i = Math.floor(h * 6), f = h * 6 - i, q = 1 - f
  const [r, g, b] = [[1, f, 0], [q, 1, 0], [0, 1, f], [0, q, 1], [f, 0, 1], [1, 0, q]][i % 6]
  return [Math.round(r * 255), Math.round(g * 255), Math.round(b * 255)]
}

/** D158 (E42): a figure with its back to the camera — its right eye on the image's right of its left one (the head's own facing), or, an eye
 *  out of frame, its right shoulder right of its left. The server's twin is finals.faces_away. */
export function facesAway(kp: Keypoint[]): boolean {
  const re = kp[14], le = kp[15]
  if (re?.[2] && le?.[2]) return re[0] > le[0]
  const rs = kp[2], ls = kp[5]
  return !!(rs?.[2] && ls?.[2] && rs[0] > ls[0])
}
/** D166 (E44): a head read by its ears before its eyes — the ears' spread against the nose–neck length: under 0.25 a side profile (neither
 *  front nor away), under 0.6 with the eyes mirrored a profile turned away, else D158's away / front; the near side is the one the nose
 *  points to (facing the image's right shows the figure's right). Without the nose, the neck and both ears, D158 decides. The server's twin
 *  is finals.head_facing. */
export type HeadFacing = 'front' | 'away' | 'side' | 'away_profile'
export function headFacing(kp: Keypoint[]): { kind: HeadFacing; near: 'right' | 'left' } {
  const mirrored = facesAway(kp)
  const [nose, neck, er, el] = [kp[0], kp[1], kp[16], kp[17]]
  if (!(nose?.[2] && neck?.[2] && er?.[2] && el?.[2])) return { kind: mirrored ? 'away' : 'front', near: 'right' }
  const r = Math.abs(er[0] - el[0]) / Math.max(1e-6, Math.hypot(nose[0] - neck[0], nose[1] - neck[1]))
  const near = nose[0] > (er[0] + el[0]) / 2 ? 'right' : 'left'
  if (r < 0.25) return { kind: 'side', near }
  if (r < 0.6 && mirrored) return { kind: 'away_profile', near }
  return { kind: mirrored ? 'away' : 'front', near }
}
/** D158 / D166: the points the pose pass draws — only the head points a camera would see, as DWPose finds them on a real head. Away: no
 *  nose and no eyes (nor their limbs), the neck, the shoulders and the ears stay (Wan drew a face on the back of a head, E42); a side
 *  profile: the nose, the near eye and the near ear; a profile turned away: the nose and the near ear (two ear dots invited a face, E44). */
export function drawnPoints(kp: Keypoint[]): Keypoint[] {
  const { kind, near } = headFacing(kp)
  const [farEye, farEar] = near === 'right' ? [15, 17] : [14, 16]
  const hide = kind === 'away' ? [0, 14, 15] : kind === 'side' ? [farEye, farEar] : kind === 'away_profile' ? [14, 15, farEar] : []
  if (!hide.length) return kp
  return kp.map((p, i) => (hide.includes(i) ? [p[0], p[1], 0] : p))
}

export function drawPose(keypoints: Keypoint[][], w: number, h: number, wholebody?: (WholeBody | null)[]): HTMLCanvasElement {
  const c = document.createElement('canvas'); c.width = w; c.height = h
  const g = c.getContext('2d')!
  g.fillStyle = '#000'; g.fillRect(0, 0, w, h)
  const r = Math.max(3, Math.round(Math.min(w, h) / 180))                               // the stroke scales with the frame (4 px at 720)
  for (const all of keypoints) {
    const kp = drawnPoints(all)
    LIMBS.forEach(([a, b], k) => {
      if (!kp[a]?.[2] || !kp[b]?.[2]) return
      const [x1, y1] = kp[a], [x2, y2] = kp[b]
      g.save(); g.globalAlpha = 0.6; g.fillStyle = `rgb(${COLOURS[k].join(',')})`
      g.translate((x1 + x2) / 2, (y1 + y2) / 2); g.rotate(Math.atan2(y2 - y1, x2 - x1))
      g.beginPath(); g.ellipse(0, 0, Math.hypot(x2 - x1, y2 - y1) / 2, r, 0, 0, Math.PI * 2); g.fill(); g.restore()
    })
    kp.forEach(([x, y, v], k) => { if (!v) return; g.fillStyle = `rgb(${COLOURS[k].join(',')})`; g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill() })
  }
  // D101: the Detailed figures' feet (dots in the body's first six colours) and hands (rainbow edges, blue dots), as DWPose draws them
  const handLine = Math.max(1, Math.round(r / 2))
  for (const wb of wholebody ?? []) {
    if (!wb) continue
    wb.feet.forEach(([x, y, v], k) => { if (!v) return; g.fillStyle = `rgb(${COLOURS[k].join(',')})`; g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill() })
    for (const hand of [wb.right, wb.left]) {
      HAND_EDGES.forEach(([a, b], k) => {
        if (!hand[a]?.[2] || !hand[b]?.[2]) return
        g.strokeStyle = `rgb(${hue(k / HAND_EDGES.length).join(',')})`; g.lineWidth = handLine
        g.beginPath(); g.moveTo(hand[a][0], hand[a][1]); g.lineTo(hand[b][0], hand[b][1]); g.stroke()
      })
      g.fillStyle = 'rgb(0,0,255)'
      for (const [x, y, v] of hand) { if (!v) continue; g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill() }
    }
  }
  return c
}

export function hslToHex(h: number, s: number, l: number): string {
  const k = (n: number) => (n + h / 30) % 12
  const a = s * Math.min(l, 1 - l)
  const f = (n: number) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)))
  return '#' + [f(0), f(8), f(4)].map((v) => Math.round(v * 255).toString(16).padStart(2, '0')).join('')
}

/** A flat, saturated colour per object index (golden-angle hues, so neighbours never resemble each other); black is the background. */
export function maskColour(i: number): string {
  return hslToHex((i * 137.508) % 360, 1, i % 2 ? 0.35 : 0.55)
}

/** A canvas as a PNG blob. */
export function toBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((res, rej) => canvas.toBlob((b) => (b ? res(b) : rej(new Error('the pass could not be encoded'))), 'image/png'))
}
