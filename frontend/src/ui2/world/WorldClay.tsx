// RS1 (D197, proto02 01 §4.2): World › Clay — the entity's 3D, where the entity is. The third mode beside Make and Edit, for the version in
// the header: a character's Figure (the body fitted to the A-pose, the shell), Skeleton (the rigging screen, D190), Poses (its own poses,
// made on the bench) and the bench's own things; a prop's Model; a place's Set. Moved whole from Clay's Library (C0, D181), which keeps the
// animations. The centre is the bench — the entity alone on a floor in Clay's own engine (D142's bench stage) — or the skeleton screen;
// an entity with nothing to stand on a bench yet shows its bin, and so does a place's Set (its bench is made when asked for, D142).
import { lazy, Suspense, useEffect } from 'react'
import { http, unwrap } from '../../api/client'
import type { Profile } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { Help } from '../../frame/Help'
import { useSession } from '../../store/session'
import { useStory } from '../../suites/story/storyStore'
import { Part } from '../Part'
import { benchShown, CLAY_TABS, useWorld } from './worldStore'

// the bench's parts load with it (three.js); the builders with the class
const ClayColumn = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: ({ tab }: { tab: string }) => <m.ClayColumn tab={tab} /> })))
const ClayStrip = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: m.Strip })))
const ClayStage = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: m.Stage })))
const SelectionInspector = lazy(() => import('../../suites/stage/StageParts').then((m) => ({ default: m.SelectionInspector })))
const SkeletonBench = lazy(() => import('../../suites/stage/SkeletonBench'))
const SkeletonParts = lazy(() => import('../../suites/stage/SkeletonBench').then((m) => ({ default: m.SkeletonParts })))
const RigPanel = lazy(() => import('../../suites/stage/RigPanel'))
const CastBody = lazy(() => import('../../suites/story/CastBody').then((m) => ({ default: m.CastBody })))
const PropModel = lazy(() => import('../../suites/story/CastParts').then((m) => ({ default: m.PropModel })))
const MeshRunForm = lazy(() => import('../../suites/story/MeshRunForm').then((m) => ({ default: m.MeshRunForm })))   // RS2: the shell's run form
const PlaceSetSection = lazy(() => import('../../suites/story/CastSet').then((m) => ({ default: m.PlaceSetSection })))

type Version = Profile['versions'][number]
const useEntity = (): { p: Profile | undefined; v: Version | undefined } => {
  const p = useStory((s) => s.profiles.find((x) => x.id === s.profileId))
  const vid = useStory((s) => s.versionId)
  return { p, v: p ? p.versions.find((x) => x.id === vid) ?? p.versions[0] : undefined }
}

/** The parts of Clay for the entity's class (a character: Figure · Skeleton · Poses · Bench). */
export function ClayTabs() {
  const tab = useWorld((s) => s.clayTab)
  const lineup = useWorld((s) => s.lineup)
  const { p } = useEntity()
  if (!p) return null
  return <div className="w-mode w-clay-tabs segmented" role="group" aria-label="The parts of Clay" data-testid="world-clay-tabs">
    {CLAY_TABS[p.cls].map((t) => <button key={t.id} type="button" className={tab === t.id && !lineup ? 'active' : ''} aria-pressed={tab === t.id && !lineup} data-tab={t.id} title={t.hint}
      onClick={() => useWorld.getState().setClayTab(t.id)}>{t.label}</button>)}
  </div>
}

const ON_THE_WAY = ['queued', 'running', 'staged'] as string[]
/** D183 (C2c): the characters whose shell is owed — a fitted body on an A-pose, no shell yet, none on its way — made in one go, each a
 *  Pixal3D job after the other; a scene's figure wears its shell when it lands. */
function MakeShells() {
  const profiles = useStory((s) => s.profiles)
  const making = useSession((s) => Object.values(s.jobs).filter((j) => j.origin?.surface === 'character_shell' && ON_THE_WAY.includes(j.status))
    .map((j) => `${j.origin!.ref}/${(j.origin!.payload as { version?: string } | null)?.version ?? ''}`).join(' '))
  const owed = profiles.filter((x) => x.cls === 'character').flatMap((x) => x.versions.filter((y) => !y.shell_asset_id && y.body_fit_from && y.anim_ref_asset_id && y.anim_ref_note !== 'arms_close').map((y) => ({ p: x, v: y })))
    .filter(({ p, v }) => !making.split(' ').includes(`${p.id}/${v.id}`))
  if (owed.length < 2) return null                                           // one owed is this page's own Make the shell ▶
  const go = async () => {
    let n = 0
    for (const { p, v } of owed) {
      try { await unwrap(http.POST('/story/profiles/{pid}/versions/{vid}/shell', { params: { path: { pid: p.id, vid: v.id } } })); n++ }
      catch (e) { useSession.getState().toast(`${p.name}'s shell: ${(e as { detail?: string }).detail ?? e}`, 'error') }
    }
    if (n) useSession.getState().toast(`${n} shell${n === 1 ? '' : 's'} queued — about four minutes each, one after another`, 'info')
  }
  return <button type="button" className="quiet" data-testid="make-shells" onClick={() => void go()}
    title={`${owed.map((x) => x.p.name).join(', ')} — Pixal3D makes each shell from its A-pose picture in the background; a scene's figure wears it when it lands (D183)`}>Make every owed shell ({owed.length})</button>
}

/** The entity's builder — the body with its fit and shell; a prop's model and height; a place's set. */
function Builder({ p, v }: { p: Profile; v: Version }) {
  return (
    <div className="w-sheet cast-page" data-testid="world-clay-builder">
      {p.cls === 'character' && <Part label="The body" quiet="line"><section className="w-build-body"><h3>Body <Help text="The figure Clay draws the character with: its height, build and proportions fitted to the A-pose front (picked in Make), its shell (the 3D model of the A-pose) and its skeleton." /></h3>
        <CastBody p={p} v={v} />
        <h3>Shell <Help text="The 3D model of the A-pose front, made in the background: the clay the character's figures are drawn in. The form is what runs — also when a fitted body queues the shell by itself (D183)." /></h3>
        <MeshRunForm p={p} v={v} testId="shell-run-form"><CommandButton id="cast.shell.make" text /><MakeShells /></MeshRunForm>
        <h3>Test <Help text="The turn test: the figure turning on the spot, performed from the A-pose on the shots' own guide — a GPU job; its cost is asked first." /></h3>
        <div className="w-verbs"><CommandButton id="story.cast.testAnimRef" text /></div></section></Part>}
      {p.cls === 'prop' && <Part label="The model" quiet="line"><PropModel p={p} v={v} /></Part>}
      {p.cls === 'place' && <Part label="The set" quiet="line" fallback={<section className="place-set" />}><PlaceSetSection p={p} v={v} /></Part>}
    </div>
  )
}

/** Clay's left column: the part's builder, the skeleton panel, or the bench's own column (Poses is its Motion section). */
export function WorldClayColumn() {
  const tab = useWorld((s) => s.clayTab)
  const { p, v } = useEntity()
  if (!p || !v) return <span className="hint">Pick or make one in the header.</span>
  if (tab === 'skeleton' && p.cls === 'character') return <Part label="The skeleton panel" fallback={<div className="w-empty">Loading…</div>}><RigPanel /></Part>
  if (tab === 'poses' || tab === 'bench') return <Suspense fallback={null}><ClayColumn tab={tab === 'poses' ? 'motion' : 'scene'} /></Suspense>
  return <Suspense fallback={null}><Builder p={p} v={v} /></Suspense>
}

/** Clay's centre: the bench (opened for the version when it changes), the skeleton screen, or — nothing to stand on a bench yet — `empty`. */
export function WorldClayCentre({ empty }: { empty: React.ReactNode }) {
  const tab = useWorld((s) => s.clayTab)
  const lineup = useWorld((s) => s.lineup)
  const benchFor = useWorld((s) => s.benchFor)
  const { p, v } = useEntity()
  const can = benchShown(p, v, tab)
  const key = p && v ? `${p.id}/${v.id}` : null
  useEffect(() => { if (tab !== 'skeleton' && !lineup && can) void useWorld.getState().ensureBench() }, [key, tab, lineup, can])
  if (tab === 'skeleton' && p?.cls === 'character') return <Part label="The skeleton bench" fallback={<div className="w-empty">Loading the bench…</div>}><div className="w-skeleton" data-testid="world-skeleton"><SkeletonBench /></div></Part>
  if (!lineup && !can) return <>{empty}</>
  if (!lineup && benchFor !== key) return <div className="w-empty">Opening the bench…</div>
  return <Suspense fallback={<div className="w-empty">Loading Clay…</div>}><div className="strip w-edit-strip"><ClayStrip /></div><div className="w-edit-stage" data-testid="world-clay" data-lineup={lineup || undefined}><ClayStage /></div></Suspense>
}

/** Clay's Inspector: the skeleton screen's parts, the bench's selected thing (Poses, Bench, the line-up), else `facts` (the entity's). */
export function WorldClayInspector({ facts }: { facts: React.ReactNode }) {
  const tab = useWorld((s) => s.clayTab)
  const lineup = useWorld((s) => s.lineup)
  const { p } = useEntity()
  if (tab === 'skeleton' && p?.cls === 'character') return <Part label="The skeleton bench" quiet="hide" fallback={<aside className="w-insp" />}><aside className="w-insp"><SkeletonParts /></aside></Part>
  if (tab === 'poses' || tab === 'bench' || lineup) return <Part label="The selection" quiet="hide" fallback={<aside className="w-insp" />}><aside className="w-insp" data-testid="world-clay-inspector"><SelectionInspector /></aside></Part>
  return <>{facts}</>
}
