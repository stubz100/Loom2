// D95 (AN1, proto01_animate 04 C1, D99 UX0): the Bin — the Catalogue as a collapsible drawer of the Dock, beside the render queue, in Image and
// Animate. The places (Unprocessed, the Library, the album's groups), a type filter and the tiles; a tile drags to wherever it is used (the
// references, a start slot, a layer — frame/drag.ts), a double-click does the likely verb of the mode you are in, the right-click lists
// them all. It is the Catalogue's own store machinery on a store of its own (`useBin`), so the Catalogue and Image's results are untouched.
// proto01_UIcast CW0: a Meshes filter, a 3D model's own verbs (on the stage, as a Cast prop's model, its lineage) and a picture's Cast
// verbs (Add to Cast ▸, Make a character / place / prop…) — the Bin was the one place a picture had none.
import { UserRound } from 'lucide-react'
import { madeForIdea, prototypeMenu } from '../story/prototype'
import { useEffect, useMemo, useState } from 'react'
import type { Asset } from '../../api/types'
import { showMenu } from '../../frame/ContextMenu'
import { mediaOf } from '../../frame/drag'
import { editPresence } from '../../frame/editPresence'
import { command, sep, type MenuItem } from '../../frame/commands'
import { useSession } from '../../store/session'
import { addToCastMenu, madeFor } from '../story/addToCast'
import { castPropMenu } from '../story/castProp'
import { profilesForMentions } from '../story/storyStore'
import { useAlbum } from './albumStore'
import { startProfile } from './catalogueCommands'
import { useBin, type Query } from './catalogueStore'
import { openPlace, paneStore, useSplit } from './split'
import { Tile } from './Tile'

type Kind = Query['kind'] | undefined
const KINDS: [Kind, string][] = [[undefined, 'All'], ['image', 'Images'], ['video', 'Clips'], ['mesh', 'Meshes']]
const TILE = 128

const openInEdit = (id: string) => void import('../edit/editorStore').then((m) => m.useEditor.getState().openFromAsset(id))
const addLayer = (id: string) => void import('../edit/editorStore').then((m) => m.useEditor.getState().addLayerFromAsset(id))
const asReference = (id: string) => void import('../generate/generateStore').then((m) => m.useGenerate.getState().addRef(id))
const asStart = (id: string) => void import('../animate/animateStore').then((m) => m.useAnimate.getState().setStart(id, true))
const playClip = (a: Asset) => void import('../animate/animateStore').then(async (m) => {
  const clip = (a.params as { clip_id?: string } | undefined)?.clip_id
  const an = m.useAnimate.getState()
  useSession.getState().setSuite('animate')
  if (clip) { await an.loadClips(); an.select(clip) }
})

/** A Bin verb: a menu entry that is also the double-click; a pick started from a panel names one by `id` (session.ui.pick). */
interface Verb { id: string; label: string; run: () => void }

/** The verbs of a Bin tile, the mode's likely one first (the double-click). */
/** An image plane at the viewport's centre on the open stage (the stage's code loads with it; the Clay level has it loaded already). */
function addPlane(id: string): void {
  void Promise.all([import('../stage/stageStore'), import('../stage/stageCommands')]).then(([s, c]) => {
    if (!s.st().addObject('plane', null, c.viewport.centre?.() ?? [0, 0, 0], id)) useSession.getState().toast('Open a stage first (the Shot section)', 'info')
  })
}

/** SC3 (D120): the picture as a set on the open stage — MoGe's relief with the picture's camera (a job of seconds; the stage reloads with it). */
function setFromImage(id: string): void {
  void import('../stage/stageStore').then((s) => s.st().setFromImage(id))
}

/** proto01_UIcast CW0: a 3D model on the open stage at the viewport's centre (a loose mesh: Clay's Meshes). */
function addMesh(id: string): void {
  void Promise.all([import('../stage/stageStore'), import('../stage/stageCommands')]).then(([s, c]) => {
    if (!s.st().addObject('mesh', null, c.viewport.centre?.() ?? [0, 0, 0], id)) useSession.getState().toast('Open a stage first (the Shot section)', 'info')
  })
}

/** The Catalogue's lineage of an asset: what it was made from and what came of it. */
function showLineage(id: string): void {
  useSession.getState().setSuite('catalogue')
  const sp = useSplit.getState()
  const c = paneStore(sp.mode === 'single' ? 0 : sp.active).getState()
  openPlace(c, 'library'); c.openLineage(id)
}

/** The rest of a tile's right-click, after its verbs: a picture's Cast verbs, a 3D model's Cast prop. */
function castItems(a: Asset): MenuItem[] {
  if (a.trashed_at) return []
  if (a.kind === 'mesh') return [sep, castPropMenu(a)]
  if (a.kind !== 'image') return []
  return [sep, prototypeMenu([a.id], madeForIdea(a)), addToCastMenu(profilesForMentions(), madeFor(a), [a.id]),   // proto01_UIcast CW1: Prototype ▸
    { label: 'Make a profile from it', icon: UserRound, items: (['character', 'place', 'prop'] as const).map((cls): MenuItem => ({ label: `Make a ${cls}…`, run: () => startProfile(cls, a.id) })) }]
}

function verbs(a: Asset, suite: string): Verb[] {
  if (a.kind === 'video') return [{ id: 'play', label: 'Play in Animate', run: () => playClip(a) }]
  if (a.kind === 'mesh') return [...(suite === 'stage' ? [{ id: 'stage.mesh', label: 'Add to the stage (a 3D model)', run: () => addMesh(a.id) }] : []),
    { id: 'lineage', label: 'Show its lineage (Catalogue)', run: () => showLineage(a.id) }]
  if (a.kind !== 'image') return []
  const edit: Verb[] = suite === 'edit' && editPresence.hasDoc ? [{ id: 'edit.layer', label: 'Add as a layer', run: () => addLayer(a.id) }] : []
  const rest: Verb[] = [{ id: 'reference', label: 'Use as a reference (Image · Make)', run: () => asReference(a.id) }, { id: 'edit.open', label: 'Open in Image · Edit', run: () => openInEdit(a.id) },
    { id: 'start', label: 'Set as the start frame (Animate)', run: () => asStart(a.id) }]
  const first = suite === 'animate' || suite === 'stage' ? rest[2] : suite === 'generate' ? rest[0] : null
  const plane: Verb[] = suite === 'stage' ? [{ id: 'stage.plane', label: 'Add to the stage (image plane)', run: () => addPlane(a.id) }, { id: 'stage.set', label: 'Add to the stage (a set from this image)', run: () => setFromImage(a.id) }] : []   // D95 (AN1, UX0 #18): the Clay level's verb
  return [...edit, ...plane, ...(first ? [first] : []), ...rest.filter((x) => x !== first)]
}

export function Bin() {
  const project = useSession((s) => s.project)
  const suite = useSession((s) => s.ui.suite)
  const pick = useSession((s) => s.ui.pick) ?? null
  const q = useBin((s) => s.q)
  const items = useBin((s) => s.items)
  const total = useBin((s) => s.total)
  const loading = useBin((s) => s.loading)
  const tree = useAlbum((s) => s.tree)
  const [selected, setSelected] = useState<string | null>(null)
  useEffect(() => {
    if (!project?.open) return
    void useBin.getState().load()
    if (!useAlbum.getState().tree) void useAlbum.getState().load()
  }, [project?.path])
  const shown = useMemo(() => (q.kind ? items.filter((a) => a.kind === q.kind) : items), [items, q.kind])   // a new asset lands before the next load
  useEffect(() => {                                                       // Escape ends the pick (the ✕ in the bar is its mouse placement, D32); before any return (rules of hooks)
    if (!pick) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.preventDefault(); useSession.getState().setUi({ pick: null }) } }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [pick])
  if (!project?.open) return <span className="meta">No project open.</span>
  const place = q.group_id ?? q.folder
  const open = (p: string) => void useBin.getState().setQuery(p === 'unprocessed' || p === 'all' ? { folder: p, group_id: undefined } : { folder: 'all', group_id: p })
  const groups = tree?.children ?? []
  const first = (a: Asset) => verbs(a, suite)[0]
  // a pick started from a panel: the verb it names on each tile that has it — the corner button, and the double-click while it lasts
  const picked = (a: Asset): Verb | undefined => (pick ? verbs(a, suite).find((v) => v.id === pick.verb) : undefined)
  const PickIcon = pick ? command(pick.cmd)?.icon : undefined
  const endPick = () => useSession.getState().setUi({ pick: null })
  return (
    <div className="bin">
      <nav className="bin-places" aria-label="Bin places">
        <button className={place === 'unprocessed' ? 'active' : ''} onClick={() => open('unprocessed')}>Unprocessed</button>
        <button className={place === 'all' ? 'active' : ''} onClick={() => open('all')}>Library</button>
        {groups.length > 0 && <span className="bin-label">Album</span>}
        {groups.map((g) => <button key={g.id} className={place === g.id ? 'active' : ''} onClick={() => open(g.id)} title={`${g.assets} items`}>{g.name}<small>{g.assets}</small></button>)}
      </nav>
      <div className="bin-main">
        <div className="bin-bar">
          <span className="segmented" role="group" aria-label="Bin type">
            {KINDS.map(([k, label]) => <button key={label} className={q.kind === k ? 'active' : ''} onClick={() => void useBin.getState().setQuery({ kind: k })}>{label}</button>)}
          </span>
          <input type="search" aria-label="search the Bin" placeholder="search" value={q.search} onChange={(e) => void useBin.getState().setQuery({ search: e.target.value })} />
          <span className="meta">{loading ? 'loading…' : `${shown.length}${total != null && total > shown.length ? ` of ${total}` : ''}`}</span>
          <span className="spacer" />
          {pick
            ? <span className="meta picking">picking for: {pick.label} <button type="button" className="quiet" aria-label="stop picking" title="Stop picking (the tiles' corner buttons go)" onClick={endPick}>✕</button></span>
            : <span className="meta">drag a tile where it is used · double-click: {suite === 'stage' ? 'an image plane / a 3D model / play' : suite === 'animate' ? 'start frame / play' : suite === 'edit' ? 'a layer' : 'a reference'}</span>}
        </div>
        <div className="bin-grid" onContextMenu={(e) => { if (pick) { e.preventDefault(); endPick() } }}                 // a right-click ends the pick (on a tile the verbs still open)
          onScroll={(e) => { const el = e.currentTarget; if (el.scrollTop + el.clientHeight > el.scrollHeight - 200) void useBin.getState().loadMore() }}>
          {shown.map((a) => (
            <Tile key={a.id} a={a} size={TILE} fill caption="off" selected={selected === a.id} primary={selected === a.id} pinned={0}
              onClick={(_e, id) => setSelected(id)} onDouble={() => { const pv = picked(a); if (pv) { pv.run(); endPick() } else first(a)?.run() }} onContext={(e) => { e.preventDefault(); setSelected(a.id); if (pick) endPick(); showMenu(e, [...verbs(a, suite), ...castItems(a)]) }}
              corner={(() => { const pv = picked(a); return pv ? { icon: PickIcon ? <PickIcon size={13} /> : undefined, label: pv.label, run: () => { pv.run(); endPick() } } : undefined })()}
              dragItems={() => [{ kind: 'asset', id: a.id, media: mediaOf(a.kind) }]} />
          ))}
          {!loading && !shown.length && <span className="meta">Nothing here.</span>}
        </div>
      </div>
    </div>
  )
}
