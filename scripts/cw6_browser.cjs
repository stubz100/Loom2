// CW6's browser half (scripts/cw6_acceptance.py runs it; Vite on 1420, the rig's orchestrator on 8792), in a visible Edge — one step:
//   bake <out> <pid>...        each place opened in Story › Cast: the set builder bakes its fitted set on its own (the product's path);
//                              waits for the faces on the version, screenshots the section; prints {pid: seconds}
//   look <out> <spec.json>     each set drawn as the engine draws it (placeSet, its faces' textures unlit, inside only) from cameras: PNGs
//   bench <out> <stage> <name> the bench stage open in Animate › Clay: a screenshot of the app
const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')
const [step, outDir, ...rest] = process.argv.slice(2)
const API = 'http://127.0.0.1:8792', H = { 'X-Loom-Token': 'e28', 'Content-Type': 'application/json' }
const api = async (m, p, b) => { const r = await fetch(API + p, { method: m, headers: H, body: b ? JSON.stringify(b) : undefined }); if (!r.ok) throw new Error(`${m} ${p} ${r.status} ${await r.text()}`); return r.json() }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

;(async () => {
  fs.mkdirSync(outDir, { recursive: true })
  const browser = await chromium.launch({ channel: 'msedge', headless: false, args: ['--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding', '--disable-background-timer-throttling'] })
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
  page.on('console', (m) => { if (m.type() === 'error') console.error('page:', m.text()) })
  const out = {}
  if (step === 'bake') {
    await page.goto('http://127.0.0.1:1420/?token=e28&port=8792&suite=story')
    await page.waitForFunction(() => !!document.querySelector('.rail'), null, { timeout: 60000 })
    for (const pid of rest) {
      const t0 = Date.now()
      await page.evaluate(async (id) => {
        const s = await import('/src/suites/story/storyStore.ts')
        const r = await import('/src/frame/suiteRegistry.tsx')
        await s.useStory.getState().loadProfiles()
        r.setRailTab('story', 'cast')
        s.useStory.getState().selectProfile(id)
      }, pid)
      await page.locator('section.place-set .set-overlay').waitFor({ timeout: 60000 })
      let n = 0
      for (let k = 0; k < 240 && !n; k++) {                                   // the bake: the page's own, when the section shows a fitted set
        await sleep(500)
        const p = await api('GET', `/story/profiles/${pid}`)
        n = (p.versions.find((v) => v.id === p.current).place_set?.faces ?? []).filter((f) => f.baked_asset_id).length
      }
      out[pid] = { seconds: Math.round((Date.now() - t0) / 100) / 10, faces: n }
      await sleep(1500)
      await page.locator('section.place-set').scrollIntoViewIfNeeded()
      await page.locator('section.place-set').screenshot({ path: path.join(outDir, `${pid}_cast.png`) })
      console.error(`${pid}: ${n} faces baked in ${out[pid].seconds} s`)
    }
  } else if (step === 'look') {
    const spec = JSON.parse(fs.readFileSync(rest[0], 'utf-8'))
    await page.goto('http://127.0.0.1:1420/?token=e28&port=8792&suite=stage')
    await page.waitForFunction(() => !!window.__loom2Stage, null, { timeout: 60000 })
    for (const s of spec) {
      for (const [k, cam] of s.cams.entries()) {
        const b64 = await page.evaluate(async ({ set, faces, cam }) => { const m = await import('/src/spikes/e38Sets.ts'); return m.lookAssets(set, faces, cam) }, { set: s.set, faces: s.faces, cam })
        fs.writeFileSync(path.join(outDir, `${s.name}_look_${k}.png`), Buffer.from(b64, 'base64'))
      }
      console.error(`${s.name}: ${s.cams.length} looks`)
    }
  } else if (step === 'final') {                                              // CW7: the final shot made on a stage with a built set; its plate rendered here
    const [stageId] = rest
    await page.goto('http://127.0.0.1:1420/?token=e28&port=8792&suite=stage')
    await page.waitForFunction(() => !!window.__loom2Stage, null, { timeout: 60000 })
    await page.evaluate(async () => { const m = await import('/src/suites/story/storyStore.ts'); await m.useStory.getState().loadProfiles() })
    await page.evaluate(async (id) => { await window.__loom2Stage.open(id) }, stageId)
    await page.locator('canvas.stage-canvas').waitFor({ timeout: 30000 })
    await sleep(6000)                                                         // the bound figure's body and the set's faces from Cast
    const t0 = Date.now()
    out.final_id = await page.evaluate(async () => {
      const s = await import('/src/suites/stage/stageStore.ts')
      const f = await import('/src/suites/stage/finalShot.ts')
      const st = s.st(), cam = st.activeCamera()
      const d = [cam.target[0] - cam.pos[0], 0, cam.target[2] - cam.pos[2]], n = Math.hypot(d[0], d[2]) || 1
      const step = (p, k) => [p[0] + (d[0] / n) * k, p[1], p[2] + (d[2] / n) * k]
      st.setRange(0, 48)
      st.setFrame(0); st.keyCamera()
      st.setFrame(48); st.updateCamera(cam.id, { pos: step(cam.pos, 0.8), target: step(cam.target, 0.8) }); st.keyCamera()   // a dolly in, 0.8 m in 2 s
      st.setFrame(0)
      await st.flush()
      const fin = await f.makeFinal({ rate: 16, name: 'CW7 kitchen', plate: null })
      await f.useFinals.getState().load()
      await f.useFinals.getState().plate(fin.id)
      return fin.id
    })
    out.seconds = Math.round((Date.now() - t0) / 1000)
    await page.screenshot({ path: path.join(outDir, 'final_stage.png') })
  } else if (step === 'bench') {
    const [stageId, name] = rest
    await page.goto('http://127.0.0.1:1420/?token=e28&port=8792&suite=stage')
    await page.waitForFunction(() => !!window.__loom2Stage, null, { timeout: 60000 })
    await page.evaluate(async () => { const m = await import('/src/suites/story/storyStore.ts'); await m.useStory.getState().loadProfiles() })
    await page.evaluate(async (id) => { await window.__loom2Stage.open(id) }, stageId)
    await page.locator('canvas.stage-canvas').waitFor({ timeout: 30000 })
    await sleep(6000)                                                         // the faces' textures arrive
    await page.screenshot({ path: path.join(outDir, `${name}_bench.png`) })
  }
  console.log(JSON.stringify(out))
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
