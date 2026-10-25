// The Inspector (D34, proto01_design/01 §6e): one scrolling column with collapsible sections instead of tabs — Tags,
// Location, Actions, Lineage, Prompt, Details — for one asset, or the bulk subset for several. The single home for the actions
// on the selection (the strip carries none); ids appear only under Details.
import { BookOpen, ChevronDown, ChevronRight, Clapperboard, Columns2, Copy, ExternalLink, Film, FolderInput, GitBranch, Image, Images, Inbox, Layers, MoreHorizontal, Package, Pencil, Pin, RotateCcw, Shuffle, Trash, Undo, Ungroup, UserRoundPlus, Wand2, X } from 'lucide-react'
import { useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api, http, unwrap } from '../../api/client'
import type { Asset, LineageTree } from '../../api/types'
import { showMenu } from '../../frame/ContextMenu'
import { command, isEnabled, markUsed, runCommand, titleFor, type MenuItem } from '../../frame/commands'
import { useKeymap } from '../../frame/keymap'
import { CommandCard } from '../../frame/CommandButton'
import { askText, useSession } from '../../store/session'
import { UsedBy } from './UsedBy'
import { useMakeFor } from '../../store/origin'
import { confirmDeleteGroup, confirmUngroup } from './groupUsers'
import { useAlbum, type PathStep } from './albumStore'
import { addToCharacterMenu, moveToMenu, forFrame, frameUseLabel } from './catalogueCommands'
import { castPropMenu } from '../story/castProp'
import { CatalogueStoreCtx, useCat } from './catalogueContext'
import { selectedOrPrimary } from './catalogueStore'
import { notePlacements } from './placement'
import { openInOtherPane, openPlaceFrom, type Place } from './split'

// ---------------------------------------------------------------- shared bits
const usePrefs = create<{ closed: Record<string, boolean>; toggle: (k: string) => void }>()(persist((set, get) => ({
  closed: { prompt: true, details: true },
  toggle: (k) => set({ closed: { ...get().closed, [k]: !get().closed[k] } }),
}), { name: 'loom2.inspector' }))

function Section({ id, title, right, children, fold = false }: { id: string; title: string; right?: ReactNode; children: ReactNode; fold?: boolean }) {
  const closed = usePrefs((s) => !!s.closed[id])
  const toggle = usePrefs((s) => s.toggle)
  return (
    <section className={`isec${fold ? ' fold' : ''}`}>
      <div className="isec-head">
        {fold ? <button className="isec-toggle" aria-expanded={!closed} onClick={() => toggle(id)}>{closed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}{title}</button> : <span className="isec-title">{title}</span>}
        {right && <span className="isec-right">{right}</span>}
      </div>
      {(!fold || !closed) && children}
    </section>
  )
}

/** D90 (B13): the Inspector's place links — in the Catalogue, its own pane; hosted by Generate, the Catalogue's active pane (the suite switches). */
function useOpenPlace(): (place: Place) => void {
  const host = useContext(CatalogueStoreCtx)
  return (place) => openPlaceFrom(host, place)
}
/** D90 (B17): "Back to Unprocessed" is the command, enabled by its one predicate (every selected asset placed). */
function ToUnprocessed() {
  const cmd = command('cat.toUnprocessed')
  return <Btn icon={<Inbox size={14} />} label="Back to Unprocessed" run={() => runCommand('cat.toUnprocessed')} disabled={!cmd || !isEnabled(cmd)} title="Back to Unprocessed (Shift+Delete): off its group page" />
}

/** "today 14:02", "yesterday 09:10", "7 Oct 14:02", "7 Oct 2025". */
export function relTime(iso: string): string {
  const d = new Date(iso), now = new Date()
  const hm = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  const day = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  const diff = (day(now) - day(d)) / 86_400_000
  if (diff === 0) return `today ${hm}`
  if (diff === 1) return `yesterday ${hm}`
  return d.getFullYear() === now.getFullYear() ? `${d.toLocaleDateString([], { day: 'numeric', month: 'short' })} ${hm}` : d.toLocaleDateString([], { day: 'numeric', month: 'short', year: 'numeric' })
}

/** D90 (01 §11.2): an Inspector button bound to a registry command (enabled by its `when`, its key in the tooltip, marked for the audit). */
function CmdBtn({ id, icon, label }: { id: string; icon?: ReactNode; label?: string }) {
  useKeymap((k) => k.version)
  const cmd = command(id)
  if (!cmd) return null
  markUsed(id)
  return <Btn icon={icon} label={label ?? cmd.label} run={() => runCommand(id)} disabled={!isEnabled(cmd)} title={titleFor(cmd, cmd.hint ? `${label ?? cmd.label}: ${cmd.hint}` : undefined)} />
}

function Btn({ icon, label, run, disabled, danger, title }: { icon?: ReactNode; label: string; run: (e: React.MouseEvent) => void; disabled?: boolean; danger?: boolean; title?: string }) {
  return <button className={`ibtn${danger ? ' danger' : ''}`} disabled={disabled} title={title ?? label} onClick={run}>{icon}<span>{label}</span></button>
}

function Tags({ ids, shared, recs }: { ids: string[]; shared: string[]; recs: Asset[] }) {
  const c = useCat()
  const [text, setText] = useState('')
  const add = (t: string) => {
    t = t.trim()
    if (!t) return
    for (const r of recs) if (!r.tags.includes(t)) void c.setTags([r.id], [...r.tags, t])
    setText('')
  }
  const remove = (t: string) => { for (const r of recs) if (r.tags.includes(t)) void c.setTags([r.id], r.tags.filter((x) => x !== t)) }
  return (
    <div className="chips tags-edit">
      {shared.map((t) => <span key={t} className="chip-f">{t}<button aria-label={`Remove tag ${t}`} onClick={() => remove(t)}><X size={11} /></button></span>)}
      <input id="insp-tag" type="text" list="tag-suggest" value={text} placeholder={ids.length > 1 ? `add to all ${ids.length}` : 'add tag'} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') add(text) }} />
      <datalist id="tag-suggest">{c.tagCloud.map((t) => <option key={t.tag} value={t.tag} />)}</datalist>
    </div>
  )
}

function useLocations(ids: string[]): Record<string, { group_id: string; path: PathStep[] } | null> | null {
  const [loc, setLoc] = useState<Record<string, { group_id: string; path: PathStep[] } | null> | null>(null)
  const tree = useAlbum((s) => s.tree)                                // refetch when placements change
  const key = ids.join(',')
  useEffect(() => {
    if (!ids.length) { setLoc(null); return }
    let live = true
    void unwrap(http.GET('/groups/where', { params: { query: { ids: ids.slice(0, 200) } } }))
      .then((r) => { if (live) { notePlacements(r); setLoc(r) } }).catch(() => { if (live) setLoc(null) })
    return () => { live = false }
  }, [key, tree]) // eslint-disable-line react-hooks/exhaustive-deps
  return loc
}

function Crumbs({ path }: { path: PathStep[] }) {
  const open = useOpenPlace()
  return (
    <span className="crumbs-i">
      <BookOpen size={13} />
      {path.map((p, i) => <span key={p.id}>{i > 0 && <span className="sep">›</span>}<button className="link" onClick={() => open({ group: p.id })}>{p.name}</button></span>)}
    </span>
  )
}

// ---------------------------------------------------------------- lineage path

function LineagePath({ a }: { a: Asset }) {
  const c = useCat()
  const [tree, setTree] = useState<LineageTree | null>(null)
  const root = a.root_id ?? a.id
  useEffect(() => {
    let live = true
    void unwrap(http.GET('/lineage/tree/{root_id}', { params: { path: { root_id: root } } })).then((t) => { if (live) setTree(t) }).catch(() => { if (live) setTree(null) })
    return () => { live = false }
  }, [root, a.id])
  const { chain, children, size } = useMemo(() => {
    if (!tree) return { chain: [] as { id: string; kind: string | null }[], children: 0, size: 0 }
    const parentOf = new Map(tree.edges.map((e) => [e.to_id, e]))
    const chain: { id: string; kind: string | null }[] = []
    let cur: string | undefined = a.id
    const seen = new Set<string>()
    while (cur && !seen.has(cur)) { seen.add(cur); const e = parentOf.get(cur); chain.unshift({ id: cur, kind: e?.kind ?? null }); cur = e?.from_id }
    return { chain, children: tree.edges.filter((e) => e.from_id === a.id).length, size: tree.items.length }
  }, [tree, a.id])
  if (!tree) return <span className="muted">…</span>
  if (size <= 1) return <span className="muted">An original, no derivations yet{a.duplicate_of ? ' (a duplicate)' : ''}.</span>
  return (
    <>
      <div className="lin-path">
        {chain.map((n, i) => (
          <span key={n.id} className="lin-step">
            {i > 0 && <span className="lin-kind">{n.kind} ›</span>}
            <button className={n.id === a.id ? 'here' : ''} title={n.id === a.id ? 'this one' : 'select'} onClick={() => { if (n.id !== a.id) c.select(n.id, 'single') }}>
              <img src={api.thumbUrl(n.id, 256)} alt="" />
            </button>
          </span>
        ))}
      </div>
      <div className="muted">{children ? `${children} derivation${children === 1 ? '' : 's'} from this one · ` : ''}{size} in the whole tree</div>
    </>
  )
}

// ---------------------------------------------------------------- prompt and details
function PromptBody({ a }: { a: Asset }) {
  const [json, setJson] = useState(false)
  const pj = a.prompt_json as Record<string, unknown> | null
  const scene = typeof pj?.scene === 'string' ? pj.scene : a.prompt_text
  const rest = pj ? Object.entries(pj).filter(([k, v]) => k !== 'scene' && v !== null && v !== '' && !(Array.isArray(v) && !v.length)) : []
  if (!scene && !pj) return <span className="muted">No prompt (imported or derived without one).</span>
  return (
    <>
      {scene && <p className="scene">{scene}</p>}
      {!json && rest.length > 0 && <div className="pj-rest">{rest.map(([k, v]) => <div key={k}><span className="k">{k}</span> {typeof v === 'string' ? v : JSON.stringify(v)}</div>)}</div>}
      {json && <pre className="json">{pj ? JSON.stringify(pj, null, 2) : a.prompt_text}</pre>}
      <div className="row-btns">
        {pj && <button className="link" onClick={() => setJson(!json)}>{json ? 'Hide JSON' : 'JSON'}</button>}
        <button className="link" onClick={() => { void navigator.clipboard?.writeText(pj ? JSON.stringify(pj, null, 2) : a.prompt_text ?? ''); useSession.getState().toast('Prompt copied', 'success') }}>Copy</button>
      </div>
    </>
  )
}

function Mono({ v }: { v: string }) {
  return <span className="mono-copy"><span className="mono">{v}</span><button className="link" onClick={() => { void navigator.clipboard?.writeText(v); useSession.getState().toast('Copied', 'success') }}>copy</button></span>
}

function DetailsBody({ a }: { a: Asset }) {
  const p = a.params as Record<string, unknown>
  const rows: [string, ReactNode][] = []
  const add = (k: string, v: unknown) => { if (v !== undefined && v !== null && v !== '') rows.push([k, typeof v === 'object' ? JSON.stringify(v) : String(v)]) }
  add('model', `${a.model_id ?? '—'}${a.variant ? ` · ${a.variant}` : ''}`)
  add('seed', a.seed)
  for (const k of ['steps', 'guidance', 'cfg', 'sampler', 'scheduler', 'denoise', 'turbo', 'te_id', 'recipe']) add(k === 'te_id' ? 'encoder' : k, p?.[k])
  add('size', `${a.w ?? '?'}×${a.h ?? '?'}${a.frames ? ` · ${a.frames} frames` : ''}${a.bytes ? ` · ${(a.bytes / 2 ** 20).toFixed(1)} MB` : ''}`)
  if (a.timings?.wall_s !== undefined) add('time', `${a.timings.wall_s} s`)
  add('created', new Date(a.created_at).toLocaleString())
  add('source', a.suite)
  if (a.duplicate_of) rows.push(['duplicate of', <Mono key="dup" v={a.duplicate_of} />])
  if (a.trashed_at) add('trashed', new Date(a.trashed_at).toLocaleString())
  rows.push(['asset', <Mono key="asset" v={a.id} />])
  if (a.job_id) rows.push(['job', <Mono key="job" v={a.job_id} />])
  if (a.session_id) rows.push(['session', <Mono key="session" v={a.session_id} />])
  if (a.compiled_graph_hash) rows.push(['graph', <Mono key="graph" v={a.compiled_graph_hash} />])
  return <dl className="kv">{rows.map(([k, v]) => <div key={k} className="kv-row"><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
}

// ---------------------------------------------------------------- the panel
function actionsMore(a: Asset): MenuItem[] {
  return [{ cmd: 'cat.loupe' }, { cmd: 'cat.showRecipe' }, { cmd: 'cat.reveal' }, { label: 'Copy prompt', icon: Copy, run: () => { void navigator.clipboard?.writeText(a.prompt_json ? JSON.stringify(a.prompt_json, null, 2) : a.prompt_text ?? ''); useSession.getState().toast('Prompt copied', 'success') } },
    { sep: true }, ...(a.trashed_at ? [{ cmd: 'cat.restore' }, { cmd: 'cat.purge' }] : [{ cmd: 'cat.trash' }])]
}

function One({ a }: { a: Asset }) {
  const c = useCat()
  const ids = [a.id]
  const loc = useLocations(ids)
  const here = loc?.[a.id]
  const open = useOpenPlace()
  useMakeFor((f) => f.generate)                                      // D125 (I2): the For chip's shot names the frame button
  return (
    <div className="insp">
      <img className="insp-thumb" src={api.thumbUrl(a.id, 512)} alt="" onDoubleClick={() => runCommand('cat.loupe')} />
      {a.kind === 'audio' && <audio className="insp-audio" controls src={api.assetUrl(a.id)} aria-label="the spoken line" />}
      <div className="meta-line">{a.model_id ?? a.suite} · {a.kind === 'audio' ? `${a.duration_s ?? '?'} s` : a.kind === 'mesh' ? '3D model' : `${a.w}×${a.h}`} · {relTime(a.created_at)}</div>
      <Section id="tags" title="Tags"><Tags ids={ids} shared={a.tags} recs={[a]} /></Section>
      <Section id="location" title="Location">
        <div className="loc">{a.trashed_at ? <span className="muted">In Trash{here ? ' (back on its page when restored)' : ''}</span> : here ? <Crumbs path={here.path} /> : <span className="crumbs-i"><Inbox size={13} /><button className="link" onClick={() => open('unprocessed')}>Unprocessed</button></span>}</div>
        {!a.trashed_at && <div className="row-btns">
          <Btn icon={<FolderInput size={14} />} label="Move to group" run={(e) => { const m = moveToMenu(); showMenu(e, 'items' in m ? m.items : []) }} />
          {here && <ToUnprocessed />}
          <Btn icon={<Copy size={14} />} label="Duplicate" run={() => runCommand('cat.duplicate')} title="Duplicate (Ctrl+D): a second copy you can place elsewhere" />
        </div>}
      </Section>
      <Section id="actions" title="Actions">
        {a.kind === 'mesh' ? <div className="igrid">{/* proto01_UIcast CF9: a 3D model's own verbs */}
          {!a.trashed_at && <Btn icon={<Package size={14} />} label="Make it a Cast prop ▾" run={(e) => showMenu(e, castPropMenu(a).items)} title="A new Cast prop with this model, or this model for a prop you have (its picture becomes a new prop's hero)" />}
          <Btn icon={<MoreHorizontal size={14} />} label="More ▾" run={(e) => showMenu(e, actionsMore(a))} />
        </div> : <div className="igrid">
          {forFrame() && a.kind === 'image' && <CmdBtn id="cat.useFrame" icon={<Clapperboard size={14} />} label={frameUseLabel()} />}
          <Btn icon={<Pencil size={14} />} label="Edit" run={() => runCommand('cat.edit')} title="Open in Edit (E)" />
          <Btn icon={<Film size={14} />} label="Animate ▾" run={(e) => showMenu(e, [{ cmd: 'cat.animate' }, { cmd: 'cat.animateEnd' }])} />
          <Btn icon={<Images size={14} />} label="Reference" run={() => runCommand('cat.reference')} title="Use as reference in Image (R)" />
          <Btn icon={<RotateCcw size={14} />} label="Re-run" run={() => runCommand('cat.rerun')} disabled={!a.params?.recipe} title="Re-run with the same seed (Ctrl+R)" />
          <Btn icon={<Shuffle size={14} />} label="Variations" run={() => runCommand('cat.variations')} disabled={!a.params?.recipe} title="New seeds (V)" />
          <CmdBtn id="cat.loadInGenerate" icon={<Wand2 size={14} />} label="Load in Image" />
          <Btn icon={<Pin size={14} />} label={c.compare.includes(a.id) ? 'Unpin' : 'Pin for compare'} run={() => runCommand('cat.pin')} title={c.compare.includes(a.id) ? `Unpin (C${c.compare.indexOf(a.id) + 1}, C)` : 'Pin for compare (C)'} />
          {a.kind === 'image' && !a.trashed_at && <Btn icon={<UserRoundPlus size={14} />} label="Add to Cast ▾" run={(e) => showMenu(e, addToCharacterMenu().items)} title="Into a Cast character, prop or place: as the hero, into the reference set or as a candidate (D93)" />}
          <Btn icon={<MoreHorizontal size={14} />} label="More ▾" run={(e) => showMenu(e, actionsMore(a))} />
        </div>}
      </Section>
      {a.kind === 'image' && <Section id="start" title="Start from this image">
        <div className="quick-cards compact">
          <CommandCard id="cat.start.removeBg" label="Select subject" hint="Edit · AI Select · Subject" />
          <CommandCard id="cat.start.upscale" label="Upscale" hint="Edit · AI Upscale" />
          <CommandCard id="cat.start.angle" label="New angle" hint="Generate · Angle" />
          <CommandCard id="cat.start.mesh" label="3D prop" hint="Pixal3D · a background job" />
          <CommandCard id="cat.start.character" label="Character" hint="Story · Cast — the hero of a profile" />
          <CommandCard id="cat.start.place" label="Place" hint="Story · Cast" />
          <CommandCard id="cat.start.prop" label="Prop" hint="Story · Cast" />
          <CommandCard id="cat.animate" label="Animate from this frame" hint="the start frame" />
        </div>
      </Section>}
      <Section id="lineage" title="Lineage" right={<button className="link" onClick={() => c.openLineage(a.id)}><GitBranch size={12} /> Open tree</button>}><LineagePath a={a} /></Section>
      <Section id="prompt" title="Prompt" fold><PromptBody a={a} /></Section>
      <Section id="details" title="Details" fold><DetailsBody a={a} /></Section>
    </div>
  )
}

function Many({ recs }: { recs: Asset[] }) {
  const c = useCat()
  const ids = recs.map((r) => r.id)
  const loc = useLocations(ids)
  const shared = recs.length ? recs[0].tags.filter((t) => recs.every((r) => r.tags.includes(t))) : []
  const places = loc ? new Set(ids.map((i) => loc[i]?.group_id ?? '')) : null
  const onePage = places && places.size === 1 && [...places][0] ? [...places][0] : null
  const groupThese = () => void askText({ title: 'Group these', text: `${ids.length} items become a group on this page, keeping their layout.`, placeholder: 'group name' })
    .then((n) => { if (n?.trim() && onePage) void unwrap(http.POST('/groups/{gid}/group', { params: { path: { gid: onePage } }, body: { items: ids.map((id) => ({ kind: 'asset' as const, id })), name: n.trim() } })).then(() => useAlbum.getState().load()) })
  return (
    <div className="insp">
      <div className="stack">{recs.slice(0, 3).reverse().map((r, i) => <img key={r.id} src={api.thumbUrl(r.id, 256)} alt="" style={{ transform: `translate(${(2 - i) * 16}px, ${(2 - i) * 10}px)` }} />)}</div>
      <div className="meta-line"><b>{recs.length} selected</b></div>
      <Section id="tags" title="Tags they share"><Tags ids={ids} shared={shared} recs={recs} /></Section>
      <Section id="location" title="Location">
        <div className="loc">{!loc ? '…' : onePage ? <Crumbs path={loc[ids[0]]!.path} /> : places!.size === 1 ? <span className="crumbs-i"><Inbox size={13} />all in Unprocessed</span> : <span className="muted">in {places!.size} places</span>}</div>
        <div className="row-btns">
          {onePage && <button className="primary" onClick={groupThese}><Layers size={14} /> Group these</button>}
          <Btn icon={<FolderInput size={14} />} label="Move to group" run={(e) => { const m = moveToMenu(); showMenu(e, 'items' in m ? m.items : []) }} />
          {places && !places.has('') && <ToUnprocessed />}
          <Btn icon={<Copy size={14} />} label="Duplicate" run={() => runCommand('cat.duplicate')} />
        </div>
      </Section>
      <Section id="actions" title="Actions">
        <div className="igrid">
          <Btn icon={<Images size={14} />} label="Reference" run={() => runCommand('cat.reference')} />
          <Btn icon={<Image size={14} />} label="Open in loupe" run={() => runCommand('cat.loupe')} />
          {c.q.folder === 'trash'
            ? <><Btn icon={<Undo size={14} />} label="Restore" run={() => runCommand('cat.restore')} /><Btn icon={<Trash size={14} />} label="Delete…" danger run={() => runCommand('cat.purge')} /></>
            : <Btn icon={<Trash size={14} />} label="Move to trash" danger run={() => runCommand('cat.trash')} />}
          <Btn icon={<ExternalLink size={14} />} label="Clear selection" run={() => c.clearSelection()} />
        </div>
      </Section>
    </div>
  )
}

function Card({ gid }: { gid: string }) {
  const open = useOpenPlace()
  const tree = useAlbum((s) => s.tree)
  const node = useMemo(() => useAlbum.getState().find(gid), [tree, gid]) // eslint-disable-line react-hooks/exhaustive-deps
  const path = useMemo(() => useAlbum.getState().pathOf(gid), [tree, gid]) // eslint-disable-line react-hooks/exhaustive-deps
  const [name, setName] = useState(node?.name ?? '')
  useEffect(() => setName(node?.name ?? ''), [node?.name])
  if (!node) return <span className="muted">…</span>
  const al = useAlbum.getState()
  const save = () => { if (name.trim() && name.trim() !== node.name) void al.rename(gid, name.trim()) }
  return (
    <div className="insp">
      <div className="stack">{node.cover_ids.slice(0, 3).reverse().map((id, i, arr) => <img key={id} src={api.thumbUrl(id, 256)} alt="" style={{ transform: `translate(${(arr.length - 1 - i) * 16}px, ${(arr.length - 1 - i) * 10}px)` }} />)}</div>
      <label className="gname">Group name<input type="text" value={name} onChange={(e) => setName(e.target.value)} onBlur={save} onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }} /></label>
      <div className="meta-line">{node.total} photo{node.total === 1 ? '' : 's'}{node.groups ? ` · ${node.groups} group${node.groups === 1 ? '' : 's'} inside` : ''} · cover: {node.cover_ids.length ? 'first on the page' : 'none yet'}</div>
      <Section id="location" title="Location"><div className="loc"><Crumbs path={path.slice(0, -1)} /></div></Section>
      <Section id="usedby" title="Used by"><div className="loc"><UsedBy gid={gid} /></div></Section>
      <Section id="group" title="Group">
        <div className="igrid">
          <Btn icon={<BookOpen size={14} />} label="Open" run={() => open({ group: gid })} />
          <Btn icon={<Columns2 size={14} />} label="Open in other pane" run={() => openInOtherPane({ group: gid })} />
          <Btn icon={<Ungroup size={14} />} label="Ungroup" run={() => void confirmUngroup(node).then((ok) => { if (ok) void al.ungroup(gid) })} title="Dissolve the group: its items land where its card was (Ctrl+Shift+G)" />
          <Btn icon={<Copy size={14} />} label="Duplicate" run={() => void al.duplicate(gid)} title="A copy of the group, its photos duplicated" />
          <Btn icon={<X size={14} />} label="Delete group…" danger run={() => void confirmDeleteGroup(node).then((ok) => { if (ok) void al.remove(gid) })} />
        </div>
        <div className="muted">To set the cover, right-click a photo on the group's page: "Use as cover of this group".</div>
      </Section>
    </div>
  )
}

export function Inspector() {
  const c = useCat()
  const s = useSession()
  const [remote, setRemote] = useState<Asset | null>(null)
  const id = c.primary
  const local = id ? c.byId(id) : undefined
  useEffect(() => {
    if (id && !local) void unwrap(http.GET('/assets/{asset_id}', { params: { path: { asset_id: id } } })).then(setRemote).catch(() => setRemote(null)); else setRemote(null)
  }, [id, local])
  if (!s.project?.open) return <span className="muted">No project.</span>
  if (c.groupSel.length === 1 && !c.selected.length) return <Card gid={c.groupSel[0]} />
  if (c.groupSel.length > 1 && !c.selected.length) return <span className="muted">{c.groupSel.length} groups selected · drag them onto another group, or right-click for more</span>
  const ids = selectedOrPrimary(c)
  if (ids.length > 1) {
    const recs = ids.map((i) => c.byId(i)).filter(Boolean) as Asset[]
    return recs.length > 1 ? <Many recs={recs} /> : <span className="muted">{ids.length} selected</span>
  }
  const a = local ?? (remote?.id === id ? remote : null)
  if (!a) return <span className="muted">Select a photo to see its details and actions here.</span>
  return <One a={a} />
}

