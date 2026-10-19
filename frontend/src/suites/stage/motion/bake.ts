// CA1 (proto01_animate 01 step 5: "bake to Stage keys at 24 fps, thinned"): a retargeted clip as the figure's object keys — placed where
// the figure stands and facing its way, one key per frame, then thinned to the keys the linear in-between cannot rebuild within a tolerance.
import type { ObjectKey } from '../anim'
import type { MotionFrame } from './retarget'

export interface Placement { pos: number[]; rot: number[]; scale: number[] }

/** One key per frame from `start`: the root motion turned by the figure's yaw and scaled with it, the joints as retargeted. */
export function bakeKeys(frames: MotionFrame[], base: Placement, start: number): ObjectKey[] {
  const yaw = ((base.rot[1] ?? 0) * Math.PI) / 180
  const c = Math.cos(yaw), s = Math.sin(yaw), k = base.scale[1] ?? 1
  return frames.map((f, i) => {
    const [x, y, z] = f.offset
    return {
      frame: start + i, ease: 'linear',
      transform: { pos: [base.pos[0] + (x * c + z * s) * k, base.pos[1] + y * k, base.pos[2] + (-x * s + z * c) * k], rot: [...base.rot], scale: [...base.scale] },
      pose: { preset: 'stand', joints: Object.fromEntries(Object.entries(f.joints).map(([j, e]) => [j, e.map((v) => Math.round(v * 100) / 100)])) },
    }
  })
}

const angleGap = (a: number, b: number) => { let d = (b - a) % 360; if (d > 180) d -= 360; if (d < -180) d += 360; return Math.abs(d) }
const lerpDeg = (a: number, b: number, w: number) => { let d = (b - a) % 360; if (d > 180) d -= 360; if (d < -180) d += 360; return a + d * w }

/** Whether the linear in-between of `a` and `b` rebuilds `m` (joints within `deg`, position within `m` metres). */
function rebuilt(a: ObjectKey, b: ObjectKey, m: ObjectKey, deg: number, metres: number): boolean {
  const w = (m.frame - a.frame) / (b.frame - a.frame)
  for (let i = 0; i < 3; i++) if (Math.abs(a.transform.pos[i] + (b.transform.pos[i] - a.transform.pos[i]) * w - m.transform.pos[i]) > metres) return false
  const ja = a.pose?.joints ?? {}, jb = b.pose?.joints ?? {}, jm = m.pose?.joints ?? {}
  for (const n of Object.keys(jm)) {
    const ea = ja[n], eb = jb[n], em = jm[n]
    if (!ea || !eb) return false
    for (let i = 0; i < 3; i++) if (angleGap(lerpDeg(ea[i], eb[i], w), em[i]) > deg) return false
  }
  return true
}

/** The fewest keys that rebuild every baked frame within the tolerance: from each kept key, reach as far as the in-between still holds. */
export function thinKeys(keys: ObjectKey[], deg = 1.0, metres = 0.005): ObjectKey[] {
  if (keys.length <= 2) return keys
  const out = [keys[0]]
  let a = 0
  while (a < keys.length - 1) {
    let b = a + 1
    while (b + 1 < keys.length) {
      const next = b + 1
      let ok = true
      for (let m = a + 1; m < next; m++) if (!rebuilt(keys[a], keys[next], keys[m], deg, metres)) { ok = false; break }
      if (!ok) break
      b = next
    }
    out.push(keys[b])
    a = b
  }
  return out
}
