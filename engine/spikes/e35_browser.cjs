// E35's browser half (engine/spikes/e35_chain.py runs it): on the final's stage, Stage projects (1) the first still alone along the path
// (PS5b), and (2) arm B — each keyframe still projected along the path from its own frame's camera, a frame between two keyframes the
// blend of the two projections by its distance to each. The frames go up as blobs (PUT /blobs); prints one JSON line {plain, blend} of
// their sha256s in frame order.
const { chromium } = require('playwright')
const [stageId, finalId, keysJson] = process.argv.slice(2)
const API = 'http://127.0.0.1:8792', H = { 'X-Loom-Token': 'e28', 'Content-Type': 'application/json' }
const api = async (m, p, b) => { const r = await fetch(API + p, { method: m, headers: H, body: b ? JSON.stringify(b) : undefined }); if (!r.ok) throw new Error(`${m} ${p} ${r.status} ${await r.text()}`); return r.json() }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
;(async () => {
  const f = await api('GET', `/finals/${finalId}`)
  const keys = JSON.parse(keysJson)
  const browser = await chromium.launch({ channel: 'msedge', headless: false, args: ['--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding', '--disable-background-timer-throttling'] })
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } })
  page.on('console', (m) => { if (m.type() === 'error') console.error('page:', m.text()) })
  await page.goto('http://127.0.0.1:1420/?token=e28&port=8792&suite=stage')
  await page.waitForFunction(() => !!window.__loom2Stage, null, { timeout: 60000 })
  await page.evaluate(async (id) => { await window.__loom2Stage.open(id) }, stageId)
  await page.locator('canvas.stage-canvas').waitFor({ timeout: 30000 })
  await sleep(2500)
  const out = await page.evaluate(async ({ f, keys }) => {
    const fs = await import('/src/suites/stage/finalShot.ts')
    const an = await import('/src/suites/stage/anim.ts')
    const ss = await import('/src/suites/stage/stageStore.ts')
    const cl = await import('/src/api/client.ts')
    const st = () => ss.useStage.getState()
    if (!st().plateProjector) (await import('/src/suites/stage/headless.ts')).ensureHeadless()
    const project = st().plateProjector
    const doc = st().current
    const { w, h } = f.size
    const times = fs.framesAt(f.range.start, f.range.end, f.rate)
    const camOf = (d) => d.cameras.find((c) => c.id === f.camera_id) ?? d.cameras[0]
    const frames = times.map((t) => { const d = an.sampleDoc(doc, t); return { cam: camOf(d), doc: d } })
    const restore = an.sampleDoc(doc, st().frame)
    const load = (id) => new Promise((res, rej) => { const im = new Image(); im.crossOrigin = 'anonymous'; im.onload = () => res(im); im.onerror = () => rej(new Error(`${id} did not load`)); im.src = cl.api.assetUrl(id) })
    const put = async (blob) => { const sha = await cl.sha256Hex(await blob.arrayBuffer()); await cl.api.putBlob(sha, blob); return sha }
    const first = await load(keys['0'])
    const plain = []
    for (const b of await project(frames, w, h, first, frames[0].cam, first.naturalWidth / first.naturalHeight, restore)) plain.push(await put(b))
    const ks = Object.keys(keys).map(Number).sort((a, b) => a - b)
    const blend = new Array(frames.length)
    for (let s = 0; s < ks.length - 1; s++) {
      const a = ks[s], b = ks[s + 1]
      const seg = frames.slice(a, b + 1)
      const ia = await load(keys[String(a)]), ib = await load(keys[String(b)])
      const pa = await project(seg, w, h, ia, frames[a].cam, ia.naturalWidth / ia.naturalHeight, restore)
      const pb = await project(seg, w, h, ib, frames[b].cam, ib.naturalWidth / ib.naturalHeight, restore)
      for (let i = 0; i < seg.length; i++) {
        if (blend[a + i]) continue                                             // a keyframe ends one segment and starts the next
        const c = new OffscreenCanvas(w, h), g = c.getContext('2d')
        g.drawImage(await createImageBitmap(pa[i]), 0, 0)
        g.globalAlpha = i / (b - a)
        g.drawImage(await createImageBitmap(pb[i]), 0, 0)
        blend[a + i] = await put(await c.convertToBlob({ type: 'image/png' }))
      }
    }
    return { plain, blend }
  }, { f, keys })
  console.log(JSON.stringify(out))
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
