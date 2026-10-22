// Global commands (07 §4): frame toggles, settings, help, the command palette. Suite switching stays on the
// TopBar tabs (Ctrl+1…5) and is registered here so the help overlay lists it.
import { Boxes, Clapperboard, FilePlus, Film, Images, Menu, MonitorPlay, FolderOpen, FolderPlus, Info, Keyboard, LayoutGrid, Maximize2, PanelBottom, PanelLeft, PanelRight, Pencil, RefreshCw, Settings, Shapes, Sparkles } from 'lucide-react'
const CircleHelp = Info
import { useSession } from '../store/session'
import { TOP_TABS } from './railTabs'
import { registerCommands } from './commands'
import { openWith } from './openWith'
import { usePalette } from './CommandPalette'

const s = () => useSession.getState()
const openTop = (id: string) => import('./topTabs').then((m) => { const t = TOP_TABS.find((x) => x.id === id); if (t) m.openTopTab(t) })
/** D90: one of Story's six workspaces (Alt+1–6), across the Story and Catalogue suites. */
const openStory = (w: string) => void import('./suiteRegistry').then((m) => {
  if (w === 'catalogue') { s().setSuite('catalogue'); return }
  m.setRailTab('story', w); s().setSuite('story'); s().setUi({ panelOpen: true })
})

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
  // D90 (02 §3) → D95 (IM1, AN1): the tabs are Story · Image · Animate, keyed Ctrl+1–3 in their order;
  // Image's two modes, Make and Edit, keep their commands without a top-bar key (the column's switch, the palette, remapped keys); the
  // Catalogue is Story's third workspace and Models & engine a sheet in ☰
  { id: 'global.suite.story', scope: 'global', label: 'Story', keys: 'Ctrl+1', placement: ['topbar'], run: () => void openTop('story') },
  { id: 'global.suite.image', scope: 'global', label: 'Image', keys: 'Ctrl+2', placement: ['topbar'], run: () => void openTop('image') },
  { id: 'global.suite.generate', scope: 'global', label: 'Image · Make', icon: Sparkles, placement: ['topbar', 'panel'], run: () => s().setSuite('generate') },
  { id: 'global.suite.edit', scope: 'global', label: 'Image · Edit', icon: Pencil, placement: ['topbar', 'panel'], run: () => s().setSuite('edit') },
  { id: 'global.suite.animate', scope: 'global', label: 'Animate', keys: 'Ctrl+3', placement: ['topbar'], run: () => void openTop('animate') },
  // AN1: Animate's viewer levels (frame/AnimateLevels.tsx) — Clay is the stage suite (P13, D81), Performance the animate suite, (D121) Final the final suite
  { id: 'global.suite.stage', scope: 'global', label: 'Animate · Clay', icon: Shapes, placement: ['topbar', 'strip'], run: () => s().setSuite('stage') },
  { id: 'global.animate.performance', scope: 'global', label: 'Animate · Performance', icon: Film, placement: ['topbar', 'strip'], run: () => s().setSuite('animate') },
  { id: 'global.animate.final', scope: 'global', label: 'Animate · Final', icon: MonitorPlay, placement: ['topbar', 'strip'], run: () => s().setSuite('final') },   // D121: the Final level, a mode of its own
  { id: 'global.suite.catalogue', scope: 'global', label: 'Catalogue (Story)', icon: Images, placement: ['rail'], run: () => s().setSuite('catalogue') },
  { id: 'global.suite.models', scope: 'global', label: 'Models & engine…', icon: Boxes, placement: ['topbar'], run: () => s().openModels() },
  ...(['world', 'cast', 'catalogue', 'shots', 'flow', 'episode'] as const).map((w, i) => ({
    id: `global.story.${w}`, scope: 'global' as const, label: `Story · ${w[0].toUpperCase()}${w.slice(1)}`, keys: `Alt+${i + 1}`, placement: ['rail'] as ['rail'],
    run: () => void openStory(w),
  })),
  // D110 (PS1): Props sits beside Cast on the rail; its key comes after the six so theirs stay as they were
  { id: 'global.story.props', scope: 'global', label: 'Story · Props', keys: 'Alt+7', placement: ['rail'], run: () => void openStory('props') },
  // D71 (P15): quick actions — the empty states' cards, the app menu and the palette
  { id: 'global.project.new', scope: 'global', label: 'New project…', icon: FolderPlus, placement: ['topbar', 'toolbar'], run: () => s().setProjectDialog('new') },
  { id: 'global.project.open', scope: 'global', label: 'Open a project…', icon: FolderOpen, placement: ['topbar', 'toolbar'], run: () => s().setProjectDialog('open') },
  { id: 'global.start.generate', scope: 'global', label: 'Generate an image', icon: Sparkles, placement: ['toolbar'], when: () => !!s().project?.open,
    run: () => { s().setSuite('generate'); void import('./suiteRegistry').then((m) => m.setRailTab('generate', 'prompt')) } },
  { id: 'global.start.newDocument', scope: 'global', label: 'New document', icon: FilePlus, placement: ['toolbar', 'topbar'], when: () => !!s().project?.open,   // D95 (UX0 #3): also in ☰
    run: () => void openWith(null, { suite: 'edit' }).then(() => import('../suites/edit/editorStore')).then((m) => m.useEditor.getState().newDocument(1920, 1080)) },
  { id: 'global.start.animate', scope: 'global', label: 'Animate from an image', icon: Clapperboard, placement: ['toolbar'], when: () => !!s().project?.open,
    run: () => { s().setSuite('catalogue'); s().toast('Pick an image, then Animate ▾ under the loupe or in the Inspector (Shift+A), or drag it onto the Animate tab', 'info') } },
])
