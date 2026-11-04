// C0 (D181, propo02 04 §4.3): Clay's own view state — the rail (Library · Scenes), the Library's kind and the asset open on it (a World
// entity version, its 3D made here: the body, the prop's model, the place's set), the bench in place of the tiles, and the scene open
// in the editor with where *← Back* goes (the shot it was opened from). The place is kept in the hash: #clay/library/<kind>/<profile>/
// <version>[/bench] and #clay/scene/<stage>. The entity is the Story store's selection (the builders' commands act on it), the scene the
// stage store's open stage (loaded on demand: three.js stays out of the layer until the editor shows).
import { create } from 'zustand'
import { useEffect, useState } from 'react'
import { http, unwrap } from '../../api/client'
import type { StageDoc } from '../../api/types'
import { navigate, onNavigate } from '../../frame/router'
import { useSession } from '../../store/session'
import { useStory, type ProfileClass } from '../../suites/story/storyStore'
import type { AnimRef } from '../../suites/stage/animationBench'

export type ClayRail = 'library' | 'scenes'
export type LibKind = 'figure' | 'prop' | 'set' | 'light' | 'camera' | 'animation'
export const KINDS: { id: LibKind; label: string; one: string; cls: ProfileClass | null }[] = [
  { id: 'figure', label: 'Figures', one: 'figure', cls: 'character' }, { id: 'prop', label: 'Props', one: 'prop', cls: 'prop' }, { id: 'set', label: 'Sets', one: 'set', cls: 'place' },
  { id: 'light', label: 'Lights', one: 'light', cls: null }, { id: 'camera', label: 'Cameras', one: 'camera', cls: null }, { id: 'animation', label: 'Animations', one: 'animation', cls: null },
]
export const kindOfClass = (cls: ProfileClass): LibKind => (cls === 'character' ? 'figure' : cls === 'prop' ? 'prop' : 'set')
export const classOfKind = (k: LibKind): ProfileClass | null => KINDS.find((x) => x.id === k)?.cls ?? null
const isKind = (x: string | undefined): x is LibKind => KINDS.some((k) => k.id === x)

export interface ClayPlace { rail: ClayRail; kind: LibKind; profile: string | null; version: string | null; bench: boolean; stage: string | null; anim: AnimRef | null }
/** The hash's Clay place: #clay/library/<kind>/<profile>/<version>/bench, #clay/scene/<stage> (the parts optional). */
export function placeOfHash(hash: string): ClayPlace | null {
  const [layer, rail, a, b, c, d] = hash.replace(/^#/, '').split('/')
  if (layer !== 'clay') return null
  if (rail === 'scene') return { rail: 'scenes', kind: 'figure', profile: null, version: null, bench: false, stage: a || null, anim: null }
  const kind = isKind(a) ? a : 'figure'
  if (kind === 'animation') {                                                       // D182 (C2b): #clay/library/animation/anm/<id> · /clip/<file>/<clip>
    const anim: AnimRef | null = b === 'anm' && c ? { kind: 'template', id: c } : b === 'clip' && c && d ? { kind: 'clip', file: c, clip: decodeURIComponent(d) } : null
    return { rail: 'library', kind, profile: null, version: null, bench: false, stage: null, anim }
  }
  const bench = b === 'bench' || c === 'bench' || d === 'bench'
  return { rail: 'library', kind, profile: b && b !== 'bench' ? b : null, version: c && c !== 'bench' ? c : null, bench, stage: null, anim: null }
}
const writeHash = (h: string): void => { if (location.hash !== h) history.replaceState(null, '', `${location.pathname}${location.search}${h}`) }
const libraryHash = (kind: LibKind, asset: { profile: string; version: string } | null, bench: boolean): string =>
  `#clay/library/${kind}${asset ? `/${asset.profile}/${asset.version}` : ''}${bench ? '/bench' : ''}`
const animHash = (a: AnimRef): string => (a.kind === 'template' ? `#clay/library/animation/anm/${a.id}` : `#clay/library/animation/clip/${a.file}/${encodeURIComponent(a.clip)}`)

/** A scene's shots: the shots whose current version is a camera on the stage (the storyboard's names). */
export function shotsOnStage<T extends { id: string; name: string; current: string; versions: { id: string; stage_id?: string | null }[] }>(stageId: string, shots: T[]): T[] {
  return shots.filter((s) => (s.versions.find((v) => v.id === s.current) ?? s.versions[0])?.stage_id === stageId)
}

export interface From { shot: string; version: string; camera: string | null; record?: boolean }   // C3: opened to record (Record mode at once)

interface ClayState {
  rail: ClayRail
  kind: LibKind
  asset: { profile: string; version: string } | null            // the Library asset open: a World entity version
  view: 'page' | 'bench' | 'animation'                           // the asset's page (its tiles behind it), Clay opened for it (D142's bench, the line-up), or the animation bench (D182)
  animation: AnimRef | null                                      // D182 (C2b): the animation on the bench
  animSel: AnimRef | null                                        // D182: the animation a tile's right-click acts on
  from: From | null                                              // the shot the scene was opened from (← Back to the shot)
  setRail: (rail: ClayRail) => void
  setKind: (kind: LibKind) => void
  /** The Library on a kind, and on an entity version when named (the Story store's selection follows: the builders act on it). */
  openLibrary: (kind: LibKind, profile?: string | null, version?: string | null) => void
  /** D142 → C0: Clay opened for the asset (its figure, its model beside a 1.75 m figure, its set from the picture's camera), in the centre. */
  openBench: () => Promise<void>
  /** CW5 → C0: the kind's entities side by side at their sizes (the open one first, twelve at most). */
  openLineup: () => Promise<void>
  closeBench: () => void
  /** D182 (C2b): an animation opened on the animation bench (a figure playing it as its one block), and the way back to the tiles. */
  openAnimation: (ref: AnimRef) => Promise<void>
  closeAnimation: () => void
  selectAnimation: (ref: AnimRef | null) => void
  /** The editor on a scene (the stage), through the shot's camera when opened from a shot; `from` left out keeps the way back it had. */
  openScene: (stageId: string, from?: From | null) => Promise<void>
  backToShot: () => Promise<void>
}

export const useClay = create<ClayState>()((set, get) => ({
  rail: placeOfHash(location.hash)?.rail ?? 'library', kind: placeOfHash(location.hash)?.kind ?? 'figure', asset: null, view: 'page', animation: null, animSel: null, from: null,
  setRail: (rail) => {
    if (rail === 'library') { get().openLibrary(get().kind, get().asset?.profile, get().asset?.version); return }
    if (get().view === 'animation') get().closeAnimation()
    set({ rail, view: 'page' })
    navigate({ suite: 'stage' })
    void import('../../suites/stage/stageStore').then((m) => writeHash(`#clay/scene${m.useStage.getState().current?.id ? `/${m.useStage.getState().current!.id}` : ''}`))
  },
  setKind: (kind) => get().openLibrary(kind),
  openLibrary: (kind, profile = null, version = null) => {
    const st = useStory.getState()
    const cls = classOfKind(kind)
    const p = profile ? st.profiles.find((x) => x.id === profile) : undefined
    if (p && p.cls !== cls) { get().openLibrary(kindOfClass(p.cls), profile, version); return }   // the entity's own kind
    if (p) st.selectProfile(p.id, version ?? p.current)
    const asset = p ? { profile: p.id, version: useStory.getState().versionId ?? p.current } : null
    if (get().view === 'animation') void import('../../suites/stage/animationBench').then((m) => m.closeAnimationBench())
    set({ rail: 'library', kind, asset, view: 'page', animation: null })
    navigate({ suite: 'story', tab: 'cast', layer: 'clay' })                        // the builders' commands (cast.*, story.cast.*) are in reach
    writeHash(libraryHash(kind, asset, false))
  },
  openBench: async () => {
    const a = get().asset
    const st = useStory.getState()
    const p = a ? st.profiles.find((x) => x.id === a.profile) : st.profile()
    if (!p) return
    const version = a?.version ?? st.versionId ?? p.current
    if (!a) get().openLibrary(kindOfClass(p.cls), p.id, version)
    const m = await import('../../suites/stage/stageStore')
    if (await m.st().openBench(p.id, version, 'clay', () => get().closeBench())) { set({ view: 'bench' }); writeHash(libraryHash(get().kind, get().asset, true)) }
  },
  openLineup: async () => {
    const cls = classOfKind(get().kind)
    if (!cls || cls === 'place') return
    const st = useStory.getState(), here = get().asset?.profile ?? null
    const all = st.profiles.filter((p) => p.cls === cls && (p.cls === 'character' || !!p.versions.find((v) => v.id === p.current)?.model_asset_id))
    const items = [...all.filter((p) => p.id === here), ...all.filter((p) => p.id !== here)].slice(0, 12).map((p) => ({ profile_id: p.id }))
    if (!items.length) return
    const m = await import('../../suites/stage/stageStore')
    if (await m.st().openLineup(items, () => get().closeBench(), 'clay')) { set({ view: 'bench' }); writeHash(libraryHash(get().kind, get().asset, true)) }
  },
  closeBench: () => {
    if (get().view !== 'bench') return
    set({ view: 'page' })
    navigate({ suite: 'story', tab: 'cast', layer: 'clay' })
    writeHash(libraryHash(get().kind, get().asset, false))
  },
  openAnimation: async (ref) => {
    set({ rail: 'library', kind: 'animation', asset: null, view: 'animation', animation: ref, animSel: ref })
    const m = await import('../../suites/stage/animationBench')
    if (!(await m.openAnimationBench(ref))) { set({ view: 'page', animation: null }); return }
    navigate({ suite: 'stage', layer: 'clay' })
    writeHash(animHash(ref))
  },
  closeAnimation: () => {
    if (get().view !== 'animation') return
    void import('../../suites/stage/animationBench').then((m) => m.closeAnimationBench())
    set({ view: 'page', animation: null })
    navigate({ suite: 'story', tab: 'cast', layer: 'clay' })
    writeHash(libraryHash('animation', null, false))
  },
  selectAnimation: (animSel) => set({ animSel }),
  openScene: async (stageId, from) => {
    set({ rail: 'scenes', view: 'page', ...(from !== undefined ? { from } : {}) })
    const m = await import('../../suites/stage/stageStore')
    const sg = m.useStage.getState()
    if (sg.current?.id !== stageId) await sg.open(stageId)
    if (from?.camera) { m.useStage.getState().setActiveCamera(from.camera); m.useStage.getState().setView('camera') }   // 04 §3: the shot's camera by default
    if (from?.record) m.useStage.getState().setMode('record')                                                              // C3: Record again ▸ from the shot's row
    navigate({ suite: 'stage' })
    writeHash(`#clay/scene/${stageId}`)
  },
  backToShot: async () => {
    const f = get().from
    if (!f) return
    const { useShots } = await import('../shots/shotsStore')
    useShots.getState().open(f.shot)
  },
}))

/** The scene open in the editor, read without loading the stage store into the layer: null until it is. */
export function useOpenScene(): Pick<StageDoc, 'id' | 'name' | 'purpose' | 'objects' | 'cameras' | 'range' | 'size' | 'length'> | null {
  const [doc, setDoc] = useState<StageDoc | null>(null)
  useEffect(() => {
    let live = true, off: (() => void) | undefined
    void import('../../suites/stage/stageStore').then(({ useStage }) => {
      if (!live) return
      setDoc(useStage.getState().current)
      off = useStage.subscribe((x, p) => { if (x.current !== p.current) setDoc(x.current) })
    })
    return () => { live = false; off?.() }
  }, [])
  return doc
}

export type SceneLite = { id: string; name: string; purpose: string; objects: number; cameras: number; range: { start: number; end: number }; fps: number }
/** The project's scenes (the stages that are no bench): read when the Scenes rail opens, again when one is made or renamed. */
export function useScenes(on: boolean): SceneLite[] {
  const [list, setList] = useState<SceneLite[]>([])
  const tick = useSession((s) => s.project?.path)
  useEffect(() => {
    if (!on) return
    let live = true
    const read = () => void unwrap(http.GET('/stages')).then((r) => { if (live) setList((r.items as StageDoc[]).filter((s) => (s.purpose ?? 'stage') === 'stage')
      .map((s) => ({ id: s.id, name: s.name, purpose: s.purpose ?? 'stage', objects: s.objects.length, cameras: s.cameras.length, range: { start: s.range?.start ?? 0, end: s.range?.end ?? 120 }, fps: s.size?.fps ?? 24 }))) }).catch(() => undefined)
    read()
    let off: (() => void) | undefined
    void import('../../suites/stage/stageStore').then(({ useStage }) => { if (live) off = useStage.subscribe((x, p) => { if (x.stages !== p.stages || x.current?.name !== p.current?.name) read() }) })
    return () => { live = false; off?.() }
  }, [on, tick])
  return list
}

/** Mounted with the Clay layer: once a project is open, the records and the place from the hash; a navigation to the stage suite from
 *  elsewhere (*Open the stage*, a recipe node, a job's origin) lands on Scenes. Returns the cleanup. */
export function startClay(): () => void {
  let opened: string | null = null
  const go = () => {
    const pj = useSession.getState().project
    const path = pj?.open ? (pj as { path?: string }).path ?? 'open' : null
    if (!path || path === opened) return
    opened = path
    const from = placeOfHash(location.hash)
    void useStory.getState().loadProfiles().then(() => {
      const c = useClay.getState()
      if (from?.rail === 'scenes') { if (from.stage) void c.openScene(from.stage); else c.setRail('scenes'); return }
      if (from?.anim) { void c.openAnimation(from.anim); return }
      c.openLibrary(from?.kind ?? c.kind, from?.profile ?? null, from?.version ?? null)
      if (from?.bench) void c.openBench()
    })
  }
  const offSession = useSession.subscribe((s, prev) => { if (s.project !== prev.project) go() })
  go()
  const onHash = () => {                                                  // a deep link followed or typed
    const at = placeOfHash(location.hash), c = useClay.getState()
    if (!at || !opened) return
    if (at.rail === 'scenes') { if (at.stage) void c.openScene(at.stage); else if (c.rail !== 'scenes') c.setRail('scenes'); return }
    if (at.anim) { if (c.view !== 'animation' || JSON.stringify(c.animation) !== JSON.stringify(at.anim)) void c.openAnimation(at.anim); return }
    if (at.profile !== (c.asset?.profile ?? null) || at.kind !== c.kind || c.rail !== 'library' || (at.bench && c.view !== 'bench')) {
      c.openLibrary(at.kind, at.profile, at.version)
      if (at.bench) void c.openBench()
    }
  }
  window.addEventListener('hashchange', onHash)
  const offNav = onNavigate((p) => {                                       // the editor opened from anywhere shows under Scenes
    const c = useClay.getState()
    if (p.suite !== 'stage' || p.layer === 'clay' || c.view === 'bench' || c.view === 'animation' || c.rail === 'scenes') return
    useClay.setState({ rail: 'scenes', view: 'page' })
    void import('../../suites/stage/stageStore').then((m) => writeHash(`#clay/scene${m.useStage.getState().current?.id ? `/${m.useStage.getState().current!.id}` : ''}`))
  })
  return () => { offSession(); offNav(); window.removeEventListener('hashchange', onHash) }
}
