// D125 (S13, proto01_UIcomp 04 §3.4; SP6): the cut from the Flow — one route (play mode's walk, a pick at each Choice), each visual node's
// shot at its approved version (bin.ts: the final one, else the current), stamped; *Assemble again* keeps the trims and the dissolves where
// the same shots follow each other; a lane clip whose shot has a newer approved take is *changed*, and *Update* swaps it with its trims kept
// (RC3's rule). Pure: assemble.test.ts.
import type { AssembleReport, CutTracks, FlowGraph, FlowNode, FlowOption, StoryVariable } from '../../../api/types'
import { optionsAvailable, startPlay, stepPlay } from '../flow/play'
import { binVersion } from './bin'
import { clampOverlaps, type Lane, type LaneClip } from './lane'

export interface RouteChoice { node: FlowNode; options: FlowOption[]; pick: string }
interface ShotLike { id: string; name: string; current: string; versions: { id: string; state: string; clip_id?: string | null }[] }
interface ClipLike { id: string; frames: number; fps: number }

/** One route of the Flow: from the Start, play mode's walk with `picks` at each Choice (an unpicked one, or a pick no longer offered, takes
 *  its first available option). The visual nodes in order and the Choices met with the options they offered. A node met again ends it. */
export function walkRoute(graph: FlowGraph, nodes: Record<string, FlowNode>, variables: StoryVariable[], picks: Record<string, string>): { nodes: FlowNode[]; choices: RouteChoice[] } {
  let s = startPlay(graph, nodes, variables)
  const seen = new Set<string>()
  const out: FlowNode[] = [], choices: RouteChoice[] = []
  while (!s.ended && s.node && !seen.has(s.node)) {
    seen.add(s.node)
    const n = nodes[s.node]
    if (s.waiting === 'choice') {
      const options = optionsAvailable(n, s.vars)
      if (!options.length) break
      const pick = options.some((o) => o.id === picks[n.id]) ? picks[n.id] : options[0].id
      choices.push({ node: n, options, pick })
      s = stepPlay(s, graph, nodes, pick)
    } else { out.push(n); s = stepPlay(s, graph, nodes) }
  }
  return { nodes: out, choices }
}

/** The route's name from its picks ("Stay", "Stay · Left"), empty for a Flow without a Choice. */
export const routeLabel = (choices: RouteChoice[]): string => choices.map((c) => c.options.find((o) => o.id === c.pick)?.label || c.pick).join(' · ')
/** The picks a cut keeps (`Timeline.route`): a Choice node id → its option id. */
export const routePicks = (choices: RouteChoice[]): Record<string, string> => Object.fromEntries(choices.map((c) => [c.node.id, c.pick]))

/** The lane of a route: each visual node's shot at its approved version, its whole clip, stamped (shot, version, node); `missing` names the
 *  nodes without a shot or a clip yet. With `prev` (Assemble again) a shot on the same clip keeps its trims, and a dissolve is kept where the
 *  same two shots still follow each other. */
export function assembleLane(route: FlowNode[], shots: ShotLike[], clips: Map<string, ClipLike>, fps: number, prev: Lane | null = null): { lane: Lane; missing: string[] } {
  const out: LaneClip[] = [], missing: string[] = []
  for (const n of route) {
    const sh = n.shot_id ? shots.find((x) => x.id === n.shot_id) : undefined
    const v = sh ? binVersion(sh) : undefined
    const c = v?.clip_id ? clips.get(v.clip_id) : undefined
    if (!sh || !v || !c) { missing.push(sh?.name || n.title || n.type); continue }
    const old = prev?.clips.find((x) => x.shot?.id === sh.id && x.source === c.id)
    const out_ = old ? Math.min(old.out, c.frames) : c.frames
    out.push({ id: old?.id ?? `${c.id}-${n.id}`, source: c.id, in: old ? Math.min(old.in, out_ - 1) : 0, out: out_, ...(c.fps !== fps ? { fps: c.fps } : {}), shot: { id: sh.id, version: v.id, node: n.id } })
  }
  const pairOv = (a: string | undefined, b: string | undefined): number => {
    if (!prev || !a || !b) return 0
    const j = prev.clips.findIndex((x, k) => k > 0 && x.shot?.id === b && prev.clips[k - 1].shot?.id === a)
    return j > 0 ? prev.overlaps[j] ?? 0 : 0
  }
  const lane: Lane = { fps, clips: out, overlaps: out.map((c, i) => (i ? pairOv(out[i - 1].shot?.id, c.shot?.id) : 0)) }
  return { lane: { ...lane, overlaps: clampOverlaps(lane) }, missing }
}

// ---- U7b (D157, proto01_UI2 05 §1): the new shell's Assemble reads each shot's final (the server's `timelines.final_of`, mirrored) ----
/** U6c: the methods whose clip is the shot's final (made in one pass, no layers to put together). */
export const CLIP_METHODS = ['one_pass', 'start_still', 'speaking']
interface FinalLike { shot_id?: string | null; shot_version?: string | null; clip_id?: string | null; updated_at: string }
interface ShotFinalLike { id: string; current: string; versions: { id: string; state: string; method?: string | null; clip_id?: string | null }[] }

/** The shot version and the clip Episode lays for a shot: the final of the version marked final, else the shot's latest final, else none.
 *  A final is a final shot's assembled clip (a final from before A1 names no version: the current one); a version made in one pass has its
 *  clip as its final. */
export function finalOf(sh: ShotFinalLike, finals: FinalLike[]): { version: string; clip: string | null } {
  const cur = sh.versions.find((v) => v.id === sh.current)
  const marked = cur?.state === 'final' ? cur : [...sh.versions].reverse().find((v) => v.state === 'final')
  const mine = finals.filter((f) => f.shot_id === sh.id && f.clip_id).sort((a, b) => (a.updated_at < b.updated_at ? 1 : a.updated_at > b.updated_at ? -1 : 0))
  const of = (v: ShotFinalLike['versions'][number]): string | null =>
    mine.find((f) => (f.shot_version || sh.current) === v.id)?.clip_id ?? (v.method && CLIP_METHODS.includes(v.method) && v.clip_id ? v.clip_id : null)
  const m = marked ? of(marked) : null
  if (marked && m) return { version: marked.id, clip: m }
  if (mine.length) return { version: mine[0].shot_version || sh.current, clip: mine[0].clip_id! }
  const c = cur ? of(cur) : null
  if (cur && c) return { version: cur.id, clip: c }
  return { version: (marked ?? cur)?.id ?? sh.current, clip: null }
}

/** F33: the route's shots and the ones without a final — what the Assemble sheet says before it runs. */
export function routeFinals(route: FlowNode[], shots: (ShotFinalLike & { name: string })[], finals: FinalLike[]): { shots: number; without: string[] } {
  const on = route.flatMap((n) => { const sh = n.shot_id ? shots.find((x) => x.id === n.shot_id) : undefined; return sh ? [{ n, sh }] : [] })
  return { shots: on.length, without: on.filter((x) => !finalOf(x.sh, finals).clip).map((x) => x.n.title || x.sh.name) }
}
export const routeFinalsText = (r: { shots: number; without: string[] }): string =>
  `${r.shots} shot${r.shots === 1 ? '' : 's'} on this route${r.without.length ? ` · ${r.without.length} without a final (left out): ${r.without.slice(0, 4).join(', ')}${r.without.length > 4 ? '…' : ''}` : ''}`

/** What the server's Assemble did, in a line. */
export function assembledText(name: string, r: AssembleReport): string {
  const n = (k: string[], what: string) => (k.length ? [`${k.length} ${what}`] : [])
  const parts = [...n(r.placed, 'placed'), ...n(r.updated, 'updated'), ...n(r.kept, 'kept'), ...n(r.removed, 'taken off'), ...n(r.held, 'held for their lines')]
  const notes = [...(r.missing.length ? [`${r.missing.length} without a final (left out): ${r.missing.slice(0, 4).join(', ')}`] : []),
    ...r.short.map((x) => `${x.name}: the lines run ${x.lines_s} s, the final ${x.final_s} s`)]
  return `${name}: ${parts.join(', ') || 'nothing changed'}${notes.length ? ` · ${notes.join(' · ')}` : ''}`
}

/** F39: V1's shots whose lines run past their end (each line placed inside its shot's run, by the node) — `lines` and `shot` in seconds. */
export function linesPast(t: CutTracks): { clip: number; shot_id: string | null; name: string; lines: number; shot: number }[] {
  const runs: CutTracks['video'][number]['items'][] = []
  for (const i of (t.video[0]?.items ?? []).filter((x) => x.kind === 'take')) {
    const r = runs[runs.length - 1], last = r?.[r.length - 1]
    if (last && i.node_id && last.node_id === i.node_id && Math.abs(last.start + last.duration - i.start) < 0.5) r.push(i); else runs.push([i])
  }
  const lines = t.audio.flatMap((tr) => tr.items).filter((i) => i.kind === 'line')
  return runs.flatMap((r) => {
    const a = r[0].start, b = r[r.length - 1].start + r[r.length - 1].duration
    const mine = r[0].node_id ? lines.filter((l) => l.node_id === r[0].node_id && l.start >= a - 0.5 && l.start < b - 0.5) : []
    const end = Math.max(...mine.map((l) => l.start + l.duration), b)
    const s1 = (x: number) => Math.round((x / t.fps) * 10) / 10
    return end > b + 0.5 ? [{ clip: r[0].id, shot_id: r[0].shot_id ?? null, name: r[0].name, lines: s1(end - a), shot: s1(b - a) }] : []
  })
}

export interface LaneChange { i: number; name: string; version: string; clip: string }
/** The lane's stamped clips whose shot has a newer approved take: its approved version (final first, else current) has another clip, or
 *  is another version. */
export function laneChanges(lane: Lane, shots: ShotLike[]): LaneChange[] {
  return lane.clips.flatMap((c, i) => {
    if (!c.shot) return []
    const sh = shots.find((x) => x.id === c.shot!.id)
    const v = sh ? binVersion(sh) : undefined
    return sh && v?.clip_id && (v.clip_id !== c.source || v.id !== c.shot.version) ? [{ i, name: sh.name, version: v.id, clip: v.clip_id }] : []
  })
}

/** *Update*: the clip at `i` becomes the change's — its trims kept within the new clip, its dissolve kept where it still fits. */
export function updateClip(lane: Lane, ch: LaneChange, clip: ClipLike): Lane {
  const c = lane.clips[ch.i]
  if (!c?.shot) return lane
  const out = Math.min(c.out, clip.frames)
  const next: LaneClip = { ...c, source: clip.id, in: Math.min(c.in, out - 1), out, shot: { ...c.shot, version: ch.version } }
  if (clip.fps !== lane.fps) next.fps = clip.fps; else delete next.fps
  const l: Lane = { ...lane, clips: lane.clips.map((x, k) => (k === ch.i ? next : x)) }
  return { ...l, overlaps: clampOverlaps(l) }
}
