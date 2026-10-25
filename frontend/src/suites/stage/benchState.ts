// CS2 (proto01_UIcast 03 §3.2): the skeleton bench's state shared by its panes, the Inspector's parts and the commands (storyCommands loads
// it with the bench) and *From the picture*. Kept apart from SkeletonBench.tsx, a components-only file.
import { useEffect, useState } from 'react'
import * as THREE from 'three'
import { http, unwrap } from '../../api/client'
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


/** D140: a picture's people as SDPose reads them — a short `keypoints` job (one GPU job through the queue), its first person as points;
 *  null when it finds nobody or the job fails. */
export async function readPicture(assetId: string): Promise<Points | null> {
  const r = await unwrap(http.POST('/jobs', { body: { recipe: { kind: 'keypoints', asset_id: assetId } as never, stage: false } }))
  const id = r.jobs[0]?.id
  for (let i = 0; id && i < 240; i++) {
    const j = await unwrap(http.GET('/jobs/{job_id}', { params: { path: { job_id: id } } }))
    if (j.status === 'failed' || j.status === 'cancelled') return null
    if (j.status === 'done') {
      const person = ((j.result as { people?: Record<string, number[]>[] } | null)?.people ?? [])[0]
      if (!person) return null
      const rows = (flat?: number[]) => { const out: number[][] = []; for (let k = 0; k + 2 < (flat ?? []).length; k += 3) out.push([flat![k], flat![k + 1], flat![k + 2]]); return out }
      return { pose: rows(person.pose_keypoints_2d), hand_left: rows(person.hand_left_keypoints_2d), hand_right: rows(person.hand_right_keypoints_2d), feet: rows(person.foot_keypoints_2d) }
    }
    await new Promise((res) => setTimeout(res, 500))
  }
  return null
}

/** *From the picture*: the hand preset and curl whose 21 points — the Detailed figure in the reference's stance, seen from the front — lie
 *  nearest SDPose's hands (each hand from its wrist, by its palm, turned so the palm points the same way: D140 reads the hero, whose hands
 *  hang or rest anyhow; SDPose's `hand_left` is the picture's left, the figure's right). */
export async function handFromPicture(body: Body, pts: Points | null): Promise<{ preset: HandPreset; curl: number; err: number } | null> {
  if (!pts) return null
  const shape = (rows: number[][] | undefined, flipY: boolean): XY[] | null => {
    if (!rows || rows.length < 21 || !seen(rows[0]) || !seen(rows[9])) return null
    const dx = rows[9][0] - rows[0][0], dy = (rows[9][1] - rows[0][1]) * (flipY ? -1 : 1)
    const s = Math.hypot(dx, dy) || 1, c = dx / s, n = dy / s                // the palm turned onto +x, scaled to one
    return rows.map((r) => {
      if (!seen(r)) return [NaN, NaN] as XY
      const x = (r[0] - rows[0][0]) / s, y = ((r[1] - rows[0][1]) * (flipY ? -1 : 1)) / s
      return [x * c + y * n, -x * n + y * c] as XY
    })
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
      const xy = shape(markers.map((m) => { const p = m.getWorldPosition(new THREE.Vector3()); return [p.x, p.y, 1] }), false)!
      for (let k = 1; k < 21; k++) { if (Number.isNaN(w[k][0])) continue; sum += Math.hypot(xy[k][0] - w[k][0], xy[k][1] - w[k][1]); n++ }
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
