// Global commands (07 §4): frame toggles, settings, help, the command palette. Suite switching stays on the
// TopBar tabs (Ctrl+1…5) and is registered here so the help overlay lists it.
import { Boxes, Clapperboard, FilePlus, Film, Images, Layers3, Menu, MonitorPlay, FolderOpen, FolderPlus, Info, Keyboard, LayoutGrid, Maximize2, PanelBottom, PanelLeft, PanelRight, Pencil, RefreshCw, Settings, Shapes, Sparkles } from 'lucide-react'
const CircleHelp = Info
import { useSession } from '../store/session'
import { TOP_TABS } from './railTabs'
import { registerCommands } from './commands'
import { openWith } from './openWith'
import { usePalette } from './CommandPalette'
import { navigate, UI2, type Layer } from './router'
import { useLayer } from '../ui2/layers'

const s = () => useSession.getState()
const openTop = (id: string) => import('./topTabs').then((m) => { const t = TOP_TABS.find((x) => x.id === id); if (t) m.openTopTab(t) })
/** D90 → D125: one of Story's five workspaces (Alt+1–5, in the rail's order). */
const openStory = (w: string) => { navigate({ suite: 'story', tab: w }); s().setUi({ panelOpen: true }) }
/** U1 (D157): in the new shell the four tabs and Ctrl+1–4 are its layers (the same commands, so one chord stays one command). */
const openLayer = (l: Layer) => useLayer.getState().setLayer(l)
/** U1 (D157, 07 §1): the new shell, or back to this one — the page reloads on the other entry; the token and the port ride along. */
function switchUi(): void {
  const q = new URLSearchParams(location.search)
  if (UI2) q.delete('ui'); else q.set('ui', '2')
  location.search = q.toString()
}

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
  // D90 (02 §3) → D95 (IM1, AN1) → D125: the tabs are Story · Image · Animate · Catalogue, keyed Ctrl+1–4 in their order;
  // Image's two modes, Make and Edit, keep their commands without a top-bar key (the column's switch, the palette, remapped keys);
  // Models & engine is a sheet in ☰
  { id: 'global.suite.story', scope: 'global', label: UI2 ? 'World' : 'Story', keys: 'Ctrl+1', placement: ['topbar'], run: () => (UI2 ? openLayer('world') : void openTop('story')) },
  { id: 'global.suite.image', scope: 'global', label: UI2 ? 'Shots' : 'Image', keys: 'Ctrl+2', placement: ['topbar'], run: () => (UI2 ? openLayer('shots') : void openTop('image')) },
  { id: 'global.suite.generate', scope: 'global', label: 'Image · Make', icon: Sparkles, placement: ['topbar', 'panel'], run: () => navigate({ suite: 'generate' }) },
  { id: 'global.suite.edit', scope: 'global', label: 'Image · Edit', icon: Pencil, placement: ['topbar', 'panel'], run: () => navigate({ suite: 'edit' }) },
  { id: 'global.suite.animate', scope: 'global', label: UI2 ? 'Episode' : 'Animate', keys: 'Ctrl+3', placement: ['topbar'], run: () => (UI2 ? openLayer('episode') : void openTop('animate')) },
  // AN1: Animate's viewer levels (frame/AnimateLevels.tsx) — Clay is the stage suite (P13, D81), Performance the animate suite, (D121) Final the final suite
  { id: 'global.suite.stage', scope: 'global', label: 'Animate · Clay', icon: Shapes, placement: ['topbar', 'strip'], run: () => navigate({ suite: 'stage' }) },
  { id: 'global.animate.performance', scope: 'global', label: 'Animate · Performance', icon: Film, placement: ['topbar', 'strip'], run: () => navigate({ suite: 'animate' }) },
  { id: 'global.animate.final', scope: 'global', label: 'Animate · Final', icon: MonitorPlay, placement: ['topbar', 'strip'], run: () => navigate({ suite: 'final' }) },   // D121: the Final level, a mode of its own
  { id: 'global.suite.catalogue', scope: 'global', label: UI2 ? 'Bin' : 'Catalogue', icon: Images, keys: 'Ctrl+4', placement: ['topbar'], run: () => (UI2 ? openLayer('bin') : void openTop('catalogue')) },   // D125: the fourth tab
  { id: 'global.ui2', scope: 'global', label: UI2 ? 'Back to the current UI' : 'Try the new UI', icon: Layers3, placement: ['topbar'], run: switchUi },   // U1 (D157): ☰
  { id: 'global.suite.models', scope: 'global', label: 'Models & engine…', icon: Boxes, placement: ['topbar'], run: () => s().openModels() },
  ...(['world', 'cast', 'flow', 'shots', 'episode'] as const).map((w, i) => ({   // D125: the rail's order (Props in Cast, the Catalogue a tab)
    id: `global.story.${w}`, scope: 'global' as const, label: `Story · ${w[0].toUpperCase()}${w.slice(1)}`, keys: `Alt+${i + 1}`, placement: ['rail'] as ['rail'],
    run: () => void openStory(w),
  })),
  // D71 (P15): quick actions — the empty states' cards, the app menu and the palette
  { id: 'global.project.new', scope: 'global', label: 'New project…', icon: FolderPlus, placement: ['topbar', 'toolbar'], run: () => s().setProjectDialog('new') },
  { id: 'global.project.open', scope: 'global', label: 'Open a project…', icon: FolderOpen, placement: ['topbar', 'toolbar'], run: () => s().setProjectDialog('open') },
  { id: 'global.start.generate', scope: 'global', label: 'Generate an image', icon: Sparkles, placement: ['toolbar'], when: () => !!s().project?.open,
    run: () => navigate({ suite: 'generate', tab: 'prompt' }) },
  { id: 'global.start.newDocument', scope: 'global', label: 'New document', icon: FilePlus, placement: ['toolbar', 'topbar'], when: () => !!s().project?.open,   // D95 (UX0 #3): also in ☰
    run: () => void openWith(null, { suite: 'edit' }).then(() => import('../suites/edit/editorStore')).then((m) => m.useEditor.getState().newDocument(1920, 1080)) },
  { id: 'global.start.animate', scope: 'global', label: 'Animate from an image', icon: Clapperboard, placement: ['toolbar'], when: () => !!s().project?.open,
    run: () => { navigate({ suite: 'catalogue' }); s().toast('Pick an image, then Animate ▾ under the loupe or in the Inspector (Shift+A), or drag it onto the Animate tab', 'info') } },
])
