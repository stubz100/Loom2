// B1 (D159): what the Bin's layer and its drawer share besides the tile — the Bin's own verbs on the selection as a menu, the grid's keys,
// and a file dropped from Windows landing in the open home.
import { useEffect, useState } from 'react'
import type { BinThing } from '../../api/types'
import { handleKeyFor, sep, type MenuItem } from '../../frame/commands'
import { listenFileDrop } from '../../shell/tauri'
import { belongs, importInto, moveTargets } from './binCommands'
import { selectedThings, shownItems, TRASH, useBin } from './binStore'
import { useSession } from '../../store/session'
import { worldItems } from './verbs'

/** The Bin's own verbs on the selection, as a menu (the drawer puts the verbs of where you are before them). */
/** C6 (D181, 04 §4.7): a kind's own verb — it opens or queues where the thing belongs (05 §2.3: the Bin makes nothing of its own): a pass →
 *  Render the passes again (the shot's Clay), a take or a still → Re-take (its Performance), a composition or final → the composition (its
 *  Final), an animatic → Record again (Clay's Record mode), a set thing → the set builder, a body thing → the body, a model → the model
 *  (the Library on the version), a voice → the version in World. Null for a kind with no home of making (a free picture, a working file). */
export function kindVerb(it: BinThing): { label: string; run: () => void } | null {
  const [top, a, c, d] = it.path.split('/')
  const shot = top === 'shots' && a ? a : null
  const vers = top === 'world' && c ? { profile: c, version: d || null } : null
  const openShot = (level: 'clay' | 'performance' | 'final', then?: 'record') => () => {
    void Promise.all([import('../shots/shotsStore'), import('../../suites/story/storyStore')]).then(async ([m, s]) => {
      if (!s.useStory.getState().shots.some((x) => x.id === shot)) await s.useStory.getState().loadShots()
      m.useShots.getState().open(shot!, level)
      if (then === 'record') await m.recordInClay()
    })
  }
  const openLib = (_kind: 'figure' | 'prop' | 'set') => () => void import('../world/worldStore').then((m) => m.useWorld.getState().openClay(vers!.profile, vers!.version, 'build'))   // RS1 (D197): World › Clay
  switch (it.shelf) {
    case 'passes': return shot ? { label: 'Render the passes again ▸', run: openShot('clay') } : null
    case 'takes': case 'stills': return shot ? { label: 'Re-take ▸', run: openShot('performance') } : null
    case 'composition': case 'final': return shot ? { label: 'The composition ▸', run: openShot('final') } : null
    case 'animatic': return shot ? { label: 'Record again ▸', run: openShot('performance', 'record') } : null
    case 'set': case 'life': return vers ? { label: 'The set builder ▸', run: openLib('set') } : null
    case 'body': case 'poses': return vers ? { label: 'The body ▸', run: openLib('figure') } : null
    case 'model': return vers ? { label: 'The model ▸', run: openLib('prop') } : null
    case 'voice': return vers ? { label: 'The voice ▸', run: () => belongs(it.path)?.open() } : null
    default: return null
  }
}

export function binMenu(it: BinThing): MenuItem[] {
  const s = useBin.getState()
  if (s.open === TRASH || it.asset.trashed_at) return [{ cmd: 'bin.item.restore' }, { cmd: 'bin.item.purge' }, sep, { cmd: 'bin.trash.empty' }]
  const many = selectedThings().length > 1
  const made = !!it.asset.params?.recipe
  const world = many ? [] : worldItems(it.asset)
  const pic = it.asset.kind === 'image' && !many
  const starts: MenuItem[] = pic ? [sep, { cmd: 'bin.item.edit' }, { cmd: 'bin.item.selectSubject' }, { cmd: 'bin.item.upscale' }, { cmd: 'bin.item.angle' },
    ...(useSession.getState().capabilities?.mesh?.model_id ? [{ cmd: 'bin.item.mesh' }] : [])] : []
  const kind = many ? null : kindVerb(it)
  return [{ cmd: 'bin.item.open' }, ...(kind ? [kind] : []), { cmd: 'bin.item.view' }, { label: 'Move to', items: moveTargets(s.homes, it.home_id ?? null) }, { cmd: 'bin.item.tag' },
    { cmd: 'bin.item.duplicate' }, { cmd: 'bin.item.pin', label: s.pins.some((a) => a.id === it.asset.id) ? 'Unpin' : undefined },
    ...(s.pins.length >= 2 ? [{ cmd: 'bin.compare' }] : []),
    ...starts,
    ...(world.length ? [sep, ...world] : []),
    ...(made && !many ? [sep, { cmd: 'bin.item.rerun' }, { cmd: 'bin.item.variations' }] : []),
    sep, { cmd: 'bin.item.reveal' }, { cmd: 'bin.selectAll' }, sep, { cmd: 'bin.item.trash' }]
}

/** The Bin's keys on its grid: the arrows move the selection (Shift: a range), the rest run the Bin's commands (handleKeyFor('bin')). */
export function gridKeys(e: React.KeyboardEvent, cols: number): void {
  if ((e.target as HTMLElement).closest('input, textarea, select')) return
  const s = useBin.getState()
  const order = shownItems(s).map((x) => x.asset.id), i = order.indexOf(s.selected ?? '')   // review K70: the arrows walk what is shown
  const d = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: cols, ArrowUp: -cols }[e.key]
  if (d !== undefined && !e.ctrlKey && !e.altKey) {
    e.preventDefault()
    const j = i < 0 ? 0 : Math.max(0, Math.min(order.length - 1, i + d))
    if (order[j]) s.select(order[j], e.shiftKey ? 'range' : 'single')
    return
  }
  if (handleKeyFor('bin', e.nativeEvent)) e.preventDefault()
}

/** OS files dropped on an element go into the open home (R9). */
export function useFileDrop(el: () => HTMLElement | null): boolean {
  const [over, setOver] = useState(false)
  useEffect(() => listenFileDrop({ over: (inside) => setOver(inside), drop: (paths) => { setOver(false); void importInto(paths) }, within: el }), [el])
  return over
}
