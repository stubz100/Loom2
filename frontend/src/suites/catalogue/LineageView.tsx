// The lineage view (D34, proto01_design/01 §6c): one derivation tree on the Stage — the root on the left, derivations to the
// right, one row per branch, the edge kind on each connector, and under every card where that asset lives (the branches of
// one lineage are usually spread over several groups). Cards select, open the loupe, drag onto groups and take the tile menu.
import { GitBranch } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../../api/client'
import type { Asset } from '../../api/types'
import { showMenu } from '../../frame/ContextMenu'
import { beginDrag } from '../../frame/drag'
import type { PathStep } from './albumStore'
import { tileMenu } from './catalogueCommands'
import { useCat } from './catalogueContext'

interface Tree {
  root_id: string; items: Asset[]; edges: { from_id: string; to_id: string; kind: string }[]
  locations: Record<string, { group_id: string; path: PathStep[] } | null>
}
const CARD_W = 240, CARD_H = 76, COL = 360, ROW = 112, PAD = 40, BEND = 24

/** "14:02" today, "7 Oct" otherwise: the card is small. */
const cardTime = (iso: string) => { const d = new Date(iso); return d.toDateString() === new Date().toDateString() ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : d.toLocaleDateString([], { day: 'numeric', month: 'short' }) }

/** Columns by depth; the first child stays on its parent's row, each further child opens a new row below the subtree. */
function layout(t: Tree): { pos: Map<string, { col: number; row: number }>; rows: number; cols: number } {
  const kids = new Map<string, string[]>()
  for (const e of t.edges) kids.set(e.from_id, [...(kids.get(e.from_id) ?? []), e.to_id])
  const created = new Map(t.items.map((a) => [a.id, a.created_at]))
  for (const [, v] of kids) v.sort((a, b) => (created.get(a) ?? '').localeCompare(created.get(b) ?? ''))
  const pos = new Map<string, { col: number; row: number }>()
  let nextRow = 0, cols = 0
  const place = (id: string, col: number, row: number) => {
    if (pos.has(id)) return
    pos.set(id, { col, row })
    cols = Math.max(cols, col + 1)
    ;(kids.get(id) ?? []).forEach((k, i) => { if (i === 0) place(k, col + 1, row); else { nextRow += 1; place(k, col + 1, nextRow) } })
  }
  const known = new Set(t.items.map((a) => a.id))
  const roots = t.items.filter((a) => !t.edges.some((e) => e.to_id === a.id && known.has(e.from_id)))
  roots.forEach((r, i) => { if (i > 0) nextRow += 1; place(r.id, 0, nextRow) })
  return { pos, rows: nextRow + 1, cols }
}

export function LineageView({ id }: { id: string }) {
  const c = useCat()
  const [tree, setTree] = useState<Tree | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [rootId, setRootId] = useState<string | null>(null)
  useEffect(() => {
    let live = true
    void api.get<Asset>(`/assets/${id}`).then((a) => { if (live) setRootId(a.root_id ?? a.id) }).catch((e) => { if (live) setError((e as Error).message) })
    return () => { live = false }
  }, [id])
  useEffect(() => {
    if (!rootId) return
    let live = true
    void api.get<Tree>(`/lineage/tree/${rootId}`).then((t) => { if (live) setTree(t) }).catch((e) => { if (live) setError((e as Error).message) })
    return () => { live = false }
  }, [rootId])
  const lay = useMemo(() => (tree ? layout(tree) : null), [tree])
  useEffect(() => {                                               // Esc goes back, like the loupe
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape' && !(e.target as HTMLElement)?.closest('input, textarea')) c.openLineage(null) }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [c])
  if (error) return <div className="cat-empty"><div><h2>Lineage unavailable</h2><p>{error}</p></div></div>
  if (!tree || !lay) return <div className="cat-empty"><div>loading the lineage…</div></div>
  const byId = new Map(tree.items.map((a) => [a.id, a]))
  const xy = (aid: string) => { const p = lay.pos.get(aid)!; return { x: PAD + p.col * COL, y: PAD + p.row * ROW } }
  const W = PAD * 2 + Math.max(0, lay.cols - 1) * COL + CARD_W, H = PAD * 2 + Math.max(0, lay.rows - 1) * ROW + CARD_H
  const sel = new Set(c.selected)
  return (
    <div className="lineage-view">
      <div className="lin-bar">
        <GitBranch size={14} /><b>Lineage</b>
        <span className="muted">{tree.items.length} asset{tree.items.length === 1 ? '' : 's'} · {lay.rows} branch{lay.rows === 1 ? '' : 'es'} · in {new Set(tree.items.map((a) => tree.locations[a.id]?.group_id ?? 'unprocessed')).size} place{new Set(tree.items.map((a) => tree.locations[a.id]?.group_id ?? 'u')).size === 1 ? '' : 's'}</span>
      </div>
      <div className="lin-scroll">
        <div className="lin-canvas" style={{ width: W, height: H }}>
          <svg className="lin-edges" width={W} height={H} aria-hidden="true">
            {tree.edges.filter((e) => lay.pos.has(e.from_id) && lay.pos.has(e.to_id)).map((e) => {
              const a = xy(e.from_id), b = xy(e.to_id)
              const x1 = a.x + CARD_W, y1 = a.y + CARD_H / 2, x2 = b.x, y2 = b.y + CARD_H / 2
              const mx = x1 + BEND                                      // branches bend right after the parent; the label sits on the last stretch
              const d = y1 === y2 ? `M ${x1} ${y1} L ${x2 - 6} ${y2}` : `M ${x1} ${y1} L ${mx} ${y1} L ${mx} ${y2} L ${x2 - 6} ${y2}`
              return <g key={`${e.from_id}-${e.to_id}`}><path d={d} /><polygon points={`${x2},${y2} ${x2 - 7},${y2 - 4} ${x2 - 7},${y2 + 4}`} /></g>
            })}
          </svg>
          {tree.edges.filter((e) => lay.pos.has(e.from_id) && lay.pos.has(e.to_id)).map((e) => {
            const a = xy(e.from_id), b = xy(e.to_id)
            const x1 = a.x + CARD_W
            const x = a.y === b.y ? x1 + (b.x - x1) / 2 : x1 + BEND + (b.x - x1 - BEND) / 2
            return <span key={`l-${e.to_id}`} className="lin-label" style={{ left: x, top: b.y + CARD_H / 2 - 22 }}>{e.kind}</span>
          })}
          {tree.items.filter((a) => lay.pos.has(a.id)).map((a) => {
            const { x, y } = xy(a.id)
            const loc = tree.locations[a.id]
            return (
              <div key={a.id} className={`lin-card${a.id === id ? ' here' : ''}${sel.has(a.id) ? ' selected' : ''}`} style={{ left: x, top: y, width: CARD_W, height: CARD_H }}
                onClick={() => c.select(a.id, 'single')} onDoubleClick={() => { if (a.id !== id) c.openLineage(a.id) }}
                onContextMenu={(e) => { c.select(a.id, 'single'); showMenu(e, tileMenu()) }}
                onPointerDown={(e) => beginDrag(e, () => ({ items: [{ kind: 'asset', id: a.id }], thumb: api.thumbUrl(a.id, 256) }))}
                title={`${a.model_id ?? a.suite} · ${a.w}×${a.h} · seed ${a.seed ?? '—'}`}>
                <img src={api.thumbUrl(a.id, 256)} alt="" draggable={false} />
                <span className="txt">
                  <b>{a.kind === 'video' ? `Clip${a.frames ? ` · ${a.frames} f` : ''}` : byId.get(a.id)?.suite === 'import' ? 'Imported' : a.suite[0].toUpperCase() + a.suite.slice(1)} · {cardTime(a.created_at)}</b>
                  <span className="where">{loc ? loc.path.slice(1).map((p) => p.name).join(' › ') || 'Album' : 'Unprocessed'}</span>
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
