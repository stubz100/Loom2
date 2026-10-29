// U8 (D157, proto01_UI2 05 §2.2): the Bin's verbs on the thing selected (rule 3: commands with a mouse home — the Inspector and a tile's
// right-click). The Bin makes nothing: it opens a thing where it belongs, moves it to another home, tags it, trashes or restores it.
import { ArrowUpRight, FolderInput, RotateCcw, Tag, Trash2 } from 'lucide-react'
import { http, unwrap } from '../../api/client'
import type { BinThing, BinNode } from '../../api/types'
import { showMenu } from '../../frame/ContextMenu'
import { registerCommands, type MenuItem } from '../../frame/commands'
import { navigate } from '../../frame/router'
import { askText, useSession } from '../../store/session'
import { homesById, TRASH, useBin } from './binStore'

const b = () => useBin.getState()
export const selectedItem = (): BinThing | null => b().items.find((x) => x.asset.id === b().selected) ?? null

/** Where a home's path belongs: World's entity version, the Look or the Sketches, a shot, a cut; null for the imports and the Trash. */
export function belongs(path: string): { label: string; open: () => void } | null {
  const [top, a, c, d] = path.split('/')
  if (top === 'world' && (a === 'look' || a === 'sketches')) return { label: a === 'look' ? 'the Look' : 'the Sketches', open: () => {
    navigate({ suite: 'generate' }); void import('../world/worldStore').then((m) => m.useWorld.getState().setRail(a)) } }
  if (top === 'world' && c) return { label: 'its version in World', open: () => {
    navigate({ suite: 'generate' }); void import('../world/worldStore').then((m) => m.useWorld.getState().pick(c, d || undefined)) } }
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
  const it = selectedItem(); if (!it) return
  await unwrap(http.POST('/groups/move', { body: { items: [{ kind: 'asset', id: it.asset.id }], to: n.id } }))
  useSession.getState().toast(`Moved to ${n.path}`, 'success')
  await b().reload()
}

const inTrash = () => b().open === TRASH

registerCommands([
  { id: 'bin.item.open', scope: 'catalogue', label: 'Open where it belongs ▸', icon: ArrowUpRight, placement: ['inspector', 'context'],
    hint: "the thing's entity version in World, its shot, or its cut", when: () => { const it = selectedItem(); return !!it && !inTrash() && !!belongs(it.path) },
    run: () => { const it = selectedItem(); if (it) belongs(it.path)?.open() } },
  { id: 'bin.item.move', scope: 'catalogue', label: 'Move to…', icon: FolderInput, placement: ['inspector'], when: () => !!selectedItem() && !inTrash(),
    hint: 'another home: what it was made for (a tile\'s right-click has the homes as a submenu)',
    run: () => { const it = selectedItem(); if (it) showMenu({ clientX: window.innerWidth / 2, clientY: window.innerHeight / 3 }, moveTargets(b().homes, it.home_id ?? null)) } },
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
