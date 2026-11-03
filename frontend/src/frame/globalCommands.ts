// Global commands (07 §4): the dock, settings, help, the command palette. The layer tabs (Ctrl+1–5) are registered here so the help
// overlay lists them.
import { Boxes, Clapperboard, FilePlus, Images, Menu, FolderOpen, FolderPlus, Info, Keyboard, LayoutGrid, NotebookPen, PanelBottom, RefreshCw, Settings, Shapes } from 'lucide-react'
const CircleHelp = Info
import { askText, useSession } from '../store/session'
import { registerCommands } from './commands'
import { openWith } from './openWith'
import { usePalette } from './CommandPalette'
import { navigate, type Layer } from './router'
import { useLayer } from '../ui2/layers'

const s = () => useSession.getState()
/** U1 (D157): the four tabs and Ctrl+1–4 are the shell's layers. B2 (D159): the ids are the old tabs' (Story · Image · Animate · Catalogue),
 *  so a key remapped under them stays. */
const openLayer = (l: Layer) => useLayer.getState().setLayer(l)

registerCommands([
  { id: 'global.palette', scope: 'global', label: 'Command palette', icon: Keyboard, keys: 'Ctrl+K', placement: ['topbar'], run: () => usePalette.getState().toggle() },
  { id: 'global.contextMenu', scope: 'global', label: 'Open the menu of the focused item', icon: Menu, keys: 'Shift+F10', alt: ['ContextMenu'], placement: ['context'],
    hint: 'a right-click does the same', run: () => void import('./useKeyboardMap').then((m) => m.openContextMenuAtFocus()) },   // D72: was a key in useKeyboardMap only
  { id: 'global.help', scope: 'global', label: 'Keyboard map and commands', icon: CircleHelp, keys: '?', placement: ['topbar'], run: () => s().setHelp(!s().helpOpen) },
  { id: 'global.settings', scope: 'global', label: 'Settings…', icon: Settings, keys: 'Ctrl+,', placement: ['rail', 'topbar'], run: () => s().openSettings(true) },
  { id: 'global.dock', scope: 'global', label: 'Toggle dock', icon: PanelBottom, keys: '`', placement: ['topbar', 'dock'], run: () => s().setUi({ dockOpen: !s().ui.dockOpen }) },
  { id: 'global.density', scope: 'global', label: 'Toggle density', icon: LayoutGrid, placement: ['topbar'], run: () => s().setUi({ density: s().ui.density === 'compact' ? 'comfortable' : 'compact' }) },
  { id: 'global.refresh', scope: 'global', label: 'Refresh state', icon: RefreshCw, placement: ['topbar'], run: () => void s().refreshAll() },
  // U1 (D157): the layers, keyed Ctrl+1–4 in their order; Models & engine is a sheet in ☰
  { id: 'global.suite.story', scope: 'global', label: 'World', keys: 'Ctrl+1', placement: ['topbar'], run: () => openLayer('world') },
  { id: 'global.suite.clay', scope: 'global', label: 'Clay', icon: Shapes, keys: 'Ctrl+2', placement: ['topbar'], run: () => openLayer('clay') },   // C0 (D181)
  { id: 'global.suite.image', scope: 'global', label: 'Shots', keys: 'Ctrl+3', placement: ['topbar'], run: () => openLayer('shots') },
  { id: 'global.suite.animate', scope: 'global', label: 'Episode', keys: 'Ctrl+4', placement: ['topbar'], run: () => openLayer('episode') },
  { id: 'global.suite.catalogue', scope: 'global', label: 'Bin', icon: Images, keys: 'Ctrl+5', placement: ['topbar'], run: () => openLayer('bin') },
  { id: 'global.suite.stage', scope: 'global', label: 'Clay · the scene', icon: Shapes, placement: ['toolbar'], run: () => navigate({ suite: 'stage' }) },   // From a stage's *Edit the stage*: Clay's Scenes
  { id: 'global.suite.models', scope: 'global', label: 'Models & engine…', icon: Boxes, placement: ['topbar'], run: () => s().openModels() },
  // D71 (P15): quick actions — the empty states' cards, the app menu and the palette
  { id: 'global.project.new', scope: 'global', label: 'New project…', icon: FolderPlus, placement: ['topbar', 'toolbar'], run: () => s().setProjectDialog('new') },
  { id: 'global.project.notes', scope: 'global', label: 'Notes…', icon: NotebookPen, placement: ['topbar'], when: () => !!s().project?.open,   // W2 (D157 Q1): the synopsis
    hint: "the project's synopsis — the story in a few paragraphs, for you (no picture reads it)",
    run: () => void import('../suites/story/storyStore').then(async ({ useStory }) => {
      const st = useStory.getState()
      if (!st.world) await st.load()
      const w = useStory.getState().world
      if (!w) return
      const text = await askText({ title: 'Notes · the synopsis', initial: w.synopsis, multiline: true, allowEmpty: true, okLabel: 'Keep',
        placeholder: 'The story in a few paragraphs — who, what they want, what stands in the way, how it ends' })
      if (text === null || text === w.synopsis) return
      useStory.getState().edit({ synopsis: text })
      await useStory.getState().flush()
    }) },
  { id: 'global.project.open', scope: 'global', label: 'Open a project…', icon: FolderOpen, placement: ['topbar', 'toolbar'], run: () => s().setProjectDialog('open') },
  { id: 'global.start.newDocument', scope: 'global', label: 'New document', icon: FilePlus, placement: ['toolbar', 'topbar'], when: () => !!s().project?.open,   // D95 (UX0 #3): also in ☰
    run: () => void openWith(null, { suite: 'edit' }).then(() => import('../suites/edit/editorStore')).then((m) => m.useEditor.getState().newDocument(1920, 1080)) },
  { id: 'global.start.animate', scope: 'global', label: 'Animate from an image', icon: Clapperboard, placement: ['toolbar'], when: () => !!s().project?.open,
    run: () => { openLayer('bin'); s().toast('Pick a still, then Set as the start frame in its right-click menu', 'info') } },
])
