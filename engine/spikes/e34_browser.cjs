// E34's browser half (engine/spikes/e34_plate.py runs it): on the orbit stage, Stage makes the final (the bare set's passes along the camera
// path), the plate's Klein still is queued and then projected along the path (PS5b's method), and the depth sequence of the same path is the
// guide of an LTX-2.3 clip that starts from that still (CA3's candidate). Prints one JSON line: {final_id, still, clip_job}.
const { chromium } = require('playwright')
const [stageId, prompt] = process.argv.slice(2)
const API = 'http://127.0.0.1:8792', H = { 'X-Loom-Token': 'e28', 'Content-Type': 'application/json' }
const api = async (m, p, b) => { const r = await fetch(API + p, { method: m, headers: H, body: b ? JSON.stringify(b) : undefined }); if (!r.ok) throw new Error(`${m} ${p} ${r.status} ${await r.text()}`); return r.json() }
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
  const fid = await page.evaluate(async () => {
    const m = await import('/src/suites/stage/finalShot.ts')
    const f = await m.makeFinal({ rate: 24, name: 'E34 orbit' })
    await m.useFinals.getState().load()
    await m.useFinals.getState().plate(f.id)
    return f.id
  })
  console.error(`final ${fid}: the plate's still queued`)
  let still = null
  for (let i = 0; i < 900 && !still; i++) { await sleep(2000); still = (await api('GET', `/finals/${fid}`)).layers.find((l) => l.id === 'plate').still_asset_id }
  if (!still) throw new Error('the plate still never landed')
  console.error(`still ${still}: projecting`)
  await page.evaluate(async (id) => { const m = await import('/src/suites/stage/finalShot.ts'); await m.useFinals.getState().load(); await m.useFinals.getState().project(id) }, fid)
  for (let i = 0; i < 600; i++) { const p = (await api('GET', `/finals/${fid}`)).layers.find((l) => l.id === 'plate'); if (p.status === 'done') break; await sleep(1000) }
  console.error('projected; the depth guide')
  const job = await page.evaluate(async ({ still, prompt }) => {
    const m = await import('/src/suites/stage/stageStore.ts')
    const s = m.useStage.getState()
    s.setClipMethod('guided'); s.setGuideKind('depth')
    await m.useStage.getState().renderPasses()
    await m.useStage.getState().renderGuide()
    m.useStage.setState({ shotStart: still })
    m.useStage.getState().setShot({ prompt_text: prompt })
    const jobs = await m.useStage.getState().animateShot()
    return jobs ? jobs[0].id : null
  }, { still, prompt })
  console.log(JSON.stringify({ final_id: fid, still, clip_job: job }))
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
