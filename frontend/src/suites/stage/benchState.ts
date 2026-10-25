// CS2 (proto01_UIcast 03 §3.2): the skeleton bench's state shared by its panes, the Inspector's parts and the commands (storyCommands loads
// it with the bench) and *From the picture*. Kept apart from SkeletonBench.tsx, a components-only file.
import { useEffect, useState } from 'react'
import * as THREE from 'three'
import type { Profile } from '../../api/types'
import type { Body } from './body'
import { mannequin, POSES } from './builders'
import { HAND_PRESETS, makeDetailed, type HandPreset } from './detailed'
import { seen, type Points, type RowKey, type XY } from './skeleton'
import { stanceOf } from './proxy'

/** The bench's state shared by its panes and the Inspector's parts (session only). */
export interface BenchUi { pts: Points | null; forVersion: string | null; row: RowKey | null; moved: number[] }
export const ui: BenchUi & { subs: Set<() => void> } = { pts: null, forVersion: null, row: null, moved: [], subs: new Set() }
export function setUi(patch: Partial<BenchUi>) { Object.assign(ui, patch); for (const f of ui.subs) f() }
export function useUi(): BenchUi { const [, tick] = useState(0); useEffect(() => { const f = () => tick((n) => n + 1); ui.subs.add(f); return () => { ui.subs.delete(f) } }, []); return ui }


/** *From the picture*: the hand preset and curl whose 21 points — the Detailed figure in the reference's stance, seen from the front — lie
 *  nearest SDPose's hands (each hand from its wrist, by its palm; SDPose's `hand_left` is the picture's left, the figure's right). */
export async function handFromPicture(body: Body, pts: Points | null): Promise<{ preset: HandPreset; curl: number; err: number } | null> {
  if (!pts) return null
  const shape = (rows: number[][] | undefined, flipY: boolean): XY[] | null => {
    if (!rows || rows.length < 21 || !seen(rows[0]) || !seen(rows[9])) return null
    const s = Math.hypot(rows[9][0] - rows[0][0], rows[9][1] - rows[0][1]) || 1
    return rows.map((r) => (seen(r) ? [(r[0] - rows[0][0]) / s, ((r[1] - rows[0][1]) / s) * (flipY ? -1 : 1)] as XY : [NaN, NaN] as XY))
  }
  const want = { r: shape(pts.hand_left, true), l: shape(pts.hand_right, true) }
  if (!want.r && !want.l) return null
  const { mannequinClone } = await import('./motion/mannequins')
  const stance = stanceOf(pts as never)
  const mat = new THREE.MeshBasicMaterial()
  let best: { preset: HandPreset; curl: number; err: number } | null = null
  for (const preset of HAND_PRESETS) for (const curl of [0.6, 1, 1.4]) {
    const fig = mannequin(mat, POSES.stand, stance, body)
    const g = new THREE.Group(); g.add(fig.root); g.updateMatrixWorld(true)
    const { root, rig } = await mannequinClone(body.figure ?? 'female', mat)
    const d = makeDetailed(root, rig, fig.joints.root.parent!, fig.joints, fig.limbs, { hands: body.hands, feet: body.feet, head: body.head, handRest: { preset, curl, spread: body.hand_rest.spread, thumb: body.hand_rest.thumb } })
    d.follow(fig.joints, null); g.updateMatrixWorld(true)
    if (!d.wholebody) return null
    let sum = 0, n = 0
    for (const [side, markers] of [['r', d.wholebody.right], ['l', d.wholebody.left]] as const) {
      const w = want[side]; if (!w) continue
      const xy = markers.map((m) => { const p = m.getWorldPosition(new THREE.Vector3()); return [p.x, p.y] as XY })
      const s = Math.hypot(xy[9][0] - xy[0][0], xy[9][1] - xy[0][1]) || 1
      for (let k = 1; k < 21; k++) { if (Number.isNaN(w[k][0])) continue; sum += Math.hypot((xy[k][0] - xy[0][0]) / s - w[k][0], (xy[k][1] - xy[0][1]) / s - w[k][1]); n++ }
    }
    const err = n ? sum / n : Infinity
    if (!best || err < best.err) best = { preset, curl, err }
  }
  return best
}

/** The bench's commands' state (storyCommands registers them; the view publishes what they act on). */
export const bench = {
  points: () => ui.pts, moved: () => ui.moved,
  resetPoints: (v: Profile['versions'][number]) => { const sd = ((v.body_points as Record<string, unknown> | null)?.sdpose ?? v.body_points) as Points | null; setUi({ pts: sd ? JSON.parse(JSON.stringify({ ...(v.body_points as object), ...sd })) : null, moved: [] }) },
  mirror: () => {                                                            // the side last moved onto the other, about the nose–ankles axis
    const pts = ui.pts; if (!pts || !ui.moved.length) return
    const pairs: [number, number][] = [[2, 5], [3, 6], [4, 7], [8, 11], [9, 12], [10, 13], [14, 15], [16, 17]]
    const last = ui.moved[ui.moved.length - 1], from = pairs.some(([a]) => a === last) ? 0 : 1
    const ax = (pts.pose[0][0] + (pts.pose[10][0] + pts.pose[13][0]) / 2) / 2
    const next = JSON.parse(JSON.stringify(pts)) as Points
    for (const pr of pairs) { const a = pr[from], c = pr[1 - from]; if (seen(pts.pose[a])) next.pose[c] = [2 * ax - pts.pose[a][0], pts.pose[a][1], pts.pose[a][2]] }
    setUi({ pts: next, moved: [...new Set([...ui.moved, ...pairs.map((pr) => pr[1 - from])])] })
  },
}
