// D121 (AW2): the one timeline's arithmetic, pure — where a frame sits on a track, which frame a pointer is on, how many frames a drag moved,
// the ruler's ticks, and a figure's keys read as bars where they run frame by frame (a motion clip's bake) and as diamonds where they stand
// alone. Timeline.tsx draws with it; the levels build their rows with `keyRuns`.

export type Span = readonly [number, number]

/** A frame's place on a track, as a CSS percentage of its width (the span's ends are 0 % and 100 %). */
export const pct = (frame: number, [a, b]: Span): string => `${((frame - a) / Math.max(1, b - a)) * 100}%`

/** The frame under a pointer at `x` on a track that starts at `left` and is `width` wide, clamped to the span. */
export function frameAt(x: number, left: number, width: number, [a, b]: Span): number {
  const f = Math.round(a + ((x - left) / Math.max(1, width)) * (b - a))
  return Math.max(a, Math.min(b, f))
}

/** The frames a drag of `dx` pixels moved on a track `width` wide. */
export const deltaFrames = (dx: number, width: number, [a, b]: Span): number => Math.round((dx / Math.max(1, width)) * (b - a))

/** The ruler's ticks: a minor one every few frames (fewer as the span grows), a major one with its seconds at every whole second. */
export function ticks([a, b]: Span, fps: number): { frame: number; major: boolean; label?: string }[] {
  const n = b - a
  const minor = n > 400 ? 24 : n > 200 ? 8 : n > 100 ? 4 : 2
  const out: { frame: number; major: boolean; label?: string }[] = []
  for (let f = Math.ceil(a / minor) * minor; f <= b; f += minor) {
    const major = fps > 0 && f % Math.round(fps) === 0
    out.push(major ? { frame: f, major, label: `${f / Math.round(fps)}s` } : { frame: f, major })
  }
  return out
}

/** Keyed frames read for a row: runs of `min` or more consecutive frames (a motion clip baked frame by frame) as bars, the rest as keys. */
export function keyRuns(frames: number[], min = 4): { runs: [number, number][]; singles: number[] } {
  const fs = [...new Set(frames)].sort((x, y) => x - y)
  const runs: [number, number][] = []
  const singles: number[] = []
  let i = 0
  while (i < fs.length) {
    let j = i
    while (j + 1 < fs.length && fs[j + 1] === fs[j] + 1) j++
    if (j - i + 1 >= min) runs.push([fs[i], fs[j]])
    else for (let k = i; k <= j; k++) singles.push(fs[k])
    i = j + 1
  }
  return { runs, singles }
}

/** The span a stage's timeline shows: from 0 past the range's end and the last key, with room to drag a key or the range's end. */
export function stageSpan(rangeEnd: number, keyed: number[]): Span {
  const last = Math.max(rangeEnd, ...keyed, 1)
  return [0, last + Math.max(12, Math.round(last * 0.1))]
}
