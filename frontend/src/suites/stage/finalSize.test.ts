// The review of 2026-10-27, V81: the final's layers are sized at the project's aspect on the pose-driven model's grid, its short side the
// model's — the model's own 832×480 used to be the size whatever the project (a 9:16 project's final came out landscape).
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { StageDoc } from '../../api/types'
import { useSession } from '../../store/session'
import { finalSize } from './finalShot'
import { useStage } from './stageStore'

const doc = (w: number, h: number) => ({ id: 'stg_1', name: 'S', size: { w, h, fps: 24 }, objects: [], cameras: [], keyframes: { camera: {}, objects: {} }, range: { start: 0, end: 48 },
  passes: [], revision: 1 }) as unknown as StageDoc

describe('finalSize (V81)', () => {
  beforeEach(() => useSession.setState({ capabilities: { stage: { animate: { size: [832, 480] }, clip: { size: [1024, 576], size_mult: 16 } }, models: {} } } as never))
  afterEach(() => { useStage.setState({ current: null }); useSession.setState({ capabilities: null } as never) })

  it('follows the project aspect on the 16 grid with the model’s short side', () => {
    useStage.setState({ current: doc(1920, 1080) })
    expect(finalSize()).toEqual([848, 480])
    useStage.setState({ current: doc(1080, 1920) })
    expect(finalSize()).toEqual([480, 848])
    useStage.setState({ current: doc(1024, 1024) })
    expect(finalSize()).toEqual([480, 480])
    useStage.setState({ current: doc(1440, 1080) })
    expect(finalSize()).toEqual([640, 480])
  })

  it('without a stage falls back to the model’s own aspect; without a pose-driven model to the clip size', () => {
    useStage.setState({ current: null })
    expect(finalSize()).toEqual([832, 480])
    useSession.setState({ capabilities: { stage: { animate: null, clip: { size: [1024, 576], size_mult: 16 } }, models: {} } } as never)
    useStage.setState({ current: doc(1920, 1080), clipMethod: 'animate' } as never)
    expect(finalSize()).toEqual(useStage.getState().guideSize())
  })
})
