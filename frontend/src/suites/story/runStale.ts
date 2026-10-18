// RC0 (D96, proto01_animate/05 §4): *Run stale* — the plan and its cost first (askConfirm), then the server queues the steps that can
// run now and the ones after them as each finishes (one job at a time, D97); their results become the version's frame and clip. A stage
// still needs fresh passes: they are rendered here (the stage's own renderer, headless when the stage is not on screen) and sent along.
import { http, unwrap, type ApiError } from '../../api/client'
import { askConfirm, useSession } from '../../store/session'

/** The stale count per `shot:version`, as the last recipe fetch saw it (RecipeSteps) — the Run stale commands' `when`. */
const staleSeen = new Map<string, number>()
export const noteStale = (shotId: string, version: string, n: number): void => { staleSeen.set(`${shotId}:${version}`, n) }
export const staleOf = (shotId: string | undefined, version: string | undefined): number => (shotId && version ? staleSeen.get(`${shotId}:${version}`) ?? 0 : 0)

export const secs = (s: number | null | undefined): string => (s == null ? '' : s < 90 ? `${Math.round(s)} s` : `${Math.round(s / 60)} min`)

/** Render the passes of the version's stage camera; their asset ids, or null (said). */
async function passesFor(shotId: string, version: string): Promise<Record<string, string> | null> {
  const toast = useSession.getState().toast
  try {
    const shot = await unwrap(http.GET('/story/shots/{sid}', { params: { path: { sid: shotId } } }))
    const v = shot.versions.find((x) => x.id === version)
    if (!v?.stage_id || !v.camera_id) { toast('The still came from a stage, but the version names none', 'error'); return null }
    const { st } = await import('../stage/stageStore')
    if (st().current?.id !== v.stage_id) await st().open(v.stage_id)
    st().setActiveCamera(v.camera_id)
    if (!(await st().renderPasses())) return null
    return st().passesEntry()?.assets ?? null
  } catch (e) { toast(`The passes were not rendered: ${(e as ApiError).detail ?? e}`, 'error'); return null }
}

export async function runStale(shotId: string, version: string): Promise<void> {
  const { toast } = useSession.getState()
  const path = { sid: shotId, vid: version }
  try {
    const dry = await unwrap(http.POST('/story/shots/{sid}/versions/{vid}/run-stale', { params: { path }, body: { dry: true } }))
    if (!dry.plan.length) { toast('Nothing in this recipe is stale', 'info'); return }
    const label = (id: string) => dry.plan.find((p) => p.id === id)?.label.toLowerCase() ?? id
    const lines = dry.plan.map((p) => `• ${p.label}${p.seconds ? ` · ≈ ${secs(p.seconds)}` : ''}`
      + (p.how === 'passes' ? ' — the stage\'s passes are rendered first' : p.how === 'stage' ? ' — made again on the stage (Animate · Clay)' : p.how === 'manual' ? ' — made again by hand' : '')
      + (p.after.length && p.how === 'server' ? ` — after the ${p.after.map(label).join(', ')}` : '') + ` (${p.reasons.join('; ')})`)
    const ok = await askConfirm({ title: 'Run the stale steps again?', text: `${lines.join('\n')}\n\nAbout ${secs(dry.seconds)} on the GPU, one job at a time. The results become this version's frame and clip; the old takes stay.`, okLabel: 'Run' })
    if (!ok) return
    const still = dry.plan.find((p) => p.how === 'passes' && !p.after.length)
    const passes = still ? await passesFor(shotId, version) : null
    if (still && !passes) return
    const r = await unwrap(http.POST('/story/shots/{sid}/versions/{vid}/run-stale', { params: { path }, body: { dry: false, passes } }))
    if (!r.queued.length) { toast(r.elsewhere.length ? `Nothing can run from here: ${r.elsewhere.map(label).join(', ')} — made again by hand` : 'Nothing could be queued', 'info'); return }
    toast(`Queued: ${r.queued.map((q) => label(q.step)).join(', ')}${r.then.length ? ` — then ${r.then.map(label).join(', ')}` : ''}${r.elsewhere.length ? ` · by hand: ${r.elsewhere.map(label).join(', ')}` : ''}`, 'success')
  } catch (e) { toast(`Run stale failed: ${(e as ApiError).detail ?? e}`, 'error') }
}
