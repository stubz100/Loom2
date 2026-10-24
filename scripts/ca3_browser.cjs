// CA3's browser half (scripts/ca3_acceptance.py runs it): on the orbit stage, Stage makes the final (F16 unless a rate is given) — the plate's method chosen by the
// camera's travel (finalShot.ts plateChoice) — and *Make the plate* queues its Klein still with the Shot tab's prompt; the server then
// generates the plate along the path from the still (LTX-2.3 on the plate's depth pass). Prints one JSON line: {final_id, method, why, travel}.
const { chromium } = require('playwright')
const [stageId, prompt, rateArg] = process.argv.slice(2)
const rate = Number(rateArg || 16)
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
  const out = await page.evaluate(async ({ prompt, rate }) => {
    const m = await import('/src/suites/stage/finalShot.ts')
    const s = await import('/src/suites/stage/stageStore.ts')
    const st = s.useStage.getState()
    const doc = st.current, cam = st.activeCamera()
    const times = m.framesAt(doc.range.start, doc.range.end, rate)
    const travel = m.cameraTravel(doc, cam.id, times)
    const choice = m.plateChoice(travel, times.length, m.canGeneratePlate())
    const f = await m.makeFinal({ rate, name: 'CA3 orbit', plate: choice.advice })   // the advice made (AUTO_GENERATE is held, D130)
    st.setShot({ prompt_text: prompt })
    await m.useFinals.getState().load()
    await m.useFinals.getState().plate(f.id)
    return { final_id: f.id, method: f.layers.find((l) => l.id === 'plate').method, advice: choice.advice, why: choice.why, travel }
  }, { prompt, rate })
  console.log(JSON.stringify(out))
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
