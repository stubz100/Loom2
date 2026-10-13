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
    vertexShader: 'varying float vZ; void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.0); vZ = -mv.z; gl_Position = projectionMatrix * mv; }',
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
export function drawPose(keypoints: Keypoint[][], w: number, h: number): HTMLCanvasElement {
  const c = document.createElement('canvas'); c.width = w; c.height = h
  const g = c.getContext('2d')!
  g.fillStyle = '#000'; g.fillRect(0, 0, w, h)
  const r = Math.max(3, Math.round(Math.min(w, h) / 180))                               // the stroke scales with the frame (4 px at 720)
  for (const kp of keypoints) {
    LIMBS.forEach(([a, b], k) => {
      if (!kp[a]?.[2] || !kp[b]?.[2]) return
      const [x1, y1] = kp[a], [x2, y2] = kp[b]
      g.save(); g.globalAlpha = 0.6; g.fillStyle = `rgb(${COLOURS[k].join(',')})`
      g.translate((x1 + x2) / 2, (y1 + y2) / 2); g.rotate(Math.atan2(y2 - y1, x2 - x1))
      g.beginPath(); g.ellipse(0, 0, Math.hypot(x2 - x1, y2 - y1) / 2, r, 0, 0, Math.PI * 2); g.fill(); g.restore()
    })
    kp.forEach(([x, y, v], k) => { if (!v) return; g.fillStyle = `rgb(${COLOURS[k].join(',')})`; g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill() })
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
