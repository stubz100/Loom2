// B1 (D159): what the Bin's layer and its drawer share besides the tile — the Bin's own verbs on the selection as a menu, the grid's keys,
// and a file dropped from Windows landing in the open home.
import { useEffect, useState } from 'react'
import type { BinThing } from '../../api/types'
import { handleKeyFor, sep, type MenuItem } from '../../frame/commands'
import { listenFileDrop } from '../../shell/tauri'
import { importInto, moveTargets } from './binCommands'
import { selectedThings, TRASH, useBin } from './binStore'
import { useSession } from '../../store/session'
import { worldItems } from './verbs'

/** The Bin's own verbs on the selection, as a menu (the drawer puts the verbs of where you are before them). */
export function binMenu(it: BinThing): MenuItem[] {
  const s = useBin.getState()
  if (s.open === TRASH || it.asset.trashed_at) return [{ cmd: 'bin.item.restore' }, { cmd: 'bin.item.purge' }, sep, { cmd: 'bin.trash.empty' }]
  const many = selectedThings().length > 1
  const made = !!it.asset.params?.recipe
  const world = many ? [] : worldItems(it.asset)
  const pic = it.asset.kind === 'image' && !many
  const starts: MenuItem[] = pic ? [sep, { cmd: 'bin.item.edit' }, { cmd: 'bin.item.selectSubject' }, { cmd: 'bin.item.upscale' }, { cmd: 'bin.item.angle' },
    ...(useSession.getState().capabilities?.mesh?.model_id ? [{ cmd: 'bin.item.mesh' }] : [])] : []
  return [{ cmd: 'bin.item.open' }, { cmd: 'bin.item.view' }, { label: 'Move to', items: moveTargets(s.homes, it.home_id ?? null) }, { cmd: 'bin.item.tag' },
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
  const order = s.items.map((x) => x.asset.id), i = order.indexOf(s.selected ?? '')
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
