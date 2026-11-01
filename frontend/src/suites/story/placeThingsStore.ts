// D180 (W60): the parts of a built set that move, picked by the author on the place's set picture — the sheet's state (the place version
// it is open for, SAM 3's points, the find in flight and the mask it left on the set picture's document), and the verbs: keep the mask as a
// thing (its card and where it stands are the server's), make a thing's 3D model, clean the set picture under the things, remove one.
// As SC3's thingsStore, for a place's set.
import { create } from 'zustand'
import { ApiError, api, http, unwrap } from '../../api/client'
import { useSession } from '../../store/session'
import { useStory } from './storyStore'

export interface ThingPoint { x: number; y: number; label: 0 | 1 }
interface Target { pid: string; vid: string }
interface PlaceThingsState {
  target: Target | null
  size: { w: number; h: number } | null                        // the set picture's pixels (the points and the mask are in them)
  points: ThingPoint[]
  mode: 0 | 1
  job: string | null                                           // the find in flight
  docId: string | null
  mask: Uint8Array | null                                      // the last find's mask, w·h grey
  open: (target: Target | null) => Promise<void>
  setMode: (m: 0 | 1) => void
  addPoint: (x: number, y: number, label: 0 | 1) => Promise<void>
  clear: () => void
  keep: (name: string) => Promise<boolean>
  model: (pid: string, vid: string, tid: string) => Promise<void>
  clean: (pid: string, vid: string) => Promise<void>
  remove: (pid: string, vid: string, tid: string) => Promise<void>
}

const toast = (text: string, kind: 'info' | 'error' | 'success' = 'error') => useSession.getState().toast(text, kind)
const detail = (e: unknown) => (e as ApiError).detail ?? String(e)
/** The set picture of a place version (its first source), or null. */
export const setPicture = (pid: string, vid: string): string | null =>
  useStory.getState().profiles.find((p) => p.id === pid)?.versions.find((v) => v.id === vid)?.place_set?.sources[0]?.asset_id ?? null

export const usePlaceThings = create<PlaceThingsState>()((set, get) => ({
  target: null, size: null, points: [], mode: 1, job: null, docId: null, mask: null,
  open: async (target) => {
    set({ target, points: [], job: null, mask: null, size: null })
    const pic = target ? setPicture(target.pid, target.vid) : null
    if (!pic) return
    try { const a = await unwrap(http.GET('/assets/{asset_id}', { params: { path: { asset_id: pic } } })); if (get().target === target) set({ size: { w: a.w ?? 0, h: a.h ?? 0 } }) }
    catch (e) { toast(`The set picture: ${detail(e)}`) }
  },
  setMode: (m) => set({ mode: m }),
  addPoint: async (x, y, label) => {
    const { target, points } = get()
    if (!target) return
    const next = [...points, { x: Math.round(x), y: Math.round(y), label }]
    set({ points: next })
    if (!next.some((p) => p.label === 1)) return                                     // SAM 3 needs a point on the thing first
    try {
      const r = await unwrap(http.POST('/story/profiles/{pid}/versions/{vid}/set/things/find', { params: { path: { pid: target.pid, vid: target.vid } }, body: { points: next } }))
      set({ job: r.job_id, docId: r.document_id })
    } catch (e) { toast(`Find the thing: ${detail(e)}`) }
  },
  clear: () => set({ points: [], mask: null, job: null }),
  keep: async (name) => {
    const { target, points, mask } = get()
    if (!target || !mask) return false
    try {
      const p = await unwrap(http.POST('/story/profiles/{pid}/versions/{vid}/set/things', { params: { path: { pid: target.pid, vid: target.vid } }, body: { name, points } }))
      useStory.setState({ profiles: useStory.getState().profiles.map((x) => (x.id === p.id ? p : x)) })
      set({ points: [], mask: null })
      return true
    } catch (e) { toast(`Keep the thing: ${detail(e)}`); return false }
  },
  model: async (pid, vid, tid) => {
    try {
      await unwrap(http.POST('/story/profiles/{pid}/versions/{vid}/set/things/{tid}/model', { params: { path: { pid, vid, tid } } }))
      toast('Its 3D model is queued — some minutes on the GPU; it lands on the thing, and Clay places it', 'info')
      await useStory.getState().loadProfiles()
    } catch (e) { toast(`Make its 3D model: ${detail(e)}`) }
  },
  clean: async (pid, vid) => {
    try {
      const r = await unwrap(http.POST('/story/profiles/{pid}/versions/{vid}/set/things/clean', { params: { path: { pid, vid } } }))
      toast(`The set picture is cleaned under ${r.things.length} thing${r.things.length === 1 ? '' : 's'} — about a minute on the GPU; the faces are baked from it again, their Fills kept`, 'info')
      await useStory.getState().loadProfiles()
    } catch (e) { toast(`Clean the set picture: ${detail(e)}`) }
  },
  remove: async (pid, vid, tid) => {
    try {
      const p = await unwrap(http.DELETE('/story/profiles/{pid}/versions/{vid}/set/things/{tid}', { params: { path: { pid, vid, tid } } }))
      useStory.setState({ profiles: useStory.getState().profiles.map((x) => (x.id === p.id ? p : x)) })
    } catch (e) { toast(`Remove the thing: ${detail(e)}`) }
  },
}))

// the find landed: its mask is the set picture's document's selection, read as raw grey bytes
useSession.subscribe((s, prev) => {
  if (s.jobs === prev.jobs) return
  const t = usePlaceThings.getState()
  if (!t.job) return
  const j = s.jobs[t.job]
  if (!j || j.status === 'queued' || j.status === 'running') return
  usePlaceThings.setState({ job: null })
  if (j.status === 'done' && t.docId) {
    const doc = t.docId
    void api.getBytes(`/documents/${doc}/selection`).then((b) => { if (usePlaceThings.getState().docId === doc) usePlaceThings.setState({ mask: new Uint8Array(b) }) })
      .catch((e) => toast(`The mask: ${detail(e)}`))
  } else if (j.status !== 'done') toast(`Find the thing ${j.status}: ${j.error ?? ''}`)
})
