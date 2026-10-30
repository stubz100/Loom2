// U4 (D157, proto01_UI2 04): Shots' own view state — the level (Flow, or the open shot's Clay · Performance · Final). The shot and its node
// are the Story store's selection (the records of today), so Shots and the old Story tabs act on the same records. The place is kept in the
// hash: #shots/<shot>/<level>. A level is also an old suite (the Flow is Story's Flow tab, Clay the stage suite), so the reused parts' keys
// and reads follow through U1's router (the layer stays Shots).
import { create } from 'zustand'
import { http, unwrap } from '../../api/client'
import { navigate, onNavigate, type Place } from '../../frame/router'
import { useSession } from '../../store/session'
import { useStory } from '../../suites/story/storyStore'
import type { FinalOwed } from '../../api/types'

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
  flowView: 'canvas' | 'list'                // B2a (D157 Q11): the Flow's canvas or its List view (the Shots board)
  setFlowView: (v: 'canvas' | 'list') => void
  open: (shotId: string, level?: ShotLevel) => void
  /** The shot's scene or camera changed: Clay opens on it again. */
  reopen: () => void
  wordsOpen: boolean
  wordsFor: WordsFor
  /** U6c (04 §4): what the shot's newest final still owes — its plate, the character layers not performed yet, D164 their face work —
   *  and the GPU minutes. */
  owed: Owed | null
  toggleWords: () => void
  setWordsFor: (w: WordsFor) => void
}

/** U6b–c (04 §4): a shot's method is its version's (`ShotVersion.method`), shown as Performance's card — Layered the Final shot card (the
 *  default), One pass the Stage clip, From the start still Image to video. */
type Card = 'final' | 'clip' | 'i2v'
type Method = 'layered' | 'one_pass' | 'start_still' | 'speaking'
const CARD: Record<Method, Card> = { layered: 'final', one_pass: 'clip', start_still: 'i2v', speaking: 'i2v' }
const METHOD: Record<Card, Method> = { final: 'layered', clip: 'one_pass', i2v: 'start_still' }

/** U6c → D164: the shot's final's owed work as the server counts it (GET /finals/{fid}/owed): what *Perform the owed layers ▶* queues,
 *  with the GPU minutes, and what it only lists (why). */
export interface Owed { fid: string; items: FinalOwed['items']; queued: number; minutes: number }
type FinalLite = { id: string; shot_id?: string | null; shot_version?: string | null; created_at: string; revision?: number }
/** The newest final made for the shot version, or null. */
export function newestFinal<T extends FinalLite>(finals: T[], shotId: string, version: string): T | null {
  return finals.filter((x) => x.shot_id === shotId && (!x.shot_version || x.shot_version === version)).sort((a, b) => (a.created_at < b.created_at ? 1 : -1))[0] ?? null
}
/** What the newest final owes, from its server count — null when nothing is queued or listed. */
export function owedOf(finals: FinalLite[], owed: Record<string, FinalOwed>, shotId: string, version: string): Owed | null {
  const f = newestFinal(finals, shotId, version)
  const o = f ? owed[f.id] : undefined
  if (!f || !o || !o.items.length) return null
  const queued = o.items.filter((x) => x.queue).length
  return { fid: f.id, items: o.items, queued, minutes: queued ? Math.max(1, Math.round(o.seconds / 60)) : 0 }
}
const OWED_WORD: Record<string, string> = { perform: 'performance', face: 'face pass', lipsync: 'lip-sync' }
/** D164: the owed items, one a line, for the foot's tooltip (rule 11: no block of text on the screen) — what is queued with its minutes,
 *  what is only listed and why. */
export function owedTitle(o: Owed): string {
  return o.items.map((it) => {
    const who = it.kind === 'plate' ? 'The plate' : `${it.name}: ${OWED_WORD[it.kind] ?? it.kind}`
    return it.queue ? `${who}${it.after ? ' (after its performance)' : ''}${it.seconds ? ` · ≈ ${Math.max(1, Math.round(it.seconds / 60))} min` : ''}` : `${who} — not queued: ${it.why}`
  }).join('\n')
}
let unOwed: (() => void) | null = null
async function followOwed(): Promise<void> {
  const { useFinals } = await import('../../suites/stage/finalShot')
  let asked = ''
  const calc = () => {
    const st = useStory.getState(), s = st.shot(), v = st.shotVersion(), fs = useFinals.getState()
    const f = s && v ? newestFinal(fs.finals as unknown as FinalLite[], s.id, v.id) : null
    const key = f ? `${f.id}:${f.revision ?? 0}` : ''
    if (f && key !== asked) { asked = key; void fs.loadOwed(f.id) }          // the server counts it again when the final moves
    useShots.setState({ owed: s && v ? owedOf(fs.finals as unknown as FinalLite[], fs.owed, s.id, v.id) : null })
  }
  calc()
  unOwed?.()
  unOwed = useFinals.subscribe(calc)
}

/** The card picked becomes the open version's method (a final version keeps its own). */
async function keepMethod(card: Card): Promise<void> {
  const st = useStory.getState(), s = st.shot(), v = st.shotVersion()
  if (!s || !v || v.state !== 'open' || (v.method ?? 'layered') === METHOD[card]) return
  try {
    const next = await unwrap(http.PATCH('/story/shots/{sid}', { params: { path: { sid: s.id } }, body: { revision: s.revision, versions: [{ id: v.id, method: METHOD[card] }] } as never }))
    useStory.setState({ shots: useStory.getState().shots.map((x) => (x.id === next.id ? next : x)) })
  } catch { /* the card stays; the method is written with the next pick */ }
}

/** U6b: Performance and Final act on this shot (F41) — Animate's For chip is the open shot version, its method's card is open, and the
 *  card picked is kept as the shot's method. */
async function enterPerformance(): Promise<void> {
  const s = useStory.getState().shot(), v = useStory.getState().shotVersion()
  if (!s || !v) return
  const [{ useMakeFor }, { forShot }, { useAnimRoute }] = await Promise.all([import('../../store/origin'), import('../../suites/story/makeFor'), import('../../suites/animate/routeStore')])
  useMakeFor.getState().set('animate', forShot(s, v))
  useAnimRoute.getState().set(CARD[(v.method ?? 'layered') as Method] ?? 'final')
  unfollow?.()
  unfollow = useAnimRoute.subscribe((r, prev) => { if (r.route !== prev.route && useShots.getState().level === 'performance') void keepMethod(r.route as Card) })
  void followOwed()
}
let unfollow: (() => void) | null = null

/** U6b (04 §5): Final opens on this shot's final — the newest final made for the shot version that has its composition — not a final of
 *  whatever stage was open last (F41). None yet: Final says so, and Performance makes one. */
async function openShotFinal(): Promise<void> {
  const s = useStory.getState().shot(), v = useStory.getState().shotVersion()
  if (!s || !v) return
  const [{ useFinals }, { useComposition }] = await Promise.all([import('../../suites/stage/finalShot'), import('../../suites/animate/compositionStore')])
  await useFinals.getState().load()
  const { finals, compositions } = useFinals.getState()
  const mine = finals.filter((f) => f.shot_id === s.id && (!f.shot_version || f.shot_version === v.id) && compositions[f.id]).sort((a, b) => (a.created_at < b.created_at ? 1 : -1))[0]
  if (mine && useComposition.getState().finalId !== mine.id) await useComposition.getState().open(mine.id)
  if (mine && !(useComposition.getState().comp?.audio ?? []).length) await useComposition.getState().layLines()   // U6c: the shot's lines on their lanes by themselves
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

let opens = 0                                                            // the shots opened: the mount's place from the hash yields to a later one
export const useShots = create<ShotsState>()((set, get) => ({
  level: placeOfHash(location.hash)?.level ?? 'flow',
  flowView: 'canvas',
  setFlowView: (flowView) => set({ flowView }),
  setLevel: (level) => {
    set({ level })
    navigate(suiteOf(level))
    writeHash(useStory.getState().shotId, level)
    if (level !== 'flow') void openClay().then(() => (level === 'performance' || level === 'final' ? enterPerformance() : undefined)).then(() => (level === 'final' ? openShotFinal() : undefined))   // U6b: every level of a shot is on its stage
  },
  open: (shotId, level) => {
    opens++
    const st = useStory.getState()
    if (!st.shots.some((x) => x.id === shotId)) {                       // B2: opened from a layer that reads no shots (World's uses, the Bin)
      void st.loadShots().then(() => { if (useStory.getState().shots.some((x) => x.id === shotId)) get().open(shotId, level) })
      return
    }
    st.selectShot(shotId)
    const s = useStory.getState().shot()
    if (s?.owner_node) useStory.getState().selectNode(s.owner_node)
    get().setLevel(level ?? get().level)                                // 04 §2: a card opens the shot at the level last used
  },
  reopen: () => { const l = get().level; if (l !== 'flow') void openClay().then(() => (l === 'performance' || l === 'final' ? enterPerformance() : undefined)) },
  wordsOpen: false, wordsFor: 'still', owed: null,
  toggleWords: () => set({ wordsOpen: !get().wordsOpen }),
  setWordsFor: (wordsFor) => set({ wordsFor }),
}))

/** Mounted with the Shots layer: once a project is open, the Flow, the shots and the board's facts, then the place from the hash — unless a
 *  shot was opened meanwhile (Episode's Finals open one as they switch to Shots: the hash's place came after it and took it back to the Flow). */
export function startShots(): () => void {
  let opened: string | null = null
  const go = () => {
    const pj = useSession.getState().project
    const path = pj?.open ? (pj as { path?: string }).path ?? 'open' : null
    if (!path || path === opened) return
    opened = path
    const st = useStory.getState(), from = placeOfHash(location.hash), n = opens
    void Promise.all([st.loadFlow(), st.loadShots(), st.loadProfiles()]).then(() => {
      void useStory.getState().loadBoard()
      const sh = useShots.getState()
      if (opens !== n) return
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
