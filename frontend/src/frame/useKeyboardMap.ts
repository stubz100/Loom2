// Global keyboard map (07 §4): keys are accelerators for registry commands. Suite keys are handled by the
// suites' own hooks through `handleKeyFor(scope, e)`. Shift+F10 / the Menu key open the context menu of the
// focused element so every right-click menu is reachable from the keyboard.
import { useEffect } from 'react'
import { useSession } from '../store/session'
import { handleKeyFor } from './commands'
import { usePalette } from './CommandPalette'
import './globalCommands'

export function openContextMenuAtFocus(): void {
  const el = (document.activeElement as HTMLElement | null) ?? document.body
  const target = el.closest('[data-id], .layer-row, .job, .loupe, .edit-canvas, .cat-grid') as HTMLElement | null ?? el
  const r = target.getBoundingClientRect()
  target.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true, clientX: r.left + Math.min(24, r.width / 2), clientY: r.top + Math.min(24, r.height / 2) }))
}

export function useKeyboardMap() {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const s = useSession.getState()
      const inField = (e.target as HTMLElement)?.closest('input, textarea, select, [contenteditable], .modal')    // a modal owns its keys
      if (e.key === 'ContextMenu' || (e.shiftKey && e.key === 'F10')) { e.preventDefault(); openContextMenuAtFocus(); return }
      if (e.ctrlKey && e.key.toLowerCase() === 'k') { e.preventDefault(); usePalette.getState().toggle(); return }
      if (usePalette.getState().open) return
      if (e.ctrlKey || e.metaKey) { if (handleKeyFor('global', e)) return }
      if (inField) return
      if (e.key === 'Escape') {
        if (s.helpOpen) s.setHelp(false)
        else if (s.settingsOpen) s.openSettings(false)
        else if (s.projectDialog) s.setProjectDialog(null)
        return
      }
      if (e.key === 'Tab' && !e.ctrlKey && !e.altKey) { e.preventDefault(); s.setUi({ focusMode: !s.ui.focusMode }); return }
      handleKeyFor('global', e)
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [])
}
