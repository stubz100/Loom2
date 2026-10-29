// U3 (D157, proto01_UI2 03): World — the entities, made and readied for Clay. The rail picks the class (or Look, Sketches), the header the
// entity and its version, the centre is the version's bin (one grid, roles as badges and filters), the Inspector the selected creation.
// U3a: the frame, the header, the bin and the Inspector; Make and Edit come into the left column in U3b.
import { Box, MapPin, Palette, PenLine, User } from 'lucide-react'
import { lazy, Suspense, useEffect } from 'react'
import { api } from '../../api/client'
import { CommandButton, MenuButton } from '../../frame/CommandButton'
import { command, isEnabled, runCommand, type MenuItem } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { useSession } from '../../store/session'
import type { Profile } from '../../api/types'
import { navigate } from '../../frame/router'
import { useStory, voiceLabel, type ProfileClass } from '../../suites/story/storyStore'
import { readiness } from './readiness'
import { WorldMake } from './WorldMake'
import { CLASSES, CLASS_LABEL, ONE, passes, startWorld, useWorld, type BinItem, type RoleFilter, type WorldRail } from './worldStore'
import './worldCommands'
import './world.css'

// U3c: the editor loads on the first Edit (its Pixi code stays out of World until then)
// U3f: the bench's Clay parts and the voices block load with their use
const BenchColumn = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: () => <m.ClayColumn tab="scene" /> })))
const BenchStrip = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: m.Strip })))
const BenchStage = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: m.Stage })))
const Voices = lazy(() => import('../../suites/story/VoicesBlock').then((m) => ({ default: m.VoicesBlock })))
/** A built set's sizes in metres (width × depth × height, as the set builder gives them). */
const setSizes = (z: Record<string, number> | undefined): string => { const d = ['w', 'd', 'h'].map((k) => z?.[k]).filter((x): x is number => typeof x === 'number'); return d.length ? ` · ${d.map((x) => x.toFixed(1)).join(' × ')} m` : '' }

const EditColumn = lazy(() => import('./WorldEdit').then((m) => ({ default: m.WorldEditColumn })))
const EditCentre = lazy(() => import('./WorldEdit').then((m) => ({ default: m.WorldEditCentre })))
const EditInspector = lazy(() => import('./WorldEdit').then((m) => ({ default: m.WorldEditInspector })))
// U3d: Look and Sketches (the style editor and Image's whole column load with them)
const LookColumn = lazy(() => import('./WorldLook').then((m) => ({ default: m.LookColumn })))
const LookCentre = lazy(() => import('./WorldLook').then((m) => ({ default: m.LookCentre })))
const LookInspector = lazy(() => import('./WorldLook').then((m) => ({ default: m.LookInspector })))
const SketchColumn = lazy(() => import('./WorldSketches').then((m) => ({ default: m.SketchColumn })))
const SketchCentre = lazy(() => import('./WorldSketches').then((m) => ({ default: m.SketchCentre })))
const SketchInspector = lazy(() => import('./WorldSketches').then((m) => ({ default: m.SketchInspector })))

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
  const voices = useStory((s) => s.voices)
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
        <span className="spacer" /><CommandButton id="world.mode.clay" text /><CommandButton id="world.entity.new" />
      </div>
      <label className="w-field"><span>appearance</span><textarea rows={2} value={v.appearance} disabled={!open} aria-label="appearance" placeholder="face, hair, build — the words every picture of it carries" onChange={(e) => sheet({ appearance: e.target.value })} /></label>
      {p.cls === 'character' && <label className="w-field"><span>outfit</span><textarea rows={1} value={v.outfit} disabled={!open} aria-label="outfit" onChange={(e) => sheet({ outfit: e.target.value })} /></label>}
      {p.cls === 'character' && <div className="w-field"><span>body</span><span className="w-val">{(v.body?.height_m ?? 1.75).toFixed(2)} m · {v.body_fit_from ? 'fitted ✓' : 'not fitted'}</span></div>}
      {p.cls === 'character' && <div className="w-field"><span>voice</span><span className="w-val w-voice">
        <select aria-label="speaks with" value={p.voice_id ?? ''} onChange={(e) => void useStory.getState().patchProfile({ voice_id: e.target.value || null })}>
          <option value="">(no voice)</option>{voices.map((x) => <option key={x.id} value={x.id}>{voiceLabel(x)}</option>)}
        </select><CommandButton id="story.cast.newVoice" text /></span></div>}
      {p.cls === 'prop' && <div className="w-field"><span>3D model</span><span className="w-val">{v.model_asset_id ? `made${v.height_m ? ` · ${v.height_m} m` : ''}` : 'not made yet'} <CommandButton id="story.cast.importModel" text label="Import GLB…" /></span></div>}
      {p.cls === 'place' && <div className="w-field"><span>the set</span><span className="w-val">{v.place_set ? `${v.place_set.kind}${setSizes(v.place_set.sizes)} · ${v.place_set.faces.length} faces` : 'not built yet'}</span></div>}
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

/** U3f (03 §5): the entity's facts — the shots that use it (and how), its versions (a click opens one), its voice, *Delete…*. */
function EntityFacts({ p, binCount }: { p: Profile; binCount: number }) {
  const uses = useStory((s) => s.castUses[p.id]?.uses)
  const vid = useStory((s) => s.versionId)
  useEffect(() => { void useStory.getState().loadCastUses(); void useStory.getState().loadVoices() }, [p.id])
  const HOW: Record<string, string> = { speaker: 'speaks', place: 'its place', figure: 'on its stage', prop: 'on its stage' }
  return (
    <aside className="w-insp" data-testid="world-inspector">
      <h4>{p.name}</h4>
      <div className="kv"><span>in the bin</span><span>{binCount}</span></div>
      <div className="w-facts" data-testid="world-uses"><span>used in shots</span>
        {uses?.length ? <ul>{uses.map((u) => <li key={u.shot_id}><button className="link" title={`Open ${u.name} in Shots`} onClick={() => { navigate({ suite: 'story', tab: 'flow' }); void import('../shots/shotsStore').then((m) => m.useShots.getState().open(u.shot_id, 'clay')) }}>{u.name}</button>
          <small> · {u.how.map((h) => HOW[h] ?? h).join(', ')} · {u.version}</small></li>)}</ul> : <span className="w-val">none yet</span>}</div>
      <div className="w-facts"><span>versions</span><ul>{p.versions.map((x) => <li key={x.id}><button className={`link${x.id === vid ? ' active' : ''}`} onClick={() => useWorld.getState().pick(p.id, x.id)}>
        {x.id}{x.label && x.label !== x.id ? ` · ${x.label}` : ''}</button><small> · {x.state === 'final' ? 'final' : 'open'}{x.id === p.current ? ' · current' : ''}</small></li>)}</ul></div>
      {p.cls === 'character' && <Suspense fallback={null}><Voices p={p} /></Suspense>}
      <div className="w-verbs"><CommandButton id="story.cast.delete" text label={`Delete ${p.name}…`} /></div>
    </aside>
  )
}

function Inspector() {
  const bin = useWorld((s) => s.bin)
  const selected = useWorld((s) => s.selected)
  const p = useStory((s) => s.profiles.find((x) => x.id === s.profileId))
  const it = bin?.items.find((x) => x.asset.id === selected)
  if (!p) return <aside className="w-insp" />
  if (!it) return <EntityFacts p={p} binCount={bin?.items.length ?? 0} />
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

function ModeSwitch() {
  const mode = useWorld((s) => s.mode)
  return <div className="w-mode segmented" role="group" aria-label="Make, Edit or Clay">
    <button className={mode === 'make' ? 'active' : ''} onClick={() => runCommand('world.mode.make')}>Make</button>
    <button className={mode === 'edit' ? 'active' : ''} disabled={mode !== 'edit' && !isEnabled(command('world.mode.edit')!)} title="Edit the selected creation" onClick={() => runCommand('world.mode.edit')}>Edit</button>
    <button className={mode === 'clay' ? 'active' : ''} disabled={mode !== 'clay' && !isEnabled(command('world.mode.clay')!)} title={command('world.mode.clay')?.hint} onClick={() => runCommand('world.mode.clay')}>Clay</button>
  </div>
}

export function WorldLayer() {
  const rail = useWorld((s) => s.rail)
  const mode = useWorld((s) => s.mode)
  const project = useSession((s) => s.project)
  useEffect(() => startWorld(), [])
  if (!project?.open) return <div className="w-layer"><Rail /><section className="w-centre wide"><div className="w-empty">Open or create a project</div></section></div>   // nothing reads before there is one
  const classRail = rail !== 'look' && rail !== 'sketches'
  return (
    <div className="w-layer" data-testid="world-layer">
      <Rail />
      {classRail ? <>
        <section className="w-left"><Header /><ModeSwitch /><div className="w-panel">{mode === 'edit' ? <Suspense fallback={null}><EditColumn /></Suspense> : mode === 'clay' ? <Suspense fallback={null}><BenchColumn /></Suspense> : <WorldMake />}</div></section>
        <section className="w-centre">{mode === 'edit' ? <Suspense fallback={<div className="w-empty">Loading the editor…</div>}><EditCentre /></Suspense>
          : mode === 'clay' ? <Suspense fallback={<div className="w-empty">Loading Clay…</div>}><div className="strip w-edit-strip"><BenchStrip /></div><div className="w-edit-stage" data-testid="world-clay"><BenchStage /></div></Suspense> : <Bin />}</section>
        {mode === 'edit' ? <Suspense fallback={<aside className="w-insp" />}><EditInspector /></Suspense> : <Inspector />}
      </> : <Suspense fallback={<section className="w-centre wide"><div className="w-empty">Loading…</div></section>}>
        {rail === 'look' ? <><section className="w-left"><div className="w-panel"><LookColumn /></div></section><section className="w-centre"><LookCentre /></section><LookInspector /></>
          : <><section className="w-left"><SketchColumn /></section><section className="w-centre"><SketchCentre /></section><SketchInspector /></>}
      </Suspense>}
    </div>
  )
}
