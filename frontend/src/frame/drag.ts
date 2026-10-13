// Drag and drop of assets and groups by pointer events (proto01_design/01 §6c). Inside Tauri, WebView2 with the OS file-drop
// handler on (needed to import dropped files with their paths) delivers no HTML5 drag events within the page, so tiles, page
// items and cards are dragged by this manager instead; drop targets register an element. One drag at a time.
// `beginDrag` starts after a few pixels of movement (a plain click stays a click); `carry` hands an already moving pointer
// over (an album page moves its items itself until the pointer leaves the page, then carries them to another target).
// D71 (P11): a target may `describe` a payload — what a drop would do ("Add as reference 3 of 4") or why it would not ("Clips can't be
// references"); the ghost shows ✓ or ✕ with that text while it hovers. `onDragHover` lets a target act on a long hover (spring-loaded tabs).
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

export interface DragItem { kind: 'asset' | 'group'; id: string; media?: 'image' | 'video' | 'mesh' }   // media: known where the drag starts (mesh: P18, a GLB prop)
/** The drag medium of an asset kind (every other kind drags as an image). */
export const mediaOf = (kind: string | undefined): 'image' | 'video' | 'mesh' => (kind === 'video' ? 'video' : kind === 'mesh' ? 'mesh' : 'image')
export interface DragPayload { items: DragItem[]; from?: string; thumb?: string; label?: string; onCancel?: () => void }
export interface DropInfo { x: number; y: number; ctrl: boolean; el: HTMLElement }

/** What a drop on a target would do (`ok`, `label`) or why it would not (`reason`). */
export interface DropVerdict { ok: boolean; label?: string; reason?: string }

export interface DropTarget {
  accept: (p: DragPayload) => boolean
  drop: (p: DragPayload, info: DropInfo) => void
  over?: (over: boolean, p: DragPayload | null) => void
  describe?: (p: DragPayload) => DropVerdict | null
}

const targets = new Map<HTMLElement, DropTarget>()
let active: { payload: DragPayload; ghost: HTMLDivElement; hint: HTMLSpanElement; over: HTMLElement | null; hintText: string } | null = null
const listeners = new Set<(p: DragPayload | null) => void>()

/** Asset ids of a payload (most drop targets take assets only). */
export const assetIds = (p: DragPayload): string[] => p.items.filter((i) => i.kind === 'asset').map((i) => i.id)
export const onlyAssets = (p: DragPayload): boolean => p.items.length > 0 && p.items.every((i) => i.kind === 'asset')
/** Asset items that are clips (by `media`, when the drag source knew it). */
export const clipIds = (p: DragPayload): string[] => p.items.filter((i) => i.kind === 'asset' && i.media === 'video').map((i) => i.id)

export function registerDropTarget(el: HTMLElement, t: DropTarget): () => void {
  targets.set(el, t)
  return () => { if (targets.get(el) === t) targets.delete(el) }
}

/** Register the element behind the returned ref as a drop target; `over` is true while an accepted drag hovers it. */
export function useDropTarget(accept: DropTarget['accept'], drop: DropTarget['drop'], describe?: DropTarget['describe']): { ref: (el: HTMLElement | null) => void; over: boolean } {
  const [over, setOver] = useState(false)
  const cb = useRef({ accept, drop, describe })
  useLayoutEffect(() => { cb.current = { accept, drop, describe } })   // the latest handlers, without re-registering
  const unreg = useRef<(() => void) | null>(null)
  const ref = useCallback((el: HTMLElement | null) => {
    unreg.current?.()
    unreg.current = el ? registerDropTarget(el, { accept: (p) => cb.current.accept(p), drop: (p, i) => cb.current.drop(p, i), over: (o) => setOver(o), describe: (p) => cb.current.describe?.(p) ?? null }) : null
  }, [])
  useEffect(() => () => unreg.current?.(), [])
  return { ref, over }
}

/** The payload of the drag in progress (null when none), for views that highlight while something is carried. */
export function useDragging(): DragPayload | null {
  const [p, setP] = useState<DragPayload | null>(active?.payload ?? null)
  useEffect(() => { listeners.add(setP); return () => { listeners.delete(setP) } }, [])
  return p
}

/** The innermost accepting target under (x, y), with what a drop would do; else the innermost refusal that says why (no element). */
export function resolveTarget(start: HTMLElement | null, p: DragPayload, lookup: (el: HTMLElement) => DropTarget | undefined = (el) => targets.get(el)): { el: HTMLElement | null; verdict: DropVerdict | null } {
  let refusal: DropVerdict | null = null
  for (let el = start; el; el = el.parentElement) {
    const t = lookup(el)
    if (!t) continue
    if (t.accept(p)) { const v = t.describe?.(p) ?? null; return { el, verdict: v?.ok === false ? { ok: true } : v } }
    if (!refusal) { const v = t.describe?.(p); if (v && !v.ok && v.reason) refusal = v }
  }
  return { el: null, verdict: refusal }
}

function swallowClick(c: MouseEvent): void { c.stopPropagation(); c.preventDefault() }

function start(p: DragPayload): void {
  const ghost = document.createElement('div')
  ghost.className = 'drag-ghost'
  if (p.thumb) { const img = document.createElement('img'); img.src = p.thumb; ghost.append(img) }
  const n = document.createElement('span')
  const groups = p.items.filter((i) => i.kind === 'group').length
  n.textContent = p.label ?? (p.items.length > 1 ? `${p.items.length} items` : groups ? 'group' : '1 photo')
  ghost.append(n)
  const hint = document.createElement('span')
  hint.className = 'drop-hint'
  ghost.append(hint)
  document.body.append(ghost)
  active = { payload: p, ghost, hint, over: null, hintText: '' }
  document.body.classList.add('dragging')
  listeners.forEach((l) => l(p))
}

function moveTo(x: number, y: number): void {
  if (!active) return
  active.ghost.style.transform = `translate(${x + 12}px, ${y + 12}px)`
  const { el: over, verdict } = resolveTarget(document.elementFromPoint(x, y) as HTMLElement | null, active.payload)
  if (over !== active.over) {
    if (active.over) targets.get(active.over)?.over?.(false, null)
    if (over) targets.get(over)?.over?.(true, active.payload)
    active.over = over
  }
  active.ghost.classList.toggle('can-drop', !!over)
  const refused = !over && !!verdict?.reason
  active.ghost.classList.toggle('refused', refused)
  const text = over && verdict?.label ? `✓ ${verdict.label}` : refused ? `✕ ${verdict!.reason}` : ''
  if (text !== active.hintText) { active.hint.textContent = text; active.hintText = text }
}

function finish(): void {
  if (!active) return
  if (active.over) targets.get(active.over)?.over?.(false, null)
  active.ghost.remove()
  active = null
  document.body.classList.remove('dragging')
  listeners.forEach((l) => l(null))
}

/** Follow the pointer until it is released: drop on the target under it (or cancel with Esc / nowhere to drop). */
function follow(x0: number, y0: number): void {
  moveTo(x0, y0)
  const move = (ev: PointerEvent) => moveTo(ev.clientX, ev.clientY)
  const up = (ev: PointerEvent) => {
    cleanup()
    if (!active) return
    const { payload: p, over } = active
    finish()
    // the click that follows this pointerup belongs to the drag, not to whatever lies under the pointer
    window.addEventListener('click', swallowClick, true)
    setTimeout(() => window.removeEventListener('click', swallowClick, true), 0)
    if (over) targets.get(over)?.drop(p, { x: ev.clientX, y: ev.clientY, ctrl: ev.ctrlKey || ev.metaKey, el: over })
    else p.onCancel?.()
  }
  const key = (ev: KeyboardEvent) => { if (ev.key === 'Escape' && active) { ev.preventDefault(); const p = active.payload; finish(); cleanup(); p.onCancel?.() } }
  const cleanup = () => {
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', up)
    window.removeEventListener('keydown', key, true)
  }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', up)
  window.addEventListener('keydown', key, true)
}

/** Call from a pointerdown: the drag starts once the pointer has moved a few pixels (a plain click stays a click). */
export function beginDrag(e: React.PointerEvent | PointerEvent, payload: () => DragPayload | null, opts: { threshold?: number } = {}): void {
  if (e.button !== 0 || active) return
  const x0 = e.clientX, y0 = e.clientY
  const threshold = opts.threshold ?? 5
  const move = (ev: PointerEvent) => {
    if (Math.hypot(ev.clientX - x0, ev.clientY - y0) < threshold) return
    cleanup()
    const p = payload()
    if (!p || !p.items.length) return
    start(p)
    follow(ev.clientX, ev.clientY)
  }
  const cleanup = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', cleanup) }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', cleanup)
}

/** Take over a pointer that is already moving something (from the pointer position x, y) and carry the payload. */
export function carry(payload: DragPayload, x: number, y: number): void {
  if (active || !payload.items.length) return
  start(payload)
  follow(x, y)
}
