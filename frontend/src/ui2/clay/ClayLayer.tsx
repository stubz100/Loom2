// C0 (D181, propo02 04 §4.3): Clay — the 3D of the story, in one place. The rail is Library · Scenes. The Library is the grid of the 3D
// assets by kind (figures, props, sets from World's entities; lights, cameras, animations), each with what it still needs; an asset opened
// has its builder in the left column (the body and its fit, shell and skeleton; a prop's model and height; a place's set builder — moved
// whole from World's Build) and its tiles behind it; Bench ▶ opens Clay for it in the centre (D142's bench, the line-up). Scenes is the
// editor on a scene (a stage), opened from a shot card with the way back. World = Make | Edit: its pictures and their roles.
import { Boxes, Clapperboard } from 'lucide-react'
import { lazy, Suspense, useEffect } from 'react'
import { api } from '../../api/client'
import type { Profile } from '../../api/types'
import { CommandButton, MenuButton } from '../../frame/CommandButton'
import { command, isEnabled, runCommand, type MenuItem } from '../../frame/commands'
import { Help } from '../../frame/Help'
import { useRailState } from '../../frame/router'
import { useSession } from '../../store/session'
import { useStory } from '../../suites/story/storyStore'
import { NoProject } from '../NoProject'
import { Part } from '../Part'
import { clayReadiness } from './readiness'
import { classOfKind, KINDS, shotsOnStage, startClay, useClay, useOpenScene, useScenes, type LibKind } from './clayStore'
import './clayCommands'
import '../world/world.css'
import './clay.css'

// the editor's parts load with the scene (three.js); the builders with the kind
const ClayColumn = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: ({ tab }: { tab: string }) => <m.ClayColumn tab={tab} /> })))
const ClayStrip = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: m.Strip })))
const ClayStage = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: m.Stage })))
const ClayFoot = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: m.ClayFoot })))
const SelectionInspector = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: m.SelectionInspector })))   // C1: one selected thing, one editor
const SkeletonBench = lazy(() => import('../../suites/stage/SkeletonBench'))
const SkeletonParts = lazy(() => import('../../suites/stage/SkeletonBench').then((m) => ({ default: m.SkeletonParts })))
const CastBody = lazy(() => import('../../suites/story/CastBody').then((m) => ({ default: m.CastBody })))
const PropModel = lazy(() => import('../../suites/story/CastParts').then((m) => ({ default: m.PropModel })))
const PlaceSetSection = lazy(() => import('../../suites/story/CastSet').then((m) => ({ default: m.PlaceSetSection })))
const MotionLibrary = lazy(() => import('../../suites/stage/motion/MotionLibrary').then((m) => ({ default: m.MotionLibrary })))

type Version = Profile['versions'][number]
const RAIL = [{ id: 'library', cmd: 'clay.rail.library', Icon: Boxes }, { id: 'scenes', cmd: 'clay.rail.scenes', Icon: Clapperboard }] as const

function Rail() {
  const rail = useClay((s) => s.rail)
  return <nav className="w-rail" aria-label="Clay">{RAIL.map(({ id, cmd, Icon }) => {
    const c = command(cmd)
    if (!c) return null
    return <button key={id} className={`w-rail-btn${rail === id ? ' active' : ''}`} title={c.hint ? `${c.label} — ${c.hint}` : c.label} aria-label={c.label} data-rail={id}
      disabled={!isEnabled(c)} onClick={() => runCommand(cmd)}><Icon size={18} /></button>
  })}</nav>
}

/** The kind's entity versions: a thumbnail (the hero, the set picture), the name and version, the readiness as chips. */
function thumbOf(p: Profile, v: Version): string | null {
  if (p.cls === 'place') return v.place_set?.sources[0]?.asset_id ?? v.anim_ref_asset_id ?? v.hero_asset_id ?? null
  return v.anim_ref_asset_id ?? v.hero_asset_id ?? null
}

function Tiles({ kind }: { kind: LibKind }) {
  const profiles = useStory((s) => s.profiles)
  const asset = useClay((s) => s.asset)
  const cls = classOfKind(kind)
  if (!cls) return <KindNote kind={kind} />
  const mine = profiles.filter((p) => p.cls === cls)
  if (!mine.length) return <div className="w-empty">No {KINDS.find((k) => k.id === kind)!.one} yet — make the {cls} in World first</div>
  return (
    <div className="c-tiles" data-testid="clay-tiles">
      {mine.map((p) => {
        const v = p.versions.find((x) => x.id === (asset?.profile === p.id ? asset.version : p.current)) ?? p.versions[0]
        const r = clayReadiness(p, v)
        const thumb = thumbOf(p, v)
        return (
          <button key={p.id} className={`c-tile${asset?.profile === p.id ? ' selected' : ''}`} data-id={p.id} title={`${p.name} ${v.id} — ${r.line}`} onClick={() => useClay.getState().openLibrary(kind, p.id, v.id)}>
            <span className="c-thumb">{thumb ? <img src={api.thumbUrl(thumb, 256)} alt="" draggable={false} /> : 'no picture yet'}</span>
            <span className="c-name">{p.name} <small>{v.id}</small></span>
            <span className="c-ready">{r.items.map((x) => <span key={x.id} className={x.state}>{x.state === 'done' ? '✓' : x.state === 'owed' ? '○' : '–'} {x.label}</span>)}</span>
            <span className={`c-line${r.owed ? '' : ' ok'}`}>{r.line}</span>
          </button>
        )
      })}
    </div>
  )
}

/** Lights, cameras and animations: what the kind holds and where it is used (their pages grow with C1–C2). */
function KindNote({ kind }: { kind: LibKind }) {
  if (kind === 'animation') return <div className="c-motion" data-testid="clay-motion"><Part label="The motion library" fallback={<div className="w-empty">Loading the library…</div>}><MotionLibrary /></Part></div>
  return <div className="c-kind-note" data-testid="clay-kind-note">{kind === 'light'
    ? 'Lights are added in a scene: the outliner\'s ＋ offers the templates (a window, the sun, a lamp…), and the light editor is under the light\'s row. Saved templates come here with C1.'
    : 'Cameras belong to scenes: one per shot, added in the outliner, its lens and height under its row. Lens presets come here with C1.'}</div>
}

function LibraryHeader() {
  const kind = useClay((s) => s.kind)
  const asset = useClay((s) => s.asset)
  const view = useClay((s) => s.view)
  const profiles = useStory((s) => s.profiles)
  const p = asset ? profiles.find((x) => x.id === asset.profile) : undefined
  const v = p ? p.versions.find((x) => x.id === asset!.version) ?? p.versions[0] : undefined
  const cls = classOfKind(kind)
  const entities = (): MenuItem[] => profiles.filter((x) => x.cls === cls).map((x) => ({ label: x.name, checked: x.id === p?.id, run: () => useClay.getState().openLibrary(kind, x.id, x.current) }))
  const versions = (): MenuItem[] => (p ? p.versions.map((x) => ({ label: `${x.id}${x.label && x.label !== x.id ? ` · ${x.label}` : ''}${x.state === 'final' ? ' · final' : ''}`, checked: x.id === v?.id, run: () => useClay.getState().openLibrary(kind, p.id, x.id) })) : [])
  const r = p && v ? clayReadiness(p, v) : null
  return (
    <div className="w-head" data-testid="clay-library-header">
      <div className="c-kinds" role="group" aria-label="the kind">{KINDS.map((k) => <button key={k.id} className={kind === k.id ? 'active' : ''} aria-pressed={kind === k.id} onClick={() => useClay.getState().setKind(k.id)}>{k.label}</button>)}</div>
      {cls && <div className="w-head-row">
        <MenuButton label={p ? p.name : `Pick a ${KINDS.find((k) => k.id === kind)!.one}`} items={entities} text />
        {p && v && <MenuButton label={`${v.id}${v.state === 'final' ? ' · final' : ''}`} items={versions} text />}
        <span className="spacer" />
        {view === 'bench' ? <CommandButton id="clay.bench.close" text /> : <><CommandButton id="clay.bench.open" text /><CommandButton id="clay.lineup" text /></>}
      </div>}
      {r && <div className="w-ready" data-testid="clay-readiness">
        {r.items.map((x) => <span key={x.id} className={`w-ready-item ${x.state}`} title={x.state === 'done' ? 'done' : x.state === 'owed' ? 'owed' : 'optional'}>
          {x.state === 'done' ? '✓' : x.state === 'owed' ? '○' : '–'} {x.label}{x.detail ? ` ${x.detail}` : ''}</span>)}
        <b className={`w-ready-line${r.owed ? '' : ' ok'}`}>{r.line}</b>
      </div>}
    </div>
  )
}

/** The asset's builder — World's Build, moved whole: the body with its fit, shell and skeleton; a prop's model and height; a place's set. */
function Builder({ p, v }: { p: Profile; v: Version }) {
  return (
    <div className="w-sheet cast-page" data-testid="clay-builder">
      {p.cls === 'character' && <Part label="The body" quiet="line"><section className="w-build-body"><h3>Body <Help text="The figure Clay draws the character with: its height, build and proportions fitted to the A-pose (a World picture), its shell (the 3D model of the A-pose) and its skeleton. The A-pose itself is made and picked in World." /></h3>
        <CastBody p={p} v={v} /><div className="w-verbs"><CommandButton id="cast.shell.make" text /><CommandButton id="cast.skeleton.open" text /></div></section></Part>}
      {p.cls === 'prop' && <Part label="The model" quiet="line"><PropModel p={p} v={v} /></Part>}
      {p.cls === 'place' && <Part label="The set" quiet="line" fallback={<section className="place-set" />}><PlaceSetSection p={p} v={v} /></Part>}
      <div className="w-verbs"><CommandButton id="clay.asset.world" text /></div>
    </div>
  )
}

/** The Inspector: the asset's facts — its entity, the scenes it stands in, its versions; the skeleton bench's parts while it is open. */
function LibraryInspector({ p, v }: { p: Profile | undefined; v: Version | undefined }) {
  const uses = useStory((s) => (p ? s.castUses[p.id]?.uses : undefined))
  const kind = useClay((s) => s.kind)
  useEffect(() => { if (p) void useStory.getState().loadCastUses() }, [p?.id])   // eslint-disable-line react-hooks/exhaustive-deps -- the entity's uses, read when it changes
  if (!p || !v) return <aside className="w-insp" data-testid="clay-inspector"><h4>{KINDS.find((k) => k.id === kind)!.label}</h4><span className="w-val">Pick one to see its 3D, or make the {classOfKind(kind) ?? 'thing'} in World first.</span></aside>
  const onStage = (uses ?? []).filter((u) => u.how.some((h) => h === 'figure' || h === 'prop' || h === 'place'))
  return (
    <aside className="w-insp" data-testid="clay-inspector">
      <h4>{p.name} <small>{v.id}</small></h4>
      <div className="w-facts"><span>in scenes</span>
        {onStage.length ? <ul>{onStage.map((u) => <li key={u.shot_id}><button className="link" title={`Open ${u.name}'s scene`} onClick={() => void import('../shots/shotsStore').then((m) => m.useShots.getState().open(u.shot_id, 'clay'))}>{u.name}</button><small> · {u.version}</small></li>)}</ul>
          : <span className="w-val">none yet</span>}</div>
      <div className="w-facts"><span>versions</span><ul>{p.versions.map((x) => <li key={x.id}><button className={`link${x.id === v.id ? ' active' : ''}`} onClick={() => useClay.getState().openLibrary(kind, p.id, x.id)}>{x.id}{x.label && x.label !== x.id ? ` · ${x.label}` : ''}</button>
        <small> · {x.state === 'final' ? 'final' : 'open'}{x.id === p.current ? ' · current' : ''}</small></li>)}</ul></div>
      <div className="w-verbs"><CommandButton id="clay.asset.world" text /></div>
    </aside>
  )
}

function Library() {
  const kind = useClay((s) => s.kind)
  const asset = useClay((s) => s.asset)
  const view = useClay((s) => s.view)
  const profiles = useStory((s) => s.profiles)
  const skeleton = useStory((s) => s.skeleton)
  const p = asset ? profiles.find((x) => x.id === asset.profile) : undefined
  const v = p ? p.versions.find((x) => x.id === asset!.version) ?? p.versions[0] : undefined
  const bench = view === 'bench'
  const skel = !bench && skeleton && p?.cls === 'character'
  return <>
    <section className="w-left" data-testid="clay-library">
      <LibraryHeader />
      <div className="w-panel">{bench ? <Suspense fallback={null}><ClayColumn tab="scene" /></Suspense> : p && v ? <Builder p={p} v={v} /> : <KindHint kind={kind} />}</div>
    </section>
    <section className="w-centre">
      {bench ? <Suspense fallback={<div className="w-empty">Loading Clay…</div>}><div className="strip w-edit-strip"><ClayStrip /></div><div className="w-edit-stage" data-testid="clay-bench"><ClayStage /></div></Suspense>
        : skel ? <Part label="The skeleton bench" fallback={<div className="w-empty">Loading the bench…</div>}><div className="w-skeleton" data-testid="clay-skeleton"><SkeletonBench /></div></Part>
        : <Tiles kind={kind} />}
    </section>
    {skel ? <Part label="The skeleton bench" quiet="hide" fallback={<aside className="w-insp" />}><aside className="w-insp"><SkeletonParts /></aside></Part>
      : bench ? <Part label="The selection" quiet="hide" fallback={<aside className="w-insp" />}><aside className="w-insp" data-testid="clay-inspector"><SelectionInspector /></aside></Part> : <LibraryInspector p={p} v={v} />}
  </>
}

function KindHint({ kind }: { kind: LibKind }) {
  const k = KINDS.find((x) => x.id === kind)!
  return <span className="hint">{k.cls ? `A ${k.one} is a ${k.cls} from World with its 3D made here. Pick one in the grid.` : k.id === 'animation' ? 'The clips a figure walks and stands with; applied on a figure\'s track in a scene.' : `${k.label} are made in a scene.`}</span>
}

/** Scenes: the scene open in the editor (a picker of the project's scenes with the shots each serves), the way back to the shot, then the
 *  editor's column and foot. */
function ScenesHeader() {
  const scene = useOpenScene()
  const scenes = useScenes(true)
  const shots = useStory((s) => s.shots)
  const nodes = useStory((s) => s.flowNodes)
  const from = useClay((s) => s.from)
  const label = (sh: { name: string; owner_node?: string | null }) => (sh.owner_node && nodes[sh.owner_node]?.title) || sh.name   // the storyboard's name for the shot
  const fromShot = from ? shots.find((s) => s.id === from.shot) : undefined
  const menu = (): MenuItem[] => [...scenes.map((s) => ({ label: `${s.name}${shotsOnStage(s.id, shots).length ? ` · ${shotsOnStage(s.id, shots).map(label).join(', ')}` : ''}`, checked: s.id === scene?.id, run: () => void useClay.getState().openScene(s.id, null) })),   // picked here: no shot to go back to
    { sep: true }, { cmd: 'stage.new' }]
  const on = scene ? shotsOnStage(scene.id, shots) : []
  return (
    <div className="w-head c-scene-head" data-testid="clay-scene-header">
      <div className="w-head-row">
        <MenuButton label={scene ? scene.name : scenes.length ? 'Pick a scene' : 'No scene yet'} items={menu} text />
        {scene && <span className="w-val">{((scene.range?.end ?? 120) - (scene.range?.start ?? 0)) / (scene.size?.fps ?? 24) > 0 ? `${(((scene.range?.end ?? 120) - (scene.range?.start ?? 0)) / (scene.size?.fps ?? 24)).toFixed(1)} s` : ''}</span>}
        <span className="spacer" />
        {from && <CommandButton id="clay.scene.back" text label={fromShot ? `← ${label(fromShot)}` : '← Back to the shot'} />}
      </div>
      {scene && <span className="c-scene-shots">{on.length ? `the camera of ${on.map(label).join(', ')}` : 'no shot on it yet'}{scene.purpose && scene.purpose !== 'stage' ? ` · ${scene.purpose}` : ''}</span>}
    </div>
  )
}

function Scenes() {
  const tab = useRailState((r) => r.active.stage) ?? 'scene'
  const project = useSession((s) => s.project)
  useEffect(() => { void useStory.getState().loadShots(); void useStory.getState().loadFlow() }, [project?.path])   // eslint-disable-line react-hooks/exhaustive-deps -- the shots on each scene, named by their nodes
  return <>
    <section className="w-left" data-testid="clay-scenes">
      <ScenesHeader />
      <div className="w-panel"><Suspense fallback={null}><ClayColumn tab={tab} /></Suspense></div>
      <div className="c-left-foot"><Suspense fallback={null}><ClayFoot /></Suspense></div>
    </section>
    <section className="w-centre">
      <Suspense fallback={<div className="w-empty">Loading Clay…</div>}><div className="strip w-edit-strip"><ClayStrip /></div><div className="w-edit-stage" data-testid="clay-scene"><ClayStage /></div></Suspense>
    </section>
    <Part label="The selection" quiet="hide" fallback={<aside className="w-insp" />}><aside className="w-insp" data-testid="clay-inspector"><SelectionInspector /></aside></Part>{/* C1 (26 §2 rule 3) */}
  </>
}

export function ClayLayer() {
  const rail = useClay((s) => s.rail)
  const project = useSession((s) => s.project)
  useEffect(() => startClay(), [])
  if (!project?.open) return <div className="w-layer"><Rail /><section className="w-centre wide"><NoProject /></section></div>
  return (
    <div className="w-layer c-layer" data-testid="clay-layer" data-rail={rail}>
      <Rail />
      {rail === 'library' ? <Library /> : <Scenes />}
    </div>
  )
}
