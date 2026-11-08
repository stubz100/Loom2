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

export type VersionBin = components['schemas']['VersionBin']
export type BinItem = components['schemas']['BinItem']
export type WorldRail = ProfileClass | 'look' | 'sketches'
export type RoleFilter = 'all' | 'hero' | 'reference' | 'a_pose' | 'set_picture' | 'model' | 'candidate'
export const CLASSES: ProfileClass[] = ['character', 'prop', 'place']
export const CLASS_LABEL: Record<ProfileClass, string> = { character: 'Characters', prop: 'Props', place: 'Places' }
export const ONE: Record<ProfileClass, string> = { character: 'character', prop: 'prop', place: 'place' }

/** The hash's World place: #world/<rail>/<profile>/<version> (its parts optional). K74: a bare #world names no rail (null) — the layer's
 *  tab writes it, and World goes on where it was left, not at the first character. */
export function placeOfHash(hash: string): { rail: WorldRail | null; entity: string | null; version: string | null } | null {
  const [layer, rail, entity, version] = hash.replace(/^#/, '').split('/')
  if (layer !== 'world') return null
  const r = (['character', 'prop', 'place', 'look', 'sketches'] as const).find((x) => x === rail) ?? null
  return { rail: r, entity: r ? entity || null : null, version: r && entity ? version || null : null }
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
  const h = `#world/${rail}${entity ? `/${entity}${version ? `/${version}` : ''}` : ''}`
  if (location.hash !== h) history.replaceState(null, '', `${location.pathname}${location.search}${h}`)
}

/** A creation passes the role filter (the chips over the grid). */
export function passes(it: Pick<BinItem, 'roles'>, f: RoleFilter): boolean {
  if (f === 'all') return true
  if (f === 'a_pose') return it.roles.some((r) => r === 'a_pose_front' || r === 'a_pose_back' || r === 'a_pose_side' || r === 'hand_picture' || r === 'feet_picture')   // RG1: the rig's pictures
  if (f === 'reference') return it.roles.some((r) => r === 'reference' || r === 'hero')
  return it.roles.includes(f)
}

interface WorldState {
  rail: WorldRail; bin: VersionBin | null; binFor: string | null; loading: boolean; selected: string | null; filter: RoleFilter
  mode: 'make' | 'edit'                                                   // U3c: the left column's Make or the editor on a creation (C0, D181: the bench and Build are Clay's Library)
  setMode: (mode: 'make' | 'edit') => void
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
  rail: placeOfHash(location.hash)?.rail ?? 'character', bin: null, binFor: null, loading: false, selected: null, filter: 'all', mode: 'make', free: null,
  setMode: (mode) => { set({ mode, ...(mode === 'edit' ? {} : { free: null }) }); if (mode !== 'edit') offEditor() },
  setRail: (rail) => {
    const ends = !!get().free && rail !== get().rail
    set({ rail, selected: null, filter: 'all', ...(ends ? { mode: 'make', free: null } : {}) })   // B2a: another rail ends a free edit (the same one, as the place applied on opening, keeps it)
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
    set({ selected: null, mode: 'make', bin: same ? get().bin : null, binFor: same ? get().binFor : null, ...(p ? { rail: p.cls } : {}) })   // K96: another entity's bin is not shown meanwhile
    if (editing) offEditor()
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
      if (from?.entity) w.pick(from.entity, from.version)
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
    if (at.entity && (at.entity !== st.profileId || (at.version && at.version !== st.versionId))) useWorld.getState().pick(at.entity, at.version)
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
  const offStory = useStory.subscribe((s, prev) => {                     // the version's pages changed (a hero, a reference, a new version)
    const pid = s.profileId, was = prev.profileId                          // K83: only what the bin reads — not a sheet keystroke, not a page read again unchanged
    if (binKey(s.profiles.find((x) => x.id === pid), s.versionId) !== binKey(prev.profiles.find((x) => x.id === was), prev.versionId)
      || pageKey(s.refPage) !== pageKey(prev.refPage) || pageKey(s.candPage) !== pageKey(prev.candPage)) void useWorld.getState().loadBin()
  })
  return () => { offSession(); offStory(); offRecords(); offNav(); window.removeEventListener('hashchange', onHash) }
}
