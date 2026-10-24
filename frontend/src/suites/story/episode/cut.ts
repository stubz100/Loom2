// CE2 (D126, proto01_animate 30 §12): a FilmCraft cut's tracks in the Episode's editor — pure helpers: where a clip sits, what a gesture
// asks of FilmCraft (the command steps POST /timelines/{id}/edit runs), the frame ↔ tick maths. FilmCraft and the server keep the cut;
// nothing here changes it. The tools are Premiere's (and FilmCraft's): Select moves a clip and trims an edge, Ripple trims and closes up,
// Roll moves an edit point, Slip moves a clip's source under it, Slide moves a clip between its neighbours, Razor cuts.
import type { CutItem, CutTrack, CutTracks, CutTransition, TrackRole, TrackStrip } from '../../../api/types'

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

// ---- CE3 (proto01_animate 30 §14): sound ----------------------------------------------------------------------------------------
/** A constant-power fade on a sound's head or tail (FilmCraft's audio transition takes the edge the video one does). */
export function fadeStep(item: CutItem, edge: 'in' | 'out', frames = 12): Step {
  return { id: 'sequence.applyAudioTransition', params: { clip: item.id, frames: Math.max(1, Math.min(frames, Math.floor(item.duration) - 1)), edge } }
}
export const gainStep = (item: CutItem, db: number): Step => ({ id: 'clip.audioGain', params: { clips: [item.id], db, mode: 'set' } })
/** Every spoken line on the cut's audio tracks, and (D127) every sound on a dialogue track. */
export const dialogueOf = (t: CutTracks): CutItem[] => t.audio.flatMap((tr) => tr.items.filter((i) => i.kind === 'line' || (tr.role === 'dialogue' && i.kind === 'sound')))
/** *Duck under the dialogue*: the lines typed dialogue, these clips music, FilmCraft keys them down where a line speaks. */
export function duckSteps(t: CutTracks, music: CutItem[]): Step[] {
  const lines = dialogueOf(t).map((i) => i.id)
  const ids = music.filter((i) => i.kind !== 'line').map((i) => i.id)
  if (!lines.length || !ids.length) return []
  return [{ id: 'essentialSound.setType', params: { clips: lines, type: 'dialogue' } }, { id: 'essentialSound.setType', params: { clips: ids, type: 'music' } },
    { id: 'essentialSound.generateDucking', params: { clips: ids } }]
}
/** *Even out the dialogue*: every line brought to −23 LUFS (EBU R128 dialogue) by its gain. */
export function evenDialogueSteps(t: CutTracks): Step[] {
  const lines = dialogueOf(t).map((i) => i.id)
  return lines.length ? [{ id: 'essentialSound.setType', params: { clips: lines, type: 'dialogue' } }, { id: 'essentialSound.autoMatch', params: { clips: lines, target: -23 } }] : []
}
/** A gain or volume in dB as the editor writes it (−6 dB, +3 dB, 0 dB). */
export const db = (v: number): string => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(Math.round(v * 10) / 10)} dB`

// ---- D127 (proto01_animate 30 §16): an audio track's channel strip and role ------------------------------------------------------
export const TRACK_ROLES: TrackRole[] = ['dialogue', 'music', 'effects']
export const ROLE_NAMES: Record<TrackRole, string> = { dialogue: 'Dialogue', music: 'Music', effects: 'Effects' }
/** The strip's ranges, as the server's config.TrackStrip brings values inside them (−96 dB is FilmCraft's silent fader floor: −∞). */
export const STRIP: Record<keyof TrackStrip, readonly [number, number]> = { gain_db: [-36, 36], volume_db: [-96, 18], pan: [-100, 100], width: [0, 200] }
export const volumeLabel = (v: number): string => (v <= STRIP.volume_db[0] ? '−∞ dB' : db(v))
/** Pan as the author reads it: 100 % L … 50 % L · 50 % R … 100 % R. */
export function panLabel(p: number): string {
  const l = Math.round((100 - p) / 2), r = 100 - l
  return r === 0 ? '100 % L' : l === 0 ? '100 % R' : `${l} % L · ${r} % R`
}
export const widthLabel = (w: number): string => (w <= 0 ? 'mono' : `${Math.round(w)} %`)
/** The strip's settings away from neutral, short — the track header's line ("gain −6 dB · vol −∞ dB · 70 % L · 30 % R · width 150 %"). */
export function stripLabel(t: TrackStrip): string {
  return [t.gain_db ? `gain ${db(t.gain_db)}` : '', t.volume_db ? `vol ${volumeLabel(t.volume_db)}` : '', t.pan ? panLabel(t.pan) : '',
    t.width !== 100 ? `width ${widthLabel(t.width)}` : ''].filter(Boolean).join(' · ')
}
/** A typed strip setting: a number brought into its range (the volume also takes −∞ / -inf), or null when it is not one. */
export function stripValue(key: keyof TrackStrip, text: string | null): number | null {
  const s = (text ?? '').trim().replace(/−/g, '-').replace(/\s*(dB|%)$/i, '')
  if (key === 'volume_db' && /^-?(inf|∞)$/i.test(s)) return STRIP.volume_db[0]
  const n = Number(s)
  if (!s || !Number.isFinite(n)) return null
  const [lo, hi] = STRIP[key]
  return Math.min(hi, Math.max(lo, n))
}
/** The volume slider's taper (0…1 of its travel): the bottom quarter is −96 (−∞)…−30 dB, the rest −30…+18 — a fader's resolution where
 *  a mix lives. Snapped to 0.5 dB and to 0 dB within 0.5 dB. */
export function faderDb(pos: number): number {
  const p = Math.min(1, Math.max(0, pos))
  const v = p <= 0.25 ? -96 + (p / 0.25) * 66 : -30 + ((p - 0.25) / 0.75) * 48
  const r = Math.round(v * 2) / 2
  return Math.abs(r) <= 0.5 ? 0 : r
}
export const faderPos = (v: number): number => (v <= -30 ? (Math.max(-96, v) + 96) / 66 * 0.25 : 0.25 + (Math.min(18, v) + 30) / 48 * 0.75)
/** A strip slider's value with its detents: gain to 0 dB within 0.5 dB, pan to the centre within 3, width to 100 % within 4. */
export function detent(key: 'gain_db' | 'pan' | 'width', v: number): number {
  const [at, near] = key === 'gain_db' ? [0, 0.5] : key === 'pan' ? [0, 3] : [100, 4]
  return Math.abs(v - at) <= near ? at : v
}
