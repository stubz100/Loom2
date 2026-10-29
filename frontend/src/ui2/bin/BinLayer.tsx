// U8 (D157, proto01_UI2 05 §2.2): the Bin — every creation in its home. The left: a search across every home and the tree of homes with
// their counts (World's entity versions, the Look, the Sketches, the shots, the cuts, the imports — the things on no page — and the
// Trash). The centre: the home's path, the kind chips and its grid (a parent shows everything below it), each thing with its role as a
// badge; a tile drags anywhere a thing goes (frame/drag). The Inspector: the thing's preview or player, its home and roles, how it was
// made, its run, and the verbs (binCommands). No batches, no Unprocessed, no Library (05 §2.1).
import { ChevronDown, ChevronRight, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, http, unwrap } from '../../api/client'
import type { BinThing, BinNode } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { showMenu } from '../../frame/ContextMenu'
import type { MenuItem } from '../../frame/commands'
import { beginDrag, mediaOf } from '../../frame/drag'
import { useSession } from '../../store/session'
import { belongs, moveTargets } from './binCommands'
import { FILTERS, passes, pathLabel, ROLE_LABEL, startBin, TRASH, useBin } from './binStore'
import '../world/world.css'
import './bin.css'

function Node({ n, depth }: { n: BinNode; depth: number }) {
  const open = useBin((s) => s.open === n.id && !s.query)
  const expanded = useBin((s) => !!s.expanded[n.id])
  return (
    <>
      <div className={`b-node${open ? ' active' : ''}`} style={{ paddingLeft: 4 + depth * 14 }} data-path={n.path}>
        {n.children.length ? <button className="b-chev" aria-label={expanded ? 'Fold' : 'Unfold'} onClick={() => useBin.getState().toggle(n.id)}>{expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}</button> : <span className="b-chev" />}
        <button className="b-open" title={n.path} onClick={() => void useBin.getState().openHome(n.id)}><span>{n.name}</span><span className="n">{n.total}</span></button>
      </div>
      {expanded && n.children.map((k) => <Node key={k.id} n={k} depth={depth + 1} />)}
    </>
  )
}

function Tree() {
  const homes = useBin((s) => s.homes)
  const trash = useBin((s) => s.trash)
  const inTrash = useBin((s) => s.open === TRASH)
  const [q, setQ] = useState(useBin.getState().query)
  return (
    <section className="w-left b-left">
      <input className="b-search" type="search" placeholder="search: prompt, name, tag, seed" aria-label="Search the Bin" value={q}
        onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') void useBin.getState().search(q) }}
        onBlur={() => { if (q !== useBin.getState().query) void useBin.getState().search(q) }} />
      <div className="b-tree" data-testid="bin-tree">
        {homes.map((h) => <Node key={h.id} n={h} depth={0} />)}
        <div className={`b-node${inTrash ? ' active' : ''}`}><span className="b-chev" />
          <button className="b-open" onClick={() => void useBin.getState().openHome(TRASH)}><span><Trash2 size={12} /> trash</span><span className="n">{trash}</span></button></div>
      </div>
    </section>
  )
}

const badgeOf = (it: BinThing): string | undefined => it.roles.map((r) => ROLE_LABEL[r]).find(Boolean)

function Tile({ it }: { it: BinThing }) {
  const sel = useBin((s) => s.selected === it.asset.id)
  const menu = (): MenuItem[] => [{ cmd: 'bin.item.open' }, { label: 'Move to', items: moveTargets(useBin.getState().homes, it.home_id ?? null) }, { cmd: 'bin.item.tag' }, { sep: true }, { cmd: 'bin.item.restore' }, { cmd: 'bin.item.trash' }]
  const badge = badgeOf(it)
  return (
    <button className={`w-tile${sel ? ' selected' : ''}`} data-id={it.asset.id} title={it.asset.prompt_text ?? it.path}
      onClick={() => useBin.getState().select(it.asset.id)}
      onContextMenu={(e) => { e.preventDefault(); useBin.getState().select(it.asset.id); showMenu(e, menu()) }}
      onPointerDown={(e) => beginDrag(e, () => (useBin.getState().open === TRASH ? null : { items: [{ kind: 'asset', id: it.asset.id, media: mediaOf(it.asset.kind) }], thumb: api.thumbUrl(it.asset.id, 256), from: 'bin' }))}>
      {it.asset.kind === 'audio' ? <span className="b-audio">♪ {it.asset.prompt_text || 'sound'}</span> : <img src={api.thumbUrl(it.asset.id, 256)} alt="" draggable={false} />}
      {badge && <span className="w-badge">{badge}</span>}
    </button>
  )
}

function Grid() {
  const items = useBin((s) => s.items)
  const filter = useBin((s) => s.filter)
  const path = useBin((s) => s.path)
  const query = useBin((s) => s.query)
  const loading = useBin((s) => s.loading)
  const homes = useBin((s) => s.homes)
  const shown = items.filter((x) => passes(x, filter))
  return (
    <section className="w-centre">
      <div className="w-bin" data-testid="bin-grid">
        <div className="w-bin-head">
          <span className="w-path" title={path}>{query ? `search: ${query}` : path === TRASH ? 'trash' : `bin/${pathLabel(homes, path)}`}</span>
          <span className="w-chips">{FILTERS.map(([f, l]) => <button key={f} className={filter === f ? 'active' : ''} onClick={() => useBin.getState().setFilter(f)}>{l}</button>)}</span>
        </div>
        {shown.length ? <div className="w-grid">{shown.map((it) => <Tile key={it.asset.id} it={it} />)}</div>
          : <div className="w-empty">{loading ? 'Reading the Bin…' : query ? 'Nothing found' : 'Nothing here'}</div>}
      </div>
    </section>
  )
}

function Preview({ it }: { it: BinThing }) {
  const url = api.fileUrl(`/assets/${it.asset.id}/file`)
  if (it.asset.kind === 'video') return <video className="w-preview" src={url} controls muted loop />
  if (it.asset.kind === 'audio') return <audio className="b-player" src={url} controls />
  return <img className="w-preview" src={api.thumbUrl(it.asset.id, 512)} alt="" />
}

function Inspector() {
  const selected = useBin((s) => s.selected)
  const items = useBin((s) => s.items)
  const homes = useBin((s) => s.homes)
  const it = items.find((x) => x.asset.id === selected) ?? null
  const bid = it?.asset.batch_id ?? null
  const [runs, setRuns] = useState<{ bid: string; n: number } | null>(null)          // the run's size, by its batch (another batch reads as none)
  useEffect(() => {
    if (bid) void unwrap(http.GET('/assets', { params: { query: { batch_id: bid, limit: 1 } } })).then((r) => setRuns({ bid, n: r.total ?? r.items.length })).catch(() => undefined)
  }, [bid])
  const run = runs && runs.bid === bid ? runs.n : null
  if (!it) return <aside className="w-insp" data-testid="bin-inspector"><span className="w-empty">Pick a thing</span></aside>
  const a = it.asset
  const made = [a.model_id, Number(a.timings?.wall_s) > 0 ? `${Math.round(Number(a.timings.wall_s))} s` : null, a.seed != null ? `seed ${a.seed}` : null].filter(Boolean).join(' · ')
  const where = belongs(it.path)
  return (
    <aside className="w-insp" data-testid="bin-inspector">
      <h4>{it.roles.map((r) => ROLE_LABEL[r]).filter(Boolean)[0] ?? (a.prompt_text?.slice(0, 40) || a.kind)}</h4>
      <Preview it={it} />
      <div className="kv"><span>home</span><span title={it.path}>{it.path ? pathLabel(homes, it.path) : '—'}</span></div>
      <div className="kv"><span>roles</span><span>{it.roles.join(' · ') || '—'}</span></div>
      {made && <div className="kv"><span>made</span><span>{made}</span></div>}
      {run !== null && run > 1 && <div className="kv"><span>same run</span><span>{run} {a.kind === 'video' ? 'clips' : 'pictures'}</span></div>}
      {a.tags.length > 0 && <div className="kv"><span>tags</span><span>{a.tags.join(', ')}</span></div>}
      {a.prompt_text && <div className="w-prompt-block"><span>prompt</span><p className="w-prompt" title={a.prompt_text}>{a.prompt_text}</p></div>}
      <div className="w-verbs">
        <CommandButton id="bin.item.open" text label={where ? `Open ${where.label} ▸` : undefined} />
        <CommandButton id="bin.item.move" text />
        <CommandButton id="bin.item.tag" text />
        <CommandButton id="bin.item.restore" text />
        <CommandButton id="bin.item.trash" text />
      </div>
    </aside>
  )
}

export function BinLayer() {
  const project = useSession((s) => s.project)
  useEffect(() => (project?.open ? startBin() : undefined), [project?.open])
  if (!project?.open) return <div className="b-layer"><section className="w-centre wide"><div className="w-empty">Open or create a project</div></section></div>
  return (
    <div className="b-layer" data-testid="bin-layer">
      <Tree />
      <Grid />
      <Inspector />
    </div>
  )
}
