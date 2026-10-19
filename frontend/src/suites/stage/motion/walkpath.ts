// CA1 (proto01_animate 01 step 5: "root motion along a path drawn on the floor" + "foot lock"; 02 §5's bar: feet within 2 cm): a clip
// walked along a floor path by **steering**, not by placing. The planted foot is pinned where it landed; at each frame the figure turns
// toward a point a little ahead on the path (pure pursuit, the turn rate capped) and its root is solved from the pinned foot at that
// heading — so the feet never slide, however the path bends, and the figure tracks the path within a stride. While no foot is down (a
// jog's flight) the root carries the clip's own travel. The walk ends where the path does.
import * as THREE from 'three'
import type { ObjectKey } from '../anim'
import type { Body } from '../body'
import { applyPose, mannequin, POSES } from '../builders'
import type { Placement } from './bake'
import { stance } from './footlock'
import { along, measure, type Measured, type P2 } from './path'
import type { MotionFrame } from './retarget'

const LOOKAHEAD_M = 0.6
const MAX_TURN_DEG = 4                                                       // a frame at 24 fps: up to 96° a second

/** The arc length of the path point closest to (x, z), searched near the last one (the figure only moves forward along it). */
function progressOf(m: Measured, x: number, z: number, from: number): number {
  let best = from, bestD = Infinity
  for (let i = 1; i < m.points.length; i++) {
    if (m.at[i] < from - 0.5) continue
    const [ax, az] = m.points[i - 1], [bx, bz] = m.points[i]
    const vx = bx - ax, vz = bz - az, len2 = vx * vx + vz * vz
    const t = len2 > 0 ? Math.max(0, Math.min(1, ((x - ax) * vx + (z - az) * vz) / len2)) : 0
    const px = ax + vx * t, pz = az + vz * t
    const d = (x - px) ** 2 + (z - pz) ** 2
    if (d < bestD) { bestD = d; best = m.at[i - 1] + (m.at[i] - m.at[i - 1]) * t }
    if (m.at[i - 1] > from + 2) break
  }
  return Math.max(from, best)
}

const wrap = (d: number) => { let x = d % 360; if (x > 180) x -= 360; if (x < -180) x += 360; return x }

export function walkAlong(frames: MotionFrame[], base: Placement, start: number, path: P2[], body?: Body | null): ObjectKey[] {
  const m = measure(path)
  const k = base.scale[1] ?? 1
  const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, undefined, body)
  const down = stance(frames, body)
  // the clip's own way of travel (its net displacement): the figure faces the path turned by it (a backward walk faces away)
  const nx = frames[frames.length - 1].offset[0] - frames[0].offset[0], nz = frames[frames.length - 1].offset[2] - frames[0].offset[2]
  const turn = Math.hypot(nx, nz) > 1e-3 ? (Math.atan2(nx, nz) * 180) / Math.PI : 0
  // each frame's ankles in the figure's own frame (x, z), relative to the root's clip-local place
  const local = frames.map((f) => {
    applyPose(fig.joints, POSES.stand, f.joints)
    fig.root.position.set(0, 0, 0)
    fig.root.updateMatrixWorld(true)
    const r = new THREE.Vector3(0, -fig.limbs.shin, 0).applyMatrix4(fig.joints.r_knee.matrixWorld)
    const l = new THREE.Vector3(0, -fig.limbs.shin, 0).applyMatrix4(fig.joints.l_knee.matrixWorld)
    return { r: [r.x * k, r.z * k] as P2, l: [l.x * k, l.z * k] as P2 }
  })
  const rot = (v: P2, yawDeg: number): P2 => { const a = (yawDeg * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a); return [v[0] * c + v[1] * s, -v[0] * s + v[1] * c] }
  let [rx, rz] = m.points[0]
  let yaw = along(m, 0.05).yaw - turn
  let progress = 0
  let pin: P2 | null = null
  const out: ObjectKey[] = []
  for (let i = 0; i < frames.length; i++) {
    const f = frames[i]
    // steer: toward the path a little ahead of where the figure is
    progress = progressOf(m, rx, rz, progress)
    const target = along(m, Math.min(m.length, progress + LOOKAHEAD_M)).pos
    if (Math.hypot(target[0] - rx, target[1] - rz) > 1e-3) {
      const want = (Math.atan2(target[0] - rx, target[1] - rz) * 180) / Math.PI - turn
      yaw += Math.max(-MAX_TURN_DEG, Math.min(MAX_TURN_DEG, wrap(want - yaw)))
    }
    const foot = down[i]
    if (foot && i > 0 && down[i - 1] === foot && pin) {
      const a = rot(local[i][foot], yaw)                                        // the root solved from the pinned foot at this heading
      rx = pin[0] - a[0]; rz = pin[1] - a[1]
    } else if (i > 0) {                                                         // a new plant, or in the air: the clip's own travel
      const d = rot([(f.offset[0] - frames[i - 1].offset[0]) * k, (f.offset[2] - frames[i - 1].offset[2]) * k], yaw)
      rx += d[0]; rz += d[1]
    }
    if (foot && (i === 0 || down[i - 1] !== foot || !pin)) { const a = rot(local[i][foot], yaw); pin = [rx + a[0], rz + a[1]] }
    if (!foot) pin = null
    out.push({ frame: start + i, ease: 'linear', transform: { pos: [rx, base.pos[1] + f.offset[1] * k, rz], rot: [base.rot[0] ?? 0, Math.round(yaw * 100) / 100, base.rot[2] ?? 0], scale: [...base.scale] },
      pose: { preset: 'stand', joints: Object.fromEntries(Object.entries(f.joints).map(([j, e]) => [j, e.map((v) => Math.round(v * 100) / 100)])) } })
    if (progress >= m.length - 0.1) break
  }
  return out
}
