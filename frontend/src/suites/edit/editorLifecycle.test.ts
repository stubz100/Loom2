// The editor's Pixi application must never be destroyed with `true`: in Pixi 8 that releases the global resource pools, and the batch
// pool hands the same Batch objects to every renderer — a live one (StrictMode's second mount, a remount during a slow init) then draws
// with destroyed batches and throws "Cannot read properties of null (reading 'geometry')" (2026-10-11, reproduced in Edge). A source
// check, since a jsdom test has no WebGL: every Application destroy in the editor keeps the shared pools.
import { describe, expect, it } from 'vitest'
import source from './EditorCanvas.tsx?raw'

describe('EditorCanvas lifecycle', () => {
  it('destroys its Pixi application without releasing the global pools', () => {
    const appDestroys = source.match(/\b(?:app|appRef\.current\??)\.destroy\(([^)]*)\)/g) ?? []
    expect(appDestroys.length).toBeGreaterThanOrEqual(3)
    for (const call of appDestroys) expect(call, call).toMatch(/\.destroy\(KEEP_SHARED\b/)
    expect(source).toMatch(/const KEEP_SHARED = \{ removeView: true \} as const/)
  })
})
