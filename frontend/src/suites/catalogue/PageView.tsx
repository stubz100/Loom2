// An album page (D34, proto01_design/01 §6c): a group opened in a pane — an endless canvas where photos and group cards sit at
// free positions, sizes and stacking. Drag moves (beyond the page's edge the items are carried to another target: a pane, a
// Places row, a tab); the corner handle resizes; a marquee on empty space selects; wheel pans, Ctrl+wheel zooms at the cursor,
// middle-drag or Space+drag pans. Ctrl+G groups the selection, Ctrl+Shift+G dissolves a card, Del sends photos back to
// Unprocessed, arrows nudge, Ctrl+Z / Ctrl+Shift+Z undo layout. Filters highlight matches; nothing is hidden or moved.
import { ArrowDownToLine, ArrowUpToLine, BookOpen, Columns2, Copy, Expand, FolderPlus, Layers, Pencil, Redo, Undo, Ungroup, X } from 'lucide-react'
import { useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { Asset } from '../../api/types'
import { showMenu } from '../../frame/ContextMenu'
import { handleKeyFor, sep, type MenuItem } from '../../frame/commands'
import { carry, registerDropTarget, type DragItem, type DragPayload } from '../../frame/drag'
import { askConfirm, askText, useSession } from '../../store/session'
import { useAlbum, type PathStep } from './albumStore'
import { tileMenu } from './catalogueCommands'
import { CatalogueStoreCtx, useCat } from './catalogueContext'
import { FILTERS } from './filters'
import { openInOtherPane, openPlace } from './split'

export const CARD_RATIO = 0.8                                       // groups.py CARD_RATIO: a card is drawn in w × 0.8w
interface Item { kind: 'asset' | 'group'; id: string; x: number; y: number; w: number; z: number }
interface Summary { id: string; name: string; assets: number; groups: number; total: number; cover_ids: string[]; revision: number }
interface Page { group: { id: string; name: string; cover_id: string | null; revision: number; items: Item[] }; path: PathStep[]; assets: Record<string, Asset>; groups: Record<string, Summary> }
interface View { x: number; y: number }
type Pos = { x: number; y: number; w: number; z: number }

const views = new Map<string, View & { z: number }>()               // pan / zoom per page for this session
const key = (it: { kind: string; id: string }) => `${it.kind}:${it.id}`

export function PageView({ gid, onOpenGroup }: { gid: string; onOpenGroup?: (id: string) => void }) {
  const c = useCat()
  const store = useContext(CatalogueStoreCtx)
  const toast = useSession((s) => s.toast)
  const host = useRef<HTMLDivElement>(null)
  const [page, setPage] = useState<Page | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [live, setLive] = useState<Record<string, Pos> | null>(null)     // positions while dragging / resizing
  const [view, setView] = useState<View>({ x: 0, y: 0 })
  const [marquee, setMarquee] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(null)
  const [dropOver, setDropOver] = useState(false)
  const undo = useRef<{ before: Item[]; after: Item[] }[]>([])
  const redo = useRef<{ before: Item[]; after: Item[] }[]>([])
  const space = useRef(false)
  const z = c.pageZoom

  // ---- data ------------------------------------------------------------------------------------------
  const load = useCallback(async () => {
    try { setPage(await api.get<Page>(`/groups/${gid}`)); setError(null) }
    catch (e) { setError(e instanceof ApiError && e.status === 404 ? 'This group no longer exists.' : (e as Error).message) }
  }, [gid])
  useEffect(() => { setPage(null); undo.current = []; redo.current = []; void load() }, [load])
  useEffect(() => {
    const onGroups = (e: Event) => { const ids = (e as CustomEvent<{ ids?: string[] }>).detail?.ids ?? []; if (ids.includes(gid) || ids.some((i) => page?.groups[i])) void load() }
    const onAsset = (e: Event) => {
      const f = (e as CustomEvent<{ type: string; data: Asset }>).detail
      if (f.type === 'asset.updated') setPage((p) => (p && p.assets[f.data.id] ? { ...p, assets: { ...p.assets, [f.data.id]: f.data } } : p))
      else if (f.type === 'asset.deleted' && page?.assets[f.data.id]) void load()
    }
    window.addEventListener('loom2:group-changed', onGroups); window.addEventListener('loom2:asset-event', onAsset)
    return () => { window.removeEventListener('loom2:group-changed', onGroups); window.removeEventListener('loom2:asset-event', onAsset) }
  }, [gid, load, page])

  // ---- geometry --------------------------------------------------------------------------------------
  const items = page?.group.items ?? []
  const heightOf = useCallback((it: { kind: string; id: string; w: number }) => {
    if (it.kind === 'group') return it.w * CARD_RATIO
    const a = page?.assets[it.id]
    return a?.w && a?.h ? it.w * (a.h / a.w) : it.w * 0.75
  }, [page])
  const pos = (it: Item): Pos => live?.[key(it)] ?? it
  const toPage = (cx: number, cy: number) => { const r = host.current!.getBoundingClientRect(); return { x: (cx - r.left - view.x) / z, y: (cy - r.top - view.y) / z } }
  const fit = useCallback(() => {
    const el = host.current
    if (!el || !items.length) { setView({ x: 40, y: 40 }); c.setPageZoom(1); return }
    const x0 = Math.min(...items.map((i) => i.x)), y0 = Math.min(...items.map((i) => i.y))
    const x1 = Math.max(...items.map((i) => i.x + i.w)), y1 = Math.max(...items.map((i) => i.y + heightOf(i)))
    const s = Math.max(0.1, Math.min(1, (el.clientWidth - 64) / (x1 - x0 || 1), (el.clientHeight - 64) / (y1 - y0 || 1)))
    c.setPageZoom(s)
    setView({ x: (el.clientWidth - (x1 - x0) * s) / 2 - x0 * s, y: Math.max(24, (el.clientHeight - (y1 - y0) * s) / 2) - y0 * s })
  }, [items, heightOf, c])
  const fitted = useRef<string | null>(null)
  useEffect(() => {                                                // first open of a page: its saved view, else fit
    if (!page || fitted.current === gid) return
    fitted.current = gid
    const v = views.get(gid)
    if (v) { setView({ x: v.x, y: v.y }); c.setPageZoom(v.z) } else fit()
  }, [page, gid]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (fitted.current === gid) views.set(gid, { ...view, z }) }, [view, z, gid])
  const lastFit = useRef(c.fitSeq)
  useEffect(() => { if (c.fitSeq !== lastFit.current) { lastFit.current = c.fitSeq; fit() } }, [c.fitSeq, fit])
  const anchor = useRef<{ cx: number; cy: number } | null>(null)
  const lastZ = useRef(z)
  useEffect(() => {                                                // keep the anchor (cursor, else the centre) still while zooming
    const el = host.current
    if (!el || lastZ.current === z) return
    const r = el.getBoundingClientRect()
    const cx = anchor.current ? anchor.current.cx - r.left : el.clientWidth / 2, cy = anchor.current ? anchor.current.cy - r.top : el.clientHeight / 2
    const k = z / lastZ.current
    setView((v) => ({ x: cx - (cx - v.x) * k, y: cy - (cy - v.y) * k }))
    lastZ.current = z
    anchor.current = null
  }, [z])

  // ---- selection ---------------------------------------------------------------------------------------
  const selAssets = new Set(c.selected), selGroups = new Set(c.groupSel)
  const isSel = (it: { kind: string; id: string }) => (it.kind === 'asset' ? selAssets.has(it.id) : selGroups.has(it.id))
  const setSel = (assets: string[], groups: string[]) => store.setState({ selected: assets, primary: assets[assets.length - 1] ?? null, anchor: assets[0] ?? null, groupSel: groups })
  const selectedItems = () => items.filter(isSel)
  const pick = (it: Item, ctrl: boolean) => {
    if (ctrl) {
      if (it.kind === 'asset') setSel(selAssets.has(it.id) ? c.selected.filter((x) => x !== it.id) : [...c.selected, it.id], c.groupSel)
      else setSel(c.selected, selGroups.has(it.id) ? c.groupSel.filter((x) => x !== it.id) : [...c.groupSel, it.id])
    } else if (!isSel(it)) setSel(it.kind === 'asset' ? [it.id] : [], it.kind === 'group' ? [it.id] : [])
  }

  // ---- writes ------------------------------------------------------------------------------------------
  const commit = useCallback(async (next: Item[], record = true) => {
    if (!page) return
    const before = page.group.items.filter((i) => next.some((n) => key(n) === key(i))).map((i) => ({ ...i }))
    setPage({ ...page, group: { ...page.group, items: page.group.items.map((i) => next.find((n) => key(n) === key(i)) ?? i) } })
    try {
      const r = await api.patch<{ revision: number }>(`/groups/${gid}/items`, { revision: page.group.revision, items: next })
      setPage((p) => (p ? { ...p, group: { ...p.group, revision: r.revision } } : p))
      if (record) { undo.current.push({ before, after: next.map((i) => ({ ...i })) }); redo.current = [] }
    } catch (e) {
      toast(e instanceof ApiError && e.status === 409 ? 'The page changed meanwhile; reloaded it, try again' : `Could not save the layout: ${(e as Error).message}`, 'error')
      void load()
    }
  }, [page, gid, toast, load])
  const topZ = () => Math.max(0, ...items.map((i) => i.z))
  const bottomZ = () => Math.min(0, ...items.map((i) => i.z))
  const stack = (front: boolean) => { const sel = selectedItems(); if (!sel.length) return; let z0 = front ? topZ() : bottomZ() - sel.length; void commit(sel.map((i) => ({ ...i, z: ++z0 }))) }
  const undoLayout = () => { const u = undo.current.pop(); if (!u) return; redo.current.push(u); void commit(u.before, false) }
  const redoLayout = () => { const u = redo.current.pop(); if (!u) return; undo.current.push(u); void commit(u.after, false) }
  const backToUnprocessed = (sel: Item[]) => {
    const assets = sel.filter((i) => i.kind === 'asset')
    if (!assets.length) return
    void useAlbum.getState().move(assets.map(({ kind, id }) => ({ kind, id })), null).then(() => {
      setSel([], c.groupSel)
      toast(`${assets.length} back in Unprocessed`, 'info', () => void useAlbum.getState().move(assets.map(({ kind, id }) => ({ kind, id })), gid, assets.map(({ x, y, w }) => ({ x, y, w }))))
    })
  }
  const groupSelection = (sel: Item[]) => {
    if (sel.length < 1) return
    void askText({ title: 'Group these', text: `${sel.length} item${sel.length === 1 ? '' : 's'} become a group on this page, keeping their layout.`, placeholder: 'group name' }).then((name) => {
      if (!name?.trim()) return
      void api.post<{ id: string }>(`/groups/${gid}/group`, { items: sel.map(({ kind, id }) => ({ kind, id })), name: name.trim() })
        .then((g) => { setSel([], [g.id]); void useAlbum.getState().load() }).catch((e) => toast(`Group failed: ${(e as Error).message}`, 'error'))
    })
  }
  const ungroup = (id: string) => void useAlbum.getState().ungroup(id)
  const deleteGroup = (s: Summary) => void askConfirm({ title: `Delete "${s.name}"?`, text: `Its ${s.total} photo${s.total === 1 ? '' : 's'} go back to Unprocessed; nothing is trashed.`, okLabel: 'Delete group', danger: true })
    .then((ok) => { if (ok) void useAlbum.getState().remove(s.id) })

  // ---- pointer: items ------------------------------------------------------------------------------------
  const onItemDown = (e: React.PointerEvent, it: Item) => {
    if (e.button !== 0) return
    e.stopPropagation()
    host.current?.focus({ preventScroll: true })
    pick(it, e.ctrlKey || e.metaKey)
    if (e.ctrlKey || e.metaKey) return
    const moving = isSel(it) ? selectedItems() : [it]
    if (!moving.some((m) => key(m) === key(it))) moving.push(it)
    const x0 = e.clientX, y0 = e.clientY
    let dragging = false
    const zTop = topZ()
    const move = (ev: PointerEvent) => {
      const dx = (ev.clientX - x0) / z, dy = (ev.clientY - y0) / z
      if (!dragging && Math.hypot(ev.clientX - x0, ev.clientY - y0) < 4) return
      dragging = true
      const r = host.current!.getBoundingClientRect()
      if (ev.clientX < r.left - 4 || ev.clientX > r.right + 4 || ev.clientY < r.top - 4 || ev.clientY > r.bottom + 4) {
        cleanup(); setLive(null)                                      // beyond the page: carry the items to another target
        const first = moving[0]
        carry({ items: moving.map(({ kind, id }) => ({ kind, id })), from: gid, thumb: first.kind === 'asset' ? api.thumbUrl(first.id, 256) : undefined }, ev.clientX, ev.clientY)
        return
      }
      setLive(Object.fromEntries(moving.map((m, i) => [key(m), { x: m.x + dx, y: m.y + dy, w: m.w, z: zTop + 1 + i }])))
    }
    const up = (ev: PointerEvent) => {
      cleanup()
      if (!dragging) return
      const dx = (ev.clientX - x0) / z, dy = (ev.clientY - y0) / z
      setLive(null)
      void commit(moving.map((m, i) => ({ ...m, x: Math.round(m.x + dx), y: Math.round(m.y + dy), z: zTop + 1 + i })))
      window.addEventListener('click', swallow, true); setTimeout(() => window.removeEventListener('click', swallow, true), 0)
    }
    const cleanup = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up) }
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
  }
  const onResizeDown = (e: React.PointerEvent, it: Item) => {
    e.stopPropagation(); e.preventDefault()
    const x0 = e.clientX
    const move = (ev: PointerEvent) => setLive({ [key(it)]: { x: it.x, y: it.y, w: Math.max(48, it.w + (ev.clientX - x0) / z), z: it.z } })
    const up = (ev: PointerEvent) => { cleanup(); setLive(null); void commit([{ ...it, w: Math.round(Math.max(48, it.w + (ev.clientX - x0) / z)) }]) }
    const cleanup = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up) }
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
  }

  // ---- pointer: canvas (pan, marquee) -----------------------------------------------------------------------
  const onCanvasDown = (e: React.PointerEvent) => {
    host.current?.focus({ preventScroll: true })
    if (e.button === 1 || (e.button === 0 && space.current)) {
      e.preventDefault()
      const x0 = e.clientX, y0 = e.clientY, v0 = view
      const move = (ev: PointerEvent) => setView({ x: v0.x + ev.clientX - x0, y: v0.y + ev.clientY - y0 })
      const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up) }
      window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
      return
    }
    if (e.button !== 0) return
    const add = e.ctrlKey || e.metaKey
    const base = { a: add ? c.selected : [], g: add ? c.groupSel : [] }
    const r = host.current!.getBoundingClientRect()
    const m0 = { x0: e.clientX - r.left, y0: e.clientY - r.top }
    let moved = false
    const move = (ev: PointerEvent) => {
      const m = { ...m0, x1: ev.clientX - r.left, y1: ev.clientY - r.top }
      if (!moved && Math.hypot(m.x1 - m.x0, m.y1 - m.y0) < 4) return
      moved = true
      setMarquee(m)
      const [ax, bx] = [Math.min(m.x0, m.x1), Math.max(m.x0, m.x1)].map((v) => (v - view.x) / z)
      const [ay, by] = [Math.min(m.y0, m.y1), Math.max(m.y0, m.y1)].map((v) => (v - view.y) / z)
      const hit = items.filter((i) => i.x < bx && i.x + i.w > ax && i.y < by && i.y + heightOf(i) > ay)
      setSel([...new Set([...base.a, ...hit.filter((i) => i.kind === 'asset').map((i) => i.id)])], [...new Set([...base.g, ...hit.filter((i) => i.kind === 'group').map((i) => i.id)])])
    }
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); setMarquee(null); if (!moved && !add) setSel([], []) }
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
  }
  useEffect(() => {                                                // wheel pans, Ctrl+wheel zooms at the cursor (non-passive)
    const el = host.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      if (e.ctrlKey || e.metaKey) { anchor.current = { cx: e.clientX, cy: e.clientY }; store.getState().setPageZoom(store.getState().pageZoom * Math.exp(-e.deltaY * 0.0015)) }
      else setView((v) => (e.shiftKey ? { x: v.x - e.deltaY, y: v.y } : { x: v.x - e.deltaX, y: v.y - e.deltaY }))
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [store, page])

  // ---- drops from elsewhere (grid, other pane, lineage, Places) ------------------------------------------------
  useEffect(() => {
    const el = host.current
    if (!el || !page) return
    return registerDropTarget(el, {
      accept: (p: DragPayload) => p.items.length > 0 && !p.items.some((i) => i.kind === 'group' && (i.id === gid || page.path.some((s) => s.id === i.id))),
      over: (o) => setDropOver(o),
      drop: (p, info) => {
        const at = toPage(info.x, info.y)
        const here = new Set(items.map(key))
        const positions = p.items.map((_, i) => ({ x: Math.round(at.x + i * 24), y: Math.round(at.y + i * 24) }))
        if (p.items.every((i) => here.has(key(i)))) { void commit(p.items.map((i, k) => ({ ...items.find((x) => key(x) === key(i))!, ...positions[k], z: topZ() + k + 1 }))); return }
        const go = async () => {
          let moving: DragItem[] = p.items
          if (info.ctrl) {                                          // Ctrl: duplicate the photos instead of moving them
            const dups = await useAlbum.getState().duplicateAssets(p.items.filter((i) => i.kind === 'asset').map((i) => i.id))
            moving = [...dups.map((id) => ({ kind: 'asset' as const, id })), ...p.items.filter((i) => i.kind === 'group')]
          }
          await useAlbum.getState().move(moving, gid, positions.slice(0, moving.length))
          await load()
        }
        void go()
      },
    })
  }, [page, gid, items, view, z]) // eslint-disable-line react-hooks/exhaustive-deps

  // ---- keys ----------------------------------------------------------------------------------------------
  const onKey = (e: React.KeyboardEvent) => {
    if ((e.target as HTMLElement)?.closest('input, textarea, select')) return
    const sel = selectedItems()
    const k = e.key, ctrl = e.ctrlKey || e.metaKey
    if (k === ' ') { space.current = true; e.preventDefault(); return }
    if (ctrl && k.toLowerCase() === 'z') { e.preventDefault(); if (e.shiftKey) redoLayout(); else undoLayout(); return }
    if (ctrl && k.toLowerCase() === 'y') { e.preventDefault(); redoLayout(); return }
    if (ctrl && k.toLowerCase() === 'a') { e.preventDefault(); setSel(items.filter((i) => i.kind === 'asset').map((i) => i.id), items.filter((i) => i.kind === 'group').map((i) => i.id)); return }
    if (ctrl && k.toLowerCase() === 'g') { e.preventDefault(); if (e.shiftKey) { const card = sel.find((i) => i.kind === 'group'); if (card) ungroup(card.id) } else groupSelection(sel); return }
    if (k === 'Escape') { setSel([], []); return }
    if ((k === 'Delete' || k === 'Backspace') && !e.shiftKey) {
      e.preventDefault()
      const card = sel.find((i) => i.kind === 'group')
      if (card && page) deleteGroup(page.groups[card.id]); else backToUnprocessed(sel)
      return
    }
    if (k === 'Enter' && sel.length === 1 && sel[0].kind === 'group') { onOpenGroup?.(sel[0].id); return }
    if (k.startsWith('Arrow') && sel.length) {
      e.preventDefault()
      const d = e.shiftKey ? 40 : 8
      const [dx, dy] = k === 'ArrowLeft' ? [-d, 0] : k === 'ArrowRight' ? [d, 0] : k === 'ArrowUp' ? [0, -d] : [0, d]
      void commit(sel.map((i) => ({ ...i, x: i.x + dx, y: i.y + dy })))
      return
    }
    if (c.selected.length) handleKeyFor('catalogue', e.nativeEvent)   // K / X / E / R … act on the selected photos
  }

  // ---- menus ----------------------------------------------------------------------------------------------
  const stackItems: MenuItem[] = [{ label: 'Bring to front', icon: ArrowUpToLine, run: () => stack(true) }, { label: 'Send to back', icon: ArrowDownToLine, run: () => stack(false) }]
  const cardMenu = (s: Summary): MenuItem[] => [
    { label: 'Open', icon: BookOpen, run: () => onOpenGroup?.(s.id) },
    { label: 'Open in other pane', icon: Columns2, run: () => openInOtherPane({ group: s.id }) },
    sep,
    { label: 'Rename…', icon: Pencil, run: () => void askText({ title: 'Rename group', initial: s.name }).then((n) => { if (n?.trim() && n !== s.name) void useAlbum.getState().rename(s.id, n.trim()) }) },
    { label: 'Duplicate', icon: Copy, run: () => void useAlbum.getState().duplicate(s.id) },
    { label: 'Ungroup', icon: Ungroup, keys: 'Ctrl+Shift+G', run: () => ungroup(s.id) },
    sep, ...stackItems, sep,
    { label: 'Delete group…', icon: X, danger: true, run: () => deleteGroup(s) },
  ]
  const photoMenu = (): MenuItem[] => {
    const sel = selectedItems()
    const one = sel.length === 1 && sel[0].kind === 'asset' ? sel[0].id : null
    return [...tileMenu(), sep, ...stackItems, ...(sel.length > 1 ? [{ label: 'Group these…', icon: Layers, keys: 'Ctrl+G', run: () => groupSelection(sel) }] : []),
      ...(one && gid !== 'album' ? [{ label: 'Use as cover of this group', icon: BookOpen, run: () => void useAlbum.getState().setCover(gid, one) }] : [])]
  }
  const canvasMenu = (e: React.MouseEvent): MenuItem[] => {
    const at = toPage(e.clientX, e.clientY)
    return [
      { label: 'New group here…', icon: FolderPlus, run: () => void askText({ title: 'New group', placeholder: 'group name' }).then((n) => { if (n?.trim()) void api.post('/groups', { name: n.trim(), parent_id: gid, x: Math.round(at.x), y: Math.round(at.y) }).then(() => useAlbum.getState().load()) }) },
      { label: 'Select all', keys: 'Ctrl+A', run: () => setSel(items.filter((i) => i.kind === 'asset').map((i) => i.id), items.filter((i) => i.kind === 'group').map((i) => i.id)) },
      { label: 'Fit', icon: Expand, run: fit },
      sep,
      { label: 'Undo', icon: Undo, keys: 'Ctrl+Z', disabled: !undo.current.length, run: undoLayout },
      { label: 'Redo', icon: Redo, keys: 'Ctrl+Shift+Z', disabled: !redo.current.length, run: redoLayout },
    ]
  }

  // ---- render ---------------------------------------------------------------------------------------------
  const filtering = !!c.q.search || FILTERS.some((f) => f.active(c.q))
  const matches = useMemo(() => new Set(c.items.map((a) => a.id)), [c.items])
  const ordered = useMemo(() => [...items].sort((a, b) => (live?.[key(a)]?.z ?? a.z) - (live?.[key(b)]?.z ?? b.z)), [items, live])
  const thumbFor = (w: number) => (w * z * (window.devicePixelRatio || 1) > 520 ? 1024 : w * z * (window.devicePixelRatio || 1) > 260 ? 512 : 256)
  if (error) return <div className="cat-empty"><div><h2>{error}</h2><button onClick={() => openPlace(c, 'unprocessed')}>Open Unprocessed</button></div></div>
  const primaryOne = c.selected.length === 1 && !c.groupSel.length ? c.selected[0] : c.groupSel.length === 1 && !c.selected.length ? c.groupSel[0] : null
  return (
    <div ref={host} className={`page${dropOver ? ' drop-over' : ''}`} tabIndex={0} onPointerDown={onCanvasDown} onKeyDown={onKey} onKeyUp={(e) => { if (e.key === ' ') space.current = false }}
      onContextMenu={(e) => { if ((e.target as HTMLElement).closest('.pitem, .pcard')) return; e.preventDefault(); showMenu(e, canvasMenu(e)) }}
      style={{ backgroundPosition: `${view.x}px ${view.y}px`, backgroundSize: `${24 * z}px ${24 * z}px` }}>
      <div className="page-world" style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${z})` }}>
        {page && ordered.map((it) => {
          const p = pos(it), h = heightOf({ ...it, w: p.w }), sel = isSel(it)
          const style = { left: p.x, top: p.y, width: p.w, height: h, zIndex: p.z }
          if (it.kind === 'group') {
            const s = page.groups[it.id]
            if (!s) return null
            return (
              <div key={key(it)} className={`pcard${sel ? ' selected' : ''}`} style={style} onPointerDown={(e) => onItemDown(e, it)} onDoubleClick={() => onOpenGroup?.(it.id)}
                onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); if (!sel) setSel([], [it.id]); showMenu(e, cardMenu(s)) }} title={`${s.name}: ${s.total} photo${s.total === 1 ? '' : 's'} · double-click to open`}>
                <div className="fan">{s.cover_ids.slice(0, 3).reverse().map((aid, i, arr) => <img key={aid} src={api.thumbUrl(aid, 256)} alt="" draggable={false} style={{ left: `${(arr.length - 1 - i) * 9}%`, top: `${(arr.length - 1 - i) * 7}%` }} />)}{!s.cover_ids.length && <span className="empty">empty</span>}</div>
                <div className="cap"><b>{s.name}</b><span>{s.total}</span></div>
                {primaryOne === it.id && <span className="handle" onPointerDown={(e) => onResizeDown(e, it)} title="drag to resize" />}
              </div>
            )
          }
          const a = page.assets[it.id]
          if (!a) return null
          const dim = filtering && !matches.has(it.id)
          return (
            <div key={key(it)} className={`pitem${sel ? ' selected' : ''}${dim ? ' dim' : ''}${a.state === 'reject' ? ' reject' : ''}`} style={style} onPointerDown={(e) => onItemDown(e, it)}
              onDoubleClick={() => c.openLoupe(it.id)} onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); if (!sel) setSel([it.id], []); showMenu(e, photoMenu()) }}
              title={`${a.model_id ?? a.suite} · seed ${a.seed ?? '—'} · ${a.w}×${a.h}`}>
              <img src={api.thumbUrl(it.id, thumbFor(p.w))} alt="" draggable={false} />
              {(a.state !== 'none' || a.rating > 0) && <span className="marks">{a.state === 'keep' && <i className="k">✓</i>}{a.state === 'reject' && <i className="r">✗</i>}{a.rating > 0 && <i className="s">{'★'.repeat(a.rating)}</i>}</span>}
              {primaryOne === it.id && <span className="handle" onPointerDown={(e) => onResizeDown(e, it)} title="drag to resize" />}
            </div>
          )
        })}
      </div>
      {marquee && <div className="marquee" style={{ left: Math.min(marquee.x0, marquee.x1), top: Math.min(marquee.y0, marquee.y1), width: Math.abs(marquee.x1 - marquee.x0), height: Math.abs(marquee.y1 - marquee.y0) }} />}
      {page && !items.length && <div className="page-empty"><div><h2>{page.group.name} is empty</h2><p>Drag photos here from Unprocessed: split the Stage (<Columns2 size={12} style={{ verticalAlign: '-2px' }} /> in the strip) to see both, or drop tiles on this group in the Places panel.</p></div></div>}
      {!page && <div className="page-empty"><div>loading…</div></div>}
    </div>
  )
}

function swallow(e: MouseEvent): void { e.stopPropagation(); e.preventDefault() }
