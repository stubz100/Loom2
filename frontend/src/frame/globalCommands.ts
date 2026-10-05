// Global commands (07 §4): frame toggles, settings, help, the command palette. Suite switching stays on the
// TopBar tabs (Ctrl+1…5) and is registered here so the help overlay lists it.
import { Info, Keyboard, LayoutGrid, Maximize2, PanelBottom, PanelLeft, PanelRight, RefreshCw, Settings } from 'lucide-react'
const CircleHelp = Info
import { useSession } from '../store/session'
import { registerCommands } from './commands'
import { usePalette } from './CommandPalette'

const s = () => useSession.getState()

registerCommands([
  { id: 'global.palette', scope: 'global', label: 'Command palette', icon: Keyboard, keys: 'Ctrl+K', placement: ['topbar'], run: () => usePalette.getState().toggle() },
  { id: 'global.help', scope: 'global', label: 'Keyboard map and commands', icon: CircleHelp, keys: '?', placement: ['topbar'], run: () => s().setHelp(!s().helpOpen) },
  { id: 'global.settings', scope: 'global', label: 'Settings…', icon: Settings, keys: 'Ctrl+,', placement: ['rail', 'topbar'], run: () => s().openSettings(true) },
  { id: 'global.panel', scope: 'global', label: 'Toggle panel', icon: PanelLeft, keys: 'Ctrl+B', placement: ['rail'], run: () => s().setUi({ panelOpen: !s().ui.panelOpen }) },
  { id: 'global.inspector', scope: 'global', label: 'Toggle inspector', icon: PanelRight, keys: 'Ctrl+I', placement: ['rail'], run: () => s().setUi({ inspectorOpen: !s().ui.inspectorOpen }) },
  { id: 'global.dock', scope: 'global', label: 'Toggle dock', icon: PanelBottom, keys: '`', placement: ['rail', 'dock'], run: () => s().setUi({ dockOpen: !s().ui.dockOpen }) },
  { id: 'global.focus', scope: 'global', label: 'Focus mode (hide panel + inspector)', icon: Maximize2, keys: 'Tab', placement: ['rail', 'topbar'], run: () => s().setUi({ focusMode: !s().ui.focusMode }) },
  { id: 'global.density', scope: 'global', label: 'Toggle density', icon: LayoutGrid, placement: ['topbar'], run: () => s().setUi({ density: s().ui.density === 'compact' ? 'comfortable' : 'compact' }) },
  { id: 'global.refresh', scope: 'global', label: 'Refresh state', icon: RefreshCw, placement: ['topbar'], run: () => void s().refreshAll() },
  { id: 'global.suite.catalogue', scope: 'global', label: 'Catalogue', keys: 'Ctrl+1', placement: ['topbar'], run: () => s().setSuite('catalogue') },
  { id: 'global.suite.generate', scope: 'global', label: 'Generate', keys: 'Ctrl+2', placement: ['topbar'], run: () => s().setSuite('generate') },
  { id: 'global.suite.edit', scope: 'global', label: 'Edit', keys: 'Ctrl+3', placement: ['topbar'], run: () => s().setSuite('edit') },
  { id: 'global.suite.animate', scope: 'global', label: 'Animate', keys: 'Ctrl+4', placement: ['topbar'], run: () => s().setSuite('animate') },
  { id: 'global.suite.models', scope: 'global', label: 'Models', keys: 'Ctrl+5', placement: ['topbar'], run: () => s().setSuite('models') },
])
