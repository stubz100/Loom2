// RS0b (D197, proto02 03 PG27): until RS3 makes a shot its scene, the stage clip covers the open shot's frames — as the final and the
// animatic do (finalShot's shotRange) — not the whole stage's range; a stage no open shot looks at, or a shot with no range of its own,
// keeps the stage's range.
import { afterEach, describe, expect, it } from 'vitest'
import type { StageDoc } from '../../api/types'
import { useStory } from '../story/storyStore'
import { clipFrames } from './anim'
import { useStage } from './stageStore'

const DOC = { schema_version: 4, id: 'stg_1', name: 'Quay', purpose: 'stage', bound: null, size: { w: 1920, h: 1080, fps: 24 }, objects: [],
  cameras: [{ id: 'cam_1', name: 'Camera 1', pos: [0, 1.5, 5], target: [0, 1, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }], active_camera: 'cam_1',
  ambient: null, keyframes: { camera: {}, objects: {} }, tracks: {}, length: 0, range: { start: 0, end: 120 }, passes: [], group_id: null, revision: 1,
  created_at: '', updated_at: '' } as unknown as StageDoc
const shot = (stage_id: string, range: { start: number; end: number } | null) =>
  ({ id: 'sht_1', name: 'Wide', current: 'v1', versions: [{ id: 'v1', state: 'open', stage_id, camera_id: 'cam_1', range }] }) as never

afterEach(() => { useStage.setState({ current: null }); useStory.setState({ shots: [], shotId: null, shotVersionId: null }) })

describe('the stage clip covers the shot (RS0b, PG27)', () => {
  it("reads the open shot's range when the shot looks at this stage", () => {
    useStage.setState({ current: DOC })
    useStory.setState({ shots: [shot('stg_1', { start: 24, end: 96 })], shotId: 'sht_1', shotVersionId: null })
    expect(useStage.getState().clipRange()).toEqual({ start: 24, end: 96 })
    expect(useStage.getState().guideFrames()).toBe(clipFrames(24, 96, 8))
    expect(useStage.getState().guideFrames()).toBeLessThan(clipFrames(0, 120, 8))
  })

  it("keeps the stage's range for a shot elsewhere, or one with no range of its own", () => {
    useStage.setState({ current: DOC })
    useStory.setState({ shots: [shot('stg_2', { start: 24, end: 96 })], shotId: 'sht_1', shotVersionId: null })
    expect(useStage.getState().clipRange()).toEqual({ start: 0, end: 120 })
    useStory.setState({ shots: [shot('stg_1', null)] })
    expect(useStage.getState().clipRange()).toEqual({ start: 0, end: 120 })
    useStory.setState({ shots: [], shotId: null })
    expect(useStage.getState().guideFrames()).toBe(clipFrames(0, 120, 8))
  })
})
