// The Catalogue Stage as one or two panes (D34, proto01_design/01 §6c). Each pane renders a place — Unprocessed, Library, Trash
// as a grid, a group as an album page — from its own catalogue store; clicking a pane makes it the active one, which the strip,
// Places, the Inspector and the commands follow. Dragging between panes moves items (Ctrl duplicates).
import { BookOpen, Columns2, Inbox, Library, MoreHorizontal, Trash2, X } from 'lucide-react'
import { useEffect, useMemo, useRef, type ComponentType } from 'react'
import { showMenu } from '../../frame/ContextMenu'
import { assetIds, onlyAssets, registerDropTarget } from '../../frame/drag'
import { useAlbum } from './albumStore'
import { activeCatalogue, CatalogueStoreCtx, InPaneCtx, type CatalogueHook } from './catalogueContext'
import { openPlace, paneStore, swapPanes, useActivePaneStore, useSplit } from './split'

/** Wrap a frame part (Panel, Strip, Inspector) so it serves the active pane's store. */
export function withActivePane<P extends object>(C: ComponentType<P>): ComponentType<P> {
  return function ActivePane(props: P) {
    const store = useActivePaneStore()
    return <CatalogueStoreCtx.Provider value={store}><C {...props} /></CatalogueStoreCtx.Provider>
  }
}

function PaneHeader({ i, store }: { i: 0 | 1; store: CatalogueHook }) {
  const q = store((s) => s.q)
  const total = store((s) => s.total)
  const tree = useAlbum((s) => s.tree)
  const active = useSplit((s) => s.active === i)
  const path = useMemo(() => (q.group_id ? useAlbum.getState().pathOf(q.group_id) : []), [q.group_id, tree]) // eslint-disable-line react-hooks/exhaustive-deps
  const [Icon, label] = q.group_id ? [BookOpen, path.slice(-2).map((p) => p.name).join(' › ') || 'Album'] : q.folder === 'trash' ? [Trash2, 'Trash'] : q.folder === 'unprocessed' ? [Inbox, 'Unprocessed'] : [Library, 'Library']
  const close = () => { const sp = useSplit.getState(); if (i === 0) swapPanes(); sp.setMode('single') }
  return (
    <div className={`pane-head${active ? ' active' : ''}`}>
      <Icon size={13} /><span className="lbl">{label}</span>{total !== null && !q.group_id && <span className="n">{total}</span>}
      <span className="spacer" />
      <button className="quiet" aria-label="Pane menu" title="Pane menu" onClick={(e) => showMenu(e, [
        { label: 'Open Unprocessed here', icon: Inbox, run: () => openPlace(store.getState(), 'unprocessed') },
        { label: 'Open Library here', icon: Library, run: () => openPlace(store.getState(), 'library') },
        { sep: true },
        { label: 'Swap panes', icon: Columns2, run: swapPanes },
        { label: 'Close this pane', icon: X, run: close },
      ])}><MoreHorizontal size={14} /></button>
    </div>
  )
}

function Pane({ i, Stage, split }: { i: 0 | 1; Stage: ComponentType; split: boolean }) {
  const store = paneStore(i)
  const body = useRef<HTMLDivElement>(null)
  useEffect(() => {                                                // a grid pane takes drops: Unprocessed moves photos back there, Trash trashes them
    const el = body.current
    if (!el) return
    return registerDropTarget(el, {
      accept: (p) => { const q = store.getState().q; return onlyAssets(p) && !q.group_id && (q.folder === 'unprocessed' || q.folder === 'trash') },
      drop: (p) => { const st = store.getState(); if (st.q.folder === 'trash') void st.trash(assetIds(p)); else void useAlbum.getState().move(p.items, null) },
    })
  }, [store])
  const active = useSplit((s) => s.active === i)
  return (
    <CatalogueStoreCtx.Provider value={store}><InPaneCtx.Provider value>
      <section className={`pane${split && active ? ' active' : ''}`} onPointerDownCapture={() => { if (split) useSplit.getState().setActive(i) }}>
        {split && <PaneHeader i={i} store={store} />}
        <div className="pane-body" ref={body}><Stage /></div>
      </section>
    </InPaneCtx.Provider></CatalogueStoreCtx.Provider>
  )
}

export function Panes({ Stage }: { Stage: ComponentType }) {
  const mode = useSplit((s) => s.mode)
  const ratio = useSplit((s) => s.ratio)
  const active = useSplit((s) => s.active)
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => { activeCatalogue.current = paneStore(mode === 'single' ? 0 : active) }, [mode, active])
  useEffect(() => { if (mode !== 'single') { const st = paneStore(1).getState(); if (!st.items.length && !st.groups.length) void st.load() } }, [mode])
  if (mode === 'single') return <Pane i={0} Stage={Stage} split={false} />
  const side = mode === 'side'
  const onDivider = (e: React.PointerEvent) => {
    e.preventDefault()
    const r = box.current!.getBoundingClientRect()
    const move = (ev: PointerEvent) => useSplit.getState().setRatio(side ? (ev.clientX - r.left) / r.width : (ev.clientY - r.top) / r.height)
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up) }
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
  }
  return (
    <div ref={box} className={`panes ${side ? 'side' : 'stacked'}`}>
      <div className="pane-slot" style={{ flexBasis: `${ratio * 100}%` }}><Pane i={0} Stage={Stage} split /></div>
      <div className="pane-divider" role="separator" aria-label="Resize panes" onPointerDown={onDivider}><span /></div>
      <div className="pane-slot" style={{ flexBasis: `${(1 - ratio) * 100}%` }}><Pane i={1} Stage={Stage} split /></div>
    </div>
  )
}

