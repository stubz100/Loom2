// P17 (D83): the Sequence tab's verbs — every one has a mouse home (the lane's context menu, the Inspector, the transport) per D32;
// undo / redo take Ctrl+Z / Ctrl+Shift+Z in the Animate scope (the clip player has no undo of its own).
import { ArrowLeft, ArrowRight, ChevronFirst, ChevronLast, ChevronLeft, ChevronRight, Clapperboard, FileDown, Pause, Play, Plus, Redo2, RefreshCw, Scissors, SkipBack, SkipForward, Trash2, Undo2, Workflow, ZoomIn, ZoomOut } from 'lucide-react'
import { registerCommands, sep, type MenuItem } from '../../../frame/commands'
import { askConfirm, askText, useSession } from '../../../store/session'
import { useAnimate } from '../../animate/animateStore'
import { useStory } from '../storyStore'
import { assembleLane, laneChanges, routeLabel, routePicks, updateClip, walkRoute } from './assemble'
import { duration, ticks } from './lane'
import { useSequence } from './sequenceStore'

const sq = () => useSequence.getState()
const hasSeq = () => !!sq().current
const hasSel = () => hasSeq() && sq().selected !== null && !!sq().lane?.clips[sq().selected!]
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
  { id: 'story.episode.undo', scope: 'story', label: 'Undo (cut)', icon: Undo2, keys: 'Ctrl+Z', placement: ['toolbar', 'context'], when: () => hasSeq() && sq().undo.length > 0, run: () => sq().undoEdit() },
  { id: 'story.episode.redo', scope: 'story', label: 'Redo (cut)', icon: Redo2, keys: 'Ctrl+Shift+Z', placement: ['toolbar', 'context'], when: () => hasSeq() && sq().redo.length > 0, run: () => sq().redoEdit() },
  { id: 'story.episode.play', scope: 'story', label: 'Play / pause the cut', icon: Play, keys: 'Space', placement: ['toolbar', 'context'], when: () => hasSeq() && !!sq().lane?.clips.length, run: () => sq().togglePlay() },
  { id: 'story.episode.stepBack', scope: 'story', label: 'Previous frame', icon: SkipBack, keys: 'ArrowLeft', placement: ['toolbar', 'context'], when: hasSeq, run: () => sq().setPlayhead(sq().playhead - 1) },
  { id: 'story.episode.stepForward', scope: 'story', label: 'Next frame', icon: SkipForward, keys: 'ArrowRight', placement: ['toolbar', 'context'], when: hasSeq, run: () => sq().setPlayhead(sq().playhead + 1) },
  { id: 'story.episode.back10', scope: 'story', label: 'Back 10 frames', icon: ChevronLeft, keys: 'Shift+ArrowLeft', placement: ['toolbar'], when: hasSeq, run: () => sq().setPlayhead(sq().playhead - 10) },
  { id: 'story.episode.fwd10', scope: 'story', label: 'Forward 10 frames', icon: ChevronRight, keys: 'Shift+ArrowRight', placement: ['toolbar'], when: hasSeq, run: () => sq().setPlayhead(sq().playhead + 10) },
  { id: 'story.episode.home', scope: 'story', label: 'Start of the cut', icon: ChevronFirst, keys: 'Home', placement: ['toolbar', 'context'], when: hasSeq, run: () => sq().setPlayhead(0) },
  { id: 'story.episode.end', scope: 'story', label: 'End of the cut', icon: ChevronLast, keys: 'End', placement: ['toolbar', 'context'], when: hasSeq, run: () => { const l = sq().lane; if (l) sq().setPlayhead(duration(l) - 1) } },
  { id: 'story.episode.zoomIn', scope: 'story', label: 'Zoom the lane in', icon: ZoomIn, placement: ['toolbar'], when: hasSeq, run: () => sq().zoom(1.5) },
  { id: 'story.episode.zoomOut', scope: 'story', label: 'Zoom the lane out', icon: ZoomOut, placement: ['toolbar'], when: hasSeq, run: () => sq().zoom(1 / 1.5) },
  { id: 'story.episode.exportEdl', scope: 'story', label: 'Export EDL (CMX 3600)', icon: FileDown, placement: ['inspector', 'context'], when: () => hasSeq() && !!sq().lane?.clips.length, run: () => void exportChecked('edl') },
  { id: 'story.episode.exportSrt', scope: 'story', label: 'Export subtitles (.srt from the nodes\' lines)', icon: FileDown, placement: ['inspector', 'context'], when: () => hasSeq() && !!sq().lane?.clips.length, run: () => void exportChecked('srt') },
  { id: 'story.episode.exportFcpxml', scope: 'story', label: 'Export FCPXML 1.10', icon: FileDown, placement: ['inspector', 'context'], when: () => hasSeq() && !!sq().lane?.clips.length, run: () => void exportChecked('fcpxml') },
  { id: 'story.episode.render', scope: 'story', label: 'Render a draft clip (CPU)', icon: Clapperboard, placement: ['inspector', 'context'], when: () => hasSeq() && !!sq().lane?.clips.length, run: () => void sq().render() },
  { id: 'story.episode.openClip', scope: 'story', label: 'Open the clip in the player', icon: Pause, placement: ['inspector', 'context'], when: hasSel,
    run: () => { const l = sq().lane!; const c = l.clips[sq().selected!]; an().select(c.source); useSession.getState().toast('Opened in the clip player (Animate · Performance)', 'info') } },
])

/** Right-click on a lane clip (selected by the caller) or on the lane's empty space. */
export function laneMenu(onClip: boolean): MenuItem[] {
  return onClip
    ? [{ cmd: 'story.episode.update' }, { cmd: 'story.episode.dissolve' }, { cmd: 'story.episode.moveLeft' }, { cmd: 'story.episode.moveRight' }, { cmd: 'story.episode.openClip' }, sep, { cmd: 'story.episode.removeClip' }, sep, { cmd: 'story.episode.undo' }, { cmd: 'story.episode.redo' }]
    : [{ cmd: 'story.episode.addCurrent' }, sep, { cmd: 'story.episode.play' }, { cmd: 'story.episode.stepBack' }, { cmd: 'story.episode.stepForward' }, { cmd: 'story.episode.home' }, { cmd: 'story.episode.end' }, sep, { cmd: 'story.episode.exportResolve' }, { label: 'Export one file', icon: FileDown, items: [{ cmd: 'story.episode.exportEdl' }, { cmd: 'story.episode.exportFcpxml' }, { cmd: 'story.episode.exportSrt' }] }, { cmd: 'story.episode.render' }, sep, { cmd: 'story.episode.assemble' }, { cmd: 'story.episode.reassemble' }, { cmd: 'story.episode.updateAll' }, sep, { cmd: 'story.episode.rename' }, { cmd: 'story.episode.delete' }, { cmd: 'story.episode.new' }, sep, { cmd: 'story.episode.undo' }, { cmd: 'story.episode.redo' }]
}
