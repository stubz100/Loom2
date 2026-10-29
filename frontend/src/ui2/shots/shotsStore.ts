// U4 (D157, proto01_UI2 04): Shots' own view state — the level (Flow, or the open shot's Clay · Performance · Final). The shot and its node
// are the Story store's selection (the records of today), so Shots and the old Story tabs act on the same records. The place is kept in the
// hash: #shots/<shot>/<level>. A level is also an old suite (the Flow is Story's Flow tab, Clay the stage suite), so the reused parts' keys
// and reads follow through U1's router (the layer stays Shots).
import { create } from 'zustand'
import { http, unwrap } from '../../api/client'
import { navigate, onNavigate, type Place } from '../../frame/router'
import { useSession } from '../../store/session'
import { useStory } from '../../suites/story/storyStore'

export type ShotLevel = 'flow' | 'clay' | 'performance' | 'final'
/** U4d (G13): the picture the header's words are shown for. */
export type WordsFor = 'still' | 'plate' | 'performance'
export const LEVELS: { id: ShotLevel; label: string }[] = [{ id: 'flow', label: 'Flow' }, { id: 'clay', label: 'Clay' }, { id: 'performance', label: 'Performance' }, { id: 'final', label: 'Final' }]

/** The hash's Shots place: #shots/<shot>/<level> (its parts optional). */
export function placeOfHash(hash: string): { shot: string | null; level: ShotLevel } | null {
  const [layer, a, b] = hash.replace(/^#/, '').split('/')
  if (layer !== 'shots') return null
  const lv = (x: string | undefined) => LEVELS.find((l) => l.id === x)?.id
  if (lv(a)) return { shot: null, level: lv(a)! }
  return { shot: a || null, level: lv(b) ?? (a ? 'clay' : 'flow') }
}
const writeHash = (shot: string | null, level: ShotLevel): void => {
  const h = shot ? `#shots/${shot}/${level}` : `#shots/${level}`
  if (location.hash !== h) history.replaceState(null, '', `${location.pathname}${location.search}${h}`)
}

/** The old suite a level reads with (its keys and its reused parts): the Flow is Story's Flow tab, Clay the stage suite. */
export function suiteOf(level: ShotLevel): { suite: 'story' | 'stage' | 'animate' | 'final'; tab?: string } {
  return level === 'flow' ? { suite: 'story', tab: 'flow' } : level === 'clay' ? { suite: 'stage' } : level === 'performance' ? { suite: 'animate' } : { suite: 'final' }
}

/** The level an old place is (a command of the old suites — *Open the stage*, *Block it on a stage…* — navigates there), or null. */
export function levelOf(p: Place): ShotLevel | null {
  return p.suite === 'stage' ? 'clay' : p.suite === 'animate' ? 'performance' : p.suite === 'final' ? 'final' : p.suite === 'story' && p.tab === 'flow' ? 'flow' : null
}

interface ShotsState {
  level: ShotLevel
  setLevel: (level: ShotLevel) => void
  open: (shotId: string, level?: ShotLevel) => void
  /** The shot's scene or camera changed: Clay opens on it again. */
  reopen: () => void
  wordsOpen: boolean
  wordsFor: WordsFor
  toggleWords: () => void
  setWordsFor: (w: WordsFor) => void
}

/** Clay on the shot's scene, through its camera (U4: the stage the version points at, its camera active). */
async function openClay(): Promise<void> {
  const v = useStory.getState().shotVersion()
  if (!v?.stage_id) return
  const { useStage, stageContext } = await import('../../suites/stage/stageStore')
  stageContext.enter(`shots/${useStory.getState().shotId}/${v.id}`)
  const st = useStage.getState(), cur = st.current
  // the server changed the open stage since Clay read it (a camera copied for this shot): read it again, or a save would be refused
  const behind = cur?.id === v.stage_id && ((!!v.camera_id && !cur.cameras.some((c) => c.id === v.camera_id)) || (v.stage_revision != null && cur.revision < v.stage_revision))
  if (cur?.id !== v.stage_id || behind) await st.open(v.stage_id)
  if (v.camera_id) { useStage.getState().setActiveCamera(v.camera_id); useStage.getState().setView('camera') }   // 04 §3: the shot's camera by default
}

/** Before a server change to the open stage (a camera copied for a shot): Clay's pending save goes first. */
export async function flushClay(): Promise<void> {
  const { useStage } = await import('../../suites/stage/stageStore')
  await useStage.getState().flush()
}

export const useShots = create<ShotsState>()((set, get) => ({
  level: placeOfHash(location.hash)?.level ?? 'flow',
  setLevel: (level) => {
    set({ level })
    navigate(suiteOf(level))
    writeHash(useStory.getState().shotId, level)
    if (level === 'clay') void openClay()
  },
  open: (shotId, level) => {
    const st = useStory.getState()
    st.selectShot(shotId)
    const s = useStory.getState().shot()
    if (s?.owner_node) useStory.getState().selectNode(s.owner_node)
    get().setLevel(level ?? get().level)                                // 04 §2: a card opens the shot at the level last used
  },
  reopen: () => { if (get().level === 'clay') void openClay() },
  wordsOpen: false, wordsFor: 'still',
  toggleWords: () => set({ wordsOpen: !get().wordsOpen }),
  setWordsFor: (wordsFor) => set({ wordsFor }),
}))

/** Mounted with the Shots layer: once a project is open, the Flow, the shots and the board's facts, then the place from the hash. */
export function startShots(): () => void {
  let opened: string | null = null
  const go = () => {
    const pj = useSession.getState().project
    const path = pj?.open ? (pj as { path?: string }).path ?? 'open' : null
    if (!path || path === opened) return
    opened = path
    const st = useStory.getState(), from = placeOfHash(location.hash)
    void Promise.all([st.loadFlow(), st.loadShots(), st.loadProfiles()]).then(() => {
      void useStory.getState().loadBoard()
      const sh = useShots.getState()
      if (from?.shot && useStory.getState().shots.some((x) => x.id === from.shot)) sh.open(from.shot, from.level)
      else sh.setLevel(from?.level === 'flow' || !useStory.getState().shotId ? 'flow' : from?.level ?? 'flow')
    })
  }
  const off = useSession.subscribe((s, prev) => { if (s.project !== prev.project) go() })
  const follow = onNavigate((p) => {                                   // the level follows a navigation that lands on Shots
    const lv = levelOf(p)
    if (lv && lv !== useShots.getState().level) { useShots.setState({ level: lv }); writeHash(useStory.getState().shotId, lv) }
  })
  go()
  return () => { off(); follow() }
}

/** U4 (G12): a new Shot after the open one — in a new scene, or the same scene as the shot before (a new camera on its stage). */
export async function newShot(scene: 'new' | 'same'): Promise<void> {
  const st = useStory.getState()
  const after = st.shot()?.owner_node ?? null
  if (scene === 'same') await flushClay()
  try {
    const n = await unwrap(http.POST('/story/flow/shots', { body: { title: '', after, scene } }))
    await Promise.all([st.loadFlow(), st.loadShots()])
    void useStory.getState().loadBoard()
    if (n.shot_id) useShots.getState().open(n.shot_id, 'clay')
  } catch (e) { useSession.getState().toast(`New shot: ${(e as { detail?: string }).detail ?? e}`, 'error') }
}
