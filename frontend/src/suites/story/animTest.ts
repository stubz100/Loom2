// CA0 (proto01_animate 01 step 2): *Test the reference* — before any shot depends on a character's animation reference, a short test
// animation shows whether it animates well: a turn on the spot (the version's body in the reference's A-pose, the Stage's pose renderer,
// stage/turnTest.ts), performed by the Stage's pose-driven model with the reference as the character. The cost is asked first; the
// sequence and the clip land on the version's candidates page and the clip is recorded on the version (anim_test_clip_id).
import { api, http, sha256Hex, unwrap, type ApiError } from '../../api/client'
import { askConfirm, useSession } from '../../store/session'
import { useStory } from './storyStore'
import { navigate } from '../../frame/router'

const secs = (s: number | null | undefined) => (s == null ? 'unmeasured' : s < 90 ? `≈ ${Math.round(s)} s` : `≈ ${Math.round(s / 60)} min`)

export async function testAnimRef(): Promise<void> {
  const { toast } = useSession.getState()
  const st = useStory.getState()
  const p = st.profile(), v = st.version()
  const caps = useSession.getState().capabilities?.stage?.animate
  if (!p || !v || !v.anim_ref_asset_id) return
  if (!caps) { toast('No pose-driven model in this build', 'error'); return }
  const frames = caps.frames_max ?? 77, fps = caps.fps ?? 16
  const [w, h] = (caps.size?.length ? caps.size : [832, 480]) as [number, number]
  const ok = await askConfirm({ title: `Test ${p.name}'s animation reference?`, okLabel: 'Test',
    text: `A turn on the spot — ${frames} frames at ${fps} fps, ${w}×${h} — through ${caps.label}: ${secs(caps.seconds)} on the GPU. The pose sequence is drawn here from ${p.name}'s body; the clip lands on the candidates page.` })
  if (!ok) return
  try {
    toast('Drawing the turn…', 'info')
    await runAnimTest(p.id, v.id)
    toast(`${p.name}'s test animation is queued — the clip lands on the candidates page and beside the reference`, 'success')
  } catch (e) { toast(`Test animation: ${(e as ApiError).detail ?? e}`, 'error') }
}

/** Draw the turn from the version's body, upload it and queue the test (no confirm — the command asks; the dev hook and the rig call this). */
export async function runAnimTest(pid: string, vid: string, stage = false): Promise<{ job_id: string; guide_asset_id: string; model_id: string }> {
  const caps = useSession.getState().capabilities?.stage?.animate
  const p = useStory.getState().profiles.find((x) => x.id === pid)
  const v = p?.versions.find((x) => x.id === vid)
  if (!caps || !p || !v) throw new Error('no pose-driven model, or the version is not loaded')
  const frames = caps.frames_max ?? 77, fps = caps.fps ?? 16
  const [w, h] = (caps.size?.length ? caps.size : [832, 480]) as [number, number]
  const { renderTurn } = await import('../stage/turnTest')
  const out = await renderTurn((v.body ?? null) as never, frames, fps, w, h, undefined, v.body_points as never, v.shell_asset_id ?? null)   // S4: in the reference's stance; CS3: on its shell
  const shas: string[] = []
  for (const blob of out.blobs) {
    const sha = await sha256Hex(await blob.arrayBuffer())
    await api.putBlob(sha, blob)
    shas.push(sha)
  }
  return unwrap(http.POST('/story/profiles/{pid}/versions/{vid}/anim-test', { params: { path: { pid, vid } }, body: { fps, size: { w, h }, frames: shas, keypoints: out.keypoints as never, stage } }))
}

/** Play the version's test clip in the Bin's large view. */
export function playAnimTest(): void {
  const v = useStory.getState().version()
  const clip = v?.anim_test_clip_id
  if (!clip) return
  void unwrap(http.GET('/clips/{clip_id}', { params: { path: { clip_id: clip } } })).then(async (c) => {   // B2a (D159): in the Bin's large view
    if (!c.asset_id) return
    navigate({ suite: 'catalogue' })
    const { useBin } = await import('../../ui2/bin/binStore')
    if (await useBin.getState().reveal(c.asset_id)) useBin.getState().view(true)
  }).catch(() => undefined)
}
