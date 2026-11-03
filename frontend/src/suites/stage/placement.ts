// C1 (D181, propo02 04 §4.3, P7; F35): where a thing added to a scene lands, and which way it faces. Pure, tested in placement.test.ts.
// Today a thing landed where the viewport's centre ray hit the floor (M10, W34); now the ＋ puts it on the floor inside the shot camera's
// frame, a little apart from what already stands there, facing the camera; a tile dragged onto the viewport lands where the mouse points.
import type { StageCamera, StageObject } from '../../api/types'

const DEG = Math.PI / 180
/** The camera's side of a point on the floor: degrees in the figure's yaw convention (+Z = 0), so a figure with this yaw faces the camera. */
export const faceCamera = (pos: number[], camPos: number[]): number => Math.round(Math.atan2(camPos[0] - pos[0], camPos[2] - pos[2]) / DEG)

/** F35: the point on the floor the camera looks at — its line of sight meets y = 0 — but no farther than 6 m out (a nearly level camera
 *  meets the floor far beyond the set) and no nearer than 1.5 m; null when the camera looks level or up (nothing on the floor in its frame). */
export function cameraFloorPoint(cam: Pick<StageCamera, 'pos' | 'target'>): number[] | null {
  const [px, py, pz] = cam.pos, [tx, ty, tz] = cam.target
  const dy = py - ty
  if (!(dy > 1e-6) || !(py > 0)) return null                               // the target is not below the camera: no floor ahead
  const dx = tx - px, dz = tz - pz
  const horiz = Math.hypot(dx, dz)
  if (horiz < 1e-6) return [+px.toFixed(3), 0, +pz.toFixed(3)]              // straight down
  const t = py / dy                                                          // how far along pos→target the floor is
  const dist = Math.min(6, Math.max(1.5, horiz * t))                         // 1.5–6 m out, along the line of sight
  const k = dist / horiz
  return [+(px + dx * k).toFixed(3), 0, +(pz + dz * k).toFixed(3)]
}

/** The landing point of a new thing: the camera's floor point (F35), else the viewport's centre; moved sideways in 0.7 m steps (to the
 *  camera's right, then its left) while another thing stands within 0.3 m of it, so three figures added in a row stand side by side (P7). */
export function landing(cam: Pick<StageCamera, 'pos' | 'target'> | null, objects: Pick<StageObject, 'transform' | 'kind' | 'visible'>[], centre: number[]): number[] {
  const base = (cam && cameraFloorPoint(cam)) ?? centre
  const taken = objects.filter((o) => o.visible !== false && o.kind !== 'set' && o.kind !== 'light').map((o) => o.transform.pos)
  const near = (p: number[]) => taken.some((q) => Math.hypot(q[0] - p[0], q[2] - p[2]) < 0.3)
  if (!near(base)) return base
  const yaw = cam ? Math.atan2(cam.target[0] - cam.pos[0], cam.target[2] - cam.pos[2]) : 0
  const right = [-Math.cos(yaw), 0, Math.sin(yaw)]                            // the camera's right on the floor: forward (sin ψ, 0, cos ψ) × up
  for (let n = 1; n <= 6; n++) for (const side of [1, -1]) {
    const p = [+(base[0] + right[0] * 0.7 * n * side).toFixed(3), base[1], +(base[2] + right[2] * 0.7 * n * side).toFixed(3)]
    if (!near(p)) return p
  }
  return base
}

/** A preset tile dragged onto the viewport: its group and id (`figures:adult`, `figures:char:<profile>`, `standins:crate`, `meshes:<asset>`). */
export function presetDrop(id: string): { group: string; id: string } | null {
  const i = id.indexOf(':')
  return i > 0 ? { group: id.slice(0, i), id: id.slice(i + 1) } : null
}
