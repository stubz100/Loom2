// E35c's browser half (engine/spikes/e35c_fill.py runs it), D132 — the plate as *project and fill*. A keyframe every 8th frame: the three
// keyframes before it projected into its camera at the still's size (the most recent first, a pixel from the first that saw it — the
// projector's coverage mode), and what none of them saw filled by Klein's Fill on an Edit document (import, document, selection, Fill,
// flatten — the API). The frames between keyframes: the nearest keyframes projected the same way at the final's size, the frame's own
// holes left to the nearest keyframe's clamped colour. Prints one JSON line {keys, frames (blob shas), keyframe_holes, frame_holes, fills}.
const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')
const [stageId, finalId, firstStill, seed, prompt, outDir, everyArg, expandArg, featherArg, grazeArg] = process.argv.slice(2)
const API = 'http://127.0.0.1:8792', TOKEN = 'e28'
const H = { 'X-Loom-Token': TOKEN, 'Content-Type': 'application/json' }
const api = async (m, p, b, raw) => {
  const r = await fetch(API + p, { method: m, headers: raw ? { 'X-Loom-Token': TOKEN, 'Content-Type': 'application/octet-stream' } : H, body: raw ?? (b ? JSON.stringify(b) : undefined) })
  if (!r.ok) throw new Error(`${m} ${p} ${r.status} ${await r.text()}`)
  return r.json()
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const waitJob = async (id) => { for (;;) { const j = (await api('GET', '/jobs')).items.find((x) => x.id === id); if (j && ['done', 'failed', 'cancelled'].includes(j.status)) return j; await sleep(1500) } }
const KW = 1280, KH = 720, EVERY = Number(everyArg || 8), EXPAND = Number(expandArg || 6), FEATHER = Number(featherArg || 8), GRAZE = Number(grazeArg || 0.17)
;(async () => {
  const f = await api('GET', `/finals/${finalId}`)
  fs.mkdirSync(path.join(outDir, 'keys'), { recursive: true })
  const browser = await chromium.launch({ channel: 'msedge', headless: false, args: ['--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding', '--disable-background-timer-throttling'] })
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } })
  page.on('console', (m) => { if (m.type() === 'error') console.error('page:', m.text()) })
  await page.goto(`http://127.0.0.1:1420/?token=${TOKEN}&port=8792&suite=stage`)
  await page.waitForFunction(() => !!window.__loom2Stage, null, { timeout: 60000 })
  await page.evaluate(async (id) => { await window.__loom2Stage.open(id) }, stageId)
  await page.locator('canvas.stage-canvas').waitFor({ timeout: 30000 })
  await sleep(2500)
  // in the page: project a stack of keyframes ({asset, frame}, the first wins where it saw the pixel) into the given frames
  await page.evaluate(async ({ f, GRAZE }) => {
    const fsh = await import('/src/suites/stage/finalShot.ts')
    const an = await import('/src/suites/stage/anim.ts')
    const ss = await import('/src/suites/stage/stageStore.ts')
    const cl = await import('/src/api/client.ts')
    const st = () => ss.useStage.getState()
    if (!st().plateProjector) (await import('/src/suites/stage/headless.ts')).ensureHeadless()
    const doc = st().current
    const times = fsh.framesAt(f.range.start, f.range.end, f.rate)
    const camOf = (d) => d.cameras.find((c) => c.id === f.camera_id) ?? d.cameras[0]
    const frames = times.map((t) => { const d = an.sampleDoc(doc, t); return { cam: camOf(d), doc: d } })
    const restore = an.sampleDoc(doc, st().frame)
    const images = {}
    const load = (id) => images[id] ??= new Promise((res, rej) => { const im = new Image(); im.crossOrigin = 'anonymous'; im.onload = () => res(im); im.onerror = () => rej(new Error(`${id} did not load`)); im.src = cl.api.assetUrl(id) })
    const pixels = async (blob, w, h) => { const c = new OffscreenCanvas(w, h), g = c.getContext('2d'); g.drawImage(await createImageBitmap(blob), 0, 0); return g.getImageData(0, 0, w, h) }
    const b64 = (u8) => { let s = ''; for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode(...u8.subarray(i, i + 0x8000)); return btoa(s) }
    window.__e35c = async (idx, w, h, stack, upload) => {
      const sel = idx.map((i) => frames[i])
      const layers = []
      for (const k of stack) {
        const im = await load(k.asset)
        const colour = await st().plateProjector(sel, w, h, im, frames[k.frame].cam, im.naturalWidth / im.naturalHeight, restore)
        const cover = await st().plateProjector(sel, w, h, im, frames[k.frame].cam, im.naturalWidth / im.naturalHeight, restore, undefined, GRAZE)
        layers.push({ colour, cover })
      }
      const out = []
      for (let i = 0; i < sel.length; i++) {
        const base = await pixels(layers[0].colour[i], w, h)                 // the nearest keyframe's colour, clamped where none saw
        const hole = new Uint8Array(w * h).fill(255)
        for (const L of layers) {
          const col = await pixels(L.colour[i], w, h), cov = await pixels(L.cover[i], w, h)
          for (let p = 0; p < w * h; p++) if (hole[p] && cov.data[p * 4] > 127) { hole[p] = 0; base.data.set(col.data.subarray(p * 4, p * 4 + 4), p * 4) }
        }
        const c = new OffscreenCanvas(w, h); c.getContext('2d').putImageData(base, 0, 0)
        const png = await c.convertToBlob({ type: 'image/png' })
        const holes = hole.reduce((a, v) => a + (v ? 1 : 0), 0) / (w * h)
        if (upload) { const sha = await cl.sha256Hex(await png.arrayBuffer()); await cl.api.putBlob(sha, png); out.push({ sha, holes }) }
        else out.push({ png: b64(new Uint8Array(await png.arrayBuffer())), mask: b64(hole), holes })
      }
      return out
    }
  }, { f, GRAZE })
  const n = f.frames
  const keys = { 0: firstStill }
  const keyHoles = { 0: 0 }, fills = []
  for (let k = EVERY; k < n; k += EVERY) {
    const before = Object.keys(keys).map(Number).sort((a, b) => b - a).slice(0, 3)
    const t0 = Date.now()
    const [r] = await page.evaluate(({ k, stack }) => window.__e35c([k], 1280, 720, stack, false), { k, stack: before.map((j) => ({ asset: keys[j], frame: j })) })
    const pngPath = path.join(outDir, 'keys', `${String(k).padStart(4, '0')}-projected.png`)
    fs.writeFileSync(pngPath, Buffer.from(r.png, 'base64'))
    keyHoles[k] = r.holes
    const imported = (await api('POST', '/assets/import', { paths: [pngPath], suite: 'stage' })).items[0].id
    if (r.holes < 0.002) { keys[k] = imported; fills.push({ k, holes: r.holes, s: (Date.now() - t0) / 1000, fill: false }); console.error(`key ${k}: nothing new`); continue }
    const docRec = await api('POST', '/documents', { from_asset: imported, name: `E35c key ${k}` })
    await api('PUT', `/documents/${docRec.id}/selection?w=${KW}&h=${KH}`, null, Buffer.from(r.mask, 'base64'))
    const sub = await api('POST', `/documents/${docRec.id}/ai`, { recipe: { kind: 'inpaint', mode: 'fill', prompt_text: prompt, seeds: [Number(seed)], expand: EXPAND, feather: FEATHER }, stage: false })
    const j = await waitJob(sub.jobs[0].id)
    if (j.status !== 'done') throw new Error(`key ${k}: the Fill ${j.status}: ${j.error}`)
    const flat = await api('POST', `/documents/${docRec.id}/flatten`, { to_catalogue: true, name: `E35c key ${k}` })
    await api('POST', `/documents/${docRec.id}/close`)
    keys[k] = flat.asset.id
    fills.push({ k, holes: r.holes, s: (Date.now() - t0) / 1000, fill_s: j.wall_s, fill: true })
    console.error(`key ${k}: ${(r.holes * 100).toFixed(1)} % filled, ${j.wall_s} s`)
  }
  // the frames: each from the keyframes around it, the nearer first, then the one before those
  const ks = Object.keys(keys).map(Number).sort((a, b) => a - b)
  const frames = new Array(n), frameHoles = new Array(n)
  for (let s = 0; s < ks.length; s++) {
    const a = ks[s], b = ks[s + 1]
    const span = b === undefined ? [a, n - 1] : [a, b - 1]
    for (const half of [0, 1]) {
      const mid = b === undefined ? span[1] : a + Math.floor((b - a) / 2)
      const idx = []
      for (let i = half ? mid + 1 : span[0]; i <= (half ? span[1] : Math.min(mid, span[1])); i++) idx.push(i)
      if (!idx.length) continue
      const order = (half && b !== undefined ? [b, a] : b !== undefined ? [a, b] : [a]).concat(ks.filter((x) => x < a).reverse().slice(0, 1))
      const out = await page.evaluate(({ idx, stack, w, h }) => window.__e35c(idx, w, h, stack, true), { idx, stack: order.map((j) => ({ asset: keys[j], frame: j })), w: f.size.w, h: f.size.h })
      out.forEach((o, i) => { frames[idx[i]] = o.sha; frameHoles[idx[i]] = o.holes })
    }
  }
  console.log(JSON.stringify({ keys, frames, keyframe_holes: keyHoles, frame_holes: frameHoles, fills }))
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
