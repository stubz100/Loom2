// Spike E38's browser half (engine/spikes/e38_sets.py runs it; Vite on 1420, the spike's orchestrator on 8792). Modes, each reading a JSON
// spec file and writing into an out dir:
//   stills  — each truth stage opened, its passes rendered, its Klein still from the clay (Stage's own Make a frame): prints {name: job id}
//   bake    — each picture baked onto its fitted set from its matched camera (stage/setBake.ts): face textures and coverages as PNGs
//   move    — a camera move through a set textured with its (composited) coverage: per frame the share unseen and too coarse, a few frames
//   look    — the set textured by its bake, from cameras: PNGs for the sheet
const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')
const [mode, specPath, outDir] = process.argv.slice(2)
const spec = JSON.parse(fs.readFileSync(specPath, 'utf-8'))
const API = 'http://127.0.0.1:8792', H = { 'X-Loom-Token': 'e28', 'Content-Type': 'application/json' }
const api = async (m, p, b) => { const r = await fetch(API + p, { method: m, headers: H, body: b ? JSON.stringify(b) : undefined }); if (!r.ok) throw new Error(`${m} ${p} ${r.status} ${await r.text()}`); return r.json() }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const png = (name, b64) => { fs.mkdirSync(path.dirname(path.join(outDir, name)), { recursive: true }); fs.writeFileSync(path.join(outDir, name), Buffer.from(b64, 'base64')) }

;(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: false, args: ['--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding', '--disable-background-timer-throttling'] })
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } })
  page.on('console', (m) => { if (m.type() === 'error') console.error('page:', m.text()) })
  await page.goto('http://127.0.0.1:1420/?token=e28&port=8792&suite=stage')
  await page.waitForFunction(() => !!window.__loom2Stage, null, { timeout: 60000 })
  const out = {}
  if (mode === 'stills') {
    for (const s of spec) {
      await page.evaluate(async (id) => { await window.__loom2Stage.open(id) }, s.stage_id)
      await page.locator('canvas.stage-canvas').waitFor({ timeout: 30000 })
      await sleep(1500)
      out[s.name] = await page.evaluate(async (prompt) => {
        const m = await import('/src/suites/stage/stageStore.ts')
        await m.useStage.getState().renderPasses()
        m.useStage.getState().setShot({ prompt_text: prompt, count: 1 })
        const jobs = await m.useStage.getState().generateShot()
        return jobs ? jobs[0].id : null
      }, s.prompt)
      console.error(`${s.name}: still queued (${out[s.name]})`)
    }
  } else if (mode === 'bake') {
    for (const s of spec) {
      const faces = await page.evaluate(async ({ asset_id, set, cam, texel }) => {
        const [m, c] = await Promise.all([import('/src/spikes/e38Sets.ts'), import('/src/api/client.ts')])
        return m.bake(c.api.assetUrl(asset_id), set, cam, texel)                                     // the app's own media URL (its key)
      }, s)
      out[s.name] = faces.map((f) => { png(`${s.name}/${f.id}.png`, f.texture); png(`${s.name}/${f.id}.cov.png`, f.coverage); return { id: f.id, w: f.w, h: f.h, px: f.px, texel_m: f.texel_m } })
      console.error(`${s.name}: ${faces.length} faces baked`)
    }
  } else if (mode === 'move') {
    for (const s of spec) {
      const cov = Object.fromEntries(Object.entries(s.coverage).map(([id, p]) => [id, fs.readFileSync(p).toString('base64')]))
      const r = await page.evaluate(async ({ set, cov, frames }) => { const m = await import('/src/spikes/e38Sets.ts'); return m.moveCoverage(set, cov, frames) }, { set: s.set, cov, frames: s.frames })
      for (const [i, b] of Object.entries(r.shots)) png(`${s.name}/move_${String(i).padStart(3, '0')}.png`, b)
      out[s.name] = { unseen: r.unseen, coarse: r.coarse }
      console.error(`${s.name}: ${s.frames.length} frames`)
    }
  } else if (mode === 'look') {
    for (const s of spec) {
      const tex = Object.fromEntries(Object.entries(s.textures).map(([id, p]) => [id, fs.readFileSync(p).toString('base64')]))
      for (const [k, cam] of s.cams.entries()) {
        const b = await page.evaluate(async ({ set, tex, cam }) => { const m = await import('/src/spikes/e38Sets.ts'); return m.look(set, tex, cam) }, { set: s.set, tex, cam })
        png(`${s.name}/look_${k}.png`, b)
      }
      out[s.name] = s.cams.length
    }
  }
  fs.writeFileSync(path.join(outDir, `${mode}.json`), JSON.stringify(out, null, 1))
  console.log(JSON.stringify(out).slice(0, 2000))
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
