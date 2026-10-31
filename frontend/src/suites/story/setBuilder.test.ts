// proto01_UIcast CW6 (D143): what a place's set builder says — its fit running or failed, a set changed since its bake, the faces to fill
// and how much of the set they are.
import { describe, expect, it } from 'vitest'
import type { Job, Profile } from '../../api/types'
import { bakeKey, type SourceCam } from '../stage/setOverlay'
import type { PlaceSetDoc } from '../stage/placeSet'
import { bakedFresh, setStatus, unseenShare, type PlaceSet } from './setBuilder'

type Version = Profile['versions'][number]
const cam: SourceCam = { pos: [0.3, 1.6, 2], target: [0.1, 1.3, -3], roll: 0, focal_mm: 24, sensor_mm: 36 }
const face = (id: string, bad: number, extra: Partial<PlaceSet['faces'][number]> = {}): PlaceSet['faces'][number] => ({ id, texture_asset_id: 'ast_t', baked_asset_id: 'ast_t', coverage_asset_id: 'ast_c',
  texel_m: 0.01, seen: 1 - bad, bad, filled: false, material: '', fill_job_id: null, crowd: null, ...extra })
const set = (faces: PlaceSet['faces'], key: string | null = null): PlaceSet => ({ kind: 'room', sizes: { width: 5, depth: 6, height: 2.8 }, parts: {}, faces, baked_key: key,
  sources: [{ asset_id: 'ast_pic', camera: cam, relief_asset_id: null, assumed: [], lens_deg: 73.7, made_at: '2026-10-25T18:00:00Z' }] })
const ver = (ps: PlaceSet | null): Version => ({ id: 'v1', anim_ref_asset_id: 'ast_pic', hero_asset_id: null, place_set: ps } as unknown as Version)
const job = (status: Job['status'], result: Record<string, unknown> = {}, created_at = '2026-10-25T18:30:00Z'): Record<string, Job> =>
  ({ j1: { id: 'j1', status, result, created_at, progress: 0.4, origin: { suite: 'story', surface: 'set_fit', ref: 'prf_k', payload: { version: 'v1' } } } as unknown as Job })

describe("a place's set builder (CW6)", () => {
  it('says what the fit is doing, and why it fitted nothing', () => {
    expect(setStatus(ver(null), {}, 'prf_k', false).text).toBe('no set yet')
    expect(setStatus(ver(null), job('running'), 'prf_k', false).text).toBe('fitting the set… 40 %')
    const no = setStatus(ver(null), job('done', { set_error: 'too little floor in the picture' }), 'prf_k', false)
    expect(no).toEqual({ text: 'not fitted: too little floor in the picture', warn: true })
    expect(setStatus(ver(set([])), {}, 'prf_k', false).text).toBe('fitted · not baked yet')
  })
  it('knows a bake made for another set or camera, and the faces still to fill', () => {
    const key = bakeKey(set([]) as PlaceSetDoc, cam)
    const fresh = set([face('floor', 0.5), face('wall_back', 0), face('ceiling', 0.3, { filled: true })], key)
    expect(bakedFresh(fresh)).toBe(true)
    expect(bakedFresh({ ...fresh, sizes: { ...fresh.sizes, depth: 7 } })).toBe(false)
    expect(setStatus(ver({ ...fresh, sizes: { ...fresh.sizes, depth: 7 } }), {}, 'prf_k', false)).toEqual({ text: 'changed since the bake', warn: true })
    expect(unseenShare(fresh)).toBeCloseTo((0.5 * 30) / (30 + 14 + 30), 3)                     // the floor's half of its 5 × 6 m; the filled ceiling counts as seen
    expect(setStatus(ver(fresh), {}, 'prf_k', false).text).toBe('1 face to fill · 20 % of the set')
    expect(setStatus(ver(set([face('floor', 0.5, { filled: true })], key)), {}, 'prf_k', false).text).toBe('baked and filled')
    expect(setStatus(ver(fresh), {}, 'prf_k', true).text).toBe('baking the faces…')
  })
})
