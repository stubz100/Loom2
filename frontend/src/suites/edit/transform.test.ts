// D68 (ArtCraft P6): the free transform's maths (D58) — homography fit and inverse, the convexity guard, the strip readout and the
// numeric scale / rotate about the reference point.
import { describe, expect, it } from 'vitest'
import { applyDrag, Homography, hitTest, insideQuad, isIdentity, keepConvex, readout, rectCorners, rotateAboutPivot, scaleAboutPivot, type Pt, type Quad, type Xform } from './transform'

const near = (a: Pt, b: Pt, eps = 1e-6) => { expect(a.x).toBeCloseTo(b.x, -Math.log10(eps)); expect(a.y).toBeCloseTo(b.y, -Math.log10(eps)) }
const xform = (rect: Xform['rect'], quad: Quad = rectCorners(rect), pivot?: Pt): Xform =>
  ({ nodeId: 'lyr_1', rect, quad, pivot: pivot ?? { x: (rect[0] + rect[2]) / 2, y: (rect[1] + rect[3]) / 2 }, interp: 'bilinear', mode: 'free', selection: false })
const turns = (q: Quad) => q.map((b, i) => { const a = q[(i + 3) % 4], c = q[(i + 1) % 4]; return (b.x - a.x) * (c.y - b.y) - (b.y - a.y) * (c.x - b.x) })
const PERSPECTIVE: Quad = [{ x: 12, y: 8 }, { x: 230, y: 30 }, { x: 205, y: 160 }, { x: 25, y: 140 }]

describe('Homography', () => {
  it('maps the rect corners onto the quad (affine and perspective)', () => {
    const rect = [10, 20, 210, 120]
    for (const quad of [rectCorners([0, 0, 400, 200]), PERSPECTIVE]) {
      const h = Homography.rectToQuad(rect, quad)!
      rectCorners(rect).forEach((c, i) => near(h.apply(c.x, c.y), quad[i]))
    }
  })
  it('round-trips points through its inverse', () => {
    const h = Homography.rectToQuad([0, 0, 100, 80], PERSPECTIVE)!
    const inv = h.inverse()!
    for (const p of [{ x: 0, y: 0 }, { x: 50, y: 40 }, { x: 99.5, y: 3.25 }, { x: -20, y: 130 }]) {
      const q = h.apply(p.x, p.y)
      near(inv.apply(q.x, q.y), p, 1e-6)
    }
    const id = h.mul(inv)
    near(id.apply(37, 11), { x: 37, y: 11 })
  })
  it('refuses degenerate input', () => {
    expect(Homography.rectToQuad([0, 0, 0, 10], PERSPECTIVE)).toBeNull()
    expect(Homography.squareToQuad([{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 2, y: 0 }, { x: 3, y: 0 }])).toBeNull()
    expect(new Homography([1, 2, 3, 2, 4, 6, 0, 0, 1]).inverse()).toBeNull()
  })
  it('measures the local scale of a uniform scale', () => {
    const h = Homography.rectToQuad([0, 0, 100, 100], rectCorners([0, 0, 200, 200]))!
    expect(h.localScale(50, 50)).toBeCloseTo(2, 9)
    expect(Homography.affine(3, 0, 0, 3, 5, 5).localScale(0, 0)).toBeCloseTo(3, 9)
  })
})

describe('box state', () => {
  it('knows an untouched box', () => {
    expect(isIdentity(xform([0, 0, 64, 32]))).toBe(true)
    expect(isIdentity(xform([0, 0, 64, 32], rectCorners([1, 0, 65, 32])))).toBe(false)
  })
  it('hit-tests handles before the body and the body before the outside', () => {
    const t = xform([0, 0, 100, 100], undefined, { x: 30, y: 30 })
    expect(hitTest(t, { x: 101, y: 1 }, 6)).toEqual({ kind: 'corner', i: 1 })
    expect(hitTest(t, { x: 50, y: 99 }, 6)).toEqual({ kind: 'edge', i: 2 })
    expect(hitTest(t, { x: 31, y: 29 }, 6)).toEqual({ kind: 'pivot' })
    expect(hitTest(t, { x: 70, y: 60 }, 6)).toEqual({ kind: 'inside' })
    expect(hitTest(t, { x: 140, y: 60 }, 6)).toEqual({ kind: 'outside' })
    expect(insideQuad(PERSPECTIVE, { x: 120, y: 90 })).toBe(true)
    expect(insideQuad(PERSPECTIVE, { x: 5, y: 150 })).toBe(false)
  })
})

describe('keepConvex', () => {
  const q0 = rectCorners([0, 0, 100, 100])
  it('leaves a convex result alone', () => {
    const q: Quad = [{ x: 0, y: 0 }, { x: 100, y: 0 }, { x: 140, y: 130 }, { x: 0, y: 100 }]
    expect(keepConvex(q0, q)).toBe(q)
  })
  it('stops a fold at the last convex point on the way', () => {
    const fold: Quad = [{ x: 0, y: 0 }, { x: 100, y: 0 }, { x: -60, y: -40 }, { x: 0, y: 100 }]   // corner 2 dragged across the box
    const kept = keepConvex(q0, fold)
    const sign = Math.sign(turns(q0)[0])
    expect(turns(kept).every((v) => Math.sign(v) === sign)).toBe(true)
    // it moved part of the way, along the drag, and only corner 2 moved
    expect(kept[2].x).toBeLessThan(100); expect(kept[2].x).toBeGreaterThan(-60)
    expect(kept[2].y / 100 - 1).toBeCloseTo((kept[2].x / 100 - 1) * (140 / 160), 6)
    near(kept[0], q0[0]); near(kept[1], q0[1]); near(kept[3], q0[3])
  })
  it('leaves a degenerate start free', () => {
    const flat: Quad = [{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 2, y: 0 }, { x: 3, y: 0 }]
    const q: Quad = [{ x: 0, y: 0 }, { x: 1, y: 5 }, { x: 2, y: 0 }, { x: 3, y: 0 }]
    expect(keepConvex(flat, q)).toBe(q)
  })
})

describe('readout, scale and rotate about the pivot', () => {
  it('reads W / H as a share of the frame and the top edge angle', () => {
    expect(readout(xform([0, 0, 200, 100]))).toEqual({ sx: 1, sy: 1, angle: 0 })
    const r = readout(xform([0, 0, 200, 100], rectCorners([10, 10, 510, 60])))
    expect(r.sx).toBeCloseTo(2.5); expect(r.sy).toBeCloseTo(0.5); expect(r.angle).toBeCloseTo(0)
  })
  it('scales in the box frame and keeps the pivot still', () => {
    const t = xform([0, 0, 200, 100], undefined, { x: 50, y: 25 })
    const q = scaleAboutPivot(t, 1.5, 0.5)
    const after = { ...t, quad: q }
    expect(readout(after).sx).toBeCloseTo(1.5); expect(readout(after).sy).toBeCloseTo(0.5)
    const h0 = Homography.squareToQuad(t.quad)!.inverse()!, h1 = Homography.squareToQuad(q)!
    const u = h0.apply(t.pivot.x, t.pivot.y)
    near(h1.apply(u.x, u.y), t.pivot)
    expect(scaleAboutPivot(t, 1, 1)).toEqual(t.quad)
  })
  it('rotates about the pivot: distances kept, the angle reads back, a full turn returns', () => {
    const t = xform([0, 0, 200, 100], undefined, { x: 20, y: 70 })
    const q = rotateAboutPivot(t, 30)
    q.forEach((c, i) => expect(Math.hypot(c.x - t.pivot.x, c.y - t.pivot.y)).toBeCloseTo(Math.hypot(t.quad[i].x - t.pivot.x, t.quad[i].y - t.pivot.y), 9))
    const r = readout({ ...t, quad: q })
    expect(r.angle).toBeCloseTo(30); expect(r.sx).toBeCloseTo(1); expect(r.sy).toBeCloseTo(1)
    rotateAboutPivot(t, 360).forEach((c, i) => near(c, t.quad[i]))
  })
})

describe('applyDrag', () => {
  const t = xform([0, 0, 200, 100], undefined, { x: 100, y: 50 })
  const none = { shift: false, alt: false, ctrl: false }
  it('moves the box and the pivot together from inside', () => {
    const r = applyDrag(t, { kind: 'inside' }, t.quad, t.pivot, { x: 10, y: 10 }, { x: 25, y: 5 }, none)
    r.quad.forEach((c, i) => near(c, { x: t.quad[i].x + 15, y: t.quad[i].y - 5 }))
    near(r.pivot, { x: 115, y: 45 })
  })
  it('scales proportionally from a corner, the opposite corner fixed', () => {
    const r = applyDrag(t, { kind: 'corner', i: 2 }, t.quad, t.pivot, { x: 200, y: 100 }, { x: 400, y: 120 }, none)
    near(r.quad[0], t.quad[0])
    const ro = readout({ ...t, quad: r.quad })
    expect(ro.sx).toBeCloseTo(2); expect(ro.sy).toBeCloseTo(2)
  })
  it('never accumulates: the same pointer gives the same box', () => {
    const a = applyDrag(t, { kind: 'outside' }, t.quad, t.pivot, { x: 300, y: 50 }, { x: 100, y: 250 }, none)
    const b = applyDrag(t, { kind: 'outside' }, t.quad, t.pivot, { x: 300, y: 50 }, { x: 100, y: 250 }, none)
    expect(a).toEqual(b)
    expect(readout({ ...t, quad: a.quad }).angle).toBeCloseTo(90)
  })
})
