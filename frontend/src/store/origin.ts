// D66 "Go to origin": a job's `origin {suite, surface, ref?, payload?}` names where it was started; this switches to that suite and shows
// the thing it was started on. Like `applyEvent`, it reaches the suite stores through dynamic imports, so the frame (the Dock) stays
// ignorant of suite internals.
// D90 (02 §5): makers in context — a maker opened *for* a Story object ("Make frame ▸" on a shot) holds a For context; while it is set,
// its submissions carry a `for_shot` origin (the server records the results as takes of that version), its Panel shows the chip with
// "← Back", and "Go to origin" on such a job goes to the same place. Opened from its own tab, a maker has none and works as before.
import { create } from 'zustand'
import type { Job, JobOrigin } from '../api/types'
import { useSession } from './session'

type Origin = NonNullable<Job['origin']>

const SUITE_LABEL: Record<Origin['suite'], string> = { generate: 'Image', edit: 'Image · Edit', animate: 'Animate', catalogue: 'Catalogue', stage: 'Stage', story: 'Story', api: 'API' }

/** D90 (02 §5): `origin.surface` of a job made for a shot version (the server's `story.FOR_SHOT`). */
export const FOR_SHOT = 'for_shot'
/** D93 (A1): `origin.surface` of a casting run from Generate — its results land as a profile version's candidates (`payload.group_id`). */
export const CAST = 'cast'
export type Maker = 'generate' | 'animate'
/** What a maker was opened for: a shot version (its name for the chip; the owner node when Make came from the Flow). */
export interface MakeFor { kind: 'shot'; shot_id: string; version: string; name: string; node_id?: string | null }

interface ForState { generate: MakeFor | null; animate: MakeFor | null; set: (maker: Maker, f: MakeFor | null) => void }
/** The For context of each maker (session only: a reload starts without one). */
export const useMakeFor = create<ForState>()((set) => ({ generate: null, animate: null, set: (maker, f) => set({ [maker]: f } as Partial<ForState>) }))
useSession.subscribe((s, prev) => { if (s.project?.path !== prev.project?.path) useMakeFor.setState({ generate: null, animate: null }) })   // another project: no shot of it

/** The chip's words: "Shot 12 · v3". */
export const forLabel = (f: MakeFor): string => `${f.name} · ${f.version}`
/** The origin a maker's job carries for a shot version; `ref` stays the maker's own (Animate: the clip on screen, so the player follows). */
export function forOrigin(f: MakeFor, suite: Maker, ref: string | null = null): JobOrigin {
  return { suite, surface: FOR_SHOT, ref, payload: { shot_id: f.shot_id, version: f.version, ...(f.node_id ? { node_id: f.node_id } : {}) } }
}
/** The origin a maker submits with: the For origin while its chip is set, else its own (`fallback`). */
export function originFor(maker: Maker, fallback: JobOrigin): JobOrigin {
  const f = useMakeFor.getState()[maker]
  return f ? forOrigin(f, maker, fallback.ref ?? null) : fallback
}

/** Where a Story job's result is shown (inventory F24): the tab and the thing to select there; null when the origin names none. */
export type StoryPlace = { tab: 'world' | 'cast' | 'shots' | 'flow'; id: string; version?: string | null }
export function storyPlace(o: Pick<Origin, 'suite' | 'surface' | 'ref' | 'payload'>): StoryPlace | null {
  const p = o.payload ?? {}
  const ver = typeof p.version === 'string' ? p.version : null
  if (o.surface === FOR_SHOT) return typeof p.shot_id === 'string' ? { tab: 'shots', id: p.shot_id, version: ver } : null
  if (o.surface === CAST && o.ref) return { tab: 'cast', id: o.ref, version: ver }                       // D93 (A1): a casting run from Generate → the profile's candidates
  if (o.suite !== 'story' || !o.ref) return null
  switch (o.surface) {
    case 'expand': case 'train': case 'lora_check': return { tab: 'cast', id: o.ref, version: ver }   // a profile version
    case 'lipsync': return { tab: 'shots', id: o.ref, version: ver }                                   // a shot version
    case 'voice': return { tab: 'flow', id: o.ref }                                                     // the node whose lines were spoken
    case 'style': return { tab: 'world', id: o.ref }                                                    // a style's sample
    default: return null
  }
}

/** Story at a place: the tab, then the profile / shot / node / style selected (records loaded first when they are not yet). */
export function goToStory(place: StoryPlace): void {
  useSession.getState().setSuite('story')
  void Promise.all([import('../suites/story/storyStore'), import('../frame/suiteRegistry')]).then(async ([m, reg]) => {
    reg.setRailTab('story', place.tab)
    const st = m.useStory.getState()
    if (place.tab === 'cast') {
      if (!st.profilesLoaded) await st.loadProfiles()
      const p = m.useStory.getState().profiles.find((x) => x.id === place.id)
      if (p && m.tabOfClass(p.cls) !== 'cast') reg.setRailTab('story', m.tabOfClass(p.cls))   // D110: a prop lives on Props
      m.useStory.getState().selectProfile(place.id, place.version)
    }
    else if (place.tab === 'shots') { if (!st.shotsLoaded) await st.loadShots(); m.useStory.getState().selectShot(place.id, place.version) }
    else if (place.tab === 'flow') { if (!st.flowLoaded) await st.loadFlow(); m.useStory.getState().selectNode(place.id) }
    else { m.useStory.getState().setSection('styles'); m.useStory.getState().select({ kind: 'style', id: place.id }) }
  })
}

/** The chip's "← Back": the shot version the maker works for. D125 (I3): going back ends the context, so later work in the maker is not
 *  silently a take of that shot; the shot's Make ▸ sets it again. */
export function goBack(maker: Maker): void {
  const f = useMakeFor.getState()[maker]
  if (!f) return
  useMakeFor.getState().set(maker, null)
  goToStory({ tab: 'shots', id: f.shot_id, version: f.version })
}

/** False for jobs without an origin (queued before D66) and for jobs submitted through the API by a script (no suite to go to). */
export const canGoToOrigin = (j: Pick<Job, 'origin'>): boolean => !!j.origin && j.origin.suite !== 'api'

/** A short description for tooltips: "Generate · results", "Edit · ai · doc_…". */
export function originLabel(o: Origin | null | undefined): string {
  if (!o) return 'no origin (queued before origins were recorded)'
  if (o.surface === FOR_SHOT) return `${SUITE_LABEL[o.suite]} · for a shot · ${String(o.payload?.shot_id ?? '')} ${String(o.payload?.version ?? '')}`.trim()
  return [SUITE_LABEL[o.suite], o.surface, o.ref].filter(Boolean).join(' · ')
}

export function goToOrigin(j: Job): void {
  const o = j.origin
  if (!o || !canGoToOrigin(j)) return
  const s = useSession.getState()
  const place = storyPlace(o)                                     // D90 (F24): Story jobs and jobs made for a shot go to their Story object
  if (place) { goToStory(place); return }
  switch (o.suite) {
    case 'generate':                                              // the job's batch in Generate's results ("this batch")
      s.setSuite('generate')
      void import('../suites/generate/generateStore').then((m) => m.useGenerate.setState({ lastBatch: m.batchOf(j), show: 'batch' }))
      break
    case 'animate':                                               // the clip the job was started on, when there was one
      s.setSuite('animate')
      if (o.ref) { const ref = o.ref; void import('../suites/animate/animateStore').then((m) => { const an = m.useAnimate.getState(); void an.loadClips().then(() => an.select(ref)) }) }
      break
    case 'edit':                                                  // the document the AI request ran on
      s.setSuite('edit')
      if (o.ref) { const ref = o.ref; void import('../suites/edit/editorStore').then((m) => { const ed = m.useEditor.getState(); if (ed.doc?.id !== ref) void ed.openDocument(ref) }) }
      break
    case 'catalogue':                                             // the group page (or, without one, the folder) in the active pane
      s.setSuite('catalogue')
      void import('../suites/catalogue/split').then((m) => {
        const sp = m.useSplit.getState()
        const c = m.paneStore(sp.mode === 'single' ? 0 : sp.active).getState()
        const folder = typeof o.payload?.folder === 'string' ? o.payload.folder : null
        if (o.ref) m.openPlace(c, { group: o.ref })
        else if (folder) void c.setQuery({ folder: folder as typeof c.q.folder, group_id: undefined, collection_id: undefined })
      })
      break
    case 'stage':                                                 // ST3: the stage the shot was framed in, at that camera
      s.setSuite('stage')
      if (o.ref) { const ref = o.ref; const cam = typeof o.payload?.camera_id === 'string' ? o.payload.camera_id : null
        void import('../suites/stage/stageStore').then((m) => { const st = m.useStage.getState(); const go = st.current?.id === ref ? Promise.resolve() : st.open(ref); void go.then(() => { if (cam) m.useStage.getState().setActiveCamera(cam) }) }) }
      break
    case 'story':                                                 // a Story job storyPlace does not place: the suite
      s.setSuite('story')
      break
    default: break
  }
}
