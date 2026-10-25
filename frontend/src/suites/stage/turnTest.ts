// CA0 (proto01_animate 01 step 2): the pose sequence of a test animation — one figure with the Cast version's body, in the reference's
// A-pose, turning once on the spot in front of a 35 mm camera that frames it whole. Rendered by the Stage's own pass renderer on a scratch
// document that is never saved (a detached canvas, as headless.ts), so the test sees the pose skeleton a shot on the stage would draw.
// Loaded lazily from Cast with the stage's code.
// proto01_UIcast CS1 (S4): the guide the shots use — the character's Detailed mannequin (hands and feet in the pose pass, the Simple dummy
// had none) — and the first frame in the reference's own stance (its arms' angles from the points the body was fitted to), then the turn.
import type { StageCamera, StageDoc, StageObject } from '../../api/types'
import type { Body } from './body'
import { StageEngine } from './engine'

/** The reference's stance when its points are not known: arms a little away from the body (01 step 2). */
const A_POSE = { r_shoulder: [0, 0, -22], l_shoulder: [0, 0, 22], r_elbow: [0, 0, 0], l_elbow: [0, 0, 0] }
type Points = { pose?: number[][] } | null | undefined

/** S4: the arms as the reference holds them, from SDPose's body points (OpenPose-18: 2–4 the right shoulder, elbow, wrist — on the picture's
 *  left for a figure facing it — 5–7 the left's): each upper arm's swing out from hanging down, each forearm's on from it, in the picture's
 *  plane (the front view). Missing points: A_POSE. */
export function stanceOf(points: Points): Record<string, number[]> {
  const p = points?.pose
  if (!p || p.length < 8) return A_POSE
  const seen = (i: number) => (p[i]?.[2] ?? 0) >= 0.3
  const out: Record<string, number[]> = { ...A_POSE }
  for (const [s, e, wr, side] of [[2, 3, 4, -1], [5, 6, 7, 1]] as const) {
    if (!seen(s) || !seen(e) || !seen(wr)) continue
    const out1 = (a: number, b: number) => Math.atan2(side * (p[b][0] - p[a][0]), p[b][1] - p[a][1]) * 180 / Math.PI   // outward from straight down
    const upper = out1(s, e), fore = out1(e, wr)
    const name = side < 0 ? 'r' : 'l'
    out[`${name}_shoulder`] = [0, 0, +(side * upper).toFixed(1)]
    out[`${name}_elbow`] = [0, 0, +(side * (fore - upper)).toFixed(1)]
  }
  return out
}

export async function renderTurn(body: Body | null, frames: number, fps: number, w: number, h: number,
                                 onProgress?: (done: number, total: number) => void, points?: Points): Promise<{ blobs: Blob[]; keypoints: unknown[] }> {
  const height = body?.height_m ?? 1.75
  // a 35 mm lens on a 36 mm sensor: the vertical view at distance d is 2·d·tan(vfov/2); the figure fills about 70 % of the frame's height
  const vfov = 2 * Math.atan((36 / (w / h)) / 2 / 35)
  const dist = height / (0.7 * 2 * Math.tan(vfov / 2))
  const cam: StageCamera = { id: 'cam', name: 'Test', pos: [0, height * 0.55, dist], target: [0, height * 0.5, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }
  const fig: StageObject = { id: 'fig', kind: 'mannequin', name: 'figure', preset: 'adult', asset_id: null, transform: { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] },
    parent: null, parent_joint: null, locked: false, visible: true, colour_id: 1, pose: { preset: 'stand', joints: stanceOf(points), extra: {} }, billboard: false, profile_id: null, version: null, body: (body ?? null) as StageObject['body'], detail: body?.figure ?? 'female', path: null, shadow_proxy: null, light: null, lens_deg: null, plate_asset_id: null, floor_y: null, plate_camera_id: null, level: null, things: [], things_document_id: null }
  const doc = { schema_version: 1, id: 'turn-test', name: 'turn test', size: { w, h, fps }, objects: [fig], cameras: [cam], active_camera: 'cam',
    keyframes: { camera: {}, objects: {} }, range: { start: 0, end: frames - 1 }, passes: [], group_id: null, revision: 0, created_at: '', updated_at: '' } as unknown as StageDoc
  const seq = Array.from({ length: frames }, (_, i) => {
    const yaw = (360 * i) / (frames - 1)
    return { cam, doc: { ...doc, objects: [{ ...fig, transform: { ...fig.transform, rot: [0, yaw, 0] } }] } as StageDoc }
  })
  const engine = new StageEngine(document.createElement('canvas'), { onPick: () => undefined, onTransformed: () => undefined, onPosed: () => undefined })
  try {
    engine.sync(doc)
    return await engine.renderSequence(seq, w, h, 'pose', doc, onProgress)
  } finally { engine.dispose() }
}
