// U8 (D157, proto01_UI2 05 §2): the Bin's pure parts — a home's path by its names, every home (and its role pages) by id, the kind chips,
// and where a home's thing belongs (World's version, the Look, a shot, a cut; nothing for the imports).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { BinNode, BinThing } from '../../api/types'
import { belongs, moveTargets } from './binCommands'
import { kindVerb } from './binMenus'
import { homesById, passes, pathLabel, selectedThings, shownItems, subtreeIds, touches, TRASH, useBin } from './binStore'

const node = (id: string, path: string, name: string, children: BinNode[] = [], pages: string[] = []): BinNode => ({ id, path, name, count: 0, total: 0, pages, children, gone: false, page: false, kinds: [] })
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

describe("the Bin's kinds (C6, D181)", () => {
  const thing = (path: string, shelf: string) => ({ asset: { id: 'a', kind: 'image' }, roles: [], home_id: 'g', path, shelf }) as unknown as BinThing
  it("gives a kind its own verb where the thing belongs, none for a free picture or a working file", () => {
    expect(kindVerb(thing('shots/sht_9/v1', 'passes'))?.label).toBe('Render the passes again ▸')
    expect(kindVerb(thing('shots/sht_9/v1', 'takes'))?.label).toBe('Re-take ▸')
    expect(kindVerb(thing('shots/sht_9/v1', 'final'))?.label).toBe('The composition ▸')
    expect(kindVerb(thing('shots/sht_9/v1', 'animatic'))?.label).toBe('Record again ▸')
    expect(kindVerb(thing('world/place/prf_1/v1', 'set'))?.label).toBe('The set builder ▸')
    expect(kindVerb(thing('world/character/prf_1/v1', 'body'))?.label).toBe('The body ▸')
    expect(kindVerb(thing('world/prop/prf_1/v1', 'model'))?.label).toBe('The model ▸')
    expect(kindVerb(thing('world/sketches', 'pictures'))).toBeNull()
    expect(kindVerb(thing('world/place/prf_1/v1', 'working'))).toBeNull()
    expect(kindVerb(thing('imports', 'set'))).toBeNull()                                          // a set thing on no version has no builder to open
  })
})

describe('the Bin in a search (review K69, K70, K95)', () => {
  const thing = (id: string, kind: string) => ({ asset: { id, kind, tags: [], trashed_at: null }, roles: [], home_id: 'g', path: 'world/look', shelf: 'pictures' }) as unknown as BinThing
  const found = [thing('p1', 'image'), thing('c1', 'video'), thing('p2', 'image'), thing('s1', 'audio'), thing('p3', 'image')]
  const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } })
  let results = found                                                                // what GET /bin/search answers
  beforeEach(() => {
    results = found
    vi.stubGlobal('fetch', vi.fn(async () => json({ items: results })))   // the client takes `fetch` when the backend is set
    setBackend({ host: '127.0.0.1', port: 8766, token: 't' } as never)
    useBin.setState({ open: null, query: 'fog', filter: 'pictures', items: found, selection: [], selected: null, viewing: false })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('K70: Select all, a range and the verbs take only the things the kind chip shows', () => {
    expect(shownItems(useBin.getState()).map((x) => x.asset.id)).toEqual(['p1', 'p2', 'p3'])
    useBin.getState().selectAll()
    expect(useBin.getState().selection).toEqual(['p1', 'p2', 'p3'])                      // the clip and the sound stay out (Ctrl+A, Delete)
    useBin.getState().select('p1'); useBin.getState().select('p3', 'range')
    expect(useBin.getState().selection).toEqual(['p1', 'p2', 'p3'])
    useBin.setState({ selection: ['p1', 'c1'], selected: 'p1' })
    expect(selectedThings().map((x) => x.asset.id)).toEqual(['p1'])
  })
  it('K70: a chip that hides selected things takes them out of the selection', () => {
    useBin.setState({ filter: 'all', selection: ['p1', 'c1'], selected: 'c1', viewing: true })
    useBin.getState().setFilter('pictures')
    expect(useBin.getState()).toMatchObject({ selection: ['p1'], selected: 'p1', viewing: true })
  })
  it('K69: a search read again keeps the selection and the large view of what is still found', async () => {
    useBin.setState({ filter: 'all', selection: ['p2', 's1'], selected: 's1', viewing: true })
    await useBin.getState().search('fog')
    expect(useBin.getState()).toMatchObject({ selection: ['p2', 's1'], selected: 's1', viewing: true })
    results = [thing('p2', 'image')]
    await useBin.getState().search('fog')
    expect(useBin.getState()).toMatchObject({ selection: ['p2'], selected: 'p2', viewing: true })
    results = []
    await useBin.getState().search('fog')
    expect(useBin.getState()).toMatchObject({ selection: [], selected: null, viewing: false })   // nothing to view: the next click selects, it opens nothing
  })
  it('K95: a right-click inside a selection makes that thing the primary and keeps the selection', () => {
    useBin.setState({ filter: 'all', selection: ['p1', 'p2', 'p3'], selected: 'p1' })
    useBin.getState().select('p3', 'primary')
    expect(useBin.getState()).toMatchObject({ selection: ['p1', 'p2', 'p3'], selected: 'p3' })
    useBin.getState().select('c1', 'primary')                                          // outside the selection: it alone
    expect(useBin.getState()).toMatchObject({ selection: ['c1'], selected: 'c1' })
  })
})
