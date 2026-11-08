// U3 (D157, proto01_UI2 03): World — the entities, made and readied for Clay. The rail picks the class (or Look, Sketches), the header the
// entity and its version (and what it still owes; the author, 2026-10-29: its description is the Sheet's, its voice the Inspector's), the
// centre is the version's bin (one grid, roles as badges and filters), the Inspector the selected creation.
// U3a: the frame, the header, the bin and the Inspector; Make and Edit come into the left column in U3b.
import { Box, MapPin, Palette, PenLine, User } from 'lucide-react'
import { lazy, memo, Suspense, useEffect } from 'react'
import { api } from '../../api/client'
import { CommandButton, MenuButton } from '../../frame/CommandButton'
import { command, isEnabled, runCommand, type MenuItem } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { useSession } from '../../store/session'
import type { Profile } from '../../api/types'
import { navigate } from '../../frame/router'
import { useStory, type ProfileClass } from '../../suites/story/storyStore'
import { Part } from '../Part'
import { PromptBlock } from '../PromptBlock'
import { readiness, type ReadyItem } from './readiness'
import { WorldMake } from './WorldMake'
import { CLASSES, CLASS_LABEL, ONE, passes, startWorld, useWorld, type BinItem, type RoleFilter, type WorldRail } from './worldStore'
import './worldCommands'
import './world.css'
import { NoProject } from '../NoProject'

// U3c: the editor loads on the first Edit (its Pixi code stays out of World until then); the voices block with its use. C0 (D181): the
// bench, the skeleton bench and Build's 3D (the body, the model, the set) live in Clay's Library now — World = Make | Edit.
const Voices = lazy(() => import('../../suites/story/VoicesBlock').then((m) => ({ default: m.VoicesBlock })))

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
// D161 → C0: a picture item opens Make, whose A-pose section makes and picks it (a click here queues nothing); the 3D is Clay's Library
const READY_VERB: Record<string, string> = { ...Object.fromEntries(['a_pose_front', 'a_pose_back', 'a_pose_side', 'hand_picture', 'feet_picture', 'reference', 'set_picture'].map((k) => [k, 'world.mode.make'])),
  carried: 'world.carried.prop', tpose: 'world.mode.make' }                            // M4; W11
/** M3, M4: what a warning chip says on hover. */
const warnTitle = (x: ReadyItem) => (x.id === 'tpose'
  ? 'The A-pose holds its arms level (a T-pose), not about 30° out: the fit took it, but the shell and Wan Animate follow the arms as drawn — make candidates in Make\'s A-pose section'
  : x.id === 'carried'
  ? `${x.detail}: the A-pose leaves it out (its hands open, no props), so a performance has it only from the words and it comes and goes — a click makes it a Cast prop, which Clay's Hold ▸ puts in the hand`
  : `${x.detail} — made before the sheet said so: make it again, or set the colour back`)
const BADGE: Record<string, string> = { hero: '★', reference: 'ref', a_pose_front: 'A·F', a_pose_back: 'A·B', a_pose_side: 'A·S', hand_picture: 'hand', feet_picture: 'feet', set_picture: 'set', model: '3D' }
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
  const prompt = (role: string) => bin?.items.find((x) => x.roles.includes(role))?.asset.prompt_text ?? null
  const r = readiness(p, v, refs, { hero: prompt('hero'), a_pose_front: prompt('a_pose_front') })   // M3: what the pictures were made with
  return (
    <div className="w-head" data-testid="world-header">
      <div className="w-head-row">
        <MenuButton label={p.name} items={entities} text />
        <MenuButton label={`${v.id}${v.label && v.label !== v.id ? ` · ${v.label}` : ''}${v.state === 'final' ? ' · final' : ''}`} items={versions} text />
        <span className="spacer" /><CommandButton id="clay.asset.open" text /><CommandButton id="world.entity.new" />
      </div>
      <div className="w-ready" data-testid="world-readiness">
        {r.items.map((x) => {
          const verb = READY_VERB[x.id], c = verb ? command(verb) : undefined
          if (x.state === 'warn') return c ? <button key={x.id} className="w-ready-item warn" data-ready={x.id} disabled={!isEnabled(c)} title={warnTitle(x)} onClick={() => runCommand(verb!)}>⚠ {x.label}</button>
            : <span key={x.id} className="w-ready-item warn" data-ready={x.id} title={warnTitle(x)}>⚠ {x.label}</span>
          const text = <>{x.state === 'done' ? '✓' : x.state === 'owed' ? '○' : '–'} {x.label}{x.detail ? ` ${x.detail}` : ''}</>
          return c && x.state !== 'done' ? <button key={x.id} className={`w-ready-item ${x.state}`} disabled={!isEnabled(c)} title={`${x.label}: in Make, below the sheet`} onClick={() => runCommand(verb!)}>{text}</button>
            : <span key={x.id} className={`w-ready-item ${x.state}`} title={x.state === 'done' ? 'done' : x.state === 'owed' ? 'owed' : 'optional'}>{text}</span>
        })}
        <b className={`w-ready-line${r.owed ? '' : ' ok'}`}>{r.line}</b>
      </div>
    </div>
  )
}

/** K83: a tile re-draws only when its own item or selection changes — a sheet keystroke re-rendered the whole grid. */
const Tile = memo(function Tile({ it }: { it: BinItem }) {
  const sel = useWorld((s) => s.selected === it.asset.id)
  const badge = it.roles.map((r) => BADGE[r]).find(Boolean)
  const menu = (): MenuItem[] => [{ cmd: 'world.mode.edit' }, { sep: true }, { cmd: 'world.creation.hero' }, { cmd: 'world.creation.reference' }, { cmd: 'world.creation.candidate' },
    { cmd: 'world.creation.aposeFront' }, { cmd: 'world.creation.aposeBack' }, { cmd: 'world.creation.aposeSide' }, { cmd: 'world.creation.handPicture' }, { cmd: 'world.creation.feetPicture' }, { cmd: 'world.creation.setPicture' }, { sep: true }, { cmd: 'world.creation.trash' }, { cmd: 'world.creation.back' }]
  return (
    <button className={`w-tile${sel ? ' selected' : ''}`} data-id={it.asset.id} title={it.asset.prompt_text ?? ''} onClick={() => useWorld.getState().select(sel ? null : it.asset.id)}
      onContextMenu={(e) => { useWorld.getState().select(it.asset.id); showMenu(e, menu()) }}>
      <img src={api.thumbUrl(it.asset.id, 256)} alt="" draggable={false} />
      {badge && <span className="w-badge">{badge}</span>}
    </button>
  )
})

function Bin() {
  const cls = useStory((s) => s.profiles.find((x) => x.id === s.profileId)?.cls)      // K83: the class and name, not the profile (a sheet keystroke)
  const name = useStory((s) => s.profiles.find((x) => x.id === s.profileId)?.name)
  const vid = useStory((s) => s.versionId)
  const bin = useWorld((s) => s.bin)
  const filter = useWorld((s) => s.filter)
  const loading = useWorld((s) => s.loading)
  if (!cls) return <div className="w-empty">Pick or make one in the header.</div>
  const items = (bin?.items ?? []).filter((x) => passes(x, filter))
  return (
    <div className="w-bin" data-testid="world-bin" onClick={(e) => { const t = e.target as HTMLElement; if (t === e.currentTarget || t.classList.contains('w-grid')) useWorld.getState().select(null) }}>{/* W12: a click around the pictures */}
      <div className="w-bin-head">
        <span className="w-path" title={bin?.path ?? ''}>bin/world/{cls}/{name}/{vid}</span>
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
        {uses?.length ? <ul>{uses.map((u) => <li key={u.shot_id}><button className="link" title={`Open ${u.name} in Shots`} onClick={() => { navigate({ suite: 'story', tab: 'flow' }); void import('../shots/shotsStore').then((m) => m.useShots.getState().open(u.shot_id, 'performance')) }}>{u.name}</button>
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
      <div className="w-verbs"><CommandButton id="world.creation.back" text label={`Back to ${p.name}`} /></div>{/* W12 */}
      <img className="w-preview" src={api.thumbUrl(it.asset.id, 512)} alt="" />
      <div className="kv"><span>roles</span><span>{it.roles.join(' · ') || '—'}</span></div>
      {it.asset.prompt_text && <PromptBlock text={it.asset.prompt_text} />}{/* W6, W13 */}
      <div className="w-verbs">
        <CommandButton id="world.mode.edit" text /><CommandButton id="world.creation.hero" text /><CommandButton id="world.creation.reference" text /><CommandButton id="world.creation.candidate" text /><CommandButton id="world.creation.trash" text />
      </div>
    </aside>
  )
}

function ModeSwitch() {
  const mode = useWorld((s) => s.mode)
  useWorld((s) => s.selected)                                              // W59: Edit follows the picked picture
  return <div className="w-mode segmented" role="group" aria-label="Make or Edit">
    <button className={mode === 'make' ? 'active' : ''} onClick={() => runCommand('world.mode.make')}>Make</button>
    <button className={mode === 'edit' ? 'active' : ''} disabled={mode !== 'edit' && !isEnabled(command('world.mode.edit')!)} title="Edit the selected creation" onClick={() => runCommand('world.mode.edit')}>Edit</button>
  </div>
}

export function WorldLayer() {
  const rail = useWorld((s) => s.rail)
  const mode = useWorld((s) => s.mode)
  const project = useSession((s) => s.project)
  useEffect(() => startWorld(), [])
  if (!project?.open) return <div className="w-layer"><Rail /><section className="w-centre wide"><NoProject /></section></div>   // nothing reads before there is one
  const classRail = rail !== 'look' && rail !== 'sketches'
  const freeEdit = !classRail && mode === 'edit'                                    // B2a: a picture that is no entity's, in the editor
  return (
    <div className="w-layer" data-testid="world-layer">
      <Rail />
      {classRail ? <>
        <section className="w-left"><Header /><ModeSwitch /><div className="w-panel">{mode === 'edit' ? <Part label="Edit" quiet="line"><EditColumn /></Part> : <WorldMake />}</div></section>
        <section className="w-centre">{mode === 'edit' ? <Part label="Edit" fallback={<div className="w-empty">Loading the editor…</div>}><EditCentre /></Part> : <Bin />}</section>
        {mode === 'edit' ? <Part label="Edit" quiet="hide" fallback={<aside className="w-insp" />}><EditInspector /></Part> : <Inspector />}
      </> : freeEdit ? <>
        <section className="w-left"><div className="w-panel"><Part label="Edit" quiet="line"><EditColumn /></Part></div></section>
        <section className="w-centre"><Part label="Edit" fallback={<div className="w-empty">Loading the editor…</div>}><EditCentre /></Part></section>
        <Part label="Edit" quiet="hide" fallback={<aside className="w-insp" />}><EditInspector /></Part>
      </> : <Suspense fallback={<section className="w-centre wide"><div className="w-empty">Loading…</div></section>}>
        {rail === 'look' ? <><section className="w-left"><div className="w-panel"><LookColumn /></div></section><section className="w-centre"><LookCentre /></section><LookInspector /></>
          : <><section className="w-left"><SketchColumn /></section><section className="w-centre"><SketchCentre /></section><SketchInspector /></>}
      </Suspense>}
    </div>
  )
}
