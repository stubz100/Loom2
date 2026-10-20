// AP1 thin (proto01_animate 20 §2, D114): the Final level's viewer — a final's composition shown frame by frame from
// `GET /finals/{id}/composition/frame?t&side`: ½ size while scrubbing (T1: 25 fps measured in E27), the full frame once the playhead
// rests (T2 ≈ 60 ms); the frames it got are kept by (revision, frame, size), so playback after a first pass is real time (T3) and an
// idle fill walks the shot at ½ while nothing else is asked — paused while the queue runs a job (D97 / D113: the session renders on
// demand only then). The chip says what is shown ("½ · cached 62 %") and always matches the frame (T8). The full AP1 (a sidecar over
// EffectCraft's frame server, the disk cache, the resolution and Fast Previews menus) comes after AE2.
import { create } from 'zustand'
import { baseUrl, getBackend, http, unwrap } from '../../api/client'
import type { Composition, Final } from '../../api/types'
import { useSession } from '../../store/session'

export type Level = 'performance' | 'final'
export type Side = 'half' | 'full'
export const REST_MS = 300                 // the playhead still this long: the full frame
const FULL_KEEP = 12                       // full frames kept (≈ 1.2 MB each at 832×480); every ½ frame of the shot is kept (≈ 150 KB)

export interface Shown { url: string; frame: number; side: Side; revision: number }

interface CompState {
  level: Level
  finalId: string | null
  final: Final | null
  comp: Composition | null
  frame: number
  playing: boolean
  shown: Shown | null
  fetching: boolean
  filled: number                           // ½ frames cached at this revision
  error: string | null
  setLevel: (level: Level) => void
  /** Show this final's composition at the Final level (its record and composition loaded, the first frame asked for). */
  open: (finalId: string) => Promise<void>
  /** Load the final and its composition again; a new revision drops the cached frames. */
  reload: () => Promise<void>
  setFrame: (n: number) => void
  step: (d: number) => void
  home: () => void
  end: () => void
  togglePlay: (on?: boolean) => void
  /** The playhead at rest: the full frame (what the rest timer calls). */
  settle: () => void
  /** The idle fill: the next ½ frame not cached, while nothing plays, nothing is in flight and no job runs. */
  tick: () => Promise<void>
}

const cache = new Map<string, string>()
const fullKeys: string[] = []
let wanted: { frame: number; side: Side } | null = null
let inflight: Promise<void> | null = null
let restTimer: number | null = null
let playTimer: number | null = null

const key = (rev: number, frame: number, side: Side) => `${rev}:${frame}:${side}`
/** The jobs the page knows: one running means the session renders on demand only (D97 / D113). */
export const queueBusy = (): boolean => Object.values(useSession.getState().jobs).some((j) => j.status === 'running')

function clearCache(): void {
  for (const u of cache.values()) URL.revokeObjectURL(u)
  cache.clear()
  fullKeys.length = 0
}

async function fetchFrame(final: Final, revision: number, frame: number, side: Side): Promise<string | null> {
  const b = getBackend()
  if (!b) return null
  const px = side === 'half' ? Math.round(Math.max(final.size.w, final.size.h) / 2) : 0
  const res = await fetch(`${baseUrl()}/finals/${final.id}/composition/frame?t=${frame / final.rate}&side=${px}`, { headers: { 'X-Loom-Token': b.token } })
  if (!res.ok) throw new Error(`frame ${frame}: ${res.status}`)
  const url = URL.createObjectURL(await res.blob())
  const k = key(revision, frame, side)
  const old = cache.get(k)
  if (old) URL.revokeObjectURL(old)
  cache.set(k, url)
  if (side === 'full') {
    fullKeys.push(k)
    while (fullKeys.length > FULL_KEEP) {
      const drop = fullKeys.shift()!
      const u = cache.get(drop)
      if (u) { URL.revokeObjectURL(u); cache.delete(drop) }
    }
  }
  return url
}

/** The chip's text: what is on screen and how much of the shot is ready. */
export function chipText(s: Pick<CompState, 'shown' | 'filled' | 'final' | 'fetching'>, busy = queueBusy()): string {
  const n = s.final?.frames ?? 0
  const pct = n ? Math.round((100 * s.filled) / n) : 0
  return `${s.shown ? (s.shown.side === 'full' ? 'full' : '½') : '…'} · cached ${pct} %${busy ? ' · a job runs: on demand' : ''}${s.fetching ? ' · fetching' : ''}`
}

export const useComposition = create<CompState>((set, get) => {
  const show = (frame: number, side: Side): boolean => {
    const { comp } = get()
    if (!comp) return false
    const url = cache.get(key(comp.revision, frame, side))
    if (!url) return false
    if (get().frame === frame && (side === 'full' || get().shown?.frame !== frame || get().shown?.side !== 'full')) set({ shown: { url, frame, side, revision: comp.revision } })
    return true
  }
  const count = (): number => {
    const { comp, final } = get()
    if (!comp || !final) return 0
    let n = 0
    for (let i = 0; i < final.frames; i++) if (cache.has(key(comp.revision, i, 'half'))) n++
    return n
  }
  const pump = (): void => {
    if (inflight) return
    inflight = (async () => {
      try {
        while (wanted) {
          const { final, comp } = get()
          const w = wanted
          if (!final || !comp) { wanted = null; break }
          if (cache.has(key(comp.revision, w.frame, w.side))) { wanted = null; show(w.frame, w.side); break }
          set({ fetching: true })
          try {
            await fetchFrame(final, comp.revision, w.frame, w.side)
            set({ error: null, filled: count() })
          } catch (e) { set({ error: (e as Error).message }) }
          if (wanted === w) wanted = null
          show(w.frame, w.side)
        }
      } finally { inflight = null; set({ fetching: false }) }
    })()
  }
  const request = (frame: number, side: Side): void => {
    if (show(frame, side)) return
    if (side === 'half' && show(frame, 'full')) return            // a full frame already here says more than a half one would
    wanted = { frame, side }
    pump()
  }
  const stopPlay = (): void => { if (playTimer !== null) { window.clearTimeout(playTimer); playTimer = null } }
  const armRest = (): void => {
    if (restTimer !== null) window.clearTimeout(restTimer)
    restTimer = window.setTimeout(() => { restTimer = null; get().settle() }, REST_MS)
  }
  return {
    level: 'performance', finalId: null, final: null, comp: null, frame: 0, playing: false, shown: null, fetching: false, filled: 0, error: null,
    setLevel: (level) => { if (level !== 'final') get().togglePlay(false); set({ level }) },
    open: async (finalId) => {
      if (get().finalId !== finalId) { get().togglePlay(false); set({ finalId, frame: 0, shown: null, comp: null, final: null }) }
      set({ level: 'final' })
      await get().reload()
    },
    reload: async () => {
      const id = get().finalId
      if (!id) return
      try {
        const final = await unwrap(http.GET('/finals/{fid}', { params: { path: { fid: id } } }))
        let comp: Composition | null = null
        try { comp = await unwrap(http.GET('/finals/{fid}/composition', { params: { path: { fid: id } } })) } catch { comp = null }
        if (comp?.revision !== get().comp?.revision || get().final?.id !== final.id) { clearCache(); wanted = null; set({ shown: null, filled: 0 }) }
        set({ final, comp, error: null, frame: Math.min(get().frame, Math.max(0, final.frames - 1)) })
        if (comp) { request(get().frame, 'half'); armRest() }
      } catch (e) { set({ error: (e as Error).message }) }
    },
    setFrame: (n) => {
      const f = get().final
      const frame = Math.max(0, Math.min(f ? f.frames - 1 : 0, Math.round(n)))
      set({ frame })
      request(frame, 'half')
      if (!get().playing) armRest()
    },
    step: (d) => { get().togglePlay(false); get().setFrame(get().frame + d) },
    home: () => { get().togglePlay(false); get().setFrame(0) },
    end: () => { get().togglePlay(false); get().setFrame((get().final?.frames ?? 1) - 1) },
    togglePlay: (on) => {
      const next = on ?? !get().playing
      if (next === get().playing) return
      set({ playing: next })
      stopPlay()
      if (!next) { armRest(); return }
      const period = 1000 / (get().final?.rate ?? 16)
      const loop = async (): Promise<void> => {
        if (!get().playing) return
        const t0 = performance.now()
        const n = get().final?.frames ?? 0
        const frame = n ? (get().frame + 1) % n : 0
        set({ frame })
        if (!show(frame, 'half') && !show(frame, 'full')) {       // not here yet: the clock waits for it (a first pass runs as fast as the frames come)
          wanted = { frame, side: 'half' }
          pump()
          while (inflight && get().playing && get().frame === frame) await inflight
        }
        if (!get().playing) return
        playTimer = window.setTimeout(() => void loop(), Math.max(0, period - (performance.now() - t0)))
      }
      playTimer = window.setTimeout(() => void loop(), period)
    },
    settle: () => { if (!get().playing && get().comp) request(get().frame, 'full') },
    tick: async () => {
      const { final, comp, playing } = get()
      if (!final || !comp || playing || inflight || wanted || queueBusy()) return
      for (let i = 0; i < final.frames; i++) {
        const frame = (get().frame + i) % final.frames
        if (!cache.has(key(comp.revision, frame, 'half'))) {
          set({ fetching: true })
          inflight = fetchFrame(final, comp.revision, frame, 'half').then(() => { set({ filled: count(), error: null }) }).catch((e: Error) => set({ error: e.message }))
            .finally(() => { inflight = null; set({ fetching: false }) })
          await inflight
          return
        }
      }
    },
  }
})
