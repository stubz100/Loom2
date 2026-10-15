// 17 (D85): the Story suite's store — SY0: the world (L1 — logline, synopsis, styles, the spine's beats, the Flow's variables) with
// debounced saves that carry its revision (409 → reload, the last change lost and said so), the section the editor shows and the item
// the Inspector edits. SY1: the profiles (L2 — a character, place or prop with versions; a version's reference set is an album group,
// its candidates another), the selected version's pages, curation and Expand. Shots (SY2) and the flow (SY3) join here. Generate reads
// the styles for its picker (09 §3a) and the profiles for its @ picker (D73 / D85).
import { create } from 'zustand'
import { type ApiError, api, http, unwrap } from '../../api/client'
import type { Clip, FlowGraph, FlowNode, FlowProblem, GroupPage, Job, LoraRecord, Profile, ProfileVersion, Shot, ShotVersion, StoryBeat, StoryVariable, VoiceRecord, World, WorldStyle } from '../../api/types'
import { useSession } from '../../store/session'
import { startPlay, stepPlay, type PlayState } from './flow/play'

export type Section = 'logline' | 'synopsis' | 'styles' | 'spine' | 'variables'
export type Selection = { kind: 'style' | 'beat' | 'variable'; id: string } | null   // a variable's id is its name
export type ProfileClass = Profile['cls']
export const SECTIONS: { id: Section; label: string }[] = [
  { id: 'logline', label: 'Logline' }, { id: 'synopsis', label: 'Synopsis' }, { id: 'styles', label: 'Styles' }, { id: 'spine', label: 'Spine' }, { id: 'variables', label: 'Variables' },
]
export const CLASS_LABEL: Record<ProfileClass, string> = { character: 'character', place: 'place', prop: 'prop' }

export interface TrainOpts { model_id: string | null; steps: number; rank: number; resolution: number; name: string; setting: string; stage: boolean }
const DEFAULT_TRAIN: TrainOpts = { model_id: null, steps: 1000, rank: 16, resolution: 512, name: '', setting: '', stage: true }
/** CN2 (19 §3b): a new voice — the draft tier's fixed Kokoro voice, or the cloning tier's reference clip with its transcript and the consent note. */
export type VoiceBody = { name: string; tier: 'draft' | 'cloning'; voice: string | null; language: string; reference_asset_id: string | null; reference_text: string; speaker: string; consent: string }
/** A voice's label in the pickers: its name, tier and (when not English) language. */
export function voiceLabel(v: { name: string; tier: string; language: string }): string {
  return `${v.name} · ${v.tier}${v.language !== 'English' ? ` · ${v.language}` : ''}`
}
/** The newest `tts` job that speaks a Flow line (the line's state in the Inspector). */
export function ttsJobFor(jobs: Record<string, Job>, nodeId: string, index: number): Job | undefined {
  type Items = { items?: { node_id?: string | null; index?: number | null }[] }
  return Object.values(jobs).filter((j) => j.kind === 'tts' && ((j.recipe as Items).items ?? []).some((it) => it.node_id === nodeId && it.index === index))
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))[0]
}
/** The newest training job of a profile version (the Inspector's state line; the verbs' `when`). */
export function latestTrainJob(jobs: Record<string, Job>, profileId: string, versionId: string): Job | undefined {
  return Object.values(jobs).filter((j) => j.kind === 'train_lora' && (j.recipe as { profile_id?: string }).profile_id === profileId && (j.recipe as { version?: string }).version === versionId)
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))[0]
}

export interface StoryState {
  world: World | null; loading: boolean; saving: boolean
  section: Section; selected: Selection
  // SY1 · Cast
  profiles: Profile[]; profilesLoaded: boolean
  profileId: string | null; versionId: string | null
  refPage: GroupPage | null; candPage: GroupPage | null; pagesFor: string | null
  /** LT2 (18 §3a / §3c): the project's trained LoRAs and the options the next training job runs with. */
  loras: LoraRecord[]
  trainOpts: TrainOpts
  loadLoras: () => Promise<void>
  setTrainOpts: (patch: Partial<TrainOpts>) => void
  train: () => Promise<{ job_id: string; trigger: string; model_id: string; staged: boolean } | null>
  deleteLora: (id: string) => Promise<void>
  useLora: (id: string) => Promise<void>
  requeueTrain: (jobId: string) => Promise<void>
  /** 18 §3h: the identity check — eight images with / without the LoRA, FaceSim against the hero (advisory). */
  checkLora: (id: string) => Promise<{ job_ids: string[] } | null>
  onLoraChanged: (data: { id?: string; profile_id?: string | null; deleted?: boolean } | null) => void
  /** CN2 (19 §3b): the project's voices, the Flow Inspector's fallback voice (lines whose speaker has none), the Cast Inspector's new-voice form. */
  voices: VoiceRecord[]
  voiceId: string | null
  voiceForm: boolean
  loadVoices: () => Promise<void>
  setVoiceId: (id: string | null) => void
  setVoiceForm: (open: boolean) => void
  createVoice: (body: VoiceBody) => Promise<VoiceRecord | null>
  deleteVoice: (id: string) => Promise<void>
  voiceLine: (nodeId: string, index: number) => Promise<void>
  voiceNode: (nodeId: string) => Promise<void>
  playLine: (assetId: string) => void
  castFilter: ProfileClass | 'all'; castSearch: string
  picked: string[]; expanding: boolean; busy: boolean
  // SY2 · Shots
  shots: Shot[]; shotsLoaded: boolean; shotId: string | null; shotVersionId: string | null
  clipsById: Record<string, Clip>; stagesLite: { id: string; name: string; revision: number }[]
  // SY3 · Flow
  flowNodes: Record<string, FlowNode>; flowGraph: FlowGraph | null; flowLoaded: boolean
  nodeId: string | null; problems: FlowProblem[] | null; play: PlayState | null; addAt: { x: number; y: number } | null
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
  patchProfile: (patch: { name?: string; cls?: ProfileClass; current?: string; voice_id?: string | null }) => Promise<void>
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
  // SY2 · Shots
  loadShots: () => Promise<void>
  selectShot: (id: string | null, version?: string | null) => void
  /** The clips the selected shot's versions and takes point at, and the stages' revisions (for the stale mark). */
  loadShotDetails: () => Promise<void>
  shot: () => Shot | undefined
  shotVersion: () => ShotVersion | undefined
  createShot: (name: string, src?: { stage_id?: string; camera_id?: string; clip_id?: string; frame_asset_id?: string }) => Promise<Shot | null>
  patchShot: (patch: { name?: string; current?: string; owner_node?: string | null }) => Promise<void>
  newShotVersion: () => Promise<void>
  finalizeShot: () => Promise<boolean>
  useTake: (kind: 'image' | 'clip', id: string) => Promise<void>
  deleteShot: () => Promise<void>
  /** Why the version cannot be finalized, or null (mirrors the server's gate: a clip at the project format's size). */
  finalizeWhy: (v: ShotVersion) => string | null
  /** The stage moved after the version's frame / clip was taken (advisory, loom R62). */
  shotStale: (v: ShotVersion) => boolean
  // SY3 · Flow
  loadFlow: () => Promise<void>
  selectNode: (id: string | null) => void
  setAddAt: (at: { x: number; y: number } | null) => void
  node: () => FlowNode | undefined
  addNode: (type: FlowNode['type'], title?: string, at?: { x: number; y: number } | null, extra?: { text?: string }) => Promise<FlowNode | null>
  patchNode: (id: string, patch: Partial<Pick<FlowNode, 'type' | 'title' | 'lines' | 'options' | 'cond' | 'set' | 'target' | 'text' | 'colour'>>) => Promise<void>
  deleteNode: (id: string) => Promise<void>
  duplicateNode: (id: string) => Promise<void>
  moveNodes: (positions: { id: string; x: number; y: number }[]) => void
  connect: (from: string, port: string, to: string) => Promise<void>
  disconnect: (from: string, port: string) => Promise<void>
  bindShot: (nodeId: string, shotId: string, version?: string | null) => Promise<void>
  unbindShot: (nodeId: string) => Promise<void>
  spawnShot: (nodeId: string, name: string) => Promise<void>
  validate: () => Promise<void>
  playStart: () => void
  playNext: (option?: string) => void
  playStop: () => void
  /** World: a Shot node made from a beat by hand (loom R55 — never synced). */
  nodeFromBeat: (beatId: string) => Promise<void>
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
// SY3: graph saves (positions, edges) go one after another, each with the index's revision; node saves likewise per node, coalesced
let graphChain: Promise<void> = Promise.resolve()
let graphPending = 0                                   // saves queued or running: no reload from the socket while one is pending
const nodeChains: Record<string, Promise<void>> = {}
const nodeQueued = new Set<string>()
let nodeSaving = 0

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
    loras: [], trainOpts: DEFAULT_TRAIN, voices: [], voiceId: null, voiceForm: false,
    castFilter: 'all', castSearch: '', picked: [], expanding: false, busy: false,
    shots: [], shotsLoaded: false, shotId: null, shotVersionId: null, clipsById: {}, stagesLite: [],
    flowNodes: {}, flowGraph: null, flowLoaded: false, nodeId: null, problems: null, play: null, addAt: null,
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
      if (data?.kind === 'shot') { void get().loadShots(); return }          // SY2: a take arrived, a finalize, a copy
      if (data?.kind === 'voice') { void get().loadVoices(); return }        // CN2: a voice made, changed, measured or deleted
      if (data?.kind === 'flow') { if (graphPending === 0 && nodeSaving === 0) void get().loadFlow(); return }   // SY3: a node or the index moved on the server (not while ours are pending)
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
      void get().loadLoras()                                                                     // LT2: the records the versions point at
      void get().loadVoices()                                                                    // CN2: the voices the speakers point at
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
    loadLoras: async () => {
      try { set({ loras: (await unwrap(http.GET('/story/loras'))).items }) } catch { set({ loras: [] }) }
    },
    setTrainOpts: (patch) => set({ trainOpts: { ...get().trainOpts, ...patch } }),
    train: async () => {
      const p = get().profile(); const v = get().version(); if (!p || !v) return null
      const o = get().trainOpts
      const caps = useSession.getState().capabilities?.train
      const model_id = o.model_id ?? caps?.bases.find((b) => b.health !== 'missing')?.model_id ?? null
      try {
        const r = await unwrap(http.POST('/story/profiles/{pid}/train', { params: { path: { pid: p.id } },
          body: { version: v.id, model_id, steps: o.steps, rank: o.rank, resolution: o.resolution, name: o.name, setting: o.setting, stage: o.stage } }))
        await get().loadProfiles()
        await useSession.getState().refreshAll()
        toast(r.staged ? `Training ${p.name} ${v.id} staged — release it when the rig is free (trigger ${r.trigger})` : `Training ${p.name} ${v.id} queued (trigger ${r.trigger})`, 'info')
        return r
      } catch (e) { toast(`Train: ${detail(e)}`); return null }
    },
    deleteLora: async (id) => {
      try {
        await unwrap(http.DELETE('/story/loras/{lid}', { params: { path: { lid: id } } }))
        await get().loadLoras(); await get().loadProfiles()
        toast('LoRA deleted — the version keeps its trigger', 'info')
      } catch (e) { toast(`Delete LoRA: ${detail(e)}`) }
    },
    useLora: async (id) => {                                                                     // 18 §5: Generate with the slot and the trigger
      const rec = get().loras.find((l) => l.id === id)
      if (!rec) { toast('that LoRA is not in the project'); return }
      const s = useSession.getState()
      const models = s.capabilities?.models ?? {}
      const { useGenerate } = await import('../generate/generateStore')
      const g = useGenerate.getState()
      const cur = g.panel.model_id
      const fits = (m: string) => models[m]?.base === rec.base && models[m]?.wired
      const model_id = fits(cur) ? cur : Object.keys(models).find(fits)
      if (!model_id) { toast(`no model of the ${rec.base} base is offered in this build`); return }
      const text = g.panel.text.includes(rec.trigger) ? g.panel.text : `${rec.trigger}, ${g.panel.text}`.replace(/, $/, '')
      g.set({ model_id, loras: [{ model_id: rec.id, strength: 1 }], prompt_mode: 'text', text })
      s.setSuite('generate')
      toast(`Generate: ${rec.name} in slot 1 with its trigger`, 'info')
    },
    checkLora: async (id) => {
      try {
        const r = await unwrap(http.POST('/story/loras/{lid}/check', { params: { path: { lid: id } } }))
        await useSession.getState().refreshAll()
        toast(`${r.job_ids.length} check images queued on ${r.model_id} — FaceSim against the hero as they land`, 'info')
        return r
      } catch (e) { toast(`Check: ${detail(e)}`); return null }
    },
    requeueTrain: async (jobId) => {
      try { await unwrap(http.POST('/jobs/{job_id}/requeue', { params: { path: { job_id: jobId } } })); await useSession.getState().refreshAll() }
      catch (e) { toast(`Resume: ${detail(e)}`) }
    },
    onLoraChanged: () => { void get().loadLoras(); void get().loadProfiles() },
    loadVoices: async () => {
      try { set({ voices: (await unwrap(http.GET('/story/voices'))).items }) } catch { set({ voices: [] }) }
    },
    setVoiceId: (id) => set({ voiceId: id }),
    setVoiceForm: (open) => set({ voiceForm: open }),
    createVoice: async (body) => {
      try {
        const r = await unwrap(http.POST('/story/voices', { body }))
        await get().loadVoices()
        const p = get().profile()
        if (p && p.cls === 'character' && !p.voice_id) await get().patchProfile({ voice_id: r.id })                // the character speaks with its first voice
        toast(`Voice ${r.name} added (${r.tier})`, 'info')
        return r
      } catch (e) { toast(`New voice: ${detail(e)}`); return null }
    },
    deleteVoice: async (id) => {
      try {
        await unwrap(http.DELETE('/story/voices/{vid}', { params: { path: { vid: id } } }))
        if (get().voiceId === id) set({ voiceId: null })
        await get().loadVoices(); await get().loadProfiles()
        toast('Voice deleted — its spoken lines stay in the Catalogue', 'info')
      } catch (e) { toast(`Delete voice: ${detail(e)}`) }
    },
    voiceLine: async (nodeId, index) => {                                                           // the speaker's voice, else the fallback picked under the lines
      try {
        const r = await unwrap(http.POST('/story/flow/nodes/{nid}/lines/{i}/voice', { params: { path: { nid: nodeId, i: index } }, body: { voice_id: get().voiceId, speed: 1, stage: false } }))
        await useSession.getState().refreshAll()
        const v = get().voices.find((x) => x.id === r.voice_ids[0])
        toast(`Line ${index + 1} queued${v ? ` — ${v.name} (${v.tier}${v.tier === 'cloning' ? ', the engine stops for it' : ''})` : ''}`, 'info')
      } catch (e) { toast(`Voice: ${detail(e)}`) }
    },
    voiceNode: async (nodeId) => {
      try {
        const r = await unwrap(http.POST('/story/flow/nodes/{nid}/voice', { params: { path: { nid: nodeId } }, body: { voice_id: get().voiceId, speed: 1, stage: false } }))
        await useSession.getState().refreshAll()
        toast(`${r.lines} line${r.lines === 1 ? '' : 's'} queued in ${r.job_ids.length} job${r.job_ids.length === 1 ? '' : 's'}`, 'info')
      } catch (e) { toast(`Voice all lines: ${detail(e)}`) }
    },
    playLine: (assetId) => {
      const a = new Audio(api.assetUrl(assetId))
      void a.play().catch(() => toast('Could not play the line'))
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
    // ---- SY2 · Shots
    loadShots: async () => {
      try {
        const r = await unwrap(http.GET('/story/shots'))
        set({ shots: r.items, shotsLoaded: true })
        const cur = get().shotId
        if (cur && !r.items.some((s) => s.id === cur)) set({ shotId: null, shotVersionId: null })
        else if (cur) { const s = r.items.find((x) => x.id === cur)!; if (!s.versions.some((v) => v.id === get().shotVersionId)) set({ shotVersionId: s.current }) }
        void get().loadShotDetails()
      } catch (e) { if ((e as ApiError).status !== 409) toast(`Shots: ${detail(e)}`) }
    },
    selectShot: (id, version) => {
      const s = id ? get().shots.find((x) => x.id === id) : undefined
      set({ shotId: s ? id : null, shotVersionId: s ? (version && s.versions.some((v) => v.id === version) ? version : s.current) : null })
      void get().loadShotDetails()
    },
    loadShotDetails: async () => {
      const s = get().shot()
      const want = new Set<string>()
      for (const v of s?.versions ?? []) { if (v.clip_id) want.add(v.clip_id); for (const t of v.takes) if (t.kind === 'clip') want.add(t.id) }
      const have = get().clipsById
      const missing = [...want].filter((id) => !have[id])
      try {
        const got = await Promise.all(missing.map((id) => unwrap(http.GET('/clips/{clip_id}', { params: { path: { clip_id: id } } })).catch(() => null)))
        const next = { ...get().clipsById }
        got.forEach((c, i) => { if (c) next[missing[i]] = c })
        const stages = await unwrap(http.GET('/stages')).catch(() => null)
        set({ clipsById: next, ...(stages ? { stagesLite: stages.items.map((x) => ({ id: x.id, name: x.name, revision: x.revision })) } : {}) })
      } catch { /* the board shows what it has */ }
    },
    shot: () => get().shots.find((s) => s.id === get().shotId),
    shotVersion: () => { const s = get().shot(); return s?.versions.find((v) => v.id === (get().shotVersionId ?? s.current)) },
    createShot: async (name, src) => {
      try {
        const s = await unwrap(http.POST('/story/shots', { body: { name, stage_id: src?.stage_id ?? null, camera_id: src?.camera_id ?? null, clip_id: src?.clip_id ?? null, frame_asset_id: src?.frame_asset_id ?? null } }))
        set({ shots: [s, ...get().shots.filter((x) => x.id !== s.id)] })
        get().selectShot(s.id)
        return s
      } catch (e) { toast(`Shot: ${detail(e)}`); return null }
    },
    patchShot: async (patch) => {
      const s = get().shot(); if (!s) return
      try {
        const next = await unwrap(http.PATCH('/story/shots/{sid}', { params: { path: { sid: s.id } }, body: { revision: s.revision, ...patch } as never }))
        set({ shots: get().shots.map((x) => (x.id === next.id ? next : x)) })
      } catch (e) {
        if ((e as ApiError).status === 409) { toast('The shot changed elsewhere — reloaded; your last change was not saved'); await get().loadShots() }
        else toast(`Shot not saved: ${detail(e)}`)
      }
    },
    newShotVersion: async () => {
      const s = get().shot(); if (!s) return
      try { const next = await unwrap(http.POST('/story/shots/{sid}/versions', { params: { path: { sid: s.id } } })); set({ shots: get().shots.map((x) => (x.id === next.id ? next : x)) }); get().selectShot(next.id, next.current) }
      catch (e) { toast(`New version: ${detail(e)}`) }
    },
    finalizeShot: async () => {
      const s = get().shot(); const v = get().shotVersion(); if (!s || !v) return false
      try {
        const next = await unwrap(http.POST('/story/shots/{sid}/versions/{vid}/finalize', { params: { path: { sid: s.id, vid: v.id } } }))
        set({ shots: get().shots.map((x) => (x.id === next.id ? next : x)) })
        toast(`${s.name} ${v.id} finalized`, 'info')
        return true
      } catch (e) { toast(`Finalize: ${detail(e)}`); return false }
    },
    useTake: async (kind, id) => {
      const s = get().shot(); const v = get().shotVersion(); if (!s || !v) return
      try {
        const next = await unwrap(http.POST('/story/shots/{sid}/versions/{vid}/take', { params: { path: { sid: s.id, vid: v.id } }, body: { kind, id, use: true } }))
        set({ shots: get().shots.map((x) => (x.id === next.id ? next : x)) })
        void get().loadShotDetails()
      } catch (e) { toast(`Take: ${detail(e)}`) }
    },
    deleteShot: async () => {
      const s = get().shot(); if (!s) return
      try { await unwrap(http.DELETE('/story/shots/{sid}', { params: { path: { sid: s.id } } })); set({ shots: get().shots.filter((x) => x.id !== s.id) }); get().selectShot(null) }
      catch (e) { toast(`Delete: ${detail(e)}`) }
    },
    finalizeWhy: (v) => {
      if (v.state === 'final') return null
      if (!v.clip_id) return 'no clip yet — animate the shot (Stage · Shot or Animate) and use the result as its clip'
      const c = get().clipsById[v.clip_id]
      const fmt = useSession.getState().project?.format
      if (!c) return `clip ${v.clip_id} is not loaded`
      if (fmt && (Math.abs(c.w - fmt.width) > 32 || Math.abs(c.h - fmt.height) > 32)) return `Draft ${c.w}×${c.h} — the format is ${fmt.width}×${fmt.height}; render Full in Animate`   // within the video grids (11 §3c)
      return null
    },
    shotStale: (v) => {
      if (!v.stage_id || v.stage_revision === null || v.stage_revision === undefined) return false
      const st = get().stagesLite.find((x) => x.id === v.stage_id)
      return !!st && st.revision > v.stage_revision
    },
    // ---- SY3 · Flow
    loadFlow: async () => {
      try {
        const r = await unwrap(http.GET('/story/flow'))
        const flowNodes: Record<string, FlowNode> = {}
        for (const n of r.nodes) flowNodes[n.id] = n
        set({ flowNodes, flowGraph: r.graph, flowLoaded: true, ...(get().nodeId && !flowNodes[get().nodeId!] ? { nodeId: null } : {}) })
      } catch (e) { if ((e as ApiError).status !== 409) toast(`Flow: ${detail(e)}`) }
    },
    selectNode: (nodeId) => set({ nodeId }),
    setAddAt: (addAt) => set({ addAt }),
    node: () => { const id = get().nodeId; return id ? get().flowNodes[id] : undefined },
    addNode: async (type, title, at, extra) => {
      const g = get().flowGraph
      const n0 = g?.nodes.length ?? 0
      const c = (await import('./storyCommands')).flowView.centre?.()
      const pos = at ?? get().addAt ?? (c ? { x: c.x - 110 + (n0 % 4) * 40, y: c.y - 40 + (n0 % 4) * 40 } : { x: 60 + (n0 % 6) * 240, y: 60 + Math.floor(n0 / 6) * 160 })   // the view's centre, stepped so new nodes do not stack
      set({ addAt: null })
      try {
        const n = await unwrap(http.POST('/story/flow/nodes', { body: { type, title: title ?? '', x: pos.x, y: pos.y, text: extra?.text ?? '', target: null } }))
        await get().loadFlow()
        set({ nodeId: n.id })
        return n
      } catch (e) { toast(`Node: ${detail(e)}`); return null }
    },
    patchNode: async (id, patch) => {
      const n = get().flowNodes[id]; if (!n) return
      set({ flowNodes: { ...get().flowNodes, [id]: { ...n, ...patch } as FlowNode } })               // at once; the save follows (one at a time per node, the latest state)
      await saveNode(get, set, id, !!(patch.type || patch.options))
    },
    deleteNode: async (id) => {
      try { await unwrap(http.DELETE('/story/flow/nodes/{nid}', { params: { path: { nid: id } } })); if (get().nodeId === id) set({ nodeId: null }); await get().loadFlow(); void get().loadShots() }
      catch (e) { toast(`Delete: ${detail(e)}`) }
    },
    duplicateNode: async (id) => {
      const n = get().flowNodes[id]; const p = get().flowGraph?.nodes.find((x) => x.id === id); if (!n) return
      const made = await get().addNode(n.type, n.title ? `${n.title} copy` : '', { x: (p?.x ?? 0) + 40, y: (p?.y ?? 0) + 40 }, { text: n.text })
      if (made) await get().patchNode(made.id, { lines: n.lines, options: n.options.map((o) => ({ ...o, id: `opt_${crypto.randomUUID().replace(/-/g, '').slice(0, 8)}` })), cond: n.cond, set: n.set, target: n.target, colour: n.colour })
    },
    moveNodes: (positions) => {
      const g = get().flowGraph; if (!g) return
      const byId = new Map(positions.map((p) => [p.id, p]))
      const nodes = g.nodes.map((p) => (byId.has(p.id) ? { ...p, x: byId.get(p.id)!.x, y: byId.get(p.id)!.y } : p))
      set({ flowGraph: { ...g, nodes } })
      saveGraph(get, set, { nodes })
    },
    connect: async (from, port, to) => {
      const g = get().flowGraph; if (!g) return
      const edges = [...g.edges.filter((e) => !(e.from === from && e.port === port)), { from, port, to }]
      set({ flowGraph: { ...g, edges } })
      saveGraph(get, set, { edges })
    },
    disconnect: async (from, port) => {
      const g = get().flowGraph; if (!g) return
      const edges = g.edges.filter((e) => !(e.from === from && e.port === port))
      set({ flowGraph: { ...g, edges } })
      saveGraph(get, set, { edges })
    },
    bindShot: async (nodeId, shotId, version) => {
      try { await unwrap(http.POST('/story/flow/nodes/{nid}/bind', { params: { path: { nid: nodeId } }, body: { shot_id: shotId, version: version ?? null } })); await Promise.all([get().loadFlow(), get().loadShots()]) }
      catch (e) { toast(`Bind: ${detail(e)}`) }
    },
    unbindShot: async (nodeId) => {
      try { await unwrap(http.POST('/story/flow/nodes/{nid}/unbind', { params: { path: { nid: nodeId } } })); await Promise.all([get().loadFlow(), get().loadShots()]) }
      catch (e) { toast(`Unbind: ${detail(e)}`) }
    },
    spawnShot: async (nodeId, name) => {
      try { await unwrap(http.POST('/story/flow/nodes/{nid}/shot', { params: { path: { nid: nodeId } }, body: { name } })); await Promise.all([get().loadFlow(), get().loadShots()]) }
      catch (e) { toast(`New shot: ${detail(e)}`) }
    },
    validate: async () => {
      try { const r = await unwrap(http.POST('/story/flow/validate')); set({ problems: r.problems }) }
      catch (e) { toast(`Validate: ${detail(e)}`) }
    },
    playStart: () => {
      const g = get().flowGraph; if (!g) return
      set({ play: startPlay(g, get().flowNodes, get().world?.variables ?? []) })
    },
    playNext: (option) => { const g = get().flowGraph; const p = get().play; if (!g || !p) return; set({ play: stepPlay(p, g, get().flowNodes, option) }) },
    playStop: () => set({ play: null }),
    nodeFromBeat: async (beatId) => {
      const b = get().world?.spine.find((x) => x.id === beatId); if (!b) return
      const made = await get().addNode('shot', b.title, null, { text: b.line })
      if (made) { const { setRailTab } = await import('../../frame/suiteRegistry'); setRailTab('story', 'flow') }
    },
  }
})

/** SY3: a node saved with its revision, one save at a time per node and never two queued — the save sends the node's latest local state, so
 *  keystrokes coalesce; a 409 reloads (the last change lost and said so). `ports`: the index is refreshed after, an edge may have gone. */
function saveNode(get: () => StoryState, set: (p: Partial<StoryState>) => void, id: string, ports: boolean): Promise<void> {
  if (nodeQueued.has(id)) return nodeChains[id]
  nodeQueued.add(id)
  nodeChains[id] = (nodeChains[id] ?? Promise.resolve()).then(async () => {
    nodeQueued.delete(id)
    const n = get().flowNodes[id]; if (!n) return
    nodeSaving += 1
    try {
      const { type, title, lines, options, cond, set: sets, target, text, colour } = n
      const next = await unwrap(http.PATCH('/story/flow/nodes/{nid}', { params: { path: { nid: id } }, body: { revision: n.revision, type, title, lines, options, cond, set: sets, target, text, colour } as never }))
      const cur = get().flowNodes[id]
      if (cur) set({ flowNodes: { ...get().flowNodes, [id]: { ...cur, revision: next.revision, updated_at: next.updated_at } } })
      if (ports) { const r = await unwrap(http.GET('/story/flow')); set({ flowGraph: r.graph }) }
    } catch (e) {
      if ((e as ApiError).status === 409) { toast('The node changed elsewhere — reloaded; your last change was not saved'); await get().loadFlow() }
      else toast(`Node not saved: ${detail(e)}`)
    } finally { nodeSaving -= 1 }
  })
  return nodeChains[id]
}

/** SY3: the index saved with its revision, one save at a time; a 409 reloads (the last change lost and said so). */
function saveGraph(get: () => StoryState, set: (p: Partial<StoryState>) => void, patch: { nodes?: FlowGraph['nodes']; edges?: FlowGraph['edges']; start?: string | null }): void {
  graphPending += 1
  graphChain = graphChain.then(async () => {
    const g = get().flowGraph; if (!g) { graphPending -= 1; return }
    try {
      void patch                                                                                   // the local index is the truth of what to send: later edits ride along
      const next = await unwrap(http.PUT('/story/flow/graph', { body: { revision: g.revision, nodes: g.nodes, edges: g.edges, start: g.start } as never }))
      const cur = get().flowGraph
      if (cur) set({ flowGraph: { ...cur, revision: next.revision, updated_at: next.updated_at, start: next.start } })     // only the revision moves: edits made meanwhile stay
    } catch (e) {
      if ((e as ApiError).status === 409) { toast('The flow changed elsewhere — reloaded; your last change was not saved'); await get().loadFlow() }
      else toast(`Flow not saved: ${detail(e)}`)
    } finally { graphPending -= 1 }
  })
}

/** Other suites' way in (Stage's "New shot from this camera", Animate's "Make a shot from this clip"): the shot is made, Story opens on it. */
export async function makeShotAndOpen(name: string, src: { stage_id?: string; camera_id?: string; clip_id?: string; frame_asset_id?: string }): Promise<void> {
  const [{ setRailTab }] = await Promise.all([import('../../frame/suiteRegistry')])
  const st = useStory.getState()
  if (!st.shotsLoaded) await st.loadShots()
  const s = await st.createShot(name, src)
  if (!s) return
  setRailTab('story', 'shots')
  useSession.getState().setSuite('story')
}

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
