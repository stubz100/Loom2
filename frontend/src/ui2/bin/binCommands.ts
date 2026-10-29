// U8 (D157, proto01_UI2 05 §2.2): the Bin's verbs on the thing selected (rule 3: commands with a mouse home — the Inspector and a tile's
// right-click). The Bin makes nothing: it opens a thing where it belongs, moves it to another home, tags it, trashes or restores it.
// B0 (D159 Q5): a move that would take a thing's role away asks first, naming the role; a home whose record was deleted gives its things
// to the Sketches.
import { ArrowUpRight, ExternalLink, FolderInput, FolderOutput, Maximize2, RotateCcw, Tag, Trash2 } from 'lucide-react'
import { openDetached } from '../../frame/loupeLink'
import { http, unwrap } from '../../api/client'
import type { BinThing, BinNode } from '../../api/types'
import { showMenu } from '../../frame/ContextMenu'
import { registerCommands, type MenuItem } from '../../frame/commands'
import { navigate } from '../../frame/router'
import { askConfirm, askText, useSession } from '../../store/session'
import { homesById, pathLabel, ROLE_WORDS, TRASH, useBin } from './binStore'

const b = () => useBin.getState()
export const selectedItem = (): BinThing | null => b().items.find((x) => x.asset.id === b().selected) ?? null

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

/** The homes a thing can move to: every home of the tree (its path as the label), but the one it is in. */
export function moveTargets(homes: BinNode[], from: string | null): MenuItem[] {
  const out: MenuItem[] = []
  const walk = (n: BinNode, depth: number) => {
    if (n.id !== from) out.push({ label: `${'  '.repeat(depth)}${n.name}`, run: () => void moveTo(n) })
    n.children.forEach((k) => walk(k, depth + 1))
  }
  homes.forEach((h) => walk(h, 0))
  return out
}

async function moveTo(n: BinNode): Promise<void> {
  const it = selectedItem(); if (it) await moveThings([it.asset.id], n)
}

/** B0 (D159 Q5): things moved to a home. One that would lose its role in its home (the hero, a reference, an A-pose, a shot's frame) is
 *  asked about first, naming the role; one a record is made on (a 3D model, a final, a set's picture) or a final version's hero stays. */
export async function moveThings(ids: string[], n: BinNode): Promise<void> {
  const homes = b().homes, toast = useSession.getState().toast
  const first = await unwrap(http.POST('/bin/move', { body: { ids, to: n.id } }))
  let moved = first.moved.length
  const refused = [...first.refused]
  if (first.ask.length) {
    const lines = first.ask.map((a) => `${a.roles.map((r) => ROLE_WORDS[r] ?? r).join(' and ')} of ${pathLabel(homes, a.home)}`)
    const ok = await askConfirm({ title: first.ask.length === 1 ? 'Move it and take its role away?' : `Move ${first.ask.length} and take their roles away?`,
      text: `${[...new Set(lines)].join(' · ')} — moved to ${n.name}, ${first.ask.length === 1 ? 'it is' : 'they are'} no longer.`, okLabel: 'Move', danger: true })
    if (ok) {
      const again = await unwrap(http.POST('/bin/move', { body: { ids: first.ask.map((a) => a.id), to: n.id, confirm: true } }))
      moved += again.moved.length
      refused.push(...again.refused)
    }
  }
  if (refused.length) toast(`${refused.length === 1 ? 'It stays' : `${refused.length} stay`}: ${ROLE_WORDS[refused[0].role] ?? refused[0].role} of ${pathLabel(homes, refused[0].home)} (${refused[0].why})`, 'info')
  if (moved) toast(`Moved to ${n.name}`, 'success')
  await b().refresh({ tree: true, home: true })
}

const inTrash = () => b().open === TRASH
const openNode = () => homeOf(b().open)

registerCommands([
  { id: 'bin.item.open', scope: 'catalogue', label: 'Open where it belongs ▸', icon: ArrowUpRight, placement: ['inspector', 'context'],
    hint: "the thing's entity version in World, its shot, or its cut", when: () => { const it = selectedItem(); return !!it && !inTrash() && !!belongs(it.path) },
    run: () => { const it = selectedItem(); if (it) belongs(it.path)?.open() } },
  { id: 'bin.item.view', scope: 'catalogue', label: 'See it large', icon: Maximize2, placement: ['inspector', 'context'], when: () => !!selectedItem(),
    hint: 'over the grid (Esc, or a click, closes it); a double-click on a tile too', run: () => b().view(true) },
  { id: 'bin.item.detach', scope: 'catalogue', label: 'Detach ↗', icon: ExternalLink, placement: ['inspector'], when: () => !!selectedItem(),
    hint: 'a second window that follows what the Bin selects — for another monitor (D155)', run: () => { void openDetached(b().selected) } },
  { id: 'bin.item.move', scope: 'catalogue', label: 'Move to…', icon: FolderInput, placement: ['inspector'], when: () => !!selectedItem() && !inTrash(),
    hint: 'another home: what it was made for (a tile\'s right-click has the homes as a submenu)',
    run: () => { const it = selectedItem(); if (it) showMenu({ clientX: window.innerWidth / 2, clientY: window.innerHeight / 3 }, moveTargets(b().homes, it.home_id ?? null)) } },
  { id: 'bin.home.rehome', scope: 'catalogue', label: 'Give its things to the Sketches', icon: FolderOutput, placement: ['panel'], when: () => !!openNode()?.gone,
    hint: 'a home whose entity, shot or cut was deleted: its things go to World › Sketches, the home goes',
    run: async () => { const n = openNode(); if (!n) return
      const r = await unwrap(http.POST('/bin/homes/{gid}/rehome', { params: { path: { gid: n.id } } }))
      useSession.getState().toast(`${r.moved} ${r.moved === 1 ? 'thing' : 'things'} went to the Sketches`, 'success')
      await b().refresh({ tree: true }); await b().openHome(r.to) } },
  { id: 'bin.item.tag', scope: 'catalogue', label: 'Tag…', icon: Tag, placement: ['inspector', 'context'], when: () => !!selectedItem() && !inTrash(),
    run: async () => {
      const it = selectedItem(); if (!it) return
      const t = await askText({ title: 'Tags', text: 'Words, separated by commas', initial: it.asset.tags.join(', '), allowEmpty: true, okLabel: 'Tag' })
      if (t === null) return
      const tags = [...new Set(t.split(',').map((x) => x.trim()).filter(Boolean))]
      await unwrap(http.PATCH('/assets/bulk', { body: { ids: [it.asset.id], changes: { tags } } }))
      await b().reload()
    } },
  { id: 'bin.item.trash', scope: 'catalogue', label: 'Trash', icon: Trash2, placement: ['inspector', 'context'], danger: true, when: () => !!selectedItem() && !inTrash(),
    run: async () => { const it = selectedItem(); if (!it) return
      await unwrap(http.POST('/assets/trash', { body: { ids: [it.asset.id] } }))
      useSession.getState().toast('Moved to the Trash', 'info', { label: 'Undo', run: () => void unwrap(http.POST('/assets/restore', { body: { ids: [it.asset.id] } })).then(() => b().reload()) })
      b().select(null); await b().reload() } },
  { id: 'bin.item.restore', scope: 'catalogue', label: 'Restore', icon: RotateCcw, placement: ['inspector', 'context'], when: () => !!selectedItem() && inTrash(),
    run: async () => { const it = selectedItem(); if (!it) return
      await unwrap(http.POST('/assets/restore', { body: { ids: [it.asset.id] } })); b().select(null); await b().reload() } },
])

/** A home of the tree by its id (a role page maps to its home). */
export const homeOf = (id: string | null | undefined): BinNode | undefined => (id ? homesById(b().homes).get(id) : undefined)
