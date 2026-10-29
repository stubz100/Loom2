// U5d (D157; proto01_UI2 04 §3.2, §2.1): two read-only tracks of the animation editor, pure — the lines of the shot at their place on the
// scene's timeline, each as long as its voice (F39: the action is timed to them, and the shot's range is extended to them only when asked),
// and the stretches where a figure turns its back to the camera (F42: a performance is told, and a character without a back view says so).
import type { FlowNode, StageCamera, StageDoc } from '../../api/types'
import { sampleDoc } from './anim'

/** The breath between two lines, in frames; an unvoiced line is timed by its words at this rate. */
export const LINE_GAP_FRAMES = 6
export const WORDS_PER_SECOND = 2.6

export interface LineSpan { index: number; from: number; to: number; text: string; speaker: string | null; seconds: number; estimated: boolean }

/** The shot's lines one after another from `start`: each as long as its voice's audio, or (not voiced yet) its words at 2.6 a second. */
export function lineSpans(lines: Pick<FlowNode['lines'][number], 'text' | 'speaker' | 'audio_asset_id'>[], secs: Record<string, number | null | undefined>, start: number, fps: number): LineSpan[] {
  const out: LineSpan[] = []
  let at = start
  lines.forEach((l, index) => {
    const text = l.text.trim()
    if (!text) return
    const voiced = l.audio_asset_id ? secs[l.audio_asset_id] ?? null : null
    const seconds = voiced ?? Math.max(0.8, text.split(/\s+/).length / WORDS_PER_SECOND)
    const n = Math.max(1, Math.round(seconds * fps))
    out.push({ index, from: at, to: at + n - 1, text, speaker: l.speaker ?? null, seconds, estimated: voiced === null })
    at += n + LINE_GAP_FRAMES
  })
  return out
}

/** F39: when the lines outlast the shot, the end frame its range would need to hold them; else null. */
export function linesOutlast(spans: LineSpan[], range: { start: number; end: number }): number | null {
  const last = spans.length ? spans[spans.length - 1].to : null
  return last !== null && last > range.end ? last : null
}

/** The direction a figure faces at its yaw (degrees; yaw 0 faces +Z, as the walk steers it — motion/walkpath.ts). */
const forward = (yawDeg: number): [number, number] => { const a = (yawDeg * Math.PI) / 180; return [Math.sin(a), Math.cos(a)] }

/** F42: the stretches of frames where the figure's back is to the camera (more than `deg` from facing it), from the document sampled at
 *  each frame (its keys and its evaluated blocks). */
export function awayStretches(doc: StageDoc, objectId: string, cameraId: string, from: number, to: number, deg = 110): [number, number][] {
  const out: [number, number][] = []
  const limit = Math.cos((deg * Math.PI) / 180)
  let open: number | null = null
  for (let f = from; f <= to; f++) {
    const d = sampleDoc(doc, f)
    const o = d.objects.find((x) => x.id === objectId), cam = d.cameras.find((c) => c.id === cameraId) as StageCamera | undefined
    let away = false
    if (o && cam) {
      const [fx, fz] = forward(o.transform.rot[1] ?? 0)
      const vx = cam.pos[0] - o.transform.pos[0], vz = cam.pos[2] - o.transform.pos[2], len = Math.hypot(vx, vz)
      away = len > 1e-6 && (fx * vx + fz * vz) / len < limit
    }
    if (away && open === null) open = f
    if (!away && open !== null) { out.push([open, f - 1]); open = null }
  }
  if (open !== null) out.push([open, to])
  return out
}
