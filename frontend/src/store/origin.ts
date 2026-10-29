// D66 "Go to origin": a job's `origin {suite, surface, ref?, payload?}` names where it was started; this switches to that suite and shows
// the thing it was started on. Like `applyEvent`, it reaches the suite stores through dynamic imports, so the frame (the Dock) stays
// ignorant of suite internals.
// D90 (02 §5): makers in context — a maker opened *for* a Story object ("Make frame ▸" on a shot) holds a For context; while it is set,
// its submissions carry a `for_shot` origin (the server records the results as takes of that version), its Panel shows the chip with
// "← Back", and "Go to origin" on such a job goes to the same place. Opened from its own tab, a maker has none and works as before.
import { create } from 'zustand'
import type { Job, JobOrigin } from '../api/types'
import { useSession } from './session'
import { navigate } from '../frame/router'

type Origin = NonNullable<Job['origin']>

const SUITE_LABEL: Record<Origin['suite'], string> = { generate: 'World · Make', edit: 'World · Edit', animate: 'Shots · Performance', catalogue: 'Bin', stage: 'Shots · Clay', story: 'Story', api: 'API' }   // B2 (D159): the layers' names

/** D90 (02 §5): `origin.surface` of a job made for a shot version (the server's `story.FOR_SHOT`). */
export const FOR_SHOT = 'for_shot'
/** D93 (A1): `origin.surface` of a casting run from Generate — its results land as a profile version's candidates (`payload.group_id`). */
export const CAST = 'cast'
export type Maker = 'generate' | 'animate'
/** What a maker was opened for: a shot version (its name for the chip; the owner node when Make came from the Flow). */
export interface MakeFor { kind: 'shot'; shot_id: string; version: string; name: string; node_id?: string | null }

/** proto01_UIcast CW2 (06 §2.2, U4): Image opened for an idea (*Explore in Image*) — what it makes stays free; each result's origin names the
 *  idea (`payload.for_idea`, the server's `ideas.FOR_IDEA`) and the idea lists it under *Made for this idea*. */
export interface ForIdea { idea_id: string; name: string }
export const FOR_IDEA = 'for_idea'

interface ForState { generate: MakeFor | null; animate: MakeFor | null; idea: ForIdea | null; set: (maker: Maker, f: MakeFor | null) => void; setIdea: (f: ForIdea | null) => void }
/** The For context of each maker (session only: a reload starts without one). Image is for a shot or for an idea, not both. */
export const useMakeFor = create<ForState>()((set) => ({ generate: null, animate: null, idea: null,
  set: (maker, f) => set({ [maker]: f, ...(maker === 'generate' && f ? { idea: null } : {}) } as Partial<ForState>),
  setIdea: (idea) => set(idea ? { idea, generate: null } : { idea: null }) }))
useSession.subscribe((s, prev) => { if (s.project?.path !== prev.project?.path) useMakeFor.setState({ generate: null, animate: null, idea: null }) })   // another project: no shot of it

/** The chip's words: "Shot 12 · v3". */
export const forLabel = (f: MakeFor): string => `${f.name} · ${f.version}`
/** The origin a maker's job carries for a shot version; `ref` stays the maker's own (Animate: the clip on screen, so the player follows). */
export function forOrigin(f: MakeFor, suite: Maker, ref: string | null = null): JobOrigin {
  return { suite, surface: FOR_SHOT, ref, payload: { shot_id: f.shot_id, version: f.version, ...(f.node_id ? { node_id: f.node_id } : {}) } }
}
/** The origin a maker submits with: the For origin while its chip is set, else its own (`fallback`). */
export function originFor(maker: Maker, fallback: JobOrigin): JobOrigin {
  const f = useMakeFor.getState()[maker]
  return f ? forOrigin(f, maker, fallback.ref ?? null) : maker === 'generate' ? withIdea(fallback) : fallback
}
/** CW2: Image's own origin with the idea its chip names (the origin is otherwise as it was: the result goes where it always goes). */
export function withIdea(o: JobOrigin): JobOrigin {
  const i = useMakeFor.getState().idea
  return i ? { ...o, payload: { ...(o.payload ?? {}), [FOR_IDEA]: i.idea_id } } : o
}
/** CW2: the idea chip's "← Back": Cast's Ideas board on the idea; the chip ends (later work in Image is free again). */
export function goBackToIdea(): void {
  const i = useMakeFor.getState().idea
  if (!i) return
  useMakeFor.getState().setIdea(null)
  goToIdea(i.idea_id)
}
/** Story › Cast's Ideas board with an idea open on its bench. */
export function goToIdea(id: string): void {
  navigate({ suite: 'story', tab: 'cast' })
  void import('../suites/story/ideasStore').then(async (m) => {
    const st = m.useIdeas.getState()
    if (!st.loaded) await st.load()
    m.useIdeas.setState({ board: 'ideas', ideaId: id })
  })
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
  navigate({ suite: 'story', tab: place.tab })
  void import('../suites/story/storyStore').then(async (m) => {
    const st = m.useStory.getState()
    if (place.tab === 'cast') {
      if (!st.profilesLoaded) await st.loadProfiles()
      const p = m.useStory.getState().profiles.find((x) => x.id === place.id)
      if (p) m.revealClass(p.cls)                                                           // D125: Cast's class switch shows it
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
  const place = storyPlace(o)                                     // D90 (F24): Story jobs and jobs made for a shot go to their Story object
  if (place) { goToStory(place); return }
  switch (o.suite) {
    case 'generate':                                              // the job's batch in Generate's results ("this batch")
      navigate({ suite: 'generate' })
      void import('../suites/generate/generateStore').then((m) => m.useGenerate.setState({ lastBatch: m.batchOf(j), show: 'batch' }))
      break
    case 'animate':                                               // the clip the job was started on, when there was one
      navigate({ suite: 'animate' })
      if (o.ref) { const ref = o.ref; void import('../suites/animate/animateStore').then((m) => { const an = m.useAnimate.getState(); void an.loadClips().then(() => an.select(ref)) }) }
      break
    case 'edit':                                                  // the document the AI request ran on
      navigate({ suite: 'edit' })
      if (o.ref) { const ref = o.ref; void import('../suites/edit/editorStore').then((m) => { const ed = m.useEditor.getState(); if (ed.doc?.id !== ref) void ed.openDocument(ref) }) }
      break
    case 'catalogue':                                             // B2 (D159): the thing in its home in the Bin, or the home of the page
      if (o.ref && (o.surface === 'mesh' || o.ref.startsWith('ast_'))) { const ref = o.ref; navigate({ suite: 'catalogue' }); void import('../ui2/bin/binStore').then((m) => void m.useBin.getState().reveal(ref)) }
      else if (o.ref) void import('../suites/story/storyCommands').then((m) => m.openGroupPage(o.ref!))
      else navigate({ suite: 'catalogue' })
      break
    case 'stage':                                                 // ST3: the stage the shot was framed in, at that camera
      navigate({ suite: 'stage' })
      if (o.ref) { const ref = o.ref; const cam = typeof o.payload?.camera_id === 'string' ? o.payload.camera_id : null
        void import('../suites/stage/stageStore').then((m) => { const st = m.useStage.getState(); const go = st.current?.id === ref ? Promise.resolve() : st.open(ref); void go.then(() => { if (cam) m.useStage.getState().setActiveCamera(cam) }) }) }
      break
    case 'story':                                                 // a Story job storyPlace does not place: the suite
      navigate({ suite: 'story' })
      break
    default: break
  }
}
