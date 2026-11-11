// C0 (D181, propo02 04 §4.3): Clay's own view state — the rail (Library · Scenes), the animation on the bench, and the scene open in the
// editor with where *← Back* goes (the shot it was opened from). RS1 (D197, proto02 01 §4.2): the Library holds the animations only — an
// entity's 3D (a character's body, shell and skeleton, a prop's model, a place's set) and its bench are World's Clay mode again
// (ui2/world/worldStore.ts); a link to the old pages (#clay/library/figure|prop|set/<profile>/<version>[/bench|/skeleton]) lands there.
// The place is kept in the hash: #clay/library, #clay/library/animation/anm/<id> and #clay/scene/<stage>. The scene is the stage store's
// open stage (loaded on demand: three.js stays out of the layer until the editor shows).
import { create } from 'zustand'
import { useEffect, useState } from 'react'
import { http, unwrap } from '../../api/client'
import type { StageDoc } from '../../api/types'
import { navigate, onNavigate } from '../../frame/router'
import { useSession } from '../../store/session'
import { useStory } from '../../suites/story/storyStore'
import type { AnimRef } from '../../suites/stage/animationBench'

export type ClayRail = 'library' | 'scenes'
/** RS1: the class of an old Library kind (a link from before the move). */
const OLD_KIND: Record<string, 'build'> = { figure: 'build', prop: 'build', set: 'build' }

export interface ClayPlace { rail: ClayRail; stage: string | null; anim: AnimRef | null
  /** RS1: an old Library link's entity — opened in World's Clay (on its bench or its skeleton when the link said so). */
  entity?: { profile: string; version: string | null; tab: 'build' | 'bench' | 'skeleton' } }
/** The hash's Clay place: #clay/library[/animation/anm/<id> | /animation/clip/<file>/<clip>], #clay/scene/<stage> (the parts optional). */
export function placeOfHash(hash: string): ClayPlace | null {
  const [layer, rail, a, b, c, d] = hash.replace(/^#/, '').split('/')
  if (layer !== 'clay') return null
  if (rail === 'scene') return { rail: 'scenes', stage: a || null, anim: null }
  if (a === 'animation') {                                                          // D182 (C2b): #clay/library/animation/anm/<id> · /clip/<file>/<clip>
    const anim: AnimRef | null = b === 'anm' && c ? { kind: 'template', id: c } : b === 'clip' && c && d ? { kind: 'clip', file: c, clip: decodeURIComponent(d) } : null
    return { rail: 'library', stage: null, anim }
  }
  const tail = [b, c, d], named = (x?: string) => (x && x !== 'bench' && x !== 'skeleton' ? x : null)
  const profile = a && OLD_KIND[a] ? named(b) : null
  return { rail: 'library', stage: null, anim: null,
    ...(profile ? { entity: { profile, version: named(c), tab: tail.includes('skeleton') ? 'skeleton' as const : tail.includes('bench') ? 'bench' as const : 'build' as const } } : {}) }
}
const writeHash = (h: string): void => { if (location.hash !== h) history.replaceState(null, '', `${location.pathname}${location.search}${h}`) }
const animHash = (a: AnimRef): string => (a.kind === 'template' ? `#clay/library/animation/anm/${a.id}` : `#clay/library/animation/clip/${a.file}/${encodeURIComponent(a.clip)}`)

/** A scene's shots: the shots whose current version is a camera on the stage (the storyboard's names). */
export function shotsOnStage<T extends { id: string; name: string; current: string; versions: { id: string; stage_id?: string | null }[] }>(stageId: string, shots: T[]): T[] {
  return shots.filter((s) => (s.versions.find((v) => v.id === s.current) ?? s.versions[0])?.stage_id === stageId)
}

export interface From { shot: string; version: string; camera: string | null; record?: boolean }   // C3: opened to record (Record mode at once)

interface ClayState {
  rail: ClayRail
  view: 'page' | 'animation'                                     // the animations' tiles, or the animation bench (D182)
  animation: AnimRef | null                                      // D182 (C2b): the animation on the bench
  animSel: AnimRef | null                                        // D182: the animation a tile's right-click acts on
  from: From | null                                              // the shot the scene was opened from (← Back to the shot)
  setRail: (rail: ClayRail) => void
  /** The Library: the animations' tiles. */
  openLibrary: () => void
  /** D182 (C2b): an animation opened on the animation bench (a figure playing it as its one block), and the way back to the tiles. */
  openAnimation: (ref: AnimRef) => Promise<void>
  closeAnimation: () => void
  selectAnimation: (ref: AnimRef | null) => void
  /** The editor on a scene (the stage), through the shot's camera when opened from a shot; `from` left out keeps the way back it had. */
  openScene: (stageId: string, from?: From | null, section?: 'still') => Promise<void>   // D186: `section` — the column section to land on (the Still's form)
  backToShot: () => Promise<void>
}

/** RS1: an entity's 3D is World's — the layer and the part (the dynamic import keeps World's store out of Clay's until a link needs it). */
export function openInWorld(profile: string, version: string | null, tab: 'build' | 'bench' | 'skeleton' | 'poses' = 'build'): void {
  void import('../world/worldStore').then((m) => m.useWorld.getState().openClay(profile, version, tab))
}

export const useClay = create<ClayState>()((set, get) => ({
  rail: placeOfHash(location.hash)?.rail ?? 'library', view: 'page', animation: null, animSel: null, from: null,
  setRail: (rail) => {
    if (rail === 'library') { get().openLibrary(); return }
    if (get().view === 'animation') get().closeAnimation()
    set({ rail, view: 'page' })
    navigate({ suite: 'stage' })
    void import('../../suites/stage/stageStore').then((m) => writeHash(`#clay/scene${m.useStage.getState().current?.id ? `/${m.useStage.getState().current!.id}` : ''}`))
  },
  openLibrary: () => {
    if (get().view === 'animation') void import('../../suites/stage/animationBench').then((m) => m.closeAnimationBench())
    set({ rail: 'library', view: 'page', animation: null })
    navigate({ suite: 'story', tab: 'cast', layer: 'clay' })
    writeHash('#clay/library')
  },
  openAnimation: async (ref) => {
    set({ rail: 'library', view: 'animation', animation: ref, animSel: ref })
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
    writeHash('#clay/library')
  },
  selectAnimation: (animSel) => set({ animSel }),
  openScene: async (stageId, from, section) => {
    set({ rail: 'scenes', view: 'page', ...(from !== undefined ? { from } : {}) })
    const m = await import('../../suites/stage/stageStore')
    const sg = m.useStage.getState()
    if (sg.current?.id !== stageId) await sg.open(stageId)
    if (from?.camera) { m.useStage.getState().setActiveCamera(from.camera); m.useStage.getState().setView('camera') }   // 04 §3: the shot's camera by default
    if (from?.record) m.useStage.getState().setMode('record')                                                              // C3: Record again ▸ from the shot's row
    navigate(section ? { suite: 'stage', tab: section } : { suite: 'stage' })                                              // D186: *Start still ▸* lands on the Still section
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
/** review K93: what the scene picker shows of the stage store's stages — a stage made, removed or renamed; not a save's new revision (every
 *  save re-read every stage document of the project). */
export function sceneListKey(stages: readonly { id: string; name: string }[], current: { id: string; name: string } | null | undefined): string {
  return JSON.stringify([stages.map((s) => [s.id, s.name]), current ? [current.id, current.name] : null])
}
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
    void import('../../suites/stage/stageStore').then(({ useStage }) => { if (live) off = useStage.subscribe((x, p) => { if ((x.stages !== p.stages || x.current !== p.current) && sceneListKey(x.stages, x.current) !== sceneListKey(p.stages, p.current)) read() }) })   // review K93
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
      if (from?.entity) { openInWorld(from.entity.profile, from.entity.version, from.entity.tab); return }   // RS1: an old Library link
      if (c.rail === 'scenes') c.setRail('scenes'); else c.openLibrary()
    })
  }
  const offSession = useSession.subscribe((s, prev) => { if (s.project !== prev.project) go() })
  go()
  const onHash = () => {                                                  // a deep link followed or typed
    const at = placeOfHash(location.hash), c = useClay.getState()
    if (!at || !opened) return
    if (at.rail === 'scenes') { if (at.stage) void c.openScene(at.stage); else if (c.rail !== 'scenes') c.setRail('scenes'); return }
    if (at.anim) { if (c.view !== 'animation' || JSON.stringify(c.animation) !== JSON.stringify(at.anim)) void c.openAnimation(at.anim); return }
    if (at.entity) { openInWorld(at.entity.profile, at.entity.version, at.entity.tab); return }                 // RS1
    if (c.rail !== 'library' || c.view !== 'page') c.openLibrary()
  }
  window.addEventListener('hashchange', onHash)
  const offNav = onNavigate((p) => {                                       // the editor opened from anywhere shows under Scenes
    const c = useClay.getState()
    if (p.suite !== 'stage' || p.layer || c.view === 'animation' || c.rail === 'scenes') return   // RS1: the stage suite on another layer (World's bench) is not Clay's
    useClay.setState({ rail: 'scenes', view: 'page' })
    void import('../../suites/stage/stageStore').then((m) => writeHash(`#clay/scene${m.useStage.getState().current?.id ? `/${m.useStage.getState().current!.id}` : ''}`))
  })
  return () => { offSession(); offNav(); window.removeEventListener('hashchange', onHash) }
}
