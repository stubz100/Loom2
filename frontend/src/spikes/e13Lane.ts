// E13 timeline spike (ArtCraft 08 §7, D74): the single-lane model, pure — integer frame ticks, clips in order, an overlap with the previous
// clip is a dissolve (14 R157). Built to be lifted into P17 as is: lookup of what shows at a frame (one clip, or two with a mix), ripple
// trims that keep every invariant, and EDL (CMX 3600) / FCPXML 1.10 export for Resolve.

export interface LaneClip { id: string; source: number; in: number; out: number }   // source frames [in, out)
export interface Lane { fps: number; clips: LaneClip[]; overlaps: number[] }         // overlaps[i]: frames clip i dissolves over clip i-1 (0 = cut)
export interface Shown { i: number; local: number }                                   // clip index, source frame
export interface At { a: Shown; b?: Shown; mix?: number }                             // b over a by mix (0 → a, 1 → b)

export const len = (c: LaneClip): number => c.out - c.in

/** Each clip's first frame on the timeline. */
export function starts(lane: Lane): number[] {
  const out: number[] = []
  let t = 0
  lane.clips.forEach((c, i) => { if (i > 0) t -= lane.overlaps[i] ?? 0; out.push(t); t += len(c) })
  return out
}

export function duration(lane: Lane): number {
  if (!lane.clips.length) return 0
  const s = starts(lane)
  return s[s.length - 1] + len(lane.clips[lane.clips.length - 1])
}

/** What shows at timeline frame f: the clip (and its source frame), or two clips mid-dissolve with the incoming one's weight. */
export function at(lane: Lane, f: number, s: number[] = starts(lane)): At | null {
  if (f < 0 || f >= duration(lane)) return null
  let hi = s.length - 1, lo = 0
  while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (s[mid] <= f) lo = mid; else hi = mid - 1 }   // last clip starting at or before f
  const i = lo, c = lane.clips[i]
  const shown = (k: number): Shown => ({ i: k, local: lane.clips[k].in + (f - s[k]) })
  const prev = i > 0 ? lane.clips[i - 1] : null
  if (prev && f < s[i - 1] + len(prev)) {                            // inside the dissolve with the previous clip
    const ov = lane.overlaps[i]
    return { a: shown(i - 1), b: shown(i), mix: (f - s[i] + 0.5) / ov }
  }
  void c
  return { a: shown(i) }
}

/** Ripple-trim clip i's in or out edge by delta frames (positive moves the edge right), within its source and keeping the dissolves
 *  no longer than either neighbour; returns a new lane (the input is not changed). */
export function trim(lane: Lane, i: number, edge: 'in' | 'out', delta: number, sourceLen: (source: number) => number): Lane {
  const clips = lane.clips.map((c) => ({ ...c }))
  const c = clips[i]
  if (edge === 'in') c.in = Math.max(0, Math.min(c.out - 1, c.in + Math.round(delta)))
  else c.out = Math.min(sourceLen(c.source), Math.max(c.in + 1, c.out + Math.round(delta)))
  const overlaps = lane.overlaps.map((o, k) => (k === 0 ? 0 : Math.min(o, len(clips[k]) - 1, len(clips[k - 1]) - 1)))
  return { ...lane, clips, overlaps }
}

/** HH:MM:SS:FF at an integer fps (non-drop). */
export function tc(frames: number, fps: number): string {
  const f = frames % fps, s = Math.floor(frames / fps)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(Math.floor(s / 3600))}:${p(Math.floor(s / 60) % 60)}:${p(s % 60)}:${p(f)}`
}

/** CMX 3600 EDL: one event per clip; a dissolve event ("D nnn") where a clip overlaps the previous one. Reel names are the source ids. */
export function toEDL(lane: Lane, title: string, reel: (source: number) => string): string {
  const s = starts(lane)
  const lines = [`TITLE: ${title}`, 'FCM: NON-DROP FRAME', '']
  lane.clips.forEach((c, i) => {
    const n = String(i + 1).padStart(3, '0')
    const r = reel(c.source).slice(0, 8).padEnd(8)
    const ov = i > 0 ? lane.overlaps[i] : 0
    const recIn = s[i], recOut = s[i] + len(c)
    if (ov > 0) {
      const prev = lane.clips[i - 1]
      lines.push(`${n}  ${reel(prev.source).slice(0, 8).padEnd(8)} V     C        ${tc(prev.out - ov, lane.fps)} ${tc(prev.out - ov, lane.fps)} ${tc(recIn, lane.fps)} ${tc(recIn, lane.fps)}`)
      lines.push(`${n}  ${r} V     D    ${String(ov).padStart(3, '0')} ${tc(c.in, lane.fps)} ${tc(c.out, lane.fps)} ${tc(recIn, lane.fps)} ${tc(recOut, lane.fps)}`)
    } else {
      lines.push(`${n}  ${r} V     C        ${tc(c.in, lane.fps)} ${tc(c.out, lane.fps)} ${tc(recIn, lane.fps)} ${tc(recOut, lane.fps)}`)
    }
    lines.push(`* FROM CLIP NAME: ${reel(c.source)}`, '')
  })
  return lines.join('\n')
}

/** FCPXML 1.10: one format and one asset per source, a spine of asset-clips with a cross dissolve where clips overlap. */
export function toFCPXML(lane: Lane, title: string, media: (source: number) => { name: string; src: string; frames: number }, w: number, h: number): string {
  const t = (fr: number) => `${fr}/${lane.fps}s`
  const esc = (x: string) => x.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;')
  const sources = [...new Set(lane.clips.map((c) => c.source))]
  const assets = sources.map((src) => {
    const m = media(src)
    return `    <asset id="a${src}" name="${esc(m.name)}" start="0s" duration="${t(m.frames)}" hasVideo="1" format="f1"><media-rep kind="original-media" src="${esc(m.src)}"/></asset>`
  })
  const s = starts(lane)
  const spine: string[] = []
  lane.clips.forEach((c, i) => {
    const ov = i > 0 ? lane.overlaps[i] : 0
    if (ov > 0) spine.push(`          <transition name="Cross Dissolve" offset="${t(s[i])}" duration="${t(ov)}"/>`)
    spine.push(`          <asset-clip ref="a${c.source}" name="${esc(media(c.source).name)}" offset="${t(s[i])}" start="${t(c.in)}" duration="${t(len(c))}" format="f1" tcFormat="NDF"/>`)
  })
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<!DOCTYPE fcpxml>',
    '<fcpxml version="1.10">',
    '  <resources>',
    `    <format id="f1" frameDuration="1/${lane.fps}s" width="${w}" height="${h}"/>`,
    ...assets,
    '  </resources>',
    '  <library>',
    `    <event name="${esc(title)}">`,
    `      <project name="${esc(title)}">`,
    `        <sequence format="f1" duration="${t(duration(lane))}" tcStart="0s" tcFormat="NDF">`,
    '          <spine>',
    ...spine.map((l) => l.replace(/^ {10}/, '            ')),
    '          </spine>',
    '        </sequence>',
    '      </project>',
    '    </event>',
    '  </library>',
    '</fcpxml>',
    '',
  ].join('\n')
}
