// CA1 (proto01_animate 01 step 5: "root motion along a path drawn on the floor"): a figure's floor path — points clicked on the floor —
// smoothed (Chaikin's corner cutting, twice) and measured by arc length, so a clip's travel (foot-locked: the distance its feet carry it)
// is laid along it: the position at each frame is the point that far along the path, the facing its tangent. Pure maths, no three.js.

export type P2 = [number, number]                                             // x, z on the floor

/** Chaikin's corner cutting: the ends kept, each corner replaced by points at ¼ and ¾ of its sides. */
export function smooth(points: P2[], passes = 2): P2[] {
  let pts = points
  for (let k = 0; k < passes && pts.length > 2; k++) {
    const out: P2[] = [pts[0]]
    for (let i = 0; i < pts.length - 1; i++) {
      const [ax, az] = pts[i], [bx, bz] = pts[i + 1]
      if (i > 0) out.push([ax * 0.75 + bx * 0.25, az * 0.75 + bz * 0.25])
      if (i < pts.length - 2) out.push([ax * 0.25 + bx * 0.75, az * 0.25 + bz * 0.75])
    }
    out.push(pts[pts.length - 1])
    pts = out
  }
  return pts
}

export interface Measured { points: P2[]; at: number[]; length: number }

/** The smoothed path with the distance from its start to each point. */
export function measure(points: P2[]): Measured {
  const pts = smooth(points)
  const at = [0]
  for (let i = 1; i < pts.length; i++) at.push(at[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
  return { points: pts, at, length: at[at.length - 1] }
}

/** The point `d` metres along the path (held at its ends) and the facing there, degrees about Y (0 = +Z, the figure's own forward). */
export function along(m: Measured, d: number): { pos: P2; yaw: number } {
  const n = m.points.length
  if (n === 1) return { pos: m.points[0], yaw: 0 }
  const t = Math.max(0, Math.min(m.length, d))
  let i = 1
  while (i < n - 1 && m.at[i] < t) i++
  const [ax, az] = m.points[i - 1], [bx, bz] = m.points[i]
  const seg = m.at[i] - m.at[i - 1]
  const w = seg > 1e-9 ? (t - m.at[i - 1]) / seg : 0
  return { pos: [ax + (bx - ax) * w, az + (bz - az) * w], yaw: (Math.atan2(bx - ax, bz - az) * 180) / Math.PI }
}
