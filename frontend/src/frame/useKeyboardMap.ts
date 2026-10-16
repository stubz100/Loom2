// Global keyboard map (07 §4): keys are accelerators for registry commands. Suite keys are handled by the
// suites' own hooks through `handleKeyFor(scope, e)`. Shift+F10 / the Menu key open the context menu of the
// focused element so every right-click menu is reachable from the keyboard.
import { useEffect } from 'react'
import { useSession } from '../store/session'
import { command, handleKeyFor, matchesCommand } from './commands'
import { usePalette } from './CommandPalette'
import './globalCommands'

/** Marks a contextmenu event this module dispatched from the keyboard (Shift+F10 / the Menu key), so a host can tell it from a right-click. */
export const FROM_KEYS = 'loom2FromKeys'
export const isMenuFromKeys = (e: Event): boolean => !!(e as unknown as Record<string, unknown>)[FROM_KEYS]

export function openContextMenuAtFocus(): void {
  const el = (document.activeElement as HTMLElement | null) ?? document.body
  let target = el.closest('[data-id], .layer-row, .job, .loupe, .edit-canvas, .cat-grid') as HTMLElement | null ?? el
  // D90 (B16): the Catalogue grid has the focus, its tiles never do — the menu is the primary selected tile's when it is rendered; when it
  // is scrolled out of the virtual window the grid opens the tile menu itself (it sees FROM_KEYS and a selection)
  if (target.matches('.cat-grid')) target = target.querySelector<HTMLElement>('.tile.primary') ?? target.querySelector<HTMLElement>('.tile.selected') ?? target
  const r = target.getBoundingClientRect()
  const ev = new MouseEvent('contextmenu', { bubbles: true, cancelable: true, clientX: r.left + Math.min(24, r.width / 2), clientY: r.top + Math.min(24, r.height / 2) })
  target.dispatchEvent(Object.assign(ev, { [FROM_KEYS]: true }))
}

export function useKeyboardMap() {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const s = useSession.getState()
      const inField = (e.target as HTMLElement)?.closest('input, textarea, select, [contenteditable], .modal')    // a modal owns its keys
      // D72: the menu key and the palette answer in fields too, through their registry commands (so a remap applies)
      const menu = command('global.contextMenu'), palette = command('global.palette')
      if (menu && matchesCommand(e, menu)) { e.preventDefault(); openContextMenuAtFocus(); return }
      if (palette && matchesCommand(e, palette)) { e.preventDefault(); usePalette.getState().toggle(); return }
      if (usePalette.getState().open) return
      if (e.ctrlKey || e.metaKey) { if (handleKeyFor('global', e)) return }
      if (inField) return
      if (e.key === 'Escape') {
        if (s.helpOpen) s.setHelp(false)
        else if (s.settingsOpen) s.openSettings(false)
        else if (s.projectDialog) s.setProjectDialog(null)
        return
      }
      handleKeyFor('global', e)                                         // incl. Tab → focus mode (global.focus, a fixed key)
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [])
}
