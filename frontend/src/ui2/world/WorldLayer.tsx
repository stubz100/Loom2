// U3 (D157, proto01_UI2 03): World — the entities, made and readied for Clay. The rail picks the class (or Look, Sketches), the header the
// entity and its version, the centre is the version's bin (one grid, roles as badges and filters), the Inspector the selected creation.
// U3a: the frame, the header, the bin and the Inspector; Make and Edit come into the left column in U3b.
import { Box, MapPin, Palette, PenLine, User } from 'lucide-react'
import { lazy, Suspense, useEffect } from 'react'
import { api } from '../../api/client'
import { CommandButton, MenuButton } from '../../frame/CommandButton'
import { command, isEnabled, runCommand, type MenuItem } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { Help } from '../../frame/Help'
import { useStory, type ProfileClass } from '../../suites/story/storyStore'
import { readiness } from './readiness'
import { WorldMake } from './WorldMake'
import { CLASSES, CLASS_LABEL, ONE, passes, startWorld, useWorld, type BinItem, type RoleFilter, type WorldRail } from './worldStore'
import './worldCommands'
import './world.css'

// U3c: the editor loads on the first Edit (its Pixi code stays out of World until then)
const EditColumn = lazy(() => import('./WorldEdit').then((m) => ({ default: m.WorldEditColumn })))
const EditCentre = lazy(() => import('./WorldEdit').then((m) => ({ default: m.WorldEditCentre })))
const EditInspector = lazy(() => import('./WorldEdit').then((m) => ({ default: m.WorldEditInspector })))

const RAIL_ICON: Record<WorldRail, typeof User> = { character: User, prop: Box, place: MapPin, look: Palette, sketches: PenLine }
/** 03 §2: an item is its verb — the Cast command that makes it (they act on the entity the header shows: the Story store's selection). */
const READY_VERB: Record<string, string> = { a_pose_front: 'story.cast.makeAnimRef', a_pose_back: 'story.cast.makeAnimRefBack', body: 'story.cast.fitBody', model: 'story.cast.makeModel',
  set_picture: 'cast.place.picture', set: 'cast.place.build', faces: 'cast.place.fill' }
const BADGE: Record<string, string> = { hero: '★', reference: 'ref', a_pose_front: 'A·F', a_pose_back: 'A·B', set_picture: 'set', model: '3D' }
const FILTERS: [RoleFilter, string][] = [['all', 'all'], ['hero', 'hero'], ['reference', 'references'], ['a_pose', 'A-pose'], ['set_picture', 'set'], ['model', 'model'], ['candidate', 'candidates']]

function Rail() {
  const rail = useWorld((s) => s.rail)
  const entry = (r: WorldRail, label: string) => {
    const Icon = RAIL_ICON[r]
    return <button key={r} className={`w-rail-btn${rail === r ? ' active' : ''}`} title={label} aria-label={label} onClick={() => useWorld.getState().setRail(r)}><Icon size={18} /></button>
  }
  return <nav className="w-rail" aria-label="World">{CLASSES.map((c) => entry(c, CLASS_LABEL[c]))}<span className="w-rail-sep" />{entry('look', 'Look')}{entry('sketches', 'Sketches')}</nav>
}

function Header() {
  const rail = useWorld((s) => s.rail)
  const profiles = useStory((s) => s.profiles)
  const p = useStory((s) => s.profiles.find((x) => x.id === s.profileId))
  const vid = useStory((s) => s.versionId)
  const bin = useWorld((s) => s.bin)
  const cls = rail as ProfileClass
  const mine = profiles.filter((x) => x.cls === cls)
  const entities = (): MenuItem[] => [...mine.map((x) => ({ label: x.name, checked: x.id === p?.id, run: () => useWorld.getState().pick(x.id) })), { sep: true }, { cmd: 'world.entity.new', label: `New ${ONE[cls]}…` }]
  if (!p) return (
    <div className="w-head">
      <div className="w-head-row"><MenuButton label={mine.length ? `Pick a ${ONE[cls]}` : `No ${ONE[cls]} yet`} items={entities} text /><CommandButton id="world.entity.new" /></div>
    </div>
  )
  const v = p.versions.find((x) => x.id === vid) ?? p.versions[0]
  const versions = (): MenuItem[] => [...p.versions.map((x) => ({ label: `${x.id}${x.label && x.label !== x.id ? ` · ${x.label}` : ''}${x.state === 'final' ? ' · final' : ''}`, checked: x.id === v.id, run: () => useWorld.getState().pick(p.id, x.id) })),
    { sep: true }, { cmd: 'world.version.new' }, { cmd: 'world.version.final' }]
  const refs = bin?.items.filter((x) => x.roles.includes('reference') || x.roles.includes('hero')).length ?? 0
  const r = readiness(p, v, refs)
  const open = v.state === 'open'
  const sheet = useStory.getState().setSheet
  return (
    <div className="w-head" data-testid="world-header">
      <div className="w-head-row">
        <MenuButton label={p.name} items={entities} text />
        <MenuButton label={`${v.id}${v.label && v.label !== v.id ? ` · ${v.label}` : ''}${v.state === 'final' ? ' · final' : ''}`} items={versions} text />
        <span className="spacer" /><CommandButton id="world.entity.new" />
      </div>
      <label className="w-field"><span>appearance</span><textarea rows={2} value={v.appearance} disabled={!open} aria-label="appearance" placeholder="face, hair, build — the words every picture of it carries" onChange={(e) => sheet({ appearance: e.target.value })} /></label>
      {p.cls === 'character' && <label className="w-field"><span>outfit</span><textarea rows={1} value={v.outfit} disabled={!open} aria-label="outfit" onChange={(e) => sheet({ outfit: e.target.value })} /></label>}
      {p.cls === 'character' && <div className="w-field"><span>body</span><span className="w-val">{(v.body?.height_m ?? 1.75).toFixed(2)} m · {v.body_fit_from ? 'fitted ✓' : 'not fitted'}</span></div>}
      {p.cls === 'prop' && <div className="w-field"><span>3D model</span><span className="w-val">{v.model_asset_id ? `made${v.height_m ? ` · ${v.height_m} m` : ''}` : 'not made yet'}</span></div>}
      {p.cls === 'place' && <div className="w-field"><span>the set</span><span className="w-val">{v.place_set ? `${v.place_set.kind} · ${v.place_set.faces.length} faces` : 'not built yet'}</span></div>}
      <div className="w-ready" data-testid="world-readiness">
        {r.items.map((x) => {
          const verb = READY_VERB[x.id], c = verb ? command(verb) : undefined
          const text = <>{x.state === 'done' ? '✓' : x.state === 'owed' ? '○' : '–'} {x.label}{x.detail ? ` ${x.detail}` : ''}</>
          return c && x.state !== 'done' ? <button key={x.id} className={`w-ready-item ${x.state}`} disabled={!isEnabled(c)} title={c.label} onClick={() => runCommand(verb!)}>{text}</button>
            : <span key={x.id} className={`w-ready-item ${x.state}`} title={x.state === 'done' ? 'done' : x.state === 'owed' ? 'owed' : 'optional'}>{text}</span>
        })}
        <b className={`w-ready-line${r.owed ? '' : ' ok'}`}>{r.line}</b>
      </div>
    </div>
  )
}

function Tile({ it }: { it: BinItem }) {
  const sel = useWorld((s) => s.selected === it.asset.id)
  const badge = it.roles.map((r) => BADGE[r]).find(Boolean)
  const menu = (): MenuItem[] => [{ cmd: 'world.mode.edit' }, { sep: true }, { cmd: 'world.creation.hero' }, { cmd: 'world.creation.reference' }, { cmd: 'world.creation.candidate' }, { sep: true }, { cmd: 'world.creation.trash' }]
  return (
    <button className={`w-tile${sel ? ' selected' : ''}`} data-id={it.asset.id} title={it.asset.prompt_text ?? ''} onClick={() => useWorld.getState().select(it.asset.id)}
      onContextMenu={(e) => { useWorld.getState().select(it.asset.id); showMenu(e, menu()) }}>
      <img src={api.thumbUrl(it.asset.id, 256)} alt="" draggable={false} />
      {badge && <span className="w-badge">{badge}</span>}
    </button>
  )
}

function Bin() {
  const p = useStory((s) => s.profiles.find((x) => x.id === s.profileId))
  const bin = useWorld((s) => s.bin)
  const filter = useWorld((s) => s.filter)
  const loading = useWorld((s) => s.loading)
  if (!p) return <div className="w-empty">Pick or make one in the header.</div>
  const items = (bin?.items ?? []).filter((x) => passes(x, filter))
  return (
    <div className="w-bin" data-testid="world-bin">
      <div className="w-bin-head">
        <span className="w-path" title={bin?.path ?? ''}>bin/world/{p.cls}/{p.name}/{useStory.getState().versionId}</span>
        <span className="w-chips">{FILTERS.map(([f, l]) => <button key={f} className={filter === f ? 'active' : ''} onClick={() => useWorld.getState().setFilter(f)}>{l}</button>)}</span>
      </div>
      {items.length ? <div className="w-grid">{items.map((it) => <Tile key={it.asset.id} it={it} />)}</div>
        : <div className="w-empty">{loading ? 'Reading the bin…' : filter === 'all' ? 'Nothing made yet' : 'Nothing with this role'}</div>}
    </div>
  )
}

function Inspector() {
  const bin = useWorld((s) => s.bin)
  const selected = useWorld((s) => s.selected)
  const p = useStory((s) => s.profiles.find((x) => x.id === s.profileId))
  const it = bin?.items.find((x) => x.asset.id === selected)
  if (!p) return <aside className="w-insp" />
  if (!it) return (
    <aside className="w-insp" data-testid="world-inspector">
      <h4>{p.name}</h4>
      <div className="kv"><span>versions</span><span>{p.versions.length}</span></div>
      <div className="kv"><span>in the bin</span><span>{bin?.items.length ?? 0}</span></div>
    </aside>
  )
  return (
    <aside className="w-insp" data-testid="world-inspector">
      <img className="w-preview" src={api.thumbUrl(it.asset.id, 512)} alt="" />
      <div className="kv"><span>roles</span><span>{it.roles.join(' · ') || '—'}</span></div>
      {it.asset.prompt_text && <div className="w-prompt-block"><span>prompt</span><p className="w-prompt" title={it.asset.prompt_text}>{it.asset.prompt_text}</p></div>}
      <div className="w-verbs">
        <CommandButton id="world.mode.edit" text /><CommandButton id="world.creation.hero" text /><CommandButton id="world.creation.reference" text /><CommandButton id="world.creation.candidate" text /><CommandButton id="world.creation.trash" text />
      </div>
    </aside>
  )
}

/** What Look and Sketches say until U3d builds them. */
function Pending({ what }: { what: string }) {
  return <div className="w-empty">{what} — not built yet <Help text="U3d (proto01_UI2 03 §6, §7): the project's styles with their sample scene, and the pictures that belong to no one yet." /></div>
}

function ModeSwitch() {
  const mode = useWorld((s) => s.mode)
  return <div className="w-mode segmented" role="group" aria-label="Make or Edit">
    <button className={mode === 'make' ? 'active' : ''} onClick={() => runCommand('world.mode.make')}>Make</button>
    <button className={mode === 'edit' ? 'active' : ''} disabled={mode !== 'edit' && !isEnabled(command('world.mode.edit')!)} title="Edit the selected creation" onClick={() => runCommand('world.mode.edit')}>Edit</button>
  </div>
}

export function WorldLayer() {
  const rail = useWorld((s) => s.rail)
  const mode = useWorld((s) => s.mode)
  useEffect(() => startWorld(), [])
  const classRail = rail !== 'look' && rail !== 'sketches'
  return (
    <div className="w-layer" data-testid="world-layer">
      <Rail />
      {classRail ? <>
        <section className="w-left"><Header /><ModeSwitch /><div className="w-panel">{mode === 'edit' ? <Suspense fallback={null}><EditColumn /></Suspense> : <WorldMake />}</div></section>
        <section className="w-centre">{mode === 'edit' ? <Suspense fallback={<div className="w-empty">Loading the editor…</div>}><EditCentre /></Suspense> : <Bin />}</section>
        {mode === 'edit' ? <Suspense fallback={<aside className="w-insp" />}><EditInspector /></Suspense> : <Inspector />}
      </> : <section className="w-centre wide"><Pending what={rail === 'look' ? 'Look' : 'Sketches'} /></section>}
    </div>
  )
}
