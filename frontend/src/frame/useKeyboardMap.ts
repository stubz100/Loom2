// Global keyboard map (07 §4). Suite-scoped keys register through their own hooks later.
import { useEffect } from 'react'
import { useSession } from '../store/session'
import { SUITES } from './TopBar'

export function useKeyboardMap() {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const s = useSession.getState()
      const inField = (e.target as HTMLElement)?.closest('input, textarea, select, [contenteditable]')
      if (e.ctrlKey && !e.shiftKey && !e.altKey && /^[1-5]$/.test(e.key)) { e.preventDefault(); s.setSuite(SUITES[Number(e.key) - 1].id); return }
      if (e.ctrlKey && e.key === ',') { e.preventDefault(); s.openSettings(true); return }
      if (e.ctrlKey && e.key.toLowerCase() === 'b') { e.preventDefault(); s.setUi({ panelOpen: !s.ui.panelOpen }); return }
      if (e.ctrlKey && e.key.toLowerCase() === 'i') { e.preventDefault(); s.setUi({ inspectorOpen: !s.ui.inspectorOpen }); return }
      if (inField) return
      if (e.key === '`') { e.preventDefault(); s.setUi({ dockOpen: !s.ui.dockOpen }); return }
      if (e.key === 'Tab' && !e.ctrlKey && !e.altKey) { e.preventDefault(); s.setUi({ focusMode: !s.ui.focusMode }); return }
      if (e.key === '?') { e.preventDefault(); s.setHelp(!s.helpOpen); return }
      if (e.key === 'Escape') {
        if (s.helpOpen) s.setHelp(false)
        else if (s.settingsOpen) s.openSettings(false)
        else if (s.projectDialog) s.setProjectDialog(null)
      }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [])
}
