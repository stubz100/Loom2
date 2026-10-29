// U8 (D157, proto01_UI2 05 §2.2): the Bin — every creation in its home. The left: a search across every home and the tree of homes with
// their counts (World's entity versions, the Look, the Sketches, the shots, the cuts, the imports — the things on no page — and the
// Trash). The centre: the home's path, the kind chips and its grid (a parent shows everything below it), each thing with its role as a
// badge; a tile drags anywhere a thing goes (frame/drag). The Inspector: the thing's preview or player, its home and roles, how it was
// made, its run, and the verbs (binCommands). No batches, no Unprocessed, no Library (05 §2.1). B0 (D159): the grid is windowed and
// reads a page at a time; a home whose record was deleted says so and gives its things to the Sketches.
// B1 (D159, 11 §3): the selection is many (a click, Ctrl, Shift, Select all; the arrows with Shift), the keys run the Bin's commands
// (Enter opens where it belongs, Space shows it large, Delete trashes, C pins, [ ] the tile size), compare, the tile size, Import… and a
// file dropped from Windows into the open home, and the Inspector's lineage (made from, made into) and what uses the thing.
import { ChevronDown, ChevronRight, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api, http, unwrap } from '../../api/client'
import type { BinNode, BinThing } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { Help } from '../../frame/Help'
import { useSession } from '../../store/session'
import { belongs, homeOf } from './binCommands'
import { BinGrid } from './BinGrid'
import { BinCompare, BinLoupe } from './BinLoupe'
import { BinTile } from './BinTile'
import { binMenu, gridKeys, useFileDrop } from './binMenus'
import { FILTERS, passes, pathLabel, ROLE_LABEL, ROLE_WORDS, selectedThings, startBin, TRASH, useBin } from './binStore'
import '../world/world.css'
import './bin.css'

function Node({ n, depth }: { n: BinNode; depth: number }) {
  const open = useBin((s) => s.open === n.id && !s.query)
  const expanded = useBin((s) => !!s.expanded[n.id])
  return (
    <>
      <div className={`b-node${open ? ' active' : ''}${n.gone ? ' gone' : ''}`} style={{ paddingLeft: 4 + depth * 14 }} data-path={n.path}>
        {n.children.length ? <button className="b-chev" aria-label={expanded ? 'Fold' : 'Unfold'} onClick={() => useBin.getState().toggle(n.id)}>{expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}</button> : <span className="b-chev" />}
        <button className="b-open" title={n.gone ? `${n.path} — deleted` : n.path} onClick={() => void useBin.getState().openHome(n.id)}><span>{n.name}{n.gone ? ' · deleted' : ''}</span><span className="n">{n.total}</span></button>
      </div>
      {expanded && n.children.map((k) => <Node key={k.id} n={k} depth={depth + 1} />)}
    </>
  )
}

/** The search and the tree of homes (the layer's left; the drawer's too, `compact`). */
export function BinTree({ compact = false }: { compact?: boolean }) {
  const homes = useBin((s) => s.homes)
  const trash = useBin((s) => s.trash)
  const inTrash = useBin((s) => s.open === TRASH)
  const [q, setQ] = useState(useBin.getState().query)
  return (
    <section className={compact ? 'b-left compact' : 'w-left b-left'}>
      <input className="b-search" type="search" placeholder={compact ? 'search' : 'search: prompt, name, tag, seed'} aria-label="Search the Bin" value={q}
        onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') void useBin.getState().search(q) }}
        onBlur={() => { if (q !== useBin.getState().query) void useBin.getState().search(q) }} />
      <div className="b-tree" data-testid={compact ? 'bin-drawer-homes' : 'bin-tree'}>
        {homes.map((h) => <Node key={h.id} n={h} depth={0} />)}
        <div className={`b-node${inTrash ? ' active' : ''}`} data-path="trash"><span className="b-chev" />
          <button className="b-open" onClick={() => void useBin.getState().openHome(TRASH)}><span><Trash2 size={12} /> trash</span><span className="n">{trash}</span></button></div>
      </div>
    </section>
  )
}

const loadMore = () => void useBin.getState().loadMore()
const keyOf = (it: BinThing) => it.asset.id

function Grid() {
  const items = useBin((s) => s.items)
  const filter = useBin((s) => s.filter)
  const path = useBin((s) => s.path)
  const query = useBin((s) => s.query)
  const loading = useBin((s) => s.loading)
  const total = useBin((s) => s.total)
  const homes = useBin((s) => s.homes)
  const tile = useBin((s) => s.tile)
  const pins = useBin((s) => s.pins.length)
  const many = useBin((s) => s.selection.length)
  const focus = useBin((s) => s.items.findIndex((x) => x.asset.id === s.selected))
  const node = homeOf(useBin((s) => s.open))
  const inTrash = useBin((s) => s.open === TRASH)
  const [cols, setCols] = useState(1)
  const el = useRef<HTMLDivElement | null>(null)
  const over = useFileDrop(useCallback(() => el.current, []))
  const shown = query ? items.filter((x) => passes(x, filter)) : items        // a home's chips filter on the server; a search's here
  const open = (it: BinThing) => { useBin.getState().select(it.asset.id); useBin.getState().view(true) }
  return (
    <section className="w-centre">
      <div className={`w-bin${over ? ' file-over' : ''}`} data-testid="bin-grid" tabIndex={0} onKeyDown={(e) => gridKeys(e, cols)}>
        <div className="w-bin-head">
          <span className="w-path" title={path}>{query ? `search: ${query}` : path === TRASH ? 'trash' : `bin/${pathLabel(homes, path)}`}</span>
          {total !== null && !loading && <span className="hint" data-testid="bin-count">{query ? shown.length : total}</span>}
          {many > 1 && <span className="hint" data-testid="bin-selected">· {many} selected</span>}
          <span className="w-chips">{FILTERS.map(([f, l]) => <button key={f} className={filter === f ? 'active' : ''} onClick={() => useBin.getState().setFilter(f)}>{l}</button>)}</span>
          <span className="spacer" />
          {pins > 0 && <><CommandButton id="bin.compare" text label={`Compare ${pins}`} /><CommandButton id="bin.unpinAll" /></>}
          <CommandButton id="bin.selectAll" />
          <CommandButton id="bin.tileSmaller" /><CommandButton id="bin.tileLarger" />
          {inTrash ? <CommandButton id="bin.trash.empty" text className="quiet danger" /> : <CommandButton id="bin.import" />}
          <Help text="A click selects, Ctrl+click adds, Shift+click a range; the arrows move (Shift: a range). Enter opens where it belongs, Space shows it large, Delete trashes, C pins for compare. A file dropped from Windows lands in this home." />
        </div>
        {node?.gone && !query && <div className="b-gone" data-testid="bin-gone"><span>{node.name} was deleted</span><CommandButton id="bin.home.rehome" text /></div>}
        {shown.length ? <BinGrid items={shown} keyOf={keyOf} min={tile} focus={focus} onCols={setCols} gridRef={(x) => { el.current = x }}
          render={(it) => <BinTile it={it} menu={binMenu} onDouble={() => open(it)} />} onEnd={loadMore} />
          : <div className="w-empty" ref={(x) => { if (!items.length) el.current = x }}>{loading ? 'Reading the Bin…' : query ? 'Nothing found' : 'Nothing here'}</div>}
        <BinLoupe />
        <BinCompare />
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

type Use = { kind: 'version' | 'shot' | 'stage'; id: string; version: string | null; name: string; role: string }

/** Where a use opens: the version in World, the shot in Shots; a stage is named only (its shots are where it is used). */
function openUse(u: Use): void {
  if (u.kind === 'version') belongs(`world/character/${u.id}/${u.version ?? ''}`)?.open()
  else if (u.kind === 'shot') belongs(`shots/${u.id}/${u.version ?? ''}`)?.open()
}

/** B1 (11 §3): what a thing was made from and what came of it (a click opens that thing in its home), and the records that use it. */
function Lineage({ id }: { id: string }) {
  const [data, setData] = useState<{ id: string; parents: string[]; children: string[]; uses: Use[] } | null>(null)
  useEffect(() => {
    let dead = false
    void Promise.all([unwrap(http.GET('/lineage/{asset_id}', { params: { path: { asset_id: id } } })).catch(() => null),
      unwrap(http.GET('/bin/things/{aid}/uses', { params: { path: { aid: id } } })).catch(() => [])]).then(([l, uses]) => {
      if (dead) return
      setData({ id, parents: [...new Set((l?.parents ?? []).map((e) => e.from_id))], children: [...new Set((l?.children ?? []).map((e) => e.to_id))], uses: uses as Use[] })
    })
    return () => { dead = true }
  }, [id])
  if (!data || data.id !== id) return null
  const row = (label: string, list: string[], testid: string) => list.length > 0 && (
    <div className="b-lineage" data-testid={testid}><span>{label}</span><span className="b-thumbs">{list.slice(0, 8).map((x) => (
      <button key={x} className="b-thumb" title="open it in its home" onClick={() => void useBin.getState().reveal(x)}><img src={api.thumbUrl(x, 256)} alt="" /></button>))}
      {list.length > 8 && <span className="hint">+{list.length - 8}</span>}</span></div>)
  return (
    <>
      {row('made from', data.parents, 'bin-made-from')}
      {row('made into', data.children, 'bin-made-into')}
      {data.uses.length > 0 && <div className="kv b-uses" data-testid="bin-uses"><span>used by</span><span>{data.uses.map((u, i) => (
        <span key={`${u.kind}${u.id}${u.version}${u.role}`}>{i > 0 && '; '}{u.kind === 'stage'
          ? <>{u.name} ({ROLE_WORDS[u.role] ?? u.role})</>
          : <button className="link" onClick={() => openUse(u)} title={`open ${u.name}`}>{u.name}</button>}{u.kind !== 'stage' && ` (${ROLE_WORDS[u.role] ?? u.role})`}</span>))}</span></div>}
    </>
  )
}

function Inspector() {
  const selected = useBin((s) => s.selected)
  const items = useBin((s) => s.items)
  const homes = useBin((s) => s.homes)
  const many = useBin((s) => s.selection.length)
  const inTrash = useBin((s) => s.open === TRASH)
  const pinned = useBin((s) => s.pins.some((x) => x.id === s.selected))
  const it = items.find((x) => x.asset.id === selected) ?? null
  const bid = it?.asset.batch_id ?? null
  const [runs, setRuns] = useState<{ bid: string; n: number } | null>(null)          // the run's size, by its batch (another batch reads as none)
  useEffect(() => {
    if (bid) void unwrap(http.GET('/assets', { params: { query: { batch_id: bid, limit: 1 } } })).then((r) => setRuns({ bid, n: r.total ?? r.items.length })).catch(() => undefined)
  }, [bid])
  const run = runs && runs.bid === bid ? runs.n : null
  if (many > 1) {
    const list = selectedThings()
    return (
      <aside className="w-insp" data-testid="bin-inspector">
        <h4>{many} selected</h4>
        <div className="b-thumbs many">{list.slice(0, 12).map((x) => <img key={x.asset.id} src={api.thumbUrl(x.asset.id, 256)} alt="" />)}</div>
        <div className="w-verbs">
          {inTrash ? <><CommandButton id="bin.item.restore" text /><CommandButton id="bin.item.purge" text /></>
            : <><CommandButton id="bin.item.move" text /><CommandButton id="bin.item.tag" text /><CommandButton id="bin.item.duplicate" text /><CommandButton id="bin.item.trash" text /></>}
          <CommandButton id="bin.clearSelection" text />
        </div>
      </aside>
    )
  }
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
      <Lineage id={a.id} />
      <div className="w-verbs">
        {inTrash ? <><CommandButton id="bin.item.restore" text /><CommandButton id="bin.item.purge" text /></> : <>
          <CommandButton id="bin.item.open" text label={where ? `Open ${where.label} ▸` : undefined} />
          <CommandButton id="bin.item.view" text />
          <CommandButton id="bin.item.detach" text />
          <CommandButton id="bin.item.move" text />
          <CommandButton id="bin.item.tag" text />
          <CommandButton id="bin.item.duplicate" text />
          <CommandButton id="bin.item.pin" text label={pinned ? 'Unpin' : undefined} />
          {a.params?.recipe ? <><CommandButton id="bin.item.rerun" text /><CommandButton id="bin.item.variations" text /></> : null}
          <CommandButton id="bin.item.reveal" text />
          <CommandButton id="bin.item.trash" text />
        </>}
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
      <BinTree />
      <Grid />
      <Inspector />
    </div>
  )
}
