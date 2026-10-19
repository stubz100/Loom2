// ST4: keyframe sampling, pure (16 §12).
import { describe, expect, it } from 'vitest'
import type { StageCamera, StageDoc, StageObject } from '../../api/types'
import { bracket, clipFrames, keyedFrames, keyframesOf, neighbourKey, sampleCamera, sampleDoc, sampleObject, withKey, withoutKey, type CameraKey, type ObjectKey } from './anim'

const cam: StageCamera = { id: 'cam', name: 'Camera 1', pos: [0, 1.5, 4], target: [0, 1, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }
const obj = { id: 'fig', kind: 'mannequin', name: 'Figure 1', preset: 'adult', asset_id: null, transform: { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] }, parent: null, locked: false, visible: true, colour_id: 1, pose: { preset: 'stand', joints: {} }, billboard: false } as unknown as StageObject

describe('anim', () => {
  it('brackets a frame between keys, holds outside, eases when asked', () => {
    const keys: CameraKey[] = [{ frame: 0, ease: 'linear', pos: [0, 0, 0], target: [0, 0, 0], focal_mm: 35 }, { frame: 10, ease: 'ease', pos: [10, 0, 0], target: [0, 0, 0], focal_mm: 50 }]
    expect(bracket(keys, -5)!.w).toBe(0); expect(bracket(keys, 20)!.a.frame).toBe(10)
    expect(bracket(keys, 5)!.w).toBeCloseTo(0.5, 5)                       // smoothstep(0.5) = 0.5
    expect(bracket(keys, 2.5)!.w).toBeCloseTo(0.15625, 5)                 // smoothstep(0.25)
    expect(bracket([], 3)).toBeNull()
  })
  it('samples the camera and the object between keys; rotations take the short way', () => {
    const keys: CameraKey[] = [{ frame: 0, ease: 'linear', pos: [0, 1, 4], target: [0, 1, 0], focal_mm: 35 }, { frame: 24, ease: 'linear', pos: [0, 1, 2], target: [0, 1, 0], focal_mm: 50 }]
    const c = sampleCamera(cam, keys, 12)
    expect(c.pos).toEqual([0, 1, 3]); expect(c.focal_mm).toBe(42.5)
    expect(sampleCamera(cam, undefined, 12)).toBe(cam)
    const ok: ObjectKey[] = [{ frame: 0, ease: 'linear', transform: { pos: [0, 0, 0], rot: [0, 350, 0], scale: [1, 1, 1] } }, { frame: 10, ease: 'linear', transform: { pos: [2, 0, 0], rot: [0, 10, 0], scale: [1, 1, 1] }, pose: { preset: 'walk', joints: {} } }]
    const o = sampleObject(obj, ok, 5)
    expect(o.transform.pos).toEqual([1, 0, 0]); expect(o.transform.rot[1]).toBeCloseTo(360, 5)   // 350 → 10 through 360, not back through 180
    expect(o.pose?.preset).toBe('walk')                                                          // w = 0.5 → the later key's preset
    expect(sampleObject(obj, ok, 2).pose?.preset).toBe('stand')
  })
  it('interpolates joints when both keys carry them under the same preset', () => {
    const ok: ObjectKey[] = [{ frame: 0, ease: 'linear', transform: obj.transform, pose: { preset: 'stand', joints: { r_shoulder: [0, 0, 0] } } },
      { frame: 10, ease: 'linear', transform: obj.transform, pose: { preset: 'stand', joints: { r_shoulder: [-90, 0, 0] } } }]
    expect(sampleObject(obj, ok, 5).pose?.joints.r_shoulder).toEqual([-45, 0, 0])
  })
  it('interpolates across a preset change when both keys spell out every joint (CA1: a clip into a keyed preset), and the extras too', () => {
    const all = (r: number) => Object.fromEntries(['root', 'spine', 'neck', 'head', 'r_shoulder', 'r_elbow', 'l_shoulder', 'l_elbow', 'r_hip', 'r_knee', 'l_hip', 'l_knee'].map((j) => [j, j === 'r_shoulder' ? [r, 0, 0] : [0, 0, 0]]))
    const ok: ObjectKey[] = [{ frame: 0, ease: 'linear', transform: obj.transform, pose: { preset: 'stand', joints: all(0), extra: { index_01_r: [0, 0, 0] } } },
      { frame: 10, ease: 'linear', transform: obj.transform, pose: { preset: 'point', joints: all(-88), extra: { index_01_r: [0, 0, 80] } } }]
    const mid = sampleObject(obj, ok, 5).pose!
    expect(mid.joints.r_shoulder).toEqual([-44, 0, 0])
    expect(mid.extra?.index_01_r).toEqual([0, 0, 40])
    const partial: ObjectKey[] = [{ ...ok[0], pose: { preset: 'stand', joints: { r_shoulder: [0, 0, 0] } } }, { ...ok[1], pose: { preset: 'point', joints: { r_shoulder: [-88, 0, 0] } } }]
    expect(sampleObject(obj, partial, 4).pose?.joints.r_shoulder).toEqual([0, 0, 0])   // partial joints under different presets: still the switch at halfway
  })
  it('samples a document, leaves one without keys alone, and keeps key lists sorted', () => {
    const doc = { id: 's', name: 'S', size: { w: 1920, h: 1080, fps: 24 }, objects: [obj], cameras: [cam], active_camera: 'cam', keyframes: { camera: {}, objects: {} }, range: { start: 0, end: 48 }, passes: [], revision: 0, schema_version: 1, created_at: '', updated_at: '', group_id: null } as unknown as StageDoc
    expect(sampleDoc(doc, 10)).toBe(doc)
    const keyed = { ...doc, keyframes: { camera: { cam: [{ frame: 24, ease: 'linear' as const, pos: [0, 1, 2], target: [0, 1, 0], focal_mm: 50 }, { frame: 0, ease: 'linear' as const, pos: [0, 1, 4], target: [0, 1, 0], focal_mm: 35 }] }, objects: {} } } as unknown as StageDoc
    expect(keyframesOf(keyed).camera.cam.map((k) => k.frame)).toEqual([0, 24])
    expect(sampleDoc(keyed, 12).cameras[0].pos).toEqual([0, 1, 3])
    const ks = withKey(keyframesOf(keyed).camera.cam, { frame: 12, ease: 'ease' as const, pos: [1, 1, 3], target: [0, 1, 0], focal_mm: 40 })
    expect(ks.map((k) => k.frame)).toEqual([0, 12, 24])
    expect(withKey(ks, { ...ks[1], focal_mm: 41 }).length).toBe(3)
    expect(withoutKey(ks, 12).map((k) => k.frame)).toEqual([0, 24])
    expect(keyedFrames({ camera: { cam: ks }, objects: { fig: [{ frame: 30, ease: 'linear' as const, transform: obj.transform }] } }, 'cam')).toEqual([0, 12, 24, 30])
    expect(neighbourKey([0, 12, 24], 12, -1)).toBe(0); expect(neighbourKey([0, 12, 24], 12, 1)).toBe(24); expect(neighbourKey([0, 12, 24], 24, 1)).toBeNull()
  })
  it('snaps a range to the clip grid (8n + 1) within the range', () => {
    expect(clipFrames(0, 120)).toBe(121); expect(clipFrames(0, 100)).toBe(97); expect(clipFrames(10, 20)).toBe(9); expect(clipFrames(0, 2)).toBe(9)
  })
})
