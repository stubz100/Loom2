// D68 (ArtCraft P6): the Catalogue's query bar (filters, the GET /assets parameters) and the album tree helpers.
import { describe, expect, it, vi } from 'vitest'
import type { MenuItem } from '../../frame/commands'
import { flatGroups, useAlbum, type AlbumNode } from './albumStore'
import { queryOf, type CatalogueState, type Query } from './catalogueStore'
import { addFilterMenu, CLEAR_ALL, FILTERS } from './filters'

const Q0: Query = { folder: 'all', state: 'all', rating_min: 0, tags_any: [], search: '', sort: 'created_desc', group: 'batch' }
const fake = (q: Partial<Query> = {}) => ({ q: { ...Q0, ...q }, setQuery: vi.fn(async () => undefined), tagCloud: [{ tag: 'harbour', count: 3 }] }) as unknown as CatalogueState & { setQuery: ReturnType<typeof vi.fn> }
const filter = (id: string) => FILTERS.find((f) => f.id === id)!

// one query that turns every filter on
const ALL_ON: Query = { ...Q0, state: 'keep', kind: 'video', suite: 'animate', model_id: 'some-model', rating_min: 3, date_preset: '7d', tags_any: ['a', 'b'],
  aspect: 'portrait', has_children: false, batch_id: 'bat_1', batch_label: '10:02', root_id: 'ast_r', root_label: 'root' }

describe('filters', () => {
  it('are all off on the default query', () => {
    expect(FILTERS.filter((f) => f.active(Q0)).map((f) => f.id)).toEqual([])
  })
  it("each filter's clear patch switches exactly that filter off", () => {
    for (const f of FILTERS) {
      expect(f.active(ALL_ON), f.id).toBe(true)
      const after = { ...ALL_ON, ...f.clear }
      expect(FILTERS.filter((g) => !g.active(after)).map((g) => g.id)).toEqual([f.id])
    }
  })
  it('CLEAR_ALL switches every filter off and empties the search', () => {
    const q = { ...ALL_ON, search: 'fog', ...CLEAR_ALL }
    expect(FILTERS.some((f) => f.active(q))).toBe(false)
    expect(q.search).toBe('')
  })
  it('name the active value on the chip', () => {
    expect(filter('state').chip({ ...Q0, state: 'none' })).toBe('State: unjudged')
    expect(filter('type').chip({ ...Q0, kind: 'video' })).toBe('Type: clips')
    expect(filter('type').chip({ ...Q0, has_document: true })).toBe('Type: documents')
    expect(filter('source').chip({ ...Q0, suite: 'extract' })).toBe('Source: Frame extract')
    expect(filter('rating').chip({ ...Q0, rating_min: 2 })).toBe('Rating ≥ ★★')
    expect(filter('date').chip({ ...Q0, date_preset: '30d' })).toBe('Date: last 30 days')
    expect(filter('date').chip({ ...Q0, created_from: '2026-10-01T00:00:00' })).toBe('Date: 2026-10-01 → …')
    expect(filter('derived').chip({ ...Q0, has_children: false })).toBe('No derivations')
    expect(filter('batch').chip({ ...Q0, batch_id: 'b', batch_label: '10:02' })).toBe('Batch · 10:02')
  })
  it('build the "+ Filter" menu: the common filters on top, the rarer ones with options under More', () => {
    const c = fake()
    const menu = addFilterMenu(c)
    const labels = menu.map((m) => ('label' in m ? m.label : 'sep' in m ? '—' : '?'))
    expect(labels).toEqual(['State', 'Type', 'Source', 'Model', 'Rating', 'Date', 'Tags', '—', 'More'])
    const more = menu[menu.length - 1] as { items: MenuItem[] }
    expect(more.items.map((m) => ('label' in m ? m.label : '?'))).toEqual(['Aspect', 'Derivations'])   // batch / lineage come from a tile's menu
  })
  it('apply their patch through setQuery and check the current value', () => {
    const c = fake({ state: 'reject' })
    const opts = filter('state').options(c) as { label: string; checked?: boolean; run: () => void }[]
    expect(opts.map((o) => [o.label, !!o.checked])).toEqual([['Kept', false], ['Rejected', true], ['Unjudged', false]])
    opts[0].run()
    expect(c.setQuery).toHaveBeenCalledWith({ state: 'keep' })
    const tags = filter('tags').options(fake({ tags_any: ['harbour'] })) as { label: string; checked?: boolean }[]
    expect(tags[0]).toMatchObject({ label: 'harbour  (3)', checked: true })
  })
})

describe('queryOf (GET /assets parameters)', () => {
  it('sends the four fixed fields and nothing unset', () => {
    expect(queryOf(Q0)).toEqual({ folder: 'all', state: 'all', sort: 'created_desc', group: 'batch' })
  })
  it('leaves out empty strings, an empty tag list and a zero rating, and trims the search', () => {
    const p = queryOf({ ...Q0, suite: '', model_id: '', search: '   ', tags_any: [], rating_min: 0 })
    expect(Object.keys(p).sort()).toEqual(['folder', 'group', 'sort', 'state'])
    expect(queryOf({ ...Q0, search: '  fog ' }).search).toBe('fog')
  })
  it('sends booleans when set, false included (D38 fix: "No derivations")', () => {
    expect(queryOf({ ...Q0, has_children: false })).toMatchObject({ has_children: false })
    expect(queryOf({ ...Q0, has_document: true })).toMatchObject({ has_document: true })
  })
  it('never sends the chip labels, and merges the extra parameters', () => {
    const p = queryOf({ ...ALL_ON }, { limit: 200, cursor: 'c1' })
    expect(p).not.toHaveProperty('batch_label')
    expect(p).not.toHaveProperty('root_label')
    expect(p).toMatchObject({ batch_id: 'bat_1', root_id: 'ast_r', tags_any: ['a', 'b'], rating_min: 3, limit: 200, cursor: 'c1' })
  })
})

describe('album tree', () => {
  const node = (id: string, name: string, children: AlbumNode[] = []) => ({ id, name, children }) as unknown as AlbumNode
  const TREE = node('album', 'Album', [node('g1', 'Harbour', [node('g11', 'Boats'), node('g12', 'Nets', [node('g121', 'Knots')])]), node('g2', 'Forest')])

  it('flatGroups lists every group below the root, depth first, with its depth', () => {
    expect(flatGroups(TREE).map(({ node: n, depth }) => `${depth}:${n.id}`)).toEqual(['0:g1', '1:g11', '1:g12', '2:g121', '0:g2'])
    expect(flatGroups(null)).toEqual([])
  })
  it('pathOf gives the trail from the root, find the node; both empty for unknown ids', () => {
    useAlbum.setState({ tree: TREE })
    const a = useAlbum.getState()
    expect(a.pathOf('g121')).toEqual([{ id: 'album', name: 'Album' }, { id: 'g1', name: 'Harbour' }, { id: 'g12', name: 'Nets' }, { id: 'g121', name: 'Knots' }])
    expect(a.pathOf('album')).toEqual([{ id: 'album', name: 'Album' }])
    expect(a.pathOf('nope')).toEqual([])
    expect(a.find('g2')?.name).toBe('Forest')
    expect(a.find('nope')).toBeNull()
    useAlbum.setState({ tree: null })
    expect(useAlbum.getState().pathOf('g1')).toEqual([])
  })
})
