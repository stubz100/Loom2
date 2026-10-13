// P17 (D83): the single-lane model, pure — lifted from the E13 spike (frontend/src/spikes/e13Lane.ts) with one addition: a clip at
// another frame rate than the lane's (Wan at 16 fps on a 24 fps lane) takes `ticks` = round(len × laneFps / clipFps) and is scrubbed by
// nearest frame — no frames are made (D27: the RIFE conform at export is post-MVP). Integer frame ticks, clips in order, an overlap with
// the previous clip is a dissolve (14 R157). The server (orchestrator/loom2/timelines.py) does the same maths and writes the exports;
// `toEDL` here exists for the parity test and a live preview.

export interface LaneClip { id: string; source: string; in: number; out: number; fps?: number; shot?: { id: string; version: string; node: string | null } }   // source frames [in, out) of clip `source`; 17 §3e: the Story shot it is
export interface Lane { fps: number; clips: LaneClip[]; overlaps: number[] }                     // overlaps[i]: ticks clip i dissolves over clip i-1
export interface Shown { i: number; local: number }                                               // clip index, source frame
export interface At { a: Shown; b?: Shown; mix?: number }                                         // b over a by mix (0 → a, 1 → b)

export const len = (c: LaneClip): number => c.out - c.in
/** Lane ticks a clip occupies: its source frames, scaled when its own rate differs from the lane's. */
export const ticks = (lane: Lane, c: LaneClip): number => Math.max(1, Math.round(len(c) * lane.fps / (c.fps ?? lane.fps)))

/** Each clip's first tick on the lane. */
export function starts(lane: Lane): number[] {
  const out: number[] = []
  let t = 0
  lane.clips.forEach((c, i) => { if (i > 0) t -= lane.overlaps[i] ?? 0; out.push(t); t += ticks(lane, c) })
  return out
}

export function duration(lane: Lane): number {
  if (!lane.clips.length) return 0
  const s = starts(lane)
  return s[s.length - 1] + ticks(lane, lane.clips[lane.clips.length - 1])
}

/** What shows at lane tick f: the clip (and its source frame, nearest when the rates differ), or two clips mid-dissolve with the
 *  incoming one's weight. */
export function at(lane: Lane, f: number, s: number[] = starts(lane)): At | null {
  if (f < 0 || f >= duration(lane)) return null
  let hi = s.length - 1, lo = 0
  while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (s[mid] <= f) lo = mid; else hi = mid - 1 }   // last clip starting at or before f
  const i = lo
  const shown = (k: number): Shown => {
    const c = lane.clips[k]
    const local = c.in + Math.floor((f - s[k]) * (c.fps ?? lane.fps) / lane.fps)
    return { i: k, local: Math.min(c.out - 1, local) }
  }
  if (i > 0 && f < s[i - 1] + ticks(lane, lane.clips[i - 1])) {   // inside the dissolve with the previous clip
    const ov = lane.overlaps[i]
    return { a: shown(i - 1), b: shown(i), mix: (f - s[i] + 0.5) / ov }
  }
  return { a: shown(i) }
}

/** Ripple trim of clip i's in or out edge by `delta` source frames; every clip keeps ≥ 1 frame and every dissolve stays shorter
 *  than both clips it joins. */
export function trim(lane: Lane, i: number, edge: 'in' | 'out', delta: number, sourceLen: (source: string) => number): Lane {
  const clips = lane.clips.map((c) => ({ ...c }))
  const c = clips[i]
  if (edge === 'in') c.in = Math.max(0, Math.min(c.out - 1, c.in + Math.round(delta)))
  else c.out = Math.min(sourceLen(c.source), Math.max(c.in + 1, c.out + Math.round(delta)))
  const next = { ...lane, clips }
  return { ...next, overlaps: clampOverlaps(next) }
}

/** Set the dissolve into clip i (0 = a cut), clamped to both clips. */
export function setOverlap(lane: Lane, i: number, frames: number): Lane {
  if (i <= 0) return lane
  const overlaps = [...lane.overlaps]
  overlaps[i] = Math.max(0, Math.round(frames))
  return { ...lane, overlaps: clampOverlaps({ ...lane, overlaps }) }
}

export function clampOverlaps(lane: Lane): number[] {
  return lane.clips.map((c, k) => (k === 0 ? 0 : Math.max(0, Math.min(lane.overlaps[k] ?? 0, ticks(lane, c) - 1, ticks(lane, lane.clips[k - 1]) - 1))))
}

/** Append a clip (whole, a cut). */
export function append(lane: Lane, c: LaneClip): Lane {
  return { ...lane, clips: [...lane.clips, c], overlaps: [...lane.overlaps, 0] }
}

export function remove(lane: Lane, i: number): Lane {
  const clips = lane.clips.filter((_, k) => k !== i)
  const overlaps = lane.overlaps.filter((_, k) => k !== i)
  if (overlaps.length) overlaps[0] = 0
  const next = { ...lane, clips, overlaps }
  return { ...next, overlaps: clampOverlaps(next) }
}

/** Move clip `from` to position `to` (its incoming dissolve travels with it; the first clip's is a cut). */
export function move(lane: Lane, from: number, to: number): Lane {
  if (from === to || from < 0 || to < 0 || from >= lane.clips.length || to >= lane.clips.length) return lane
  const clips = [...lane.clips], overlaps = [...lane.overlaps]
  const [c] = clips.splice(from, 1); const [o] = overlaps.splice(from, 1)
  clips.splice(to, 0, c); overlaps.splice(to, 0, o)
  overlaps[0] = 0
  const next = { ...lane, clips, overlaps }
  return { ...next, overlaps: clampOverlaps(next) }
}

/** HH:MM:SS:FF at an integer fps (non-drop). */
export function tc(frames: number, fps: number): string {
  const f = frames % fps, s = Math.floor(frames / fps)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(Math.floor(s / 3600))}:${p(Math.floor(s / 60) % 60)}:${p(s % 60)}:${p(f)}`
}

const reel = (source: string): string => source.replace(/^clp_/, '').slice(0, 8).padEnd(8)

/** CMX 3600 EDL — the same text orchestrator/loom2/timelines.py writes (parity-tested); source times in the clip's own frames. */
export function toEDL(lane: Lane, title: string): string {
  const s = starts(lane)
  const lines = [`TITLE: ${title}`, 'FCM: NON-DROP FRAME', '']
  lane.clips.forEach((c, i) => {
    const n = String(i + 1).padStart(3, '0')
    const rate = c.fps ?? lane.fps
    const ov = i > 0 ? lane.overlaps[i] : 0
    const recIn = s[i], recOut = s[i] + ticks(lane, c)
    if (ov > 0) {
      const prev = lane.clips[i - 1]
      const prate = prev.fps ?? lane.fps
      const pov = Math.round(ov * prate / lane.fps)
      lines.push(`${n}  ${reel(prev.source)} V     C        ${tc(prev.out - pov, prate)} ${tc(prev.out - pov, prate)} ${tc(recIn, lane.fps)} ${tc(recIn, lane.fps)}`)
      lines.push(`${n}  ${reel(c.source)} V     D    ${String(ov).padStart(3, '0')} ${tc(c.in, rate)} ${tc(c.out, rate)} ${tc(recIn, lane.fps)} ${tc(recOut, lane.fps)}`)
    } else {
      lines.push(`${n}  ${reel(c.source)} V     C        ${tc(c.in, rate)} ${tc(c.out, rate)} ${tc(recIn, lane.fps)} ${tc(recOut, lane.fps)}`)
    }
    lines.push(`* FROM CLIP NAME: ${c.source}`, '')
  })
  return lines.join('\n')
}
