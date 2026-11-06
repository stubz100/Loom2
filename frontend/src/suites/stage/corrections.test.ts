// C2 (D181, P8 / P10): corrections over a block, where Apply lands, a dragged clip.
import { describe, expect, it } from 'vitest'
import type { StageDoc, StageObject } from '../../api/types'
import { sampleFigure, type BlockRun, type ObjectKey } from './anim'
import { clipDrop, correctionKey, correctionWords, diffJoints, nextStart } from './corrections'
import { blockStartAt } from './blocks'

const FIG = { id: 'fig', kind: 'mannequin', name: 'Nora', transform: { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] },
  pose: { preset: 'stand', joints: {}, extra: {}, ground: 0, pins: {}, contacts: {}, gaze: null }, visible: true, locked: false } as unknown as StageObject
const JOINTS = ['root', 'spine', 'neck', 'head', 'r_shoulder', 'l_shoulder', 'r_elbow', 'l_elbow', 'r_hip', 'l_hip', 'r_knee', 'l_knee']
/** A walk block: every joint spelled out, the root moving along +X, the hips swinging. */
const walkKey = (frame: number): ObjectKey => ({ frame, ease: 'linear', transform: { pos: [frame * 0.1, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] },
  pose: { preset: 'walk', joints: Object.fromEntries(JOINTS.map((j) => [j, j === 'r_hip' ? [frame % 2 ? 20 : -20, 0, 0] : [0, 0, 0]])), extra: {}, ground: 0, pins: {}, contacts: {}, gaze: null } })
const RUN: BlockRun = { id: 'blk', start: 0, end: 40, blendIn: 0, keys: Array.from({ length: 41 }, (_, f) => walkKey(f)) }

describe('the review of 2026-11-06: K11 / K12', () => {
  it('K11: a block starts from the figure before it — a correction inside it does not re-anchor it', () => {
    const base = sampleFigure(FIG, undefined, [RUN], 30)
    const head = correctionKey(30, base, { head: [0, 30, 0] }, undefined, undefined)              // stores the walk's frame-30 place (x 3.0)
    expect(head.transform.pos[0]).toBeCloseTo(3)
    expect(blockStartAt(FIG, [head], [], 0).transform.pos).toEqual([0, 0, 0])                        // was x 3.0: the walk restarted 3 m on
    const before = { frame: 0, ease: 'ease', transform: { pos: [1, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] } } as ObjectKey
    expect(blockStartAt(FIG, [before, head], [], 0).transform.pos).toEqual([1, 0, 0])                // a key at the start places it
  })
  it('K12: a correction carries the gaze, the pins and the holds over the block', () => {
    const base = sampleFigure(FIG, undefined, [RUN], 20)
    const gaze = { camera: true, object_id: null, joint: null }
    const key = correctionKey(20, base, {}, undefined, undefined, { gaze, pins: {}, contacts: {} })
    expect(key.pose!.gaze).toEqual(gaze)
    expect(sampleFigure(FIG, [key], [RUN], 20).pose!.gaze).toEqual(gaze)                             // was null: Look at did nothing over a clip
    expect(correctionWords(key)).toBe('the gaze')
  })
})

describe('C2: corrections over a block (P8)', () => {
  it('a correction key changes only its joints, the block keeps moving the figure', () => {
    const base = sampleFigure(FIG, undefined, [RUN], 20)
    const key = correctionKey(20, base, { head: [0, 30, 0] }, undefined, undefined)
    expect(key.correction).toBe(true)
    expect(key.pose!.joints).toEqual({ head: [0, 30, 0] })
    const at = sampleFigure(FIG, [key], [RUN], 20)
    expect(at.pose!.joints.head).toEqual([0, 30, 0])
    expect(at.pose!.joints.r_hip).toEqual(base.pose!.joints.r_hip)                                  // the walk's own joints stay
    expect(at.transform.pos[0]).toBeCloseTo(2)                                                       // no glide: the block's position
    const near = sampleFigure(FIG, [key], [RUN], 23)
    expect(near.pose!.joints.head[1]).toBeGreaterThan(0); expect(near.pose!.joints.head[1]).toBeLessThan(30)   // eased in and out
    expect(near.transform.pos[0]).toBeCloseTo(2.3)
    expect(sampleFigure(FIG, [key], [RUN], 30).pose!.joints.head).toEqual([0, 0, 0])                   // gone six frames on
  })
  it('successive edits at one frame accumulate: the second keeps the first joint', () => {
    const base = sampleFigure(FIG, undefined, [RUN], 20)
    const first = correctionKey(20, base, { spine: [0, 30, 0] }, undefined, undefined)
    const second = correctionKey(20, base, { neck: [0, 30, 0] }, undefined, first)
    expect(Object.keys(second.pose!.joints).sort()).toEqual(['neck', 'spine'])
    expect(correctionWords(second)).toBe('spine, neck')
    const third = correctionKey(20, base, { spine: [0, 10, 0] }, undefined, second)
    expect(third.pose!.joints.spine).toEqual([0, 10, 0])                                               // the newest wins
    expect(correctionKey(20, base, { head: [0, 5, 0] }, undefined, { ...first, correction: undefined }).pose!.joints).toEqual({ head: [0, 5, 0] })   // a legacy full key is not merged
  })
  it('diffs joints beyond half a degree only', () => {
    expect(diffJoints({ head: [0, 0, 0], neck: [0, 0.2, 0] }, { head: [0, 30, 0], neck: [0, 0.4, 0], spine: [0, 0, 0] })).toEqual({ head: [0, 30, 0] })
  })
})

describe('C2: where a clip lands (P10)', () => {
  const doc = (blocks: { start: number; length: number }[]) => ({ range: { start: 0, end: 120 }, tracks: { fig: blocks } }) as unknown as StageDoc
  it("after the figure's last block, else the shot's start", () => {
    expect(nextStart(doc([]), 'fig')).toBe(0)
    expect(nextStart(doc([{ start: 10, length: 25 }, { start: 0, length: 5 }]), 'fig')).toBe(35)
    expect(nextStart({ range: { start: 24, end: 120 }, tracks: {} } as unknown as StageDoc, 'fig')).toBe(24)
  })
  it('reads a dragged clip or template', () => {
    expect(clipDrop('clip:mf_1:Walk_Loop')).toEqual({ kind: 'clip', file: 'mf_1', clip: 'Walk_Loop' })
    expect(clipDrop('clip:mf_1:A:B')).toEqual({ kind: 'clip', file: 'mf_1', clip: 'A:B' })
    expect(clipDrop('template:anm_2')).toEqual({ kind: 'template', id: 'anm_2' })
    expect(clipDrop('figures:adult')).toBeNull()
  })
})
