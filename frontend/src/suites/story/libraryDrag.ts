// D92 (owed until 2026-10-17): World › Library's drag reorder — a press on a tile that moves 5 px becomes a drag within its field's row:
// an insertion line before / after the tile under the pointer (left / right half), the entry's name on a ghost, Esc cancels; the drop is
// `useLibrary.moveTo` (the same `PUT /story/library/order` as Move earlier / later, which stay). A drag never leaves its field (a field's
// entries are that field's words). Pointer events, as every in-app drag (frame/AGENTS.md rule 2) — the edit layers panel's pattern.
import { useLibrary } from './libraryStore'

const MARKS = ['drop-before', 'drop-after'] as const

/** Where a drop at x lands relative to a tile: its left half → before, its right half → after. */
export function sideOf(x: number, r: { left: number; width: number }): 'before' | 'after' {
  return x < r.left + r.width / 2 ? 'before' : 'after'
}

export function libraryDrag(e: React.PointerEvent<HTMLElement>): void {
  const tile = (e.target as HTMLElement).closest<HTMLElement>('.preset-icon[data-id]')
  if (e.button !== 0 || !tile) return
  const row = e.currentTarget, id = tile.dataset.id!
  const x0 = e.clientX, y0 = e.clientY
  let dragging = false, ghost: HTMLDivElement | null = null
  let target: { id: string; where: 'before' | 'after' } | null = null
  const clear = () => row.querySelectorAll('.drop-before, .drop-after').forEach((el) => el.classList.remove(...MARKS))
  const hit = (x: number, y: number) => {
    clear(); target = null
    const el = (document.elementFromPoint(x, y) as HTMLElement | null)?.closest<HTMLElement>('.preset-icon[data-id]')
    if (!el || !row.contains(el) || el.dataset.id === id) return
    const where = sideOf(x, el.getBoundingClientRect())
    target = { id: el.dataset.id!, where }
    el.classList.add(`drop-${where}`)
  }
  const end = () => {
    window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); window.removeEventListener('pointercancel', up); window.removeEventListener('keydown', key, true)
    ghost?.remove(); clear(); tile.classList.remove('dragging')
  }
  const move = (ev: PointerEvent) => {
    if (!dragging) {
      if (Math.hypot(ev.clientX - x0, ev.clientY - y0) < 5) return
      dragging = true
      ghost = document.createElement('div'); ghost.className = 'lib-ghost'
      ghost.textContent = tile.getAttribute('aria-label') ?? ''
      document.body.appendChild(ghost)
      tile.classList.add('dragging')
    }
    if (ghost) { ghost.style.left = `${ev.clientX + 12}px`; ghost.style.top = `${ev.clientY + 8}px` }
    hit(ev.clientX, ev.clientY)
  }
  const up = (ev: PointerEvent) => {
    const t = target
    end()
    if (!dragging || ev.type === 'pointercancel') return
    libraryDrag.justDropped = true; setTimeout(() => { libraryDrag.justDropped = false })
    if (t) void useLibrary.getState().moveTo(id, t.id, t.where)
  }
  const key = (ev: KeyboardEvent) => { if (ev.key === 'Escape' && dragging) { ev.preventDefault(); ev.stopPropagation(); target = null; dragging = false; end() } }
  window.addEventListener('pointermove', move); window.addEventListener('pointerup', up); window.addEventListener('pointercancel', up); window.addEventListener('keydown', key, true)
}
/** True for the click that follows a drop (the row swallows it, so the tile under the pointer is not selected). */
libraryDrag.justDropped = false
