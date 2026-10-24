// E35d's setup for a new move (engine/spikes/e35d_run.py runs it): on the move's stage, Stage makes the final at F16 with its plate
// projected (no clip queued), and *Make the plate* queues its Klein still with the place's prompt. Prints one JSON line {final_id}.
const { chromium } = require('playwright')
const [stageId, prompt] = process.argv.slice(2)
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
  const out = await page.evaluate(async (prompt) => {
    const m = await import('/src/suites/stage/finalShot.ts')
    const s = await import('/src/suites/stage/stageStore.ts')
    const f = await m.makeFinal({ rate: 16, name: 'E35d move', plate: 'projected' })
    s.useStage.getState().setShot({ prompt_text: prompt })
    await m.useFinals.getState().load()
    await m.useFinals.getState().plate(f.id)
    return { final_id: f.id }
  }, prompt)
  console.log(JSON.stringify(out))
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
