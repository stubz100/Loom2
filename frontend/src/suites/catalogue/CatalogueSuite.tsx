// Catalogue suite (08, redesigned by proto01_design/01 · D34): the Places panel (Unprocessed, Library, the Album's groups,
// Trash), the fixed-slot strip with filter chips, a virtualised grid with keyboard-by-row, loupe and compare on the stage, and
// the inspector. Generate shows its results with the same Stage and Inspector and, until its own pass, the older Strip below.
import { useVirtualizer } from '@tanstack/react-virtual'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../../api/client'
import type { Asset } from '../../api/types'
import type { SuiteDef } from '../../frame/suiteRegistry'
import { DEFAULT_RAIL } from '../../frame/railTabs'
import { listenFileDrop } from '../../shell/tauri'
import { useSession } from '../../store/session'
import { Compare, Loupe } from './Loupe'
import { Tile } from './Tile'
import { selectedOrPrimary, type GroupHeader, type GroupMode, type Sort } from './catalogueStore'
import { useActiveCatalogue, useCat } from './catalogueContext'
import { CommandButton, CommandRow } from '../../frame/CommandButton'
import { handleKeyFor, runCommand } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { gridMenu, headerMenu, tileMenu } from './catalogueCommands'
import { CatalogueStrip, EmptyTrashButton } from './CatalogueStrip'
import { CLEAR_ALL } from './filters'
import { Places } from './Places'
import { useAlbum } from './albumStore'
import { Inspector } from './Inspector'
import { LineageView } from './LineageView'
import { PageView } from './PageView'
import { Panes, withActivePane } from './Panes'
import { openPlace, paneStore, useSplit } from './split'
import './catalogue.css'

/** Group headers show the scene of a JSON prompt rather than the raw JSON. */
const excerptOf = (p: string) => { const m = /^\{\s*"scene"\s*:\s*"([^"]{1,80})/.exec(p); return m ? m[1] : p }

const GROUPS: [GroupMode, string][] = [['batch', 'Batch'], ['lineage', 'Lineage'], ['session', 'Session'], ['model', 'Model'], ['none', 'None']]
const SORTS: [Sort, string][] = [['created_desc', 'newest'], ['created_asc', 'oldest'], ['rating_desc', 'rating'], ['model', 'model'], ['size_desc', 'size']]

// ---------------------------------------------------------------- Panel
function Panel() {
  const c = useCat()
  const s = useSession()
  useEffect(() => {
    if (!s.project?.open) return
    const p = new URLSearchParams(location.search)
    const place = p.get('place')                                  // deep links for screenshots and checks: ?place=unprocessed|library|trash|<group id>
    const patch = place === 'library' ? { folder: 'all' as const, group_id: undefined } : place === 'trash' ? { folder: 'trash' as const, group_id: undefined }
      : place === 'unprocessed' ? { folder: 'unprocessed' as const, group_id: undefined } : place ? { folder: 'all' as const, group_id: place } : null
    const loaded = patch ? c.setQuery(patch) : c.load()
    const split = p.get('split'), place2 = p.get('place2')               // ?split=stacked|side&place2=unprocessed|library|trash|<group id>
    if (split === 'stacked' || split === 'side') useSplit.getState().setMode(split)
    if (place2) openPlace(paneStore(1).getState(), place2 === 'unprocessed' || place2 === 'library' || place2 === 'trash' ? place2 : { group: place2 })
    void loaded.then(() => {                                       // ?loupe=<id>  ?compare=a,b
      const l = p.get('loupe'); const cmp = p.get('compare'); const sel = p.get('select'); const lin = p.get('lineage')
      if (sel) c.select(sel, 'single')                         // ?select=<id> and ?lineage=<id>, for checks
      if (lin) c.openLineage(lin)
      else if (l) c.openLoupe(l)
      else if (cmp) { cmp.split(',').filter(Boolean).forEach((id) => c.togglePin(id)); c.setCompareOpen(true) }
    })
    void c.refreshMeta()
    void useAlbum.getState().load()
  }, [s.project?.path]) // eslint-disable-line react-hooks/exhaustive-deps
  return <Places />
}

// ---------------------------------------------------------------- Strip (Generate's results, until its pass: §9)
export function Strip() {
  const c = useCat()
  const s = useSession()
  const ids = selectedOrPrimary(c)
  const [tagText, setTagText] = useState('')
  if (!s.project?.open) return <span>Catalogue</span>
  const activeChips = [c.q.search && `"${c.q.search}"`, c.q.state !== 'all' && c.q.state, c.q.model_id, c.q.rating_min > 0 && `★≥${c.q.rating_min}`, ...c.q.tags_any.map((t) => `#${t}`), c.q.aspect, c.q.has_children !== undefined && (c.q.has_children ? 'has derivations' : 'no derivations'), (c.q.created_from || c.q.created_to) && `${c.q.created_from?.slice(0, 10) ?? '…'} → ${c.q.created_to?.slice(0, 10) ?? '…'}`].filter(Boolean) as string[]
  return (
    <>
      <span>group</span>
      <select value={c.q.group} onChange={(e) => c.setQuery({ group: e.target.value as GroupMode })}>{GROUPS.map(([g, l]) => <option key={g} value={g}>{l}</option>)}</select>
      {c.q.group !== 'none' && <CommandRow ids={['cat.expandAll', 'cat.collapseAll']} />}
      <div className="segmented">{(['all', 'keep', 'reject'] as const).map((st) => <button key={st} className={c.q.state === st ? 'active' : ''} onClick={() => c.setQuery({ state: st })}>{st}</button>)}</div>
      <span>sort</span>
      <select value={c.q.sort} onChange={(e) => c.setQuery({ sort: e.target.value as Sort })}>{SORTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
      {activeChips.length > 0 && <span className="chips">{activeChips.map((x) => <span key={x} className="chip-f">{x}</span>)}</span>}
      <span style={{ color: c.error ? 'var(--error)' : 'var(--fg3)' }}>{c.error ?? `${c.total ?? '…'} assets${c.loading ? ' · loading' : ''}`}</span>
      <span className="spacer" />
      {ids.length > 0 && (
        <>
          <span>▣ {ids.length}</span>
          <CommandRow ids={['cat.keep', 'cat.reject', 'cat.unstate', 'gap', 'cat.loupe', 'cat.edit', 'cat.reference', 'cat.pin', 'gap', 'cat.selectAll', 'cat.clearSelection']} />
          <input id="strip-tag" type="text" value={tagText} placeholder="tag…" style={{ width: 90, minHeight: 24 }} onChange={(e) => setTagText(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && tagText.trim()) { const t = tagText.trim(); void Promise.all(ids.map((id) => { const a = c.byId(id); return a && !a.tags.includes(t) ? c.setTags([id], [...a.tags, t]) : Promise.resolve() })); setTagText('') } }} />
          {c.q.folder === 'trash' ? <><CommandRow ids={['cat.restore', 'cat.purge']} /><EmptyTrashButton /></> : <CommandButton id="cat.trash" />}
        </>
      )}
      {c.compare.length >= 2 && <button className="quiet" onClick={() => runCommand('cat.compare')} style={{ color: 'var(--accent)' }} title="Open compare (Shift+C)">Compare {c.compare.length}</button>}
      {c.compare.length > 0 && <CommandButton id="cat.unpinAll" />}
      <CommandButton id="cat.tileSmaller" />
      <input type="range" min={96} max={512} step={16} value={c.tile} onChange={(e) => c.setTile(Number(e.target.value))} title="tile size ([ / ])" style={{ width: 110 }} />
      <CommandButton id="cat.tileLarger" />
    </>
  )
}

// ---------------------------------------------------------------- Stage
function EmptyGrid() {
  const c = useCat()
  const filtered = !!c.q.search || Object.entries(CLEAR_ALL).some(([k, v]) => k !== 'search' && JSON.stringify((c.q as unknown as Record<string, unknown>)[k] ?? v) !== JSON.stringify(v))
  const [title, text] = filtered ? ['Nothing matches these filters', ''] : c.q.folder === 'unprocessed' ? ['Nothing to sort', 'New generations, edits, clips and imports land here. Import files with the Import button or drop them here.']
    : c.q.folder === 'trash' ? ['Trash is empty', ''] : c.q.group_id ? ['This page is empty', 'Drag photos onto this group in the Places panel, or use "Move to group" on a tile.'] : ['No assets yet', 'Import files, or generate your first image.']
  return <div className="cat-empty"><div><h2>{title}</h2>{text && <p>{text}</p>}{filtered && <button onClick={() => void c.setQuery(CLEAR_ALL)}>Clear filters</button>}</div></div>
}

type Row = { kind: 'header'; g: GroupHeader } | { kind: 'tiles'; items: Asset[] } | { kind: 'note'; text: string; key: string }

export function Stage() {
  const c = useCat()
  const s = useSession()
  const scrollRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(1000)
  useActiveCatalogue()
  const compareOpen = c.compareOpen
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const ro = new ResizeObserver(() => setWidth(el.clientWidth))
    ro.observe(el)
    setWidth(el.clientWidth)
    return () => ro.disconnect()
  }, [c.loupe, compareOpen])
  const fill = useSession((st) => st.ui.thumbFit === 'fill')
  const caption = useSession((st) => st.ui.caption)
  const [fileOver, setFileOver] = useState(false)
  useEffect(() => listenFileDrop({                                 // OS files dropped on the grid are imported (into Unprocessed)
    over: (inside) => setFileOver(inside),
    drop: (paths) => {
      setFileOver(false)
      void c.importPaths(paths).then((n) => s.toast(`Imported ${n} item${n === 1 ? '' : 's'} into Unprocessed`, 'success')).catch((e) => s.toast(`Import failed: ${(e as Error).message}`, 'error'))
    },
    within: () => scrollRef.current,
  }), [c]) // eslint-disable-line react-hooks/exhaustive-deps
  const gap = 8
  const cols = Math.max(1, Math.floor((width - 16) / (c.tile + gap)))
  const cellH = Math.round(c.tile * 0.72) + (caption === 'off' ? 0 : 22)
  const rows = useMemo<Row[]>(() => {
    const out: Row[] = []
    const chunk = (items: Asset[]) => { for (let i = 0; i < items.length; i += cols) out.push({ kind: 'tiles', items: items.slice(i, i + cols) }) }
    if (c.q.group === 'none') chunk(c.items)
    else for (const g of c.groups) {
      out.push({ kind: 'header', g })
      if (c.expanded[g.key]) { const items = c.groupItems[g.key]; if (items) chunk(items); else out.push({ kind: 'note', text: c.groupErrors[g.key] ? `failed: ${c.groupErrors[g.key]}` : 'loading…', key: g.key }) }
    }
    return out
  }, [c.items, c.groups, c.groupItems, c.groupErrors, c.expanded, c.q.group, cols])
  const rowKey = useCallback((i: number) => { const r = rows[i]; return r.kind === 'header' ? `h:${r.g.key}` : r.kind === 'tiles' ? `t:${r.items[0]?.id}:${r.items.length}` : `n:${i}` }, [rows])
  const headerIdx = useMemo(() => rows.map((r, i) => (r.kind === 'header' ? i : -1)).filter((i) => i >= 0), [rows])
  const activeSticky = useRef(-1)
  const virt = useVirtualizer({ count: rows.length, getScrollElement: () => scrollRef.current, getItemKey: rowKey,
    estimateSize: (i) => (rows[i].kind === 'tiles' ? cellH + gap : rows[i].kind === 'header' ? 36 : 28), overscan: 6,
    rangeExtractor: (range) => {
      const active = [...headerIdx].reverse().find((i) => i <= range.startIndex) ?? -1
      activeSticky.current = active
      const out = new Set<number>()
      if (active >= 0) out.add(active)
      for (let i = Math.max(0, range.startIndex - range.overscan); i <= Math.min(range.count - 1, range.endIndex + range.overscan); i++) out.add(i)
      return [...out].sort((a, b) => a - b)
    } })
  const vitems = virt.getVirtualItems()
  useEffect(() => {
    if (c.q.group === 'none' && c.nextCursor && vitems.length && vitems[vitems.length - 1].index >= rows.length - 3) void c.loadMore()
    // expanded groups load as their placeholder rows come into view (bounded by the store's in-flight limit)
    for (const v of vitems) { const r = rows[v.index]; if (r?.kind === 'note' && !c.groupErrors[r.key]) void c.loadGroup(r.key) }
  }, [vitems, rows, c.nextCursor, c.q.group]) // eslint-disable-line react-hooks/exhaustive-deps

  const rowOf = useCallback((id: string) => rows.findIndex((r) => r.kind === 'tiles' && r.items.some((a) => a.id === id)), [rows])
  const focusId = useCallback((id: string, mode: 'single' | 'range') => {
    c.select(id, mode)
    const ri = rowOf(id)
    if (ri >= 0) virt.scrollToIndex(ri, { align: 'auto' })
  }, [c, rowOf, virt])

  const onKey = (e: React.KeyboardEvent) => {
    if ((e.target as HTMLElement)?.closest('input, textarea, select')) return
    if (c.loupe || compareOpen) return
    const order = c.visibleOrder()
    const ids = selectedOrPrimary(c)
    const i = c.primary ? order.indexOf(c.primary) : -1
    const move = (j: number) => { if (j >= 0 && j < order.length) focusId(order[j], e.shiftKey ? 'range' : 'single') }
    const k = e.key
    if (k === 'ArrowRight') { e.preventDefault(); move(i < 0 ? 0 : i + 1) }
    else if (k === 'ArrowLeft') { e.preventDefault(); move(i < 0 ? 0 : i - 1) }
    else if (k === 'ArrowDown') { e.preventDefault(); move(i < 0 ? 0 : Math.min(order.length - 1, i + cols)) }
    else if (k === 'ArrowUp') { e.preventDefault(); move(i < 0 ? 0 : Math.max(0, i - cols)) }
    else if (k === 'Home') { e.preventDefault(); move(0) }
    else if (k === 'End') { e.preventDefault(); move(order.length - 1) }
    else handleKeyFor('catalogue', e.nativeEvent)        // every other key is an accelerator for a registry command (07 §3c)
    void ids
  }
  const onTileContext = (e: React.MouseEvent, id: string) => {
    if (!c.selected.includes(id)) c.select(id, 'single')
    showMenu(e, tileMenu())
  }

  const onTileClick = (e: React.MouseEvent, id: string) => c.select(id, e.ctrlKey || e.metaKey ? 'toggle' : e.shiftKey ? 'range' : 'single')
  if (!s.project?.open) return <div className="placeholder"><div><h2>Catalogue</h2>open or create a project to begin</div></div>
  if (c.lineage) return <LineageView id={c.lineage} />
  if (c.q.group_id && !c.loupe && !c.compareOpen) return <PageView gid={c.q.group_id} onOpenGroup={(id) => openPlace(c, { group: id })} />
  const loupeAsset = c.loupe ? c.byId(c.loupe) : undefined
  if (loupeAsset) return <Loupe asset={loupeAsset} />
  if (compareOpen && c.compare.length >= 2) {
    const assets = c.compare.map((id) => c.byId(id)).filter(Boolean) as Asset[]
    if (assets.length >= 2) return <Compare assets={assets} />
  }
  const empty = !c.loading && rows.length === 0
  return (
    <div className="cat-grid" ref={scrollRef} tabIndex={0} onKeyDown={onKey} onContextMenu={(e) => { if ((e.target as HTMLElement).closest('.tile, .cat-header')) return; showMenu(e, gridMenu()) }}>
      {empty && <EmptyGrid />}
      {fileOver && <div className="file-over">Drop to import into Unprocessed</div>}
      <div className="cat-rows" style={{ height: virt.getTotalSize() }}>
        {vitems.map((v) => {
          const r = rows[v.index]
          const sticky = r.kind === 'header' && v.index === activeSticky.current
          const st = sticky ? { position: 'sticky' as const, top: 0, zIndex: 2 } : { transform: `translateY(${v.start}px)` }
          if (r.kind === 'header') return (
            <div key={v.key} className={`cat-header${sticky ? ' sticky' : ''}`} style={st} data-index={v.index} ref={sticky ? undefined : virt.measureElement} onClick={() => c.toggleGroup(r.g.key)} onContextMenu={(e) => showMenu(e, headerMenu(r.g.key))}>
              <span>{c.expanded[r.g.key] ? '▾' : '▸'}</span>
              {r.g.cover_id && <img className="cover" src={api.thumbUrl(r.g.cover_id, 256)} alt="" loading="lazy" />}
              <b>{r.g.label}</b>{r.g.model_id && <span>· {r.g.model_id}</span>}<span className="excerpt">{r.g.prompt_excerpt ? `· "${excerptOf(r.g.prompt_excerpt)}"` : ''}</span>
              <span>{r.g.count} · {new Date(r.g.last_created).toLocaleString()}</span>
            </div>
          )
          if (r.kind === 'note') return <div key={v.key} className="cat-header" style={st} data-index={v.index} ref={virt.measureElement}><span className="excerpt">{r.text}</span>{c.groupErrors[r.key] && <button className="quiet" onClick={(e) => { e.stopPropagation(); c.retryGroup(r.key) }}>retry</button>}</div>
          return (
            <div key={v.key} className="cat-row" data-index={v.index} ref={virt.measureElement} style={{ ...st, gridTemplateColumns: `repeat(${cols}, ${c.tile}px)`, gridAutoRows: `${cellH}px`, height: cellH + gap, paddingBottom: gap }}>
              {r.items.map((a) => <Tile key={a.id} a={a} size={c.tile} fill={fill} caption={caption} selected={c.selected.includes(a.id)} primary={c.primary === a.id} pinned={c.compare.indexOf(a.id) + 1} onClick={onTileClick} onDouble={(id) => c.openLoupe(id)} onLineage={(id) => c.openLineage(id)} onContext={onTileContext} dragIds={() => selectedOrPrimary(c)} />)}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- Inspector (Inspector.tsx)
export { Inspector }

export const CatalogueSuite: SuiteDef = {
  id: 'catalogue', rail: DEFAULT_RAIL.catalogue, wideStrip: true,
  Panel: withActivePane(Panel), Strip: withActivePane(CatalogueStrip), Stage: () => <Panes Stage={Stage} />, Inspector: withActivePane(Inspector),
}
