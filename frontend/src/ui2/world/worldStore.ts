// U3 (D157, proto01_UI2 03): World's own view state — the rail's class (or Look, Sketches), the version's bin, the selected creation and
// the role filter. The entity and its version are the Story store's selection (the records layer of today: profiles, their sheets, the
// add and hero routes), so World and the old Cast act on the same records. The place is kept in the hash: #world/<class>/<profile>/<version>.
import { create } from 'zustand'
import { currentPlace, navigate, onNavigate, settleSuite } from '../../frame/router'
import { http, unwrap } from '../../api/client'
import type { components } from '../../api/schema'
import type { GroupPage, Profile } from '../../api/types'
import { onRecords } from '../../store/records'
import { useSession } from '../../store/session'
import { useStory, type ProfileClass } from '../../suites/story/storyStore'
import { useLayer } from '../layers'

export type VersionBin = components['schemas']['VersionBin']
export type BinItem = components['schemas']['BinItem']
export type WorldRail = ProfileClass | 'look' | 'sketches'
export type RoleFilter = 'all' | 'hero' | 'reference' | 'a_pose' | 'set_picture' | 'model' | 'candidate'
export const CLASSES: ProfileClass[] = ['character', 'prop', 'place']
export const CLASS_LABEL: Record<ProfileClass, string> = { character: 'Characters', prop: 'Props', place: 'Places' }
export const ONE: Record<ProfileClass, string> = { character: 'character', prop: 'prop', place: 'place' }

/** RS1 (D197, proto02 01 §4.2): the parts of World's Clay mode — the entity's builder (a character's figure and shell, a prop's model, a
 *  place's set), a character's skeleton and its poses, and the bench's own things (its light, its camera). */
export type ClayTab = 'build' | 'skeleton' | 'poses' | 'bench'
const BENCH_TAB = { id: 'bench' as const, label: 'Bench', hint: "the bench's own things: its light, its camera" }
export const CLAY_TABS: Record<ProfileClass, { id: ClayTab; label: string; hint: string }[]> = {
  character: [{ id: 'build', label: 'Figure', hint: 'its sizes, the fit to the A-pose, the shell' }, { id: 'skeleton', label: 'Skeleton', hint: "the body's joints on the A-pose and the shell, its hands, its feet & legs" },
    { id: 'poses', label: 'Poses', hint: 'its own poses: pose the figure on the bench, pin what must stay, Save for the character' }, BENCH_TAB],
  prop: [{ id: 'build', label: 'Model', hint: 'its 3D model and its height' }, BENCH_TAB],
  place: [{ id: 'build', label: 'Set', hint: 'the set fitted from the set picture, its faces, its things, its life' }, BENCH_TAB],
}
const isTab = (x: string | undefined): x is ClayTab => x === 'build' || x === 'skeleton' || x === 'poses' || x === 'bench'
const hasTab = (cls: ProfileClass, tab: ClayTab): boolean => CLAY_TABS[cls].some((t) => t.id === tab)

/** The hash's World place: #world/<rail>/<profile>/<version>[/clay[/<part>]] (its parts optional). K74: a bare #world names no rail (null)
 *  — the layer's tab writes it, and World goes on where it was left, not at the first character. */
export function placeOfHash(hash: string): { rail: WorldRail | null; entity: string | null; version: string | null; clay?: ClayTab } | null {
  const [layer, rail, entity, version, mode, tab] = hash.replace(/^#/, '').split('/')
  if (layer !== 'world') return null
  const r = (['character', 'prop', 'place', 'look', 'sketches'] as const).find((x) => x === rail) ?? null
  const clay: ClayTab | null = r && entity && mode === 'clay' ? (isTab(tab) ? tab : 'build') : null
  return { rail: r, entity: r ? entity || null : null, version: r && entity ? version || null : null, ...(clay ? { clay } : {}) }
}

/** RS1: the entity version has something to stand on a bench — a character always (its figure), a prop its model, a place its built set. */
export function benchable(p: Pick<Profile, 'cls'> | undefined, v: { model_asset_id?: string | null; place_set?: unknown } | undefined): boolean {
  return !!p && !!v && (p.cls === 'character' || (p.cls === 'prop' && !!v.model_asset_id) || (p.cls === 'place' && !!v.place_set))
}

/** K83: what of the shown version its bin reads — the pages, the roles' pictures (bins.py version_bin); a typed sheet word changes none of it,
 *  and each keystroke read the bin again. */
export function binKey(p: Profile | undefined, vid: string | null): string {
  const v = p?.versions.find((x) => x.id === vid)
  if (!p || !v) return ''
  return JSON.stringify([p.id, p.cls, v.id, v.group_id, v.candidates_group_id, v.hero_asset_id, v.anim_ref_asset_id, v.anim_ref_back_asset_id, v.anim_ref_side_asset_id,
    v.hand_ref_asset_id, v.feet_ref_asset_id, v.shell_asset_id, v.model_asset_id, (v.place_set?.sources ?? []).map((x) => x.asset_id)])
}
const pageKey = (g: GroupPage | null): string => (g ? `${g.group.id}:${g.group.revision}:${g.group.updated_at}` : '')

/** K74: the editor's keys go with it — World's Make (a rail, an entity picked, a free edit closed) puts the suite back under World's own. */
function offEditor(): void {
  if (currentPlace().suite === 'edit') navigate({ suite: 'generate' })
}
const writeHash = (rail: WorldRail, entity: string | null, version: string | null): void => {
  const w = useWorld.getState()
  const clay = entity && version && w.mode === 'clay' ? `/clay${w.clayTab === 'build' ? '' : `/${w.clayTab}`}` : ''   // RS1: the Clay mode and its part
  const h = `#world/${rail}${entity ? `/${entity}${version ? `/${version}` : ''}` : ''}${clay}`
  if (location.hash !== h) history.replaceState(null, '', `${location.pathname}${location.search}${h}`)
}

/** A creation passes the role filter (the chips over the grid). */
export function passes(it: Pick<BinItem, 'roles'>, f: RoleFilter): boolean {
  if (f === 'all') return true
  if (f === 'a_pose') return it.roles.some((r) => r === 'a_pose_front' || r === 'a_pose_back' || r === 'a_pose_side' || r === 'hand_picture' || r === 'feet_picture')   // RG1: the rig's pictures
  if (f === 'reference') return it.roles.some((r) => r === 'reference' || r === 'hero')
  return it.roles.includes(f)
}

/** RS1: the suite under World's Clay — the stage's (the bench's tools and keys), or Story's Cast on Skeleton (the rig's commands). */
function clayPlace(tab: ClayTab): void {
  const away = useLayer.getState().layer !== 'world'                              // opened from another layer (a shot's cast, the Bin): World shows
  if (tab === 'skeleton') { if (away || currentPlace().suite !== 'story') navigate({ suite: 'story', tab: 'cast', layer: 'world' }) }
  else if (away || currentPlace().suite !== 'stage') navigate({ suite: 'stage', layer: 'world' })
}

/** RS1: the bench is in Clay's centre — on every part but Skeleton, and not on a place's Set: a place's bench is made once from its
 *  picture's camera and kept (D142), so it is opened when asked for (Bench), not while the set is still being fitted. */
export function benchShown(p: Pick<Profile, 'cls'> | undefined, v: { model_asset_id?: string | null; place_set?: unknown } | undefined, tab: ClayTab): boolean {
  return tab !== 'skeleton' && benchable(p, v) && !(p!.cls === 'place' && tab === 'build')
}

interface WorldState {
  rail: WorldRail; bin: VersionBin | null; binFor: string | null; loading: boolean; selected: string | null; filter: RoleFilter
  mode: 'make' | 'edit' | 'clay'                                          // U3c: Make or the editor on a creation; RS1 (D197): Clay — the entity's 3D, here again (D181's Library kinds are gone)
  setMode: (mode: 'make' | 'edit' | 'clay') => void
  clayTab: ClayTab                                                        // RS1: the part of Clay shown
  lineup: boolean                                                         // RS1: the bench shows the class's line-up, not the entity's own bench
  benchFor: string | null                                                 // RS1: the entity version whose bench the stage store holds (profile/version), 'lineup' for the line-up
  setClayTab: (tab: ClayTab) => void
  /** RS1: the entity's 3D — World on it, in Clay, on the part named (every old way into Clay's Library lands here). */
  openClay: (entity: string, version?: string | null, tab?: ClayTab) => void
  /** RS1: the bench stage of the entity shown opened in the stage store (made once and kept, D142), when it has something to stand on it. */
  ensureBench: () => Promise<void>
  /** RS1 (CW5): the class's characters or props side by side at their sizes (the one shown first, twelve at most), on the bench. */
  openLineup: () => Promise<void>
  free: { id: string; home: string | null; name: string } | null        // B2a (D159): an edit of a picture that is no entity's (a sketch, a take, an import): it saves beside it
  setRail: (rail: WorldRail) => void
  pick: (entity: string | null, version?: string | null) => void
  /** K74: World shown again (the layer's tab, a reload at #world): its own rail, entity and mode, as it was left. */
  resume: () => void
  loadBin: () => Promise<void>
  select: (id: string | null) => void
  setFilter: (f: RoleFilter) => void
}

export const useWorld = create<WorldState>()((set, get) => ({
  rail: placeOfHash(location.hash)?.rail ?? 'character', bin: null, binFor: null, loading: false, selected: null, filter: 'all', mode: 'make', free: null, clayTab: 'build', lineup: false, benchFor: null,
  setMode: (mode) => {
    const st = useStory.getState(), p = st.profile()
    if (mode === 'clay' && !p) return
    const tab = mode === 'clay' && p && !hasTab(p.cls, get().clayTab) ? 'build' : get().clayTab   // a part the class has
    set({ mode, clayTab: tab, lineup: false, ...(mode === 'edit' ? {} : { free: null }) })
    if (mode !== 'edit') offEditor()
    if (mode !== 'clay' && st.skeleton) st.setSkeleton(false)
    if (mode === 'clay') { clayPlace(tab); if (st.skeleton !== (tab === 'skeleton')) st.setSkeleton(tab === 'skeleton') }
    if (p && (get().rail === p.cls)) writeHash(p.cls, p.id, st.versionId)
  },
  setClayTab: (tab) => {
    const st = useStory.getState(), p = st.profile()
    if (!p || !hasTab(p.cls, tab)) return
    set({ mode: 'clay', clayTab: tab, lineup: false, free: null })
    if (st.skeleton !== (tab === 'skeleton')) st.setSkeleton(tab === 'skeleton')
    clayPlace(tab)
    writeHash(p.cls, p.id, st.versionId)
  },
  openClay: (entity, version = null, tab = 'build') => {
    const st = useStory.getState(), p = st.profiles.find((x) => x.id === entity)
    if (!p) return
    if (st.profileId !== p.id || (version && st.versionId !== version) || get().rail !== p.cls) get().pick(p.id, version)
    get().setClayTab(hasTab(p.cls, tab) ? tab : 'build')
  },
  ensureBench: async () => {
    const st = useStory.getState(), p = st.profile(), v = st.version()
    if (get().mode !== 'clay' || get().clayTab === 'skeleton' || get().lineup) return
    if (!p || !v || !benchShown(p, v, get().clayTab)) { set({ benchFor: null }); return }
    const key = `${p.id}/${v.id}`
    const m = await import('../../suites/stage/stageStore')
    const cur = m.useStage.getState().current
    if (get().benchFor === key && cur?.purpose === 'bench' && cur.bound?.profile_id === p.id) return
    set({ benchFor: null })
    if (!(await m.st().openBench(p.id, v.id, 'world', () => useWorld.getState().setClayTab('build')))) return
    const now = useStory.getState()
    if (`${now.profileId}/${now.versionId}` !== key || get().mode !== 'clay') return          // another entity picked meanwhile: its own effect opens its bench
    set({ benchFor: key })
    if (p.cls === 'character') {                                                              // the bound figure selected: Poses and the Inspector act on it
      const fig = m.useStage.getState().current?.objects.find((o) => o.kind === 'mannequin' && o.profile_id === p.id)
      if (fig && m.useStage.getState().selected !== fig.id) m.useStage.getState().select(fig.id)
    }
  },
  openLineup: async () => {
    const st = useStory.getState(), cls = get().rail
    if (cls !== 'character' && cls !== 'prop') return
    const here = st.profile()?.cls === cls ? st.profileId : null
    const all = st.profiles.filter((p) => p.cls === cls && (p.cls === 'character' || !!p.versions.find((v) => v.id === p.current)?.model_asset_id))
    const items = [...all.filter((p) => p.id === here), ...all.filter((p) => p.id !== here)].slice(0, 12).map((p) => ({ profile_id: p.id }))
    if (!items.length || !here) return
    const m = await import('../../suites/stage/stageStore')
    if (st.skeleton) st.setSkeleton(false)
    if (await m.st().openLineup(items, () => useWorld.getState().setClayTab('build'), 'world')) set({ mode: 'clay', clayTab: 'bench', lineup: true, benchFor: 'lineup', free: null })
  },
  setRail: (rail) => {
    const ends = !!get().free && rail !== get().rail
    const noClay = get().mode === 'clay' && (rail === 'look' || rail === 'sketches')            // RS1: Look and Sketches have no 3D
    set({ rail, selected: null, filter: 'all', lineup: false, ...(ends || noClay ? { mode: 'make', free: null } : {}) })   // B2a: another rail ends a free edit (the same one, as the place applied on opening, keeps it)
    if (noClay) { if (useStory.getState().skeleton) useStory.getState().setSkeleton(false); navigate({ suite: 'generate' }) }
    if (ends) offEditor()                                                                      // K74: a closed free edit left the editor's keys live
    const st = useStory.getState()
    const keep = st.profile()
    if (rail === 'look' || rail === 'sketches') { writeHash(rail, null, null); return }
    if (keep && keep.cls === rail) { writeHash(rail, keep.id, st.versionId); return }
    const first = st.profiles.find((p) => p.cls === rail)
    get().pick(first?.id ?? null)
  },
  pick: (entity, version = null) => {
    const st = useStory.getState()
    st.selectProfile(entity, version)
    const p = st.profile(), key = p ? `${p.id}/${useStory.getState().versionId}` : null
    const same = !!key && key === get().binFor, editing = get().mode === 'edit'
    const wasClay = get().mode === 'clay', clay = wasClay && !!p                                                  // RS1: Clay stays the mode; a part the class has not falls back to its builder
    const tab = clay && hasTab(p!.cls, get().clayTab) ? get().clayTab : 'build'
    set({ selected: null, mode: clay ? 'clay' : 'make', clayTab: tab, lineup: false, bin: same ? get().bin : null, binFor: same ? get().binFor : null, ...(p ? { rail: p.cls } : {}) })   // K96: another entity's bin is not shown meanwhile
    if (editing) offEditor()
    if (clay && st.skeleton !== (tab === 'skeleton')) st.setSkeleton(tab === 'skeleton')
    if (wasClay && !clay) navigate({ suite: 'generate' })                                      // no entity left for Clay: the bench's keys go with it
    writeHash(p ? p.cls : get().rail, p?.id ?? null, p ? useStory.getState().versionId : null)
    if (p) void get().loadBin()
  },
  resume: () => {
    const w = get(), st = useStory.getState(), p = st.profile()
    if (w.rail === 'look' || w.rail === 'sketches') { writeHash(w.rail, null, null); return }
    if (!p) { w.setRail(w.rail); return }                                                         // its entity went (or another project): the rail's first
    if (p.cls !== w.rail) { w.pick(p.id, st.versionId); return }                                  // Clay's Library or Shots picked another: World shows it
    writeHash(w.rail, p.id, st.versionId)                                                         // as it was left: the mode, the selection and the filter kept
    if (w.binFor !== `${p.id}/${st.versionId}`) void w.loadBin()
  },
  loadBin: async () => {
    const st = useStory.getState(), p = st.profile(), vid = st.versionId
    if (!p || !vid) { set({ bin: null, binFor: null }); return }
    const key = `${p.id}/${vid}`
    set({ loading: true })
    try {
      const bin = await unwrap(http.GET('/story/profiles/{pid}/versions/{vid}/bin', { params: { path: { pid: p.id, vid } } }))
      const now = useStory.getState()
      if (`${now.profileId}/${now.versionId}` === key) set({ bin, binFor: key })
    } catch (e) { useSession.getState().toast(`The bin could not be read: ${(e as { detail?: string }).detail ?? e}`, 'error') }
    finally { set({ loading: false }) }
  },
  select: (selected) => set({ selected }),
  setFilter: (filter) => set({ filter }),
}))

/** Mounted with the World layer: once a project is open (and again when another opens), the records, the place from the hash, and the bin
 *  following its version's pages. Returns the cleanup. */
export function startWorld(): () => void {
  let opened: string | null = null
  const go = () => {
    const pj = useSession.getState().project
    const path = pj?.open ? (pj as { path?: string }).path ?? 'open' : null
    if (!path || path === opened) return
    opened = path
    const from = placeOfHash(location.hash)
    void useStory.getState().load()                                         // the world record: the Look's styles
    void useStory.getState().loadProfiles().then(() => {
      const w = useWorld.getState()
      if (from?.entity && from.clay) w.openClay(from.entity, from.version, from.clay)   // RS1: a link into the entity's 3D
      else if (from?.entity) w.pick(from.entity, from.version)
      else if (from?.rail && from.rail !== w.rail) w.setRail(from.rail)
      else w.resume()                                                       // K74: a bare #world (the layer's tab) goes on where World was left
    })
  }
  if (useWorld.getState().mode !== 'edit' && currentPlace().suite === 'edit') settleSuite({ suite: 'generate' })   // K74: the editor's keys only with the editor shown
  const offSession = useSession.subscribe((s, prev) => { if (s.project !== prev.project) go() })
  go()
  const onHash = () => {                                                  // a deep link followed or typed: #world/<class>/<profile>/<version>
    const at = placeOfHash(location.hash), st = useStory.getState()
    if (!at || !opened) return
    const w = useWorld.getState()
    if (at.entity && at.clay && (at.entity !== st.profileId || (at.version && at.version !== st.versionId) || w.mode !== 'clay' || w.clayTab !== at.clay)) w.openClay(at.entity, at.version, at.clay)
    else if (at.entity && (at.entity !== st.profileId || (at.version && at.version !== st.versionId))) useWorld.getState().pick(at.entity, at.version)
    else if (!at.entity && at.rail && at.rail !== useWorld.getState().rail) useWorld.getState().setRail(at.rail)   // K74: a bare #world moves nothing
  }
  window.addEventListener('hashchange', onHash)
  const offNav = onNavigate((p) => {                                       // B2a: the editor opened from anywhere shows in World
    const w = useWorld.getState()
    if (p.suite !== 'edit' || w.mode === 'edit') return
    if (w.rail === 'look' || w.rail === 'sketches') useWorld.setState({ mode: 'edit', free: w.free ?? { id: '', home: null, name: 'imports' } })   // no entity: saved to Imports
    else w.setMode('edit')
  })
  const offRecords = onRecords('ui2.world.bin', ['group.changed', 'asset.deleted', 'asset.updated'], () => void useWorld.getState().loadBin())   // U1's bus: a creation landed or moved
  const offSkel = useStory.subscribe((s, prev) => {                      // RS1 (D190): Skeleton opened or closed by its own commands is Clay's part
    if (s.skeleton === prev.skeleton) return
    const w = useWorld.getState(), p = s.profile()
    if (s.skeleton && p?.cls === 'character' && (w.mode !== 'clay' || w.clayTab !== 'skeleton')) w.setClayTab('skeleton')
    else if (!s.skeleton && w.mode === 'clay' && w.clayTab === 'skeleton') w.setClayTab('build')
  })
  const offStory = useStory.subscribe((s, prev) => {                     // the version's pages changed (a hero, a reference, a new version)
    const pid = s.profileId, was = prev.profileId                          // K83: only what the bin reads — not a sheet keystroke, not a page read again unchanged
    if (binKey(s.profiles.find((x) => x.id === pid), s.versionId) !== binKey(prev.profiles.find((x) => x.id === was), prev.versionId)
      || pageKey(s.refPage) !== pageKey(prev.refPage) || pageKey(s.candPage) !== pageKey(prev.candPage)) void useWorld.getState().loadBin()
  })
  return () => { offSession(); offStory(); offSkel(); offRecords(); offNav(); window.removeEventListener('hashchange', onHash) }
}
