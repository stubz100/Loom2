// E6 — frame-accurate scrubbing with Mediabunny's CanvasSink (12 §1 E6, 05 §4).
// Pass bar: every frame of a 121-frame 24 fps MP4 reachable, step time < 50 ms. Frames carry a 7-bit code
// burned in by orchestrator/spikes/e6_make_clip.py so correctness is verified pixel-wise, not assumed.
import { ALL_FORMATS, CanvasSink, Input, UrlSource } from 'mediabunny'
import { log, report, stats } from './report'

const FPS = 24, N = 121

function readCode(c: HTMLCanvasElement | OffscreenCanvas): number {
  const ctx = (c as HTMLCanvasElement).getContext('2d', { willReadFrequently: true }) as CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D | null
  if (!ctx) return -1
  let v = 0
  for (let b = 0; b < 7; b++) {
    const px = ctx.getImageData(16 + b * 16 + 7, 23, 1, 1).data
    v = (v << 1) | (px[0] > 127 ? 1 : 0)
  }
  return v
}

export async function runE6(mount: HTMLElement, out: HTMLElement) {
  const rows: Record<string, unknown>[] = []
  for (const clip of ['e6_clip.mp4', 'e6_clip_g6.mp4', 'e6_clip_intra.mp4']) {
    try { rows.push(await scrubClip(mount, out, `/spikes/${clip}`)) } catch (e) { log(out, `${clip}: ${(e as Error).message}`) }
  }
  return report({ spike: 'e6', clips: rows }, out)
}

async function scrubClip(mount: HTMLElement, out: HTMLElement, url: string) {
  const input = new Input({ source: new UrlSource(url), formats: ALL_FORMATS })
  const track = await input.getPrimaryVideoTrack()
  if (!track) throw new Error('no video track')
  const canDecode = await track.canDecode()
  const codec = track.codec
  const duration = await input.computeDuration()
  log(out, `E6 ${url}: codec ${codec} ${track.displayWidth}x${track.displayHeight}, duration ${duration.toFixed(3)} s, canDecode=${canDecode}`)
  const view = document.createElement('canvas')
  view.width = track.displayWidth; view.height = track.displayHeight; view.style.width = '512px'
  mount.replaceChildren(view)
  const vctx = view.getContext('2d')!

  const sink = new CanvasSink(track, { poolSize: 3 })
  const step = async (i: number) => {
    const t0 = performance.now()
    const w = await sink.getCanvas((i + 0.5) / FPS)
    const dt = performance.now() - t0
    if (!w) return { dt, code: -1 }
    const code = readCode(w.canvas)
    vctx.drawImage(w.canvas, 0, 0)
    return { dt, code }
  }

  const seq: number[] = []; let seqWrong = 0
  for (let i = 0; i < N; i++) { const r = await step(i); seq.push(r.dt); if (r.code !== i) seqWrong++ }
  const order = Array.from({ length: N }, (_, i) => i).sort(() => Math.random() - 0.5).slice(0, 60)
  const rnd: number[] = []; let rndWrong = 0
  for (const i of order) { const r = await step(i); rnd.push(r.dt); if (r.code !== i) rndWrong++ }
  const back: number[] = []; let backWrong = 0
  for (let i = N - 1; i >= 0; i -= 3) { const r = await step(i); back.push(r.dt); if (r.code !== i) backWrong++ }

  const row = {
    clip: url, codec, frames: N, fps: FPS, canDecode,
    sequential: { ...stats(seq), wrong: seqWrong },
    random_access: { ...stats(rnd), wrong: rndWrong },
    backward_step3: { ...stats(back), wrong: backWrong },
  }
  log(out, `${url} sequential: median ${row.sequential.median} ms p95 ${row.sequential.p95} ms wrong ${seqWrong}/${N} · random: median ${row.random_access.median} ms p95 ${row.random_access.p95} wrong ${rndWrong}/${order.length} · backward: median ${row.backward_step3.median} ms wrong ${backWrong}`)
  return row
}
