// D158 rig (scripts/d158_rig.py): a shot's final made in the new shell, in headless Edge — Shots › the shot › Performance › Final shot ›
// Make the final shot…, confirmed — so its passes are drawn by today's Stage (the pose pass without face points on a turned figure).
// Waits until the stage has one final more than before. Args: <app url with the shot's hash> <api port> <token> <stage id>.
const { createRequire } = require('module')
const req = createRequire(require('path').join(__dirname, '..', 'frontend', 'package.json'))
const { chromium } = req('playwright')
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
;(async () => {
  const [url, port, token, stageId] = process.argv.slice(2)
  const finals = async () => (await (await fetch(`http://127.0.0.1:${port}/finals?stage_id=${stageId}`, { headers: { 'X-Loom-Token': token } })).json()).items.length
  const before = await finals()
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
  page.on('pageerror', (e) => console.log(`pageerror: ${String(e).slice(0, 300)}`))
  await page.goto(url)
  await page.locator('.perf-cards button', { hasText: 'Final shot' }).click({ timeout: 60_000 })
  await page.locator('.final-section button', { hasText: /^Make the final shot/ }).click({ timeout: 60_000 })
  const dialog = page.locator('.modal.ask')
  await dialog.locator('button.primary').click({ timeout: 30_000 })
  const t0 = Date.now()
  while (Date.now() - t0 < 300_000 && (await finals()) <= before) await sleep(1000)
  const after = await finals()
  console.log(JSON.stringify({ before, after, seconds: Math.round((Date.now() - t0) / 1000) }))
  await browser.close()
  process.exit(after > before ? 0 : 1)
})().catch((e) => { console.error(e); process.exit(1) })
