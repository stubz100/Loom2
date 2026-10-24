// P17 (D83): the Sequence tab's verbs — every one has a mouse home (the lane's context menu, the Inspector, the transport) per D32;
// undo / redo take Ctrl+Z / Ctrl+Shift+Z in the Animate scope (the clip player has no undo of its own).
import { AppWindow, ArrowDown, ArrowLeft, ArrowLeftRight, ArrowRight, ArrowRightLeft, ArrowUp, ChevronFirst, ChevronLast, ChevronLeft, ChevronRight, Clapperboard, Columns2, FileDown, Film, FolderOpen, Gauge, Lock, Mic, MousePointer2, MoveHorizontal, Music, Pause, Pencil, Play, Plug, Plus, Redo2, RefreshCw, Scissors, SkipBack, SkipForward, SlidersHorizontal, Snowflake, Sparkles, SplitSquareHorizontal, SquareDashed, Tag, ToggleLeft, Trash2, Undo2, UnfoldHorizontal, Volume2, VolumeX, Workflow, ZoomIn, ZoomOut } from 'lucide-react'
import { registerCommands, sep, type MenuItem } from '../../../frame/commands'
import { askConfirm, askText, useSession } from '../../../store/session'
import { useAnimate } from '../../animate/animateStore'
import { useStory } from '../storyStore'
import { assembleLane, laneChanges, routeLabel, routePicks, updateClip, walkRoute } from './assemble'
import { duration, ticks } from './lane'
import { isCut, lastMovie, useSequence } from './sequenceStore'
import { CUT_TOOLS, dialogueOf, duckSteps, evenDialogueSteps, fadeStep, findItem, gainStep, isVideo, panLabel, ROLE_NAMES, STRIP, stripValue, ticksOf, trackRef, transitionInto, transitionStep, TRACK_ROLES, volumeLabel, widthLabel, type CutTool } from './cut'
import type { TrackRole, TrackStrip } from '../../../api/types'
import { revealPath } from '../../../shell/tauri'

const sq = () => useSequence.getState()
const hasSeq = () => !!sq().current
/** RC3: the open cut's newest finished movie, as the absolute path the job wrote. */
const movieFile = (): string | null => { const c = sq().current; const m = c ? lastMovie(useSession.getState().jobs, c.id) : null; return m?.status === 'done' ? m.file : null }
const hasSel = () => hasSeq() && !isCut() && sq().selected !== null && !!sq().lane?.clips[sq().selected!]
/** CE2: the clip selected on a FilmCraft cut's tracks, with its track. */
const selCut = () => { const t = sq().tracks, id = sq().selClip; return t && id !== null ? findItem(t, id) : null }
/** CE2: the cut's length in frames (a FilmCraft cut: its tracks; today's: its lane). */
export const cutLength = (): number => (isCut() ? Math.ceil(sq().tracks?.duration ?? 0) : sq().lane ? duration(sq().lane!) : 0)
/** AU4: the effect a chain row's button is about (commands take no arguments; the row sets this first). */
export const fxItem: { id?: string } = {}
const selFx = () => { const tr = selTrack(); return tr && fxItem.id ? tr.chain.find((e) => e.id === fxItem.id) ?? null : null }
const fxIndex = () => { const tr = selTrack(); return tr && fxItem.id ? tr.chain.findIndex((e) => e.id === fxItem.id) : -1 }
/** CE2: the track a header's click or right-click selected (D127: the store's, so the Inspector's strip and the menu agree). */
const selTrack = () => { const t = sq().tracks, id = sq().selTrack; return t && id !== null ? [...t.video, ...t.audio].find((x) => x.id === id) ?? null : null }
const an = () => useAnimate.getState()
type BinClip = Parameters<ReturnType<typeof useSequence.getState>['addClip']>[0]
/** D90 (01 §11.2): the bin entry the + was pressed on (commands take no arguments; the button sets this first, a run clears it). */
export const binItem: { shot?: { clip: BinClip; ref: { id: string; version: string; node: string | null } }; clip?: BinClip } = {}

/** 17 §3e: what on the lane is not a final shot version — a plain clip, a draft version, a stale one (advisory, 02 §7). */
export function laneChecklist(): { i: number; what: string }[] {
  const lane = sq().lane; if (!lane) return []
  const st = useStory.getState()
  const out: { i: number; what: string }[] = []
  const changed = new Map(laneChanges(lane, st.shots).map((x) => [x.i, x]))
  lane.clips.forEach((c, i) => {
    if (!c.shot) { out.push({ i, what: 'a plain clip, not a shot' }); return }
    const sh = st.shots.find((s) => s.id === c.shot!.id)
    const v = sh?.versions.find((x) => x.id === c.shot!.version)
    const ch = changed.get(i)
    if (ch) out.push({ i, what: `${ch.name} has a newer approved take (${ch.version}) — Update` })   // D125 (S13): changed
    else if (!sh || !v) out.push({ i, what: 'its shot is gone' })
    else if (v.state !== 'final') out.push({ i, what: `${sh.name} ${v.id} is not final` })
    else if (st.shotStale(v)) out.push({ i, what: `${sh.name} ${v.id} is stale (its stage moved)` })
  })
  return out
}

/** D125 (#6): the lane's clips below the project format (beyond the video models' 32 px grid) — a delivery note under the checklist, never a
 *  reason for the export to ask (no video route renders the format; Resolve scales them). The distinct sizes, largest first. */
export function laneBelowFormat(): { count: number; sizes: string[] } {
  const lane = sq().lane; const fmt = useSession.getState().project?.format
  if (!lane || !fmt) return { count: 0, sizes: [] }
  const byId = new Map(an().clips.map((c) => [c.id, c]))
  const small = lane.clips.map((c) => byId.get(c.source)).filter((c): c is NonNullable<typeof c> => !!c && (Math.abs(c.w - fmt.width) > 32 || Math.abs(c.h - fmt.height) > 32))
  const sizes = [...new Set(small.sort((a, b) => b.w * b.h - a.w * a.h).map((c) => `${c.w}×${c.h}`))]
  return { count: small.length, sizes }
}

/** The export goes on after a look at the checklist when something on the lane is not a final shot (loom R153 kept advisory). D125 (S14):
 *  asked once, only when something is listed; the clips below the format ride along as a note. */
async function exportChecked(format: 'edl' | 'fcpxml' | 'srt' | 'resolve'): Promise<void> {
  const issues = laneChecklist()
  const n = sq().lane?.clips.length ?? 0
  if (issues.length) {
    const below = laneBelowFormat()
    const ok = await askConfirm({ title: `Export with ${issues.length} of ${n} clips listed?`, okLabel: 'Export anyway',
      text: issues.slice(0, 6).map((x) => `clip ${x.i + 1}: ${x.what}`).join('\n') + (issues.length > 6 ? `\n… and ${issues.length - 6} more` : '')
        + (below.count ? `\n(${below.count} below the format — Resolve scales them)` : '') })
    if (!ok) return
  }
  await sq().exportAs(format)
}

/** D125 (S13): the cut from a route — a new one named `name`, or the open one again (its trims and dissolves kept where the same shots follow
 *  each other); the route's picks kept on the cut. */
export async function assembleCut(picks: Record<string, string>, name: string | null): Promise<void> {
  const st = useStory.getState()
  if (!st.flowGraph) return
  const walk = walkRoute(st.flowGraph, st.flowNodes, st.world?.variables ?? [], picks)
  if (name !== null && !(await sq().create(name))) return
  const cur = sq().current
  if (!cur) return
  const { lane, missing } = assembleLane(walk.nodes, st.shots, new Map(an().clips.map((c) => [c.id, c])), cur.fps, name === null ? sq().lane : null)
  useSequence.setState({ current: { ...cur, route: routePicks(walk.choices) } })
  sq().apply(() => lane, 'assemble')
  const label = routeLabel(walk.choices)
  useSession.getState().toast(`${cur.name}: ${lane.clips.length} shot${lane.clips.length === 1 ? '' : 's'}${label ? ` of the ${label} route` : ''}${missing.length ? ` · ${missing.length} without a clip yet (${missing.slice(0, 4).join(', ')})` : ''}`, missing.length ? 'info' : 'success')
}

/** D125 (S13): the selected lane clip's change, when its shot has a newer approved take. */
const selChange = () => { const l = sq().lane; const i = sq().selected; return l && i !== null ? laneChanges(l, useStory.getState().shots).find((x) => x.i === i) ?? null : null }
const allChanges = () => { const l = sq().lane; return l ? laneChanges(l, useStory.getState().shots) : [] }
/** *Update* the changes: each clip swapped for its shot's approved take, the trims kept (one undo step). */
async function updateChanges(list: ReturnType<typeof allChanges>): Promise<void> {
  if (list.some((x) => !an().clips.some((c) => c.id === x.clip))) await an().loadClips()          // a take made since the clips were listed
  const byId = new Map(an().clips.map((c) => [c.id, c]))
  const ok = list.filter((x) => byId.has(x.clip))
  if (!ok.length) { useSession.getState().toast('The newer take is not loaded yet — try again in a moment', 'info'); return }
  if (isCut()) {                                                    // CE2: FilmCraft plays the new take in place; the edits around it stay
    for (const x of ok) {
      const c = sq().lane?.clips[x.i]
      if (c?.shot) await sq().cutReplace(Number(c.id), { clip_id: x.clip, shot_id: c.shot.id, shot_version: x.version, node_id: c.shot.node })
    }
    return
  }
  sq().apply((l) => ok.reduce((acc, x) => updateClip(acc, x, byId.get(x.clip)!), l), 'update')
}

registerCommands([
  { id: 'story.episode.new', scope: 'story', label: 'New cut…', icon: Plus, placement: ['panel', 'context'],
    run: () => void askText({ title: 'New cut', text: 'One cut of the episode: a single lane at the project frame rate; shots and clips come from the bins.', placeholder: 'cut name', initial: 'Cut' }).then((n) => { if (n?.trim()) void sq().create(n.trim()) }) },
  // D125 (S13, S14): the cut from the Flow, its changed shots, one export for Resolve
  { id: 'story.episode.assemble', scope: 'story', label: 'Assemble from the Flow…', icon: Workflow, hint: 'a new cut of one route: every shot in order at its approved take, stamped — the sheet asks at each Choice',
    placement: ['panel', 'context'], when: () => !!useStory.getState().flowGraph?.start, run: () => sq().setAssembleFor({ tlId: null }) },
  { id: 'story.episode.reassemble', scope: 'story', label: 'Assemble again…', icon: Workflow, hint: 'the cut rebuilt from its route (the picks can change); trims and dissolves stay where the same shots follow each other',
    placement: ['inspector', 'context'], when: () => hasSeq() && !!sq().current?.route && !!useStory.getState().flowGraph?.start, run: () => sq().setAssembleFor({ tlId: sq().current!.id }) },
  { id: 'story.episode.update', scope: 'story', label: 'Update to the approved take', icon: RefreshCw, hint: "the shot's newer approved take replaces the clip; the trims stay", placement: ['inspector', 'context'],
    when: () => !!selChange(), run: () => { const c = selChange(); if (c) void updateChanges([c]) } },
  { id: 'story.episode.updateAll', scope: 'story', label: 'Update every changed clip', icon: RefreshCw, placement: ['inspector', 'context'], when: () => allChanges().length > 0, run: () => void updateChanges(allChanges()) },
  { id: 'story.episode.exportResolve', scope: 'story', label: 'Export for Resolve ▶', icon: FileDown, hint: 'the FCPXML with markers and the voice lane, the EDL, the SRT and markers.txt in one folder named after the cut; the checklist asks once, only when something is listed',
    placement: ['panel', 'inspector', 'context'], when: () => hasSeq() && !!sq().lane?.clips.length, run: () => void exportChecked('resolve') },
  { id: 'story.episode.rename', scope: 'story', label: 'Rename the cut…', icon: Clapperboard, placement: ['inspector', 'context'], when: hasSeq,
    run: () => void askText({ title: 'Rename the cut', initial: sq().current?.name ?? '', placeholder: 'cut name' }).then((n) => { if (n?.trim()) void sq().rename(n.trim()) }) },
  { id: 'story.episode.delete', scope: 'story', label: 'Delete the cut', icon: Trash2, placement: ['inspector', 'context'], when: hasSeq,
    run: () => void askConfirm({ title: 'Delete this cut?', text: 'The cut and its exports go; the clips stay in the Catalogue.', okLabel: 'Delete', danger: true }).then((ok) => { if (ok) void sq().destroy() }) },
  { id: 'story.episode.addCurrent', scope: 'story', label: 'Add the current clip', icon: Plus, placement: ['panel', 'context'], when: () => hasSeq() && !!an().clip(),
    run: () => { const c = an().clip(); if (c) sq().addClip(c) } },
  { id: 'story.episode.addShot', scope: 'story', label: 'Add the shot to the cut', icon: Plus, placement: ['panel'], hint: 'at the end, stamped with the shot (or drag it onto the lane)', when: () => hasSeq() && !!binItem.shot,
    run: () => { const b = binItem.shot; binItem.shot = undefined; if (b) sq().addShot(b.clip, b.ref) } },
  { id: 'story.episode.addClip', scope: 'story', label: 'Add the clip to the cut', icon: Plus, placement: ['panel'], hint: 'at the end (or drag it onto the lane)', when: () => hasSeq() && !!binItem.clip,
    run: () => { const c = binItem.clip; binItem.clip = undefined; if (c) sq().addClip(c) } },
  { id: 'story.episode.removeClip', scope: 'story', label: 'Remove from the cut', icon: Trash2, placement: ['inspector', 'context'], when: hasSel, run: () => sq().removeClip(sq().selected!) },
  { id: 'story.episode.moveLeft', scope: 'story', label: 'Move clip earlier', icon: ArrowLeft, placement: ['inspector', 'context'], when: () => hasSel() && sq().selected! > 0, run: () => sq().moveClip(sq().selected!, sq().selected! - 1) },
  { id: 'story.episode.moveRight', scope: 'story', label: 'Move clip later', icon: ArrowRight, placement: ['inspector', 'context'], when: () => hasSel() && sq().selected! < (sq().lane?.clips.length ?? 0) - 1, run: () => sq().moveClip(sq().selected!, sq().selected! + 1) },
  { id: 'story.episode.dissolve', scope: 'story', label: 'Dissolve from the previous clip (12 frames)', icon: Scissors, placement: ['inspector', 'context'], when: () => hasSel() && sq().selected! > 0,
    run: () => { const i = sq().selected!; const l = sq().lane!; sq().setDissolve(i, l.overlaps[i] ? 0 : Math.min(12, ticks(l, l.clips[i]) - 1, ticks(l, l.clips[i - 1]) - 1)) } },
  { id: 'story.episode.undo', scope: 'story', label: 'Undo (cut)', icon: Undo2, keys: 'Ctrl+Z', placement: ['toolbar', 'context'],
    when: () => hasSeq() && (isCut() ? (sq().tracks?.undo ?? 0) > 0 && !sq().cutBusy : sq().undo.length > 0), run: () => sq().undoEdit() },
  { id: 'story.episode.redo', scope: 'story', label: 'Redo (cut)', icon: Redo2, keys: 'Ctrl+Shift+Z', placement: ['toolbar', 'context'],
    when: () => hasSeq() && (isCut() ? (sq().tracks?.redo ?? 0) > 0 && !sq().cutBusy : sq().redo.length > 0), run: () => sq().redoEdit() },
  { id: 'story.episode.play', scope: 'story', label: 'Play / pause the cut', icon: Play, keys: 'Space', placement: ['toolbar', 'context'], when: () => hasSeq() && cutLength() > 0, run: () => sq().togglePlay() },
  { id: 'story.episode.stepBack', scope: 'story', label: 'Previous frame', icon: SkipBack, keys: 'ArrowLeft', placement: ['toolbar', 'context'], when: hasSeq, run: () => sq().setPlayhead(sq().playhead - 1) },
  { id: 'story.episode.stepForward', scope: 'story', label: 'Next frame', icon: SkipForward, keys: 'ArrowRight', placement: ['toolbar', 'context'], when: hasSeq, run: () => sq().setPlayhead(sq().playhead + 1) },
  { id: 'story.episode.back10', scope: 'story', label: 'Back 10 frames', icon: ChevronLeft, keys: 'Shift+ArrowLeft', placement: ['toolbar'], when: hasSeq, run: () => sq().setPlayhead(sq().playhead - 10) },
  { id: 'story.episode.fwd10', scope: 'story', label: 'Forward 10 frames', icon: ChevronRight, keys: 'Shift+ArrowRight', placement: ['toolbar'], when: hasSeq, run: () => sq().setPlayhead(sq().playhead + 10) },
  { id: 'story.episode.home', scope: 'story', label: 'Start of the cut', icon: ChevronFirst, keys: 'Home', placement: ['toolbar', 'context'], when: hasSeq, run: () => sq().setPlayhead(0) },
  { id: 'story.episode.end', scope: 'story', label: 'End of the cut', icon: ChevronLast, keys: 'End', placement: ['toolbar', 'context'], when: hasSeq, run: () => sq().setPlayhead(cutLength() - 1) },
  { id: 'story.episode.zoomIn', scope: 'story', label: 'Zoom the lane in', icon: ZoomIn, placement: ['toolbar'], when: hasSeq, run: () => sq().zoom(1.5) },
  { id: 'story.episode.zoomOut', scope: 'story', label: 'Zoom the lane out', icon: ZoomOut, placement: ['toolbar'], when: hasSeq, run: () => sq().zoom(1 / 1.5) },
  { id: 'story.episode.exportEdl', scope: 'story', label: 'Export EDL (CMX 3600)', icon: FileDown, placement: ['inspector', 'context'], when: () => hasSeq() && !!sq().lane?.clips.length, run: () => void exportChecked('edl') },
  { id: 'story.episode.exportSrt', scope: 'story', label: 'Export subtitles (.srt from the nodes\' lines)', icon: FileDown, placement: ['inspector', 'context'], when: () => hasSeq() && !!sq().lane?.clips.length, run: () => void exportChecked('srt') },
  { id: 'story.episode.exportFcpxml', scope: 'story', label: 'Export FCPXML 1.10', icon: FileDown, placement: ['inspector', 'context'], when: () => hasSeq() && !!sq().lane?.clips.length, run: () => void exportChecked('fcpxml') },
  { id: 'story.episode.render', scope: 'story', label: 'Render a draft clip (CPU)', icon: Clapperboard, placement: ['inspector', 'context'], when: () => hasSeq() && !!sq().lane?.clips.length, run: () => void sq().render() },
  { id: 'story.episode.renderMovie', scope: 'story', label: 'Render the movie (MP4, CPU)', icon: Film, placement: ['inspector', 'context'], when: () => hasSeq() && !!sq().lane?.clips.length,   // RC3 (proto01_animate 29)
    run: () => void sq().render(true) },
  { id: 'story.episode.revealMovie', scope: 'story', label: 'Reveal the movie in its folder', icon: FolderOpen, placement: ['inspector'], when: () => !!movieFile(),
    run: () => { const f = movieFile(); if (f) void revealPath(f) } },
  { id: 'story.episode.openClip', scope: 'story', label: 'Open the clip in the player', icon: Pause, placement: ['inspector', 'context'], when: () => hasSel() || !!selCut()?.item.clip_id,
    run: () => { const id = isCut() ? selCut()?.item.clip_id : sq().lane!.clips[sq().selected!].source; if (id) { an().select(id); useSession.getState().toast('Opened in the clip player (Animate · Performance)', 'info') } } },
])

/** Right-click on a lane clip (selected by the caller) or on the lane's empty space. */
export function laneMenu(onClip: boolean): MenuItem[] {
  return onClip
    ? [{ cmd: 'story.episode.update' }, { cmd: 'story.episode.dissolve' }, { cmd: 'story.episode.moveLeft' }, { cmd: 'story.episode.moveRight' }, { cmd: 'story.episode.openClip' }, sep, { cmd: 'story.episode.removeClip' }, sep, { cmd: 'story.episode.undo' }, { cmd: 'story.episode.redo' }]
    : [{ cmd: 'story.episode.addCurrent' }, sep, { cmd: 'story.episode.play' }, { cmd: 'story.episode.stepBack' }, { cmd: 'story.episode.stepForward' }, { cmd: 'story.episode.home' }, { cmd: 'story.episode.end' }, sep, { cmd: 'story.episode.exportResolve' }, { label: 'Export one file', icon: FileDown, items: [{ cmd: 'story.episode.exportEdl' }, { cmd: 'story.episode.exportFcpxml' }, { cmd: 'story.episode.exportSrt' }] }, { cmd: 'story.episode.render' }, { cmd: 'story.episode.renderMovie' }, sep, { cmd: 'story.episode.assemble' }, { cmd: 'story.episode.reassemble' }, { cmd: 'story.episode.updateAll' }, sep, { cmd: 'story.episode.rename' }, { cmd: 'story.episode.delete' }, { cmd: 'story.episode.new' }, sep, { cmd: 'story.episode.undo' }, { cmd: 'story.episode.redo' }]
}

// ---- CE2 (D126, proto01_animate 30 §12): a FilmCraft cut's editor — the tools, a clip's verbs, a track's verbs; each a FilmCraft command
const TOOL_INFO: Record<CutTool, { label: string; icon: typeof MousePointer2; keys: string; hint: string }> = {
  select: { label: 'Select', icon: MousePointer2, keys: 'V', hint: 'drag a clip to move it (onto another track of its kind too); drag an edge to trim' },
  ripple: { label: 'Ripple trim', icon: ArrowRightLeft, keys: 'B', hint: 'drag an edge: the clips after it follow' },
  roll: { label: 'Roll', icon: Columns2, keys: 'N', hint: 'drag the edit point between two clips: one gets longer, the other shorter' },
  slip: { label: 'Slip', icon: MoveHorizontal, keys: 'Y', hint: 'drag a clip: its source moves under it, the cut stays' },
  slide: { label: 'Slide', icon: SplitSquareHorizontal, keys: 'U', hint: 'drag a clip between its neighbours: they give and take' },
  razor: { label: 'Razor', icon: Scissors, keys: 'C', hint: 'click a clip to cut it there' },
}
const cutSel = () => isCut() && !!selCut() && !sq().cutBusy
const audioTrack = () => isCut() && !!selTrack() && !isVideo(sq().tracks!, selTrack()!)
const ROLE_ICONS: Record<TrackRole, typeof Mic> = { dialogue: Mic, music: Music, effects: Sparkles }
/** D127: the strip's four settings as the header's right-click asks for them (the key, the label, its icon, the question, how it reads now). */
const STRIP_ASKS: [keyof TrackStrip, string, typeof Mic, string, (v: number) => string][] = [
  ['gain_db', 'Gain…', SlidersHorizontal, 'gain (dB, −36 … +36; before its effects)', volumeLabel],
  ['volume_db', 'Volume…', Volume2, 'volume (dB, −∞ … +18; -inf is silent)', volumeLabel],
  ['pan', 'Pan…', ArrowLeftRight, 'pan (−100 = 100 % left, 0 = 50 / 50, +100 = 100 % right)', panLabel],
  ['width', 'Width…', UnfoldHorizontal, 'width (%, 0 = mono, 100 = as recorded, 200 = wider)', widthLabel],
]
const edit1 = (id: string, params: Record<string, unknown>) => void sq().cutEdit([{ id, params }])
const atPlayhead = () => { const s = selCut(); return !!s && sq().playhead > s.item.start && sq().playhead < s.item.start + s.item.duration }

registerCommands([
  ...CUT_TOOLS.map((tool) => ({
    id: `story.cut.tool.${tool}`, scope: 'story' as const, label: `${TOOL_INFO[tool].label} tool`, icon: TOOL_INFO[tool].icon, keys: TOOL_INFO[tool].keys, hint: TOOL_INFO[tool].hint,
    placement: ['toolbar'] as ['toolbar'], when: isCut, run: () => sq().setTool(tool),
  })),
  { id: 'story.cut.speed', scope: 'story', label: 'Speed…', icon: Gauge, placement: ['inspector', 'context'], when: cutSel, hint: 'the clip plays faster or slower; its length on the track stays',
    run: () => { const s = selCut(); if (s) void askText({ title: 'Speed (%)', initial: String(Math.round(s.item.speed * 100)), placeholder: '100' }).then((v) => { const n = Number(v); if (v && n > 0) edit1('clip.speedDuration', { clips: [s.item.id], speed: n, ripple: false }) }) } },
  { id: 'story.cut.freeze', scope: 'story', label: 'Freeze frame at the playhead', icon: Snowflake, placement: ['inspector', 'context'], when: () => cutSel() && atPlayhead() && isVideo(sq().tracks!, selCut()!.track),
    run: () => { const s = selCut(); if (s) edit1('clip.frameHold', { clips: [s.item.id], time: ticksOf(sq().playhead, sq().tracks!.fps) }) } },
  { id: 'story.cut.dissolveIn', scope: 'story', label: 'Dissolve in (12 frames)', icon: SquareDashed, placement: ['inspector', 'context'], when: () => cutSel() && isVideo(sq().tracks!, selCut()!.track),
    run: () => { const s = selCut(); if (s) void sq().cutEdit([transitionStep(s.item, 'cross_dissolve', 'in')]) } },
  { id: 'story.cut.dissolveOut', scope: 'story', label: 'Dissolve out (12 frames)', icon: SquareDashed, placement: ['inspector', 'context'], when: () => cutSel() && isVideo(sq().tracks!, selCut()!.track),
    run: () => { const s = selCut(); if (s) void sq().cutEdit([transitionStep(s.item, 'cross_dissolve', 'out')]) } },
  { id: 'story.cut.dipIn', scope: 'story', label: 'Dip to black in', icon: SquareDashed, placement: ['context'], when: () => cutSel() && isVideo(sq().tracks!, selCut()!.track),
    run: () => { const s = selCut(); if (s) void sq().cutEdit([transitionStep(s.item, 'dip_to_black', 'in')]) } },
  { id: 'story.cut.dipOut', scope: 'story', label: 'Dip to black out', icon: SquareDashed, placement: ['context'], when: () => cutSel() && isVideo(sq().tracks!, selCut()!.track),
    run: () => { const s = selCut(); if (s) void sq().cutEdit([transitionStep(s.item, 'dip_to_black', 'out')]) } },
  { id: 'story.cut.removeTransition', scope: 'story', label: 'Remove the transition into it', icon: Trash2, placement: ['inspector', 'context'], when: () => cutSel() && !!transitionInto(selCut()!.track, selCut()!.item),
    run: () => { const s = selCut(); const x = s && transitionInto(s.track, s.item); if (x) edit1('loom2.removeTransition', { transition: x.id }) } },
  { id: 'story.cut.lift', scope: 'story', label: 'Lift (leave a gap)', icon: Trash2, placement: ['inspector', 'context'], when: cutSel, danger: true,
    run: () => { const s = selCut(); if (s) edit1('edit.clear', { clips: [s.item.id] }) } },
  { id: 'story.cut.rippleDelete', scope: 'story', label: 'Ripple delete', icon: Trash2, placement: ['inspector', 'context'], when: cutSel, danger: true, hint: 'the clips after it close up (FilmCraft says why when a synced track is in the way)',
    run: () => { const s = selCut(); if (s) edit1('edit.rippleDelete', { clips: [s.item.id] }) } },
  { id: 'story.cut.rename', scope: 'story', label: 'Rename the clip…', icon: Pencil, placement: ['context'], when: cutSel,
    run: () => { const s = selCut(); if (s) void askText({ title: 'Rename the clip', initial: s.item.name }).then((n) => { if (n?.trim()) edit1('clip.rename', { clip: s.item.id, name: n.trim() }) }) } },
  { id: 'story.cut.track.rename', scope: 'story', label: 'Rename the track…', icon: Pencil, placement: ['context', 'inspector'], when: () => isCut() && !!selTrack(),
    run: () => { const tr = selTrack(); if (tr) void askText({ title: 'Rename the track', initial: tr.name }).then((n) => { if (n?.trim()) edit1('timeline.setTrack', { track: tr.id, name: n.trim() }) }) } },
  { id: 'story.cut.track.lock', scope: 'story', label: 'Lock / unlock the track', icon: Lock, placement: ['context', 'inspector'], when: () => isCut() && !!selTrack(),
    run: () => { const tr = selTrack(); if (tr) edit1('timeline.setTrack', { track: tr.id, locked: !tr.locked }) } },
  { id: 'story.cut.track.mute', scope: 'story', label: 'Mute / unmute the track', icon: VolumeX, placement: ['context', 'inspector'], when: () => isCut() && !!selTrack(),
    run: () => { const tr = selTrack(); if (tr) edit1('timeline.setTrack', { track: tr.id, muted: !tr.muted }) } },
  // CE3 (proto01_animate 30 §14): sound — each a FilmCraft command on the clip or the track
  { id: 'story.cut.gain', scope: 'story', label: 'Gain…', icon: Volume2, placement: ['inspector', 'context'], when: () => cutSel() && !isVideo(sq().tracks!, selCut()!.track),
    run: () => { const s = selCut(); if (s) void askText({ title: 'Gain (dB)', initial: String(Math.round(s.item.gain_db * 10) / 10), placeholder: '0' }).then((v) => { const n = Number(v); if (v !== null && v.trim() !== '' && Number.isFinite(n)) void sq().cutEdit([gainStep(s.item, n)]) }) } },
  { id: 'story.cut.fadeIn', scope: 'story', label: 'Fade in (12 frames)', icon: Volume2, placement: ['inspector', 'context'], when: () => cutSel() && !isVideo(sq().tracks!, selCut()!.track),
    run: () => { const s = selCut(); if (s) void sq().cutEdit([fadeStep(s.item, 'in')]) } },
  { id: 'story.cut.fadeOut', scope: 'story', label: 'Fade out (12 frames)', icon: VolumeX, placement: ['inspector', 'context'], when: () => cutSel() && !isVideo(sq().tracks!, selCut()!.track),
    run: () => { const s = selCut(); if (s) void sq().cutEdit([fadeStep(s.item, 'out')]) } },
  { id: 'story.cut.duck', scope: 'story', label: 'Duck under the dialogue', icon: VolumeX, placement: ['inspector', 'context'], hint: 'FilmCraft keys this sound down where a line speaks (the lines typed dialogue, this music)',
    when: () => cutSel() && !isVideo(sq().tracks!, selCut()!.track) && selCut()!.item.kind !== 'line' && dialogueOf(sq().tracks!).length > 0,
    run: () => { const s = selCut(); if (s) void sq().cutEdit(duckSteps(sq().tracks!, [s.item])) } },
  { id: 'story.cut.evenDialogue', scope: 'story', label: 'Even out the dialogue (−23 LUFS)', icon: Volume2, placement: ['inspector', 'context'], hint: 'every spoken line brought to −23 LUFS by its gain (EBU R128 dialogue)',
    when: () => isCut() && !!sq().tracks && dialogueOf(sq().tracks!).length > 0 && !sq().cutBusy, run: () => void sq().cutEdit(evenDialogueSteps(sq().tracks!)) },
  // D127 (30 §16): an audio track's strip — gain, volume, pan, width — and its role (Settings › Audio's strip for it)
  ...STRIP_ASKS.map(([key, label, icon, title, shown]) => ({
    id: `story.cut.track.${key === 'gain_db' ? 'gain' : key === 'volume_db' ? 'volume' : key}`, scope: 'story' as const, label, icon, placement: ['context', 'inspector'] as ['context', 'inspector'],
    when: () => audioTrack() && !sq().cutBusy,
    run: () => { const tr = selTrack(); if (tr) void askText({ title: `${tr.name}: ${title}`, text: `now ${shown(tr[key])}`, initial: String(tr[key] <= STRIP.volume_db[0] && key === 'volume_db' ? '-inf' : tr[key]), placeholder: String(STRIP[key].join(' … ')) })
      .then((v) => { const n = stripValue(key, v); if (n !== null) void sq().cutStrip(tr.id, { [key]: n }) }) },
  })),
  ...[...TRACK_ROLES, null].map((role) => ({
    id: `story.cut.track.role.${role ?? 'none'}`, scope: 'story' as const, label: role ? ROLE_NAMES[role] : 'No role', icon: role ? ROLE_ICONS[role] : Tag, placement: ['context'] as ['context'],
    hint: role ? `named ${ROLE_NAMES[role]}, its gain, volume, pan and width set to the role's in Settings › Audio` : 'the role cleared; the strip stays',
    when: () => audioTrack() && !sq().cutBusy && selTrack()!.role !== role, run: () => { const tr = selTrack(); if (tr) void sq().cutRole(tr.id, role) },
  })),
  // AU4 (30 §16): a track's chain of VST3 effects — loom2's own host runs them; the track prints before the mix, the movie and the exports
  { id: 'story.cut.track.addEffect', scope: 'story', label: 'Add an effect…', icon: Plug, placement: ['context', 'inspector'], hint: 'a VST3 effect from your folders, after the others; loom2 prints the track through its effects before the mix, the movie and the exports',
    when: () => audioTrack() && !sq().cutBusy, run: () => { const tr = selTrack(); if (tr) sq().setFxPicker(tr.id) } },
  { id: 'story.cut.fx.edit', scope: 'story', label: "Open the effect's window", icon: AppWindow, placement: ['inspector'], hint: 'its own editor in a window of loom2\'s host; its settings are kept when you close the window',
    when: () => !!selFx() && !sq().fxOpen, run: () => { const tr = selTrack(), e = selFx(); if (tr && e) void sq().cutFxEditor(tr.id, e.id) } },
  { id: 'story.cut.fx.bypass', scope: 'story', label: 'Bypass / use the effect', icon: ToggleLeft, placement: ['inspector'], when: () => !!selFx() && !sq().cutBusy,
    run: () => { const tr = selTrack(), e = selFx(); if (tr && e) void sq().cutFx(tr.id, { op: 'bypass', fx: e.id, bypass: !e.bypass }) } },
  { id: 'story.cut.fx.up', scope: 'story', label: 'Earlier in the chain', icon: ArrowUp, placement: ['inspector'], when: () => fxIndex() > 0 && !sq().cutBusy,
    run: () => { const tr = selTrack(), e = selFx(); if (tr && e) void sq().cutFx(tr.id, { op: 'move', fx: e.id, to: fxIndex() - 1 }) } },
  { id: 'story.cut.fx.down', scope: 'story', label: 'Later in the chain', icon: ArrowDown, placement: ['inspector'], when: () => fxIndex() >= 0 && fxIndex() < (selTrack()?.chain.length ?? 0) - 1 && !sq().cutBusy,
    run: () => { const tr = selTrack(), e = selFx(); if (tr && e) void sq().cutFx(tr.id, { op: 'move', fx: e.id, to: fxIndex() + 1 }) } },
  { id: 'story.cut.fx.remove', scope: 'story', label: 'Remove the effect', icon: Trash2, placement: ['inspector'], danger: true, when: () => !!selFx() && !sq().cutBusy,
    run: () => { const tr = selTrack(), e = selFx(); if (tr && e) void sq().cutFx(tr.id, { op: 'remove', fx: e.id }) } },
  { id: 'story.cut.track.resetRole', scope: 'story', label: "Reset to its role's settings", icon: RefreshCw, placement: ['context', 'inspector'], hint: "gain, volume, pan and width as the role's in Settings › Audio",
    when: () => audioTrack() && !sq().cutBusy && !!selTrack()!.role, run: () => { const tr = selTrack(); if (tr?.role) void sq().cutRole(tr.id, tr.role) } },
  { id: 'story.cut.track.duck', scope: 'story', label: 'Duck the track under the dialogue', icon: VolumeX, placement: ['context', 'inspector'],
    when: () => isCut() && !!selTrack() && !isVideo(sq().tracks!, selTrack()!) && selTrack()!.items.some((i) => i.kind !== 'line') && dialogueOf(sq().tracks!).length > 0,
    run: () => { const tr = selTrack(); if (tr) void sq().cutEdit(duckSteps(sq().tracks!, tr.items)) } },
  { id: 'story.cut.addVideoTrack', scope: 'story', label: 'Add a video track', icon: Plus, placement: ['context', 'toolbar'], when: () => isCut() && !sq().cutBusy,
    run: () => edit1('sequence.addTracks', { video: 1, audio: 0 }) },
  { id: 'story.cut.addAudioTrack', scope: 'story', label: 'Add an audio track', icon: Volume2, placement: ['context', 'toolbar'], when: () => isCut() && !sq().cutBusy,
    run: () => edit1('sequence.addTracks', { video: 0, audio: 1 }) },
])

/** CE2: a clip's right-click on a FilmCraft cut (the clip selected by the caller). */
export function cutClipMenu(): MenuItem[] {
  const s = selCut()
  const t = sq().tracks
  const moveTo: MenuItem[] = s && t ? (isVideo(t, s.track) ? t.video : t.audio).filter((x) => x.id !== s.track.id).map((x) => ({
    label: `${trackRef(t, x)} · ${x.name}`, run: () => edit1('timeline.move', { moves: [{ clip: s.item.id, track: x.id, time: ticksOf(s.item.start, t.fps) }], insert: false }) })) : []
  const video = !!s && !!t && isVideo(t, s.track)
  const look: MenuItem[] = video ? [{ cmd: 'story.cut.dissolveIn' }, { cmd: 'story.cut.dissolveOut' }, { cmd: 'story.cut.dipIn' }, { cmd: 'story.cut.dipOut' }]
    : [{ cmd: 'story.cut.gain' }, { cmd: 'story.cut.fadeIn' }, { cmd: 'story.cut.fadeOut' }, { cmd: 'story.cut.duck' }, { cmd: 'story.cut.evenDialogue' }]   // CE3: a sound's verbs
  return [{ cmd: 'story.episode.update' }, sep, { cmd: 'story.cut.speed' }, { cmd: 'story.cut.freeze' }, sep, ...look, { cmd: 'story.cut.removeTransition' }, sep,
    ...(moveTo.length ? [{ label: 'Move to track', icon: ArrowRight, items: moveTo } as MenuItem, sep] : []),
    { cmd: 'story.cut.rename' }, { cmd: 'story.episode.openClip' }, sep, { cmd: 'story.cut.lift' }, { cmd: 'story.cut.rippleDelete' }, sep, { cmd: 'story.episode.undo' }, { cmd: 'story.episode.redo' }]
}

/** CE2: a track header's right-click (the track selected by the caller); D127: an audio track's strip and role. */
export function cutTrackMenu(): MenuItem[] {
  const strip: MenuItem[] = audioTrack() ? [{ cmd: 'story.cut.track.gain' }, { cmd: 'story.cut.track.volume' }, { cmd: 'story.cut.track.pan' }, { cmd: 'story.cut.track.width' },
    { label: 'Role', icon: Tag, items: [...TRACK_ROLES.map((r) => ({ cmd: `story.cut.track.role.${r}` })), { cmd: 'story.cut.track.role.none' }] }, { cmd: 'story.cut.track.resetRole' }, { cmd: 'story.cut.track.addEffect' }, sep] : []
  return [{ cmd: 'story.cut.track.rename' }, { cmd: 'story.cut.track.lock' }, { cmd: 'story.cut.track.mute' }, sep, ...strip, { cmd: 'story.cut.track.duck' }, sep,
    { cmd: 'story.cut.evenDialogue' }, sep, { cmd: 'story.cut.addVideoTrack' }, { cmd: 'story.cut.addAudioTrack' }]
}

/** CE2: the tracks' empty space. */
export function cutSpaceMenu(): MenuItem[] {
  return [{ cmd: 'story.episode.play' }, { cmd: 'story.episode.home' }, { cmd: 'story.episode.end' }, sep, { cmd: 'story.cut.addVideoTrack' }, { cmd: 'story.cut.addAudioTrack' }, sep,
    { cmd: 'story.episode.exportResolve' }, { label: 'Export one file', icon: FileDown, items: [{ cmd: 'story.episode.exportEdl' }, { cmd: 'story.episode.exportFcpxml' }, { cmd: 'story.episode.exportSrt' }] },
    { cmd: 'story.episode.render' }, { cmd: 'story.episode.renderMovie' }, sep, { cmd: 'story.episode.reassemble' }, { cmd: 'story.episode.updateAll' }, sep,
    { cmd: 'story.episode.rename' }, { cmd: 'story.episode.delete' }, sep, { cmd: 'story.episode.undo' }, { cmd: 'story.episode.redo' }]
}
