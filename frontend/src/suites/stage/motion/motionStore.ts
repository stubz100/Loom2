// CA1 (proto01_animate 01 step 5): the motion library's state in the Motion section — the files, the clips of the files opened so far, the
// clip picked with its trim / speed / in-place, and *Apply at the playhead*: the clip retargeted onto the selected figure (its body's hip
// height), baked from the playhead where the figure stands and facing its way, thinned, written as its keys (one undo step).
import { create } from 'zustand'
import { useSession } from '../../../store/session'
import type { ApiError } from '../../../api/client'
import { bodyDims } from '../body'
import { st } from '../stageStore'
import { bakeKeys, thinKeys } from './bake'
import { clipsOf, listFiles, retargetClip, type MotionClip, type MotionFile } from './library'

export type MotionFilter = 'all' | 'starter' | 'local'

interface MotionState {
  files: MotionFile[]; localDir: string | null; starterDir: string | null; loaded: boolean; error: string | null
  clips: Record<string, MotionClip[] | 'loading' | { error: string }>      // per file id
  open: Record<string, boolean>                                              // the file groups shown open
  filter: MotionFilter; q: string
  picked: MotionClip | null; start: number; end: number | null; speed: number; inPlace: boolean
  applying: boolean
  refresh: () => Promise<void>
  toggle: (file: MotionFile) => void
  pick: (clip: MotionClip | null) => void
  set: (patch: Partial<Pick<MotionState, 'filter' | 'q' | 'start' | 'end' | 'speed' | 'inPlace'>>) => void
  apply: () => Promise<void>
}

/** A Mixamo download is one clip named after its file: it is listed without loading the file. */
export const singleClip = (f: MotionFile): MotionClip => ({ file: f, name: f.name, duration: 0, rig: null, rootMotion: false })

export const useMotion = create<MotionState>((set, get) => ({
  files: [], localDir: null, starterDir: null, loaded: false, error: null, clips: {}, open: {}, filter: 'all', q: '',
  picked: null, start: 0, end: null, speed: 1, inPlace: false, applying: false,
  refresh: async () => {
    try {
      const r = await listFiles()
      set({ files: r.items, localDir: r.local_dir, starterDir: r.starter_dir, loaded: true, error: null })
    } catch (e) { set({ loaded: true, error: (e as ApiError).detail ?? String(e) }) }
  },
  toggle: (file) => {
    const open = !get().open[file.id]
    set({ open: { ...get().open, [file.id]: open } })
    if (!open || get().clips[file.id]) return
    set({ clips: { ...get().clips, [file.id]: 'loading' } })
    clipsOf(file).then((c) => set({ clips: { ...get().clips, [file.id]: c } }))
      .catch((e) => set({ clips: { ...get().clips, [file.id]: { error: e instanceof Error ? e.message : String(e) } } }))
  },
  pick: (clip) => set({ picked: clip, start: 0, end: null, speed: 1, inPlace: false }),
  set: (patch) => set(patch),
  apply: async () => {
    const s = useSession.getState()
    const clip = get().picked
    const o = st().object(st().selected)
    const doc = st().current
    if (!clip || !o || o.kind !== 'mannequin' || !doc) return
    const at = st().sampledDoc()?.objects.find((x) => x.id === o.id) ?? o
    const dims = bodyDims(o.body as never)
    const hip = (0.04 + dims.limbs.thigh + dims.limbs.shin) * dims.scale                 // the figure's hip above its ankles (its body's)
    set({ applying: true })
    try {
      const r = await retargetClip(clip, { fps: doc.size.fps || 24, start: get().start, end: get().end ?? undefined, speed: get().speed, hip, inPlace: get().inPlace })
      const frame = st().frame
      const keys = thinKeys(bakeKeys(r.frames, at.transform, frame))
      st().applyMotion(o.id, keys, `motion · ${clip.name}`)
      s.toast(`${clip.name} on ${o.name}: frames ${frame}–${frame + r.frames.length - 1} (${r.frames.length} frames, ${keys.length} keys${r.travel > 0.05 ? `, ${r.travel.toFixed(2)} m travelled` : ''})`, 'success')
    } catch (e) { s.toast(`The clip was not applied: ${e instanceof Error ? e.message : String(e)}`, 'error') }
    finally { set({ applying: false }) }
  },
}))
