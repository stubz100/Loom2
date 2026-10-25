// CS2 (proto01_UIcast 03 §3.2, 06 §2.4; D136 U17): the skeleton bench's arithmetic, kept out of the views so the tests can hold it.
//   · the picture ↔ the figure: a similarity by the nose and the ankles' middle (the front view), both ways;
//   · the panel's rows: each part a length in centimetres at the figure's height (the factor in its tooltip), an adult's range, whether the
//     fit sets it;
//   · a blue point dragged on the reference: the part it ends set to where it was dropped (the bench locks it).
import { BUILD_WIDTH, DEFAULT_BODY, ELBOW_AT, KNEE_AT, bodyDims, type Body } from './body'

export type XY = [number, number]
/** The points the body was fitted to (ProfileVersion.body_points): rows of [x, y, confidence] in the picture's pixels. */
export interface Points { canvas?: number[]; pose: number[][]; hand_left?: number[][]; hand_right?: number[][]; feet?: number[][] }

/** COCO-18's names, in OpenPose's order (the pose pass and SDPose share it). */
export const COCO = ['nose', 'neck', 'r_shoulder', 'r_elbow', 'r_wrist', 'l_shoulder', 'l_elbow', 'l_wrist', 'r_hip', 'r_knee', 'r_ankle', 'l_hip', 'l_knee', 'l_ankle', 'r_eye', 'l_eye', 'r_ear', 'l_ear'] as const
export const seen = (p: number[] | undefined) => !!p && (p[2] ?? 0) >= 0.3

/** The similarity between the picture (y down) and the figure's front plane (y up; facing the camera, its x runs as the picture's), by the
 *  nose and the ankles' middle. `fig` are the figure's 18 markers' (x, y). Null when either lacks those points. */
export function pictureMap(pose: number[][], fig: XY[]): { toFig: (p: XY) => XY; toPic: (f: XY) => XY; scale: number } | null {
  if (!seen(pose[0]) || !seen(pose[10]) || !seen(pose[13]) || fig.length < 14) return null
  const aP: XY = [(pose[10][0] + pose[13][0]) / 2, (pose[10][1] + pose[13][1]) / 2], aF: XY = [(fig[10][0] + fig[13][0]) / 2, (fig[10][1] + fig[13][1]) / 2]
  const hP = Math.hypot(pose[0][0] - aP[0], pose[0][1] - aP[1]), hF = Math.hypot(fig[0][0] - aF[0], fig[0][1] - aF[1])
  if (hP < 1e-6 || hF < 1e-9) return null
  const s = hF / hP
  return { scale: s, toFig: ([x, y]) => [aF[0] + (x - aP[0]) * s, aF[1] - (y - aP[1]) * s], toPic: ([x, y]) => [aP[0] + (x - aF[0]) / s, aP[1] - (y - aF[1]) / s] }
}

/** The pairs (SDPose's point, the figure's marker, in the picture's pixels) more than `limit` of the height apart — the bench's red ticks. */
export function disagreements(pose: number[][], fig: XY[], limit = 0.03): { k: number; at: XY; fig: XY; off: number }[] {
  const m = pictureMap(pose, fig)
  if (!m) return []
  const h = Math.hypot(pose[0][0] - (pose[10][0] + pose[13][0]) / 2, pose[0][1] - (pose[10][1] + pose[13][1]) / 2)
  const out: { k: number; at: XY; fig: XY; off: number }[] = []
  fig.forEach((f, k) => {
    if (!seen(pose[k])) return
    const q = m.toPic(f), off = Math.hypot(q[0] - pose[k][0], q[1] - pose[k][1]) / h
    if (off > limit) out.push({ k, at: [pose[k][0], pose[k][1]], fig: q, off })
  })
  return out
}

/** The reference cropped to the figure: its points' box (the body's, the hands' and the feet's) with a margin of 8 % of the figure's
 *  height, kept inside the picture — the pane's viewBox [x, y, w, h]. Null without a whole figure. */
export function cropOf(p: Points, w: number, h: number): [number, number, number, number] | null {
  const all = [...p.pose, ...(p.hand_left ?? []), ...(p.hand_right ?? []), ...(p.feet ?? [])].filter(seen)
  if (all.length < 4) return null
  const xs = all.map((q) => q[0]), ys = all.map((q) => q[1])
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys)
  const m = 0.08 * (y1 - y0) + 8
  const cx0 = Math.max(0, x0 - m), cy0 = Math.max(0, y0 - 1.6 * m), cx1 = Math.min(w, x1 + m), cy1 = Math.min(h, y1 + m)   // more over the head (the hair)
  return [Math.round(cx0), Math.round(cy0), Math.round(cx1 - cx0), Math.round(cy1 - cy0)]
}

// ---- the panel's rows ---------------------------------------------------------------------------------------------------------------
export type RowKey = 'head' | 'neck' | 'torso' | 'shoulders' | 'hips' | 'upper_arm' | 'forearm' | 'thigh' | 'shin' | 'hands' | 'feet'
export interface Row { key: RowKey; label: string; factor: keyof Body; band: [number, number]; group: string }
/** The parts in the panel's order: the factor each row moves, an adult's range of it (a row outside turns amber, nothing blocks). */
export const ROWS: Row[] = [
  { key: 'head', label: 'head size', factor: 'head', band: [0.85, 1.15], group: 'Head and neck' },
  { key: 'neck', label: 'neck length', factor: 'neck', band: [0.75, 1.3], group: 'Head and neck' },
  { key: 'torso', label: 'torso length', factor: 'torso', band: [0.88, 1.15], group: 'Torso' },
  { key: 'shoulders', label: 'shoulder width', factor: 'shoulders', band: [0.85, 1.15], group: 'Torso' },
  { key: 'hips', label: 'hip width', factor: 'hips', band: [0.85, 1.2], group: 'Torso' },
  { key: 'upper_arm', label: 'upper arm', factor: 'elbow', band: [0.48, 0.56], group: 'Arms' },
  { key: 'forearm', label: 'arm length', factor: 'arms', band: [0.9, 1.1], group: 'Arms' },
  { key: 'thigh', label: 'thigh', factor: 'knee', band: [0.47, 0.54], group: 'Legs' },
  { key: 'shin', label: 'leg length', factor: 'legs', band: [0.9, 1.1], group: 'Legs' },
  { key: 'hands', label: 'hand size', factor: 'hands', band: [0.85, 1.15], group: 'Hands' },
  { key: 'feet', label: 'foot size', factor: 'feet', band: [0.85, 1.15], group: 'Feet' },
]
/** The factors the fit sets (body.py fit_body's unknowns) — the rows a lock keeps. */
export const FITTED: (keyof Body)[] = ['head', 'neck', 'torso', 'shoulders', 'hips', 'arms', 'elbow', 'legs', 'knee', 'hands', 'feet']

/** A row's length in centimetres at the figure's height (builders.ts's dimensions, scaled to it). */
export function lengthCm(b: Body, key: RowKey): number {
  const d = bodyDims(b), s = d.scale, w = BUILD_WIDTH[b.build] ?? 1
  const leg = d.limbs.thigh + d.limbs.shin
  const m = {
    head: 0.242 * b.head, neck: 0.12 * (b.neck ?? 1), torso: 0.44 * b.torso, shoulders: 2 * 0.21 * b.shoulders * (0.5 + 0.5 * w), hips: 0.2 * w * (b.hips ?? 1),
    upper_arm: d.limbs.upper_arm, forearm: d.limbs.forearm, thigh: d.limbs.thigh, shin: d.limbs.shin,
    hands: 0.147 * leg * (b.hands ?? 1) * (b.figure === 'male' ? 1.848 : 1.908), feet: 0.3 * leg * (b.feet ?? 1),   // the Detailed hand wrist → the middle fingertip (its palm × 1.91 / 1.85, measured on Stage, D140); the Detailed foot per leg
  }[key]
  return Math.round(m * s * 1000) / 10
}

export const outside = (b: Body, r: Row) => { const v = Number(b[r.factor] ?? 1); return v < r.band[0] || v > r.band[1] }

// ---- a blue point dragged ---------------------------------------------------------------------------------------------------------------
/** The factor a figure marker's drag sets, and its new value: `fig` the markers' (x, y) on the front plane, `to` where marker `k` was
 *  dropped (the same plane). The part it ends: a wrist the arm, an elbow its place along the arm, an ankle the leg, a knee its place, a
 *  shoulder the shoulders' width, a hip the hips', the nose the neck, an ear the head. Null for a point no part ends at. */
export function dragFactor(b: Body, fig: XY[], k: number, to: XY): { factor: keyof Body; value: number } | null {
  const d = (a: XY, c: XY) => Math.hypot(a[0] - c[0], a[1] - c[1])
  const along = (a: XY, c: XY, p: XY) => { const ax = c[0] - a[0], ay = c[1] - a[1], L = Math.hypot(ax, ay) || 1; return ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / (L * L) }
  const clamp = (v: number, lo: number, hi: number) => Math.round(Math.min(hi, Math.max(lo, v)) * 1000) / 1000
  const name = COCO[k]
  if (name === 'r_wrist' || name === 'l_wrist') { const s = name === 'r_wrist' ? 2 : 5; const old = d(fig[s], fig[s + 1]) + d(fig[s + 1], fig[s + 2]); return { factor: 'arms', value: clamp(b.arms * (d(fig[s], fig[s + 1]) + d(fig[s + 1], to)) / old, 0.6, 1.6) } }
  if (name === 'r_elbow' || name === 'l_elbow') { const s = name === 'r_elbow' ? 2 : 5; return { factor: 'elbow', value: clamp(along(fig[s], fig[s + 2], to), 0.35, 0.65) } }
  if (name === 'r_ankle' || name === 'l_ankle') { const h = name === 'r_ankle' ? 8 : 11; const old = d(fig[h], fig[h + 1]) + d(fig[h + 1], fig[h + 2]); return { factor: 'legs', value: clamp(b.legs * (d(fig[h], fig[h + 1]) + d(fig[h + 1], to)) / old, 0.5, 1.6) } }
  if (name === 'r_knee' || name === 'l_knee') { const h = name === 'r_knee' ? 8 : 11; return { factor: 'knee', value: clamp(along(fig[h], fig[h + 2], to), 0.35, 0.65) } }
  const mid = (a: XY, c: XY): XY => [(a[0] + c[0]) / 2, (a[1] + c[1]) / 2]
  if (name === 'r_shoulder' || name === 'l_shoulder') { const c = mid(fig[2], fig[5]); return { factor: 'shoulders', value: clamp(b.shoulders * Math.abs(to[0] - c[0]) / (Math.abs(fig[k][0] - c[0]) || 1e-6), 0.6, 1.8) } }
  if (name === 'r_hip' || name === 'l_hip') { const c = mid(fig[8], fig[11]); return { factor: 'hips', value: clamp((b.hips ?? 1) * Math.abs(to[0] - c[0]) / (Math.abs(fig[k][0] - c[0]) || 1e-6), 0.6, 1.6) } }
  if (name === 'nose') {                                                       // the nose's rise over the shoulders' line: the neck's length (0.12 · neck)
    const unit = d(fig[0], mid(fig[10], fig[13])) / (bodyDims(b).top - 0.04)   // the front plane's units per dummy unit (≈ the scale)
    return { factor: 'neck', value: clamp((b.neck ?? 1) + (to[1] - fig[0][1]) / (0.12 * unit), 0.5, 3) }
  }
  if (name === 'r_ear' || name === 'l_ear') { const c = mid(fig[16], fig[17]); return { factor: 'head', value: clamp(b.head * Math.abs(to[0] - c[0]) / (Math.abs(fig[k][0] - c[0]) || 1e-6), 0.5, 2.5) } }
  return null
}

/** The body with one factor set by hand and kept by *Fit again* (the bench's locks). */
export function setLocked(b: Body, factor: keyof Body, value: number): Body {
  const locks = (b.locks ?? []).includes(factor as string) ? b.locks : [...(b.locks ?? []), factor as string]
  return { ...b, [factor]: value, locks }
}

/** A row's factor back to what the fit gives (its lock off): the default when nothing was fitted. */
export function unlock(b: Body, factor: keyof Body): Body {
  return { ...b, locks: (b.locks ?? []).filter((x) => x !== factor) }
}

export const DEFAULTS: Partial<Record<keyof Body, number>> = { elbow: ELBOW_AT, knee: KNEE_AT }
export const defaultOf = (f: keyof Body) => (DEFAULTS[f] ?? (DEFAULT_BODY[f] as number))
