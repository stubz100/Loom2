// CE2 (D126, proto01_animate 30 §12): a FilmCraft cut's tracks in the Episode's editor — pure helpers: where a clip sits, what a gesture
// asks of FilmCraft (the command steps POST /timelines/{id}/edit runs), the frame ↔ tick maths. FilmCraft and the server keep the cut;
// nothing here changes it. The tools are Premiere's (and FilmCraft's): Select moves a clip and trims an edge, Ripple trims and closes up,
// Roll moves an edit point, Slip moves a clip's source under it, Slide moves a clip between its neighbours, Razor cuts.
import type { CutItem, CutTrack, CutTracks, CutTransition } from '../../../api/types'

export const TICK = 254_016_000_000                       // FilmCraft's ticks a second
export type CutTool = 'select' | 'ripple' | 'roll' | 'slip' | 'slide' | 'razor'
export const CUT_TOOLS: CutTool[] = ['select', 'ripple', 'roll', 'slip', 'slide', 'razor']
export interface Step { id: string; params?: Record<string, unknown> }

export const ticksOf = (frames: number, fps: number): number => Math.round((frames * TICK) / fps)
export const allTracks = (t: CutTracks): CutTrack[] => [...t.video, ...t.audio]
export const endOf = (track: CutTrack | undefined): number => Math.max(0, ...(track?.items ?? []).map((i) => i.start + i.duration))

/** A track's short name as FilmCraft takes it in commands ("V1" … "A3"). */
export function trackRef(t: CutTracks, track: CutTrack): string {
  const v = t.video.findIndex((x) => x.id === track.id)
  return v >= 0 ? `V${v + 1}` : `A${t.audio.findIndex((x) => x.id === track.id) + 1}`
}

export function findItem(t: CutTracks, id: number): { track: CutTrack; item: CutItem } | null {
  for (const track of allTracks(t)) { const item = track.items.find((i) => i.id === id); if (item) return { track, item } }
  return null
}

export function neighbours(track: CutTrack, item: CutItem): { prev: CutItem | null; next: CutItem | null } {
  const items = [...track.items].sort((a, b) => a.start - b.start)
  const k = items.findIndex((i) => i.id === item.id)
  return { prev: k > 0 ? items[k - 1] : null, next: k >= 0 && k + 1 < items.length ? items[k + 1] : null }
}

export function itemAt(track: CutTrack, frame: number): CutItem | null {
  return track.items.find((i) => i.start <= frame && frame < i.start + i.duration) ?? null
}

export const transitionInto = (track: CutTrack, item: CutItem): CutTransition | undefined => track.transitions.find((x) => x.to === item.id)
export const transitionOutOf = (track: CutTrack, item: CutItem): CutTransition | undefined => track.transitions.find((x) => x.from === item.id)

/** The clip's name in the editor: a take by its shot's name (else its clip as the bins show it), a picture or a sound by what it is, a
 *  line by its number; the file's name otherwise. */
export function itemLabel(item: CutItem, shot?: { name: string }, clip?: { model_id: string; frames: number }): string {
  if (shot) return shot.name
  if (clip) return `${clip.model_id.split('-')[0]} · ${clip.frames}f`
  if (item.kind === 'line') return `line ${(item.line ?? 0) + 1}`
  if (item.kind === 'picture' || item.kind === 'sound') return item.kind
  return item.name.replace(/\.(png|jpg|jpeg|webp|wav|mp3|mp4|mov)$/i, '')
}

/** Where a pointer gesture lands: on the clip's body or on one of its edges (the outer 6 px). */
export type Grip = 'body' | 'in' | 'out'
export const gripAt = (x: number, width: number, edge = 6): Grip => (x < Math.min(edge, width / 3) ? 'in' : x > width - Math.min(edge, width / 3) ? 'out' : 'body')

/** The command a drag asks for: `delta` frames along the time, onto `toTrack` (the body with Select). Null when it asks nothing. */
export function dragStep(t: CutTracks, tool: CutTool, track: CutTrack, item: CutItem, grip: Grip, delta: number, toTrack: CutTrack = track): Step | null {
  const d = Math.round(delta)
  const moved = toTrack.id !== track.id
  if (!d && !moved) return null
  if (tool === 'razor') return null
  if (tool === 'slip') return { id: 'timeline.slip', params: { clip: item.id, deltaFrames: d } }
  if (tool === 'slide') return grip === 'body' ? { id: 'timeline.slide', params: { clip: item.id, deltaFrames: d } } : null
  if (tool === 'roll') {
    const { prev, next } = neighbours(track, item)
    const left = grip === 'in' ? prev : grip === 'out' ? item : null
    const right = grip === 'in' ? item : grip === 'out' ? next : null
    if (!left || !right || Math.abs(left.start + left.duration - right.start) > 0.5) return null      // an edit point needs two clips that touch
    return { id: 'timeline.roll', params: { left: left.id, right: right.id, deltaFrames: clampRoll(left, right, d) } }
  }
  if (grip === 'body') {
    if (tool === 'ripple') return null
    if (moved && (isVideo(t, track) !== isVideo(t, toTrack))) return null                         // a picture stays on a video track, a sound on an audio one
    return { id: 'timeline.move', params: { moves: [{ clip: item.id, track: toTrack.id, time: ticksOf(Math.max(0, item.start + d), t.fps) }], insert: false } }
  }
  return { id: 'timeline.trim', params: { clip: item.id, edge: grip, mode: tool === 'ripple' ? 'ripple' : 'regular', deltaFrames: clampTrim(item, grip, d) } }
}

export const isVideo = (t: CutTracks, track: CutTrack): boolean => t.video.some((x) => x.id === track.id)

/** A trim keeps at least a frame of the clip (FilmCraft refuses the rest: a trim past the media's end is its to answer). */
export function clampTrim(item: CutItem, edge: 'in' | 'out', d: number): number {
  return edge === 'in' ? Math.min(d, Math.floor(item.duration) - 1) : Math.max(d, 1 - Math.floor(item.duration))
}
export function clampRoll(left: CutItem, right: CutItem, d: number): number {
  return Math.max(1 - Math.floor(left.duration), Math.min(d, Math.floor(right.duration) - 1))
}

/** Razor: the clip under the pointer cut at the frame (FilmCraft cuts that track only). */
export function razorStep(t: CutTracks, track: CutTrack, frame: number): Step | null {
  const it = itemAt(track, frame)
  if (!it || frame <= it.start || frame >= it.start + it.duration) return null
  return { id: 'timeline.razor', params: { time: ticksOf(Math.round(frame), t.fps), track: track.id } }
}

/** What a drop on a track places: a clip (a take, with its shot when it comes from the Shots bin) or a Catalogue picture / video on a
 *  video track; anything else on an audio track is taken for a sound (the drag knows images and videos only: the server checks the kind). */
export function trackDrop<C extends { id: string; asset_id?: string | null }>(items: { kind: string; id: string; media?: string }[], video: boolean, clips: C[]):
  { clips: C[]; assets: string[]; verdict: { ok: boolean; label?: string; reason?: string } } {
  const assets = items.filter((i) => i.kind === 'asset')
  if (!assets.length) return { clips: [], assets: [], verdict: { ok: false } }
  const asClip = (i: { id: string }) => clips.find((c) => c.asset_id === i.id || c.id === i.id)
  const take = assets.map(asClip).filter((c): c is C => !!c)
  const rest = assets.filter((i) => !asClip(i)).map((i) => i.id)
  if (!video && take.length) return { clips: [], assets: [], verdict: { ok: false, reason: 'A clip goes on a video track' } }
  const n = take.length + rest.length
  return { clips: video ? take : [], assets: rest, verdict: { ok: true, label: video ? `Place ${n === 1 ? 'it' : `${n} items`} here` : `Place ${n === 1 ? 'the sound' : `${n} sounds`} here` } }
}

/** A dissolve or a dip on a clip's head or tail (FilmCraft centres it on the cut, using the clips' handles). */
export function transitionStep(item: CutItem, effect: 'cross_dissolve' | 'dip_to_black', edge: 'in' | 'out', frames = 12): Step {
  return { id: 'sequence.applyVideoTransition', params: { clip: item.id, effect, frames: Math.max(1, Math.min(frames, Math.floor(item.duration) - 1)), edge } }
}
