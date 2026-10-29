// U5b (D157 G8; proto01_UI2 04 §3.2): clip blocks under the key layer — the merge rule (anim.sampleFigure), a template's block re-based
// to where the figure stands, and what a block's evaluation reads (blocks.blockKey).
import { describe, expect, it } from 'vitest'
import type { StageDoc, StageObject } from '../../api/types'
import { sampleDoc, sampleFigure, setBlockRuns, type BlockRun, type ObjectKey } from './anim'
import { blockKey, templateRun, type MotionBlock } from './blocks'

const fig = { id: 'fig', kind: 'mannequin', name: 'Ines', transform: { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] }, pose: { preset: 'stand', joints: {} }, visible: true } as unknown as StageObject
const at = (frame: number, x: number, arm = 0, ease: ObjectKey['ease'] = 'linear'): ObjectKey =>
  ({ frame, ease, transform: { pos: [x, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] }, pose: { preset: 'stand', joints: Object.fromEntries(Array.from({ length: 12 }, (_, i) => [`j${i}`, [i === 0 ? arm : 0, 0, 0]])) } })
/** A block from frame 10 to 20 that walks from x = 1 to x = 2 with the arm at 90°. */
const run: BlockRun = { id: 'blk_a', start: 10, end: 20, blendIn: 0, keys: Array.from({ length: 11 }, (_, i) => at(10 + i, 1 + i / 10, 90)) }

describe('blocks under the key layer (U5b)', () => {
  it('outside a block the layer reaches its first pose and leaves from its last; inside, the block plays', () => {
    const layer = [at(0, 0), at(30, 5)]
    expect(sampleFigure(fig, layer, [], 15).transform.pos[0]).toBeCloseTo(2.5)         // no blocks: the layer as before
    expect(sampleFigure(fig, layer, [run], 15).transform.pos[0]).toBeCloseTo(1.5)      // in the block
    expect(sampleFigure(fig, layer, [run], 0).transform.pos[0]).toBeCloseTo(0)
    expect(sampleFigure(fig, layer, [run], 25).transform.pos[0]).toBeCloseTo(3.5, 1)   // from the block's end (2) to the next key (5), linear
    expect(sampleFigure(fig, layer, [run], 5).transform.pos[0]).toBeGreaterThan(0)    // on its way to the block's first pose
  })
  it('eases in from where the figure was over its blend, and a layer key inside it is a correction', () => {
    const blended = { ...run, blendIn: 6 }
    const layer = [at(0, 0, 0)]
    const arm = (f: number, l: ObjectKey[] = layer, r = blended) => sampleFigure(fig, l, [r], f).pose!.joints.j0[0]
    expect(arm(10)).toBeCloseTo(0)                                                          // the block's start: still the pose before
    expect(arm(13)).toBeGreaterThan(10); expect(arm(13)).toBeLessThan(80)
    expect(arm(16)).toBeCloseTo(90)
    const fix = [...layer, at(18, 1.8, 45)]                                                 // a correction at frame 18: the arm at 45°
    expect(arm(18, fix, run)).toBeCloseTo(45)
    expect(arm(15, fix, run)).toBeGreaterThan(45); expect(arm(15, fix, run)).toBeLessThan(90)   // easing towards it
    expect(arm(12, fix, run)).toBeCloseTo(90)                                               // beyond its reach the block plays
  })
  it('a figure with blocks and no keys moves in the document at a frame', () => {
    const doc = { id: 'stg', objects: [fig], cameras: [], keyframes: { camera: {}, objects: {} }, tracks: { fig: [{ id: 'blk_a' }] }, size: { w: 1920, h: 1080, fps: 24 }, range: { start: 0, end: 30 } } as unknown as StageDoc
    setBlockRuns((_d, id) => (id === 'fig' ? [run] : []))
    try { expect(sampleDoc(doc, 15).objects[0].transform.pos[0]).toBeCloseTo(1.5) } finally { setBlockRuns(() => []) }
  })
})

describe('a block\'s evaluation (U5b)', () => {
  const b = { id: 'blk_a', source: { kind: 'library', id: 'mot_x', clip: 'Walk_Loop' }, start: 12, trim_in: 0, trim_out: null, loops: 1, speed: 1, blend_in: 6, blend_out: 0,
    in_place: false, foot_lock: true, ground: true, mirror: false, path: false, length: 0 } as MotionBlock
  const doc = { size: { w: 1920, h: 1080, fps: 24 } } as unknown as StageDoc
  it('reads the block, the figure\'s body and where it starts — not its blend or its measured length', () => {
    const k = blockKey(doc, fig, b, fig)
    expect(blockKey(doc, fig, { ...b, blend_in: 0, length: 90 }, fig)).toBe(k)
    expect(blockKey(doc, fig, { ...b, loops: 3 }, fig)).not.toBe(k)
    expect(blockKey(doc, fig, b, { transform: { pos: [1, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] } })).not.toBe(k)   // an earlier block moved: it re-flows
    expect(blockKey(doc, { ...fig, body: { height_m: 1.5 } as never }, b, fig)).not.toBe(k)
  })
  it('a template is re-based to where the figure stands and its facing, re-timed by its speed, repeated by its loops', () => {
    const t = { frames: 11, hip: 0.91, keys: [at(0, 5), at(10, 6)].map((k) => ({ ...k, transform: { ...k.transform, rot: [0, 90, 0] } })) }
    const where = { transform: { pos: [0, 0, 2], rot: [0, 0, 0], scale: [1, 1, 1] } }
    const keys = templateRun(t, fig, { start: 20, loops: 2, speed: 2, mirror: false, in_place: false }, where)
    expect(keys.map((k) => k.frame)).toEqual([20, 25, 30])                                 // 0, 10 / 2, then the loop's end
    expect(keys[0].transform.pos.map((v) => Math.round(v * 100) / 100)).toEqual([0, 0, 2])  // its first key where the figure stands
    expect(keys[0].transform.rot[1]).toBeCloseTo(0)                                         // facing the figure's way
    const step = Math.hypot(keys[1].transform.pos[0] - keys[0].transform.pos[0], keys[1].transform.pos[2] - keys[0].transform.pos[2])
    expect(step).toBeGreaterThan(0.5)                                                       // it travels (scaled by the hips)
    expect(templateRun(t, fig, { start: 0, loops: 1, speed: 1, mirror: false, in_place: true }, where).every((k) => k.transform.pos[0] === 0 && k.transform.pos[2] === 2)).toBe(true)
  })
})

describe('a block dragged on its track (U5c)', () => {
  const b = { id: 'blk_a', source: { kind: 'library', id: 'mot_x', clip: 'Wave' }, start: 24, trim_in: 0.5, trim_out: null, loops: 1, speed: 1, blend_in: 6, blend_out: 0,
    in_place: false, foot_lock: true, ground: true, mirror: false, path: false, length: 48 } as MotionBlock
  it('moves, trims its start and end in clip seconds, loops a looping clip, slides the clip inside it', async () => {
    const { dragPatch } = await import('./blockEdit')
    expect(dragPatch(b, 'move', -30, 24)).toEqual({ start: 0 })                             // not before frame 0
    expect(dragPatch(b, 'in', 12, 24)).toEqual({ start: 36, trim_in: 1 })                    // 12 frames = 0.5 s of clip
    expect(dragPatch(b, 'in', -24, 24)).toEqual({ start: 12, trim_in: 0 })                   // no further back than the clip's start
    expect(dragPatch(b, 'out', -24, 24)!.trim_out).toBeCloseTo(0.5 + 23 / 24, 9)
    expect(dragPatch({ ...b, loops: 2 }, 'out', 48, 24)).toEqual({ loops: 4 })              // 24 frames a loop: 96 frames → 4
    expect(dragPatch(b, 'slip', -6, 24)).toEqual({ trim_in: 0.75 })
    expect(dragPatch(b, 'move', 0, 24)).toBeNull()
  })
})
