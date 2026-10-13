// Global commands (07 §4): frame toggles, settings, help, the command palette. Suite switching stays on the
// TopBar tabs (Ctrl+1…5) and is registered here so the help overlay lists it.
import { Clapperboard, FilePlus, Menu, FolderOpen, FolderPlus, Info, Keyboard, LayoutGrid, Maximize2, PanelBottom, PanelLeft, PanelRight, RefreshCw, Settings, Sparkles } from 'lucide-react'
const CircleHelp = Info
import { useSession } from '../store/session'
import { registerCommands } from './commands'
import { openWith } from './openWith'
import { usePalette } from './CommandPalette'

const s = () => useSession.getState()

registerCommands([
  { id: 'global.palette', scope: 'global', label: 'Command palette', icon: Keyboard, keys: 'Ctrl+K', placement: ['topbar'], run: () => usePalette.getState().toggle() },
  { id: 'global.contextMenu', scope: 'global', label: 'Open the menu of the focused item', icon: Menu, keys: 'Shift+F10', alt: ['ContextMenu'], placement: ['context'],
    hint: 'a right-click does the same', run: () => void import('./useKeyboardMap').then((m) => m.openContextMenuAtFocus()) },   // D72: was a key in useKeyboardMap only
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
  { id: 'global.suite.stage', scope: 'global', label: 'Stage', keys: 'Ctrl+6', placement: ['topbar'], run: () => s().setSuite('stage') },   // P13 (D81)
  // D71 (P15): quick actions — the empty states' cards, the app menu and the palette
  { id: 'global.project.new', scope: 'global', label: 'New project…', icon: FolderPlus, placement: ['topbar', 'toolbar'], run: () => s().setProjectDialog('new') },
  { id: 'global.project.open', scope: 'global', label: 'Open a project…', icon: FolderOpen, placement: ['topbar', 'toolbar'], run: () => s().setProjectDialog('open') },
  { id: 'global.start.generate', scope: 'global', label: 'Generate an image', icon: Sparkles, placement: ['toolbar'], when: () => !!s().project?.open,
    run: () => { s().setSuite('generate'); void import('./suiteRegistry').then((m) => m.setRailTab('generate', 'prompt')) } },
  { id: 'global.start.newDocument', scope: 'global', label: 'New document', icon: FilePlus, placement: ['toolbar'], when: () => !!s().project?.open,
    run: () => void openWith(null, { suite: 'edit' }).then(() => import('../suites/edit/editorStore')).then((m) => m.useEditor.getState().newDocument(1920, 1080)) },
  { id: 'global.start.animate', scope: 'global', label: 'Animate from an image', icon: Clapperboard, placement: ['toolbar'], when: () => !!s().project?.open,
    run: () => { s().setSuite('catalogue'); s().toast('Pick an image, then Animate ▾ under the loupe or in the Inspector (Shift+A), or drag it onto the Animate tab', 'info') } },
])
