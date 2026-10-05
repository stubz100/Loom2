// E3 brush worker (FastMask pattern): owns an OffscreenCanvas, stamps dabs from the main thread's pointer
// stream inside its own rAF loop, and reports per-dab latency (event time → frame commit) back.
type Pt = { x: number; y: number; p: number; t: number } // t = absolute ms (timeOrigin + now)

let ctx: OffscreenCanvasRenderingContext2D | null = null
let queue: Pt[] = []
let pending: { t: number }[] = [] // dabs drawn in the last frame, resolved at the next frame start (= commit)
let drawn = 0
let frames = 0
const latencies: number[] = []
let brush: OffscreenCanvas | null = null
const RADIUS = 24

function makeBrush() {
  brush = new OffscreenCanvas(RADIUS * 2, RADIUS * 2)
  const b = brush.getContext('2d')!
  const g = b.createRadialGradient(RADIUS, RADIUS, 0, RADIUS, RADIUS, RADIUS)
  g.addColorStop(0, 'rgba(240,168,50,0.9)')
  g.addColorStop(0.7, 'rgba(240,168,50,0.5)')
  g.addColorStop(1, 'rgba(240,168,50,0)')
  b.fillStyle = g
  b.fillRect(0, 0, RADIUS * 2, RADIUS * 2)
}

function frame() {
  const now = performance.timeOrigin + performance.now()
  for (const d of pending) latencies.push(now - d.t) // previous frame is on screen now
  pending = []
  if (ctx && queue.length) {
    const q = queue
    queue = []
    for (const p of q) {
      const s = 0.5 + p.p * 0.8
      ctx.globalAlpha = 0.35 + p.p * 0.5
      ctx.drawImage(brush!, p.x - RADIUS * s, p.y - RADIUS * s, RADIUS * 2 * s, RADIUS * 2 * s)
      drawn++
      pending.push({ t: p.t })
    }
  }
  frames++
  requestAnimationFrame(frame)
}

self.onmessage = (e: MessageEvent) => {
  const m = e.data
  if (m.type === 'init') {
    const c = m.canvas as OffscreenCanvas
    ctx = c.getContext('2d', { desynchronized: true, alpha: false }) as OffscreenCanvasRenderingContext2D
    ctx.fillStyle = '#2b2b2b'
    ctx.fillRect(0, 0, c.width, c.height)
    makeBrush()
    requestAnimationFrame(frame)
  } else if (m.type === 'pts') {
    queue.push(...(m.pts as Pt[]))
  } else if (m.type === 'stats') {
    ;(self as unknown as Worker).postMessage({ type: 'stats', drawn, frames, latencies: latencies.splice(0) })
  }
}
