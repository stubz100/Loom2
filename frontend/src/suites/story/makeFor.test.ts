// D90 (02 §5, §4.2): Make ▸ for a shot version — the version it works for, what the makers start from, a board's references in mention
// order, and the board drop rule on a Flow node.
import { describe, expect, it } from 'vitest'
import type { Asset, FlowNode, GroupPage, Profile, Shot } from '../../api/types'
import { boardDrop, boardRefs, clipPrefill, forShot, framePrefill, makeTarget } from './makeFor'

const node = (type: FlowNode['type'], extra: Partial<FlowNode> = {}): FlowNode => ({
  schema_version: 1, id: 'node_1', type, title: '', lines: [], options: [], cond: null, set: [], target: null, text: '', shot_id: null, shot_version: null, board_group_id: null, colour: null,
  revision: 0, created_at: '', updated_at: '', ...extra,
})
const version = (id: string, state: 'open' | 'final' = 'open') => ({ id, state, stage_id: null, camera_id: null, stage_revision: null, frame_asset_id: null, clip_id: null, takes: [], derived_from: null, created_at: '', finalized_at: null })
const shot = (current: string, versions: ReturnType<typeof version>[], owner: string | null = null): Shot =>
  ({ schema_version: 1, id: 'sht_1', name: 'Shot 12', owner_node: owner, current, versions, revision: 0, created_at: '', updated_at: '' }) as Shot
const profile = (id: string, name: string): Profile => ({ id, name, cls: 'character', current: 'v1', versions: [{ id: 'v1', group_id: `grp_${id}` }] }) as unknown as Profile

describe('makeTarget / forShot', () => {
  it('works for the asked version when open, else the current one when open, else none', () => {
    const s = shot('v2', [version('v1', 'final'), version('v2')])
    expect(makeTarget(s, 'v1')?.id).toBe('v2')                        // a node pins a final version: the current open one
    expect(makeTarget(s, 'v2')?.id).toBe('v2')
    expect(makeTarget(s)?.id).toBe('v2')
    expect(makeTarget(shot('v1', [version('v1', 'final')]), 'v1')).toBeNull()
    expect(makeTarget(undefined)).toBeNull()
    expect(forShot(s, s.versions[1], null)).toEqual({ kind: 'shot', shot_id: 'sht_1', version: 'v2', name: 'Shot 12', node_id: null })
    expect(forShot(shot('v1', [version('v1')], 'node_7'), version('v1')).node_id).toBe('node_7')        // the owner when Make came from Shots
  })
})

describe('framePrefill / clipPrefill', () => {
  const cast = [profile('prf_m', 'Mara'), profile('prf_j', 'Joe')]
  it('a Shot node gives its line (else its title); a Dialogue node its title and its speakers as @mentions', () => {
    expect(framePrefill(node('shot', { text: 'Mara opens the gate.', title: 'Gate' }), cast)).toEqual({ text: 'Mara opens the gate', mentions: [] })
    expect(framePrefill(node('shot', { title: 'Gate' }), cast).text).toBe('Gate')
    const d = node('dialogue', { title: 'At the gate', lines: [{ speaker: 'prf_m', text: 'Hi.', audio_asset_id: null, audio_text: null }, { speaker: 'prf_j', text: 'Hey.', audio_asset_id: null, audio_text: null }, { speaker: 'prf_m', text: 'Bye.', audio_asset_id: null, audio_text: null }] })
    const p = framePrefill(d, cast)
    expect(p.text).toBe('@Mara and @Joe, At the gate')
    expect(p.mentions).toEqual([{ group_id: 'grp_prf_m', name: 'Mara', profile_id: 'prf_m' }, { group_id: 'grp_prf_j', name: 'Joe', profile_id: 'prf_j' }])
  })
  it('nothing to say leaves the prompt alone', () => {
    expect(framePrefill(undefined, cast)).toEqual({ text: null, mentions: [] })
    expect(framePrefill(node('shot'), cast).text).toBeNull()
    expect(framePrefill(node('hub', { title: 'Crossroads' }), cast).text).toBeNull()
    expect(clipPrefill(node('shot', { text: ' the gate swings open ' }))).toBe('the gate swings open')
    expect(clipPrefill(node('dialogue', { text: 'x' }))).toBeNull()
    expect(clipPrefill(undefined)).toBeNull()
  })
})

describe('boardRefs / boardDrop', () => {
  const a = (id: string, kind = 'image', trashed: string | null = null) => ({ id, kind, trashed_at: trashed }) as unknown as Asset
  const item = (id: string, x: number, y: number, kind: 'asset' | 'group' = 'asset') => ({ id, kind, x, y, w: 240, z: 0 })
  it('the cover first, then the page top to bottom, left to right; clips and trashed assets skipped', () => {
    const page = { group: { cover_id: 'ast_c', items: [item('ast_b', 300, 0), item('ast_a', 0, 0), item('ast_c', 0, 400), item('ast_v', 0, 200), item('ast_t', 600, 0), item('grp_x', 0, 50, 'group'), item('ast_d', 0, 300)] },
      assets: { ast_a: a('ast_a'), ast_b: a('ast_b'), ast_c: a('ast_c'), ast_d: a('ast_d'), ast_v: a('ast_v', 'video'), ast_t: a('ast_t', 'image', '2026-10-16') } } as unknown as GroupPage
    expect(boardRefs(page)).toEqual(['ast_c', 'ast_a', 'ast_b', 'ast_d'])
    expect(boardRefs({ ...page, group: { ...page.group, cover_id: null } } as GroupPage)).toEqual(['ast_a', 'ast_b', 'ast_d', 'ast_c'])
  })
  it('one group card is a board; images and several groups are refused with the reason', () => {
    expect(boardDrop({ items: [{ kind: 'group', id: 'grp_1' }], label: 'Gate refs' }, 'Gate')).toEqual({ group: 'grp_1', verdict: { ok: true, label: 'Make "Gate refs" the board of Gate' } })
    expect(boardDrop({ items: [{ kind: 'asset', id: 'ast_1' }] }, 'Gate').verdict).toMatchObject({ ok: false, reason: expect.stringMatching(/A board is a group/) })
    expect(boardDrop({ items: [{ kind: 'group', id: 'grp_1' }, { kind: 'group', id: 'grp_2' }] }, 'Gate').verdict).toMatchObject({ ok: false, reason: expect.stringMatching(/One board per node/) })
    expect(boardDrop({ items: [] }, 'Gate').verdict.ok).toBe(false)
  })
})
