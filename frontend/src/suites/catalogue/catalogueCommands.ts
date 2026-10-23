// Catalogue commands (08 §3/§6, 07 §3c): one definition each; the grid keys, the strip icons, the inspector verbs
// and the right-click menus (tile, grid, group header, loupe) all read from here. They act on whichever
// catalogue store instance is on screen (the Catalogue itself or Generate's results).
import { ArrowLeftRight, Wand2, Box, Clapperboard, ImageUp, ImagePlus, Inbox as InboxIcon, MapPin, Package, UserRound, ChevronLeft, Eraser, ImageUpscale, Orbit, ChevronRight, Columns2, Copy, Expand, GitBranch, ExternalLink, Film, FolderInput, FolderPlus, Image, Images, Inbox, Layers, ListTree, Pencil, Pin, PinOff, RotateCcw, Search, Shrink, Shuffle, SquareCheck, SquareX, Tag, Trash, Undo, Upload, X, ZoomIn, ZoomOut } from 'lucide-react'
import { ApiError, http, unwrap } from '../../api/client'
import { registerCommands, sep, type MenuItem } from '../../frame/commands'
import { openWith } from '../../frame/openWith'
import { revealPath } from '../../shell/tauri'
import { askConfirm, askText, useSession } from '../../store/session'
import { flatGroups, useAlbum } from './albumStore'
import { activeCatalogue } from './catalogueContext'
import { catView } from './viewKeys'
import { allPlaced } from './placement'
import type { JobOrigin } from '../../api/types'
import { originFor } from '../../store/origin'
import { selectedOrPrimary, useGenerateResults, type GroupMode } from './catalogueStore'
import { addToCastMenu, castTarget, madeFor } from '../story/addToCast'
import { profilesForMentions, useStory } from '../story/storyStore'

export const GROUP_MODES: [GroupMode, string][] = [['batch', 'Batch'], ['lineage', 'Lineage'], ['session', 'Session'], ['model', 'Model'], ['none', 'None']]

const cat = () => activeCatalogue.current.getState()
const ids = () => selectedOrPrimary(cat())
const primary = () => { const c = cat(); return c.primary ? c.byId(c.primary) : undefined }
const hasSel = () => ids().length > 0
const inTrash = () => cat().q.folder === 'trash'
const gen = () => import('../generate/generateStore').then((m) => m.useGenerate.getState())
const focusField = (id: string) => setTimeout(() => document.getElementById(id)?.focus(), 50)
/** D66: where a re-run / variations from the grid was asked for — Generate's results grid, or the Catalogue pane on screen (a group page
 *  names its group in `ref`; elsewhere `ref` is null and the payload keeps the folder, so "Go to origin" can return to it). */
const originHere = (): JobOrigin => {
  if (activeCatalogue.current === useGenerateResults) return originFor('generate', { suite: 'generate', surface: 'results' })   // D125 (I4): Image's For chip
  const q = cat().q
  return { suite: 'catalogue', surface: 'group', ref: q.group_id ?? null, payload: { folder: q.folder } }
}

registerCommands([
  { id: 'cat.selectAll', scope: 'catalogue', label: 'Select all', icon: SquareCheck, keys: 'Ctrl+A', placement: ['context', 'strip'], run: () => cat().selectAll() },
  { id: 'cat.clearSelection', scope: 'catalogue', label: 'Clear selection', icon: SquareX, keys: 'Escape', placement: ['context', 'strip'], when: hasSel, run: () => cat().clearSelection() },
  { id: 'cat.loupe', scope: 'catalogue', label: 'Open in loupe', icon: Image, keys: 'Enter', placement: ['context', 'inspector', 'strip'], when: () => !!cat().primary, run: () => cat().openLoupe(cat().primary) },
  { id: 'cat.edit', scope: 'catalogue', label: 'Open in Edit', icon: Pencil, keys: 'E', placement: ['context', 'inspector', 'strip'], when: () => !!cat().primary, run: () => { const id = cat().primary!; void import('../edit/editorStore').then((m) => m.useEditor.getState().openFromAsset(id)) } },
  { id: 'cat.tag', scope: 'catalogue', label: 'Tag…', icon: Tag, keys: 'T', placement: ['context', 'strip', 'inspector'], when: hasSel, run: () => { if (!useSession.getState().ui.inspectorOpen) useSession.getState().setUi({ inspectorOpen: true }); focusField('insp-tag') } },
  { id: 'cat.reference', scope: 'catalogue', label: 'Use as reference in Image', icon: Images, keys: 'R', placement: ['context', 'inspector', 'strip'], when: hasSel, run: () => { const list = ids(); void gen().then((g) => g.addRefs(list)) } },   // D90 (B12): up to the model's max_refs, one toast for the rest
  { id: 'cat.rerun', scope: 'catalogue', label: 'Re-run (same seed)', icon: RotateCcw, keys: 'Ctrl+R', placement: ['context', 'inspector'], when: () => !!primary()?.params?.recipe, run: () => { const a = primary(); const o = originHere(); if (a) void gen().then((g) => g.rerun(a, o)) } },
  { id: 'cat.variations', scope: 'catalogue', label: 'Variations (new seeds)', icon: Shuffle, keys: 'V', placement: ['context', 'inspector'], when: () => !!primary()?.params?.recipe, run: () => { const a = primary(); const o = originHere(); if (a) void gen().then((g) => g.variations(a, undefined, o)) } },
  // D90 (01 §11.2): the asset's prompt and parameters into Generate's panel (was an Inspector-only button)
  { id: 'cat.loadInGenerate', scope: 'catalogue', label: 'Load in Image', icon: Wand2, placement: ['context', 'inspector'], hint: 'this asset\'s prompt and parameters into Image\'s Make column panel', when: () => !!primary()?.params?.recipe,
    run: () => { const a = primary(); if (a) void gen().then((g) => { g.loadFromAsset(a, false); useSession.getState().setSuite('generate') }) } },
  { id: 'cat.pin', scope: 'catalogue', label: 'Pin for compare', icon: Pin, keys: 'C', placement: ['context', 'inspector', 'strip'], when: () => !!cat().primary, run: () => cat().togglePin(cat().primary!) },
  { id: 'cat.compare', scope: 'catalogue', label: 'Open compare', icon: Columns2, keys: 'Shift+C', placement: ['context', 'strip'], when: () => cat().compare.length >= 2, run: () => cat().setCompareOpen(true) },
  { id: 'cat.unpinAll', scope: 'catalogue', label: 'Unpin all', icon: PinOff, placement: ['context', 'strip'], when: () => cat().compare.length > 0, run: () => cat().clearCompare() },
  { id: 'cat.animate', scope: 'catalogue', label: 'Animate from this frame', icon: Film, keys: 'Shift+A', placement: ['context', 'inspector'], when: () => !!primary(), run: () => { const a = primary(); if (!a) return
      void import('../animate/animateStore').then((m) => { const an = m.useAnimate.getState(); const clipId = (a.params as { clip_id?: string }).clip_id
        if (a.kind === 'video' && clipId) { useSession.getState().setSuite('animate'); void an.loadClips().then(() => an.select(clipId)) } else an.setStart(a.id, true) }) } },
  { id: 'cat.animateEnd', scope: 'catalogue', label: 'Use as the end frame', icon: Film, hint: 'in Animate', keys: 'Shift+Z', placement: ['context', 'inspector'], when: () => !!primary() && primary()!.kind === 'image', run: () => { const a = primary(); if (a) void import('../animate/animateStore').then((m) => m.useAnimate.getState().setEnd(a.id, true)) } },
  { id: 'cat.reveal', scope: 'catalogue', label: 'Reveal in folder', icon: ExternalLink, keys: 'Ctrl+Shift+R', placement: ['context', 'inspector'], when: () => !!primary(), run: () => { const a = primary(); if (a) void revealPath(a.path) } },
  { id: 'cat.trash', scope: 'catalogue', label: 'Move to trash', icon: Trash, keys: 'Delete', alt: ['Backspace'], danger: true, placement: ['context', 'strip', 'inspector'], when: () => hasSel() && !inTrash(),
    run: () => void cat().trash(ids()) },                         // D90 (B5): the store's trash toasts once, with Undo, for every caller
  { id: 'cat.restore', scope: 'catalogue', label: 'Restore from trash', icon: Undo, placement: ['context', 'strip', 'inspector'], when: () => hasSel() && inTrash(), run: () => void cat().restore(ids()) },
  { id: 'cat.purge', scope: 'catalogue', label: 'Delete permanently…', icon: Trash, danger: true, placement: ['context', 'strip'], when: () => hasSel() && inTrash(), run: () => { const list = ids(); void askConfirm({ title: `Delete ${list.length} permanently?`, text: 'The files are removed from the project. This cannot be undone.', okLabel: 'Delete permanently', danger: true }).then((ok) => { if (ok) void cat().purge(list) }) } },
  // Empty trash: the strip's button is a two-step confirm (07 §1.5); from a menu or the palette it asks once (§10 finding 2)
  { id: 'cat.emptyTrash', scope: 'catalogue', label: 'Empty trash…', icon: Trash, danger: true, placement: ['panel', 'context', 'strip'], when: () => (cat().counts.trash ?? 0) > 0,
    run: () => { const c = cat(); const n = c.counts.trash ?? 0; void askConfirm({ title: `Empty the Trash?`, text: `${n} item${n === 1 ? ' is' : 's are'} deleted permanently: files, manifests and thumbnails. This cannot be undone.`, okLabel: 'Delete permanently', danger: true })
      .then((ok) => { if (ok) void c.emptyTrash().then((k) => useSession.getState().toast(`Trash emptied: ${k} item${k === 1 ? '' : 's'} deleted permanently`, 'success')) }) } },
  { id: 'cat.groupCycle', scope: 'catalogue', label: 'Cycle grouping', icon: ListTree, keys: 'G', placement: ['strip', 'context'], run: () => { const c = cat(); const i = GROUP_MODES.findIndex(([g]) => g === c.q.group); void c.setQuery({ group: GROUP_MODES[(i + 1) % GROUP_MODES.length][0] }) } },
  { id: 'cat.expandAll', scope: 'catalogue', label: 'Expand all groups', icon: Expand, placement: ['strip', 'context'], when: () => cat().q.group !== 'none', run: () => cat().expandAll(true) },
  { id: 'cat.collapseAll', scope: 'catalogue', label: 'Collapse all groups', icon: Shrink, placement: ['strip', 'context'], when: () => cat().q.group !== 'none', run: () => cat().expandAll(false) },
  { id: 'cat.tileSmaller', scope: 'catalogue', label: 'Smaller tiles', icon: ZoomOut, keys: '[', placement: ['strip'], run: () => cat().setTile(cat().tile - 32) },
  { id: 'cat.tileLarger', scope: 'catalogue', label: 'Larger tiles', icon: ZoomIn, keys: ']', placement: ['strip'], run: () => cat().setTile(cat().tile + 32) },
  { id: 'cat.search', scope: 'catalogue', label: 'Search', icon: Search, keys: 'F', placement: ['strip', 'context'], run: () => focusField('cat-search') },
  // D34: duplicates, batches, Unprocessed (proto01_design/01 §3 B5, B8, A19)
  { id: 'cat.duplicate', scope: 'catalogue', label: 'Duplicate', icon: Copy, keys: 'Ctrl+D', placement: ['context', 'inspector'], when: hasSel,
    run: () => { const list = ids(); void useAlbum.getState().duplicateAssets(list).then((n) => useSession.getState().toast(`Duplicated ${n.length} item${n.length === 1 ? '' : 's'}`, 'success')) } },
  { id: 'cat.showBatch', scope: 'catalogue', label: 'Show this batch', icon: Layers, placement: ['context'], when: () => !!primary()?.batch_id,
    run: () => { const a = primary(); if (a?.batch_id) void cat().setQuery({ batch_id: a.batch_id, batch_label: new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }) } },
  { id: 'cat.toUnprocessed', scope: 'catalogue', label: 'Back to Unprocessed', icon: Inbox, keys: 'Shift+Delete', placement: ['context', 'inspector'], when: () => allPlaced(ids(), cat().q),   // D90 (B17): every selected asset is placed, not only on a group page
    run: () => void useAlbum.getState().move(ids().map((id) => ({ kind: 'asset' as const, id })), null) },
  { id: 'cat.import', scope: 'catalogue', label: 'Import…', icon: Upload, placement: ['strip', 'context'], run: () => void import('./CatalogueStrip').then((m) => m.importInteractive(cat(), 'files')) },
  { id: 'cat.prev', scope: 'catalogue', label: 'Previous image', icon: ChevronLeft, keys: 'ArrowLeft', placement: ['strip', 'context'], when: () => loupeIndex() > 0, run: () => { const c = cat(); c.openLoupe(c.visibleOrder()[loupeIndex() - 1]) } },
  { id: 'cat.next', scope: 'catalogue', label: 'Next image', icon: ChevronRight, keys: 'ArrowRight', placement: ['strip', 'context'], when: () => { const i = loupeIndex(); return i >= 0 && i < cat().visibleOrder().length - 1 }, run: () => { const c = cat(); c.openLoupe(c.visibleOrder()[loupeIndex() + 1]) } },
  { id: 'cat.closeLoupe', scope: 'catalogue', label: 'Back (Esc)', icon: X, placement: ['strip', 'context'], when: () => !!cat().loupe || cat().compareOpen || !!cat().lineage, run: () => { const c = cat(); if (c.loupe) c.openLoupe(null); else if (c.lineage) c.openLineage(null); else c.setCompareOpen(false) } },
  // D71 (P15): "Start from this image" — Edit with the right AI tool already chosen
  { id: 'cat.start.removeBg', scope: 'catalogue', label: 'Select subject…', icon: Eraser, hint: 'opens Edit with AI Select · Subject (it selects; Inpaint or a mask does the rest)', placement: ['inspector', 'context'], when: () => !!primary() && primary()!.kind === 'image',
    run: () => { const a = primary(); if (a) void openWith(a.id, { suite: 'edit', aiOp: 'select', selMode: 'subject' }) } },
  { id: 'cat.start.upscale', scope: 'catalogue', label: 'Upscale in Edit…', icon: ImageUpscale, placement: ['inspector', 'context'], when: () => !!primary() && primary()!.kind === 'image',
    run: () => { const a = primary(); if (a) void openWith(a.id, { suite: 'edit', aiOp: 'upscale' }) } },
  // P14 (D82): a new viewpoint of the image — Generate's Angle tab with this asset as the source
  { id: 'cat.start.angle', scope: 'catalogue', label: 'New angle…', icon: Orbit, placement: ['inspector', 'context', 'toolbar'], when: () => !!primary() && primary()!.kind === 'image',
    run: () => { const a = primary(); if (a) void openWith(a.id, { suite: 'generate', slot: 'angle' }) } },
  // 17 SY2 (D85): a clip's tile → a Story shot with the clip
  { id: 'cat.start.shot', scope: 'catalogue', label: 'Make a shot from this clip…', icon: Clapperboard, placement: ['inspector', 'context'],
    when: () => { const a = primary(); return !!a && a.kind === 'video' && !!(a.params as { clip_id?: string }).clip_id },
    run: () => { const a = primary(); const cid = (a?.params as { clip_id?: string } | undefined)?.clip_id; if (!a || !cid) return
      void askText({ title: 'Make a shot from this clip', text: 'A Story shot with this clip as its clip.', initial: (a.prompt_text || 'Shot').split(/[,.]/)[0].slice(0, 40), placeholder: 'shot name' })
        .then((n) => { if (n?.trim()) void import('../story/storyStore').then((m) => m.makeShotAndOpen(n.trim(), { clip_id: cid })) }) } },
  // 17 SY1 (D85): the image becomes the hero of a new Story profile (its reference set a group with the image as cover); Story opens on it
  ...(['character', 'place', 'prop'] as const).map((cls) => ({
    id: `cat.start.${cls}`, scope: 'catalogue' as const, label: `Make a ${cls}…`, icon: cls === 'character' ? UserRound : cls === 'place' ? MapPin : Package, placement: ['inspector', 'context'] as ['inspector', 'context'],
    when: () => !!primary() && primary()!.kind === 'image',
    run: () => { const a = primary(); if (!a) return
      void askText({ title: `Make a ${cls} from this image`, text: 'The image moves onto a new reference page as the hero and cover; @name mentions it in prompts; Expand fills the coverage grid from it.', placeholder: `${cls} name` })
        .then(async (name) => {
          if (!name?.trim()) return
          const [m, reg] = await Promise.all([import('../story/storyStore'), import('../../frame/suiteRegistry')])
          const p = await m.useStory.getState().createProfile(name.trim(), cls, a.id)
          if (p) { reg.setRailTab('story', m.tabOfClass(cls)); useSession.getState().setSuite('story') }   // D110: a prop opens on Props
        }) },
  })),
  // D93 (A2): "Add to character ▸" — the selection into a Cast profile's current version (the menu entry names the profile: castTarget)
  ...([['hero', 'as the hero', ImageUp], ['reference', 'into the reference set', ImagePlus], ['candidate', 'as a candidate', InboxIcon]] as const).map(([role, how, icon]) => ({
    id: `cat.addTo.${role}`, scope: 'catalogue' as const, label: `Add to character ${how}`, icon, placement: ['context', 'inspector'] as ['context', 'inspector'],
    hint: role === 'hero' ? 'it joins the reference set as its cover' : role === 'candidate' ? 'onto the version\'s candidates page' : 'moved from Unprocessed or its candidates, copied from any other page',
    when: () => { const p = castTarget.pid ? useStory.getState().profiles.find((x) => x.id === castTarget.pid) : undefined
      const imgs = ids().filter((i) => cat().byId(i)?.kind === 'image')
      return !!p && p.versions.find((v) => v.id === p.current)?.state === 'open' && imgs.length > 0 && imgs.length === ids().length && (role !== 'hero' || imgs.length === 1) && !inTrash() },
    run: () => { const pid = castTarget.pid; const list = ids(); if (pid) void useStory.getState().addToProfile(pid, list, role) },
  })),
  // P18 (D84): a 3D prop from the image — Pixal3D as a background job, its cost said before it is queued; the mesh lands in the Catalogue
  { id: 'cat.start.mesh', scope: 'catalogue', label: 'Make a 3D prop…', icon: Box, placement: ['inspector', 'context'],
    when: () => !!primary() && primary()!.kind === 'image' && !!useSession.getState().capabilities?.mesh?.model_id,
    run: () => {
      const a = primary(); const mc = useSession.getState().capabilities?.mesh
      if (!a || !mc?.model_id) return
      const mins = (s: number | null | undefined) => (s ? `${Math.round(s / 60)} min` : '?')
      void askConfirm({ title: 'Make a 3D prop from this image?', okLabel: 'Queue it',
        text: `${mc.label} cuts the object out and builds a textured GLB (${mc.resolutions[0]}, ${Math.round(mc.faces / 1000)}k faces). About ${mins(mc.seconds)} with the model loaded, ${mins(mc.cold_seconds)} from cold, on this card${mc.health === 'missing' ? ' — its weights are missing (Models › Fetch)' : ''}. It runs in the background; the prop lands here and in the Stage library.` })
        .then(async (ok) => {
          if (!ok) return
          const s = useSession.getState()
          try {
            await unwrap(http.POST('/jobs', { body: { recipe: { kind: 'image_to_mesh', asset_id: a.id } as never, stage: false, origin: { suite: 'catalogue', surface: 'mesh', ref: a.id } } }))
            s.toast(`Queued a 3D prop from ${a.id} (${mins(mc.seconds)})`, 'success')
          } catch (e) { s.toast(`Make a 3D prop failed: ${(e as ApiError).detail ?? e}`, 'error') }
        })
    } },
  // D72: the loupe's and compare's own keys, now remappable (the buttons in their bars are these commands)
  { id: 'cat.loupe.fit', scope: 'catalogue', label: 'Fit to view', keys: 'Ctrl+0', placement: ['toolbar'], when: () => !!catView.fit, run: () => catView.fit?.() },
  { id: 'cat.loupe.one', scope: 'catalogue', label: 'Actual pixels (1:1)', keys: 'Ctrl+Alt+0', placement: ['toolbar'], when: () => !!catView.one, run: () => catView.one?.() },
  { id: 'cat.compare.swap', scope: 'catalogue', label: 'Swap the compared images', icon: ArrowLeftRight, keys: 'Tab', placement: ['toolbar'], when: () => !!catView.swap, run: () => catView.swap?.() },
  { id: 'cat.lineage', scope: 'catalogue', label: 'Show lineage', icon: GitBranch, keys: 'L', placement: ['context', 'inspector'], when: () => !!cat().primary, run: () => cat().openLineage(cat().primary) },
])
function loupeIndex(): number { const c = cat(); return c.loupe ? c.visibleOrder().indexOf(c.loupe) : -1 }

export const groupMenu = (): MenuItem => ({ label: 'Group by', icon: ListTree, items: [...GROUP_MODES.map(([g, l]): MenuItem => ({ label: l, checked: cat().q.group === g, run: () => void cat().setQuery({ group: g }) })), sep, { cmd: 'cat.groupCycle' }] })   // D90 (C20): G's mouse home

/** "Move to group ▸": every group of the Album, plus a new one (D34). */
export function moveToMenu(): MenuItem {
  const al = useAlbum.getState()
  const list = () => ids().map((id) => ({ kind: 'asset' as const, id }))
  const here = cat().q.group_id
  return { label: 'Move to group', icon: FolderInput, items: [
    { label: 'New group…', icon: FolderPlus, run: () => { const items = list(); void askText({ title: 'New group', text: `${items.length} item${items.length === 1 ? '' : 's'} move onto it.`, placeholder: 'group name' }).then((n) => { if (n?.trim()) void al.create(n.trim()).then((gid) => al.move(items, gid)) }) } },
    ...(al.tree ? [sep, { label: 'Album page', run: () => void al.move(list(), al.tree!.id), disabled: here === al.tree.id }] : []),
    ...flatGroups(al.tree).map(({ node, depth }) => ({ label: `${' '.repeat(depth)}${node.name}`, disabled: here === node.id, run: () => void al.move(list(), node.id) })),
  ] }
}

/** D93 (A2): "Add to character ▸" for the selection — the profiles the primary was made for first (its recipe's profile mentions). */
export const addToCharacterMenu = () => addToCastMenu(profilesForMentions(), madeFor(primary()))

/** D90 (01 §11.4): a clip's tile — Make a shot sits at the menu's top level and the image starts are left out. */
const clipTile = () => primary()?.kind === 'video'
/** Right-click on a tile (the tile has been made primary / selected by the caller). */
export function tileMenu(): MenuItem[] {
  return [
    { cmd: 'cat.loupe' }, { cmd: 'cat.edit' }, sep,
    moveToMenu(), { cmd: 'cat.toUnprocessed' }, { cmd: 'cat.duplicate' }, { cmd: 'cat.showBatch' }, { cmd: 'cat.lineage' }, sep,
    { cmd: 'cat.tag' }, sep,
    { cmd: 'cat.reference' }, { cmd: 'cat.loadInGenerate' }, { cmd: 'cat.rerun' }, { cmd: 'cat.variations' }, { cmd: 'cat.animate' }, { cmd: 'cat.animateEnd' }, ...(clipTile() ? [{ cmd: 'cat.start.shot' }] : []), sep,
    ...(clipTile() || inTrash() ? [] : [addToCharacterMenu()]),
    ...(clipTile() ? [] : [{ label: 'Start from this image', icon: Image, items: [{ cmd: 'cat.start.removeBg' }, { cmd: 'cat.start.upscale' }, { cmd: 'cat.start.angle' }, { cmd: 'cat.start.mesh' }, sep, { cmd: 'cat.start.character' }, { cmd: 'cat.start.place' }, { cmd: 'cat.start.prop' }] } as MenuItem, sep]),
    { cmd: 'cat.pin', label: cat().primary && cat().compare.includes(cat().primary!) ? 'Unpin' : 'Pin for compare' }, { cmd: 'cat.compare' }, sep,
    { cmd: 'cat.reveal' }, sep,
    ...(inTrash() ? [{ cmd: 'cat.restore' }, { cmd: 'cat.purge' }, { cmd: 'cat.emptyTrash' }] : [{ cmd: 'cat.trash' }]),
  ]
}
/** Right-click on empty grid space. */
export function gridMenu(): MenuItem[] {
  const grouped = cat().q.group !== 'none'                         // Generate's results still group by batch (§9)
  return [{ cmd: 'cat.import' }, sep, { cmd: 'cat.selectAll' }, { cmd: 'cat.clearSelection' }, sep, groupMenu(), ...(grouped ? [{ cmd: 'cat.expandAll' }, { cmd: 'cat.collapseAll' }] : []), sep, { cmd: 'cat.search' }, { cmd: 'cat.unpinAll' }]   // D90 (C20): grouping is reachable by mouse, not only by G
}
/** Right-click on a group header. */
export function headerMenu(key: string): MenuItem[] {
  const c = cat()
  return [{ label: c.expanded[key] ? 'Collapse group' : 'Expand group', icon: c.expanded[key] ? Shrink : Expand, run: () => c.toggleGroup(key) }, { cmd: 'cat.expandAll' }, { cmd: 'cat.collapseAll' }, sep, groupMenu()]
}
