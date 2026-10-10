// S2 spike benchmark (PE6): PhotoCraft's Quick Selection and Magnetic Lasso as wasm32 (frontend/wasm/pcwasm, committed as smartselect/pcwasm.wasm), run in a worker
// thread of Node — the same V8 as Edge / WebView2 — on a raw RGBA image: module size, instantiation, per-stroke latency.
// Usage: node scripts/s2_wasm_bench.mjs <image.rgba> <w> <h> [wasm path]
import { readFileSync } from 'node:fs'
import { gzipSync } from 'node:zlib'
import { Worker, isMainThread, parentPort, workerData } from 'node:worker_threads'

if (isMainThread) {
  const [img, w, h, wasm = 'frontend/src/suites/edit/smartselect/pcwasm.wasm'] = process.argv.slice(2)
  const bytes = readFileSync(wasm)
  console.log(`module ${bytes.length} B, gzip -9 ${gzipSync(bytes, { level: 9 }).length} B`)
  const wk = new Worker(new URL(import.meta.url), { workerData: { img, w: Number(w), h: Number(h), wasm } })
  wk.on('message', (m) => console.log(m))
  wk.on('error', (e) => { console.error(e); process.exit(1) })
} else {
  const { img, w, h, wasm } = workerData
  const t0 = performance.now()
  const { instance } = await WebAssembly.instantiate(readFileSync(wasm), {})
  const X = instance.exports
  const tInst = performance.now() - t0
  const mem = () => new Uint8Array(X.memory.buffer)
  const rgba = readFileSync(img)
  let t = performance.now()
  const p = X.alloc(rgba.length); mem().set(rgba, p); X.set_image(p, w, h); X.dealloc(p, rgba.length)
  const tSet = performance.now() - t
  const stroke = (pts, size) => {
    const q = X.alloc(pts.length * 4)
    new Float32Array(X.memory.buffer, q, pts.length).set(pts)
    const s = performance.now(); const ok = X.quick(q, pts.length / 2, size); const dt = performance.now() - s
    X.dealloc(q, pts.length * 4)
    const box = ok ? [0, 1, 2, 3].map((i) => X.region_box(i)) : null
    return { dt, area: box ? (box[2] - box[0]) * (box[3] - box[1]) : 0, box }
  }
  const out = [`${w}×${h}: instantiate ${tInst.toFixed(1)} ms, set image ${tSet.toFixed(1)} ms`]
  // clicks at five places with a 30 px brush, then a 15-point drag (like Photoshop's Quick Selection)
  const clicks = [[0.3, 0.4], [0.5, 0.5], [0.7, 0.3], [0.2, 0.8], [0.8, 0.75]].map(([fx, fy]) => stroke([fx * w, fy * h], 30))
  out.push(`quick select click (30 px brush): ${clicks.map((c) => c.dt.toFixed(0)).join(' / ')} ms; boxes ${clicks.map((c) => c.box ? `${c.box[2] - c.box[0]}×${c.box[3] - c.box[1]}` : '-').join(', ')}`)
  const drag = []; for (let i = 0; i < 15; i++) drag.push(w * (0.35 + i * 0.01), h * (0.45 + Math.sin(i / 3) * 0.02))
  const d = stroke(drag, 40)
  out.push(`quick select drag (15 points, 40 px brush): ${d.dt.toFixed(0)} ms; box ${d.box ? `${d.box[2] - d.box[0]}×${d.box[3] - d.box[1]}` : '-'}`)
  const big = stroke([0.5 * w, 0.5 * h], 200)
  out.push(`quick select click (200 px brush): ${big.dt.toFixed(0)} ms; box ${big.box ? `${big.box[2] - big.box[0]}×${big.box[3] - big.box[1]}` : '-'}`)
  // magnetic lasso: eight ~120 px segments (each call is one pointer move's worth of tracing in the tool)
  const segs = []
  let a = [0.25 * w, 0.3 * h]
  for (let i = 0; i < 8; i++) {
    const b = [a[0] + 120 * Math.cos(i * 0.6), a[1] + 120 * Math.sin(i * 0.6)]
    t = performance.now(); const n = X.trace(a[0], a[1], b[0], b[1], 10, 0.1); segs.push({ dt: performance.now() - t, n })
    a = b
  }
  out.push(`magnetic lasso 120 px segment: first ${segs[0].dt.toFixed(1)} ms, then ${segs.slice(1).map((s) => s.dt.toFixed(1)).join(' / ')} ms (${segs.map((s) => s.n).join(', ')} points)`)
  parentPort.postMessage(out.join('\n'))
}
