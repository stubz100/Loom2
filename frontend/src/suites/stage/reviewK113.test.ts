// The review of 2026-11-06 (journal 11:55), K113 — the rigging benches: Mirror after a refit copies the side moved last, a point moved again
// goes last, the picture cropped to the read (not to the points as dragged), D183's per-joint reset, the bent shoe's points, the Try it on
// header following the bench.
import * as THREE from 'three'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DEFAULT_BODY, resetPlaced } from './body'
import { bench, movedLast, orderMoved, setUi } from './benchState'
import { bentFoot } from './proxy'
import { readOf, type Points } from './skeleton'
import { watchTryOn } from './animationBench'
import { useStage } from './stageStore'

const pose = (): number[][] => Array.from({ length: 18 }, (_, k) => [100 + k * 10, 50 + k * 20, 1])

describe('K113: Mirror copies the side moved last, after a refit too', () => {
  afterEach(() => setUi({ pts: null, moved: [], forVersion: null }))
  it("keeps this session's order through a refit's read (the joints' order), and a point moved again goes last", () => {
    expect(orderMoved([3], [3, 6])).toEqual([6, 3])                    // 6 moved before this session, 3 just now
    expect(orderMoved([6, 3], [3])).toEqual([3])                        // a point back on SDPose's leaves the list
    expect(movedLast([3, 6], 3)).toEqual([6, 3])
  })
  it('mirrors the right elbow just dragged onto the left, not the left onto the right', () => {
    const pts: Points = { pose: pose() }
    pts.pose[3] = [40, 200, 1]                                           // the right elbow, dragged
    setUi({ pts, moved: orderMoved([3], [3, 6]) })
    expect(bench.mirror()).toBe(true)
    const ax = (pts.pose[0][0] + (pts.pose[10][0] + pts.pose[13][0]) / 2) / 2
    expect(bench.points()!.pose[6]).toEqual([2 * ax - 40, 200, 1])
    expect(bench.moved().at(-1)).toBe(3)                                 // the side copied from stays last: Mirror again does the same
  })
  it('a nose or a neck moved last has no side: the last sided point decides', () => {
    setUi({ pts: { pose: pose() }, moved: [6, 0] })
    expect(bench.mirror()).toBe(true)
    expect(bench.points()!.pose[3][1]).toBe(pose()[6][1])               // the left copied onto the right
  })
})

describe('K113: the picture is cropped to the read; D183 resets one joint', () => {
  it('reads SDPose\'s own points when the version keeps them apart', () => {
    const kept = { pose: [[1, 1, 1]], sdpose: { pose: [[5, 5, 1]] } } as Points & { sdpose: Partial<Points> }
    expect(readOf(kept)!.pose).toEqual([[5, 5, 1]])
    expect(readOf({ pose: [[1, 1, 1]] })!.pose).toEqual([[1, 1, 1]])
    expect(readOf(null)).toBeNull()
  })
  it('resets one placed joint, or all', () => {
    const b = { ...DEFAULT_BODY, joint_offsets: { r_elbow: [0.1, 0, 0], l_knee: [0, 0.02, 0] } }
    expect(resetPlaced(b, 'r_elbow').joint_offsets).toEqual({ l_knee: [0, 0.02, 0] })
    expect(resetPlaced(b, null).joint_offsets).toEqual({})
    expect(b.joint_offsets).toHaveProperty('r_elbow')                    // the body given is not changed
  })
})

describe('K113: the bent shoe carries its points', () => {
  it('moves the heel and ball with the ankle and the toe with the ball', () => {
    const root = new THREE.Group()
    const ankle = new THREE.Bone(); ankle.name = 'r_ankle_rig'; ankle.position.set(0, 0.1, 0); root.add(ankle)
    const ball = new THREE.Bone(); ball.name = 'r_ball_rig'; ball.position.set(0, -0.07, 0.12); ankle.add(ball)
    const m = bentFoot(root, 'r', () => { ball.quaternion.setFromAxisAngle(new THREE.Vector3(-1, 0, 0), Math.PI / 6) })   // the push-off: toes up 30°
    const heel = new THREE.Vector3(0, 0.03, -0.05).applyMatrix4(m.heel), toe = new THREE.Vector3(0, 0.03, 0.2).applyMatrix4(m.toe)
    expect(heel.toArray()).toEqual([0, 0.03, -0.05])                     // the ankle did not turn: the heel stays
    expect(toe.y).toBeGreaterThan(0.06)                                  // the toe rose about the ball
    const back = toe.clone().applyMatrix4(m.toe.clone().invert())        // a drag on the bent shoe, taken back to the flat one
    expect(back.z).toBeCloseTo(0.2); expect(back.y).toBeCloseTo(0.03)
    const none = bentFoot(new THREE.Group(), 'l', () => undefined)       // a foot not rigged: nothing moves
    expect(new THREE.Vector3(1, 2, 3).applyMatrix4(none.toe).toArray()).toEqual([1, 2, 3])
  })
})

describe("K113: Try it on's header follows the bench", () => {
  it('tells who the bench figure is at once and again when the scene changes', () => {
    const told = vi.fn()
    const off = watchTryOn(told)
    expect(told).toHaveBeenLastCalledWith(null)                          // no bench: the dummy
    const n = told.mock.calls.length
    useStage.setState({ frame: 3 } as never)
    expect(told.mock.calls.length).toBeGreaterThan(n)
    off()
    useStage.setState({ frame: 4 } as never)
    expect(told.mock.calls.length).toBe(n + 1)
  })
})
