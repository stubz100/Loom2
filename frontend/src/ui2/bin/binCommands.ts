// U8 (D157, proto01_UI2 05 §2.2): the Bin's verbs (rule 3: commands with a mouse home — the Inspector, a tile's right-click, the grid's
// head). The Bin makes nothing: it opens a thing where it belongs, moves it to another home, tags it, trashes or restores it.
// B0 (D159 Q5): a move that would take a thing's role away asks first, naming the role; a home whose record was deleted gives its things
// to the Sketches. B1 (D159, 11 §3): the scope `bin`, every verb on the selection (one thing or many): duplicate, reveal, Delete
// permanently…, Empty trash…, Select all, compare (two to four pinned), the tile size, Import… into the open home, the large view's Fit,
// 1:1, previous and next, Re-run and Variations landing beside the thing, a picture made into a World entity. The grid's key hook answers
// the keys shown (handleKeyFor('bin')). B2a (D159, 11 §7): the quick starts on a picture — Open in Edit, Select subject…, Upscale…, New
// angle…, Make a 3D prop… — and Add to World ▸ (the things named go into an entity's version as the hero, a reference or a candidate).
import { ArrowLeftRight, ArrowUpRight, Box, ChevronLeft, ChevronRight, Columns2, Copy, Eraser, ExternalLink, FolderInput, FolderOpen, FolderOutput, ImagePlus, ImageUp,
  FolderPlus, ImageUpscale, Inbox, Maximize2, Orbit, Pencil, PencilLine, Pin, PinOff, RotateCcw, Shuffle, SquareCheck, SquareX, Tag, Trash, Trash2, Undo, Upload, ZoomIn, ZoomOut } from 'lucide-react'
import { http, unwrap } from '../../api/client'
import type { BinNode, BinThing } from '../../api/types'
import { showMenu } from '../../frame/ContextMenu'
import { registerCommands, setReach, type MenuItem } from '../../frame/commands'
import { openDetached } from '../../frame/loupeLink'
import { navigate } from '../../frame/router'
import { isTauri, pickFiles, revealPath } from '../../shell/tauri'
import { askConfirm, askText, useSession } from '../../store/session'
import { castTarget } from '../../suites/story/addToCast'
import { useStory } from '../../suites/story/storyStore'
import type { OpenWith } from '../../frame/openWith'
import { HEADINGS, homesById, pathLabel, ROLE_WORDS, selectedThings, TILE, TRASH, useBin } from './binStore'

const b = () => useBin.getState()
export const selectedItem = (): BinThing | null => b().items.find((x) => x.asset.id === b().selected) ?? null
const things = () => selectedThings()
const ids = () => things().map((x) => x.asset.id)
const n = () => things().length
const plural = (k: number, one: string, many = `${one}s`) => `${k} ${k === 1 ? one : many}`

/** Where a home's path belongs: World's entity version, the Look or the Sketches, a shot, a cut; null for the imports and the Trash. */
export function belongs(path: string): { label: string; open: () => void } | null {
  const [top, a, c, d] = path.split('/')
  if (top === 'world' && (a === 'look' || a === 'sketches')) return { label: a === 'look' ? 'the Look' : 'the Sketches', open: () => {
    navigate({ suite: 'generate' }); void import('../world/worldStore').then((m) => m.useWorld.getState().setRail(a)) } }
  if (top === 'world' && c) return { label: 'its version in World', open: () => {
    navigate({ suite: 'generate' })
    void Promise.all([import('../world/worldStore'), import('../../suites/story/storyStore')]).then(async ([m, s]) => {
      if (!s.useStory.getState().profiles.some((p) => p.id === c)) await s.useStory.getState().loadProfiles()   // R8: World may not have read them yet
      m.useWorld.getState().pick(c, d || undefined)
    }) } }
  if (top === 'shots' && a) return { label: 'its shot', open: () => {
    navigate({ suite: 'story', tab: 'flow' })
    void Promise.all([import('../shots/shotsStore'), import('../../suites/story/storyStore')]).then(async ([m, s]) => {
      if (!s.useStory.getState().shots.some((x) => x.id === a)) await s.useStory.getState().loadShots()     // the Bin reads no shots of its own
      m.useShots.getState().open(a)
    }) } }
  if (top === 'episode' && a) return { label: 'its cut', open: () => {
    navigate({ suite: 'story', tab: 'episode' }); void import('../../suites/story/episode/sequenceStore').then((m) => m.useSequence.getState().open(a)) } }
  return null
}

/** The homes the selection can move to: every home of the tree (indented under its parent) but the one the thing is in and the headings;
 *  an entity or a shot takes it into its current version. */
export function moveTargets(homes: BinNode[], from: string | null): MenuItem[] {
  const out: MenuItem[] = []
  const walk = (node: BinNode, depth: number) => {
    const label = `${'  '.repeat(depth)}${node.name}`
    if (HEADINGS.has(node.path)) out.push({ label, disabled: true, run: () => undefined })
    else if (node.id !== from && !node.gone) out.push({ label, run: () => void moveThings(ids(), node) })
    node.children.forEach((k) => walk(k, depth + 1))
  }
  homes.forEach((h) => walk(h, 0))
  return out
}

/** B0 (D159 Q5): things moved to a home. One that would lose its role in its home (the hero, a reference, an A-pose, a shot's frame) is
 *  asked about first, naming the role; one a record is made on (a 3D model, a final, a set's picture) or a final version's hero stays. */
export async function moveThings(list: string[], to: BinNode): Promise<void> {
  if (!list.length) return
  const homes = b().homes, toast = useSession.getState().toast
  const first = await unwrap(http.POST('/bin/move', { body: { ids: list, to: to.id } }))
  let moved = first.moved.length
  const refused = [...first.refused]
  if (first.ask.length) {
    const lines = first.ask.map((a) => `${a.roles.map((r) => ROLE_WORDS[r] ?? r).join(' and ')} of ${pathLabel(homes, a.home)}`)
    const ok = await askConfirm({ title: first.ask.length === 1 ? 'Move it and take its role away?' : `Move ${first.ask.length} and take their roles away?`,
      text: `${[...new Set(lines)].join(' · ')} — moved to ${to.name}, ${first.ask.length === 1 ? 'it is' : 'they are'} no longer.`, okLabel: 'Move', danger: true })
    if (ok) {
      const again = await unwrap(http.POST('/bin/move', { body: { ids: first.ask.map((a) => a.id), to: to.id, confirm: true } }))
      moved += again.moved.length
      refused.push(...again.refused)
    }
  }
  if (refused.length) toast(`${refused.length === 1 ? 'It stays' : `${refused.length} stay`}: ${ROLE_WORDS[refused[0].role] ?? refused[0].role} of ${pathLabel(homes, refused[0].home)} (${refused[0].why})`, 'info')
  if (moved) toast(`Moved ${moved === 1 ? '' : `${moved} `}to ${to.name}`, 'success')
  await b().refresh({ tree: true, home: true })
}

/** B1 (R9): files brought in from the disk into the open home (Imports when the Trash, a search or Imports itself is open). */
export async function importInto(paths: string[]): Promise<void> {
  if (!paths.length) return
  const s = b(), node = homeOf(s.open), toast = useSession.getState().toast
  const to = node && node.path !== 'imports' && !HEADINGS.has(node.path) && !s.query ? node : null
  try {
    const r = await unwrap(http.POST('/assets/import', { body: { paths, to: to?.id ?? null } }))
    toast(`${plural(r.items.length, 'thing')} brought into ${to ? to.name : 'Imports'}`, 'success')
    await b().refresh({ tree: true, home: true })
  } catch (e) { toast(`Import failed: ${(e as { detail?: string }).detail ?? e}`, 'error') }
}

async function importAsk(): Promise<void> {
  let paths: string[] = []
  if (isTauri()) paths = await pickFiles('Bring pictures, clips or sounds in')
  else {
    const t = await askText({ title: 'Import', text: 'Files or folders to copy into the project, separated by ";".', placeholder: 'F:/refs/alley.png; F:/refs/moodboard' })
    paths = t ? t.split(/[;\n]/).map((x) => x.trim().replace(/^"|"$/g, '')).filter(Boolean) : []
  }
  await importInto(paths)
}

async function tagThings(): Promise<void> {
  const list = things(); if (!list.length) return
  const one = list.length === 1
  const t = await askText(one ? { title: 'Tags', text: 'Words, separated by commas', initial: list[0].asset.tags.join(', '), allowEmpty: true, okLabel: 'Tag' }
    : { title: `Tag ${list.length} things`, text: 'Words to add to each, separated by commas', okLabel: 'Tag' })
  if (t === null) return
  const words = [...new Set(t.split(',').map((x) => x.trim()).filter(Boolean))]
  const by = new Map<string, string[]>()                                       // one request per resulting tag list
  for (const it of list) {
    const tags = one ? words : [...new Set([...it.asset.tags, ...words])]
    const k = JSON.stringify(tags)
    by.set(k, [...(by.get(k) ?? []), it.asset.id])
  }
  for (const [k, group] of by) await unwrap(http.PATCH('/assets/bulk', { body: { ids: group, changes: { tags: JSON.parse(k) as string[] } } }))
  await b().refresh({ home: true })
}

async function trashThings(): Promise<void> {
  const list = ids(); if (!list.length) return
  await unwrap(http.POST('/assets/trash', { body: { ids: list } }))
  useSession.getState().toast(`${plural(list.length, 'thing')} moved to the Trash`, 'info', { label: 'Undo', run: () => void unwrap(http.POST('/assets/restore', { body: { ids: list } })).then(() => b().reload()) })
  b().select(null); await b().reload()
}

/** Re-run (same seed) or Variations (new seeds) of a made thing: its recipe again, its own origin, so the new ones land beside it. */
async function again(kind: 'rerun' | 'variations'): Promise<void> {
  const it = selectedItem(); if (!it?.asset.params?.recipe) return
  const g = (await import('../../suites/generate/generateStore')).useGenerate.getState()
  const origin = it.asset.origin ?? undefined
  if (kind === 'rerun') await g.rerun(it.asset, origin as never); else await g.variations(it.asset, undefined, origin as never)
}

const inTrash = () => b().open === TRASH
const picture = () => { const it = selectedItem(); return it && !it.asset.trashed_at && it.asset.kind === 'image' ? it : null }
const editWith = (o?: OpenWith) => { const it = picture(); if (it) void import('../world/editAnywhere').then((m) => m.editAnywhere(it.asset.id, o)) }

/** P18 (D84): a 3D prop from the picture — the mesh job, its cost said first; the GLB lands in Imports (World's prop takes it as its model). */
async function makeMesh(): Promise<void> {
  const it = picture(); const mc = useSession.getState().capabilities?.mesh
  if (!it || !mc?.model_id) return
  const mins = (s: number | null | undefined) => (s ? `${Math.round(s / 60)} min` : '?')
  if (!await askConfirm({ title: 'Make a 3D prop from this picture?', okLabel: 'Queue it',
    text: `${mc.label} cuts the object out and builds a textured GLB (${mc.resolutions[0]}, ${Math.round(mc.faces / 1000)}k faces). About ${mins(mc.seconds)} with the model loaded, ${mins(mc.cold_seconds)} from cold, on this card${mc.health === 'missing' ? ' — its weights are missing (Models › Fetch)' : ''}. It runs in the background; the model lands in Imports.` })) return
  try {
    await unwrap(http.POST('/jobs', { body: { recipe: { kind: 'image_to_mesh', asset_id: it.asset.id } as never, stage: false, origin: { suite: 'catalogue', surface: 'mesh', ref: it.asset.id } } }))
    useSession.getState().toast(`Queued a 3D prop (${mins(mc.seconds)})`, 'success')
  } catch (e) { useSession.getState().toast(`Make a 3D prop failed: ${(e as { detail?: string }).detail ?? e}`, 'error') }
}

/** Add to World ▸ (D93 A2): the entry names the entity, its version and the things (castTarget); the server moves or copies them in. */
const addable = (role: 'hero' | 'reference' | 'candidate') => () => {
  const p = castTarget.pid ? useStory.getState().profiles.find((x) => x.id === castTarget.pid) : undefined
  const list = castTarget.ids ?? []
  return !!p && p.versions.find((v) => v.id === (castTarget.vid ?? p.current))?.state === 'open' && list.length > 0 && (role !== 'hero' || list.length === 1)
}
const addTo = (role: 'hero' | 'reference' | 'candidate') => async () => {
  const { pid, vid, ids: list } = castTarget
  if (!pid || !list?.length) return
  await useStory.getState().addToProfile(pid, list, role, vid)
  await b().refresh({ tree: true, home: true })
}
const openNode = () => homeOf(b().open)
/** B3 (D159): the open node is a page (a folder of a home) / a home that holds things (not a heading, the Trash or a deleted record's). */
const openPage = () => { const n = openNode(); return n?.page ? n : undefined }
const holds = () => { const n = openNode(); return !!n && !b().query && !n.gone && !HEADINGS.has(n.path) }
/** The node a page sits in: its home, or the page around it. */
const parentOf = (page: BinNode): BinNode | undefined => [...homesById(b().homes).values()].find((x) => x.children.some((k) => k.id === page.id))
const live = () => n() > 0 && !inTrash()
const order = () => b().items.map((x) => x.asset.id)
const step = (d: number) => { const o = order(), i = o.indexOf(b().selected ?? ''); const j = i + d; if (j >= 0 && j < o.length) b().select(o[j]) }
/** The large view's Fit and 1:1, set while it is open (the view owns its transform). */
export const loupeView: { fit?: () => void; one?: () => void } = {}

registerCommands([
  { id: 'bin.item.open', scope: 'bin', label: 'Open where it belongs ▸', icon: ArrowUpRight, keys: 'Enter', placement: ['inspector', 'context'],
    hint: "the thing's entity version in World, its shot, or its cut", when: () => { const it = selectedItem(); return !!it && !inTrash() && !!belongs(it.path) },
    run: () => { const it = selectedItem(); if (it) belongs(it.path)?.open() } },
  { id: 'bin.item.view', scope: 'bin', label: 'See it large', icon: Maximize2, keys: 'Space', placement: ['inspector', 'context'], when: () => !!selectedItem(),
    hint: 'over the grid — Ctrl+wheel zooms, a drag pans, ← → the next; Esc closes it. A double-click on a tile too', run: () => b().view(!b().viewing) },
  { id: 'bin.item.detach', scope: 'bin', label: 'Detach ↗', icon: ExternalLink, placement: ['inspector'], when: () => !!selectedItem(),
    hint: 'a second window that follows what the Bin selects — for another monitor (D155)', run: () => { void openDetached(b().selected) } },
  { id: 'bin.item.move', scope: 'bin', label: 'Move to…', icon: FolderInput, placement: ['inspector'], when: live,
    hint: 'another home: what it was made for (a tile\'s right-click has the homes as a submenu)',
    run: () => { const it = selectedItem(); showMenu({ clientX: window.innerWidth / 2, clientY: window.innerHeight / 3 }, moveTargets(b().homes, it?.home_id ?? null)) } },
  { id: 'bin.item.tag', scope: 'bin', label: 'Tag…', icon: Tag, keys: 'T', placement: ['inspector', 'context'], when: live, run: tagThings },
  { id: 'bin.item.duplicate', scope: 'bin', label: 'Duplicate', icon: Copy, keys: 'Ctrl+D', placement: ['inspector', 'context'], when: live, hint: 'a copy of each, beside it in its home',
    run: async () => { const r = await unwrap(http.POST('/assets/duplicate', { body: { ids: ids() } })); useSession.getState().toast(`Duplicated ${plural(r.ids.length, 'thing')}`, 'success'); await b().reload() } },
  { id: 'bin.item.reveal', scope: 'bin', label: 'Reveal in folder', icon: FolderOpen, keys: 'Ctrl+Shift+R', placement: ['inspector', 'context'], when: () => !!selectedItem(),
    run: () => { const it = selectedItem(); if (it) void revealPath(it.asset.path) } },
  { id: 'bin.item.rerun', scope: 'bin', label: 'Re-run (same seed)', icon: RotateCcw, keys: 'Ctrl+R', placement: ['inspector', 'context'], hint: 'its recipe again; the new one lands beside it',
    when: () => !inTrash() && !!selectedItem()?.asset.params?.recipe, run: () => again('rerun') },
  { id: 'bin.item.variations', scope: 'bin', label: 'Variations (new seeds)', icon: Shuffle, keys: 'V', placement: ['inspector', 'context'], hint: 'four more with new seeds, beside it',
    when: () => !inTrash() && !!selectedItem()?.asset.params?.recipe, run: () => again('variations') },
  { id: 'bin.item.edit', scope: 'bin', label: 'Open in Edit', icon: Pencil, keys: 'E', placement: ['inspector', 'context'], when: () => !!picture(),
    hint: "in World's Edit: in its version when it is an entity's, else saved beside it", run: () => editWith() },
  { id: 'bin.item.selectSubject', scope: 'bin', label: 'Select subject…', icon: Eraser, placement: ['inspector', 'context'], when: () => !!picture(),
    hint: 'Edit with AI Select · Subject (it selects; Inpaint or a mask does the rest)', run: () => editWith({ suite: 'edit', aiOp: 'select', selMode: 'subject' }) },
  { id: 'bin.item.upscale', scope: 'bin', label: 'Upscale in Edit…', icon: ImageUpscale, placement: ['inspector', 'context'], when: () => !!picture(),
    run: () => editWith({ suite: 'edit', aiOp: 'upscale' }) },
  { id: 'bin.item.angle', scope: 'bin', label: 'New angle…', icon: Orbit, placement: ['inspector', 'context'], when: () => !!picture(), hint: 'a new viewpoint of the picture (P14)',
    run: () => { const it = picture(); if (it) void import('../../frame/openWith').then((m) => m.openWith(it.asset.id, { suite: 'generate', slot: 'angle' })) } },
  { id: 'bin.item.mesh', scope: 'bin', label: 'Make a 3D prop…', icon: Box, placement: ['inspector', 'context'], when: () => !!picture() && !!useSession.getState().capabilities?.mesh?.model_id,
    run: makeMesh },
  { id: 'bin.addTo.hero', scope: 'bin', label: 'Add to World as the hero', icon: ImageUp, placement: ['context'], hint: 'it joins the reference set as its cover', when: addable('hero'), run: addTo('hero') },
  { id: 'bin.addTo.reference', scope: 'bin', label: 'Add to World into the reference set', icon: ImagePlus, placement: ['context'], when: addable('reference'), run: addTo('reference') },
  { id: 'bin.addTo.candidate', scope: 'bin', label: 'Add to World as a candidate', icon: Inbox, placement: ['context'], when: addable('candidate'), run: addTo('candidate') },
  { id: 'bin.item.pin', scope: 'bin', label: 'Pin for compare', icon: Pin, keys: 'C', placement: ['inspector', 'context'], when: () => !!selectedItem() && !inTrash(),
    hint: 'two to four pinned things side by side (zoom and pan together)', run: () => { const it = selectedItem(); if (it) b().pin(it.asset) } },
  { id: 'bin.compare', scope: 'bin', label: 'Compare', icon: Columns2, keys: 'Shift+C', placement: ['panel', 'context'], when: () => b().pins.length >= 2, run: () => b().compare(true) },
  { id: 'bin.unpinAll', scope: 'bin', label: 'Unpin all', icon: PinOff, placement: ['panel', 'toolbar'], when: () => b().pins.length > 0, run: () => b().unpinAll() },
  { id: 'bin.compare.swap', scope: 'bin', label: 'Swap the compared', icon: ArrowLeftRight, keys: 'Tab', placement: ['toolbar'], when: () => b().comparing, run: () => b().swap() },
  { id: 'bin.selectAll', scope: 'bin', label: 'Select all', icon: SquareCheck, keys: 'Ctrl+A', placement: ['panel', 'context'], when: () => b().items.length > 0, run: () => b().selectAll() },
  { id: 'bin.clearSelection', scope: 'bin', label: 'Clear selection', icon: SquareX, keys: 'Escape', placement: ['inspector'], when: () => b().selection.length > 0, run: () => b().select(null) },
  { id: 'bin.tileSmaller', scope: 'bin', label: 'Smaller tiles', icon: ZoomOut, keys: '[', placement: ['panel'], when: () => b().tile > TILE.min, run: () => b().setTile(b().tile - TILE.step) },
  { id: 'bin.tileLarger', scope: 'bin', label: 'Larger tiles', icon: ZoomIn, keys: ']', placement: ['panel'], when: () => b().tile < TILE.max, run: () => b().setTile(b().tile + TILE.step) },
  // B3 (D159 Q2): pages are folders of a home — made, renamed and removed here; a page's things are its home's too
  { id: 'bin.page.new', scope: 'bin', label: 'New page…', icon: FolderPlus, placement: ['panel', 'context'], when: holds,
    hint: 'a folder of the open home (or page): its things are the home\'s too', run: async () => {
      const node = openNode(); if (!node) return
      const name = await askText({ title: 'New page', text: `A folder of ${node.name}: what goes into it is ${node.name}'s too.`, placeholder: 'the page\'s name', okLabel: 'Make the page' })
      if (!name?.trim()) return
      const g = await unwrap(http.POST('/groups', { body: { name: name.trim(), parent_id: node.id } }))
      await b().refresh({ tree: true }); if (!b().expanded[node.id]) b().toggle(node.id); await b().openHome(g.id) } },
  { id: 'bin.page.rename', scope: 'bin', label: 'Rename the page…', icon: PencilLine, placement: ['panel', 'context'], when: () => !!openPage(), run: async () => {
    const page = openPage(); if (!page) return
    const name = await askText({ title: 'Rename the page', initial: page.name, placeholder: 'the page\'s name', okLabel: 'Rename' })
    if (!name?.trim() || name.trim() === page.name) return
    await unwrap(http.PATCH('/groups/{gid}', { params: { path: { gid: page.id } }, body: { name: name.trim() } }))
    await b().refresh({ tree: true }) } },
  { id: 'bin.page.delete', scope: 'bin', label: 'Delete the page…', icon: FolderOutput, placement: ['panel', 'context'], danger: true, when: () => !!openPage(), run: async () => {
    const page = openPage(); if (!page) return
    const up = parentOf(page)
    const users = (await unwrap(http.GET('/groups/used-by', { params: { query: { ids: [page.id] } } })).catch(() => ({} as Record<string, { name: string }[]>)))[page.id] ?? []
    const ok = await askConfirm({ title: `Delete the page ${page.name}?`, okLabel: 'Delete the page', danger: true,
      text: `Its ${plural(page.total, 'thing')} and the pages inside it go to ${up?.name ?? 'its home'}; nothing is deleted.${users.length ? ` It is used by ${users.map((u) => u.name).slice(0, 3).join(', ')}, which will no longer find it.` : ''}` })
    if (!ok) return
    await unwrap(http.POST('/groups/{gid}/ungroup', { params: { path: { gid: page.id } } }))
    await b().refresh({ tree: true }); if (up) await b().openHome(up.id) } },
  { id: 'bin.import', scope: 'bin', label: 'Import…', icon: Upload, placement: ['panel'], hint: 'pictures, clips or sounds from the disk, into the open home (or Imports); a file dropped from Windows too',
    run: importAsk },
  { id: 'bin.loupe.prev', scope: 'bin', label: 'Previous', icon: ChevronLeft, keys: 'ArrowLeft', placement: ['toolbar'], when: () => b().viewing && order().indexOf(b().selected ?? '') > 0, run: () => step(-1) },
  { id: 'bin.loupe.next', scope: 'bin', label: 'Next', icon: ChevronRight, keys: 'ArrowRight', placement: ['toolbar'], when: () => { const o = order(); return b().viewing && o.indexOf(b().selected ?? '') < o.length - 1 }, run: () => step(1) },
  { id: 'bin.loupe.fit', scope: 'bin', label: 'Fit', keys: 'Ctrl+0', placement: ['toolbar'], when: () => b().viewing && !!loupeView.fit, run: () => loupeView.fit?.() },
  { id: 'bin.loupe.one', scope: 'bin', label: '1:1', keys: 'Ctrl+Alt+0', placement: ['toolbar'], hint: 'actual pixels', when: () => b().viewing && !!loupeView.one, run: () => loupeView.one?.() },
  { id: 'bin.home.rehome', scope: 'bin', label: 'Give its things to the Sketches', icon: FolderOutput, placement: ['panel'], when: () => !!openNode()?.gone,
    hint: 'a home whose entity, shot or cut was deleted: its things go to World › Sketches, the home goes',
    run: async () => { const node = openNode(); if (!node) return
      const r = await unwrap(http.POST('/bin/homes/{gid}/rehome', { params: { path: { gid: node.id } } }))
      useSession.getState().toast(`${plural(r.moved, 'thing')} went to the Sketches`, 'success')
      await b().refresh({ tree: true }); await b().openHome(r.to) } },
  { id: 'bin.item.trash', scope: 'bin', label: 'Trash', icon: Trash2, keys: 'Delete', placement: ['inspector', 'context'], danger: true, when: live, run: trashThings },
  { id: 'bin.item.restore', scope: 'bin', label: 'Restore', icon: Undo, placement: ['inspector', 'context'], when: () => n() > 0 && inTrash(),
    run: async () => { await unwrap(http.POST('/assets/restore', { body: { ids: ids() } })); b().select(null); await b().reload() } },
  { id: 'bin.item.purge', scope: 'bin', label: 'Delete permanently…', icon: Trash, keys: 'Shift+Delete', placement: ['inspector', 'context'], danger: true, when: () => n() > 0 && inTrash(),
    run: async () => { const list = ids()
      if (!await askConfirm({ title: `Delete ${plural(list.length, 'thing')} permanently?`, text: 'The files are removed from the project. This cannot be undone.', okLabel: 'Delete permanently', danger: true })) return
      await unwrap(http.POST('/assets/purge', { body: { ids: list } })); b().select(null); await b().reload() } },
  { id: 'bin.trash.empty', scope: 'bin', label: 'Empty trash…', icon: Trash, placement: ['panel', 'context'], danger: true, when: () => b().trash > 0,
    run: async () => { const k = b().trash
      if (!await askConfirm({ title: 'Empty the Trash?', text: `${plural(k, 'thing is', 'things are')} deleted permanently: files, manifests and thumbnails. This cannot be undone.`, okLabel: 'Delete permanently', danger: true })) return
      const r = await unwrap(http.POST('/assets/purge', { body: { ids: null } }))
      useSession.getState().toast(`Trash emptied: ${plural(r.purged, 'thing')} deleted permanently`, 'success'); b().select(null); await b().reload() } },
])

// B2 (D159): the Bin layer is still the `catalogue` suite in `ui.suite`; its keys, help and palette reach the Bin's scope
setReach('catalogue', [{ scope: 'bin' }])

/** A home of the tree by its id (a role page maps to its home). */
export const homeOf = (id: string | null | undefined): BinNode | undefined => (id && id !== TRASH ? homesById(b().homes).get(id) : undefined)
