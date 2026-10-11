// E13 timeline spike (ArtCraft 08 §7, D74), the browser half: a DOM single lane over e13Lane.ts, measured against 08's bars —
//   1. scrub 10 × 5 s clips at 24 fps with ≤ 1 frame error (every shown frame's burned-in code read back: which clip, which frame);
//   2. smooth trims with 50 clips on the lane (model update + re-layout per trim step, p95 under half a 60 Hz frame);
//   3. one crossfade previewed (the canvas mixes the two clips by the dissolve's weight — checked on pixels);
//   4. EDL + FCPXML export (the files go to engine/spikes/out/e13 through the runner; the Resolve import is the author's check).
// Clips: orchestrator/spikes/e13_make_clips.py → /spikes/e13/c00…c09.mp4 (640×360, 120 frames, GOP 6, 11-bit code: 4 clip + 7 frame).
import { ALL_FORMATS, CanvasSink, Input, UrlSource } from 'mediabunny'
import { at, duration, len, starts, toEDL, toFCPXML, trim, type Lane } from './e13Lane'
import { log, report } from './report'

const FPS = 24, N = 120, W = 640, H = 360, CLIPS = 10

function readCode(ctx: CanvasRenderingContext2D): number {
  let v = 0
  for (let k = 0; k < 11; k++) v = (v << 1) | (ctx.getImageData(8 + k * 16 + 7, 15, 1, 1).data[0] > 127 ? 1 : 0)
  return v
}

class Sources {
  private sinks = new Map<number, CanvasSink>()
  async sink(source: number): Promise<CanvasSink> {
    let s = this.sinks.get(source)
    if (!s) {
      const input = new Input({ source: new UrlSource(`/spikes/e13/c${String(source).padStart(2, '0')}.mp4`), formats: ALL_FORMATS })
      const track = await input.getPrimaryVideoTrack()
      if (!track) throw new Error(`clip ${source}: no video track`)
      s = new CanvasSink(track, { poolSize: 4 })
      this.sinks.set(source, s)
    }
    return s
  }
  async frame(source: number, local: number): Promise<HTMLCanvasElement | OffscreenCanvas | null> {
    const w = await (await this.sink(source)).getCanvas((local + 0.5) / FPS)
    return w ? w.canvas : null
  }
}

/** Draw timeline frame f of the lane into ctx: one clip, or two by the dissolve's weight. */
async function render(lane: Lane, f: number, src: Sources, ctx: CanvasRenderingContext2D, s = starts(lane)): Promise<ReturnType<typeof at>> {
  const what = at(lane, f, s)
  if (!what) return null
  const a = await src.frame(lane.clips[what.a.i].source, what.a.local)
  ctx.globalAlpha = 1
  if (a) ctx.drawImage(a, 0, 0)
  if (what.b) {
    const b = await src.frame(lane.clips[what.b.i].source, what.b.local)
    ctx.globalAlpha = what.mix ?? 0
    if (b) ctx.drawImage(b, 0, 0)
    ctx.globalAlpha = 1
  }
  return what
}

/** The lane as DOM: one absolutely placed block per clip (px per frame), dissolves shaded, a playhead. */
function drawLane(el: HTMLElement, lane: Lane, pxPerFrame: number, playhead: number): void {
  const s = starts(lane)
  const blocks = lane.clips.map((c, i) => {
    const ov = i > 0 ? lane.overlaps[i] : 0
    return `<div class="e13-clip" style="left:${s[i] * pxPerFrame}px;width:${len(c) * pxPerFrame}px;background:hsl(${(c.source * 36) % 360} 45% 40%)">` +
      (ov ? `<i class="e13-ov" style="width:${ov * pxPerFrame}px"></i>` : '') + `<b>${c.id}</b><span class="e13-h l"></span><span class="e13-h r"></span></div>`
  })
  el.innerHTML = blocks.join('') + `<div class="e13-play" style="left:${playhead * pxPerFrame}px"></div>`
  el.style.width = `${duration(lane) * pxPerFrame}px`
}

const pct = (xs: number[], p: number) => { const s = [...xs].sort((a, b) => a - b); return +s[Math.min(s.length - 1, Math.floor(p * s.length))].toFixed(2) }

export async function runE13(mount: HTMLElement, out: HTMLElement) {
  const style = document.createElement('style')
  style.textContent = `.e13-lane{position:relative;height:56px;background:#1a1a1a;margin:8px 0;overflow:hidden}.e13-clip{position:absolute;top:4px;height:48px;border:1px solid #000;box-sizing:border-box;color:#fff;font:11px sans-serif;overflow:hidden}.e13-ov{position:absolute;left:0;top:0;bottom:0;background:repeating-linear-gradient(45deg,#fff3 0 4px,#0000 4px 8px)}.e13-h{position:absolute;top:0;bottom:0;width:6px;background:#fff6}.e13-h.l{left:0}.e13-h.r{right:0}.e13-play{position:absolute;top:0;bottom:0;width:2px;background:#f33}`
  document.head.append(style)
  const view = document.createElement('canvas'); view.width = W; view.height = H; view.style.width = '480px'
  const ctx = view.getContext('2d', { willReadFrequently: true })!
  const laneEl = document.createElement('div'); laneEl.className = 'e13-lane'
  const scroller = document.createElement('div'); scroller.style.cssText = 'width:100%;overflow-x:auto'; scroller.append(laneEl)
  mount.replaceChildren(view, scroller)
  const src = new Sources()
  const result: Record<string, unknown> = { spike: 'e13' }

  // 1 · scrub: 10 clips end to end (1200 frames), a sequential sweep across every cut plus 200 random seeks, each frame's code read back
  const ten: Lane = { fps: FPS, clips: Array.from({ length: CLIPS }, (_, k) => ({ id: `c${k}`, source: k, in: 0, out: N })), overlaps: Array(CLIPS).fill(0) }
  const s10 = starts(ten), total = duration(ten)
  const probe = [...Array.from({ length: total }, (_, f) => f).filter((f) => f % N < 3 || f % N > N - 4), ...Array.from({ length: 200 }, () => Math.floor(Math.random() * total))]
  const errs: number[] = [], times: number[] = []
  let wrongClip = 0
  for (const f of probe) {
    const t0 = performance.now()
    const what = await render(ten, f, src, ctx, s10)
    times.push(performance.now() - t0)
    const code = readCode(ctx), clip = code >> 7, local = code & 127
    if (!what || clip !== ten.clips[what.a.i].source) { wrongClip++; errs.push(Infinity); continue }
    errs.push(Math.abs((s10[what.a.i] + (local - ten.clips[what.a.i].in)) - f))
    drawLane(laneEl, ten, 1, f)
  }
  result.scrub = { frames: probe.length, max_error_frames: Math.max(...errs), over_1_frame: errs.filter((e) => e > 1).length, wrong_clip: wrongClip,
    step_ms_p50: pct(times, 0.5), step_ms_p95: pct(times, 0.95), pass: errs.every((e) => e <= 1) }
  log(out, `scrub: ${JSON.stringify(result.scrub)}`)

  // 2 · trims with 50 clips: 240 trim steps on random clips and edges; each = model update + lane re-layout (forced), timed
  let fifty: Lane = { fps: FPS, clips: Array.from({ length: 50 }, (_, k) => ({ id: `t${k}`, source: k % CLIPS, in: 10, out: 100 })), overlaps: Array.from({ length: 50 }, (_, k) => (k && k % 7 === 0 ? 8 : 0)) }
  drawLane(laneEl, fifty, 0.6, 0)
  const trimMs: number[] = []
  for (let n = 0; n < 240; n++) {
    const t0 = performance.now()
    fifty = trim(fifty, Math.floor(Math.random() * 50), Math.random() < 0.5 ? 'in' : 'out', Math.round((Math.random() - 0.5) * 8), () => N)
    drawLane(laneEl, fifty, 0.6, 0)
    void laneEl.offsetWidth                                            // force the layout the next paint would do
    trimMs.push(performance.now() - t0)
    if (n % 24 === 0) await new Promise(requestAnimationFrame)
  }
  result.trim = { clips: 50, steps: 240, step_ms_p50: pct(trimMs, 0.5), step_ms_p95: pct(trimMs, 0.95), max_ms: pct(trimMs, 1), pass: pct(trimMs, 0.95) <= 8.3 }
  log(out, `trim: ${JSON.stringify(result.trim)}`)

  // 3 · crossfade: clip 0 dissolving into clip 5 over 12 frames; mid-dissolve the canvas must be the weighted mix of the two frames
  const xf: Lane = { fps: FPS, clips: [{ id: 'x0', source: 0, in: 0, out: N }, { id: 'x5', source: 5, in: 0, out: N }], overlaps: [0, 12] }
  const mid = starts(xf)[1] + 6
  const what = await render(xf, mid, src, ctx)
  const px = (c: CanvasRenderingContext2D) => c.getImageData(W - 40, H - 30, 1, 1).data                // background, away from the drifting block
  const solo = document.createElement('canvas'); solo.width = W; solo.height = H
  const sctx = solo.getContext('2d', { willReadFrequently: true })!
  sctx.drawImage((await src.frame(0, what!.a.local))!, 0, 0); const pa = px(sctx)
  sctx.drawImage((await src.frame(5, what!.b!.local))!, 0, 0); const pb = px(sctx)
  const got = px(ctx), m = what!.mix!
  const want = [0, 1, 2].map((k) => pa[k] * (1 - m) + pb[k] * m)
  const off = Math.max(...[0, 1, 2].map((k) => Math.abs(got[k] - want[k])))
  result.crossfade = { frame: mid, mix: +m.toFixed(3), off_by: +off.toFixed(1), pass: !!what?.b && off <= 4 }
  drawLane(laneEl, xf, 2, mid)
  log(out, `crossfade: ${JSON.stringify(result.crossfade)}`)

  // 4 · export: the scrub lane with two dissolves → EDL and FCPXML (the runner saves them; Resolve imports them by hand)
  const exp: Lane = { ...ten, overlaps: ten.overlaps.map((_, k) => (k === 3 || k === 7 ? 12 : 0)) }
  const media = (s: number) => ({ name: `c${String(s).padStart(2, '0')}.mp4`, src: `file:///F:/source/repos/stubz003_loom2/frontend/public/spikes/e13/c${String(s).padStart(2, '0')}.mp4`, frames: N })
  const edl = toEDL(exp, 'loom2 E13', (s) => `C${String(s).padStart(2, '0')}`)
  const fcpxml = toFCPXML(exp, 'loom2 E13', media, W, H)
  const doc = new DOMParser().parseFromString(fcpxml, 'application/xml')
  result.export = { duration_frames: duration(exp), edl_lines: edl.split('\n').length, fcpxml_ok: !doc.querySelector('parsererror'), transitions: doc.querySelectorAll('transition').length }
  ;(window as unknown as { __e13Files?: Record<string, string> }).__e13Files = { 'e13.edl': edl, 'e13.fcpxml': fcpxml }
  log(out, `export: ${JSON.stringify(result.export)}`)
  ;(window as unknown as { __e13?: unknown }).__e13 = result
  return report(result as { spike: string }, out)
}
