// C3 (D181, propo02 04 §4.3; 05 Q6): Record ▶ — the animatic. The scene's lit clay (every object in its own material, the lights with their
// shadows, the backdrops) through the shot's camera over the shot's range, frame-stepped at the scene's fps and the draft size on the CPU
// (the viewport's own renderer, no GPU job), then posted as the version's animatic: a clip of the project, its proxy in the Bin under the
// shot, the version stamped with the scene's revision (the Shots header's row says *stale* once the scene moves on). The storyboard's
// first deliverable: it plays on the card and Episode cuts it until a performance replaces it.
import { api, http, sha256Hex, unwrap, type ApiError } from '../../api/client'
import { useSession } from '../../store/session'
import { useStory } from '../story/storyStore'
import { sampleDoc } from './anim'
import { blocksReady } from './blocks'
import { shotRange } from './finalShot'
import { st, useStage, type SequenceRenderer } from './stageStore'

export interface RecordFor { shot: string; version: string }

/** What Record ▶ will make for the shot: its range on the scene and the seconds it is. */
export function animaticPlan(doc: { range: { start: number; end: number }; size: { fps?: number } }, forShot: RecordFor | null): { start: number; end: number; frames: number; seconds: string } {
  const r = forShot ? shotRange(doc as never, { shot_id: forShot.shot, version: forShot.version }) : doc.range
  const frames = Math.max(1, r.end - r.start + 1)
  return { start: r.start, end: r.end, frames, seconds: (frames / Math.max(1, doc.size.fps ?? 24)).toFixed(1) }
}

/** Render the shot's frames and post them as its animatic. True when the version carries it. */
export async function recordAnimatic(forShot: RecordFor): Promise<boolean> {
  const s = st()
  const session = useSession.getState()
  const cam = s.activeCamera()
  if (!s.current || !cam) { session.toast('No camera to record through', 'error'); return false }
  if (!s.sequenceRenderer) (await import('./headless')).ensureHeadless()
  const render = st().sequenceRenderer as SequenceRenderer | null
  if (!render) { session.toast('The scene is not ready to record', 'error'); return false }
  useStage.setState({ rendering: true })
  try {
    await s.flush()
    const doc = st().current
    if (!doc) return false
    const plan = animaticPlan(doc, forShot)
    const [w, h] = st().shotSize()
    await blocksReady(doc)                                                           // U5: the figures' clip blocks evaluated before a frame is sampled
    const times = Array.from({ length: plan.frames }, (_, i) => plan.start + i)
    const sampled = times.map((t) => { const d = sampleDoc(doc, t); return { cam: d.cameras.find((c) => c.id === cam.id) ?? cam, doc: d, frame: t } })
    const out = await render(sampled, w, h, 'beauty', sampleDoc(doc, st().frame))
    const shas: string[] = []
    const uploaded = new Set<string>()
    for (const blob of out.blobs) {
      const sha = await sha256Hex(await blob.arrayBuffer())
      if (!uploaded.has(sha)) { await api.putBlob(sha, blob); uploaded.add(sha) }
      shas.push(sha)
    }
    const next = await unwrap(http.POST('/story/shots/{sid}/versions/{vid}/animatic', { params: { path: { sid: forShot.shot, vid: forShot.version } }, body: { frames: shas, fps: doc.size.fps } }))
    useStory.setState({ shots: useStory.getState().shots.map((x) => (x.id === next.id ? next : x)) })
    session.toast(`Animatic recorded: ${shas.length} frames at ${w}×${h}`, 'success')
    return true
  } catch (e) { session.toast(`Record failed: ${(e as ApiError).detail ?? e}`, 'error'); return false } finally { useStage.setState({ rendering: false }) }
}
