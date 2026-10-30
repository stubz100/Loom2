// D165: the Windows view's keys (the twin of orchestrator/loom2/boxes.py) and the final it opens on.
import { describe, expect, it } from 'vitest'
import { boxAt, moved, rectOf, removeAt, resized, upsert, type BoxKey } from './boxKeys'

const WIN: [number, number] = [480, 848]

describe('the boxes as keys (D165)', () => {
  it('interpolate in straight lines between keys and hold the ends', () => {
    const keys: BoxKey[] = [{ frame: 9, cx: 50, cy: 20, h: 30 }, { frame: 5, cx: 10, cy: 20, h: 10 }]
    expect(boxAt(keys, 'window', 0)).toEqual({ cx: 10, cy: 20, size: 10 })
    expect(boxAt(keys, 'window', 7)).toEqual({ cx: 30, cy: 20, size: 20 })
    expect(boxAt(keys, 'window', 20)).toEqual({ cx: 50, cy: 20, size: 30 })
    expect(boxAt([], 'head', 3)).toBeNull()
  })
  it('a window keeps Wan\'s portrait shape, a head box is square; moving and resizing keep them so', () => {
    expect(rectOf({ cx: 100, cy: 200, size: 848 }, 'window', WIN)).toEqual([-140, -224, 480, 848])
    expect(rectOf({ cx: 100, cy: 200, size: 40 }, 'head', WIN)).toEqual([80, 180, 40, 40])
    expect(moved({ cx: 1, cy: 2, size: 3 }, 10, 20)).toEqual({ cx: 11, cy: 22, size: 3 })
    expect(resized({ cx: 0, cy: 0, size: 100 }, 'window', 48, 10, WIN).size).toBeCloseTo(169.6)   // the corner 48 px right: 96 px wide → 169.6 tall
    expect(resized({ cx: 0, cy: 0, size: 100 }, 'head', 2, 1, WIN).size).toBe(8)                  // never under the smallest size
  })
  it('a key set at a frame replaces the one there; a key deleted leaves the others', () => {
    const keys: BoxKey[] = [{ frame: 0, cx: 1, cy: 1, side: 40 }, { frame: 10, cx: 5, cy: 5, side: 40 }]
    const set = upsert(keys, 'head', 10, { cx: 6.004, cy: 7, size: 50 })
    expect(set).toEqual([{ frame: 0, cx: 1, cy: 1, side: 40 }, { frame: 10, cx: 6, cy: 7, side: 50 }])
    expect(upsert(keys, 'head', 4, { cx: 2, cy: 2, size: 2 }).map((k) => [k.frame, k.side])).toEqual([[0, 40], [4, 8], [10, 40]])
    expect(removeAt(set, 0)).toEqual([{ frame: 10, cx: 6, cy: 7, side: 50 }])
  })
  it('the view opens on the shot version\'s newest final, else the stage\'s newest', async () => {
    const { finalFor } = await import('./windowsStore')
    const f = (id: string, at: string, extra = {}) => ({ id, created_at: at, shot_id: 'sht_a', shot_version: 'v1', ...extra }) as never
    const finals = [f('f1', '1'), f('f2', '2'), f('f3', '3', { shot_id: 'sht_b' })]
    expect(finalFor(finals, 'sht_a', 'v1')).toEqual(expect.objectContaining({ id: 'f2' }))
    expect(finalFor(finals, 'sht_c', 'v1')).toEqual(expect.objectContaining({ id: 'f3' }))
    expect(finalFor([], 'sht_a', 'v1')).toBeNull()
  })
})
