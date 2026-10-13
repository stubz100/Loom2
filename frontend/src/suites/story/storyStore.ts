// 17 (D85): the Story suite's store — SY0: the world (L1 — logline, synopsis, styles, the spine's beats, the Flow's variables) with
// debounced saves that carry its revision (409 → reload, the last change lost and said so), the section the editor shows and the item
// the Inspector edits. SY1: the profiles (L2 — a character, place or prop with versions; a version's reference set is an album group,
// its candidates another), the selected version's pages, curation and Expand. Shots (SY2) and the flow (SY3) join here. Generate reads
// the styles for its picker (09 §3a) and the profiles for its @ picker (D73 / D85).
import { create } from 'zustand'
import { type ApiError, http, unwrap } from '../../api/client'
import type { GroupPage, Profile, ProfileVersion, StoryBeat, StoryVariable, World, WorldStyle } from '../../api/types'
import { useSession } from '../../store/session'

export type Section = 'logline' | 'synopsis' | 'styles' | 'spine' | 'variables'
export type Selection = { kind: 'style' | 'beat' | 'variable'; id: string } | null   // a variable's id is its name
export type ProfileClass = Profile['cls']
export const SECTIONS: { id: Section; label: string }[] = [
  { id: 'logline', label: 'Logline' }, { id: 'synopsis', label: 'Synopsis' }, { id: 'styles', label: 'Styles' }, { id: 'spine', label: 'Spine' }, { id: 'variables', label: 'Variables' },
]
export const CLASS_LABEL: Record<ProfileClass, string> = { character: 'character', place: 'place', prop: 'prop' }

export interface StoryState {
  world: World | null; loading: boolean; saving: boolean
  section: Section; selected: Selection
  // SY1 · Cast
  profiles: Profile[]; profilesLoaded: boolean
  profileId: string | null; versionId: string | null
  refPage: GroupPage | null; candPage: GroupPage | null; pagesFor: string | null
  castFilter: ProfileClass | 'all'; castSearch: string
  picked: string[]; expanding: boolean; busy: boolean
  load: () => Promise<void>
  flush: () => Promise<void>
  setSection: (s: Section) => void
  select: (s: Selection) => void
  /** A change to the world: applied at once, saved after 300 ms with the document's revision. */
  edit: (patch: Partial<Pick<World, 'logline' | 'synopsis' | 'styles' | 'default_style' | 'spine' | 'variables'>>) => void
  addStyle: (name?: string) => string
  setStyle: (id: string, patch: Partial<WorldStyle>) => void
  removeStyle: (id: string) => void
  setDefaultStyle: (id: string | null) => void
  addBeat: (title?: string) => string
  setBeat: (id: string, patch: Partial<StoryBeat>) => void
  removeBeat: (id: string) => void
  moveBeat: (id: string, delta: -1 | 1) => void
  addVariable: (name?: string) => string
  setVariable: (name: string, patch: Partial<StoryVariable>) => void
  removeVariable: (name: string) => void
  /** The selected item goes (a style, a beat or a variable). */
  removeSelected: () => void
  /** `story.changed` on the socket: another writer moved a record — reload when nothing of ours is pending. */
  onChanged: (data: { kind?: string; id?: string; revision?: number; deleted?: boolean } | null) => void
  /** `group.changed`: the selected version's pages follow. */
  onGroupChanged: (ids: string[]) => void
  // SY1 · Cast
  loadProfiles: () => Promise<void>
  selectProfile: (id: string | null, version?: string | null) => void
  loadPages: () => Promise<void>
  profile: () => Profile | undefined
  version: () => ProfileVersion | undefined
  createProfile: (name: string, cls: ProfileClass, hero?: string | null, stub?: string) => Promise<Profile | null>
  patchProfile: (patch: { name?: string; cls?: ProfileClass; current?: string }) => Promise<void>
  setStub: (stub: string) => void
  setHero: (assetId: string | null) => Promise<void>
  newVersion: () => Promise<void>
  lockVersion: () => Promise<void>
  deleteProfile: () => Promise<void>
  curate: (ids: string[], verdict: 'keep' | 'reject') => Promise<void>
  expand: (preset: string, seeds: number, tier: 'draft' | 'full') => Promise<{ batch_id: string; job_ids: string[]; cells: number } | null>
  pick: (id: string | null, additive?: boolean) => void
  setCastFilter: (f: ProfileClass | 'all') => void
  setCastSearch: (s: string) => void
}

const uid = (prefix: string) => `${prefix}_${crypto.randomUUID().replace(/-/g, '').slice(0, 8)}`
const EMPTY: World = { schema_version: 1, logline: '', synopsis: '', styles: [], default_style: null, spine: [], variables: [], revision: 0, created_at: '', updated_at: '' }
const toast = (text: string, kind: 'error' | 'info' = 'error') => useSession.getState().toast(text, kind)
const detail = (e: unknown) => (e as ApiError).detail ?? String(e)

let saveTimer: number | null = null
let saveSeq = 0

async function save(get: () => StoryState, set: (p: Partial<StoryState>) => void): Promise<void> {
  const cur = get().world
  if (!cur) return
  const seq = ++saveSeq
  set({ saving: true })
  try {
    const next = await unwrap(http.PUT('/story/world', { body: cur as never }))
    if (seq === saveSeq && get().world) set({ world: { ...get().world!, revision: next.revision, updated_at: next.updated_at } })
  } catch (e) {
    const err = e as ApiError
    if (err.status === 409) {
      toast('The world changed elsewhere — reloaded; your last change was not saved')
      await get().load()
    } else toast(`World not saved: ${err.detail ?? e}`)
  } finally { if (seq === saveSeq) set({ saving: false }) }
}

function schedule(get: () => StoryState, set: (p: Partial<StoryState>) => void): void {
  if (saveTimer) window.clearTimeout(saveTimer)
  saveTimer = window.setTimeout(() => { saveTimer = null; void save(get, set) }, 300)
}

// SY1: the stub saves after a pause, with the profile's revision
let stubTimer: number | null = null

export const useStory = create<StoryState>()((set, get) => {
  const edit: StoryState['edit'] = (patch) => { const w = get().world ?? EMPTY; set({ world: { ...w, ...patch } }); schedule(get, set) }
  const replaceProfile = (p: Profile) => set({ profiles: [p, ...get().profiles.filter((x) => x.id !== p.id)] })
  const patchWith = async (body: Record<string, unknown>): Promise<Profile | null> => {
    const p = get().profile()
    if (!p) return null
    try {
      const next = await unwrap(http.PATCH('/story/profiles/{pid}', { params: { path: { pid: p.id } }, body: { revision: p.revision, ...body } as never }))
      replaceProfile(next)
      return next
    } catch (e) {
      if ((e as ApiError).status === 409) { toast('The profile changed elsewhere — reloaded; your last change was not saved'); await get().loadProfiles() }
      else toast(`Profile not saved: ${detail(e)}`)
      return null
    }
  }
  return {
    world: null, loading: false, saving: false, section: 'logline', selected: null,
    profiles: [], profilesLoaded: false, profileId: null, versionId: null, refPage: null, candPage: null, pagesFor: null,
    castFilter: 'all', castSearch: '', picked: [], expanding: false, busy: false,
    load: async () => {
      set({ loading: true })
      try { set({ world: await unwrap(http.GET('/story/world')) }) }
      catch (e) { if ((e as ApiError).status !== 409) toast(`World: ${detail(e)}`); set({ world: null }) }
      finally { set({ loading: false }) }
    },
    flush: async () => { if (saveTimer) { window.clearTimeout(saveTimer); saveTimer = null; await save(get, set) } },
    setSection: (section) => set({ section }),
    select: (selected) => set({ selected }),
    edit,
    addStyle: (name) => {
      const w = get().world ?? EMPTY
      const id = uid('sty')
      const n = name?.trim() || `Style ${w.styles.length + 1}`
      edit({ styles: [...w.styles, { id, name: n, fragment: '', group_id: null }], default_style: w.default_style ?? (w.styles.length ? w.default_style : id) })
      set({ selected: { kind: 'style', id }, section: 'styles' })
      return id
    },
    setStyle: (id, patch) => { const w = get().world; if (w) edit({ styles: w.styles.map((s) => (s.id === id ? { ...s, ...patch } : s)) }) },
    removeStyle: (id) => {
      const w = get().world; if (!w) return
      edit({ styles: w.styles.filter((s) => s.id !== id), default_style: w.default_style === id ? null : w.default_style })
      if (get().selected?.id === id) set({ selected: null })
    },
    setDefaultStyle: (id) => edit({ default_style: id }),
    addBeat: (title) => {
      const w = get().world ?? EMPTY
      const id = uid('beat')
      edit({ spine: [...w.spine, { id, title: title?.trim() || `Beat ${w.spine.length + 1}`, line: '' }] })
      set({ selected: { kind: 'beat', id }, section: 'spine' })
      return id
    },
    setBeat: (id, patch) => { const w = get().world; if (w) edit({ spine: w.spine.map((b) => (b.id === id ? { ...b, ...patch } : b)) }) },
    removeBeat: (id) => { const w = get().world; if (!w) return; edit({ spine: w.spine.filter((b) => b.id !== id) }); if (get().selected?.id === id) set({ selected: null }) },
    moveBeat: (id, delta) => {
      const w = get().world; if (!w) return
      const i = w.spine.findIndex((b) => b.id === id), j = i + delta
      if (i < 0 || j < 0 || j >= w.spine.length) return
      const spine = [...w.spine]; const [b] = spine.splice(i, 1); spine.splice(j, 0, b)
      edit({ spine })
    },
    addVariable: (name) => {
      const w = get().world ?? EMPTY
      let n = name?.trim().replace(/[^A-Za-z0-9_]/g, '_') || `flag_${w.variables.length + 1}`
      if (/^\d/.test(n)) n = `_${n}`
      while (w.variables.some((v) => v.name === n)) n = `${n}_`
      edit({ variables: [...w.variables, { name: n, type: 'bool', values: [], default: false }] })
      set({ selected: { kind: 'variable', id: n }, section: 'variables' })
      return n
    },
    setVariable: (name, patch) => {
      const w = get().world; if (!w) return
      const vars = w.variables.map((v) => {
        if (v.name !== name) return v
        const next = { ...v, ...patch }
        if (next.type === 'enum') { if (!next.values.length) next.values = ['a', 'b']; if (typeof next.default !== 'string' || !next.values.includes(next.default)) next.default = next.values[0] }
        else { next.values = []; if (typeof next.default !== 'boolean') next.default = false }
        return next
      })
      edit({ variables: vars })
      if (patch.name && get().selected?.kind === 'variable' && get().selected?.id === name) set({ selected: { kind: 'variable', id: patch.name } })
    },
    removeVariable: (name) => { const w = get().world; if (!w) return; edit({ variables: w.variables.filter((v) => v.name !== name) }); if (get().selected?.id === name) set({ selected: null }) },
    removeSelected: () => {
      const s = get().selected; if (!s) return
      if (s.kind === 'style') get().removeStyle(s.id); else if (s.kind === 'beat') get().removeBeat(s.id); else get().removeVariable(s.id)
    },
    onChanged: (data) => {
      if (data?.kind === 'profile') {                                        // SY1: a profile moved on the server (an Expand's candidates page, a lock, a copy)
        if (stubTimer !== null) return
        void get().loadProfiles()
        return
      }
      if (data?.kind && data.kind !== 'world') return
      const w = get().world
      if (!w || saveTimer !== null || get().saving) return
      if (data?.revision !== undefined && data.revision <= w.revision) return
      void get().load()
    },
    onGroupChanged: (ids) => {
      const v = get().version()
      if (v && ids.some((g) => g === v.group_id || g === v.candidates_group_id)) void get().loadPages()
    },
    // ---- SY1 · Cast
    loadProfiles: async () => {
      try {
        const r = await unwrap(http.GET('/story/profiles'))
        set({ profiles: r.items, profilesLoaded: true })
        const cur = get().profileId
        if (cur && !r.items.some((p) => p.id === cur)) set({ profileId: null, versionId: null, refPage: null, candPage: null, pagesFor: null })
        else if (cur) {
          const p = r.items.find((x) => x.id === cur)!
          if (!p.versions.some((v) => v.id === get().versionId)) set({ versionId: p.current })
          void get().loadPages()
        }
      } catch (e) { if ((e as ApiError).status !== 409) toast(`Profiles: ${detail(e)}`) }
    },
    selectProfile: (id, version) => {
      const p = id ? get().profiles.find((x) => x.id === id) : undefined
      set({ profileId: p ? id : null, versionId: p ? (version && p.versions.some((v) => v.id === version) ? version : p.current) : null, picked: [] })
      if (p) void get().loadPages()
      else set({ refPage: null, candPage: null, pagesFor: null })
    },
    loadPages: async () => {
      const v = get().version()
      if (!v) { set({ refPage: null, candPage: null, pagesFor: null }); return }
      const key = `${get().profileId}/${v.id}`
      try {
        const [ref, cand] = await Promise.all([
          unwrap(http.GET('/groups/{gid}', { params: { path: { gid: v.group_id } } })),
          v.candidates_group_id ? unwrap(http.GET('/groups/{gid}', { params: { path: { gid: v.candidates_group_id } } })) : Promise.resolve(null),
        ])
        if (get().version()?.id === v.id && get().profileId === key.split('/')[0]) set({ refPage: ref, candPage: cand, pagesFor: key })
      } catch (e) { if ((e as ApiError).status !== 404) toast(`Reference set: ${detail(e)}`) }
    },
    profile: () => get().profiles.find((p) => p.id === get().profileId),
    version: () => { const p = get().profile(); return p?.versions.find((v) => v.id === (get().versionId ?? p.current)) },
    createProfile: async (name, cls, hero, stub) => {
      try {
        const p = await unwrap(http.POST('/story/profiles', { body: { name, cls, hero_asset_id: hero ?? null, stub: stub ?? '' } }))
        replaceProfile(p)
        get().selectProfile(p.id)
        return p
      } catch (e) { toast(`Profile: ${detail(e)}`); return null }
    },
    patchProfile: async (patch) => { await patchWith(patch) },
    setStub: (stub) => {
      const p = get().profile(); const v = get().version()
      if (!p || !v || v.state !== 'open') return
      replaceProfile({ ...p, versions: p.versions.map((x) => (x.id === v.id ? { ...x, stub } : x)) })
      if (stubTimer) window.clearTimeout(stubTimer)
      stubTimer = window.setTimeout(() => { stubTimer = null; void patchWith({ versions: [{ id: v.id, stub: get().version()?.stub ?? stub }] }) }, 400)
    },
    setHero: async (assetId) => { const v = get().version(); if (v) await patchWith({ versions: [{ id: v.id, hero_asset_id: assetId }] }) },
    newVersion: async () => {
      const p = get().profile(); if (!p) return
      set({ busy: true })
      try { const next = await unwrap(http.POST('/story/profiles/{pid}/versions', { params: { path: { pid: p.id } } })); replaceProfile(next); get().selectProfile(next.id, next.current) }
      catch (e) { toast(`New version: ${detail(e)}`) } finally { set({ busy: false }) }
    },
    lockVersion: async () => {
      const p = get().profile(); const v = get().version(); if (!p || !v) return
      set({ busy: true })
      try { replaceProfile(await unwrap(http.POST('/story/profiles/{pid}/versions/{vid}/lock', { params: { path: { pid: p.id, vid: v.id } } }))) }
      catch (e) { toast(`Lock: ${detail(e)}`) } finally { set({ busy: false }) }
    },
    deleteProfile: async () => {
      const p = get().profile(); if (!p) return
      try { await unwrap(http.DELETE('/story/profiles/{pid}', { params: { path: { pid: p.id } } })); set({ profiles: get().profiles.filter((x) => x.id !== p.id) }); get().selectProfile(null) }
      catch (e) { toast(`Delete: ${detail(e)}`) }
    },
    curate: async (ids, verdict) => {
      const p = get().profile(); const v = get().version(); if (!p || !v || !ids.length) return
      try {
        await unwrap(http.POST('/story/profiles/{pid}/versions/{vid}/curate', { params: { path: { pid: p.id, vid: v.id } }, body: { asset_ids: ids, verdict } }))
        set({ picked: get().picked.filter((i) => !ids.includes(i)) })
        await get().loadPages()
      } catch (e) { toast(`Curate: ${detail(e)}`) }
    },
    expand: async (preset, seeds, tier) => {
      const p = get().profile(); const v = get().version(); if (!p || !v) return null
      set({ expanding: true })
      try {
        const r = await unwrap(http.POST('/story/profiles/{pid}/expand', { params: { path: { pid: p.id } }, body: { version: v.id, preset, seeds_per_cell: seeds, tier, style_id: get().world?.default_style ?? null } }))
        await get().loadProfiles()
        toast(`${r.cells} jobs queued for ${p.name} ${v.id} — the candidates land on "${p.name} · ${v.id} · candidates"`, 'info')
        return r
      } catch (e) { toast(`Expand: ${detail(e)}`); return null } finally { set({ expanding: false }) }
    },
    pick: (id, additive) => {
      if (!id) { set({ picked: [] }); return }
      const cur = get().picked
      set({ picked: additive ? (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]) : [id] })
    },
    setCastFilter: (castFilter) => set({ castFilter }),
    setCastSearch: (castSearch) => set({ castSearch }),
  }
})

export const sy = () => useStory.getState()

/** D85: the style Generate carries — the panel's own choice, or the world's default when it has none; null = no style. */
export function styleFor(choice: string | null | undefined): string | null {
  if (choice !== undefined) return choice
  return useStory.getState().world?.default_style ?? null
}

/** The profiles Generate's @ picker offers (loaded on first ask). */
export function profilesForMentions(): Profile[] {
  const s = useStory.getState()
  if (!s.profilesLoaded) void s.loadProfiles()
  return s.profiles
}
