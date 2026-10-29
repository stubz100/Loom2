// U8 (D157, proto01_UI2 05 §2): the Bin's pure parts — a home's path by its names, every home (and its role pages) by id, the kind chips,
// and where a home's thing belongs (World's version, the Look, a shot, a cut; nothing for the imports).
import { describe, expect, it } from 'vitest'
import type { BinNode, BinThing } from '../../api/types'
import { belongs, moveTargets } from './binCommands'
import { homesById, passes, pathLabel, subtreeIds, touches, TRASH, useBin } from './binStore'

const node = (id: string, path: string, name: string, children: BinNode[] = [], pages: string[] = []): BinNode => ({ id, path, name, count: 0, total: 0, pages, children, gone: false, page: false })
const homes = [
  node('g_w', 'world', 'World', [node('g_c', 'world/character', 'Characters', [node('g_i', 'world/character/prf_1', 'Ines', [node('g_v', 'world/character/prf_1/v1', 'v1 · rain gear', [], ['g_ref'])])])]),
  node('g_s', 'shots', 'Shots', [node('g_sh', 'shots/sht_9', 'The seal', [node('g_sv', 'shots/sht_9/v1', 'v1')])]),
  node('g_im', 'imports', 'Imports'),
]

describe('the Bin (U8)', () => {
  it('names a path by its homes, finds a home by its id or a role page', () => {
    expect(pathLabel(homes, 'world/character/prf_1/v1')).toBe('world/character/Ines/v1')
    expect(pathLabel(homes, 'shots/sht_9/v1')).toBe('shots/The seal/v1')
    const by = homesById(homes)
    expect(by.get('g_ref')?.id).toBe('g_v')                                   // the reference set is a role inside its version's home
    expect(by.get('g_sv')?.path).toBe('shots/sht_9/v1')
  })
  it('filters by kind and says where a thing belongs', () => {
    const t = (kind: string) => ({ asset: { kind }, roles: [], path: '' }) as unknown as BinThing
    expect([passes(t('image'), 'pictures'), passes(t('video'), 'pictures'), passes(t('video'), 'clips'), passes(t('mesh'), 'models'), passes(t('audio'), 'all')]).toEqual([true, false, true, true, true])
    expect(belongs('world/character/prf_1/v1')?.label).toBe('its version in World')
    expect(belongs('world/look')?.label).toBe('the Look')
    expect(belongs('shots/sht_9/v1')?.label).toBe('its shot')
    expect(belongs('episode/tl_1')?.label).toBe('its cut')
    expect([belongs('imports'), belongs('trash'), belongs('')]).toEqual([null, null, null])
  })
  it('offers every other home to move to', () => {
    const labels = moveTargets(homes, 'g_v').map((m) => ('label' in m ? m.label : ''))
    expect(labels.map((l) => l?.trim())).toEqual(['World', 'Characters', 'Ines', 'Shots', 'The seal', 'v1', 'Imports'])
  })
})

describe('the Bin holds up (B0, D159)', () => {
  const at = (open: string | null, query = '') => ({ open, homes, query })
  it('reads the open home again only when a frame touches it', () => {
    expect([...subtreeIds(homes[0])]).toEqual(['g_w', 'g_c', 'g_i', 'g_v', 'g_ref'])
    expect(touches({ type: 'group.changed', data: { ids: ['g_ref'] } }, at('g_w'))).toBe(true)          // a reference set inside it
    expect(touches({ type: 'group.changed', data: { ids: ['g_sv'] } }, at('g_w'))).toBe(false)          // a shot's home is not World's
    expect(touches({ type: 'asset.created', data: { id: 'a' } }, at('g_im'))).toBe(true)                 // the imports: a thing on no page
    expect(touches({ type: 'asset.created', data: { id: 'a' } }, at('g_w'))).toBe(false)                // it lands in a home by group.changed
    expect(touches({ type: 'story.changed', data: { kind: 'profile', id: 'prf_1' } }, at('g_c'))).toBe(true)   // Ines's hero moved: the badges
    expect(touches({ type: 'story.changed', data: { kind: 'shot', id: 'sht_9' } }, at('g_w'))).toBe(false)
    expect(touches({ type: 'asset.updated', data: { id: 'a' } }, at(TRASH))).toBe(true)
    expect(touches({ type: 'group.changed', data: { ids: [] } }, at(null, 'fog'))).toBe(true)          // a search reads again
  })
  it('applies a change or a removal in place', () => {
    const thing = (id: string, trashed: string | null = null) => ({ asset: { id, kind: 'image', tags: [], trashed_at: trashed }, roles: [], home_id: 'g_v', path: '' }) as unknown as BinThing
    useBin.setState({ open: 'g_v', items: [thing('a'), thing('b')], total: 2, selected: 'b' })
    useBin.getState().patch({ ...thing('a').asset, tags: ['fog'] })
    expect(useBin.getState().items[0].asset.tags).toEqual(['fog'])
    useBin.getState().patch({ ...thing('b').asset, trashed_at: '2026-10-29T12:00:00Z' })                  // trashed: it leaves the home
    expect(useBin.getState().items.map((x) => x.asset.id)).toEqual(['a'])
    expect([useBin.getState().total, useBin.getState().selected]).toEqual([1, null])
    useBin.getState().drop('a')
    expect(useBin.getState().items).toEqual([])
  })
})
