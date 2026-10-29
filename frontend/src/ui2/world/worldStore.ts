// U3 (D157, proto01_UI2 03): World's own view state — the rail's class (or Look, Sketches), the version's bin, the selected creation and
// the role filter. The entity and its version are the Story store's selection (the records layer of today: profiles, their sheets, the
// add and hero routes), so World and the old Cast act on the same records. The place is kept in the hash: #world/<class>/<profile>/<version>.
import { create } from 'zustand'
import { navigate, onNavigate } from '../../frame/router'
import { http, unwrap } from '../../api/client'
import type { components } from '../../api/schema'
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

/** The hash's World place: #world/<rail>/<profile>/<version> (its parts optional). */
export function placeOfHash(hash: string): { rail: WorldRail; entity: string | null; version: string | null } | null {
  const [layer, rail, entity, version] = hash.replace(/^#/, '').split('/')
  if (layer !== 'world') return null
  const r = (['character', 'prop', 'place', 'look', 'sketches'] as const).find((x) => x === rail) ?? 'character'
  return { rail: r, entity: entity || null, version: version || null }
}
const writeHash = (rail: WorldRail, entity: string | null, version: string | null): void => {
  const h = `#world/${rail}${entity ? `/${entity}${version ? `/${version}` : ''}` : ''}`
  if (location.hash !== h) history.replaceState(null, '', `${location.pathname}${location.search}${h}`)
}

/** A creation passes the role filter (the chips over the grid). */
export function passes(it: Pick<BinItem, 'roles'>, f: RoleFilter): boolean {
  if (f === 'all') return true
  if (f === 'a_pose') return it.roles.some((r) => r === 'a_pose_front' || r === 'a_pose_back')
  if (f === 'reference') return it.roles.some((r) => r === 'reference' || r === 'hero')
  return it.roles.includes(f)
}

interface WorldState {
  rail: WorldRail; bin: VersionBin | null; binFor: string | null; loading: boolean; selected: string | null; filter: RoleFilter
  mode: 'make' | 'edit' | 'clay' | 'sheet'                                 // U3c: the left column's Make or the editor on a creation; U3f: the bench; B2a: the Sheet
  setMode: (mode: 'make' | 'edit' | 'clay' | 'sheet') => void
  free: { id: string; home: string | null; name: string } | null        // B2a (D159): an edit of a picture that is no entity's (a sketch, a take, an import): it saves beside it
  setRail: (rail: WorldRail) => void
  pick: (entity: string | null, version?: string | null) => void
  loadBin: () => Promise<void>
  select: (id: string | null) => void
  setFilter: (f: RoleFilter) => void
}

export const useWorld = create<WorldState>()((set, get) => ({
  rail: placeOfHash(location.hash)?.rail ?? 'character', bin: null, binFor: null, loading: false, selected: null, filter: 'all', mode: 'make', free: null,
  setMode: (mode) => set({ mode, ...(mode === 'edit' ? {} : { free: null }) }),
  setRail: (rail) => {
    set({ rail, selected: null, filter: 'all', ...(get().free ? { mode: 'make', free: null } : {}) })   // B2a: another rail ends a free edit
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
    const p = st.profile()
    if (get().mode === 'clay') navigate({ suite: 'generate' })                // U3f: off the bench, back to Make
    set({ selected: null, mode: 'make', bin: p ? get().bin : null, binFor: p ? get().binFor : null, ...(p ? { rail: p.cls } : {}) })
    writeHash(p ? p.cls : get().rail, p?.id ?? null, p ? useStory.getState().versionId : null)
    if (p) void get().loadBin()
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
      else w.setRail(from?.rail ?? w.rail)
    })
  }
  const offSession = useSession.subscribe((s, prev) => { if (s.project !== prev.project) go() })
  go()
  const onHash = () => {                                                  // a deep link followed or typed: #world/<class>/<profile>/<version>
    const at = placeOfHash(location.hash), st = useStory.getState()
    if (!at || !opened) return
    if (at.entity && (at.entity !== st.profileId || (at.version && at.version !== st.versionId))) useWorld.getState().pick(at.entity, at.version)
    else if (!at.entity && at.rail !== useWorld.getState().rail) useWorld.getState().setRail(at.rail)
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
    if (s.profiles !== prev.profiles || s.versionId !== prev.versionId || s.refPage !== prev.refPage || s.candPage !== prev.candPage) void useWorld.getState().loadBin()
  })
  return () => { offSession(); offStory(); offRecords(); offNav(); window.removeEventListener('hashchange', onHash) }
}
