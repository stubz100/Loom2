// E35d's browser half (engine/spikes/e35d_run.py runs it), D133 — project and fill for any large move. Stage's coverage pass gives each
// pixel the cosine at which a keyframe saw it (0 outside its frustum); a frame's pixel comes from the keyframe that saw it most head-on.
// A pixel is *bad* when no keyframe saw it (cosine below SEEN) or the frame sees it more than MAG times as head-on as the best keyframe
// did while that one saw it below FILL (it would be magnified: soft, stretched). Keyframes are placed where the move needs them: walking on
// from the last keyframe, a frame whose bad share passes UNSEEN becomes the next keyframe and its bad pixels are filled by Klein's Fill on
// an Edit document (import, document, selection, Fill, flatten — the API). Prints one JSON line {keys, frames, frame_bad, fills, probes}.
const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')
const [stageId, finalId, firstStill, seed, prompt, outDir, unseenArg, seenArg, fillArg, magArg] = process.argv.slice(2)
const API = 'http://127.0.0.1:8792', TOKEN = 'e28'
const H = { 'X-Loom-Token': TOKEN, 'Content-Type': 'application/json' }
const api = async (m, p, b, raw) => {
  const r = await fetch(API + p, { method: m, headers: raw ? { 'X-Loom-Token': TOKEN, 'Content-Type': 'application/octet-stream' } : H, body: raw ?? (b ? JSON.stringify(b) : undefined) })
  if (!r.ok) throw new Error(`${m} ${p} ${r.status} ${await r.text()}`)
  return r.json()
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const waitJob = async (id) => { for (;;) { const j = (await api('GET', '/jobs')).items.find((x) => x.id === id); if (j && ['done', 'failed', 'cancelled'].includes(j.status)) return j; await sleep(1500) } }
const KW = 1280, KH = 720, PW = 320, PH = 180
const UNSEEN = Number(unseenArg || 0.03), SEEN = Number(seenArg || 0.05), FILL = Number(fillArg || 0.34), MAG = Number(magArg || 2), EXPAND = 48, FEATHER = 32, STACK = 3
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
  await page.evaluate(async (f) => {
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
    // the stack's best view of each pixel: {cos (0–255), the layer}; colour: the best layer's colour (the first layer's clamped where none saw)
    window.__e35d = async (idx, w, h, stack, opts) => {
      const sel = idx.map((i) => frames[i])
      const own = await load(stack[0].asset)                                 // any picture: only the frame's own cosine is read
      const selfAt = sel.length > 1 ? null : await st().plateProjector(sel, w, h, own, sel[0].cam, w / h, restore, undefined, true)
      const layers = []
      for (const k of stack) {
        const im = await load(k.asset)
        const cover = await st().plateProjector(sel, w, h, im, frames[k.frame].cam, im.naturalWidth / im.naturalHeight, restore, undefined, true)
        const colour = opts.probe ? null : await st().plateProjector(sel, w, h, im, frames[k.frame].cam, im.naturalWidth / im.naturalHeight, restore)
        layers.push({ colour, cover })
      }
      const out = []
      for (let i = 0; i < sel.length; i++) {
        const best = new Uint8Array(w * h), who = new Int8Array(w * h).fill(-1)
        for (let li = 0; li < layers.length; li++) {
          const cov = await pixels(layers[li].cover[i], w, h)
          for (let p = 0; p < w * h; p++) { const v = cov.data[p * 4]; if (v > best[p]) { best[p] = v; who[p] = li } }
        }
        const me = selfAt ? await pixels(selfAt[0], w, h) : await pixels((await st().plateProjector([sel[i]], w, h, own, sel[i].cam, w / h, restore, undefined, true))[0], w, h)
        const bad = new Uint8Array(w * h)
        let nbad = 0
        for (let p = 0; p < w * h; p++) {
          const b = best[p], m = me.data[p * 4]
          if (b < opts.seen * 255 || (b < opts.fill * 255 && m > opts.mag * Math.max(b, 1))) { bad[p] = 255; nbad++ }
        }
        if (opts.probe) { out.push({ bad: nbad / (w * h) }); continue }
        const cols = []
        for (const L of layers) cols.push(await pixels(L.colour[i], w, h))
        const img = new ImageData(w, h)
        img.data.set(cols[0].data)
        for (let p = 0; p < w * h; p++) if (who[p] > 0 && best[p] >= opts.seen * 255) img.data.set(cols[who[p]].data.subarray(p * 4, p * 4 + 4), p * 4)
        const c = new OffscreenCanvas(w, h); c.getContext('2d').putImageData(img, 0, 0)
        const png = await c.convertToBlob({ type: 'image/png' })
        if (opts.upload) { const sha = await cl.sha256Hex(await png.arrayBuffer()); await cl.api.putBlob(sha, png); out.push({ sha, bad: nbad / (w * h) }); continue }
        out.push({ png: b64(new Uint8Array(await png.arrayBuffer())), mask: b64(bad), bad: nbad / (w * h) })
      }
      return out
    }
  }, f)
  const n = f.frames
  const keys = { 0: firstStill }
  const fills = [], probes = []
  const stackAt = (before) => Object.keys(keys).map(Number).filter((k) => k <= before).sort((a, b) => b - a).slice(0, STACK).map((j) => ({ asset: keys[j], frame: j }))
  let last = 0
  for (let t = 1; t < n; t++) {
    const O = { seen: SEEN, fill: FILL, mag: MAG }
    const [p] = await page.evaluate(({ t, stack, w, h, O }) => window.__e35d([t], w, h, stack, { ...O, probe: true }), { t, stack: stackAt(last), w: PW, h: PH, O })
    probes.push({ t, bad: p.bad })
    if (p.bad <= UNSEEN && t < n - 1) continue
    const k = t                                                      // the first frame past the share — and the last frame (the move's end)
    const t0 = Date.now()
    const [r] = await page.evaluate(({ k, stack, O }) => window.__e35d([k], 1280, 720, stack, O), { k, stack: stackAt(last), O })
    const pngPath = path.join(outDir, 'keys', `${String(k).padStart(4, '0')}-projected.png`)
    fs.writeFileSync(pngPath, Buffer.from(r.png, 'base64'))
    const imported = (await api('POST', '/assets/import', { paths: [pngPath], suite: 'stage' })).items[0].id
    if (r.bad < 0.002) { keys[k] = imported; fills.push({ k, filled: r.bad, fill: false }); last = k; continue }
    const docRec = await api('POST', '/documents', { from_asset: imported, name: `E35d key ${k}` })
    await api('PUT', `/documents/${docRec.id}/selection?w=${KW}&h=${KH}`, null, Buffer.from(r.mask, 'base64'))
    const sub = await api('POST', `/documents/${docRec.id}/ai`, { recipe: { kind: 'inpaint', mode: 'fill', prompt_text: prompt, seeds: [Number(seed)], expand: EXPAND, feather: FEATHER }, stage: false })
    const j = await waitJob(sub.jobs[0].id)
    if (j.status !== 'done') throw new Error(`key ${k}: the Fill ${j.status}: ${j.error}`)
    const flat = await api('POST', `/documents/${docRec.id}/flatten`, { to_catalogue: true, name: `E35d key ${k}` })
    await api('POST', `/documents/${docRec.id}/close`)
    keys[k] = flat.asset.id
    fills.push({ k, filled: r.bad, s: (Date.now() - t0) / 1000, fill_s: j.wall_s, fill: true })
    console.error(`key ${k}: ${(r.bad * 100).toFixed(1)} % filled, ${j.wall_s} s`)
    last = k
  }
  // the frames: each from the keyframes around it and the ones before, the most head-on view per pixel
  const ks = Object.keys(keys).map(Number).sort((a, b) => a - b)
  const frames = new Array(n), frameBad = new Array(n)
  for (let s = 0; s < ks.length; s++) {
    const a = ks[s], b = ks[s + 1]
    const idx = []
    for (let i = a; i < (b ?? n); i++) idx.push(i)
    const stack = [b, a, ...ks.filter((x) => x < a).reverse().slice(0, STACK - 1)].filter((x) => x !== undefined).map((j) => ({ asset: keys[j], frame: j }))
    for (let c = 0; c < idx.length; c += 8) {
      const part = idx.slice(c, c + 8)
      const out = await page.evaluate(({ part, stack, w, h, O }) => window.__e35d(part, w, h, stack, { ...O, upload: true }), { part, stack, w: f.size.w, h: f.size.h, O: { seen: SEEN, fill: FILL, mag: MAG } })
      out.forEach((o, i) => { frames[part[i]] = o.sha; frameBad[part[i]] = o.bad })
    }
  }
  console.log(JSON.stringify({ keys, frames, frame_bad: frameBad, fills, probes }))
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
