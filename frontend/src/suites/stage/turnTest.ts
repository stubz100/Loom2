// CA0 (proto01_animate 01 step 2): the pose sequence of a test animation — one figure with the Cast version's body, in the reference's
// A-pose, turning once on the spot in front of a 35 mm camera that frames it whole. Rendered by the Stage's own pass renderer on a scratch
// document that is never saved (a detached canvas, as headless.ts), so the test sees the pose skeleton a shot on the stage would draw.
// Loaded lazily from Cast with the stage's code.
import type { StageCamera, StageDoc, StageObject } from '../../api/types'
import type { Body } from './body'
import { StageEngine } from './engine'

/** The reference's stance: arms a little away from the body (01 step 2). */
const A_POSE = { r_shoulder: [0, 0, -22], l_shoulder: [0, 0, 22], r_elbow: [0, 0, 0], l_elbow: [0, 0, 0] }

export async function renderTurn(body: Body | null, frames: number, fps: number, w: number, h: number,
                                 onProgress?: (done: number, total: number) => void): Promise<{ blobs: Blob[]; keypoints: unknown[] }> {
  const height = body?.height_m ?? 1.75
  // a 35 mm lens on a 36 mm sensor: the vertical view at distance d is 2·d·tan(vfov/2); the figure fills about 70 % of the frame's height
  const vfov = 2 * Math.atan((36 / (w / h)) / 2 / 35)
  const dist = height / (0.7 * 2 * Math.tan(vfov / 2))
  const cam: StageCamera = { id: 'cam', name: 'Test', pos: [0, height * 0.55, dist], target: [0, height * 0.5, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }
  const fig: StageObject = { id: 'fig', kind: 'mannequin', name: 'figure', preset: 'adult', asset_id: null, transform: { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] },
    parent: null, locked: false, visible: true, colour_id: 1, pose: { preset: 'stand', joints: A_POSE, extra: {} }, billboard: false, profile_id: null, version: null, body: (body ?? null) as StageObject['body'], detail: null, path: null, shadow_proxy: null, light: null, lens_deg: null, plate_asset_id: null, floor_y: null, plate_camera_id: null }
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
