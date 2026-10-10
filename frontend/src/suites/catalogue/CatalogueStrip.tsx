// The Catalogue strip (D34, proto01_design/01 §6b, §7): fixed slots, the same with or without a selection —
// Place · Query (search, filter chips, + Filter, clear, count) · Sort · Selection · Compare tray · Import · Zoom.
import { ArrowLeft, ArrowLeftRight, BookOpen, ChevronDown, Columns2, FolderOpen, Inbox, Library, Plus, Rows2, Search, Square, TextCursorInput, Trash2, Upload, X, ZoomIn, ZoomOut } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../../api/client'
import { CommandButton } from '../../frame/CommandButton'
import { showMenu } from '../../frame/ContextMenu'
import { markUsed, runCommand } from '../../frame/commands'
import { isTauri, pickFiles, pickFolder } from '../../shell/tauri'
import { askText, useSession } from '../../store/session'
import { ALBUM_ID, useAlbum } from './albumStore'
import { useCat } from './catalogueContext'
import type { CatalogueState, Sort } from './catalogueStore'
import { addFilterMenu, CLEAR_ALL, FILTERS } from './filters'
import { openPlace, swapPanes, useSplit } from './split'

const SORTS: [Sort, string][] = [['created_desc', 'Newest'], ['created_asc', 'Oldest'], ['rating_desc', 'Rating'], ['model', 'Model'], ['size_desc', 'Size']]

/** Import ▸ Files… / Folder… / Paths…: the OS pickers inside the app, a typed path in a browser. Imports land in Unprocessed. */
export async function importInteractive(c: CatalogueState, how: 'files' | 'folder' | 'paths'): Promise<void> {
  let paths: string[] = []
  if (how === 'files' && isTauri()) paths = await pickFiles('Import images or clips')
  else if (how === 'folder' && isTauri()) { const p = await pickFolder('Import a folder'); if (p) paths = [p] }
  else {
    const t = await askText({ title: 'Import', text: 'Files or folders to copy into the project, separated by ";". ComfyUI and A1111 PNG metadata is read into the parameters.', placeholder: 'F:/refs/alley.png; F:/refs/moodboard' })
    paths = t ? t.split(/[;\n]/).map((x) => x.trim().replace(/^"|"$/g, '')).filter(Boolean) : []
  }
  if (!paths.length) return
  const toast = useSession.getState().toast
  try { const n = await c.importPaths(paths); toast(`Imported ${n} item${n === 1 ? '' : 's'} into Unprocessed`, 'success') }
  catch (e) { toast(`Import failed: ${(e as Error).message}`, 'error') }
}

/** Two-step (07 §1.5): the first click arms it for 4 s, the second purges every trashed asset. */
export function EmptyTrashButton() {
  const c = useCat()
  const [armed, setArmed] = useState(false)
  useEffect(() => { if (!armed) return; const t = setTimeout(() => setArmed(false), 4000); return () => clearTimeout(t) }, [armed])
  markUsed('cat.emptyTrash')
  const n = c.counts.trash ?? c.total ?? 0
  if (!n && !c.purging) return null
  const run = () => {
    if (!armed) { setArmed(true); return }
    setArmed(false)
    void c.emptyTrash().then((k) => useSession.getState().toast(`Trash emptied: ${k} item${k === 1 ? '' : 's'} deleted permanently`, 'success'))
      .catch((e) => useSession.getState().toast(`Empty trash failed: ${(e as Error).message}`, 'error'))
  }
  return (
    <button className={`danger small${armed ? ' armed' : ''}`} disabled={c.purging} onClick={run} title={armed ? 'Click again to delete permanently' : `Delete all ${n} trashed items permanently`}>
      {c.purging ? 'Emptying…' : armed ? `Click again: delete ${n}` : 'Empty trash'}
    </button>
  )
}

function PlaceSlot() {
  const c = useCat()
  const tree = useAlbum((s) => s.tree)                                  // a selector must not build a fresh array (re-renders forever)
  const path = useMemo(() => (c.q.group_id ? useAlbum.getState().pathOf(c.q.group_id) : []), [tree, c.q.group_id])
  if (c.q.group_id) return (
    <nav className="slot-place crumbs" aria-label="Place">
      <BookOpen size={14} className="ic" />
      {(path.length ? path : [{ id: ALBUM_ID, name: 'Album' }]).map((p, i, all) => i < all.length - 1
        ? <span key={p.id}><button className="crumb" onClick={() => openPlace(c, { group: p.id })}>{p.name}</button><span className="sep">›</span></span>
        : <b key={p.id} title={p.name}>{p.name}</b>)}
    </nav>
  )
  const [Icon, label] = c.q.folder === 'trash' ? [Trash2, 'Trash'] : c.q.folder === 'unprocessed' ? [Inbox, 'Unprocessed'] : [Library, 'Library']
  return <div className="slot-place"><Icon size={15} className="ic" /><b>{label}</b>{c.q.folder === 'trash' && <EmptyTrashButton />}</div>
}

function QuerySlot() {
  const c = useCat()
  const [text, setText] = useState(c.q.search)
  useEffect(() => setText(c.q.search), [c.q.search])
  useEffect(() => { if (text === c.q.search) return; const t = setTimeout(() => void c.setQuery({ search: text }), 250); return () => clearTimeout(t) }, [text]) // eslint-disable-line react-hooks/exhaustive-deps
  const chips = FILTERS.filter((f) => f.active(c.q))
  const any = chips.length > 0 || !!c.q.search
  return (
    <div className="slot-query">
      <label className="search">
        <Search size={14} />
        <input id="cat-search" type="text" value={text} placeholder="Search prompts, tags, seeds" onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === 'Escape') { setText(''); (e.target as HTMLInputElement).blur() } }} />
      </label>
      {chips.map((f) => (
        <span key={f.id} className="fchip">
          <button className="fchip-label" title={`change the ${f.label.toLowerCase()} filter`} onClick={(e) => { const opts = f.options(c); showMenu(e, [...opts, ...(opts.length ? [{ sep: true as const }] : []), { label: 'Remove filter', icon: X, run: () => void c.setQuery(f.clear) }]) }}>{f.chip(c.q)}</button>
          <button className="fchip-x" aria-label={`Remove filter ${f.chip(c.q)}`} onClick={() => void c.setQuery(f.clear)}><X size={12} /></button>
        </span>
      ))}
      <button className="fchip-add" onClick={(e) => showMenu(e, addFilterMenu(c))}><Plus size={12} />Filter</button>
      {any && <button className="quiet icon" title="Clear search and filters" aria-label="Clear search and filters" onClick={() => { setText(''); void c.setQuery(CLEAR_ALL) }}><X size={14} /></button>}
      <span className="count" style={c.error ? { color: 'var(--error)' } : undefined}>{c.error ?? `${c.total ?? '…'}${c.loading ? ' · loading' : ''}`}</span>
    </div>
  )
}

/** Split ▾: single, stacked (a page above Unprocessed) or side by side; swap the panes. */
function SplitButton() {
  const mode = useSplit((s) => s.mode)
  const Icon = mode === 'side' ? Columns2 : mode === 'stacked' ? Rows2 : Square
  const set = (m: 'single' | 'stacked' | 'side') => useSplit.getState().setMode(m)
  return (
    <button className="split-pick" title="Split the Stage: two places at once" aria-label="Split" onClick={(e) => showMenu(e, [
      { label: 'Single', icon: Square, checked: mode === 'single', run: () => set('single') },
      { label: 'Stacked', icon: Rows2, checked: mode === 'stacked', run: () => set('stacked') },
      { label: 'Side by side', icon: Columns2, checked: mode === 'side', run: () => set('side') },
      { sep: true },
      { label: 'Swap panes', icon: ArrowLeftRight, disabled: mode === 'single', run: swapPanes },
    ])}><Icon size={15} /><ChevronDown size={12} /></button>
  )
}

export function CatalogueStrip() {
  const c = useCat()
  const s = useSession()
  if (!s.project?.open) return <span>Catalogue</span>
  if (c.loupe || c.compareOpen || c.lineage) return (                           // R8: the loupe and compare bring their own bar
    <div className="cstrip"><button className="quiet" onClick={() => runCommand('cat.closeLoupe')}><ArrowLeft size={14} /> Back</button><PlaceSlot /></div>
  )
  const nSel = c.selected.length
  return (
    <div className="cstrip">
      <PlaceSlot />
      <QuerySlot />
      <span className="div" />
      <label className="slot-sort" title="Sort">
        <select value={c.q.sort} disabled={!!c.q.group_id} title={c.q.group_id ? 'a page keeps its own arrangement' : undefined} onChange={(e) => void c.setQuery({ sort: e.target.value as Sort })} aria-label="Sort">{SORTS.map(([k, l]) => <option key={k} value={k}>Sort: {l}</option>)}</select>
      </label>
      <span className="div" />
      <span className="slot-sel">
        {nSel > 0 && <span className="pill">{nSel} selected<button aria-label="Clear selection" title="Clear selection (Esc)" onClick={() => c.clearSelection()}><X size={12} /></button></span>}
      </span>
      <span className="slot-cmp">
        {c.compare.length > 0 && <span className="tray">
          {c.compare.slice(0, 4).map((id) => <img key={id} src={api.thumbUrl(id, 256)} alt="" />)}
          <button className="go" disabled={c.compare.length < 2} title={c.compare.length < 2 ? 'Pin one more to compare' : 'Open compare (Shift+C)'} onClick={() => runCommand('cat.compare')}>Compare</button>
          <button aria-label="Unpin all" title="Unpin all" onClick={() => c.clearCompare()}><X size={12} /></button>
        </span>}
      </span>
      <span className="div" />
      <SplitButton />
      <span className="split-btn">
        <button onClick={() => void importInteractive(c, isTauri() ? 'files' : 'paths')} title="Import images or clips into Unprocessed (or drop files on the grid)"><Upload size={14} />Import</button>
        <button className="caret" aria-label="Import options" onClick={(e) => showMenu(e, [
          { label: 'Files…', icon: Upload, run: () => void importInteractive(c, 'files'), disabled: !isTauri() },
          { label: 'Folder…', icon: FolderOpen, run: () => void importInteractive(c, 'folder'), disabled: !isTauri() },
          { label: 'Paths…', icon: TextCursorInput, run: () => void importInteractive(c, 'paths') },
        ])}><ChevronDown size={12} /></button>
      </span>
      <span className="div" />
      {c.q.group_id
        ? <span className="slot-zoom">
          <button className="quiet icon" aria-label="Zoom out" title="Zoom out (Ctrl+wheel on the page)" onClick={() => c.setPageZoom(c.pageZoom / 1.25)}><ZoomOut size={16} /></button>
          <input type="range" min={-2.3} max={1.38} step={0.01} value={Math.log(c.pageZoom)} onChange={(e) => c.setPageZoom(Math.exp(Number(e.target.value)))} title={`page zoom ${Math.round(c.pageZoom * 100)} %`} aria-label="Page zoom" />
          <button className="quiet icon" aria-label="Zoom in" title="Zoom in" onClick={() => c.setPageZoom(c.pageZoom * 1.25)}><ZoomIn size={16} /></button>
          <button className="fit" onClick={() => c.requestFit()} title="Fit the page's content">Fit</button>
        </span>
        : <span className="slot-zoom">
          <CommandButton id="cat.tileSmaller" />
          <input type="range" min={96} max={512} step={16} value={c.tile} onChange={(e) => c.setTile(Number(e.target.value))} title="tile size ([ / ])" aria-label="Tile size" />
          <CommandButton id="cat.tileLarger" />
        </span>}
    </div>
  )
}
