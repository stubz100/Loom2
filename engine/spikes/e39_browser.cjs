// Spike E39's browser half (engine/spikes/e39_poses.py measure): the dev page in a visible Edge, frontend/src/spikes/e39Poses.ts run on each
// character; its images to <outDir>/<name>_*.png, its numbers to <outDir>/results.json. Args: <inputs JSON> <outDir>.
const { chromium } = require('playwright')
const fs = require('fs')
const [inputsJson, outDir] = process.argv.slice(2)
;(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: false, args: ['--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding', '--disable-background-timer-throttling'] })
  const page = await browser.newPage({ viewport: { width: 1200, height: 900 } })
  page.on('console', (m) => { if (m.type() === 'error') console.error('page:', m.text().slice(0, 300)) })
  await page.goto('http://127.0.0.1:1420/?token=e28&port=8792&suite=stage')
  await page.waitForFunction(() => !!window.__loom2Stage, null, { timeout: 60000 })
  const rows = []
  for (const input of JSON.parse(inputsJson)) {
    const t0 = Date.now()
    const r = await page.evaluate(async (inp) => {
      const [m, c] = await Promise.all([import('/src/spikes/e39Poses.ts'), import('/src/api/client.ts')])
      return m.measurePoses({ ...inp, meshUrl: inp.mesh ? c.api.assetUrl(inp.mesh) : null })
    }, input)
    for (const [k, v] of Object.entries(r.views || {})) fs.writeFileSync(`${outDir}/${input.name}_${k}.png`, Buffer.from(v, 'base64'))
    delete r.views
    r.seconds = Math.round((Date.now() - t0) / 1000)
    rows.push(r)
    console.log(`${input.name}: ${r.seconds} s`)
  }
  fs.writeFileSync(`${outDir}/results.json`, JSON.stringify(rows, null, 1))
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
