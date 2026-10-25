// CS3's browser half (scripts/cs3_acceptance.py runs it): the A1 stage open in a visible Edge — its bound figures take their Cast bodies
// and shells (CS2: the version's shell is the figure's shadow proxy; CS3: its clay, the guide's landmarks on it) — then one step:
//   make <stage> <rate> <w> <h>       a new final made as the Final shot card makes one; prints {final_id, seconds}
//   apply <stage> <final> <layer> <frame>   *Apply from a frame…* on that layer (skeleton keys, the guide drawn again, the batches from the
//                                     frame performed again); prints {keys, seconds}
const { chromium } = require('playwright')
const [step, stageId, ...rest] = process.argv.slice(2)
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
  await sleep(6000)                                                              // the bodies and shells synced, the mannequins and shells loaded
  const t0 = Date.now()
  if (step === 'make') {
    const [rate, w, h] = rest
    const fid = await page.evaluate(async ([r, ww, hh]) => {
      const m = await import('/src/suites/stage/finalShot.ts')
      const f = await m.makeFinal({ rate: Number(r), name: 'CS3 shell', size: [Number(ww), Number(hh)], plate: 'projected' })
      return f.id
    }, [rate, w, h])
    console.log(JSON.stringify({ final_id: fid, seconds: Math.round((Date.now() - t0) / 1000) }))
  } else if (step === 'apply') {
    const [fid, lid, frame] = rest
    const keys = await page.evaluate(async ([f, l, fr]) => {
      const m = await import('/src/suites/stage/finalShot.ts')
      const s = await import('/src/suites/stage/stageStore.ts')
      await m.useFinals.getState().load()
      await m.useFinals.getState().skeletonFrom(f, l, Number(fr))
      await s.st().flush()
      const o = s.st().current.objects.find((x) => x.id === m.useFinals.getState().finals.find((y) => y.id === f).layers.find((y) => y.id === l).object_id)
      return s.st().keys().skeleton?.[o.id] ?? []
    }, [fid, lid, frame])
    console.log(JSON.stringify({ keys, seconds: Math.round((Date.now() - t0) / 1000) }))
  }
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
