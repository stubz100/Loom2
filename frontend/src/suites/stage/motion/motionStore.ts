// CA1 (proto01_animate 01 step 5): the motion library's state in the Motion section — the files, the clips of the files opened so far, the
// clip picked with its trim / speed / in-place, and *Apply at the playhead*. U5 (G8): the clip becomes a block on the selected figure's
// track (blocks.ts evaluates it: retargeted onto its body's hip height, from where it stands at the playhead and facing its way).
import { create } from 'zustand'
import { useSession } from '../../../store/session'
import type { ApiError } from '../../../api/client'
import { st } from '../stageStore'
import { keyframesOf } from '../anim'
import { blockKeys, useBlocks, type MotionBlock } from '../blocks'
import { clipsOf, listFiles, type MotionClip, type MotionFile } from './library'

export type MotionFilter = 'all' | 'starter' | 'local' | 'mine'   // U5c: mine — the project's animations and the author's library

interface MotionState {
  files: MotionFile[]; localDir: string | null; starterDir: string | null; loaded: boolean; error: string | null
  clips: Record<string, MotionClip[] | 'loading' | { error: string }>      // per file id
  open: Record<string, boolean>                                              // the file groups shown open
  filter: MotionFilter; q: string
  picked: MotionClip | null; start: number; end: number | null; speed: number; inPlace: boolean
  lock: boolean; ground: boolean; alongPath: boolean; blend: number        // foot lock; the feet on the floor (AP1, D141); walk the figure's floor path; frames eased in from what it was doing
  applying: boolean
  refresh: () => Promise<void>
  toggle: (file: MotionFile) => void
  pick: (clip: MotionClip | null) => void
  set: (patch: Partial<Pick<MotionState, 'filter' | 'q' | 'start' | 'end' | 'speed' | 'inPlace' | 'lock' | 'ground' | 'alongPath' | 'blend'>>) => void
  apply: () => Promise<void>
}

/** A Mixamo download is one clip named after its file: it is listed without loading the file. */
export const singleClip = (f: MotionFile): MotionClip => ({ file: f, name: f.name, duration: 0, rig: null, rootMotion: false })

export const useMotion = create<MotionState>((set, get) => ({
  files: [], localDir: null, starterDir: null, loaded: false, error: null, clips: {}, open: {}, filter: 'all', q: '',
  picked: null, start: 0, end: null, speed: 1, inPlace: false, lock: true, ground: true, alongPath: true, blend: 6, applying: false,
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
  pick: (clip) => set({ picked: clip, start: 0, end: null, speed: 1, inPlace: false }),                   // the lock, path and blend choices stay
  set: (patch) => set(patch),
  apply: async () => {
    // U5 (D157 G8): a clip is a block on the figure's track — evaluated first (its length goes on the block; a clip that cannot be
    // evaluated is not added), never baked into its keys, and the stage's range stays as it is (F37)
    const s = useSession.getState()
    const clip = get().picked
    const o = st().object(st().selected)
    const doc = st().current
    if (!clip || !o || o.kind !== 'mannequin' || !doc) return
    const path = get().alongPath && !!o.path && o.path.length >= 2
    const had = (keyframesOf(doc).objects[o.id]?.length ?? 0) > 0 || (doc.tracks?.[o.id]?.length ?? 0) > 0
    const block: MotionBlock = { id: `blk_${crypto.randomUUID().replace(/-/g, '').slice(0, 8)}`, source: { kind: 'library', id: clip.file.id, clip: clip.name },
      start: st().frame, trim_in: get().start, trim_out: get().end ?? null, loops: path && /_loop$|loop$/i.test(clip.name) ? 0 : 1, speed: get().speed,
      blend_in: had ? get().blend : 0, blend_out: 0, in_place: get().inPlace && !path, foot_lock: get().lock, ground: get().ground, mirror: false, path, length: 0 }
    set({ applying: true })
    try {
      const probe = { ...doc, tracks: { ...(doc.tracks ?? {}), [o.id]: [...(doc.tracks?.[o.id] ?? []), block] } }
      const keys = await blockKeys(probe, o.id, block.id)
      if (!keys?.length) throw new Error(useBlocks.getState().errors[block.id] ?? 'it could not be evaluated')
      const first = keys[0].frame, last = keys[keys.length - 1].frame
      st().addBlock(o.id, { ...block, length: last - first + 1 })
      const past = last > doc.range.end ? ` — past the shot's end (${doc.range.end}); the range stays` : ''
      s.toast(`${clip.name} on ${o.name}: a clip from frame ${first} to ${last}${path ? ', along its path' : ''}${get().lock ? ', feet locked' : ''}${past}`, 'success')
    } catch (e) { s.toast(`The clip was not applied: ${e instanceof Error ? e.message : String(e)}`, 'error') }
    finally { set({ applying: false }) }
  },
}))
