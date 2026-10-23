// D123 (SC3c): the things of a picture set, picked by the author on its picture. The sheet's state — the set it is open for, the points
// (SAM 3's prompts: 1 the thing, 0 not it), the find in flight and the mask it left on the set's document — and the make in flight (the
// clean plate, the relief's rebuild, a model per thing), the stage reloaded as each lands.
import { create } from 'zustand'
import { ApiError, api, http, unwrap } from '../../api/client'
import { askText, useSession } from '../../store/session'
import { useStage } from './stageStore'

export interface ThingPoint { x: number; y: number; label: 0 | 1 }
interface ThingsState {
  setId: string | null
  size: { w: number; h: number } | null                        // the picture's pixels (the points and the mask are in them)
  points: ThingPoint[]
  mode: 0 | 1                                                  // what a left click marks: 1 the thing, 0 not it (a right-click the other)
  job: string | null                                           // the find in flight
  docId: string | null
  mask: Uint8Array | null                                      // the last find's mask, w·h grey
  shadows: Uint8Array | null                                   // D124: the shadows the clean takes with the things not made yet, w·h grey
  making: string[]                                             // the make's jobs still to land
  open: (setId: string | null) => Promise<void>
  setMode: (m: 0 | 1) => void
  addPoint: (x: number, y: number, label: 0 | 1) => Promise<void>
  clear: () => void
  keep: (name: string) => Promise<boolean>
  rename: (setId: string, thingId: string) => Promise<void>
  remove: (setId: string, thingId: string) => Promise<void>
  make: (setId: string) => Promise<void>
  /** D124: the shadows *Make the things* would clean with them, read again (after a keep or a removal). */
  loadShadows: () => Promise<void>
}

const toast = (text: string, kind: 'info' | 'error' | 'success' = 'error') => useSession.getState().toast(text, kind)
const detail = (e: unknown) => (e as ApiError).detail ?? String(e)
const stageId = () => useStage.getState().current?.id ?? null
const reload = async () => { const id = stageId(); if (id) await useStage.getState().open(id) }
const plateOf = (setId: string) => useStage.getState().current?.objects.find((o) => o.id === setId)?.plate_asset_id ?? null

export const useThings = create<ThingsState>()((set, get) => ({
  setId: null, size: null, points: [], mode: 1, job: null, docId: null, mask: null, shadows: null, making: [],
  open: async (setId) => {
    set({ setId, points: [], job: null, mask: null, size: null, shadows: null })
    const plate = setId ? plateOf(setId) : null
    if (!plate) return
    try { const a = await unwrap(http.GET('/assets/{asset_id}', { params: { path: { asset_id: plate } } })); if (get().setId === setId) set({ size: { w: a.w ?? 0, h: a.h ?? 0 } }) }
    catch (e) { toast(`The set's picture: ${detail(e)}`) }
    await get().loadShadows()
  },
  loadShadows: async () => {
    const { setId } = get()
    const sid = stageId()
    const things = useStage.getState().current?.objects.find((o) => o.id === setId)?.things ?? []
    if (!setId || !sid || !things.some((t) => !t.mesh_asset_id)) { set({ shadows: null }); return }
    try {
      const b = new Uint8Array(await api.getBytes(`/stages/${sid}/sets/${setId}/things/shadows`))
      if (get().setId === setId) set({ shadows: b.some((v) => v > 127) ? b : null })
    } catch (e) { toast(`The things' shadows: ${detail(e)}`) }
  },
  setMode: (m) => set({ mode: m }),
  addPoint: async (x, y, label) => {
    const { setId, points } = get()
    const sid = stageId()
    if (!setId || !sid) return
    const next = [...points, { x: Math.round(x), y: Math.round(y), label }]
    set({ points: next })
    if (!next.some((p) => p.label === 1)) return                                     // SAM 3 needs a point on the thing first
    try {
      const r = await unwrap(http.POST('/stages/{st_id}/sets/{set_id}/things/find', { params: { path: { st_id: sid, set_id: setId } }, body: { points: next } }))
      set({ job: r.job_id, docId: r.document_id })
    } catch (e) { toast(`Find the thing: ${detail(e)}`) }
  },
  clear: () => set({ points: [], mask: null, job: null }),
  keep: async (name) => {
    const { setId, points, mask } = get()
    const sid = stageId()
    if (!setId || !sid || !mask) return false
    await useStage.getState().flush()
    try {
      await unwrap(http.POST('/stages/{st_id}/sets/{set_id}/things', { params: { path: { st_id: sid, set_id: setId } }, body: { name, points } }))
      set({ points: [], mask: null })
      await reload()
      void get().loadShadows()
      return true
    } catch (e) { toast(`Keep the thing: ${detail(e)}`); return false }
  },
  rename: async (setId, thingId) => {
    const sid = stageId()
    const t = useStage.getState().current?.objects.find((o) => o.id === setId)?.things?.find((x) => x.id === thingId)
    if (!sid || !t) return
    const name = await askText({ title: 'Rename the thing', initial: t.name, okLabel: 'Rename' })
    if (!name?.trim() || name.trim() === t.name) return
    await useStage.getState().flush()
    try { await unwrap(http.PATCH('/stages/{st_id}/sets/{set_id}/things/{thing_id}', { params: { path: { st_id: sid, set_id: setId, thing_id: thingId } }, body: { name: name.trim() } })); await reload() }
    catch (e) { toast(`Rename: ${detail(e)}`) }
  },
  remove: async (setId, thingId) => {
    const sid = stageId()
    if (!sid) return
    await useStage.getState().flush()
    try { await unwrap(http.DELETE('/stages/{st_id}/sets/{set_id}/things/{thing_id}', { params: { path: { st_id: sid, set_id: setId, thing_id: thingId } } })); await reload(); if (get().setId === setId) void get().loadShadows() }
    catch (e) { toast(`Remove: ${detail(e)}`) }
  },
  make: async (setId) => {
    const sid = stageId()
    if (!sid) return
    await useStage.getState().flush()
    try {
      const r = await unwrap(http.POST('/stages/{st_id}/sets/{set_id}/things/make', { params: { path: { st_id: sid, set_id: setId } } }))
      set({ making: [r.clean_job_id] })                                        // the rebuild and the models follow the Fill (its result names them)
      toast(`Making ${r.models.length} thing${r.models.length === 1 ? '' : 's'}: the plate cleaned first (with their shadows${r.shadows ? `, ${(r.shadows * 100).toFixed(1)} % of the picture` : ': none found'}), then a 3D model of each (≈ ${r.models.length * 5 + 1} min) — the stage follows as they land`, 'info')
    } catch (e) { toast(`Make the things: ${detail(e)}`) }
  },
}))

// the find landed: its mask is the set's document's selection, read as raw grey bytes
useSession.subscribe((s, prev) => {
  if (s.jobs === prev.jobs) return
  const t = useThings.getState()
  if (t.job) {
    const j = s.jobs[t.job]
    if (j && j.status !== 'queued' && j.status !== 'running') {
      useThings.setState({ job: null })
      if (j.status === 'done' && t.docId) {
        const doc = t.docId
        void api.getBytes(`/documents/${doc}/selection`).then((b) => { if (useThings.getState().docId === doc) useThings.setState({ mask: new Uint8Array(b) }) })
          .catch((e) => toast(`The mask: ${detail(e)}`))
      } else if (j.status !== 'done') toast(`Find the thing ${j.status}: ${j.error ?? ''}`)
    }
  }
  // the make: each landing job reloads the stage (what the Fill queues when it lands — the rebuild, then the models — joins the list)
  if (t.making.length) {
    let changed = false
    const left: string[] = []
    for (const id of t.making) {
      const j = s.jobs[id]
      if (!j || j.status === 'queued' || j.status === 'running') { left.push(id); continue }
      changed = true
      const r = j.result as { next_job_id?: string; next_job_ids?: string[] } | null
      left.push(...(r?.next_job_ids ?? (r?.next_job_id ? [r.next_job_id] : [])))
      if (j.status !== 'done') toast(`${j.kind === 'image_to_mesh' ? 'A thing\'s model' : j.kind === 'inpaint' ? 'The clean plate' : 'The set\'s rebuild'} ${j.status}: ${j.error ?? ''}`)
    }
    if (changed) {
      useThings.setState({ making: left })
      void reload()
      if (!left.length) toast('The things are made: the clean plate under them, each a model standing where it stood', 'success')
    }
  }
})
