// D190: the skeleton panel's pictures to pick from — those made as the part first (the newest first), the A-pose views for the feet, the rest.
import { describe, expect, it } from 'vitest'
import { picturesFor, type BinItem } from './rigPictures'

const item = (id: string, side: string | null, at = '2026-11-05T10:00:00', kind = 'image'): BinItem => ({ page: 'grp', roles: [],
  asset: { id, kind, created_at: at, origin: side ? { suite: 'story', surface: 'anim_ref', ref: 'prf_g', payload: { version: 'v1', side } } : null } } as unknown as BinItem)
const v = { anim_ref_asset_id: 'a_front', anim_ref_back_asset_id: null, anim_ref_side_asset_id: 'a_side' }

describe('D190: a hand or feet picture is picked from the version\'s pictures', () => {
  const items = [item('h1', 'hand', '2026-11-05T09:00:00'), item('h2', 'hand', '2026-11-05T10:00:00'), item('f1', 'feet'), item('a_front', 'front'), item('a_side', 'side'),
    item('hero', null), item('clip', null, '2026-11-05T10:00:00', 'video')]
  it('hands: the hand pictures made, the newest first, then the rest (no A-pose view: a hand is read from a close-up)', () => {
    const g = picturesFor(items, v, 'hand')
    expect(g.made.map((x) => x.asset.id)).toEqual(['h2', 'h1'])
    expect(g.views).toEqual([])
    expect(g.others.map((x) => x.asset.id)).toEqual(['f1', 'a_front', 'a_side', 'hero'])          // a video is no picture
  })
  it('feet: the feet pictures made, then the side view and the A-pose to pick (never picked for the author)', () => {
    const g = picturesFor(items, v, 'feet')
    expect(g.made.map((x) => x.asset.id)).toEqual(['f1'])
    expect(g.views.map((x) => x.asset.id)).toEqual(['a_side', 'a_front'])
    expect(g.others.map((x) => x.asset.id)).toEqual(['h1', 'h2', 'hero'])   // the bin's order
  })
})
