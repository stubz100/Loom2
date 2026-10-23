// D68 (ArtCraft P6): the Catalogue's query bar (filters, the GET /assets parameters) and the album tree helpers.
import { describe, expect, it, vi } from 'vitest'
import type { MenuItem } from '../../frame/commands'
import { flatGroups, useAlbum, type AlbumNode } from './albumStore'
import { queryOf, type CatalogueState, type Query } from './catalogueStore'
import { addFilterMenu, CLEAR_ALL, FILTERS } from './filters'

const Q0: Query = { folder: 'all', tags_any: [], search: '', sort: 'created_desc', group: 'batch' }
const fake = (q: Partial<Query> = {}) => ({ q: { ...Q0, ...q }, setQuery: vi.fn(async () => undefined), tagCloud: [{ tag: 'harbour', count: 3 }] }) as unknown as CatalogueState & { setQuery: ReturnType<typeof vi.fn> }
const filter = (id: string) => FILTERS.find((f) => f.id === id)!

// one query that turns every filter on
const ALL_ON: Query = { ...Q0, kind: 'video', suite: 'animate', model_id: 'some-model', date_preset: '7d', tags_any: ['a', 'b'],
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
    expect(filter('type').chip({ ...Q0, kind: 'video' })).toBe('Type: clips')
    expect(filter('type').chip({ ...Q0, has_document: true })).toBe('Type: documents')
    expect(filter('source').chip({ ...Q0, suite: 'extract' })).toBe('Source: Frame extract')
    expect(filter('date').chip({ ...Q0, date_preset: '30d' })).toBe('Date: last 30 days')
    expect(filter('date').chip({ ...Q0, created_from: '2026-10-01T00:00:00' })).toBe('Date: 2026-10-01 → …')
    expect(filter('derived').chip({ ...Q0, has_children: false })).toBe('No derivations')
    expect(filter('batch').chip({ ...Q0, batch_id: 'b', batch_label: '10:02' })).toBe('Batch · 10:02')
  })
  it('build the "+ Filter" menu: the common filters on top, the rarer ones with options under More', () => {
    const c = fake()
    const menu = addFilterMenu(c)
    const labels = menu.map((m) => ('label' in m ? m.label : 'sep' in m ? '—' : '?'))
    expect(labels).toEqual(['Type', 'Source', 'Model', 'Date', 'Tags', '—', 'More'])                          // D122: no State, no Rating
    expect(FILTERS.some((f) => f.id === 'state' || f.id === 'rating')).toBe(false)
    const more = menu[menu.length - 1] as { items: MenuItem[] }
    expect(more.items.map((m) => ('label' in m ? m.label : '?'))).toEqual(['Aspect', 'Derivations'])   // batch / lineage come from a tile's menu
  })
  it('apply their patch through setQuery and check the current value', () => {
    const c = fake({ kind: 'video' })
    const opts = filter('type').options(c) as { label: string; checked?: boolean; run: () => void }[]
    expect(opts.map((o) => [o.label, !!o.checked])).toEqual([['Images', false], ['Clips', true], ['Audio', false], ['Has a document', false]])
    opts[0].run()
    expect(c.setQuery).toHaveBeenCalledWith({ kind: 'image', has_document: undefined })
    const tags = filter('tags').options(fake({ tags_any: ['harbour'] })) as { label: string; checked?: boolean }[]
    expect(tags[0]).toMatchObject({ label: 'harbour  (3)', checked: true })
  })
})

describe('queryOf (GET /assets parameters)', () => {
  it('sends the four fixed fields and nothing unset', () => {
    expect(queryOf(Q0)).toEqual({ folder: 'all', sort: 'created_desc', group: 'batch' })
  })
  it('leaves out empty strings and an empty tag list, and trims the search', () => {
    const p = queryOf({ ...Q0, suite: '', model_id: '', search: '   ', tags_any: [] })
    expect(Object.keys(p).sort()).toEqual(['folder', 'group', 'sort'])
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
    expect(p).toMatchObject({ batch_id: 'bat_1', root_id: 'ast_r', tags_any: ['a', 'b'], limit: 200, cursor: 'c1' })
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

// D90 (B17): one predicate for "Back to Unprocessed" — every selected asset placed in a group
describe('allPlaced', () => {
  it('is true on a group page, false in Unprocessed and the Trash, elsewhere what /groups/where said', async () => {
    const { allPlaced, clearPlacements, notePlacements } = await import('./placement')
    clearPlacements()
    expect(allPlaced([], { folder: 'all', group_id: 'g1' })).toBe(false)
    expect(allPlaced(['a'], { folder: 'all', group_id: 'g1' })).toBe(true)
    expect(allPlaced(['a'], { folder: 'unprocessed' })).toBe(false)
    expect(allPlaced(['a'], { folder: 'trash' })).toBe(false)
    expect(allPlaced(['a'], { folder: 'all' })).toBe(false)                         // unknown: not placed
    notePlacements({ a: { group_id: 'g1' }, b: null, c: { group_id: 'album' } })
    expect(allPlaced(['a', 'c'], { folder: 'all' })).toBe(true)                     // the Album page counts as placed
    expect(allPlaced(['a', 'b'], { folder: 'all' })).toBe(false)
  })
  it('forgets every placement when the album tree changes (a move, a group made or removed)', async () => {
    const { allPlaced, notePlacements } = await import('./placement')
    notePlacements({ a: { group_id: 'g1' } })
    expect(allPlaced(['a'], { folder: 'all' })).toBe(true)
    useAlbum.setState({ tree: { id: 'album', name: 'Album', children: [] } as unknown as AlbumNode })
    expect(allPlaced(['a'], { folder: 'all' })).toBe(false)
    useAlbum.setState({ tree: null })
  })
})

// D90 (B10): the loupe and compare show clips and spoken lines as media, not as a broken <img>
describe('loupeMedia', () => {
  it('plays a clip in a video (an Animate clip names its clip), a line in an audio, and zooms only images', async () => {
    const { loupeMedia } = await import('./media')
    const v = loupeMedia({ id: 'ast_v', kind: 'video', params: { clip_id: 'clip_1' } })
    expect(v).toMatchObject({ kind: 'video', clipId: 'clip_1', zoom: false })
    expect(v.src).toContain('/assets/ast_v/file')
    expect(loupeMedia({ id: 'ast_w', kind: 'video', params: {} })).toMatchObject({ kind: 'video', clipId: null })
    const a = loupeMedia({ id: 'ast_a', kind: 'audio', params: {} })
    expect(a).toMatchObject({ kind: 'audio', zoom: false })
    expect((a as { poster: string }).poster).toContain('/thumbs/ast_a/')
    expect(loupeMedia({ id: 'ast_i', kind: 'image', params: {} })).toMatchObject({ kind: 'image', zoom: true })
    expect(loupeMedia({ id: 'ast_m', kind: 'mesh', params: {} }).src).toContain('/thumbs/ast_m/1024')
  })
})

// D90 (B13): the Inspector's place links from Generate switch to the Catalogue and open the place in its active pane
describe('openPlaceFrom', () => {
  it("opens in the Catalogue's active pane from Generate's results, and in place from a pane", async () => {
    const [{ openPlaceFrom, useSplit }, st, { useSession }] = await Promise.all([import('./split'), import('./catalogueStore'), import('../../store/session')])
    const spy = (h: typeof st.useCatalogue) => { const f = vi.fn(async () => undefined); h.setState({ setQuery: f }); return f }
    const p0 = spy(st.useCatalogue), p1 = spy(st.useCataloguePane2), gen = spy(st.useGenerateResults)
    useSession.setState({ ui: { ...useSession.getState().ui, suite: 'generate' } })
    useSplit.setState({ mode: 'side', active: 1 })
    openPlaceFrom(st.useGenerateResults, { group: 'g7' })
    expect(useSession.getState().ui.suite).toBe('catalogue')
    expect(p1).toHaveBeenCalledWith(expect.objectContaining({ group_id: 'g7' }))
    expect(gen).not.toHaveBeenCalled()
    expect(p0).not.toHaveBeenCalled()
    openPlaceFrom(st.useCatalogue, 'unprocessed')
    expect(p0).toHaveBeenCalledWith(expect.objectContaining({ folder: 'unprocessed' }))
    useSplit.setState({ mode: 'single', active: 0 })
  })
})
