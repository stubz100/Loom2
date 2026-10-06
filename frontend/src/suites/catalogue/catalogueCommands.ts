// Catalogue commands (08 §3/§6, 07 §3c): one definition each; the grid keys, the strip icons, the inspector verbs
// and the right-click menus (tile, grid, group header, loupe) all read from here. They act on whichever
// catalogue store instance is on screen (the Catalogue itself or Generate's results).
import { Check, ChevronLeft, ChevronRight, Circle, Columns2, Expand, ExternalLink, Film, Image, Images, ListTree, Pencil, Pin, PinOff, RotateCcw, Search, Shrink, Shuffle, SquareCheck, SquareX, Star, Tag, Trash, Undo, X, ZoomIn, ZoomOut } from 'lucide-react'
import { registerCommands, sep, type MenuItem } from '../../frame/commands'
import { setRailTab } from '../../frame/suiteRegistry'
import { revealPath } from '../../shell/tauri'
import { askConfirm, useSession } from '../../store/session'
import { activeCatalogue } from './catalogueContext'
import { selectedOrPrimary, type GroupMode } from './catalogueStore'

export const GROUP_MODES: [GroupMode, string][] = [['batch', 'Batch'], ['lineage', 'Lineage'], ['session', 'Session'], ['model', 'Model'], ['none', 'None']]

const cat = () => activeCatalogue.current.getState()
const ids = () => selectedOrPrimary(cat())
const primary = () => { const c = cat(); return c.primary ? c.byId(c.primary) : undefined }
const hasSel = () => ids().length > 0
const inTrash = () => cat().q.folder === 'trash'
const gen = () => import('../generate/generateStore').then((m) => m.useGenerate.getState())
const focusField = (id: string) => setTimeout(() => document.getElementById(id)?.focus(), 50)

registerCommands([
  { id: 'cat.selectAll', scope: 'catalogue', label: 'Select all', icon: SquareCheck, keys: 'Ctrl+A', placement: ['context', 'strip'], run: () => cat().selectAll() },
  { id: 'cat.clearSelection', scope: 'catalogue', label: 'Clear selection', icon: SquareX, keys: 'Escape', placement: ['context', 'strip'], when: hasSel, run: () => cat().clearSelection() },
  { id: 'cat.loupe', scope: 'catalogue', label: 'Open in loupe', icon: Image, keys: 'Enter', placement: ['context', 'inspector', 'strip'], when: () => !!cat().primary, run: () => cat().openLoupe(cat().primary) },
  { id: 'cat.edit', scope: 'catalogue', label: 'Open in Edit', icon: Pencil, keys: 'E', placement: ['context', 'inspector', 'strip'], when: () => !!cat().primary, run: () => { const id = cat().primary!; void import('../edit/editorStore').then((m) => m.useEditor.getState().openFromAsset(id)) } },
  { id: 'cat.keep', scope: 'catalogue', label: 'Keep', icon: Check, keys: 'K', placement: ['context', 'strip', 'inspector'], when: hasSel, run: () => void cat().setState(ids(), 'keep') },
  { id: 'cat.reject', scope: 'catalogue', label: 'Reject', icon: X, keys: 'X', placement: ['context', 'strip', 'inspector'], when: hasSel, run: () => void cat().setState(ids(), 'reject') },
  { id: 'cat.unstate', scope: 'catalogue', label: 'Clear keep / reject', icon: Circle, keys: 'U', placement: ['context', 'strip', 'inspector'], when: hasSel, run: () => void cat().setState(ids(), 'none') },
  ...[0, 1, 2, 3, 4, 5].map((n) => ({ id: `cat.rate.${n}`, scope: 'catalogue' as const, label: n ? `Rate ${'★'.repeat(n)}` : 'Remove rating', icon: Star, keys: String(n), placement: ['context', 'inspector'] as ['context', 'inspector'], when: hasSel, run: () => void cat().setRating(ids(), n) })),
  { id: 'cat.tag', scope: 'catalogue', label: 'Tag…', icon: Tag, keys: 'T', placement: ['context', 'strip', 'inspector'], when: hasSel, run: () => { if (!useSession.getState().ui.inspectorOpen) useSession.getState().setUi({ inspectorOpen: true }); focusField('insp-tag') } },
  { id: 'cat.reference', scope: 'catalogue', label: 'Use as reference in Generate', icon: Images, keys: 'R', placement: ['context', 'inspector', 'strip'], when: hasSel, run: () => { const list = ids(); void gen().then((g) => list.forEach((id) => g.addRef(id))) } },
  { id: 'cat.rerun', scope: 'catalogue', label: 'Re-run (same seed)', icon: RotateCcw, keys: 'Ctrl+R', placement: ['context', 'inspector'], when: () => !!primary()?.params?.recipe, run: () => { const a = primary(); if (a) void gen().then((g) => g.rerun(a)) } },
  { id: 'cat.variations', scope: 'catalogue', label: 'Variations (new seeds)', icon: Shuffle, keys: 'V', placement: ['context', 'inspector'], when: () => !!primary()?.params?.recipe, run: () => { const a = primary(); if (a) void gen().then((g) => g.variations(a)) } },
  { id: 'cat.pin', scope: 'catalogue', label: 'Pin for compare', icon: Pin, keys: 'C', placement: ['context', 'inspector', 'strip'], when: () => !!cat().primary, run: () => cat().togglePin(cat().primary!) },
  { id: 'cat.compare', scope: 'catalogue', label: 'Open compare', icon: Columns2, keys: 'Shift+C', placement: ['context', 'strip'], when: () => cat().compare.length >= 2, run: () => cat().setCompareOpen(true) },
  { id: 'cat.unpinAll', scope: 'catalogue', label: 'Unpin all', icon: PinOff, placement: ['context', 'strip'], when: () => cat().compare.length > 0, run: () => cat().clearCompare() },
  { id: 'cat.animate', scope: 'catalogue', label: 'Animate from this frame (start)', icon: Film, keys: 'Shift+A', placement: ['context', 'inspector', 'strip'], when: () => !!primary(), run: () => { const a = primary(); if (!a) return
      void import('../animate/animateStore').then((m) => { const an = m.useAnimate.getState(); const clipId = (a.params as { clip_id?: string }).clip_id
        if (a.kind === 'video' && clipId) { useSession.getState().setSuite('animate'); void an.loadClips().then(() => an.select(clipId)) } else an.setStart(a.id, true) }) } },
  { id: 'cat.animateEnd', scope: 'catalogue', label: 'Use as the end frame in Animate', icon: Film, keys: 'Shift+Z', placement: ['context', 'inspector'], when: () => !!primary() && primary()!.kind !== 'video', run: () => { const a = primary(); if (a) void import('../animate/animateStore').then((m) => m.useAnimate.getState().setEnd(a.id, true)) } },
  { id: 'cat.reveal', scope: 'catalogue', label: 'Reveal in folder', icon: ExternalLink, keys: 'Ctrl+Shift+R', placement: ['context', 'inspector'], when: () => !!primary(), run: () => { const a = primary(); if (a) void revealPath(a.path) } },
  { id: 'cat.trash', scope: 'catalogue', label: 'Move to trash', icon: Trash, keys: 'Delete', alt: ['Backspace'], danger: true, placement: ['context', 'strip', 'inspector'], when: () => hasSel() && !inTrash(),
    run: () => { const list = ids(); const c = cat(); void c.trash(list).then(() => useSession.getState().toast(`Moved ${list.length} to trash`, 'info', () => void c.restore(list))) } },
  { id: 'cat.restore', scope: 'catalogue', label: 'Restore from trash', icon: Undo, placement: ['context', 'strip', 'inspector'], when: () => hasSel() && inTrash(), run: () => void cat().restore(ids()) },
  { id: 'cat.purge', scope: 'catalogue', label: 'Delete permanently…', icon: Trash, danger: true, placement: ['context', 'strip'], when: () => hasSel() && inTrash(), run: () => { const list = ids(); void askConfirm({ title: `Delete ${list.length} permanently?`, text: 'The files are removed from the project. This cannot be undone.', okLabel: 'Delete permanently', danger: true }).then((ok) => { if (ok) void cat().purge(list) }) } },
  // Empty trash: the button in the Library panel / strip is a two-step confirm (07 §1.5); this entry arms it from menus and the palette
  { id: 'cat.emptyTrash', scope: 'catalogue', label: 'Empty trash…', icon: Trash, danger: true, placement: ['panel', 'context', 'strip'], when: () => inTrash() && (cat().total ?? 0) > 0,
    run: () => { const c = cat(); const n = c.total ?? 0; useSession.getState().toast(`Permanently delete all ${n} trashed items? Use the Empty trash button (click it twice) in the Library panel or the strip.`, 'info') } },
  { id: 'cat.groupCycle', scope: 'catalogue', label: 'Cycle grouping', icon: ListTree, keys: 'G', placement: ['strip', 'context'], run: () => { const c = cat(); const i = GROUP_MODES.findIndex(([g]) => g === c.q.group); void c.setQuery({ group: GROUP_MODES[(i + 1) % GROUP_MODES.length][0] }) } },
  { id: 'cat.expandAll', scope: 'catalogue', label: 'Expand all groups', icon: Expand, placement: ['strip', 'context'], when: () => cat().q.group !== 'none', run: () => cat().expandAll(true) },
  { id: 'cat.collapseAll', scope: 'catalogue', label: 'Collapse all groups', icon: Shrink, placement: ['strip', 'context'], when: () => cat().q.group !== 'none', run: () => cat().expandAll(false) },
  { id: 'cat.tileSmaller', scope: 'catalogue', label: 'Smaller tiles', icon: ZoomOut, keys: '[', placement: ['strip'], run: () => cat().setTile(cat().tile - 32) },
  { id: 'cat.tileLarger', scope: 'catalogue', label: 'Larger tiles', icon: ZoomIn, keys: ']', placement: ['strip'], run: () => cat().setTile(cat().tile + 32) },
  { id: 'cat.search', scope: 'catalogue', label: 'Search and filters', icon: Search, keys: 'F', placement: ['panel', 'context'], run: () => { setRailTab('catalogue', 'filters'); useSession.getState().setUi({ panelOpen: true }); focusField('cat-search') } },
  { id: 'cat.prev', scope: 'catalogue', label: 'Previous image', icon: ChevronLeft, keys: 'ArrowLeft', placement: ['strip', 'context'], when: () => loupeIndex() > 0, run: () => { const c = cat(); c.openLoupe(c.visibleOrder()[loupeIndex() - 1]) } },
  { id: 'cat.next', scope: 'catalogue', label: 'Next image', icon: ChevronRight, keys: 'ArrowRight', placement: ['strip', 'context'], when: () => { const i = loupeIndex(); return i >= 0 && i < cat().visibleOrder().length - 1 }, run: () => { const c = cat(); c.openLoupe(c.visibleOrder()[loupeIndex() + 1]) } },
  { id: 'cat.closeLoupe', scope: 'catalogue', label: 'Close loupe / compare', icon: X, placement: ['strip', 'context'], when: () => !!cat().loupe || cat().compareOpen, run: () => { const c = cat(); if (c.loupe) c.openLoupe(null); else c.setCompareOpen(false) } },
])
function loupeIndex(): number { const c = cat(); return c.loupe ? c.visibleOrder().indexOf(c.loupe) : -1 }

export const rateMenu = (): MenuItem => ({ label: 'Rate', icon: Star, items: [5, 4, 3, 2, 1, 0].map((n) => ({ cmd: `cat.rate.${n}` })) })
export const groupMenu = (): MenuItem => ({ label: 'Group by', icon: ListTree, items: GROUP_MODES.map(([g, l]) => ({ label: l, checked: cat().q.group === g, run: () => void cat().setQuery({ group: g }) })) })

/** Right-click on a tile (the tile has been made primary / selected by the caller). */
export function tileMenu(): MenuItem[] {
  return [
    { cmd: 'cat.loupe' }, { cmd: 'cat.edit' }, sep,
    { cmd: 'cat.keep' }, { cmd: 'cat.reject' }, { cmd: 'cat.unstate' }, rateMenu(), { cmd: 'cat.tag' }, sep,
    { cmd: 'cat.reference' }, { cmd: 'cat.rerun' }, { cmd: 'cat.variations' }, { cmd: 'cat.animate' }, { cmd: 'cat.animateEnd' }, sep,
    { cmd: 'cat.pin', label: cat().primary && cat().compare.includes(cat().primary!) ? 'Unpin from compare' : 'Pin for compare' }, { cmd: 'cat.compare' }, sep,
    { cmd: 'cat.reveal' }, sep,
    ...(inTrash() ? [{ cmd: 'cat.restore' }, { cmd: 'cat.purge' }, { cmd: 'cat.emptyTrash' }] : [{ cmd: 'cat.trash' }]),
  ]
}
/** Right-click on empty grid space. */
export function gridMenu(): MenuItem[] {
  return [{ cmd: 'cat.selectAll' }, { cmd: 'cat.clearSelection' }, sep, groupMenu(), { cmd: 'cat.expandAll' }, { cmd: 'cat.collapseAll' }, sep, { cmd: 'cat.search' }, { cmd: 'cat.unpinAll' }]
}
/** Right-click on a group header. */
export function headerMenu(key: string): MenuItem[] {
  const c = cat()
  return [{ label: c.expanded[key] ? 'Collapse group' : 'Expand group', icon: c.expanded[key] ? Shrink : Expand, run: () => c.toggleGroup(key) }, { cmd: 'cat.expandAll' }, { cmd: 'cat.collapseAll' }, sep, groupMenu()]
}
