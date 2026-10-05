// E3 — brush latency on a 2K preview canvas driven by a worker (12 §1 E3, 05 §3b, D19 mouse-first).
// Pass bar: ≤ 1 frame visible lag at 2K preview, no dropped dabs at fast strokes.
// Synthetic mode replays a fast Lissajous stroke at 240 events/s × 4 coalesced points through the same
// enqueue path the real pointer handler uses; interactive mode (move the mouse over the canvas) is always on.
import { log, report, stats } from './report'

type Pt = { x: number; y: number; p: number; t: number }

export async function runE3(mount: HTMLElement, out: HTMLElement, opts: { synthetic?: boolean; seconds?: number }) {
  const { synthetic = true, seconds = 5 } = opts
  const W = 2048, H = 1152
  const canvas = document.createElement('canvas')
  canvas.width = W; canvas.height = H
  canvas.style.width = '100%'; canvas.style.maxWidth = `${W}px`; canvas.style.touchAction = 'none'; canvas.style.cursor = 'crosshair'
  mount.replaceChildren(canvas)
  const off = canvas.transferControlToOffscreen()
  const worker = new Worker(new URL('./brushWorker.ts', import.meta.url), { type: 'module' })
  worker.postMessage({ type: 'init', canvas: off }, [off])

  let sent = 0, events = 0
  const abs = (ts: number) => performance.timeOrigin + ts
  const enqueue = (pts: Pt[]) => { sent += pts.length; worker.postMessage({ type: 'pts', pts }) }
  const toCanvas = (ev: PointerEvent) => {
    const r = canvas.getBoundingClientRect()
    return { x: (ev.clientX - r.left) * (W / r.width), y: (ev.clientY - r.top) * (H / r.height), p: ev.pressure || 0.5, t: abs(ev.timeStamp) }
  }
  const onMove = (ev: PointerEvent) => {
    events++
    const co = typeof ev.getCoalescedEvents === 'function' ? ev.getCoalescedEvents() : []
    enqueue((co.length ? co : [ev]).map(toCanvas))
  }
  const rawName = 'onpointerrawupdate' in canvas ? 'pointerrawupdate' : 'pointermove'
  canvas.addEventListener(rawName, onMove as EventListener)
  log(out, `E3 canvas ${W}x${H}, worker OffscreenCanvas 2D desynchronized, listening on ${rawName} (move the mouse to paint)`)

  // display refresh estimate
  const refresh = await new Promise<number>((res) => {
    const ts: number[] = []
    const f = (t: number) => { ts.push(t); if (ts.length < 40) requestAnimationFrame(f); else res(1000 / ((ts[39] - ts[0]) / 39)) }
    requestAnimationFrame(f)
  })

  let synthRows: Record<string, unknown> | null = null
  if (synthetic) {
    const hz = 240, perEvent = 4, n = hz * seconds
    let i = 0
    const t0 = performance.now()
    await new Promise<void>((done) => {
      const timer = setInterval(() => {
        const pts: Pt[] = []
        for (let k = 0; k < perEvent; k++) {
          const u = (i * perEvent + k) / (n * perEvent) * Math.PI * 2 * 3
          pts.push({ x: W / 2 + Math.sin(u * 2.1) * W * 0.42, y: H / 2 + Math.cos(u * 1.3) * H * 0.42, p: 0.3 + 0.7 * Math.abs(Math.sin(u * 5)), t: abs(performance.now()) })
        }
        events++
        enqueue(pts)
        if (++i >= n) { clearInterval(timer); done() }
      }, 1000 / hz)
    })
    const elapsed = (performance.now() - t0) / 1000
    await new Promise((r) => setTimeout(r, 300))
    const st = await new Promise<{ drawn: number; frames: number; latencies: number[] }>((res) => {
      worker.onmessage = (e) => res(e.data)
      worker.postMessage({ type: 'stats' })
    })
    const lat = stats(st.latencies)
    const frameMs = 1000 / refresh
    synthRows = {
      events, points_sent: sent, dabs_drawn: st.drawn, dropped: sent - st.drawn, seconds: +elapsed.toFixed(2),
      achieved_event_hz: +(events / elapsed).toFixed(0), worker_fps: +(st.frames / elapsed).toFixed(0), display_hz: +refresh.toFixed(0),
      latency_ms: lat, latency_frames_median: +(lat.median / frameMs).toFixed(2), latency_frames_p95: +(lat.p95 / frameMs).toFixed(2),
    }
    log(out, `synthetic stroke: ${sent} points, ${st.drawn} dabs drawn (${sent - st.drawn} dropped), event rate ${(events / elapsed).toFixed(0)}/s, latency median ${lat.median} ms (${(lat.median / frameMs).toFixed(2)} frames) p95 ${lat.p95} ms`)
  }
  return report({ spike: 'e3', canvas: [W, H], listener: rawName, synthetic: synthRows }, out)
}
