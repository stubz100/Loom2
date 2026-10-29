// U8 (D157, proto01_UI2 05 §2.3): the Bin as the Dock's drawer in World, Shots and Episode. B1 (D159, R7): the same Bin as the layer — its
// store, its tree of homes, its windowed grid and its tiles — in a drawer's size, with no Catalogue code. A tile's double-click does the
// likely verb of where you are (a reference in Make, a layer in Edit, the start frame in Performance, an image plane on Clay's stage), its
// right-click lists those verbs, a picture's World verbs and the Bin's own; a tile drags to wherever it is used. A pick started from a
// panel ("Add image plane…") puts its button in the corner of each tile that can take it; a right-click on the grid or Esc ends it.
import { useCallback, useEffect, useRef, useState } from 'react'
import type { Asset, BinThing } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { command, sep, type MenuItem } from '../../frame/commands'
import { Help } from '../../frame/Help'
import { useSession } from '../../store/session'
import { BinGrid } from './BinGrid'
import { BinTree } from './BinLayer'
import { binMenu, gridKeys, useFileDrop } from './binMenus'
import { BinTile } from './BinTile'
import { FILTERS, passes, startBin, TILE, TRASH, useBin } from './binStore'
import { verbsHere, type Verb } from './verbs'
import './bin.css'

const keyOf = (it: BinThing) => it.asset.id
const loadMore = () => void useBin.getState().loadMore()
const endPick = () => useSession.getState().setUi({ pick: null })

/** A tile's right-click in the drawer: the verbs of where you are, then the Bin's own. */
function drawerMenu(suite: string) {
  return (it: BinThing): MenuItem[] => {
    const here = verbsHere(it.asset, suite).map((v): MenuItem => ({ label: v.label, run: v.run }))
    return [...here, ...(here.length ? [sep] : []), ...binMenu(it)]
  }
}

export default function BinDrawer() {
  const project = useSession((s) => s.project)
  const suite = useSession((s) => s.ui.suite)
  const pick = useSession((s) => s.ui.pick) ?? null
  const items = useBin((s) => s.items)
  const filter = useBin((s) => s.filter)
  const query = useBin((s) => s.query)
  const loading = useBin((s) => s.loading)
  const total = useBin((s) => s.total)
  const inTrash = useBin((s) => s.open === TRASH)
  const focus = useBin((s) => s.items.findIndex((x) => x.asset.id === s.selected))
  const [cols, setCols] = useState(1)
  const el = useRef<HTMLDivElement | null>(null)
  const over = useFileDrop(useCallback(() => el.current, []))
  useEffect(() => (project?.open ? startBin() : undefined), [project?.open])
  useEffect(() => {                                                       // Esc ends a pick (the ✕ in the bar is its mouse placement, D32)
    if (!pick) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.preventDefault(); endPick() } }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [pick])
  if (!project?.open) return <span className="meta">No project open.</span>
  const shown = query ? items.filter((x) => passes(x, filter)) : items
  const picked = (a: Asset): Verb | undefined => (pick ? verbsHere(a, suite).find((v) => v.id === pick.verb) : undefined)
  const PickIcon = pick ? command(pick.cmd)?.icon : undefined
  const double = (it: BinThing) => { const pv = picked(it.asset); if (pv) { pv.run(); endPick() } else verbsHere(it.asset, suite)[0]?.run() }
  const corner = (it: BinThing) => { const pv = picked(it.asset); return pv ? { icon: PickIcon ? <PickIcon size={13} /> : undefined, label: pv.label, run: () => { pv.run(); endPick() } } : undefined }
  const menu = drawerMenu(suite)
  return (
    <div className="bin b-drawer">
      <BinTree compact />
      <div className={`bin-main${over ? ' file-over' : ''}`}>
        <div className="bin-bar">
          <span className="segmented" role="group" aria-label="Bin type">
            {FILTERS.map(([f, l]) => <button key={f} className={filter === f ? 'active' : ''} onClick={() => useBin.getState().setFilter(f)}>{l}</button>)}
          </span>
          <span className="meta">{loading ? 'loading…' : `${total ?? shown.length}`}</span>
          <span className="spacer" />
          {pick ? <span className="meta picking">picking for: {pick.label} <button type="button" className="quiet" aria-label="stop picking" title="Stop picking (the tiles' corner buttons go)" onClick={endPick}>✕</button></span>
            : inTrash ? <CommandButton id="bin.trash.empty" text className="quiet danger" />
            : <><CommandButton id="bin.import" /><Help text={`Drag a tile to where it is used. Double-click: ${suite === 'stage' ? 'an image plane, a 3D model, or play' : suite === 'animate' ? 'the start frame, or play' : suite === 'edit' ? 'a layer' : 'a reference'}. Right-click: every verb.`} /></>}
        </div>
        <div className="bin-grid-host" tabIndex={0} onKeyDown={(e) => gridKeys(e, cols)} onContextMenu={(e) => { if (pick && !(e.target as HTMLElement).closest('.w-tile')) { e.preventDefault(); endPick() } }}>
          {shown.length ? <BinGrid items={shown} keyOf={keyOf} min={TILE.drawer} gap={6} className="bin-grid" focus={focus} onCols={setCols} gridRef={(x) => { el.current = x }}
            render={(it) => <BinTile it={it} menu={menu} onDouble={() => double(it)} corner={corner(it)} />} onEnd={loadMore} />
            : <div className="meta b-empty" ref={(x) => { if (!items.length) el.current = x }}>{loading ? '' : inTrash ? 'The trash is empty.' : 'Nothing here.'}</div>}
        </div>
      </div>
    </div>
  )
}
