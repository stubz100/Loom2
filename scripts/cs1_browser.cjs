// CS1's browser half (scripts/cs1_acceptance.py runs it): the A1 stage open in a visible Edge — its bound figures take their Cast bodies (the
// refitted ones) — and a new final made from it as the Final shot card makes one (Stage renders every layer's passes: the figures' pose
// guides with CS1's one body and rest hands). Prints one JSON line {final_id, seconds}.
const { chromium } = require('playwright')
const [stageId, rate, w, h] = process.argv.slice(2)
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
;(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: false, args: ['--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding', '--disable-background-timer-throttling'] })
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } })
  page.on('console', (m) => { if (m.type() === 'error') console.error('page:', m.text()) })
  await page.goto('http://127.0.0.1:1420/?token=e28&port=8792&suite=stage')
  await page.waitForFunction(() => !!window.__loom2Stage, null, { timeout: 60000 })
  await page.evaluate(async () => { const m = await import('/src/suites/story/storyStore.ts'); await m.useStory.getState().loadProfiles() })
  await page.evaluate(async (id) => { await window.__loom2Stage.open(id) }, stageId)
  await page.locator('canvas.stage-canvas').waitFor({ timeout: 30000 })
  await sleep(4000)                                                              // the bodies synced, the Detailed mannequins loaded
  const t0 = Date.now()
  const fid = await page.evaluate(async ([r, ww, hh]) => {
    const m = await import('/src/suites/stage/finalShot.ts')
    const f = await m.makeFinal({ rate: Number(r), name: 'CS1 after', size: [Number(ww), Number(hh)], plate: 'projected' })
    return f.id
  }, [rate, w, h])
  console.log(JSON.stringify({ final_id: fid, seconds: Math.round((Date.now() - t0) / 1000) }))
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
