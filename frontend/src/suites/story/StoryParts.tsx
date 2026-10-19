// 17 (D85): the Story suite's parts (StorySuite.ts registers them) — SY0: the World tab. Panel: the sections with their counts and the
// adders; Stage: the editor over story/world.json (logline, synopsis, styles, the spine, variables); Inspector: the project format (the
// finalize gate), counts, the selected item's fields (a style's editor: StyleWorld.tsx, D90; a library entry's and a saved panel's:
// LibraryWorld.tsx, D92). SY1: the Cast tab — Panel: the profiles by class; Strip: the
// version selector and the bootstrap strip; Stage: the version page (hero, the character sheet — D93 B4, the coverage grid, the candidates with keep / reject);
// Inspector: the profile and the version. Mouse-first (D32): every verb is a button or a menu entry.
import { Film, ImagePlus, Lock } from 'lucide-react'
import { useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react'
import { api, http, unwrap } from '../../api/client'
import { CommandButton, MenuButton } from '../../frame/CommandButton'
import { markUsed, runCommand, sep, type MenuItem } from '../../frame/commands'
import { openPressMenu, showMenu } from '../../frame/ContextMenu'
import { DEV_HOOKS } from '../../devHooks'
import { useSuiteRail } from '../../frame/suiteRegistry'
import { useSession } from '../../store/session'
import type { Asset, Profile, Shot, ShotVersion, StoryBeat, StoryVariable, WorldStyle } from '../../api/types'
import { coverageGrid, readiness, rowsCovered } from './coverage'
import { TrainingBlock } from './TrainingBlock'
import { VoicesBlock } from './VoicesBlock'
import { LipsyncBlock } from './LipsyncBlock'
import { RecipeSteps } from './RecipeSteps'
import { StyleEditor, StyleGrid } from './StyleWorld'
import { EntryEditor, LibraryGrid, PanelEditor, PanelGrid } from './LibraryWorld'
import { useLibrary } from './libraryStore'
import { useGenerate } from '../generate/generateStore'
import { versionName } from '../generate/sheet'
import { CastSheet } from './CastSheet'
import { askExpand, makeClipItems, makeFrameItems, profileMenu, rowMenu, runOnItem, shotMenu, storyItem } from './storyCommands'
import { flatGroups, useAlbum } from '../catalogue/albumStore'
import { findNode } from './styleSamples'
import { storyKey } from './storyKeys'
import { CLASS_LABEL, SECTIONS, sy, ttsJobFor, useStory, voiceLabel, type ProfileClass, type Section } from './storyStore'
import { FlowCanvas } from './flow/FlowCanvas'
import { SequenceInspector, SequencePanel } from './episode/SequencePanel'
import { SequenceStage } from './episode/SequenceStage'
import { laneChecklist } from './episode/sequenceCommands'
import { useSequence } from './episode/sequenceStore'
import { NODE_LABEL } from './flow/types'
import { optionsAvailable } from './flow/play'
import type { FlowNode, FlowOption, StageObject } from '../../api/types'
import { speakersOf, speakerVersion } from './makeFor'
import { CommandRow } from '../../frame/CommandButton'
import './story.css'

/** Dev hook (`window.__loom2Story`, DEV_HOOKS only): the smoke test and scripts/sy_acceptance.py drive the suite through the store. */
function devHook(): Record<string, unknown> {
  const w = window as unknown as { __loom2Story?: Record<string, unknown> }
  w.__loom2Story ??= { state: () => ({ world: sy().world, selected: sy().selected, section: sy().section, profileId: sy().profileId, versionId: sy().versionId, refPage: sy().refPage, candPage: sy().candPage }),
    load: () => sy().load(), flush: () => sy().flush(),
    addStyle: (name?: string) => sy().addStyle(name), setStyle: (id: string, patch: Partial<WorldStyle>) => sy().setStyle(id, patch), edit: (patch: Record<string, unknown>) => sy().edit(patch as never),
    // SY1
    loadProfiles: () => sy().loadProfiles(), selectProfile: (id: string | null, v?: string | null) => sy().selectProfile(id, v), loadPages: () => sy().loadPages(),
    createProfile: (name: string, cls: ProfileClass, hero?: string | null, appearance?: string) => sy().createProfile(name, cls, hero, appearance),
    expand: (preset: string, seeds = 1, tier: 'draft' | 'full' = 'draft') => sy().expand(preset, seeds, tier), curate: (ids: string[], verdict: 'keep' | 'reject') => sy().curate(ids, verdict),
    animTest: (pid: string, vid: string, stage = false) => import('./animTest').then((m) => m.runAnimTest(pid, vid, stage)),   // CA0: scripts/ca0_acceptance.py --parts test
    lock: () => sy().lockVersion(), newVersion: () => sy().newVersion(), setStub: (s: string) => sy().setSheet({ appearance: s }), setSheet: (patch: Record<string, unknown>) => sy().setSheet(patch as never),
    train: (opts: Record<string, unknown> = {}) => { sy().setTrainOpts(opts as never); return sy().train() }, loras: () => sy().loras, loadLoras: () => sy().loadLoras(),
    useLora: (id: string) => sy().useLora(id), deleteLora: (id: string) => sy().deleteLora(id), checkLora: (id: string) => sy().checkLora(id),
    // SY2
    loadShots: () => sy().loadShots(), selectShot: (id: string | null, v?: string | null) => sy().selectShot(id, v), shots: () => ({ shots: sy().shots, shotId: sy().shotId, shotVersionId: sy().shotVersionId }),
    createShot: (name: string, src?: { stage_id?: string; camera_id?: string; clip_id?: string; frame_asset_id?: string }) => sy().createShot(name, src), useTake: (kind: 'image' | 'clip', id: string) => sy().useTake(kind, id),
    finalizeShot: () => sy().finalizeShot(), newShotVersion: () => sy().newShotVersion(),
    // SY3
    loadFlow: () => sy().loadFlow(), flow: () => ({ nodes: sy().flowNodes, graph: sy().flowGraph, nodeId: sy().nodeId, problems: sy().problems, play: sy().play }),
    addNode: (t: FlowNode['type'], title?: string, at?: { x: number; y: number }) => sy().addNode(t, title, at), connect: (a: string, port: string, b: string) => sy().connect(a, port, b),
    patchNode: (id: string, patch: Record<string, unknown>) => sy().patchNode(id, patch as never), selectNode: (id: string | null) => sy().selectNode(id), validate: () => sy().validate(),
    playStart: () => sy().playStart(), playNext: (o?: string) => sy().playNext(o), playStop: () => sy().playStop(),
    openShots: (id: string | null) => { void import('../../frame/suiteRegistry').then((m) => { m.setRailTab('story', 'shots'); useSession.getState().setSuite('story'); sy().selectShot(id) }) },
    openTab: (tab: 'world' | 'cast' | 'shots' | 'flow' | 'episode') => { void import('../../frame/suiteRegistry').then((m) => { m.setRailTab('story', tab); useSession.getState().setSuite('story') }) } }
  return w.__loom2Story
}
if (DEV_HOOKS) devHook()

const menu = (kind: 'beat' | 'variable', id: string): MenuItem[] => rowMenu(kind, id).map((m) => (m === 'sep' ? sep : m))

// ------------------------------------------------------------------ Panel · World
function WorldTab() {
  const world = useStory((s) => s.world)
  const section = useStory((s) => s.section)
  const entries = useLibrary((l) => l.library?.entries.length ?? 0)
  const panels = useGenerate((g) => g.presets.length)
  const counts: Record<Section, number | null> = {
    logline: null, synopsis: null, styles: world?.styles.length ?? 0, library: entries, panels, spine: world?.spine.length ?? 0, variables: world?.variables.length ?? 0,
  }
  return (
    <div className="story-panel">
      <div className="story-list" role="list">
        {SECTIONS.map((s) => (
          <button key={s.id} className={`story-row${section === s.id ? ' active' : ''}`} role="listitem" onClick={() => sy().setSection(s.id)} title={`Show the ${s.label} section`}>
            <span>{s.label}</span>{counts[s.id] !== null && <span className="n">{counts[s.id]}</span>}
          </button>
        ))}
      </div>
      <h4>Add</h4>
      <div className="verbs"><CommandButton id="story.world.addStyle" text /><CommandButton id="story.world.addEntry" text /><CommandButton id="story.world.addBeat" text /><CommandButton id="story.world.addVariable" text /></div>
      <span className="hint">The styles reach Generate's Style picker and the library its preset tiles; a beat becomes a Flow node by hand; the variables drive the Flow's conditions.</span>
    </div>
  )
}

// ------------------------------------------------------------------ Panel · Cast
function CastTab() {
  const profiles = useStory((s) => s.profiles)
  const profileId = useStory((s) => s.profileId)
  const filter = useStory((s) => s.castFilter)
  const search = useStory((s) => s.castSearch)
  const q = search.trim().toLowerCase()
  const shown = profiles.filter((p) => (filter === 'all' || p.cls === filter) && (!q || p.name.toLowerCase().includes(q)))
  return (
    <div className="story-panel cast-panel">
      <div className="segmented" aria-label="class">
        {(['all', 'character', 'place', 'prop'] as const).map((c) => <button key={c} className={filter === c ? 'active' : ''} onClick={() => sy().setCastFilter(c)}>{c === 'all' ? 'all' : `${CLASS_LABEL[c]}s`}</button>)}
      </div>
      <input type="search" value={search} aria-label="search profiles" placeholder="search" onChange={(e) => sy().setCastSearch(e.target.value)} />
      <div className="story-list" role="list">
        {shown.map((p) => {
          const v = p.versions.find((x) => x.id === p.current)
          return (
            <button key={p.id} className={`story-row profile-row${profileId === p.id ? ' active' : ''}`} role="listitem" data-id={p.id} onClick={() => sy().selectProfile(p.id)}
              onContextMenu={(e) => { sy().selectProfile(p.id); showMenu(e, profileMenu()) }}>
              {v?.hero_asset_id ? <img className="pthumb" src={api.thumbUrl(v.hero_asset_id, 256)} alt="" /> : <span className="pthumb empty" />}
              <span className="pname">{p.name}<span className="muted"> · {CLASS_LABEL[p.cls]}</span></span>
              <span className="n">{p.current} <i className={`dot ${v?.state === 'final' ? 'tight' : 'ok'}`} title={v?.state === 'final' ? 'final' : 'open'} /></span>
            </button>
          )
        })}
        {!shown.length && <div className="empty hint">{profiles.length ? 'No profile matches.' : 'No profiles yet — "Make a character…" on a Catalogue tile, or New character…'}</div>}
      </div>
      <div className="verbs"><CommandButton id="story.cast.new" text /><CommandButton id="story.cast.newPlace" text /><CommandButton id="story.cast.newProp" text /></div>
    </div>
  )
}

// ------------------------------------------------------------------ Panel · Shots
/** D90 (01 §11.6): a Flow node as the user knows it — its title, else its first line or its type; never the raw id. */
const nodeName = (nodes: Record<string, FlowNode>, id: string): string => { const n = nodes[id]; return n ? n.title || (n.type === 'dialogue' ? n.lines[0]?.text?.slice(0, 30) : '') || `${NODE_LABEL[n.type]} node` : 'a Flow node' }
const shotThumb = (s: Shot, clipsById: Record<string, { asset_id: string | null }>): string | null => {
  const v = s.versions.find((x) => x.id === s.current)
  if (!v) return null
  if (v.frame_asset_id) return v.frame_asset_id
  const c = v.clip_id ? clipsById[v.clip_id] : undefined
  return c?.asset_id ?? null
}

function ShotsTab() {
  const shots = useStory((s) => s.shots)
  const shotId = useStory((s) => s.shotId)
  const clipsById = useStory((s) => s.clipsById)
  const flowNodes = useStory((s) => s.flowNodes)
  const groups = new Map<string, Shot[]>()
  for (const s of shots) { const k = s.owner_node ?? ''; groups.set(k, [...(groups.get(k) ?? []), s]) }
  const keys = [...groups.keys()].sort((a, b) => (a === '' ? -1 : b === '' ? 1 : a.localeCompare(b)))
  return (
    <div className="story-panel shots-panel">
      <div className="story-list" role="list">
        {keys.map((k) => (
          <div key={k || 'unbound'} className="shot-group">
            <h4>{k ? nodeName(flowNodes, k) : 'Unbound'}<span className="n"> · {groups.get(k)!.length}</span></h4>
            {groups.get(k)!.map((s) => {
              const v = s.versions.find((x) => x.id === s.current)
              const thumb = shotThumb(s, clipsById)
              return (
                <button key={s.id} className={`story-row shot-row${shotId === s.id ? ' active' : ''}`} role="listitem" data-id={s.id} onClick={() => sy().selectShot(s.id)}
                  onContextMenu={(e) => { sy().selectShot(s.id); showMenu(e, shotMenu()) }}>
                  {thumb ? <img className="pthumb" src={api.thumbUrl(thumb, 256)} alt="" /> : <span className="pthumb empty" />}
                  <span className="pname">{s.name}<span className="muted"> · {v?.stage_id ? 'stage' : v?.clip_id ? 'clip' : 'empty'}</span></span>
                  <span className="n">{s.current} <i className={`dot ${v?.state === 'final' ? 'tight' : 'ok'}`} title={v?.state === 'final' ? 'final' : 'open'} /></span>
                </button>
              )
            })}
          </div>
        ))}
        {!shots.length && <div className="empty hint">No shots yet — "New shot from this camera" in Stage, "Make a shot from this clip" in Animate, or New shot…</div>}
      </div>
      <div className="verbs"><CommandButton id="story.shot.new" text /></div>
    </div>
  )
}

// ------------------------------------------------------------------ Panel · Flow
function FlowTab() {
  const flowNodes = useStory((s) => s.flowNodes)
  const nodeId = useStory((s) => s.nodeId)
  const world = useStory((s) => s.world)
  const play = useStory((s) => s.play)
  const [q, setQ] = useState('')
  const list = Object.values(flowNodes).filter((n) => !q.trim() || (n.title || NODE_LABEL[n.type]).toLowerCase().includes(q.trim().toLowerCase())).sort((a, b) => a.created_at.localeCompare(b.created_at))
  const types = [...new Set(list.map((n) => n.type))]
  return (
    <div className="story-panel flow-panel">
      <input type="search" value={q} aria-label="search nodes" placeholder="search nodes" onChange={(e) => setQ(e.target.value)} />
      <div className="story-list" role="list">
        {types.map((t) => (
          <div key={t} className="shot-group">
            <h4>{NODE_LABEL[t]}<span className="n"> · {list.filter((n) => n.type === t).length}</span></h4>
            {list.filter((n) => n.type === t).map((n) => (
              <button key={n.id} className={`story-row node-row${nodeId === n.id ? ' active' : ''}${play?.node === n.id ? ' playing' : ''}`} role="listitem" data-id={n.id} onClick={() => sy().selectNode(n.id)}>
                <span className="pname">{n.title || (n.type === 'dialogue' ? n.lines[0]?.text?.slice(0, 30) : NODE_LABEL[n.type]) || NODE_LABEL[n.type]}</span>
                {(n.type === 'dialogue' || n.type === 'shot') && <span className="n">{n.shot_id ? 'shot' : '—'}</span>}
              </button>
            ))}
          </div>
        ))}
        {!list.length && <div className="empty hint">No nodes yet — the Strip's ✚ buttons add them; right-click the canvas to add one where you point.</div>}
      </div>
      <h4>Variables<span className="n"> · {world?.variables.length ?? 0}</span></h4>
      <div className="vars">
        {(world?.variables ?? []).map((v) => <div key={v.name} className="kv"><span>{v.name}</span><span>{play ? String(play.vars[v.name]) : `${v.type} · ${String(v.default)}`}</span></div>)}
        {!world?.variables.length && <span className="hint">none — declare them in World</span>}
      </div>
    </div>
  )
}

export function Panel({ tab }: { tab: string }) {
  const project = useSession((s) => s.project)
  useEffect(() => { if (project?.open) { void sy().load(); void sy().loadProfiles(); void sy().loadShots(); void sy().loadFlow(); void useLibrary.getState().load(); void useGenerate.getState().loadPresets() } }, [project?.path]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!project?.open) return <span className="hint">Open or create a project to begin.</span>
  if (tab === 'cast') return <CastTab />
  if (tab === 'shots') return <ShotsTab />
  if (tab === 'flow') return <FlowTab />
  if (tab === 'episode') return <SequencePanel />
  return <WorldTab />
}

export function PrimaryAction() {
  const saving = useStory((s) => s.saving)
  const world = useStory((s) => s.world)
  const profileId = useStory((s) => s.profileId)
  const profiles = useStory((s) => s.profiles)
  const versionId = useStory((s) => s.versionId)
  const expanding = useStory((s) => s.expanding)
  const caps = useSession((s) => s.capabilities?.story)
  const shots = useStory((s) => s.shots)
  const shotId = useStory((s) => s.shotId)
  const shotVersionId = useStory((s) => s.shotVersionId)
  const clipsById = useStory((s) => s.clipsById)
  const { active: tab } = useSuiteRail()
  const play = useStory((s) => s.play)
  const flowGraph = useStory((s) => s.flowGraph)
  const flowNodes = useStory((s) => s.flowNodes)
  const seqLane = useSequence((s) => s.lane)
  const seqCurrent = useSequence((s) => s.current)
  markUsed('story.cast.expand'); markUsed('story.shot.new'); markUsed('story.flow.play'); markUsed('story.flow.stop'); markUsed('story.episode.exportFcpxml'); markUsed('story.episode.new')
  if (tab === 'episode') {
    const issues = seqLane ? laneChecklist().length : 0
    const n = seqLane?.clips.length ?? 0
    return (
      <div>
        {seqCurrent ? <button className="primary" disabled={!n} onClick={() => runCommand('story.episode.exportFcpxml')} title="FCPXML with chapter markers (and markers.txt beside it); the checklist asks first when a clip is not a final shot">Export ▶</button>
          : <button className="primary" onClick={() => runCommand('story.episode.new')}>New cut…</button>}
        <div className="estimate">{!seqCurrent ? <span style={{ color: 'var(--fg3)' }}>no cut open</span> : !n ? <span style={{ color: 'var(--fg3)' }}>the lane is empty</span> : issues ? <span style={{ color: 'var(--fg3)' }}>{issues} of {n} clips not final shots</span> : <><span className="dot ok" />{n} clip{n === 1 ? '' : 's'} · every one a final shot</>}</div>
      </div>
    )
  }
  if (tab === 'flow') {
    const n = Object.keys(flowNodes).length
    return (
      <div>
        {play ? <button className="primary" onClick={() => runCommand('story.flow.stop')}>Stop</button>
          : <button className="primary" disabled={!flowGraph?.start} onClick={() => runCommand('story.flow.play')} title="Walk the graph from the Start: authored clips and lines, never a model (P)">Play ▶</button>}
        <div className="estimate">{play ? (play.ended ? 'the end' : `at ${flowNodes[play.node ?? '']?.title || play.node}`) : flowGraph?.start ? `${n} node${n === 1 ? '' : 's'} · from the Start` : <span style={{ color: 'var(--fg3)' }}>no Start node yet</span>}</div>
      </div>
    )
  }
  if (tab === 'shots') {
    const s = shots.find((x) => x.id === shotId); const v = s?.versions.find((x) => x.id === (shotVersionId ?? s.current))
    void clipsById
    const why = v ? sy().finalizeWhy(v) : null
    return (
      <div>
        <button className="primary" onClick={() => runCommand('story.shot.new')} title="An empty shot; its takes come from Stage, Animate or the board">New shot…</button>
        <div className="estimate">{!s || !v ? <span style={{ color: 'var(--fg3)' }}>pick a shot</span> : v.state === 'final' ? <><span className="dot ok" />{v.id} final</> : why ? <span style={{ color: 'var(--fg3)' }}>{why}</span> : <><span className="dot ok" />{v.id} ready to mark final</>}</div>
      </div>
    )
  }
  if (tab === 'cast') {
    const p = profiles.find((x) => x.id === profileId); const v = p?.versions.find((x) => x.id === (versionId ?? p.current))
    const reason = !p ? 'pick a profile' : !v ? 'no version' : v.state !== 'open' ? `${v.id} is final — expand a new version` : !v.hero_asset_id ? 'no hero image yet' : !caps?.model_id ? 'no model in this build' : expanding ? 'queuing…' : caps.missing.length ? `weights missing: ${caps.missing.join(', ')}` : ''
    const secs = (caps?.seconds ?? 0) * (caps?.presets.full?.cells ?? 0)
    return (
      <div>
        <button className="primary" disabled={!!reason} onClick={() => runCommand('story.cast.expand')} title="Queue one job per coverage cell (Full coverage; the dialog says the cost) — Ctrl+Enter">Expand ▶</button>
        <div className="estimate">{reason ? <span style={{ color: 'var(--fg3)' }}>{reason}</span> : <><span className="dot ok" />{caps?.presets.full?.cells ?? '?'} cells · ≈ {Math.max(1, Math.round(secs / 60))} min warm · {caps?.short}</>}</div>
      </div>
    )
  }
  if (!world) return null
  return <div className="estimate"><span className={`dot ${saving ? 'tight' : 'ok'}`} />{saving ? 'saving…' : `saved · revision ${world.revision}`}</div>
}

// ------------------------------------------------------------------ Strip
function Bootstrap({ p }: { p: Profile }) {
  const refPage = useStory((s) => s.refPage)
  const candPage = useStory((s) => s.candPage)
  const versionId = useStory((s) => s.versionId)
  const caps = useSession((s) => s.capabilities?.story)
  const v = p.versions.find((x) => x.id === (versionId ?? p.current))
  const refs = Object.values(refPage?.assets ?? {})
  const grid = coverageGrid(refs, caps?.coverage.shots ?? [], caps?.coverage.angles ?? [])
  const ready = readiness(refs, caps?.coverage.shots ?? [], caps?.coverage.angles ?? [], !!v?.hero_asset_id)
  const curated = (caps?.coverage.shots?.length ?? 0) > 0 && rowsCovered(grid).length === (caps?.coverage.shots?.length ?? 0)
  const steps: { id: string; label: string; done: boolean; hint: string; run?: string }[] = [
    { id: 'cast', label: 'Cast', done: !!v?.hero_asset_id, hint: v?.hero_asset_id ? 'the hero is set' : 'make an image the hero ("Make a character…" on a tile, or pick a candidate)' },
    { id: 'expand', label: 'Expand', done: Object.keys(candPage?.assets ?? {}).length > 0, hint: 'one job per coverage cell with the hero as the reference', run: 'story.cast.expand' },
    { id: 'curate', label: 'Curate', done: curated, hint: curated ? 'every shot-size row has a reference' : 'add candidates to the reference set until every shot-size row has one (advisory)' },
    { id: 'train', label: 'Train', done: !!v?.lora, hint: v?.lora ? `the version holds a LoRA (trigger ${v.trigger})` : `readiness ${ready.score} · ${ready.summary} — ${ready.lines[0]}; a LoRA from the reference set (advisory)`, run: 'story.cast.train' },
    { id: 'lock', label: 'Final', done: v?.state === 'final', hint: 'the version becomes read-only; a retake is a new version', run: 'story.cast.lock' },
  ]
  return (
    <span className="bootstrap" aria-label="bootstrap">
      {steps.map((s, i) => (
        <span key={s.id} className={`bs-step${s.done ? ' done' : ''}`} title={s.hint}>
          {s.run ? <button className="quiet" onClick={() => runCommand(s.run!)}>{s.label}{s.done ? ' ✓' : ''}</button> : <span>{s.label}{s.done ? ' ✓' : ''}</span>}
          {i < steps.length - 1 && <span className="sep">›</span>}
        </span>
      ))}
    </span>
  )
}

/** D90 (02 §5): "Make frame ▸" and "Make clip ▸" — press menus of the registry's commands (the Strip, the board, the Inspector). */
function MakeMenus() {
  return <span className="make-menus"><MenuButton label="Make frame" icon={ImagePlus} items={makeFrameItems} text size={14} /><MenuButton label="Make clip" icon={Film} items={makeClipItems} text size={14} /></span>
}

export function Strip() {
  const world = useStory((s) => s.world)
  const project = useSession((s) => s.project)
  const profiles = useStory((s) => s.profiles)
  const profileId = useStory((s) => s.profileId)
  const versionId = useStory((s) => s.versionId)
  const shots = useStory((s) => s.shots)
  const shotId = useStory((s) => s.shotId)
  const shotVersionId = useStory((s) => s.shotVersionId)
  const stagesLite = useStory((s) => s.stagesLite)
  const { active: tab } = useSuiteRail()
  const play = useStory((s) => s.play)
  const problems = useStory((s) => s.problems)
  for (const id of ['story.shot.makeFrame', 'story.shot.makeFrameStage', 'story.shot.makeClip', 'story.shot.makeClipStage']) markUsed(id)   // in the Make ▸ menus
  markUsed('story.cast.lock'); markUsed('story.cast.newVersion'); markUsed('story.shot.finalize'); markUsed('story.shot.newVersion'); markUsed('story.shot.openStage'); markUsed('story.shot.openAnimate')
  if (tab === 'episode') {
    return <div className="story-strip"><span>Episode</span><span className="spacer" /><span className="hint">the hand-built render list: shots from the Shots bin, clips from the Clips bin; every join a cut or a dissolve</span></div>
  }
  if (tab === 'flow') {
    return (
      <div className="story-strip flow-strip">
        <CommandRow ids={['story.flow.add.start', 'story.flow.add.hub', 'story.flow.add.dialogue', 'story.flow.add.choice', 'story.flow.add.condition', 'story.flow.add.action', 'story.flow.add.shot', 'story.flow.add.jump', 'story.flow.add.comment']} />
        <span className="spacer" />
        {problems && <span className={`hint${problems.length ? ' warn' : ''}`}>{problems.length ? `${problems.length} problem${problems.length === 1 ? '' : 's'}` : 'valid'}</span>}
        <CommandButton id="story.flow.validate" />
        {play ? <CommandButton id="story.flow.stop" /> : <CommandButton id="story.flow.play" />}
        <CommandButton id="story.flow.fit" />
      </div>
    )
  }
  if (tab === 'shots') {
    const s = shots.find((x) => x.id === shotId)
    if (!s) return <div className="story-strip"><span>Shots</span><span className="spacer" /><span className="hint">pick a shot, or make one from a Stage camera or an Animate clip</span></div>
    const v = s.versions.find((x) => x.id === (shotVersionId ?? s.current))
    const stale = v ? sy().shotStale(v) : false
    const stageName = v?.stage_id ? (stagesLite.find((x) => x.id === v.stage_id)?.name ?? v.stage_id) : null
    return (
      <div className="story-strip">
        <b>{s.name}</b>
        <select aria-label="shot version" value={v?.id ?? s.current} onChange={(e) => sy().selectShot(s.id, e.target.value)} title="The version shown (the Flow pins one; the current one by default)">
          {s.versions.map((x) => <option key={x.id} value={x.id}>{x.id}{x.id === s.current ? ' · current' : ''}{x.state === 'final' ? ' · final' : ''}</option>)}
        </select>
        <CommandButton id="story.shot.newVersion" />
        {v?.state === 'final' ? <span className="lock-badge" title={`marked final ${v.finalized_at ?? ''}`}><Lock size={12} /> final</span> : <CommandButton id="story.shot.finalize" />}
        {stale && <span className="stale-badge" title="The stage moved after this version's frame / clip was taken — still usable (advisory)">stale</span>}
        <span className="spacer" />
        {stageName && <span className="hint">{stageName}</span>}
        <MakeMenus />
        <CommandButton id="story.shot.openStage" /><CommandButton id="story.shot.openAnimate" />
      </div>
    )
  }
  if (tab === 'cast') {
    const p = profiles.find((x) => x.id === profileId)
    if (!p) return <div className="story-strip"><span>Cast</span><span className="spacer" /><span className="hint">pick a profile, or make one from a Catalogue tile</span></div>
    const v = p.versions.find((x) => x.id === (versionId ?? p.current))
    return (
      <div className="story-strip">
        <b>{p.name}</b>
        <select aria-label="version" value={v?.id ?? p.current} onChange={(e) => sy().selectProfile(p.id, e.target.value)} title="The version shown (mentions use the current one unless pinned)">
          {p.versions.map((x) => <option key={x.id} value={x.id}>{versionName(x)}{x.id === p.current ? ' · current' : ''}{x.state === 'final' ? ' · final' : ''}</option>)}
        </select>
        <CommandButton id="story.cast.newVersion" />
        {v?.state === 'final' ? <span className="lock-badge" title={`marked final ${v.locked_at ?? ''}`}><Lock size={12} /> final</span> : <CommandButton id="story.cast.lock" />}
        <span className="spacer" />
        <Bootstrap p={p} />
      </div>
    )
  }
  return (
    <div className="story-strip">
      <span>World</span>
      <span className="spacer" />
      {world && project?.open && project.format && <span className="hint">{project.name} · {project.format.width}×{project.format.height} · {project.format.fps} fps</span>}
    </div>
  )
}

// ------------------------------------------------------------------ Stage: the World editor
function BeatRow({ b, i, active }: { b: StoryBeat; i: number; active: boolean }) {
  return (
    <div className={`row-item beat-row${active ? ' active' : ''}`} data-id={b.id} onClick={() => sy().select({ kind: 'beat', id: b.id })} onContextMenu={(e) => showMenu(e, menu('beat', b.id))}>
      <span className="k">{i + 1}</span>
      <input type="text" value={b.title} aria-label="beat title" placeholder="title" onChange={(e) => sy().setBeat(b.id, { title: e.target.value })} />
      <input type="text" value={b.line} aria-label="beat line" placeholder="one line: what happens" onChange={(e) => sy().setBeat(b.id, { line: e.target.value })} />
      <span className="tools">
        <button className="quiet" title="Move earlier" aria-label={`move beat ${i + 1} earlier`} disabled={i === 0} onClick={(e) => { e.stopPropagation(); sy().moveBeat(b.id, -1) }}>▲</button>
        <button className="quiet" title="Move later" aria-label={`move beat ${i + 1} later`} onClick={(e) => { e.stopPropagation(); sy().moveBeat(b.id, 1) }}>▼</button>
        <button className="quiet" title="Remove this beat" aria-label={`remove beat ${i + 1}`} onClick={(e) => { e.stopPropagation(); sy().removeBeat(b.id) }}>✕</button>
      </span>
    </div>
  )
}

function VarRow({ v, active }: { v: StoryVariable; active: boolean }) {
  return (
    <div className={`row-item var-row${active ? ' active' : ''}`} data-id={v.name} onClick={() => sy().select({ kind: 'variable', id: v.name })} onContextMenu={(e) => showMenu(e, menu('variable', v.name))}>
      <input type="text" value={v.name} aria-label="variable name" placeholder="name" onChange={(e) => sy().setVariable(v.name, { name: e.target.value.replace(/[^A-Za-z0-9_]/g, '_') })} />
      <select value={v.type} aria-label="variable type" onChange={(e) => sy().setVariable(v.name, { type: e.target.value as StoryVariable['type'] })}><option value="bool">bool</option><option value="enum">enum</option></select>
      {v.type === 'enum'
        ? <input type="text" value={v.values.join(', ')} aria-label="enum values" placeholder="values, comma-separated" onChange={(e) => sy().setVariable(v.name, { values: e.target.value.split(',').map((x) => x.trim()).filter(Boolean) })} />
        : <span className="k">true / false</span>}
      {v.type === 'enum'
        ? <select value={String(v.default)} aria-label="default value" onChange={(e) => sy().setVariable(v.name, { default: e.target.value })}>{v.values.map((x) => <option key={x} value={x}>{x}</option>)}</select>
        : <select value={v.default ? 'true' : 'false'} aria-label="default value" onChange={(e) => sy().setVariable(v.name, { default: e.target.value === 'true' })}><option value="false">false</option><option value="true">true</option></select>}
      <span className="tools"><button className="quiet" title="Remove this variable" aria-label={`remove variable ${v.name}`} onClick={(e) => { e.stopPropagation(); sy().removeVariable(v.name) }}>✕</button></span>
    </div>
  )
}

function WorldEditor() {
  const world = useStory((s) => s.world)
  const loading = useStory((s) => s.loading)
  const section = useStory((s) => s.section)
  const selected = useStory((s) => s.selected)
  const host = useRef<HTMLDivElement>(null)
  useEffect(() => { host.current?.querySelector<HTMLElement>(`#story-sec-${section}`)?.scrollIntoView({ block: 'start', behavior: 'smooth' }) }, [section])
  if (!world) return <div className="story-empty"><div>{loading ? 'Loading the world…' : 'The world could not be read.'}</div></div>
  return (
    <div ref={host} className="world-editor" tabIndex={0} onKeyDown={(e) => { storyKey('world', e.nativeEvent) }}>
      <section id="story-sec-logline">
        <h3>Logline<span className="hint">one sentence</span></h3>
        <textarea rows={2} value={world.logline} aria-label="logline" placeholder="Who wants what, and what stands in the way." onChange={(e) => sy().edit({ logline: e.target.value })} />
      </section>
      <section id="story-sec-synopsis">
        <h3>Synopsis</h3>
        <textarea rows={8} value={world.synopsis} aria-label="synopsis" placeholder="The story in a page." onChange={(e) => sy().edit({ synopsis: e.target.value })} />
      </section>
      <section id="story-sec-styles">
        <h3>Styles<span className="hint">one per generation; click a style to edit it, drop a Catalogue image on it to make its sample; ★ marks the default Generate preselects</span></h3>
        <StyleGrid />
        <div className="adder"><CommandButton id="story.world.addStyle" text /></div>
      </section>
      <section id="story-sec-library">
        <h3>Library<span className="hint">every preset of Generate's prompt fields — words and a picture; click one to edit it in the Inspector, + Add puts new words in a field</span></h3>
        <LibraryGrid />
      </section>
      <section id="story-sec-panels">
        <h3>Saved panels<span className="hint">Generate's whole-panel templates, each shown by its latest result; click one for Apply, Rename and Delete</span></h3>
        <PanelGrid />
      </section>
      <section id="story-sec-spine">
        <h3>Spine<span className="hint">the beats in order; a Flow node is made from a beat by hand</span></h3>
        <div className="rows">
          {world.spine.map((b, i) => <BeatRow key={b.id} b={b} i={i} active={selected?.kind === 'beat' && selected.id === b.id} />)}
          {!world.spine.length && <div className="empty">No beats yet.</div>}
        </div>
        <div className="adder"><CommandButton id="story.world.addBeat" text /></div>
      </section>
      <section id="story-sec-variables">
        <h3>Variables<span className="hint">bool or enum flags the Flow's conditions read</span></h3>
        <div className="rows">
          {world.variables.map((v) => <VarRow key={v.name} v={v} active={selected?.kind === 'variable' && selected.id === v.name} />)}
          {!world.variables.length && <div className="empty">No variables yet.</div>}
        </div>
        <div className="adder"><CommandButton id="story.world.addVariable" text /></div>
      </section>
    </div>
  )
}

// ------------------------------------------------------------------ Stage: the Cast version page
function candidateMenu(id: string): MenuItem[] {
  const s = sy()
  if (!s.picked.includes(id)) s.pick(id)
  return [{ cmd: 'story.cast.keep' }, { cmd: 'story.cast.reject' }, { cmd: 'story.cast.setHero' }, sep, { cmd: 'story.cast.useAsAnimRef' }, { cmd: 'story.cast.useAsAnimRefBack' }, sep, { cmd: 'story.cast.openCandidates' }]
}

function Candidate({ a, picked }: { a: Asset; picked: boolean }) {
  const cell = (a.params as { coverage_cell?: { shot?: string; angle?: string; expression?: string } } | null)?.coverage_cell
  const title = cell ? `${cell.shot ?? ''} · ${cell.angle ?? ''} · ${cell.expression ?? ''}` : a.prompt_text ?? ''
  return (
    <div className={`cand-card${picked ? ' picked' : ''}${a.state === 'reject' ? ' reject' : ''}${a.state === 'keep' ? ' keep' : ''}`} data-id={a.id} title={title}
      onClick={(e: ReactMouseEvent) => sy().pick(a.id, e.ctrlKey || e.shiftKey)} onContextMenu={(e) => showMenu(e, candidateMenu(a.id))}>
      <img src={api.thumbUrl(a.id, 256)} alt="" />
      {cell && <span className="cell">{cell.shot} · {cell.angle}</span>}
      <span className="tools">
        <button className="quiet" title="Add to the reference set" aria-label="add to the reference set" onClick={(e) => { e.stopPropagation(); void sy().curate([a.id], 'keep') }}>✓</button>
        <button className="quiet" title="Reject" aria-label="reject" onClick={(e) => { e.stopPropagation(); void sy().curate([a.id], 'reject') }}>✕</button>
      </span>
    </div>
  )
}

/** CA0 (01 step 2, §10): the version's animation reference — what Wan Animate is given for the character: full body, a neutral A-pose,
 *  16:9 with the figure centred and padded (a portrait one loses its head and feet to the node's crop), a plain ground. A prop's is the
 *  object alone in a three-quarter view. Made from the sheet and references; any candidate can be picked (its right-click). */
function AnimRef({ p, v }: { p: Profile; v: Profile['versions'][number] }) {
  const slot = (side: 'front' | 'back', id: string | null | undefined, label: string) => (
    <div className={`anim-ref-slot${id ? '' : ' empty'}`} data-side={side}
      onContextMenu={(e) => showMenu(e, side === 'back' ? [{ cmd: 'story.cast.makeAnimRefBack' }, { cmd: 'story.cast.clearAnimRefBack' }] : [{ cmd: 'story.cast.makeAnimRef' }, { cmd: 'story.cast.fitBody' }, { cmd: 'story.cast.clearAnimRef' }])}>
      {id ? <img src={api.thumbUrl(id, 512)} alt={label} /> : <span className="hint">{label}: none yet</span>}
      <span className="cell">{label}</span>
    </div>
  )
  markUsed('story.cast.useAsAnimRef'); markUsed('story.cast.useAsAnimRefBack'); markUsed('story.cast.clearAnimRef'); markUsed('story.cast.clearAnimRefBack')
  return (
    <section className="anim-ref">
      <h3>Animation reference <span className="hint">{p.cls === 'prop' ? 'the prop alone, a three-quarter view, 16:9' : 'full body, A-pose, 16:9, plain ground — what Wan Animate is given'}</span></h3>
      <div className="anim-ref-row">
        {slot('front', v.anim_ref_asset_id, p.cls === 'prop' ? 'reference' : 'front')}
        {p.cls === 'character' && slot('back', v.anim_ref_back_asset_id, 'back (optional)')}
        {p.cls === 'character' && <AnimTestSlot clipId={v.anim_test_clip_id ?? null} />}
        <div className="verbs">
          <CommandButton id="story.cast.makeAnimRef" text />
          {p.cls === 'character' && <CommandButton id="story.cast.makeAnimRefBack" text />}
          {p.cls === 'character' && <CommandButton id="story.cast.testAnimRef" text />}
        </div>
      </div>
    </section>
  )
}

/** CA0: the version's latest test animation (a turn on the spot) — its first frame, played in Animate. */
function AnimTestSlot({ clipId }: { clipId: string | null }) {
  const [got, setGot] = useState<{ clip: string; asset: string | null } | null>(null)   // the clip's first-frame asset, keyed by the clip it belongs to
  useEffect(() => {
    let live = true
    if (clipId) void unwrap(http.GET('/clips/{clip_id}', { params: { path: { clip_id: clipId } } })).then((c) => { if (live) setGot({ clip: clipId, asset: c.asset_id ?? null }) }).catch(() => undefined)
    return () => { live = false }
  }, [clipId])
  const thumb = got && got.clip === clipId ? got.asset : null
  markUsed('story.cast.playAnimTest')
  return (
    <div className={`anim-ref-slot${clipId ? '' : ' empty'}`} data-side="test" onDoubleClick={() => runCommand('story.cast.playAnimTest')}
      onContextMenu={(e) => showMenu(e, [{ cmd: 'story.cast.playAnimTest' }, { cmd: 'story.cast.testAnimRef' }])}>
      {thumb ? <img src={api.thumbUrl(thumb, 512)} alt="the test animation" /> : <span className="hint">{clipId ? 'the test clip' : 'test: none yet'}</span>}
      <span className="cell">test · a turn{clipId ? ' — right-click to play' : ''}</span>
    </div>
  )
}

function CastPage() {
  const profiles = useStory((s) => s.profiles)
  const profileId = useStory((s) => s.profileId)
  const versionId = useStory((s) => s.versionId)
  const refPage = useStory((s) => s.refPage)
  const candPage = useStory((s) => s.candPage)
  const picked = useStory((s) => s.picked)
  const caps = useSession((s) => s.capabilities?.story)
  markUsed('story.cast.keep'); markUsed('story.cast.reject'); markUsed('story.cast.setHero'); markUsed('story.cast.openCandidates'); markUsed('story.cast.openGroup'); markUsed('story.cast.delete')
  const p = profiles.find((x) => x.id === profileId)
  if (!p) return <div className="story-empty"><div>Pick a profile on the left, or make one: <b>Make a character…</b> on a Catalogue tile puts the image in as the hero.<div className="quick-cards"><CommandButton id="story.cast.new" text /></div></div></div>
  const v = p.versions.find((x) => x.id === (versionId ?? p.current))
  if (!v) return null
  const refs = Object.values(refPage?.assets ?? {})
  const grid = coverageGrid(refs, caps?.coverage.shots ?? [], caps?.coverage.angles ?? [])
  const cands = Object.values(candPage?.assets ?? {}).sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
  const open = v.state === 'open'
  return (
    <div className="cast-page" tabIndex={0} onKeyDown={(e) => { storyKey('cast', e.nativeEvent) }}>
      <div className="cast-head">
        <div className="hero-card">{v.hero_asset_id ? <img src={api.thumbUrl(v.hero_asset_id, 512)} alt="" /> : <span className="hint">no hero yet</span>}</div>
        <div className="cast-fields">
          <h2>{p.name} <span className="muted">— {CLASS_LABEL[p.cls]} — {versionName(v)} ({open ? 'open' : 'final'})</span></h2>
          <CastSheet p={p} v={v} />{/* D93 (B4): the character sheet (was the one prompt stub) */}
          <div className="counts"><span>reference set · <b>{refs.length}</b></span><span>candidates · <b>{cands.length}</b></span>{v.candidates_group_id === null && <span className="hint">(none expanded yet)</span>}</div>
        </div>
      </div>
      <section>
        <h3>Coverage <span className="hint">kept references per shot size × angle; thin cells are tinted (advisory)</span></h3>
        <table className="cov-grid" aria-label="coverage">
          <thead><tr><th /> {grid.angles.map((a) => <th key={a}>{a}</th>)}</tr></thead>
          <tbody>
            {grid.shots.map((s) => <tr key={s}><th>{s}</th>{grid.angles.map((a) => { const n = grid.counts[s]?.[a] ?? 0; return <td key={a} className={n ? (n >= 2 ? 'full' : 'one') : 'thin'}>{n || '–'}</td> })}</tr>)}
          </tbody>
        </table>
        {grid.uncelled > 0 && <span className="hint">{grid.uncelled} reference{grid.uncelled === 1 ? '' : 's'} without a cell (the hero, imports).</span>}
      </section>
      {(p.cls === 'character' || p.cls === 'prop') && <AnimRef p={p} v={v} />}
      <section>
        <h3>Candidates <span className="hint">newest first · ✓ adds to the reference set, ✕ rejects · click to select, Ctrl-click for several</span></h3>
        {!cands.length && <div className="empty">{open ? <>No candidates yet — <button className="link" onClick={() => void askExpand('full', 1, 'draft')} disabled={!v.hero_asset_id}>Expand ▶</button> makes one image per coverage cell.</> : 'This version is final.'}</div>}
        <div className="story-cands" role="list">
          {cands.map((a) => <Candidate key={a.id} a={a} picked={picked.includes(a.id)} />)}
        </div>
      </section>
    </div>
  )
}

// ------------------------------------------------------------------ Stage: the shot board
function Take({ kind, id, current, clipsById }: { kind: 'image' | 'clip'; id: string; current: boolean; clipsById: Record<string, { asset_id: string | null; frames: number; w: number; h: number }> }) {
  const c = kind === 'clip' ? clipsById[id] : undefined
  const thumb = kind === 'image' ? id : c?.asset_id ?? null
  markUsed('story.shot.useTake')
  return (
    <div className={`take-card${current ? ' current' : ''}`} data-kind={kind} data-id={id} title={kind === 'clip' ? (c ? `${c.frames} f · ${c.w}×${c.h}` : id) : id}
      onContextMenu={(e) => { storyItem.take = { kind, id }; showMenu(e, [{ cmd: 'story.shot.useTake' }]) }}>
      {thumb ? <img src={api.thumbUrl(thumb, 256)} alt="" /> : <span className="empty">{kind}</span>}
      <span className="cell">{kind === 'clip' ? <><Film size={10} /> {c ? `${c.frames} f · ${c.w}×${c.h}` : 'clip'}</> : 'frame'}{current ? ' · in use' : ''}</span>
      {!current && <span className="tools"><button className="quiet" title={kind === 'clip' ? 'Use as the clip' : 'Use as the frame'} aria-label={`use ${kind}`} onClick={() => runOnItem({ take: { kind, id } }, 'story.shot.useTake')}>✓ use</button></span>}
    </div>
  )
}

function ShotBoard() {
  const shots = useStory((s) => s.shots)
  const shotId = useStory((s) => s.shotId)
  const shotVersionId = useStory((s) => s.shotVersionId)
  const clipsById = useStory((s) => s.clipsById)
  markUsed('story.shot.release'); markUsed('story.shot.delete')
  const s = shots.find((x) => x.id === shotId)
  if (!s) return <div className="story-empty"><div>Pick a shot on the left, or make one: <b>New shot from this camera</b> on a Stage camera, <b>Make a shot from this clip</b> in Animate.<div className="quick-cards"><CommandButton id="story.shot.new" text /></div></div></div>
  const v = s.versions.find((x) => x.id === (shotVersionId ?? s.current))
  if (!v) return null
  const clip = v.clip_id ? clipsById[v.clip_id] : undefined
  const why = sy().finalizeWhy(v)
  return (
    <div className="cast-page shot-board" tabIndex={0} onKeyDown={(e) => { storyKey('shots', e.nativeEvent) }}>
      <section>
        <h3>Versions <span className="hint">each owns one clip; the Flow pins one, the Episode takes the final one</span></h3>
        <div className="version-cards">
          {s.versions.map((x) => {
            const c = x.clip_id ? clipsById[x.clip_id] : undefined
            const thumb = x.frame_asset_id ?? c?.asset_id ?? null
            return (
              <div key={x.id} className={`version-card${x.id === v.id ? ' active' : ''}`} data-id={x.id} onClick={() => sy().selectShot(s.id, x.id)}>
                {thumb ? <img src={api.thumbUrl(thumb, 256)} alt="" /> : <span className="empty">no frame</span>}
                <span className="cell">{x.id} · {x.state}{sy().shotStale(x) ? ' · stale' : ''}{c ? ` · ${c.frames} f ${c.w}×${c.h}` : x.clip_id ? ' · clip' : ' · no clip'}</span>
              </div>
            )
          })}
        </div>
      </section>
      <section>
        <h3>{s.name} <span className="muted">— {v.id} ({v.state})</span></h3>
        <div className="shot-player">
          {clip ? <video controls src={api.fileUrl(`/clips/${clip.id}/proxy.mp4`)} aria-label="the version's clip" />
            : v.frame_asset_id ? <img src={api.thumbUrl(v.frame_asset_id, 1024)} alt="" aria-label="the version's frame" />
            : <span className="hint">No frame or clip yet — Make frame ▸ / Make clip ▸ below (Generate, Animate or the stage camera), or use a take.</span>}
        </div>
        <div className="counts">{why ? <span className="hint">{why}</span> : v.state === 'final' ? <span>final · the clip the Flow and the Episode bind</span> : <span>ready to mark final</span>}</div>
        <div className="make-row"><MakeMenus /><span className="hint">{v.state === 'open' ? 'Generate or Animate open for this version; what they make comes back here as takes' : 'final — make a new version for more takes'}</span></div>
      </section>
      <section>
        <h3>Takes <span className="hint">everything tried for this version · ✓ use makes one the frame or the clip</span></h3>
        {!v.takes.length && <div className="empty">No takes yet.</div>}
        <div className="story-cands" role="list">
          {[...v.takes].reverse().map((t) => <Take key={`${t.kind}:${t.id}`} kind={t.kind} id={t.id} current={(t.kind === 'image' ? v.frame_asset_id : v.clip_id) === t.id} clipsById={clipsById} />)}
        </div>
      </section>
    </div>
  )
}

// ------------------------------------------------------------------ Stage: play mode (no model is ever invoked — loom R143)
function PlayView() {
  markUsed('story.flow.next'); markUsed('story.flow.restart'); markUsed('story.flow.stop')
  const play = useStory((s) => s.play)
  const flowNodes = useStory((s) => s.flowNodes)
  const shots = useStory((s) => s.shots)
  const clipsById = useStory((s) => s.clipsById)
  const profiles = useStory((s) => s.profiles)
  if (!play) return null
  const n = play.node ? flowNodes[play.node] : undefined
  const sh = n?.shot_id ? shots.find((s) => s.id === n.shot_id) : undefined
  const v = sh?.versions.find((x) => x.id === (n?.shot_version ?? sh.current))
  const clip = v?.clip_id ? clipsById[v.clip_id] : undefined
  const speaker = (id: string | null | undefined) => (id ? profiles.find((p) => p.id === id)?.name ?? id : null)
  return (
    <div className="play-view" data-testid="play-view">
      <div className="play-stage">
        {n && clip ? <video key={clip.id} autoPlay controls src={api.fileUrl(`/clips/${clip.id}/proxy.mp4`)} aria-label="the node's clip" />
          : n && v?.frame_asset_id ? <img src={api.thumbUrl(v.frame_asset_id, 1024)} alt="" aria-label="the node's frame" />
          : <div className="play-card">{play.ended ? 'The end.' : n ? `${NODE_LABEL[n.type]} · ${n.title || ''}${n.shot_id ? '' : ' (no shot bound)'}` : ''}</div>}
      </div>
      {n?.type === 'dialogue' && n.lines.length > 0 && <div className="play-lines">{n.lines.map((l, i) => <p key={i}>{speaker(l.speaker) && <b>{speaker(l.speaker)}: </b>}{l.text}</p>)}</div>}
      <div className="play-controls">
        {play.ended ? <button className="primary restart" onClick={() => runCommand('story.flow.restart')}>Restart</button>
          : n?.type === 'choice' ? optionsAvailable(n, play.vars).map((o: FlowOption) => <button key={o.id} className="option primary" onClick={() => sy().playNext(o.id)}>{o.label || '…'}</button>)
          : <button className="primary next" onClick={() => runCommand('story.flow.next')}>Next ▸</button>}
        {!play.ended && <CommandButton id="story.flow.restart" />}<button onClick={() => runCommand('story.flow.stop')}>Stop</button>
        <span className="hint">{play.trail.length} step{play.trail.length === 1 ? '' : 's'} · {Object.entries(play.vars).map(([k, val]) => `${k} = ${String(val)}`).join(' · ') || 'no variables'}</span>
      </div>
    </div>
  )
}

export function Stage() {
  const project = useSession((s) => s.project)
  const { active: tab } = useSuiteRail()
  const play = useStory((s) => s.play)
  markUsed('story.world.addStyle'); markUsed('story.world.addBeat'); markUsed('story.world.addVariable'); markUsed('story.world.remove'); markUsed('story.cast.new'); markUsed('story.cast.newPlace'); markUsed('story.cast.newProp')
  if (!project?.open) return <div className="story-empty"><div>Open or create a project to begin.</div></div>
  if (tab === 'cast') return <CastPage />
  if (tab === 'shots') return <ShotBoard />
  if (tab === 'flow') return play ? <PlayView /> : <FlowCanvas />
  if (tab === 'episode') return <SequenceStage />
  return <WorldEditor />
}

// ------------------------------------------------------------------ Inspector
function CastInspector() {
  const profiles = useStory((s) => s.profiles)
  const profileId = useStory((s) => s.profileId)
  const versionId = useStory((s) => s.versionId)
  const picked = useStory((s) => s.picked)
  const p = profiles.find((x) => x.id === profileId)
  if (!p) return <span className="hint">Nothing selected.</span>
  const v = p.versions.find((x) => x.id === (versionId ?? p.current))
  return (
    <div className="story-insp">
      <h4>{p.name}</h4>
      <div className="kv">
        <span>name</span><input type="text" value={p.name} aria-label="profile name" onChange={(e) => sy().renameProfile(e.target.value)} />
        <span>class</span>
        <select value={p.cls} aria-label="profile class" onChange={(e) => void sy().patchProfile({ cls: e.target.value as ProfileClass })}>{(Object.keys(CLASS_LABEL) as ProfileClass[]).map((c) => <option key={c} value={c}>{CLASS_LABEL[c]}</option>)}</select>
        <span>current</span>
        <select value={p.current} aria-label="current version" onChange={(e) => void sy().patchProfile({ current: e.target.value })}>{p.versions.map((x) => <option key={x.id} value={x.id}>{versionName(x)}</option>)}</select>
        <span>versions</span><span>{p.versions.length}</span>
        <span>mention</span><span className="mono">@{p.name}</span>
      </div>
      {v && <>
        <h4>Version {versionName(v)} · {v.state}</h4>
        <div className="kv">
          <span>hero</span><span>{v.hero_asset_id ? <img className="insp-thumb small" src={api.thumbUrl(v.hero_asset_id, 256)} alt="" /> : '—'}</span>
          <span>reference set</span><span className="mono">{v.group_id}</span>
          <span>candidates</span><span className="mono">{v.candidates_group_id ?? '—'}</span>
          <span>from</span><span>{v.derived_from ?? '—'}</span>
          <span>created</span><span>{v.created_at.slice(0, 16).replace('T', ' ')}</span>
        </div>
        <div className="verbs"><CommandButton id="story.cast.useAsSubject" text /></div>
        <div className="verbs"><CommandButton id="story.cast.expand" text /><CommandButton id="story.cast.lock" text /><CommandButton id="story.cast.newVersion" text /></div>
        <div className="verbs"><CommandButton id="story.cast.openGroup" text /><CommandButton id="story.cast.openCandidates" text /></div>
        <TrainingBlock p={p} v={v} />
        {p.cls === 'character' && <VoicesBlock p={p} />}
        {picked.length > 0 && <><h4>{picked.length} candidate{picked.length === 1 ? '' : 's'} selected</h4><div className="verbs"><CommandButton id="story.cast.keep" text /><CommandButton id="story.cast.reject" text /><CommandButton id="story.cast.setHero" text /></div></>}
      </>}
      <div className="verbs"><CommandButton id="story.cast.delete" text /></div>
    </div>
  )
}

function ShotInspector() {
  const shots = useStory((s) => s.shots)
  const shotId = useStory((s) => s.shotId)
  const shotVersionId = useStory((s) => s.shotVersionId)
  const clipsById = useStory((s) => s.clipsById)
  const stagesLite = useStory((s) => s.stagesLite)
  const flowNodes = useStory((s) => s.flowNodes)
  const s = shots.find((x) => x.id === shotId)
  if (!s) return <span className="hint">Nothing selected.</span>
  const v = s.versions.find((x) => x.id === (shotVersionId ?? s.current))
  const clip = v?.clip_id ? clipsById[v.clip_id] : undefined
  const stage = v?.stage_id ? stagesLite.find((x) => x.id === v.stage_id) : undefined
  return (
    <div className="story-insp">
      <h4>{s.name}</h4>
      <div className="kv">
        <span>name</span><input type="text" value={s.name} aria-label="shot name" onChange={(e) => sy().renameShot(e.target.value)} />
        <span>owner</span><span>{s.owner_node ? nodeName(flowNodes, s.owner_node) : 'unbound (a Flow node binds it)'}</span>
        <span>current</span>
        <select value={s.current} aria-label="current shot version" onChange={(e) => void sy().patchShot({ current: e.target.value })}>{s.versions.map((x) => <option key={x.id} value={x.id}>{x.id}</option>)}</select>
        <span>versions</span><span>{s.versions.length}</span>
      </div>
      {v && <ShotVersionFields v={v} clip={clip} stage={stage} />}
      {v && <RecipeSteps shotId={s.id} version={v.id} editable={v.state === 'open'} run="story.shot.runStale" />}{/* RC0 (D96) */}
      {v && v.state === 'open' && <LipsyncBlock v={v} ownerNode={s.owner_node ?? null} />}
      <div className="verbs"><CommandButton id="story.shot.release" text /><CommandButton id="story.shot.delete" text /></div>
    </div>
  )
}

function ShotVersionFields({ v, clip, stage }: { v: ShotVersion; clip?: { frames: number; fps: number; w: number; h: number }; stage?: { name: string; revision: number } }) {
  return (
    <>
      <h4>Version {v.id} · {v.state}{sy().shotStale(v) ? ' · stale' : ''}</h4>
      <div className="kv">
        <span>source</span><span>{v.stage_id ? `${stage?.name ?? v.stage_id} · camera ${v.camera_id}${v.stage_revision !== null && v.stage_revision !== undefined ? ` · rev ${v.stage_revision}` : ''}` : 'none (a clip or takes)'}</span>
        <span>frame</span><span>{v.frame_asset_id ? <img className="insp-thumb small" src={api.thumbUrl(v.frame_asset_id, 256)} alt="" /> : '—'}</span>
        <span>clip</span><span>{clip ? `${clip.frames} f @ ${clip.fps} · ${clip.w}×${clip.h}` : v.clip_id ?? '—'}</span>
        <span>takes</span><span>{v.takes.length}</span>
        <span>from</span><span>{v.derived_from ?? '—'}</span>
        <span>created</span><span>{v.created_at.slice(0, 16).replace('T', ' ')}</span>
        {v.finalized_at && <><span>marked final</span><span>{v.finalized_at.slice(0, 16).replace('T', ' ')}</span></>}
      </div>
      <div className="verbs"><CommandButton id="story.shot.finalize" text /><CommandButton id="story.shot.newVersion" text /></div>
      <div className="verbs"><MakeMenus /></div>
      <div className="verbs"><CommandButton id="story.shot.openStage" text /><CommandButton id="story.shot.openAnimate" text /></div>
    </>
  )
}

function LinesEditor({ n }: { n: FlowNode }) {
  const profiles = useStory((s) => s.profiles)
  const voices = useStory((s) => s.voices)
  const voiceId = useStory((s) => s.voiceId)
  const caps = useSession((s) => s.capabilities?.voice)
  const setLines = (lines: FlowNode['lines']) => void sy().patchNode(n.id, { lines })
  return (
    <div className="lines-editor">
      {n.lines.map((l, i) => (
        <div key={i} className="line-row">
          <select value={l.speaker ?? ''} aria-label={`speaker ${i + 1}`} onChange={(e) => setLines(n.lines.map((x, k) => (k === i ? { ...x, speaker: e.target.value || null } : x)))}>
            <option value="">(no speaker)</option>{profiles.filter((p) => p.cls === 'character').map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <input type="text" value={l.text} aria-label={`line ${i + 1}`} placeholder="the line" onChange={(e) => setLines(n.lines.map((x, k) => (k === i ? { ...x, text: e.target.value } : x)))} />
          <LineVoice n={n} i={i} l={l} available={!!caps?.available} />
          <button className="quiet" title="Remove the line" aria-label={`remove line ${i + 1}`} onClick={() => setLines(n.lines.filter((_, k) => k !== i))}>✕</button>
        </div>
      ))}
      <button className="quiet" onClick={() => setLines([...n.lines, { speaker: null, text: '', audio_asset_id: null, audio_text: null }])} title="Add a line">+ line</button>
      {caps?.available && n.lines.length > 0 && (
        <div className="voice-row">
          <select aria-label="fallback voice" value={voiceId ?? ''} title="The voice for lines whose speaker has none (a character's own voice is set in Cast)" onChange={(e) => sy().setVoiceId(e.target.value || null)}>
            <option value="">voice for lines without a speaker's own…</option>{voices.map((v) => <option key={v.id} value={v.id}>{voiceLabel(v)}</option>)}
          </select>
          <CommandButton id="story.flow.voiceAll" text />
        </div>
      )}
    </div>
  )
}

/** CN2: a line's voice — ▶ plays the spoken line (marked when the words changed since), 🎙 speaks it (its speaker's voice, else the fallback). */
function LineVoice({ n, i, l, available }: { n: FlowNode; i: number; l: FlowNode['lines'][number]; available: boolean }) {
  markUsed('story.flow.voiceLine')
  const jobs = useSession((s) => s.jobs)
  const job = ttsJobFor(jobs, n.id, i)
  const busy = !!job && ['staged', 'queued', 'running'].includes(job.status)
  const stale = !!l.audio_asset_id && l.audio_text !== l.text
  const audio = l.audio_asset_id
  return (
    <span className="line-voice">
      {audio && <button className={`quiet play${stale ? ' stale' : ''}`} title={stale ? 'Play the spoken line — the words changed since; voice it again' : 'Play the spoken line'} aria-label={`play line ${i + 1}`} onClick={() => sy().playLine(audio)}>▶</button>}
      <button className="quiet" disabled={busy || !available || !l.text.trim()} aria-label={`voice line ${i + 1}`}
        title={busy ? `speaking… (${job?.status}${job?.progress_text ? ` · ${job.progress_text}` : ''})` : job?.status === 'failed' ? `the last voice job failed: ${job.error ?? ''} — try again` : audio ? 'Voice this line again' : "Voice this line (its speaker's voice, else the voice picked below)"}
        onClick={() => runOnItem({ line: { node: n.id, index: i } }, 'story.flow.voiceLine')}>{busy ? '…' : '🎙'}</button>
    </span>
  )
}

function OptionsEditor({ n }: { n: FlowNode }) {
  const world = useStory((s) => s.world)
  const vars = world?.variables ?? []                                                           // derived in render: a selector must not return a fresh array
  const setOptions = (options: FlowNode['options']) => void sy().patchNode(n.id, { options })
  return (
    <div className="lines-editor">
      {n.options.map((o, i) => (
        <div key={o.id} className="line-row option-row">
          <input type="text" value={o.label} aria-label={`option ${i + 1}`} placeholder="the option's label" onChange={(e) => setOptions(n.options.map((x) => (x.id === o.id ? { ...x, label: e.target.value } : x)))} />
          <select value={o.require?.var ? `${String(o.require.var)}=${String(o.require.value)}` : ''} aria-label={`option ${i + 1} requires`} title="Offered only when this holds" onChange={(e) => { const [vv, val] = e.target.value.split('='); setOptions(n.options.map((x) => (x.id === o.id ? { ...x, require: vv ? { var: vv, value: val === 'true' ? true : val === 'false' ? false : val } : null } : x))) }}>
            <option value="">always</option>{vars.flatMap((v) => (v.type === 'bool' ? ['true', 'false'] : v.values).map((val) => <option key={`${v.name}=${val}`} value={`${v.name}=${val}`}>{v.name} = {val}</option>))}
          </select>
          <button className="quiet" title="Remove the option" aria-label={`remove option ${i + 1}`} onClick={() => setOptions(n.options.filter((x) => x.id !== o.id))}>✕</button>
        </div>
      ))}
      <button className="quiet" onClick={() => setOptions([...n.options, { id: `opt_${crypto.randomUUID().replace(/-/g, '').slice(0, 8)}`, label: '', require: null, set: [] }])} title="Add an option">+ option</button>
    </div>
  )
}

function SetsEditor({ n, sets, onChange }: { n: FlowNode; sets: Record<string, unknown>[]; onChange: (s: Record<string, unknown>[]) => void }) {
  const world = useStory((s) => s.world)
  const vars = world?.variables ?? []                                                           // derived in render: a selector must not return a fresh array
  void n
  return (
    <div className="lines-editor">
      {sets.map((s, i) => (
        <div key={i} className="line-row set-row">
          <select value={String(s.var ?? '')} aria-label={`set ${i + 1} variable`} onChange={(e) => onChange(sets.map((x, k) => (k === i ? { ...x, var: e.target.value } : x)))}><option value="">variable</option>{vars.map((v) => <option key={v.name} value={v.name}>{v.name}</option>)}</select>
          {(() => { const v = vars.find((x) => x.name === s.var); const vals = v ? (v.type === 'bool' ? ['true', 'false'] : v.values) : []
            return <select value={String(s.value ?? '')} aria-label={`set ${i + 1} value`} onChange={(e) => onChange(sets.map((x, k) => (k === i ? { ...x, value: e.target.value === 'true' ? true : e.target.value === 'false' ? false : e.target.value } : x)))}>{vals.map((val) => <option key={val} value={val}>{val}</option>)}</select> })()}
          <button className="quiet" aria-label={`remove set ${i + 1}`} onClick={() => onChange(sets.filter((_, k) => k !== i))}>✕</button>
        </div>
      ))}
      <button className="quiet" onClick={() => onChange([...sets, { var: vars[0]?.name ?? '', value: vars[0] ? (vars[0].type === 'bool' ? true : vars[0].values[0]) : '' }])} title="Set a variable">+ set</button>
    </div>
  )
}

/** D90 (02 §4.2): the node's board — an album group (picked here, or a group card dropped on the node), its cover and count; a Dialogue or
 *  Shot node's board gives Make frame its references. */
function BoardField({ n }: { n: FlowNode }) {
  const tree = useAlbum((a) => a.tree)
  useEffect(() => { if (!useAlbum.getState().tree) void useAlbum.getState().load() }, [])
  const g = findNode(tree, n.board_group_id)
  return (
    <>
      <h4>Board <span className="hint">references, mood, places — a group of the album</span></h4>
      <div className="kv board-field">
        <span>group</span>
        <select value={n.board_group_id ?? ''} aria-label="board" onChange={(e) => void sy().patchNode(n.id, { board_group_id: e.target.value || null })}>
          <option value="">(no board)</option>
          {n.board_group_id && !g && <option value={n.board_group_id}>(a deleted group)</option>}
          {flatGroups(tree).map(({ node, depth }) => <option key={node.id} value={node.id}>{`${'\u00a0\u00a0'.repeat(depth)}${node.name} · ${node.total}`}</option>)}
        </select>
        {g && <><span>cover</span><span>{g.cover_ids[0] ? <img className="insp-thumb small" src={api.thumbUrl(g.cover_ids[0], 256)} alt="" /> : <span className="hint">an empty group</span>}</span></>}
      </div>
      <div className="verbs"><CommandButton id="story.flow.openBoard" text /><CommandButton id="story.flow.clearBoard" text /></div>
    </>
  )
}

/** D93 (C7): where a Dialogue or Shot node happens — a Cast place (its hero beside the select); Make frame ▸ links Generate's scene to it. */
function PlaceField({ n }: { n: FlowNode }) {
  const profiles = useStory((s) => s.profiles)
  const places = profiles.filter((p) => p.cls === 'place')
  const cur = n.place_id ? profiles.find((p) => p.id === n.place_id) : undefined
  const hero = cur?.versions.find((v) => v.id === cur.current)?.hero_asset_id
  return (
    <div className="kv place-field">
      <span>where</span>
      <select value={n.place_id ?? ''} aria-label="where (a Cast place)" title="A Cast place: Make frame ▸ links Generate's scene to it (its sheet and references)" onChange={(e) => void sy().patchNode(n.id, { place_id: e.target.value || null })}>
        <option value="">(no place)</option>
        {n.place_id && !cur && <option value={n.place_id}>(a deleted place)</option>}
        {places.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
      {cur && <><span /><span className="place-hero">{hero ? <img className="place-thumb" src={api.thumbUrl(hero, 256)} alt="" /> : null}<span className="hint">{cur.name} · {cur.current}</span></span></>}
      {!places.length && <><span /><span className="hint">no places in the Cast yet — New profile… (place)</span></>}
    </div>
  )
}

/** D93 follow-up: which version of each speaking character the node uses — a chip per speaker ("current ▾", or "v2 · rain gear ▾" when
 *  pinned); Make frame ▸ uses it, unless the bound shot's stage binds the character to another version (the Stage binding wins — said here). */
function SpeakerVersions({ n }: { n: FlowNode }) {
  const profiles = useStory((s) => s.profiles)
  const shots = useStory((s) => s.shots)
  const sh = n.shot_id ? shots.find((s) => s.id === n.shot_id) : undefined
  const stageId = sh?.versions.find((v) => v.id === (n.shot_version ?? sh.current))?.stage_id ?? null
  const [loaded, setLoaded] = useState<{ stage: string; figs: StageObject[] } | null>(null)        // the bound shot's stage figures (Stage wins)
  const figs = loaded && loaded.stage === stageId ? loaded.figs : []
  useEffect(() => {
    let off = false
    if (stageId) void unwrap(http.GET('/stages/{st_id}', { params: { path: { st_id: stageId } } }))
      .then((s) => { if (!off) setLoaded({ stage: stageId, figs: s.objects.filter((o) => o.kind === 'mannequin') }) }).catch(() => { if (!off) setLoaded({ stage: stageId, figs: [] }) })
    return () => { off = true }
  }, [stageId])
  const speakers = speakersOf(n, profiles)
  if (!speakers.length) return null
  const pin = (pid: string, vid: string | null) => {
    const next = { ...(n.speaker_versions ?? {}) }
    if (vid) next[pid] = vid; else delete next[pid]
    void sy().patchNode(n.id, { speaker_versions: next })
  }
  return (
    <>
      <h4>Speakers <span className="hint">the version each one wears here</span></h4>
      <div className="speaker-versions" data-testid="speaker-versions">
        {speakers.map((p) => {
          const pinned = n.speaker_versions?.[p.id] ?? null
          const pv = pinned ? p.versions.find((v) => v.id === pinned) : undefined
          const cur = p.versions.find((v) => v.id === p.current)
          const sv = speakerVersion(p, n, figs)
          const hero = (pv ?? cur)?.hero_asset_id
          const items = (): MenuItem[] => [
            { label: `current (${cur ? versionName(cur) : p.current})`, checked: !pinned, run: () => pin(p.id, null) }, sep,
            ...p.versions.map((v) => ({ label: `${versionName(v)}${v.state === 'final' ? ' · final' : ''}`, checked: pinned === v.id, run: () => pin(p.id, v.id) })),
          ]
          const stageWins = sv.from === 'stage' && sv.version !== (pv ? pv.id : p.current)
          return (
            <div key={p.id} className="speaker-row" data-profile={p.id}>
              {hero ? <img className="speaker-thumb" src={api.thumbUrl(hero, 256)} alt="" /> : <span className="speaker-thumb" />}
              <span className="who">{p.name}</span>
              <button type="button" className={`version-chip${pv ? ' pinned' : ''}`} aria-haspopup="menu" aria-label={`${p.name}'s version`}
                title={`The version of ${p.name} this node uses — Make frame ▸ links the subject at it (press and drag to one, or click)`}
                onPointerDown={(e) => openPressMenu(e, items)} onContextMenu={(e) => e.preventDefault()}>
                {pv ? versionName(pv) : 'current'} <span className="caret">▾</span>
              </button>
              {pinned && !pv && <span className="hint">{pinned} was deleted — the current one is used</span>}
              {stageWins && <span className="hint stage-wins">the shot's stage binds {sv.version} — the Stage binding wins</span>}
            </div>
          )
        })}
      </div>
    </>
  )
}

function NodeInspector() {
  const nodeId = useStory((s) => s.nodeId)
  const flowNodes = useStory((s) => s.flowNodes)
  const shots = useStory((s) => s.shots)
  const problems = useStory((s) => s.problems)
  const world = useStory((s) => s.world)
  const vars = world?.variables ?? []                                                           // derived in render: a selector must not return a fresh array
  markUsed('story.flow.makeFrame'); markUsed('story.flow.makeClip'); markUsed('story.flow.openBoard'); markUsed('story.flow.clearBoard')
  markUsed('story.flow.delete'); markUsed('story.flow.duplicate'); markUsed('story.flow.newShot'); markUsed('story.flow.unbind'); markUsed('story.flow.openShot'); markUsed('story.flow.validate'); markUsed('story.flow.fit'); markUsed('story.flow.voiceAll')
  for (const t of ['start', 'hub', 'dialogue', 'choice', 'condition', 'action', 'shot', 'jump', 'comment']) markUsed(`story.flow.add.${t}`)
  const n = nodeId ? flowNodes[nodeId] : undefined
  const mine = problems?.filter((p) => !n || p.node_id === n.id || (!p.node_id && !n)) ?? []
  if (!n) return (
    <div className="story-insp">
      {problems && <><h4>Validation</h4><ul className="flow-problems">{problems.map((p, i) => <li key={i} className={p.code}><button className="link" onClick={() => sy().selectNode(p.node_id)}>{p.message}</button></li>)}{!problems.length && <li className="ok">No problems.</li>}</ul></>}
      <span className="hint">Select a node on the canvas or in the outline.</span>
    </div>
  )
  const sh = n.shot_id ? shots.find((s) => s.id === n.shot_id) : undefined
  const unbound = shots.filter((s) => !s.owner_node || s.owner_node === n.id)
  const visual = n.type === 'dialogue' || n.type === 'shot'
  return (
    <div className="story-insp node-insp">
      <h4>{NODE_LABEL[n.type]} · {n.title || n.id}</h4>
      <div className="kv">
        <span>type</span>
        <select value={n.type} aria-label="node type" onChange={(e) => void sy().patchNode(n.id, { type: e.target.value as FlowNode['type'] })}>{(Object.keys(NODE_LABEL) as FlowNode['type'][]).map((t) => <option key={t} value={t}>{NODE_LABEL[t]}</option>)}</select>
        <span>title</span><input type="text" value={n.title} aria-label="node title" onChange={(e) => void sy().patchNode(n.id, { title: e.target.value })} />
        {n.type === 'comment' && <><span>text</span><textarea rows={3} value={n.text} aria-label="note text" onChange={(e) => void sy().patchNode(n.id, { text: e.target.value })} /></>}
        {n.type === 'shot' && <><span>line</span><textarea rows={2} value={n.text} aria-label="shot line" placeholder="what happens (a beat's line lands here)" onChange={(e) => void sy().patchNode(n.id, { text: e.target.value })} /></>}
        {n.type === 'jump' && <><span>target</span><select value={n.target ?? ''} aria-label="jump target" onChange={(e) => void sy().patchNode(n.id, { target: e.target.value || null })}><option value="">(none)</option>{Object.values(flowNodes).filter((x) => x.id !== n.id && x.type !== 'comment').map((x) => <option key={x.id} value={x.id}>{x.title || NODE_LABEL[x.type]}</option>)}</select></>}
        {n.type === 'condition' && <><span>condition</span><div className="cond-row">
          <select value={n.cond?.var ?? ''} aria-label="condition variable" onChange={(e) => void sy().patchNode(n.id, { cond: { var: e.target.value, op: n.cond?.op ?? 'eq', value: n.cond?.value ?? true } })}><option value="">variable</option>{vars.map((v) => <option key={v.name} value={v.name}>{v.name}</option>)}</select>
          <select value={n.cond?.op ?? 'eq'} aria-label="condition operator" onChange={(e) => void sy().patchNode(n.id, { cond: { var: n.cond?.var ?? '', op: e.target.value as 'eq' | 'ne', value: n.cond?.value ?? true } })}><option value="eq">=</option><option value="ne">≠</option></select>
          {(() => { const v = vars.find((x) => x.name === n.cond?.var); const vals = v ? (v.type === 'bool' ? ['true', 'false'] : v.values) : ['true', 'false']
            return <select value={String(n.cond?.value ?? 'true')} aria-label="condition value" onChange={(e) => void sy().patchNode(n.id, { cond: { var: n.cond?.var ?? '', op: n.cond?.op ?? 'eq', value: e.target.value === 'true' ? true : e.target.value === 'false' ? false : e.target.value } })}>{vals.map((val) => <option key={val} value={val}>{val}</option>)}</select> })()}
        </div></>}
      </div>
      {n.type === 'dialogue' && <><h4>Lines</h4><LinesEditor n={n} /></>}
      {n.type === 'choice' && <><h4>Options <span className="hint">each is an out-port</span></h4><OptionsEditor n={n} /></>}
      {n.type === 'action' && <><h4>Sets</h4><SetsEditor n={n} sets={n.set} onChange={(set) => void sy().patchNode(n.id, { set })} /></>}
      {visual && <PlaceField n={n} />}
      {visual && <SpeakerVersions n={n} />}
      {visual && <>
        <h4>Shot</h4>
        {sh ? <div className="kv"><span>bound</span><span>{sh.name} · {n.shot_version ?? sh.current} · {sh.versions.find((v) => v.id === (n.shot_version ?? sh.current))?.state ?? '?'}</span>
          <span>version</span><select value={n.shot_version ?? sh.current} aria-label="bound version" onChange={(e) => void sy().bindShot(n.id, sh.id, e.target.value)}>{sh.versions.map((v) => <option key={v.id} value={v.id}>{v.id}{v.state === 'final' ? ' · final' : ''}</option>)}</select></div>
          : <div className="kv"><span>bind</span><select value="" aria-label="bind shot" onChange={(e) => { if (e.target.value) void sy().bindShot(n.id, e.target.value) }}><option value="">an unbound shot…</option>{unbound.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>}
        <div className="verbs"><CommandButton id="story.flow.newShot" text /><CommandButton id="story.flow.openShot" text /><CommandButton id="story.flow.unbind" text /></div>
        <div className="verbs"><CommandButton id="story.flow.makeFrame" text /><CommandButton id="story.flow.makeClip" text /></div>
      </>}
      <BoardField n={n} />
      {mine.length > 0 && <><h4>Problems</h4><ul className="flow-problems">{mine.map((p, i) => <li key={i} className={p.code}>{p.message}</li>)}</ul></>}
      <div className="verbs"><CommandButton id="story.flow.duplicate" text /><CommandButton id="story.flow.delete" text /></div>
    </div>
  )
}

export function Inspector() {
  const world = useStory((s) => s.world)
  const lib = useLibrary((l) => l.library)                                // D92 (a stable selection: the record, not a fresh list)
  const libEntries = lib?.entries ?? []
  const selected = useStory((s) => s.selected)
  const project = useSession((s) => s.project)
  const { active: tab } = useSuiteRail()
  if (!project?.open) return <span className="hint">Nothing selected.</span>
  if (tab === 'cast') return <CastInspector />
  if (tab === 'shots') return <ShotInspector />
  if (tab === 'flow') return <NodeInspector />
  if (tab === 'episode') return <SequenceInspector />
  if (!world) return <span className="hint">Nothing selected.</span>
  const fmt = project.format
  const style = selected?.kind === 'style' ? world.styles.find((s) => s.id === selected.id) : undefined
  const beat = selected?.kind === 'beat' ? world.spine.find((b) => b.id === selected.id) : undefined
  const variable = selected?.kind === 'variable' ? world.variables.find((v) => v.name === selected.id) : undefined
  const entry = selected?.kind === 'entry' ? libEntries.find((e) => e.id === selected.id) : undefined
  return (
    <div className="story-insp">
      <h4>World</h4>
      <div className="kv">
        <span>format</span><span title="Fixed at the project's creation; a shot's clip must be at this size to be marked final">{fmt ? `${fmt.aspect[0]}:${fmt.aspect[1]} · ${fmt.width}×${fmt.height} · ${fmt.fps} fps` : '—'}</span>
        <span>styles</span><span>{world.styles.length}</span>
        <span>library</span><span>{libEntries.length}</span>
        <span>beats</span><span>{world.spine.length}</span>
        <span>variables</span><span>{world.variables.length}</span>
        <span>revision</span><span>{world.revision}</span>
      </div>
      {style && <StyleEditor key={style.id} s={style} isDefault={world.default_style === style.id} />}
      {entry && <EntryEditor key={entry.id} e={entry} />}
      {selected?.kind === 'panel' && <PanelEditor name={selected.id} />}
      {beat && <>
        <h4>Beat {world.spine.indexOf(beat) + 1}</h4>
        <div className="kv">
          <span>title</span><input type="text" value={beat.title} aria-label="selected beat title" onChange={(e) => sy().setBeat(beat.id, { title: e.target.value })} />
          <span>line</span><textarea rows={3} value={beat.line} aria-label="selected beat line" onChange={(e) => sy().setBeat(beat.id, { line: e.target.value })} />
        </div>
        <div className="verbs"><CommandButton id="story.world.beatUp" text /><CommandButton id="story.world.beatDown" text /><CommandButton id="story.world.beatToNode" text /><CommandButton id="story.world.remove" text /></div>
      </>}
      {variable && <>
        <h4>Variable · {variable.name}</h4>
        <div className="kv">
          <span>type</span><span>{variable.type}</span>
          <span>values</span><span>{variable.type === 'enum' ? variable.values.join(', ') : 'true / false'}</span>
          <span>default</span><span>{String(variable.default)}</span>
        </div>
        <div className="verbs"><CommandButton id="story.world.remove" text /></div>
      </>}
    </div>
  )
}
