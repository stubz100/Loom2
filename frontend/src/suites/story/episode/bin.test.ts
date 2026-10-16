// D90 (B7, Y57): the Shots bin offers the final version's clip, and the lane's drop stamps a Shots-bin card with its shot.
import { describe, expect, it } from 'vitest'
import { binVersion, laneTake, shotRows } from './bin'

const v = (id: string, state: 'open' | 'final', clip_id: string | null) => ({ id, state, clip_id })
const shots = [
  { id: 'sht_b', name: 'Bridge', current: 'v3', owner_node: 'nd_1', versions: [v('v1', 'final', 'clp_b1'), v('v2', 'final', 'clp_b2'), v('v3', 'open', 'clp_b3')] },
  { id: 'sht_a', name: 'Alley', current: 'v1', owner_node: null, versions: [v('v1', 'open', 'clp_a1')] },
  { id: 'sht_c', name: 'Cellar', current: 'v2', owner_node: 'nd_2', versions: [v('v1', 'open', 'clp_c1'), v('v2', 'final', 'clp_c2')] },
  { id: 'sht_d', name: 'Dock', current: 'v1', owner_node: null, versions: [v('v1', 'open', null)] },
]
const clips = ['clp_b1', 'clp_b2', 'clp_b3', 'clp_a1', 'clp_c1', 'clp_c2', 'clp_x'].map((id) => ({ id, asset_id: `ast_${id}` }))
const drag = (ids: string[], from?: string) => ({ items: ids.map((id) => ({ kind: 'asset' as const, id, media: 'video' as const })), from })

describe('Episode bins (D90)', () => {
  it('takes the final version: the current when final, else the newest final, else the current (Y57)', () => {
    expect(binVersion(shots[0])?.id).toBe('v2')
    expect(binVersion(shots[1])?.id).toBe('v1')
    expect(binVersion(shots[2])?.id).toBe('v2')
  })
  it('lists shots with a clip, final ones first, then by name', () => {
    expect(shotRows(shots, clips).map((r) => `${r.sh.id}:${r.v.id}:${r.c.id}`)).toEqual(['sht_b:v2:clp_b2', 'sht_c:v2:clp_c2', 'sht_a:v1:clp_a1'])
  })
  it('stamps a Shots-bin card with its shot, version and node; a clip from elsewhere lands plain (B7)', () => {
    const card = laneTake(drag(['ast_clp_b2'], 'shots-bin'), clips, shots)
    expect(card.verdict).toEqual({ ok: true, label: 'Add Bridge to the end of the episode' })
    expect(card.take).toEqual([{ clip: clips[1], shot: { id: 'sht_b', version: 'v2', node: 'nd_1' } }])
    const plain = laneTake(drag(['ast_clp_b2'], 'sequence-bin'), clips, shots)
    expect(plain.take).toEqual([{ clip: clips[1] }])
    expect(plain.verdict.ok).toBe(true)
  })
  it('refuses what is not a clip of the project', () => {
    expect(laneTake(drag(['ast_unknown'], 'shots-bin'), clips, shots)).toEqual({ take: [], verdict: { ok: false, reason: 'Only clips go on the lane' } })
  })
})
