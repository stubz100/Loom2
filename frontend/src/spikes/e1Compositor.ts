// E1 — PixiJS v8 layer compositor benchmark (12 §1 E1, 05 §3b).
// Pass bar: 60 fps compositing 6 × 4K layers with 3 advanced blend modes + a mask, on WebGPU and on WebGL2.
import { Application, Container, Graphics, RendererType, RenderTexture, Sprite } from 'pixi.js'
import 'pixi.js/advanced-blend-modes'
import { log, report, stats } from './report'

type Pref = 'webgpu' | 'webgl'
const MODES = ['normal', 'multiply', 'screen', 'overlay', 'soft-light', 'difference'] as const

function paintLayer(app: Application, size: number, seed: number): RenderTexture {
  const rt = RenderTexture.create({ width: size, height: size })
  const g = new Graphics()
  let s = seed * 9301 + 49297
  const rnd = () => ((s = (s * 9301 + 49297) % 233280) / 233280)
  g.rect(0, 0, size, size).fill({ color: (0x203040 + seed * 0x152030) & 0xffffff, alpha: seed === 0 ? 1 : 0.35 })
  for (let i = 0; i < 160; i++) {
    g.circle(rnd() * size, rnd() * size, 60 + rnd() * size * 0.12).fill({ color: Math.floor(rnd() * 0xffffff), alpha: 0.55 })
  }
  for (let i = 0; i < 40; i++) {
    g.rect(rnd() * size, rnd() * size, 200 + rnd() * 900, 20 + rnd() * 160).fill({ color: Math.floor(rnd() * 0xffffff), alpha: 0.4 })
  }
  app.renderer.render({ container: g, target: rt })
  g.destroy()
  return rt
}

export async function runE1(mount: HTMLElement, out: HTMLElement, opts: { preference: Pref; layers?: number; size?: number; seconds?: number }) {
  const { preference, layers = 6, size = 4096, seconds = 6 } = opts
  const app = new Application()
  const w = Math.max(640, window.innerWidth), h = Math.max(480, window.innerHeight - 140)
  await app.init({ preference, width: w, height: h, antialias: false, resolution: 1, powerPreference: 'high-performance', background: 0x202020 })
  mount.replaceChildren(app.canvas)
  const renderer = app.renderer.type === RendererType.WEBGPU ? 'webgpu' : app.renderer.type === RendererType.WEBGL ? 'webgl' : `type-${app.renderer.type}`
  log(out, `E1 renderer=${renderer} viewport=${w}x${h} layers=${layers} size=${size}² modes=${MODES.join(',')}`)

  const t0 = performance.now()
  const world = new Container()
  const sprites: Sprite[] = []
  for (let i = 0; i < layers; i++) {
    const sp = new Sprite(paintLayer(app, size, i))
    sp.blendMode = MODES[i % MODES.length]
    sp.position.set(i * 37, i * 23)
    world.addChild(sp)
    sprites.push(sp)
  }
  const mask = new Graphics().circle(size / 2, size / 2, size * 0.42).fill(0xffffff)
  world.addChild(mask)
  sprites[3].mask = mask
  app.stage.addChild(world)
  const buildMs = performance.now() - t0
  log(out, `layers built in ${buildMs.toFixed(0)} ms (GPU textures ≈ ${(layers * size * size * 4 / 2 ** 20).toFixed(0)} MiB)`)

  const phases = [
    { name: 'fit', scale: Math.min(w, h) / size },
    { name: '1:1', scale: 1 },
    { name: 'zoom-2x', scale: 2 },
  ]
  const results: Record<string, unknown> = {}
  for (const ph of phases) {
    const frames: number[] = []
    let t = 0
    const tick = () => {
      t += 1 / 60
      world.scale.set(ph.scale)
      world.position.set((w - size * ph.scale) / 2 + Math.sin(t * 1.3) * 120 * ph.scale, (h - size * ph.scale) / 2 + Math.cos(t * 0.9) * 90 * ph.scale)
      frames.push(app.ticker.deltaMS)
    }
    app.ticker.add(tick)
    await new Promise((r) => setTimeout(r, seconds * 1000))
    app.ticker.remove(tick)
    const st = stats(frames.slice(10))
    const fps = +(1000 / (frames.slice(10).reduce((a, b) => a + b, 0) / Math.max(1, frames.length - 10))).toFixed(1)
    results[ph.name] = { fps, frame_ms: st }
    log(out, `phase ${ph.name}: ${fps} fps · frame ms median ${st.median} p95 ${st.p95} max ${st.max}`)
  }
  app.ticker.stop()

  // vsync-independent throughput: render back-to-back and wait for GPU completion each time
  // (the rig's display runs at 29–30 Hz, so rAF-paced fps cannot show the real compositing cost)
  const gpu = (app.renderer as unknown as { gpu?: { device?: GPUDevice } }).gpu
  const gl = (app.renderer as unknown as { gl?: WebGL2RenderingContext }).gl
  const px = new Uint8Array(4)
  const sync = async () => { if (gpu?.device) await gpu.device.queue.onSubmittedWorkDone(); else if (gl) gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px) }
  for (const ph of phases) {
    world.scale.set(ph.scale)
    world.position.set((w - size * ph.scale) / 2, (h - size * ph.scale) / 2)
    app.render(); await sync()
    const times: number[] = []
    for (let i = 0; i < 60; i++) {
      world.position.x += Math.sin(i) * 2
      const t0 = performance.now()
      app.render(); await sync()
      times.push(performance.now() - t0)
    }
    const st = stats(times)
    ;(results[ph.name] as Record<string, unknown>).throughput = { fps_equiv: +(1000 / st.median).toFixed(0), render_ms: st }
    log(out, `phase ${ph.name} throughput (no vsync): ${(1000 / st.median).toFixed(0)} fps-equivalent · render+complete ms median ${st.median} p95 ${st.p95}`)
  }

  // offscreen variant: composite into a viewport-sized RenderTexture instead of the canvas, so the measure cannot be
  // tied to swap-chain acquisition (in WebView2 the canvas path reports exactly one vsync per render)
  const offRt = RenderTexture.create({ width: w, height: h })
  const syncOff = async () => { if (gpu?.device) await gpu.device.queue.onSubmittedWorkDone(); else if (gl) gl.finish() }
  for (const ph of phases) {
    world.scale.set(ph.scale)
    world.position.set((w - size * ph.scale) / 2, (h - size * ph.scale) / 2)
    app.renderer.render({ container: app.stage, target: offRt }); await syncOff()
    const times: number[] = []
    for (let i = 0; i < 60; i++) {
      world.position.x += Math.sin(i) * 2
      const t0 = performance.now()
      app.renderer.render({ container: app.stage, target: offRt }); await syncOff()
      times.push(performance.now() - t0)
    }
    const st = stats(times)
    ;(results[ph.name] as Record<string, unknown>).throughput_offscreen = { fps_equiv: +(1000 / st.median).toFixed(0), render_ms: st }
    log(out, `phase ${ph.name} offscreen throughput: ${(1000 / st.median).toFixed(0)} fps-equivalent · ms median ${st.median} p95 ${st.p95}`)
  }
  offRt.destroy(true)
  const row = await report({ spike: 'e1', renderer, preference, layers, size, modes: MODES, mask: true, build_ms: +buildMs.toFixed(0), viewport: [w, h], phases: results }, out)
  app.destroy(true, { children: true, texture: true })
  return row
}
