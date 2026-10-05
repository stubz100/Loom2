// Catalogue suite (08): Library/Filters/Collections/Import panel, strip with group/state/sort/bulk/zoom, a
// virtualised grid with keyboard-by-row, loupe and compare on the stage, and an Info/Params/Lineage/Tags inspector.
import { useVirtualizer } from '@tanstack/react-virtual'
import { FolderOpen, Upload } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../../api/client'
import type { Asset } from '../../api/types'
import { setRailTab, type SuiteDef } from '../../frame/suiteRegistry'
import { DEFAULT_RAIL } from '../../frame/railTabs'
import { isTauri, pickFiles, pickFolder, revealPath } from '../../shell/tauri'
import { useSession } from '../../store/session'
import { Compare, Loupe } from './Loupe'
import { Tile } from './Tile'
import { selectedOrPrimary, type Folder, type GroupHeader, type GroupMode, type Sort } from './catalogueStore'
import { useCat } from './catalogueContext'
import './catalogue.css'

/** Group headers show the scene of a JSON prompt rather than the raw JSON. */
const excerptOf = (p: string) => { const m = /^\{\s*"scene"\s*:\s*"([^"]{1,80})/.exec(p); return m ? m[1] : p }

const FOLDERS: [Folder, string][] = [['all', 'All'], ['today', 'Today'], ['last_session', 'Last session'], ['images', 'Images'], ['clips', 'Clips'], ['documents', 'Documents'], ['imported', 'Imported'], ['rejected', 'Rejected'], ['trash', 'Trash']]
const GROUPS: [GroupMode, string][] = [['batch', 'Batch'], ['lineage', 'Lineage'], ['session', 'Session'], ['model', 'Model'], ['none', 'None']]
const SORTS: [Sort, string][] = [['created_desc', 'newest'], ['created_asc', 'oldest'], ['rating_desc', 'rating'], ['model', 'model'], ['size_desc', 'size']]

// ---------------------------------------------------------------- Panel
function Panel({ tab }: { tab: string }) {
  const c = useCat()
  const s = useSession()
  useEffect(() => {
    if (!s.project?.open) return
    const p = new URLSearchParams(location.search)
    const g = p.get('group')
    const tab = p.get('tab')
    if (tab && ['library', 'filters', 'collections', 'import'].includes(tab)) setRailTab('catalogue', tab)
    const loaded = g && ['none', 'batch', 'lineage', 'session', 'model'].includes(g) && g !== c.q.group ? c.setQuery({ group: g as GroupMode }) : c.load()
    void loaded.then(() => {                      // deep links for screenshots and sharing: ?loupe=<id>  ?compare=a,b
      const l = p.get('loupe'); const cmp = p.get('compare')
      if (l) c.openLoupe(l)
      else if (cmp) { cmp.split(',').filter(Boolean).forEach((id) => c.togglePin(id)); c.setCompareOpen(true) }
      if (p.get('expand') === 'all') c.expandAll(true)
    })
    void c.refreshMeta()
  }, [s.project?.path]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!s.project?.open) return <span style={{ color: 'var(--fg3)' }}>Open or create a project.</span>
  if (tab === 'filters') return <Filters />
  if (tab === 'collections') return <Collections />
  if (tab === 'import') return <ImportPanel />
  return (
    <div className="lib-tree">
      {FOLDERS.map(([f, label]) => (
        <button key={f} className={c.q.folder === f && !c.q.collection_id ? 'active' : ''} onClick={() => c.setQuery({ folder: f, collection_id: undefined })}>
          <span>{label}</span><span className="n">{c.counts[f] ?? ''}</span>
        </button>
      ))}
      <h4>Collections</h4>
      {c.collections.map((col) => (
        <button key={col.id} className={c.q.collection_id === col.id ? 'active' : ''} onClick={() => c.setQuery({ collection_id: col.id, folder: 'all' })} title={col.kind === 'manual' ? 'drop assets here to add them' : 'smart collection'}
          onDragOver={(e) => { if (col.kind === 'manual') { e.preventDefault(); e.currentTarget.style.borderColor = 'var(--accent)' } }}
          onDragLeave={(e) => { e.currentTarget.style.borderColor = '' }}
          onDrop={(e) => { e.preventDefault(); e.currentTarget.style.borderColor = ''; const ids = (e.dataTransfer.getData('text/loom2-assets') || '').split(',').filter(Boolean); if (ids.length && col.kind === 'manual') void c.addToCollection(col.id, ids) }}>
          <span>{col.kind === 'smart' ? '◈ ' : ''}{col.name}</span><span className="n">{col.count}</span>
        </button>
      ))}
      <button onClick={() => { const name = window.prompt('Collection name'); if (name) void c.createCollection(name) }}><span>+ new collection</span><span /></button>
    </div>
  )
}

export function Filters() {
  const c = useCat()
  const caps = useSession((s) => s.capabilities)
  const q = c.q
  const models = Object.keys(caps?.models ?? {})
  const toggleTag = (t: string) => c.setQuery({ tags_any: q.tags_any.includes(t) ? q.tags_any.filter((x) => x !== t) : [...q.tags_any, t] })
  return (
    <div className="form" style={{ gridTemplateColumns: '84px 1fr' }}>
      <label>Search</label><input id="cat-search" type="text" value={q.search} placeholder="prompt, tags, seed…" onChange={(e) => c.setQuery({ search: e.target.value })} />
      <label>State</label>
      <div className="segmented">{(['all', 'none', 'keep', 'reject'] as const).map((st) => <button key={st} className={q.state === st ? 'active' : ''} onClick={() => c.setQuery({ state: st })}>{st}</button>)}</div>
      <label>Suite</label>
      <select value={q.suite ?? ''} onChange={(e) => c.setQuery({ suite: e.target.value || undefined })}><option value="">any</option>{['generate', 'inpaint', 'refine', 'animate', 'extract', 'import'].map((x) => <option key={x}>{x}</option>)}</select>
      <label>Model</label>
      <select value={q.model_id ?? ''} onChange={(e) => c.setQuery({ model_id: e.target.value || undefined })}><option value="">any</option>{models.map((m) => <option key={m}>{m}</option>)}</select>
      <label>Rating ≥</label>
      <select value={q.rating_min} onChange={(e) => c.setQuery({ rating_min: Number(e.target.value) })}>{[0, 1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n ? '★'.repeat(n) : 'any'}</option>)}</select>
      <label>Aspect</label>
      <select value={q.aspect ?? ''} onChange={(e) => c.setQuery({ aspect: (e.target.value || undefined) as never })}><option value="">any</option><option value="landscape">landscape</option><option value="portrait">portrait</option><option value="square">square</option></select>
      <label>Children</label>
      <select value={q.has_children === undefined ? '' : String(q.has_children)} onChange={(e) => c.setQuery({ has_children: e.target.value === '' ? undefined : e.target.value === 'true' })}><option value="">any</option><option value="true">has derivations</option><option value="false">none</option></select>
      <label>Created</label>
      <div style={{ display: 'flex', gap: 4 }}>
        <input type="date" value={q.created_from?.slice(0, 10) ?? ''} onChange={(e) => c.setQuery({ created_from: e.target.value ? `${e.target.value}T00:00:00` : undefined })} />
        <input type="date" value={q.created_to?.slice(0, 10) ?? ''} onChange={(e) => c.setQuery({ created_to: e.target.value ? `${e.target.value}T23:59:59` : undefined })} />
      </div>
      <label>Tags</label>
      <div className="chips">{c.tagCloud.slice(0, 24).map((t) => <span key={t.tag} className="chip-f" style={q.tags_any.includes(t.tag) ? { borderColor: 'var(--accent)', color: 'var(--fg)' } : undefined} onClick={() => toggleTag(t.tag)}>{t.tag} <small>{t.count}</small></span>)}{!c.tagCloud.length && <span style={{ color: 'var(--fg3)' }}>no tags yet</span>}</div>
      <label />
      <div style={{ display: 'flex', gap: 6 }}>
        <button onClick={() => c.setQuery({ state: 'all', suite: undefined, model_id: undefined, rating_min: 0, tags_any: [], aspect: undefined, has_children: undefined, search: '', created_from: undefined, created_to: undefined })}>Clear filters</button>
        <button onClick={() => { const name = window.prompt('Smart collection name'); if (name) void c.createCollection(name, 'smart', { folder: q.folder, state: q.state, suite: q.suite, model_id: q.model_id, rating_min: q.rating_min, tags_any: q.tags_any, aspect: q.aspect, has_children: q.has_children, search: q.search || undefined }) }}>Save as smart collection</button>
      </div>
    </div>
  )
}

function Collections() {
  const c = useCat()
  const [confirm, setConfirm] = useState<string | null>(null)
  return (
    <div className="lib-tree">
      {c.collections.map((col) => (
        <div key={col.id} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <button style={{ flex: 1 }} className={c.q.collection_id === col.id ? 'active' : ''} onClick={() => c.setQuery({ collection_id: col.id, folder: 'all' })}><span>{col.kind === 'smart' ? '◈ ' : ''}{col.name}</span><span className="n">{col.count}</span></button>
          <button className="quiet" title="rename" onClick={() => { const n = window.prompt('Rename', col.name); if (n) void c.renameCollection(col.id, n) }}>✎</button>
          {col.kind === 'smart' && <button className="quiet" title="convert to manual (freeze members)" onClick={() => void c.convertCollection(col.id)}>◈→▣</button>}
          <button className="quiet" title={confirm === col.id ? 'click again to delete' : 'delete'} style={confirm === col.id ? { color: 'var(--error)' } : undefined}
            onClick={() => { if (confirm === col.id) { void c.deleteCollection(col.id); setConfirm(null) } else { setConfirm(col.id); setTimeout(() => setConfirm((x) => (x === col.id ? null : x)), 2000) } }}>✕</button>
        </div>
      ))}
      {!c.collections.length && <span style={{ color: 'var(--fg3)' }}>No collections. Select assets and use "Add to collection", or save filters as a smart collection.</span>}
    </div>
  )
}

function ImportPanel() {
  const c = useCat()
  const toast = useSession((s) => s.toast)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [over, setOver] = useState(false)
  const run = async () => {
    const paths = text.split('\n').map((x) => x.trim()).filter(Boolean)
    if (!paths.length) return
    setBusy(true)
    try { const n = await c.importPaths(paths); toast(`Imported ${n} asset${n === 1 ? '' : 's'}`, 'success'); setText('') }
    catch (e) { toast(`Import failed: ${(e as Error).message}`, 'error') }
    finally { setBusy(false) }
  }
  return (
    <div>
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={5} style={{ width: '100%' }} placeholder={'One path per line: files or folders\nF:/refs/alley.png'} />
      <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
        {isTauri() && <button onClick={() => void pickFiles('Import images or clips').then((p) => p.length && setText((t) => [t, ...p].filter(Boolean).join('\n')))}><Upload size={14} /> Files…</button>}
        {isTauri() && <button onClick={() => void pickFolder('Import a folder').then((p) => p && setText((t) => [t, p].filter(Boolean).join('\n')))}><FolderOpen size={14} /> Folder…</button>}
        <button className="primary" disabled={busy || !text.trim()} onClick={() => void run()}>Import</button>
      </div>
      <div className={`drop${over ? ' over' : ''}`} onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); const names = [...e.dataTransfer.files].map((f) => (f as File & { path?: string }).path).filter(Boolean) as string[]; if (names.length) setText((t) => [t, ...names].filter(Boolean).join('\n')); else toast('Drop needs the shell for file paths; use Files… instead', 'info') }}>
        Drop files or folders here
      </div>
      <p style={{ color: 'var(--fg3)', fontSize: 12 }}>Imports copy into the project with a sidecar manifest; ComfyUI and A1111 PNG metadata is parsed into Params.</p>
    </div>
  )
}

// ---------------------------------------------------------------- Strip
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
      {c.q.group !== 'none' && <><button className="quiet" onClick={() => c.expandAll(true)} title="expand all">▾</button><button className="quiet" onClick={() => c.expandAll(false)} title="collapse all">▸</button></>}
      <div className="segmented">{(['all', 'keep', 'reject'] as const).map((st) => <button key={st} className={c.q.state === st ? 'active' : ''} onClick={() => c.setQuery({ state: st })}>{st}</button>)}</div>
      <span>sort</span>
      <select value={c.q.sort} onChange={(e) => c.setQuery({ sort: e.target.value as Sort })}>{SORTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
      {activeChips.length > 0 && <span className="chips">{activeChips.map((x) => <span key={x} className="chip-f">{x}</span>)}</span>}
      <span style={{ color: c.error ? 'var(--error)' : 'var(--fg3)' }}>{c.error ?? `${c.total ?? '…'} assets${c.loading ? ' · loading' : ''}`}</span>
      <span className="spacer" />
      {ids.length > 0 && (
        <>
          <span>▣ {ids.length}</span>
          <button className="quiet" onClick={() => void c.setState(ids, 'keep')} title="Keep (K)">✓</button>
          <button className="quiet" onClick={() => void c.setState(ids, 'reject')} title="Reject (X)">✗</button>
          <button className="quiet" onClick={() => void c.setState(ids, 'none')} title="Clear state (U)">○</button>
          <input type="text" value={tagText} placeholder="tag…" style={{ width: 90, minHeight: 24 }} onChange={(e) => setTagText(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && tagText.trim()) { const t = tagText.trim(); void Promise.all(ids.map((id) => { const a = c.byId(id); return a && !a.tags.includes(t) ? c.setTags([id], [...a.tags, t]) : Promise.resolve() })); setTagText('') } }} />
          <select value="" onChange={(e) => { if (e.target.value) void c.addToCollection(e.target.value, ids) }} title="Add to collection"><option value="">+ collection</option>{c.collections.filter((x) => x.kind === 'manual').map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select>
          {c.q.folder === 'trash' ? <><button className="quiet" onClick={() => void c.restore(ids)}>Restore</button><button className="quiet" onClick={() => { if (window.confirm(`Permanently delete ${ids.length}?`)) void c.purge(ids) }}>Purge</button></> : <button className="quiet" onClick={() => void c.trash(ids)} title="Trash (Del ×2)">🗑</button>}
        </>
      )}
      {c.compare.length >= 2 && <button className="quiet" onClick={() => c.setCompareOpen(!c.compareOpen)} style={{ color: 'var(--accent)' }} title="open compare (Shift+C)">Compare {c.compare.length}</button>}
      <input type="range" min={96} max={512} step={16} value={c.tile} onChange={(e) => c.setTile(Number(e.target.value))} title="tile size ([ / ])" style={{ width: 110 }} />
      <button className="quiet" onClick={() => c.setFill(!c.fill)} title="fit / fill">{c.fill ? 'fill' : 'fit'}</button>
    </>
  )
}

// ---------------------------------------------------------------- Stage
type Row = { kind: 'header'; g: GroupHeader } | { kind: 'tiles'; items: Asset[] } | { kind: 'note'; text: string; key: string }

export function Stage() {
  const c = useCat()
  const s = useSession()
  const scrollRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(1000)
  const [pendingDel, setPendingDel] = useState(0)
  const compareOpen = c.compareOpen
  const setCompareOpen = c.setCompareOpen
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const ro = new ResizeObserver(() => setWidth(el.clientWidth))
    ro.observe(el)
    setWidth(el.clientWidth)
    return () => ro.disconnect()
  }, [c.loupe, compareOpen])
  const gap = 8
  const cols = Math.max(1, Math.floor((width - 16) / (c.tile + gap)))
  const cellH = Math.round(c.tile * 0.72) + 22
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
    else if (k === 'a' && e.ctrlKey) { e.preventDefault(); c.selectAll() }
    else if (k === 'Enter' && c.primary) { e.preventDefault(); c.openLoupe(c.primary) }
    else if (k === 'Escape') { c.clearSelection() }
    else if (k === 'k' || k === 'K') void c.setState(ids, 'keep')
    else if (k === 'x' || k === 'X') void c.setState(ids, 'reject')
    else if (k === 'u' || k === 'U') void c.setState(ids, 'none')
    else if (/^[0-5]$/.test(k) && !e.ctrlKey) void c.setRating(ids, Number(k))
    else if (k === 'c' && c.primary) c.togglePin(c.primary)
    else if (k === 'C' && c.compare.length >= 2) setCompareOpen(true)
    else if (k === 'Delete' || k === 'Backspace') {
      if (!ids.length) return
      if (pendingDel && Date.now() - pendingDel < 1500) { setPendingDel(0); void c.trash(ids) } else { setPendingDel(Date.now()); s.toast('Press Delete again to move to Trash', 'info') }
    }
    else if (k === 'g' || k === 'G') { const gi = GROUPS.findIndex(([g]) => g === c.q.group); c.setQuery({ group: GROUPS[(gi + 1) % GROUPS.length][0] }) }
    else if (k === '[') c.setTile(c.tile - 32)
    else if (k === ']') c.setTile(c.tile + 32)
    else if (k === 'f' || k === 'F') { e.preventDefault(); setRailTab('catalogue', 'filters'); setTimeout(() => document.getElementById('cat-search')?.focus(), 50) }
    else if (k === 't' || k === 'T') { e.preventDefault(); document.getElementById('insp-tag')?.focus() }
    else if (k === 'e' || k === 'E') s.toast('Send to Edit arrives in M4', 'info')
    else if (k === 'r' && e.ctrlKey && c.primary) { e.preventDefault(); const a = c.byId(c.primary); if (a) void import('../generate/generateStore').then((m) => m.useGenerate.getState().rerun(a)) }
    else if ((k === 'r' || k === 'R') && !e.ctrlKey) { ids.forEach((id) => void import('../generate/generateStore').then((m) => m.useGenerate.getState().addRef(id))) }
    else if (k === 'v' || k === 'V') { const a = c.primary ? c.byId(c.primary) : undefined; if (a) void import('../generate/generateStore').then((m) => m.useGenerate.getState().variations(a)) }
    else if (k === 'A' && e.shiftKey) s.toast('Send to Animate arrives in M6', 'info')
    else return
  }

  const onTileClick = (e: React.MouseEvent, id: string) => c.select(id, e.ctrlKey || e.metaKey ? 'toggle' : e.shiftKey ? 'range' : 'single')
  if (!s.project?.open) return <div className="placeholder"><div><h2>Catalogue</h2>open or create a project to begin</div></div>
  const loupeAsset = c.loupe ? c.byId(c.loupe) : undefined
  if (loupeAsset) return <Loupe asset={loupeAsset} />
  if (compareOpen && c.compare.length >= 2) {
    const assets = c.compare.map((id) => c.byId(id)).filter(Boolean) as Asset[]
    if (assets.length >= 2) return <Compare assets={assets} />
  }
  const empty = !c.loading && rows.length === 0
  return (
    <div className="cat-grid" ref={scrollRef} tabIndex={0} onKeyDown={onKey}>
      {empty && <div className="cat-empty"><div><h2>{c.counts.all ? 'Nothing matches these filters' : 'No assets yet'}</h2>{c.counts.all ? <button onClick={() => c.setQuery({ state: 'all', search: '', tags_any: [], model_id: undefined, rating_min: 0, aspect: undefined, has_children: undefined, folder: 'all', collection_id: undefined })}>Clear filters</button> : 'Import files from the panel, or generate your first image.'}</div></div>}
      <div className="cat-rows" style={{ height: virt.getTotalSize() }}>
        {vitems.map((v) => {
          const r = rows[v.index]
          const sticky = r.kind === 'header' && v.index === activeSticky.current
          const st = sticky ? { position: 'sticky' as const, top: 0, zIndex: 2 } : { transform: `translateY(${v.start}px)` }
          if (r.kind === 'header') return (
            <div key={v.key} className={`cat-header${sticky ? ' sticky' : ''}`} style={st} data-index={v.index} ref={sticky ? undefined : virt.measureElement} onClick={() => c.toggleGroup(r.g.key)}>
              <span>{c.expanded[r.g.key] ? '▾' : '▸'}</span>
              {r.g.cover_id && <img className="cover" src={api.thumbUrl(r.g.cover_id, 256)} alt="" loading="lazy" />}
              <b>{r.g.label}</b>{r.g.model_id && <span>· {r.g.model_id}</span>}<span className="excerpt">{r.g.prompt_excerpt ? `· "${excerptOf(r.g.prompt_excerpt)}"` : ''}</span>
              <span>{r.g.count} · {new Date(r.g.last_created).toLocaleString()}</span>
            </div>
          )
          if (r.kind === 'note') return <div key={v.key} className="cat-header" style={st} data-index={v.index} ref={virt.measureElement}><span className="excerpt">{r.text}</span>{c.groupErrors[r.key] && <button className="quiet" onClick={(e) => { e.stopPropagation(); c.retryGroup(r.key) }}>retry</button>}</div>
          return (
            <div key={v.key} className="cat-row" data-index={v.index} ref={virt.measureElement} style={{ ...st, gridTemplateColumns: `repeat(${cols}, ${c.tile}px)`, gridAutoRows: `${cellH}px`, height: cellH + gap, paddingBottom: gap }}>
              {r.items.map((a) => <Tile key={a.id} a={a} size={c.tile} fill={c.fill} selected={c.selected.includes(a.id)} primary={c.primary === a.id} pinned={c.compare.indexOf(a.id) + 1} onClick={onTileClick} onDouble={(id) => c.openLoupe(id)} dragIds={() => selectedOrPrimary(c)} />)}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- Inspector
export function Inspector() {
  const c = useCat()
  const s = useSession()
  const [tab, setTab] = useState<'info' | 'params' | 'lineage' | 'tags'>('info')
  const [remote, setRemote] = useState<Asset | null>(null)
  const id = c.primary
  const local = id ? c.byId(id) : undefined
  useEffect(() => {
    if (id && !local) void api.get<Asset>(`/assets/${id}`).then(setRemote).catch(() => setRemote(null)); else setRemote(null)
  }, [id, local])
  const a = local ?? (remote?.id === id ? remote : null)
  if (!s.project?.open) return <span style={{ color: 'var(--fg3)' }}>No project.</span>
  if (!a) return <span style={{ color: 'var(--fg3)' }}>{c.selected.length > 1 ? `${c.selected.length} selected` : 'Select an asset.'}</span>
  const ids = selectedOrPrimary(c)
  const bulk = ids.length > 1
  return (
    <div>
      <div className="tabs2">{(['info', 'params', 'lineage', 'tags'] as const).map((t) => <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>{t}</button>)}</div>
      {tab === 'info' && (
        <div>
          <img className="insp-thumb" src={api.thumbUrl(a.id, 512)} alt="" />
          <dl className="kv">
            <dt>id</dt><dd className="mono">{a.id}{bulk ? ` (+${ids.length - 1})` : ''}</dd>
            <dt>kind</dt><dd>{a.kind} · {a.suite}</dd>
            <dt>size</dt><dd>{a.w}×{a.h}{a.frames ? ` · ${a.frames} f` : ''} · {a.bytes ? `${(a.bytes / 1024).toFixed(0)} KB` : ''}</dd>
            <dt>created</dt><dd>{new Date(a.created_at).toLocaleString()}</dd>
            <dt>model</dt><dd>{a.model_id ?? '—'}{a.variant ? ` · ${a.variant}` : ''}</dd>
            <dt>seed</dt><dd className="mono">{a.seed ?? '—'}</dd>
            {Object.entries(a.params).filter(([k]) => ['steps', 'guidance', 'cfg', 'turbo', 'width', 'height'].includes(k)).map(([k, v]) => <><dt key={k}>{k}</dt><dd key={k + 'v'}>{String(v)}</dd></>)}
            {a.timings?.wall_s !== undefined && <><dt>time</dt><dd>{String(a.timings.wall_s)} s</dd></>}
            {a.trashed_at && <><dt>trashed</dt><dd style={{ color: 'var(--error)' }}>{new Date(a.trashed_at).toLocaleString()}</dd></>}
          </dl>
          <div style={{ display: 'flex', gap: 6, marginTop: 10, alignItems: 'center' }}>
            <div className="segmented">
              <button className={a.state === 'keep' ? 'active' : ''} onClick={() => void c.setState(ids, 'keep')}>✓ keep</button>
              <button className={a.state === 'reject' ? 'active' : ''} onClick={() => void c.setState(ids, 'reject')}>✗ reject</button>
              <button className={a.state === 'none' ? 'active' : ''} onClick={() => void c.setState(ids, 'none')}>○</button>
            </div>
            <span className="stars-edit">{[1, 2, 3, 4, 5].map((n) => <button key={n} className={a.rating >= n ? 'on' : ''} onClick={() => void c.setRating(ids, a.rating === n ? 0 : n)}>★</button>)}</span>
          </div>
          <div className="chips" style={{ marginTop: 8 }}>{a.tags.map((t) => <span key={t} className="chip-f">{t}<button onClick={() => void c.setTags([a.id], a.tags.filter((x) => x !== t))}>✕</button></span>)}</div>
          <div className="verbs">
            <button onClick={() => s.toast('Send to Edit arrives in M4', 'info')}>Send to Edit <kbd>E</kbd></button>
            <button onClick={() => s.toast('Send to Animate arrives in M6', 'info')}>Animate start <kbd>⇧A</kbd></button>
            <button onClick={() => void import('../generate/generateStore').then((m) => m.useGenerate.getState().addRef(a.id))}>Reference <kbd>R</kbd></button>
            <button onClick={() => void import('../generate/generateStore').then((m) => m.useGenerate.getState().rerun(a))} disabled={!a.params?.recipe}>Re-run <kbd>⌃R</kbd></button>
            <button onClick={() => void import('../generate/generateStore').then((m) => m.useGenerate.getState().variations(a))} disabled={!a.params?.recipe}>Variations <kbd>V</kbd></button>
            <button onClick={() => c.togglePin(a.id)}>{c.compare.includes(a.id) ? 'Unpin' : 'Compare'} <kbd>C</kbd></button>
            <button onClick={() => c.openLoupe(a.id)}>Loupe <kbd>↵</kbd></button>
            <button onClick={() => void revealPath(a.path)}>Reveal</button>
            {a.trashed_at ? <button onClick={() => void c.restore(ids)}>Restore</button> : <button onClick={() => void c.trash(ids)}>Trash <kbd>Del</kbd></button>}
          </div>
        </div>
      )}
      {tab === 'params' && (
        <div>
          <h4 style={{ margin: '0 0 6px', color: 'var(--fg3)', fontSize: 11 }}>PROMPT</h4>
          <pre className="json">{a.prompt_json ? JSON.stringify(a.prompt_json, null, 2) : (a.prompt_text || '—')}</pre>
          {a.prompt_json && a.prompt_text && <pre className="json" style={{ marginTop: 6 }}>{a.prompt_text}</pre>}
          <h4 style={{ margin: '10px 0 6px', color: 'var(--fg3)', fontSize: 11 }}>PARAMETERS</h4>
          <dl className="kv">{Object.entries(a.params).map(([k, v]) => <><dt key={k}>{k}</dt><dd key={k + 'v'} className="mono">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</dd></>)}
            {a.compiled_graph_hash && <><dt>graph</dt><dd className="mono">{a.compiled_graph_hash}</dd></>}
            {a.job_id && <><dt>job</dt><dd className="mono">{a.job_id}</dd></>}
            {a.session_id && <><dt>session</dt><dd className="mono">{a.session_id}</dd></>}
          </dl>
          <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
            <button onClick={() => { void navigator.clipboard?.writeText(a.prompt_json ? JSON.stringify(a.prompt_json, null, 2) : a.prompt_text ?? ''); s.toast('Prompt copied', 'success') }}>Copy prompt</button>
            <button disabled={!a.params?.recipe} onClick={() => void import('../generate/generateStore').then((m) => { m.useGenerate.getState().loadFromAsset(a, false); s.setSuite('generate') })}>Load into Panel</button>
            <button disabled={!a.params?.recipe} onClick={() => void import('../generate/generateStore').then((m) => m.useGenerate.getState().rerun(a))}>All → Re-run</button>
          </div>
        </div>
      )}
      {tab === 'lineage' && <LineageTab a={a} />}
      {tab === 'tags' && <TagsTab a={a} ids={ids} />}
    </div>
  )
}

function LineageTab({ a }: { a: Asset }) {
  const c = useCat()
  const [lin, setLin] = useState<{ parents: { from_id: string; kind: string }[]; children: { to_id: string; kind: string }[] } | null>(null)
  useEffect(() => { void api.get<typeof lin>(`/lineage/${a.id}`).then(setLin).catch(() => setLin(null)) }, [a.id])
  const go = (id: string) => { c.select(id, 'single') }
  return (
    <div className="lin-list">
      <h4 style={{ margin: '0 0 6px', color: 'var(--fg3)', fontSize: 11 }}>PARENTS</h4>
      {lin?.parents.map((p) => <button key={p.from_id} onClick={() => go(p.from_id)}><img src={api.thumbUrl(p.from_id, 256)} alt="" /><span className="mono">{p.from_id}</span><span style={{ color: 'var(--fg3)' }}>{p.kind}</span></button>) ?? '…'}
      {lin && !lin.parents.length && <span style={{ color: 'var(--fg3)' }}>none (root)</span>}
      <h4 style={{ margin: '10px 0 6px', color: 'var(--fg3)', fontSize: 11 }}>CHILDREN</h4>
      {lin?.children.map((p) => <button key={p.to_id} onClick={() => go(p.to_id)}><img src={api.thumbUrl(p.to_id, 256)} alt="" /><span className="mono">{p.to_id}</span><span style={{ color: 'var(--fg3)' }}>{p.kind}</span></button>)}
      {lin && !lin.children.length && <span style={{ color: 'var(--fg3)' }}>none</span>}
      <div style={{ marginTop: 10 }}><button onClick={() => c.setQuery({ group: 'lineage', root_id: a.root_id ?? a.id, folder: 'all', collection_id: undefined })}>Show as tree</button> {c.q.root_id && <button onClick={() => c.setQuery({ root_id: undefined })}>All roots</button>}</div>
    </div>
  )
}

function TagsTab({ a, ids }: { a: Asset; ids: string[] }) {
  const c = useCat()
  const [text, setText] = useState('')
  const add = (t: string) => {
    t = t.trim()
    if (!t) return
    void Promise.all(ids.map((id) => { const x = c.byId(id) ?? (id === a.id ? a : undefined); return x && !x.tags.includes(t) ? c.setTags([id], [...x.tags, t]) : Promise.resolve() }))
    setText('')
  }
  return (
    <div>
      <input id="insp-tag" type="text" list="tag-suggest" value={text} placeholder={ids.length > 1 ? `add tag to ${ids.length} assets` : 'add tag'} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') add(text) }} style={{ width: '100%' }} />
      <datalist id="tag-suggest">{c.tagCloud.map((t) => <option key={t.tag} value={t.tag} />)}</datalist>
      <div className="chips" style={{ marginTop: 8 }}>{a.tags.map((t) => <span key={t} className="chip-f">{t}<button onClick={() => void c.setTags([a.id], a.tags.filter((x) => x !== t))}>✕</button></span>)}</div>
      <h4 style={{ margin: '12px 0 6px', color: 'var(--fg3)', fontSize: 11 }}>RECENT TAGS</h4>
      <div className="chips">{c.tagCloud.slice(0, 20).map((t) => <span key={t.tag} className="chip-f" style={{ cursor: 'pointer' }} onClick={() => add(t.tag)}>{t.tag} <small>{t.count}</small></span>)}</div>
    </div>
  )
}

export const CatalogueSuite: SuiteDef = {
  id: 'catalogue', rail: DEFAULT_RAIL.catalogue,
  Panel, Strip, Stage, Inspector,
  primary: { label: 'Import files…', run: () => setRailTab('catalogue', 'import') },
}
