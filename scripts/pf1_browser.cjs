// PF1's browser half (scripts/pf1_acceptance.py runs it): the final's stage open in a visible Edge, the finals' poll's step run until the
// plate is done — `useFinals.fill` (Stage's probes, keyframes and frames; the server's Fills) exactly as the Final shot card's poll runs it.
// Prints one JSON line {steps, seconds}.
const { chromium } = require('playwright')
const [stageId, finalId] = process.argv.slice(2)
const API = 'http://127.0.0.1:8792', H = { 'X-Loom-Token': 'e28', 'Content-Type': 'application/json' }
const api = async (m, p) => { const r = await fetch(API + p, { method: m, headers: H }); if (!r.ok) throw new Error(`${m} ${p} ${r.status} ${await r.text()}`); return r.json() }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
;(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: false, args: ['--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding', '--disable-background-timer-throttling'] })
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } })
  page.on('console', (m) => { if (m.type() === 'error') console.error('page:', m.text()) })
  await page.goto('http://127.0.0.1:1420/?token=e28&port=8792&suite=stage')
  await page.waitForFunction(() => !!window.__loom2Stage, null, { timeout: 60000 })
  await page.evaluate(async (id) => { await window.__loom2Stage.open(id) }, stageId)
  await page.locator('canvas.stage-canvas').waitFor({ timeout: 30000 })
  await sleep(2500)
  const t0 = Date.now()
  let steps = 0
  for (;;) {
    const plate = (await api('GET', `/finals/${finalId}`)).layers.find((l) => l.id === 'plate')
    if (plate.status === 'done' || plate.status === 'failed') { if (plate.status === 'failed') throw new Error(plate.error); break }
    if (Date.now() - t0 > 3600_000) throw new Error('the plate was not filled in an hour')
    await page.evaluate(async (fid) => { const m = await import('/src/suites/stage/finalShot.ts'); await m.useFinals.getState().load(); await m.useFinals.getState().fill(fid) }, finalId)
    steps++
    await sleep(2000)
  }
  console.log(JSON.stringify({ steps, seconds: Math.round((Date.now() - t0) / 1000) }))
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
