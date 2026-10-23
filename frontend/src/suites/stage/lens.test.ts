// D123 (SC3c-1): the lens a set from an image is asked for — what the author types, and what the picture knows of its own.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { Asset } from '../../api/types'
import { hfovOfMm, lensGuess, mmInText, parseLens } from './lens'

describe('parseLens', () => {
  it('reads degrees, a focal length in mm, or nothing (MoGe reads it)', () => {
    expect(parseLens('')).toBeNull()
    expect(parseLens('   ')).toBeNull()
    expect(parseLens('70')).toBe(70)
    expect(parseLens('69.5°')).toBe(69.5)
    expect(parseLens('75 deg')).toBe(75)
    expect(parseLens('35 mm')).toBe(hfovOfMm(35))
    expect(parseLens('24mm')).toBe(73.7)                                        // 2·atan(18/24)
    expect(parseLens('50,0 mm')).toBe(39.6)
  })
  it('refuses what is not a lens, or one outside 20–150°', () => {
    for (const t of ['wide', '10', '200°', '3 mm', '300 mm', '35 cm', '-40']) expect(parseLens(t), t).toBe('invalid')
    expect(parseLens('8 mm')).toBe(132.1)                                       // a very wide lens is still one
  })
})

describe('what the picture knows', () => {
  afterEach(() => vi.unstubAllGlobals())
  const asset = (a: Partial<Asset>) => ({ id: 'ast_1', params: {}, prompt_json: null, prompt_text: null, ...a }) as unknown as Asset
  it('a prompt names its lens', () => {
    expect(mmInText('a 50 mm portrait lens')).toBe(50)
    expect(mmInText('35mm, shallow focus')).toBe(35)
    expect(mmInText('wide shot')).toBeNull()
  })
  it("a Stage still gives its camera's focal; a prompt its lens; nothing gives none", async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(input instanceof Request ? input.url : String(input))
      return url.pathname === '/stages/stg_1' ? Response.json({ id: 'stg_1', cameras: [{ id: 'cam_a', name: 'Camera 1', focal_mm: 28 }] }) : new Response('gone', { status: 404 })
    }))
    setBackend({ host: '127.0.0.1', port: 8766, token: 't' })                    // after the stub: the client takes fetch when it is made
    expect(await lensGuess(asset({ params: { recipe: { kind: 'stage_shot', stage_id: 'stg_1', camera_id: 'cam_a' } } }))).toEqual({ mm: 28, from: 'the Stage camera Camera 1' })
    expect(await lensGuess(asset({ params: { recipe: { kind: 'stage_shot', stage_id: 'stg_gone', camera_id: 'cam_a' } } }))).toBeNull()
    expect(await lensGuess(asset({ prompt_json: { camera: { lens: '85mm telephoto' } } }))).toEqual({ mm: 85, from: 'the prompt' })
    expect(await lensGuess(asset({ prompt_text: 'a quiet street, 24 mm' }))).toEqual({ mm: 24, from: 'the prompt' })
    expect(await lensGuess(asset({}))).toBeNull()
  })
})
