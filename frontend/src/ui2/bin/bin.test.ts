// U8 (D157, proto01_UI2 05 §2): the Bin's pure parts — a home's path by its names, every home (and its role pages) by id, the kind chips,
// and where a home's thing belongs (World's version, the Look, a shot, a cut; nothing for the imports).
import { describe, expect, it } from 'vitest'
import type { BinNode, BinThing } from '../../api/types'
import { belongs, moveTargets } from './binCommands'
import { homesById, passes, pathLabel } from './binStore'

const node = (id: string, path: string, name: string, children: BinNode[] = [], pages: string[] = []): BinNode => ({ id, path, name, count: 0, total: 0, pages, children })
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
