// U3b (D157, proto01_UI2 03 §3): an entity version's Make panel is its own — a context never seen is seeded with the entity linked (a
// subject card, or a place's scene); returning restores what was set there; every class has its framings.
import { describe, expect, it, vi } from 'vitest'
import { makeContext, useGenerate } from '../../suites/generate/generateStore'
import { enterMake, FRAMINGS, makeKey } from './make'

describe('U3b: Make per entity', () => {
  it('seeds a new context with the entity, restores a known one', () => {
    vi.spyOn(useGenerate.getState(), 'refreshPreview').mockResolvedValue(undefined as never)
    const frame = vi.spyOn(useGenerate.getState(), 'applyFrame').mockImplementation(() => {})
    enterMake('character', 'prf_ines', 'v1')
    expect(frame).toHaveBeenLastCalledWith({ text: null, subjects: [{ profile_id: 'prf_ines', version: 'v1' }], place: null })
    useGenerate.getState().set({ text: 'kept for Ines' })
    enterMake('place', 'prf_quay', 'v1')
    expect(frame).toHaveBeenLastCalledWith({ text: null, subjects: [], place: 'prf_quay' })
    expect(frame).toHaveBeenCalledTimes(2)
    enterMake('character', 'prf_ines', 'v1')
    expect(frame).toHaveBeenCalledTimes(2)                                                     // known: restored, not seeded again
    expect(useGenerate.getState().panel.text).toBe('kept for Ines')
    expect(makeContext.key).toBe(makeKey('character', 'prf_ines', 'v1'))
  })
  it('gives every class three framings', () => {
    expect(Object.fromEntries(Object.entries(FRAMINGS).map(([k, f]) => [k, f.map((x) => x.label)]))).toEqual({
      character: ['portrait', 'waist-up', 'full body'], prop: ['on its own', 'in a hand', 'in its setting'], place: ['wide', 'empty, eye level', 'a detail'] })
  })
})
