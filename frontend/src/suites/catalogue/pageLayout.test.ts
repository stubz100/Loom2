// D68 (ArtCraft P6): album page geometry (D34) extracted from PageView — coordinates, fit, marquee, resize, z-order.
import { describe, expect, it } from 'vitest'
import { CARD_RATIO, fitView, itemHeight, marqueeHits, MIN_ITEM_W, resizedWidth, restack, toPage, zoomAbout, type Placed } from './pageLayout'

const photo = (id: string, x: number, y: number, w: number, z = 0) => ({ kind: 'asset', id, x, y, w, z })
const card = (id: string, x: number, y: number, w: number, z = 0) => ({ kind: 'group', id, x, y, w, z })
const square = (it: Placed) => itemHeight(it, { w: 100, h: 100 })

describe('itemHeight', () => {
  it('draws cards at the card ratio and photos at their aspect (4:3 while unknown)', () => {
    expect(itemHeight(card('g', 0, 0, 200))).toBe(200 * CARD_RATIO)
    expect(itemHeight(photo('a', 0, 0, 200), { w: 1920, h: 1080 })).toBeCloseTo(112.5)
    expect(itemHeight(photo('a', 0, 0, 200), { w: null, h: null })).toBe(150)
    expect(itemHeight(photo('a', 0, 0, 200))).toBe(150)
  })
})

describe('toPage / zoomAbout', () => {
  it('turns a client point into page coordinates through the host offset, the pan and the zoom', () => {
    expect(toPage(150, 90, { left: 50, top: 10 }, { x: 20, y: 30 }, 2)).toEqual({ x: 40, y: 25 })
    expect(toPage(70, 40, { left: 50, top: 10 }, { x: 20, y: 30 }, 1)).toEqual({ x: 0, y: 0 })
  })
  it('keeps the anchor point still while zooming', () => {
    const v = { x: 30, y: -10 }, cx = 200, cy = 120, z0 = 0.5, k = 3
    const before = toPage(cx, cy, { left: 0, top: 0 }, v, z0)
    const after = toPage(cx, cy, { left: 0, top: 0 }, zoomAbout(v, cx, cy, k), z0 * k)
    expect(after.x).toBeCloseTo(before.x); expect(after.y).toBeCloseTo(before.y)
  })
})

describe('fitView', () => {
  it('shows an empty page at its origin, zoom 1', () => {
    expect(fitView([], square, 800, 600)).toEqual({ zoom: 1, view: { x: 40, y: 40 } })
  })
  it('never enlarges, and centres the content horizontally', () => {
    const f = fitView([photo('a', 100, 100, 100)], square, 800, 600)
    expect(f.zoom).toBe(1)
    expect(f.view.x + 100 + 50).toBeCloseTo(400)                    // the item's centre lands on the host's centre
  })
  it('shrinks large content into the host with its margin, never below 0.1', () => {
    const items = [photo('a', 0, 0, 1000), photo('b', 1000, 0, 1000)]  // 2000 × 1000
    const f = fitView(items, square, 1064, 600)
    expect(f.zoom).toBeCloseTo(0.5)
    expect(f.view.x).toBeCloseTo(32)
    expect(f.view.y).toBeGreaterThanOrEqual(24)
    expect(fitView([photo('a', 0, 0, 100000)], square, 800, 600).zoom).toBe(0.1)
  })
})

describe('marqueeHits', () => {
  const items = [photo('a', 0, 0, 100), photo('b', 200, 0, 100), card('g', 0, 200, 100)]
  it('selects what the box overlaps, in any drag direction, through pan and zoom', () => {
    const view = { x: 10, y: 10 }, z = 0.5                         // page (0, 0) at host (10, 10); 100 page px = 50 host px
    const ids = (m: { x0: number; y0: number; x1: number; y1: number }) => marqueeHits(items, m, view, z, square).map((i) => i.id)
    expect(ids({ x0: 0, y0: 0, x1: 40, y1: 40 })).toEqual(['a'])
    expect(ids({ x0: 200, y0: 40, x1: 40, y1: 0 })).toEqual(['a', 'b'])
    expect(ids({ x0: 0, y0: 200, x1: 30, y1: 100 })).toEqual(['g'])
  })
  it('does not count touching an edge', () => {
    expect(marqueeHits(items, { x0: 100, y0: 0, x1: 200, y1: 50 }, { x: 0, y: 0 }, 1, square)).toEqual([])
  })
})

describe('resize and z-order', () => {
  it('resizes by the pointer move over the zoom, never below the minimum width', () => {
    expect(resizedWidth(200, 50, 0.5)).toBe(300)
    expect(resizedWidth(200, -1000, 1)).toBe(MIN_ITEM_W)
  })
  it('brings the selection to the front above everything, in selection order', () => {
    const items = [photo('a', 0, 0, 10, 3), photo('b', 0, 0, 10, 7), photo('c', 0, 0, 10, -2)]
    expect(restack(items, [items[2], items[0]], true).map((i) => [i.id, i.z])).toEqual([['c', 8], ['a', 9]])
  })
  it('sends the selection to the back strictly below everything else', () => {
    const items = [photo('a', 0, 0, 10, 3), photo('b', 0, 0, 10, 7), photo('c', 0, 0, 10, -2)]
    const back = restack(items, [items[1], items[0]], false)
    expect(back.map((i) => [i.id, i.z])).toEqual([['b', -4], ['a', -3]])
    expect(Math.max(...back.map((i) => i.z))).toBeLessThan(items[2].z)
  })
  it('works where every z is 0 (before D68 Send to back tied with the bottom item here)', () => {
    const items = [photo('a', 0, 0, 10), photo('b', 0, 0, 10)]
    expect(restack(items, [items[1]], true)[0].z).toBe(1)
    expect(restack(items, [items[1]], false)[0].z).toBe(-1)
    expect(restack([photo('c', 0, 0, 10, -5)], [photo('c', 0, 0, 10, -5)], true)[0].z).toBe(1)
  })
})
