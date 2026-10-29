// 17 (D85): the Story suite's parts (StorySuite.ts registers them) — SY0: the World tab. Panel: the sections with their counts and the
// adders; Stage: the editor over story/world.json (logline, synopsis, styles, the spine, variables); Inspector: the project format (the
// finalize gate), counts, the selected item's fields (a style's editor: StyleWorld.tsx, D90; a library entry's and a saved panel's:
// LibraryWorld.tsx, D92). SY1: the Cast tab — Panel: the profiles by class; Strip: the
// version selector; Stage: the readiness row (D125), the version page (hero, the character sheet — D93 B4, the coverage grid, the candidates and Add to the reference set);
// Inspector: the profile and the version. Mouse-first (D32): every verb is a button or a menu entry.
import { Film, ImagePlus, Lock } from 'lucide-react'
import { IdeaBench, IdeaInspector, IdeasList } from './Ideas'
import { useIdeas } from './ideasStore'
import { Help } from '../../frame/Help'
import { lazy, Suspense, useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react'
import { api, http, unwrap } from '../../api/client'
import { CommandButton, MenuButton } from '../../frame/CommandButton'
import { command, markUsed, runCommand, sep, type MenuItem } from '../../frame/commands'
import { openPressMenu, showMenu } from '../../frame/ContextMenu'
import { DEV_HOOKS } from '../../devHooks'
import { useSuiteRail } from '../../frame/router'
import { useSession } from '../../store/session'
import type { Asset, Shot, ShotVersion, StoryBeat, StoryVariable, WorldStyle } from '../../api/types'
import { cellOf, coverageGrid } from './coverage'
import { ITEM_LABEL, readinessOf, rowSummary, shotNeeds } from './castReady'
import { spineTodo } from './episodeVerbs'
import { ROUTE_LABEL, bareNode } from './board'
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
import { CastBody } from './CastBody'
import { AnimRef, PropModel } from './CastParts'
import { askExpand, castCells, castNext, ITEM_NEXT, itemCommand, makeClipItems, makeFrameItems, NEXT_LABEL, onStoryItem, profileMenu, rowMenu, runOnItem, selectedNext, stageUsers } from './storyCommands'
import { BoardPanel, LinkStageSheet, ShotsBoard, VoiceAllButton } from './ShotsBoard'
import { FlowRecipe, ShotRecipe } from './recipe/StoryRecipe'
import { flatGroups, useAlbum } from '../../store/album'
import { findNode } from './styleSamples'
import { storyKey } from './storyKeys'
import { CLASS_LABEL, SECTIONS, revealClass, sy, ttsJobFor, useStory, voiceLabel, type ProfileClass, type Section } from './storyStore'
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
import { navigate, setRailTab } from '../../frame/router'

/** Dev hook (`window.__loom2Story`, DEV_HOOKS only): the smoke test and scripts/sy_acceptance.py drive the suite through the store. */
// CS2: the skeleton bench loads with the stage's code (three.js), only when opened
const SkeletonBench = lazy(() => import('../stage/SkeletonBench'))
const SkeletonParts = lazy(() => import('../stage/SkeletonBench').then((m) => ({ default: m.SkeletonParts })))

function devHook(): Record<string, unknown> {
  const w = window as unknown as { __loom2Story?: Record<string, unknown> }
  w.__loom2Story ??= { state: () => ({ world: sy().world, selected: sy().selected, section: sy().section, profileId: sy().profileId, versionId: sy().versionId, refPage: sy().refPage, candPage: sy().candPage }),
    load: () => sy().load(), flush: () => sy().flush(),
    addStyle: (name?: string) => sy().addStyle(name), setStyle: (id: string, patch: Partial<WorldStyle>) => sy().setStyle(id, patch), edit: (patch: Record<string, unknown>) => sy().edit(patch as never),
    // SY1
    loadProfiles: () => sy().loadProfiles(), selectProfile: (id: string | null, v?: string | null) => sy().selectProfile(id, v), loadPages: () => sy().loadPages(),
    createProfile: (name: string, cls: ProfileClass, hero?: string | null, appearance?: string) => sy().createProfile(name, cls, hero, appearance),
    expand: (preset: string, seeds = 1, tier: 'draft' | 'full' = 'draft') => sy().expand(preset, seeds, tier), addRefs: (ids: string[]) => sy().addRefs(ids),
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
    openShots: (id: string | null) => { navigate({ suite: 'story', tab: 'shots' }); sy().selectShot(id) },
    openTab: (tab: 'world' | 'cast' | 'shots' | 'flow' | 'episode') => navigate({ suite: 'story', tab }) }
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
  const templates = useStory((s) => s.shotTemplates.length)                                   // RC2e
  const counts: Record<Section, number | null> = {
    logline: null, synopsis: null, styles: world?.styles.length ?? 0, library: entries, panels, templates, spine: world?.spine.length ?? 0, variables: world?.variables.length ?? 0,
  }
  return (
    <div className="story-panel">
      <div className="story-list" role="list">
        {SECTIONS.map((s, i) => [
          s.presets && !SECTIONS[i - 1]?.presets ? <h4 key="presets" className="presets-head">Presets<Help text={"Image's prompt-field presets and saved panels — tools of the making, kept here after the bible."} /></h4> : null,
          <button key={s.id} className={`story-row${section === s.id ? ' active' : ''}`} role="listitem" onClick={() => sy().setSection(s.id)} title={`Show the ${s.label} section`}>
            <span>{s.label}</span>{counts[s.id] !== null && <span className="n">{counts[s.id]}</span>}
          </button>,
        ])}
      </div>
      <h4>Add</h4>
      <div className="verbs"><CommandButton id="story.world.addStyle" text /><CommandButton id="story.world.addEntry" text /><CommandButton id="story.world.addBeat" text /><CommandButton id="story.world.addVariable" text /></div>
      <Help text={"The styles reach Generate's Style picker and the library its preset tiles; a beat becomes a Flow node by hand; the variables drive the Flow's conditions."} />
    </div>
  )
}

// ------------------------------------------------------------------ Panel · Cast
/** SY1: the profiles of the tab. D125 (#2): one class switch — all · characters · places · props (D110's Props tab folded back into Cast). */
function CastTab() {
  const profiles = useStory((s) => s.profiles)
  const profileId = useStory((s) => s.profileId)
  const filter = useStory((s) => s.castFilter)
  const search = useStory((s) => s.castSearch)
  const q = search.trim().toLowerCase()
  const shown = profiles.filter((p) => (filter === 'all' || p.cls === filter) && (!q || p.name.toLowerCase().includes(q)))
  const uses = useStory((s) => s.castUses)
  const shots = useStory((s) => s.shots)
  const flowNodes = useStory((s) => s.flowNodes)
  const board = useIdeas((s) => s.board)
  useEffect(() => { void sy().loadCastUses() }, [profiles, shots, flowNodes])          // D125 (S5): each row says what it owes for its shots
  return (
    <div className="story-panel cast-panel">
      <div className="segmented board-switch" role="group" aria-label="board">{/* proto01_UIcast CW1 (06 §2.1): the kept profiles, or the ideas before them */}
        {(['cast', 'ideas'] as const).map((b) => <button key={b} type="button" className={board === b ? 'active' : ''} aria-pressed={board === b} onClick={() => useIdeas.getState().setBoard(b)}>{b === 'cast' ? 'Cast' : 'Ideas'}</button>)}
        <Help text={"Ideas come before Cast: loose pictures gathered as variants, with their clay, nothing in production yet. Keep ▶ makes one a Cast profile (or a new version of one)."} />
      </div>
      <div className="segmented" aria-label="class">
        {(['all', 'character', 'place', 'prop'] as const).map((c) => <button key={c} className={filter === c ? 'active' : ''} onClick={() => sy().setCastFilter(c)}>{c === 'all' ? 'all' : `${CLASS_LABEL[c]}s`}</button>)}
      </div>
      <input type="search" value={search} aria-label={board === 'ideas' ? 'search ideas' : 'search profiles'} placeholder="search" onChange={(e) => sy().setCastSearch(e.target.value)} />
      {board === 'ideas' ? <IdeasList filter={filter} q={q} /> : <>
      <div className="story-list" role="list">
        {shown.map((p) => {
          const v = p.versions.find((x) => x.id === p.current)
          return (
            <button key={p.id} className={`story-row profile-row${profileId === p.id ? ' active' : ''}`} role="listitem" data-id={p.id} onClick={() => sy().selectProfile(p.id)}
              onContextMenu={(e) => { sy().selectProfile(p.id); showMenu(e, profileMenu()) }}>
              {v?.hero_asset_id ? <img className="pthumb" src={api.thumbUrl(v.hero_asset_id, 256)} alt="" /> : <span className="pthumb empty" />}
              <span className="pname">{p.name}<span className="muted"> · {CLASS_LABEL[p.cls]}</span>
                {v && uses[p.id] && <span className="owes">{rowSummary(readinessOf(p, v, uses[p.id].uses, uses[p.id].refs[v.id]), uses[p.id].uses)}</span>}</span>
              <span className="n">{p.current} <i className={`dot ${v?.state === 'final' ? 'tight' : 'ok'}`} title={v?.state === 'final' ? 'final' : 'open'} /></span>
            </button>
          )
        })}
        {!shown.length && <div className="empty hint">{profiles.length ? (filter === 'prop' ? 'No props yet — New prop…' : 'No profile matches.')
          : 'No profiles yet — New character…, or "Make a character…" on a picture in the Bin'}</div>}
      </div>
      <div className="verbs"><CommandButton id="story.cast.new" text /><CommandButton id="story.cast.newPlace" text /><CommandButton id="story.cast.newProp" text /><CommandButton id="story.cast.lineup" text /></div>
      </>}
    </div>
  )
}

// ------------------------------------------------------------------ Panel · Shots
/** D90 (01 §11.6): a Flow node as the user knows it — its title, else its first line or its type; never the raw id. */
const nodeName = (nodes: Record<string, FlowNode>, id: string): string => { const n = nodes[id]; return n ? n.title || (n.type === 'shot' ? n.lines[0]?.text?.slice(0, 30) : '') || `${NODE_LABEL[n.type]} node` : 'a Flow node' }
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
                <span className="pname">{n.title || (n.type === 'shot' ? n.lines[0]?.text?.slice(0, 30) : NODE_LABEL[n.type]) || NODE_LABEL[n.type]}</span>
                {n.type === 'shot' && <span className="n">{n.shot_id ? 'shot' : '—'}</span>}
              </button>
            ))}
          </div>
        ))}
        {!list.length && <div className="empty hint">No nodes yet — the Strip's ✚ buttons add them; right-click the canvas to add one where you point.</div>}
      </div>
      <h4>Variables<span className="n"> · {world?.variables.length ?? 0}</span></h4>
      <div className="vars">
        {(world?.variables ?? []).map((v) => <div key={v.name} className="kv"><span>{v.name}</span><span>{play ? String(play.vars[v.name]) : `${v.type} · ${String(v.default)}`}</span></div>)}
        {!world?.variables.length && <span className="hint">none <Help text={"Declare them in World."} /></span>}
      </div>
    </div>
  )
}

export function Panel({ tab }: { tab: string }) {
  const project = useSession((s) => s.project)
  useEffect(() => { if (project?.open) { void sy().load(); void sy().loadProfiles(); void sy().loadShots(); void sy().loadFlow(); void sy().loadTemplates(); void useLibrary.getState().load(); void useGenerate.getState().loadPresets() } }, [project?.path]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!project?.open) return <span className="hint">Open or create a project to begin.</span>
  if (tab === 'cast') return <CastTab />
  if (tab === 'shots') return <BoardPanel />                                      // D125 (SP3): the board's filters and legend; the shots are the board
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
  const boardFinals = useStory((s) => s.boardFinals)                               // D125 (SP3): the next step reads the board's records
  const boardCuts = useStory((s) => s.boardCuts)
  const castUses = useStory((s) => s.castUses)                                     // D125 (SP5): the Cast foot's next owed step reads them
  const picked = useStory((s) => s.picked)
  const { active: tab } = useSuiteRail()
  const play = useStory((s) => s.play)
  const flowGraph = useStory((s) => s.flowGraph)
  const flowNodes = useStory((s) => s.flowNodes)
  const seqLane = useSequence((s) => s.lane)
  const seqCurrent = useSequence((s) => s.current)
  const flowStart = useStory((s) => !!s.flowGraph?.start)
  markUsed('story.cast.expand'); markUsed('story.shot.new'); markUsed('story.flow.play'); markUsed('story.flow.stop'); markUsed('story.episode.exportResolve'); markUsed('story.episode.assemble')
  if (tab === 'episode') {
    const issues = seqLane ? laneChecklist().length : 0
    const n = seqLane?.clips.length ?? 0
    return (
      <div>
        {seqCurrent ? <button className="primary" disabled={!n} onClick={() => runCommand('story.episode.exportResolve')} title="The FCPXML with markers and the voice lane, the EDL, the SRT and markers.txt in one folder named after the cut; the checklist asks once, only when something is listed">Export for Resolve ▶</button>
          : <button className="primary" disabled={!flowStart} onClick={() => runCommand('story.episode.assemble')} title="A new cut of one route of the Flow, every shot at its approved take">Assemble from the Flow…</button>}
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
    void clipsById; void boardFinals; void boardCuts
    const why = v ? sy().finalizeWhy(v) : null
    const next = s && v ? selectedNext() : null                                      // D125 (SP3): the foot is the shot's next step
    return (
      <div>
        <button className="primary" disabled={!next} onClick={() => runCommand('story.shot.next')} title="The first step the shot still owes (the board's first owed cell) — Ctrl+Enter">{next ? `${NEXT_LABEL[next]} ▶` : s ? 'Nothing owed ▶' : 'Pick a shot'}</button>
        <div className="estimate">{!s || !v ? <span style={{ color: 'var(--fg3)' }}>pick a shot</span> : v.state === 'final' ? <><span className="dot ok" />{v.id} final</> : why ? <span style={{ color: 'var(--fg3)' }}>{why}</span> : <><span className="dot ok" />{v.id} ready to mark final</>}</div>
      </div>
    )
  }
  if (tab === 'cast') {
    const p = profiles.find((x) => x.id === profileId); const v = p?.versions.find((x) => x.id === (versionId ?? p.current))
    const reason = !p ? 'pick a profile' : !v ? 'no version' : v.state !== 'open' ? `${v.id} is final — expand a new version` : !v.hero_asset_id ? 'no hero image yet' : !caps?.model_id ? 'no model in this build' : expanding ? 'queuing…' : caps.missing.length ? `weights missing: ${caps.missing.join(', ')}` : ''
    const secs = (caps?.seconds ?? 0) * (caps?.presets.full?.cells ?? 0)
    void castUses; void picked
    const next = castNext()                                                           // D125 (S5): the version's next owed step, with the shots that need it
    if (next) return (
      <div>
        <button className="primary" disabled={!itemCommand(next.item)} onClick={() => runCommand('story.cast.next')} title="The first item of the readiness row a shot of this profile still needs">{ITEM_NEXT[next.item]} ▶</button>
        <div className="estimate"><span className="dot tight" />for {next.shots.join(', ')}</div>
      </div>
    )
    return (
      <div>
        <button className="primary" disabled={!!reason} onClick={() => runCommand('story.cast.expand')} title="Image opens with this version as the subject and the coverage grid as its poses; its Expand ▶ lands the images as candidates — Ctrl+Enter">Expand in Image ▶</button>
        <div className="estimate">{reason ? <span style={{ color: 'var(--fg3)' }}>{reason}</span> : <><span className="dot ok" />{caps?.presets.full?.cells ?? '?'} cells · ≈ {Math.max(1, Math.round(secs / 60))} min warm · {caps?.short}</>}</div>
      </div>
    )
  }
  if (!world) return null
  const todo = tab === 'world' ? spineTodo(world.spine, Object.values(flowNodes)).length : 0          // D125 (S4): the World's foot makes the Flow
  return (
    <div>
      {todo > 0 && <button className="primary" onClick={() => runCommand('story.world.flowFromSpine')} title="A Start, then one Shot node per beat not yet made, in a row, connected in the spine's order">Make the Flow from the spine ▶</button>}
      <div className="estimate"><span className={`dot ${saving ? 'tight' : 'ok'}`} />{saving ? 'saving…' : `saved · revision ${world.revision}`}{todo > 0 ? ` · ${todo} beat${todo === 1 ? '' : 's'} without a node` : ''}</div>
    </div>
  )
}

// ------------------------------------------------------------------ Strip
/** D125 (S5, SP5): the version's readiness for the shots it is in, under the strip — each item is its verb (castReady.ts; the bootstrap
 *  strip it replaces had Expand and Curate, now the References item). Done ✓ · owed ○ (a shot needs it) · open – (none does yet). */
const READY_GLYPH = { done: '✓', owed: '○', open: '–' } as const
function ReadinessRow() {
  useStory((s) => s.castUses); useStory((s) => s.profiles); useStory((s) => s.versionId); useStory((s) => s.picked); useStory((s) => s.candPage); useStory((s) => s.refPage)
  useEffect(() => { void sy().loadCastUses() }, [])
  const cells = castCells()
  if (!cells) return null
  return (
    <div className="cast-ready" aria-label="readiness">
      {cells.map((c) => {
        const id = itemCommand(c.item)
        const why = c.state === 'done' ? 'done' : c.shots.length ? `${c.shots.join(', ')} need${c.shots.length === 1 ? 's' : ''} it` : 'no shot needs it yet'
        return (
          <button key={c.item} type="button" className={`ready-item ${c.state}`} data-item={c.item} disabled={!id} onClick={() => { if (id) runCommand(id) }}
            title={`${ITEM_LABEL[c.item]}: ${why}${id ? ` — ${command(id)?.label ?? ''}` : ''}`} aria-label={`${ITEM_LABEL[c.item]}: ${c.state}`}>
            <span className="g">{READY_GLYPH[c.state]}</span>{ITEM_LABEL[c.item]}{c.text ? <span className="t">{c.text}</span> : null}
          </button>
        )
      })}
    </div>
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
    return <div className="story-strip"><span>Episode</span><span className="spacer" /><Help text={"The hand-built render list: shots from the Shots bin, clips from the Clips bin; every join a cut or a dissolve."} /></div>
  }
  if (tab === 'flow') {
    return (
      <div className="story-strip flow-strip">
        <CommandRow ids={['story.flow.add.start', 'story.flow.add.hub', 'story.flow.add.dialogue', 'story.flow.add.choice', 'story.flow.add.condition', 'story.flow.add.action', 'story.flow.add.shot', 'story.flow.add.jump', 'story.flow.add.comment']} />
        <span className="spacer" />
        {problems && <span className={`hint${problems.length ? ' warn' : ''}`}>{problems.length ? `${problems.length} problem${problems.length === 1 ? '' : 's'}` : 'valid'}</span>}
        <VoiceAllButton />
        <CommandButton id="story.flow.validate" />
        {play ? <CommandButton id="story.flow.stop" /> : <CommandButton id="story.flow.play" />}
        <CommandButton id="story.flow.fit" />
      </div>
    )
  }
  if (tab === 'shots') {
    const s = shots.find((x) => x.id === shotId)
    if (!s) return <div className="story-strip"><span>Shots</span><span className="spacer" /><span className="hint">no shot picked</span><Help text={"Pick a shot, or make one from a Stage camera or an Animate clip."} /></div>
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
    if (!p) return <div className="story-strip"><span>Cast</span><span className="spacer" /><span className="hint">no profile picked</span><Help text={'Pick a character, a place or a prop, or make one — from a picture in the Bin, or New character / place / prop.'} /></div>
    const v = p.versions.find((x) => x.id === (versionId ?? p.current))
    return (
      <div className="story-strip">
        <b>{p.name}</b>
        <select aria-label="version" value={v?.id ?? p.current} onChange={(e) => sy().selectProfile(p.id, e.target.value)} title="The version shown (mentions use the current one unless pinned)">
          {p.versions.map((x) => <option key={x.id} value={x.id}>{versionName(x)}{x.id === p.current ? ' · current' : ''}{x.state === 'final' ? ' · final' : ''}</option>)}
        </select>
        <CommandButton id="story.cast.newVersion" />
        {v?.state === 'final' ? <span className="lock-badge" title={`marked final ${v.locked_at ?? ''}`}><Lock size={12} /> final</span> : <CommandButton id="story.cast.lock" />}
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
        <h3>Logline<Help text={"One sentence."} /></h3>
        <textarea rows={2} value={world.logline} aria-label="logline" placeholder="Who wants what, and what stands in the way." onChange={(e) => sy().edit({ logline: e.target.value })} />
      </section>
      <section id="story-sec-synopsis">
        <h3>Synopsis</h3>
        <textarea rows={8} value={world.synopsis} aria-label="synopsis" placeholder="The story in a page." onChange={(e) => sy().edit({ synopsis: e.target.value })} />
      </section>
      <section id="story-sec-spine">
        <h3>Spine<Help text={"The beats in order. Make the Flow from the spine makes a Start and one Shot node per beat not yet made, each with its shot, connected in this order; a single beat's node comes from its right-click."} /><span className="spacer" /><CommandButton id="story.world.flowFromSpine" /></h3>
        <div className="rows">
          {world.spine.map((b, i) => <BeatRow key={b.id} b={b} i={i} active={selected?.kind === 'beat' && selected.id === b.id} />)}
          {!world.spine.length && <div className="empty">No beats yet.</div>}
        </div>
        <div className="adder"><CommandButton id="story.world.addBeat" text /></div>
      </section>
      <section id="story-sec-styles">
        <h3>Styles<Help text={"One per generation; click a style to edit it, drop a picture from the Bin on it to make its sample; ★ marks the default Generate preselects."} /></h3>
        <StyleGrid />
        <div className="adder"><CommandButton id="story.world.addStyle" text /></div>
        <div className="kv sample-scene"><span>sample scene<Help text={"U2 (D157): the scene every style's sample is rendered on — this project's own (a harbour story's looks judged on a harbour), so the samples compare. Empty: the scene in Settings › Samples. A changed scene does not remake the samples already made."} /></span>
          <textarea rows={2} value={world.sample_scene} aria-label="sample scene" placeholder="e.g. a fishing harbour at dusk, a ferry at the pier" onChange={(e) => sy().edit({ sample_scene: e.target.value })} /></div>
      </section>
      <section id="story-sec-variables">
        <h3>Variables<Help text={"Bool or enum flags the Flow's conditions read."} /></h3>
        <div className="rows">
          {world.variables.map((v) => <VarRow key={v.name} v={v} active={selected?.kind === 'variable' && selected.id === v.name} />)}
          {!world.variables.length && <div className="empty">No variables yet.</div>}
        </div>
        <div className="adder"><CommandButton id="story.world.addVariable" text /></div>
      </section>
      <h2 className="presets-head">Presets<Help text={"Image's tools, kept after the bible (D125): the prompt fields' presets and the whole-panel templates."} /></h2>
      <section id="story-sec-library">
        <h3>Library<Help text={"Every preset of Generate's prompt fields — words and a picture; click one to edit it in the Inspector, + Add puts new words in a field."} /></h3>
        <LibraryGrid />
      </section>
      <section id="story-sec-panels">
        <h3>Saved panels<Help text={"Generate's whole-panel templates, each shown by its latest result; click one for Apply, Rename and Delete."} /></h3>
        <PanelGrid />
      </section>
      <section id="story-sec-templates">
        <h3>Shot templates<Help text={"Shots kept to start others from (RC2e): a node's kind, its lines, its route and its camera. Save as a template… on a Shot in the Flow keeps one; New Shot from a template ▸ (the Flow's right-click) places one — beside a node, in its scene with its camera on that node's stage."} /></h3>
        <TemplateRows />
      </section>
    </div>
  )
}

/** RC2e: the picked Shot template in the World Inspector — what it keeps, and its verbs. */
function TemplateEditor({ id }: { id: string }) {
  const t = useStory((s) => s.shotTemplates.find((x) => x.id === id))
  if (!t) return null
  return (
    <>
      <h4>Shot template · {t.name}</h4>
      <div className="kv">
        <span>kind</span><span>{NODE_LABEL[t.node_type]}</span>
        <span>route</span><span>{t.route ? ROUTE_LABEL[t.route] ?? t.route : '—'}</span>
        <span>lines</span><span>{t.lines.length ? t.lines.map((l) => l.text).join(' / ') : '—'}</span>
        <span>camera</span><span>{t.camera ? `${t.camera.name} · ${Math.round(t.camera.focal_mm)} mm${t.camera.keys.length ? ` · ${t.camera.keys.length} keys` : ''}` : 'none (it was not on a stage)'}</span>
      </div>
      <div className="verbs"><CommandButton id="story.template.use" text /><CommandButton id="story.template.rename" text /><CommandButton id="story.template.delete" text /></div>
    </>
  )
}

/** RC2e: the World's Shot templates — a row each (its kind, route and camera); a click picks it for the Inspector's verbs, a right-click
 *  shows them. */
function TemplateRows() {
  const ts = useStory((s) => s.shotTemplates)
  const selected = useStory((s) => s.selected)
  useEffect(() => { void sy().loadTemplates() }, [])
  if (!ts.length) return <div className="empty">None yet — Save as a template… on a Shot in the Flow.</div>
  return (
    <div className="rows template-rows">
      {ts.map((t) => (
        <button key={t.id} className={`story-row${selected?.kind === 'template' && selected.id === t.id ? ' active' : ''}`} data-template={t.id} onClick={() => sy().select({ kind: 'template', id: t.id })}
          onContextMenu={(e) => { sy().select({ kind: 'template', id: t.id }); showMenu(e, [{ cmd: 'story.template.use' }, sep, { cmd: 'story.template.rename' }, { cmd: 'story.template.delete' }]) }}>
          <span>{t.name}</span><span className="muted">{NODE_LABEL[t.node_type]} · {t.lines.length ? `${t.lines.length} line${t.lines.length === 1 ? '' : 's'} · ` : ''}{t.route ? ROUTE_LABEL[t.route] ?? t.route : ''}{t.camera ? ` · ${Math.round(t.camera.focal_mm)} mm` : ''}</span>
        </button>
      ))}
    </div>
  )
}

// ------------------------------------------------------------------ Stage: the Cast version page
function candidateMenu(id: string): MenuItem[] {
  const s = sy()
  if (!s.picked.includes(id)) s.pick(id)
  return [{ cmd: 'story.cast.addRef' }, { cmd: 'story.cast.setHero' }, sep, { cmd: 'story.cast.useAsAnimRef' }, { cmd: 'story.cast.useAsAnimRefBack' }, { cmd: 'cast.place.usePicture' }, sep, { cmd: 'story.cast.openCandidates' }]
}

function Candidate({ a, picked }: { a: Asset; picked: boolean }) {
  const cell = (a.params as { coverage_cell?: { shot?: string; angle?: string; expression?: string } } | null)?.coverage_cell
  const title = cell ? `${cell.shot ?? ''} · ${cell.angle ?? ''} · ${cell.expression ?? ''}` : a.prompt_text ?? ''
  return (
    <div className={`cand-card${picked ? ' picked' : ''}`} data-id={a.id} title={title}
      onClick={(e: ReactMouseEvent) => sy().pick(a.id, e.ctrlKey || e.shiftKey)} onContextMenu={(e) => showMenu(e, candidateMenu(a.id))}>
      <img src={api.thumbUrl(a.id, 256)} alt="" />
      {cell && <span className="cell">{cell.shot} · {cell.angle}</span>}
      <span className="tools">
        <button className="quiet" title="Add to the reference set" aria-label="add to the reference set" onClick={(e) => { e.stopPropagation(); void sy().addRefs([a.id]) }}>✓</button>
      </span>
    </div>
  )
}

/** CA0 (01 step 2, §10): the version's animation reference — what Wan Animate is given for the character: full body, a neutral A-pose,
 *  16:9 with the figure centred and padded (a portrait one loses its head and feet to the node's crop), a plain ground. A prop's is the
 *  object alone in a three-quarter view. Made from the sheet and references; any candidate can be picked (its right-click). */
const PlaceSetSection = lazy(() => import('./CastSet').then((m) => ({ default: m.PlaceSetSection })))   // CW6: three.js only when a place is open

/** D125 (S5): a use of *In N shots* opens its shot on the Shots board. */
const openShotRow = (id: string) => { sy().selectShot(id); setRailTab('story', 'shots') }

function CastPage() {
  const profiles = useStory((s) => s.profiles)
  const profileId = useStory((s) => s.profileId)
  const versionId = useStory((s) => s.versionId)
  const refPage = useStory((s) => s.refPage)
  const candPage = useStory((s) => s.candPage)
  const picked = useStory((s) => s.picked)
  const caps = useSession((s) => s.capabilities?.story)
  const filterIsProp = useStory((s) => s.castFilter === 'prop')
  const castUses = useStory((s) => s.castUses)
  markUsed('story.cast.addRef'); markUsed('story.cast.setHero'); markUsed('story.cast.openCandidates'); markUsed('story.cast.openGroup'); markUsed('story.cast.delete')
  markUsed('story.cast.useAsAnimRef'); markUsed('story.cast.useAsAnimRefBack')   // the candidates' menus (the animation reference's section is in CastParts)
  const p = profiles.find((x) => x.id === profileId)
  if (!p) return filterIsProp
    ? <div className="story-empty"><div>Pick a prop on the left, or make one. A prop is made like a character: its look and reference images first, then its 3D model, which Animate places in the scene. <b>Make a prop…</b> on a picture in the Bin puts the image in as the hero.<div className="quick-cards"><CommandButton id="story.cast.newProp" text /></div></div></div>
    : <div className="story-empty"><div>Pick a profile on the left, or make one: <b>Make a character…</b> on a picture in the Bin puts the image in as the hero.<div className="quick-cards"><CommandButton id="story.cast.new" text /></div></div></div>
  const v = p.versions.find((x) => x.id === (versionId ?? p.current))
  if (!v) return null
  const refs = Object.values(refPage?.assets ?? {})
  const grid = coverageGrid(refs, caps?.coverage.shots ?? [], caps?.coverage.angles ?? [])
  const cands = Object.values(candPage?.assets ?? {}).sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
  const open = v.state === 'open'
  const uses = castUses[p.id]?.uses ?? []
  const cells = castCells() ?? []
  return (
    <div className="cast-page" tabIndex={0} onKeyDown={(e) => { storyKey('cast', e.nativeEvent) }}>
      <ReadinessRow />
      <div className="cast-head">
        <div className="hero-card">{v.hero_asset_id ? <img src={api.thumbUrl(v.hero_asset_id, 512)} alt="" /> : <span className="hint">no hero yet</span>}</div>
        <div className="cast-fields">
          <h2>{p.name} <span className="muted">— {CLASS_LABEL[p.cls]} — {versionName(v)} ({open ? 'open' : 'final'})</span></h2>
          <CastSheet p={p} v={v} />{/* D93 (B4): the character sheet (was the one prompt stub) */}
          <CastBody p={p} v={v} />{/* CA0: the body shapes the Stage dummy (D161: no longer inside the sheet) */}
          <div className="counts"><span>reference set · <b>{refs.length}</b></span><span>candidates · <b>{cands.length}</b></span>{v.candidates_group_id === null && <span className="hint">(none expanded yet)</span>}</div>
        </div>
      </div>
      <section className="in-shots">
        <h3>In {uses.length} shot{uses.length === 1 ? '' : 's'} <Help text={"The shots that use this profile — a line's speaker, a node's place, a stage figure or a prop's mesh bound to it — with each shot's route and what it still needs from this version. A click opens the shot."} /></h3>
        {uses.length ? <div className="use-list">{uses.map((u) => { const need = shotNeeds(u, cells, p.cls)
          return (
            <button key={u.shot_id} type="button" className="use-row" data-id={u.shot_id} onClick={() => openShotRow(u.shot_id)} title="Open the shot in Shots">
              <b>{u.name}</b><span className="route">{ROUTE_LABEL[u.route] ?? u.route} · {u.how.join(', ')}</span><span className={need.length ? 'needs' : 'ok'}>{need.length ? `needs ${need.join(', ')}` : 'ready'}</span>
            </button>
          ) })}</div> : <span className="hint">in no shot yet</span>}
      </section>
      <section className="ref-set">{/* proto01_UIcast CF6: the kept pictures themselves, not only their count */}
        <h3>Reference set <Help text={"The version's kept references, the hero first, each under its coverage cell. A click opens the set in the Bin (its page), where they are sorted, tagged or taken out."} /></h3>
        {refs.length ? <div className="story-refs" role="list" aria-label="the reference set">
          {[...refs].sort((a, b) => (a.id === v.hero_asset_id ? -1 : b.id === v.hero_asset_id ? 1 : a.created_at < b.created_at ? -1 : 1)).slice(0, REF_SHOWN).map((a) => { const c = cellOf(a)
            return <button key={a.id} type="button" role="listitem" className={`ref-card${a.id === v.hero_asset_id ? ' hero' : ''}`} data-id={a.id} onClick={() => runCommand('story.cast.openGroup')}
              onContextMenu={(e) => showMenu(e, [{ cmd: 'story.cast.openGroup' }])} title="Open the reference set in the Bin">
              <img src={api.thumbUrl(a.id, 256)} alt="" /><span className="cell">{a.id === v.hero_asset_id ? 'hero' : c ? `${c.shot} · ${c.angle}` : 'no cell'}</span></button> })}
          {refs.length > REF_SHOWN && <button type="button" className="link" onClick={() => runCommand('story.cast.openGroup')}>+{refs.length - REF_SHOWN} more</button>}
        </div> : <span className="hint">none yet — ✓ on a candidate keeps it here</span>}
      </section>
      {p.cls === 'place' && <Suspense fallback={<section className="place-set" />}><PlaceSetSection p={p} v={v} /></Suspense>}{/* CW6 (D143): the set builder, a place's own tool */}
      <section>
        <h3>Coverage <Help text={"Kept references per shot size × angle; thin cells are tinted (advisory)."} /></h3>
        <table className="cov-grid" aria-label="coverage">
          <thead><tr><th />{grid.angles.map((a) => <th key={a}>{a}</th>)}</tr></thead>
          <tbody>
            {grid.shots.map((s) => <tr key={s}><th>{s}</th>{grid.angles.map((a) => { const n = grid.counts[s]?.[a] ?? 0; return <td key={a} className={n ? (n >= 2 ? 'full' : 'one') : 'thin'}>{n || '–'}</td> })}</tr>)}
          </tbody>
        </table>
        {grid.uncelled > 0 && <span className="hint">{grid.uncelled} reference{grid.uncelled === 1 ? '' : 's'} without a cell (the hero, imports).</span>}
      </section>
      {(p.cls === 'character' || p.cls === 'prop') && <AnimRef p={p} v={v} />}
      {p.cls === 'prop' && <PropModel p={p} v={v} />}
      <section>
        <h3>Candidates <Help text={"Newest first · ✓ adds to the reference set · click to select, Ctrl-click for several."} /></h3>
        {!cands.length && <div className="empty">{open ? <>No candidates yet — <button className="link" onClick={() => void askExpand('full', 1, 'draft')} disabled={!v.hero_asset_id} title="Queues one draft image per coverage cell here, the cost said first">Queue the coverage ▶</button> makes one image per coverage cell.</> : 'This version is final.'}</div>}
        <div className="story-cands" role="list">
          {cands.map((a) => <Candidate key={a.id} a={a} picked={picked.includes(a.id)} />)}
        </div>
      </section>
    </div>
  )
}

const REF_SHOWN = 24                                                               // proto01_UIcast CF6: the rest one click away, in the Catalogue

// ------------------------------------------------------------------ Stage: the shot board
function Take({ kind, id, current, clipsById }: { kind: 'image' | 'clip'; id: string; current: boolean; clipsById: Record<string, { asset_id: string | null; frames: number; w: number; h: number }> }) {
  const c = kind === 'clip' ? clipsById[id] : undefined
  const thumb = kind === 'image' ? id : c?.asset_id ?? null
  markUsed('story.shot.useTake')
  return (
    <div className={`take-card${current ? ' current' : ''}`} data-kind={kind} data-id={id} title={kind === 'clip' ? (c ? `${c.frames} f · ${c.w}×${c.h}` : id) : id}
      onContextMenu={(e) => showMenu(e, [{ cmd: 'story.shot.useTake', on: onStoryItem({ take: { kind, id } }) }])}>
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
  if (!s) return <div className="story-empty"><div>Pick a shot on the left — every Shot node in Flow has one.<div className="quick-cards"><CommandButton id="story.shot.new" text /></div></div></div>
  const v = s.versions.find((x) => x.id === (shotVersionId ?? s.current))
  if (!v) return null
  const clip = v.clip_id ? clipsById[v.clip_id] : undefined
  const why = sy().finalizeWhy(v)
  return (
    <div className="cast-page shot-board" tabIndex={0} onKeyDown={(e) => { storyKey('shots', e.nativeEvent) }}>
      <section>
        <h3>Versions <Help text={"Each owns one clip; the Flow pins one, the Episode takes the final one."} /></h3>
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
            : <span className="hint">No frame or clip yet. <Help text={"Make frame ▸ / Make clip ▸ below (Generate, Animate or the stage camera), or use a take."} /></span>}
        </div>
        <div className="counts">{why ? <span className="hint">{why}</span> : v.state === 'final' ? <span>final · the clip the Flow and the Episode bind</span> : <span>ready to mark final</span>}</div>
        <div className="make-row"><MakeMenus /><Help text={v.state === 'open' ? 'Generate or Animate open for this version; what they make comes back here as takes.' : 'Final: make a new version for more takes.'} /></div>
      </section>
      <ShotRecipe shotId={s.id} version={v.id} />{/* RC1 (proto01_animate 28) */}
      <section>
        <h3>Takes <Help text={"Everything tried for this version · ✓ use makes one the frame or the clip."} /></h3>
        {!v.takes.length && <div className="empty">No takes yet.</div>}
        <div className="story-cands" role="list">
          {[...v.takes].reverse().map((t) => <Take key={`${t.kind}:${t.id}`} kind={t.kind} id={t.id} current={(t.kind === 'image' ? v.frame_asset_id : v.clip_id) === t.id} clipsById={clipsById} />)}
        </div>
      </section>
    </div>
  )
}

// ------------------------------------------------------------------ Stage: play mode (no model is ever invoked — loom R143)
export function PlayView() {
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
      {n?.type === 'shot' && n.lines.length > 0 && <div className="play-lines">{n.lines.map((l, i) => <p key={i}>{speaker(l.speaker) && <b>{speaker(l.speaker)}: </b>}{l.text}</p>)}</div>}
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
  const flowRecipe = useStory((s) => s.flowRecipe)                                  // RC1: the node's recipe in place of the canvas
  const skeleton = useStory((s) => s.skeleton)                                      // CS2: the skeleton bench in place of the page
  const board = useIdeas((s) => s.board)                                            // CW1: the Ideas board's bench
  markUsed('story.world.addStyle'); markUsed('story.world.addBeat'); markUsed('story.world.addVariable'); markUsed('story.world.remove'); markUsed('story.cast.new'); markUsed('story.cast.newPlace'); markUsed('story.cast.newProp')
  if (!project?.open) return <div className="story-empty"><div>Open or create a project to begin.</div></div>
  if (tab === 'cast' && board === 'ideas') return <IdeaBench />                                                                       // proto01_UIcast CW1
  if (tab === 'cast') return skeleton ? <Suspense fallback={<span className="hint">loading the bench…</span>}><SkeletonBench /></Suspense> : <CastPage />   // CS2
  if (tab === 'shots') return <div className="shots-stage"><ShotsBoard /><ShotBoard /><LinkStageSheet /></div>   // D125 (SP3): the board, the selected shot's page under it
  if (tab === 'flow') return play ? <PlayView /> : <>{flowRecipe ? <FlowRecipe /> : <FlowCanvas />}<LinkStageSheet /></>
  if (tab === 'episode') return <SequenceStage />
  return <WorldEditor />
}

// ------------------------------------------------------------------ Inspector
function CastInspector() {
  const skeleton = useStory((s) => s.skeleton)
  const board = useIdeas((s) => s.board)
  if (board === 'ideas') return <IdeaInspector />                                              // proto01_UIcast CW1
  if (skeleton) return <Suspense fallback={null}><SkeletonParts /></Suspense>                // CS2: the bench's parts
  return <CastSheetInspector />
}

function CastSheetInspector() {
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
        <select value={p.cls} aria-label="profile class" onChange={(e) => { const cls = e.target.value as ProfileClass   // D110: a prop moves to Props, a character or place to Cast
          void sy().patchProfile({ cls }).then(() => revealClass(cls)) }}>{(Object.keys(CLASS_LABEL) as ProfileClass[]).map((c) => <option key={c} value={c}>{CLASS_LABEL[c]}</option>)}</select>
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
        {picked.length > 0 && <><h4>{picked.length} candidate{picked.length === 1 ? '' : 's'} selected</h4><div className="verbs"><CommandButton id="story.cast.addRef" text /><CommandButton id="story.cast.setHero" text /></div></>}
      </>}
      <div className="verbs"><CommandButton id="story.cast.delete" text /></div>
    </div>
  )
}

/** D125 (#4, S10): Shots' Inspector — the shot's node first (when a Flow node owns it), then the shot: the same panel as the Flow's. */
function ShotInspector() {
  const shots = useStory((s) => s.shots)
  const shotId = useStory((s) => s.shotId)
  const flowNodes = useStory((s) => s.flowNodes)
  const s = shots.find((x) => x.id === shotId)
  if (!s) return <span className="hint">Nothing selected.</span>
  return <NodeShotPanel n={s.owner_node ? flowNodes[s.owner_node] : undefined} s={s} />
}

/** D125 (#4, S10): a node and its shot as one panel — the node's own fields, then its shot's (the selected shot: selecting a node selects
 *  its shot, and a shot its node, so the shot verbs and the node verbs both act on what is shown). */
function NodeShotPanel({ n, s }: { n?: FlowNode; s?: Shot }) {
  const visual = n?.type === 'shot'
  const shotId = useStory((st) => st.shotId)
  useEffect(() => { if (s && shotId !== s.id) sy().selectShot(s.id, n?.shot_version) }, [s, shotId, n?.shot_version])   // the shot verbs act on the shot shown (a node picked before the shots loaded)
  return (
    <div className="story-insp node-insp" data-testid="node-shot-panel">
      {n && <NodeFields n={n} />}
      {visual && !s && <UnboundShot n={n!} />}
      {s && <ShotFields s={s} n={visual ? n : undefined} />}
      {n && <div className="verbs"><CommandButton id="story.flow.duplicate" text /><CommandButton id="story.flow.delete" text /></div>}
    </div>
  )
}

/** The shot's half of the panel: its name and versions, the shown version's fields and verbs, its recipe (RC0) and lip-sync. */
function ShotFields({ s, n }: { s: Shot; n?: FlowNode }) {
  const shotVersionId = useStory((st) => st.shotVersionId)
  const clipsById = useStory((st) => st.clipsById)
  const stagesLite = useStory((st) => st.stagesLite)
  const flowNodes = useStory((st) => st.flowNodes)
  const v = s.versions.find((x) => x.id === (shotVersionId ?? s.current))
  const clip = v?.clip_id ? clipsById[v.clip_id] : undefined
  const stage = v?.stage_id ? stagesLite.find((x) => x.id === v.stage_id) : undefined
  return (
    <>
      <h4 className="shot-head">Shot · {s.name}</h4>
      <div className="kv">
        {!n && <><span>name</span><input type="text" value={s.name} aria-label="shot name" onChange={(e) => sy().renameShot(e.target.value)} /></>}{/* RC2a: with its node, the node's title is the name */}
        {!n && <><span>node</span><span>{s.owner_node ? nodeName(flowNodes, s.owner_node) : '—'}</span></>}
        <span>current</span>
        <select value={s.current} aria-label="current shot version" title="The version the node shows — Play and the cut use it" onChange={(e) => void sy().patchShot({ current: e.target.value })}>{s.versions.map((x) => <option key={x.id} value={x.id}>{x.id}{x.state === 'final' ? ' · final' : ''}</option>)}</select>
        <span>versions</span><span>{s.versions.length}</span>
        {n && <MadeElsewhere n={n} />}
      </div>
      {v && <ShotVersionFields v={v} clip={clip} stage={stage} />}
      {v && <RecipeSteps shotId={s.id} version={v.id} editable={v.state === 'open'} run="story.shot.runStale" />}{/* RC0 (D96) */}
      {v && v.state === 'open' && <LipsyncBlock v={v} ownerNode={s.owner_node ?? null} />}
      <div className="verbs">{n ? <CommandButton id="story.flow.openShot" text /> : null}{n ? <CommandButton id="story.flow.recipe" text /> : null}<CommandButton id="story.shot.graphInAnimate" text /><CommandButton id="story.shot.release" text /><CommandButton id="story.shot.delete" text /></div>
    </>
  )
}

/** RC2a: the shots made elsewhere (each a Shot node outside the routes) a node can take as its own — the node's shot, if it has work in
 *  it, moves out to a node of its own (nothing is lost). */
function useMadeElsewhere(n: FlowNode): Shot[] {
  const shots = useStory((s) => s.shots)
  const flowNodes = useStory((s) => s.flowNodes)
  const graph = useStory((s) => s.flowGraph)
  return shots.filter((s) => { const o = s.owner_node ? flowNodes[s.owner_node] : undefined; return s.owner_node !== n.id && (!o || bareNode(o, graph)) })
}
function MadeElsewhere({ n }: { n: FlowNode }) {
  const made = useMadeElsewhere(n)
  if (!made.length) return null
  return <><span>take</span><select value="" aria-label="bind shot" title="A shot made elsewhere (a Shot node outside the routes) becomes this node's shot; its own, if it has work in it, moves to a node of its own"
    onChange={(e) => { if (e.target.value) void sy().bindShot(n.id, e.target.value) }}><option value="">a shot made elsewhere…</option>{made.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></>
}

/** A visual node without a shot (made with `shot: false` through the API): its own, or a shot made elsewhere. */
function UnboundShot({ n }: { n: FlowNode }) {
  return (
    <>
      <h4>Shot</h4>
      <div className="kv"><MadeElsewhere n={n} /></div>
      <div className="verbs"><CommandButton id="story.flow.newShot" text /></div>
    </>
  )
}

/** RC2f: a stage shared with other Shots is linked — who shares it, and *Make its stage independent*. */
function StageShared({ v }: { v: ShotVersion }) {
  const shotId = useStory((s) => s.shotId)
  useStory((s) => s.shots)
  const users = shotId && v.stage_id ? stageUsers(shotId, v.stage_id) : []
  if (!users.length) return null
  return <><span>stage</span><span className="linked" title={`the same set, props, lights and figures as ${users.map((u) => u.name).join(', ')} — an edit there shows here`} data-linked="stage">
    linked · {users.length + 1} Shots <CommandButton id="story.shot.ownStage" text /></span></>
}

function ShotVersionFields({ v, clip, stage }: { v: ShotVersion; clip?: { frames: number; fps: number; w: number; h: number }; stage?: { name: string; revision: number } }) {
  return (
    <>
      <h4>Version {v.id} · {v.state}{sy().shotStale(v) ? ' · stale' : ''}</h4>
      <div className="kv">
        <span>source</span><span>{v.stage_id ? `${stage?.name ?? v.stage_id} · camera ${v.camera_id}${v.stage_revision !== null && v.stage_revision !== undefined ? ` · rev ${v.stage_revision}` : ''}` : 'none (a clip or takes)'}</span>
        {v.stage_id && <StageShared v={v} />}
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

export function LinesEditor({ n }: { n: FlowNode }) {
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
      <h4>Board <Help text={"References, mood, places — a group of the album."} /></h4>
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
      {!places.length && <><span /><span className="hint">no places in the Cast yet <Help text={"Story › Cast › New place…"} /></span></>}
      {n.place_id && <><span /><span><CommandButton id="story.flow.placeForward" text size={14} /></span></>}{/* D125 (S7) */}
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
      <h4>Speakers <Help text={"The version each one wears here. In a scene its Shots share them (linked): a change here is the scene's, unless this Shot keeps its own."} /></h4>
      {n.scene_id && <div className="linked-row" data-linked="cast">{n.own.includes('cast') ? 'its own' : 'linked · the scene\'s'} <CommandButton id="story.flow.ownCast" text /><CommandButton id="story.flow.linkCast" text /></div>}
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
  markUsed('story.flow.openBoard'); markUsed('story.flow.clearBoard')
  markUsed('story.flow.delete'); markUsed('story.flow.duplicate'); markUsed('story.flow.newShot'); markUsed('story.flow.openShot'); markUsed('story.flow.validate'); markUsed('story.flow.fit'); markUsed('story.flow.voiceAll')
  markUsed('story.flow.placeForward')
  for (const t of ['start', 'hub', 'choice', 'condition', 'action', 'shot', 'jump', 'comment']) markUsed(`story.flow.add.${t}`)
  const n = nodeId ? flowNodes[nodeId] : undefined
  if (!n) return (
    <div className="story-insp">
      {problems && <><h4>Validation</h4><ul className="flow-problems">{problems.map((p, i) => <li key={i} className={p.code}><button className="link" onClick={() => sy().selectNode(p.node_id)}>{p.message}</button></li>)}{!problems.length && <li className="ok">No problems.</li>}</ul></>}
      <span className="hint">Nothing selected. <Help text={"Select a node on the canvas or in the outline."} /></span>
    </div>
  )
  const sh = n.shot_id ? shots.find((s) => s.id === n.shot_id) : undefined
  return <NodeShotPanel n={n} s={sh} />                                              // D125 (S10): the same panel as Shots'
}

/** The node's half of the panel: its type and title, its own fields by type, where, its speakers' versions, its board, its problems. */
/** RC2c: the node's scene group — pick one to join it, (none) to leave; *Make a scene of it…* and *New Shot from this Shot* beside. */
function SceneField({ n }: { n: FlowNode }) {
  const scenes = useStory((s) => s.scenes)
  return (
    <>
      <div className="kv">
        <span>scene <Help text="A scene group frames Shots that share a set, a light and a cast — a dialogue in shot / reverse-shot is several Shots, one scene. Episode grades a scene as one." /></span>
        <select value={n.scene_id ?? ''} aria-label="node scene" onChange={(e) => { const sid = e.target.value; if (sid) void sy().sceneMembers(sid, [n.id], []); else if (n.scene_id) void sy().sceneMembers(n.scene_id, [], [n.id]) }}>
          <option value="">(none)</option>{scenes.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
      </div>
      <div className="verbs"><CommandButton id="story.scene.make" text /><CommandButton id="story.flow.sibling" text /></div>
    </>
  )
}

function NodeFields({ n }: { n: FlowNode }) {
  const flowNodes = useStory((s) => s.flowNodes)
  const problems = useStory((s) => s.problems)
  const world = useStory((s) => s.world)
  const vars = world?.variables ?? []                                                           // derived in render: a selector must not return a fresh array
  const mine = problems?.filter((p) => p.node_id === n.id) ?? []
  const visual = n.type === 'shot'
  return (
    <>
      <h4>{NODE_LABEL[n.type]} · {n.title || n.id}</h4>
      <div className="kv">
        <span>type</span>
        <select value={n.type} aria-label="node type" onChange={(e) => void sy().patchNode(n.id, { type: e.target.value as FlowNode['type'] })}>{(Object.keys(NODE_LABEL) as FlowNode['type'][]).map((t) => <option key={t} value={t}>{NODE_LABEL[t]}</option>)}</select>
        <span>title</span><input type="text" value={n.title} aria-label="node title" onChange={(e) => void sy().patchNode(n.id, { title: e.target.value })} />
        {n.type === 'comment' && <><span>text</span><textarea rows={3} value={n.text} aria-label="note text" onChange={(e) => void sy().patchNode(n.id, { text: e.target.value })} /></>}
        {n.type === 'shot' && <><span>action</span><textarea rows={2} value={n.text} aria-label="shot line" placeholder="what happens (a beat's line lands here)" onChange={(e) => void sy().patchNode(n.id, { text: e.target.value })} /></>}
        {n.type === 'jump' && <><span>target</span><select value={n.target ?? ''} aria-label="jump target" onChange={(e) => void sy().patchNode(n.id, { target: e.target.value || null })}><option value="">(none)</option>{Object.values(flowNodes).filter((x) => x.id !== n.id && x.type !== 'comment').map((x) => <option key={x.id} value={x.id}>{x.title || NODE_LABEL[x.type]}</option>)}</select></>}
        {n.type === 'condition' && <><span>condition</span><div className="cond-row">
          <select value={n.cond?.var ?? ''} aria-label="condition variable" onChange={(e) => void sy().patchNode(n.id, { cond: { var: e.target.value, op: n.cond?.op ?? 'eq', value: n.cond?.value ?? true } })}><option value="">variable</option>{vars.map((v) => <option key={v.name} value={v.name}>{v.name}</option>)}</select>
          <select value={n.cond?.op ?? 'eq'} aria-label="condition operator" onChange={(e) => void sy().patchNode(n.id, { cond: { var: n.cond?.var ?? '', op: e.target.value as 'eq' | 'ne', value: n.cond?.value ?? true } })}><option value="eq">=</option><option value="ne">≠</option></select>
          {(() => { const v = vars.find((x) => x.name === n.cond?.var); const vals = v ? (v.type === 'bool' ? ['true', 'false'] : v.values) : ['true', 'false']
            return <select value={String(n.cond?.value ?? 'true')} aria-label="condition value" onChange={(e) => void sy().patchNode(n.id, { cond: { var: n.cond?.var ?? '', op: n.cond?.op ?? 'eq', value: e.target.value === 'true' ? true : e.target.value === 'false' ? false : e.target.value } })}>{vals.map((val) => <option key={val} value={val}>{val}</option>)}</select> })()}
        </div></>}
      </div>
      {n.type === 'shot' && <><h4>Lines</h4><LinesEditor n={n} /></>}{/* U2 (G5): a Shot speaks — a Dialogue was a Shot with lines */}
      {n.type === 'choice' && <><h4>Options <Help text={"Each is an out-port."} /></h4><OptionsEditor n={n} /></>}
      {n.type === 'action' && <><h4>Sets</h4><SetsEditor n={n} sets={n.set} onChange={(set) => void sy().patchNode(n.id, { set })} /></>}
      {visual && <PlaceField n={n} />}
      <SceneField n={n} />
      {visual && <SpeakerVersions n={n} />}
      <BoardField n={n} />
      {mine.length > 0 && <><h4>Problems</h4><ul className="flow-problems">{mine.map((p, i) => <li key={i} className={p.code}>{p.message}</li>)}</ul></>}
    </>
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
      {selected?.kind === 'template' && <TemplateEditor id={selected.id} />}
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
