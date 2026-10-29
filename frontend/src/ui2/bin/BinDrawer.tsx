// U8 (D157, proto01_UI2 05 §2.3): the Bin as the Dock's drawer in World, Shots and Episode — the homes' tree in place of the old places
// (Unprocessed, the Library, the album's groups); the drawer's grid, its verbs and its drag are the Bin's of D95 (a double-click does the
// likely verb of where you are, the right-click lists them all, a tile drags to wherever it is used).
import { ChevronDown, ChevronRight, Trash2 } from 'lucide-react'
import { useEffect } from 'react'
import type { BinNode } from '../../api/types'
import { Bin } from '../../suites/catalogue/Bin'
import { useBin as useDrawer } from '../../suites/catalogue/catalogueStore'
import { useBin } from './binStore'
import './bin.css'

function Row({ n, depth }: { n: BinNode; depth: number }) {
  const active = useDrawer((s) => s.q.home_id === n.id && s.q.folder !== 'trash')
  const expanded = useBin((s) => !!s.expanded[n.id])
  return (
    <>
      <div className={`b-node${active ? ' active' : ''}`} style={{ paddingLeft: depth * 12 }} data-path={n.path}>
        {n.children.length ? <button className="b-chev" aria-label={expanded ? 'Fold' : 'Unfold'} onClick={() => useBin.getState().toggle(n.id)}>{expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}</button> : <span className="b-chev" />}
        <button className="b-open" title={n.path} onClick={() => void useDrawer.getState().setQuery({ folder: 'all', group_id: undefined, home_id: n.id })}><span>{n.name}</span><span className="n">{n.total}</span></button>
      </div>
      {expanded && n.children.map((k) => <Row key={k.id} n={k} depth={depth + 1} />)}
    </>
  )
}

function Homes() {
  const homes = useBin((s) => s.homes)
  const trash = useBin((s) => s.trash)
  const inTrash = useDrawer((s) => s.q.folder === 'trash')
  useEffect(() => {
    void useBin.getState().loadTree().then(() => {
      const q = useDrawer.getState().q, first = useBin.getState().homes[0]
      if (!q.home_id && q.folder !== 'trash' && first) void useDrawer.getState().setQuery({ folder: 'all', group_id: undefined, home_id: first.id })
    })
  }, [])
  return (
    <nav className="bin-places b-drawer-homes" aria-label="Bin homes" data-testid="bin-drawer-homes">
      {homes.map((h) => <Row key={h.id} n={h} depth={0} />)}
      <button className={`bin-trash${inTrash ? ' active' : ''}`} onClick={() => void useDrawer.getState().setQuery({ folder: 'trash', group_id: undefined, home_id: undefined })}
        title="What was moved to the trash: restore it, or delete it permanently"><Trash2 size={12} /> Trash{trash > 0 && <small>{trash}</small>}</button>
    </nav>
  )
}

export default function BinDrawer() {
  return <Bin places={<Homes />} />
}
