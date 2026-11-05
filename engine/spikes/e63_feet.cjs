// E63 (RG2b, D188 F5; owed since 2026-11-05 09:25): does Wan Animate follow the guide's rolling feet? Through the product path on the rig
// (one GPU job at a time, the queue's): Followed's shot 1 made again as a final with today's code — the Detailed figure's heels and toes
// rolling with the clip (RG2b) in its pose pass — and only Nora's layer performed (Wan Animate, then the matte), beside her take of
// 2026-11-04 made with the old guide (its feet flat on the shin). engine/spikes/e63_feet.py then reads both takes' feet.
// Run from frontend/ (Playwright is there): node ../engine/spikes/e63_feet.cjs [shot] [figure name] — Vite on 1420, the orchestrator on 8766.
const { chromium } = require('@playwright/test')
const fs = require('fs')
const path = require('path')
const BASE = 'http://127.0.0.1:8766', H = { 'X-Loom-Token': 'devtoken', 'Content-Type': 'application/json' }
const api = async (m, p, b) => { const r = await fetch(BASE + p, { method: m, headers: H, body: b ? JSON.stringify(b) : undefined }); if (!r.ok) throw new Error(`${m} ${p}: ${r.status} ${await r.text()}`); return r.json() }
const OUT = path.join(__dirname, 'out', 'e63')
fs.mkdirSync(OUT, { recursive: true })
const [shot = 'sht_9c8ebc78', who = 'Nora'] = process.argv.slice(2)
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

;(async () => {
  const sv = (await api('GET', `/story/shots/${shot}`)).versions[0]
  const before = new Set((await api('GET', `/finals?stage_id=${sv.stage_id}`)).items.map((f) => f.id))
  const b = await chromium.launch({ channel: 'msedge', headless: false })
  const page = await b.newPage({ viewport: { width: 1600, height: 950 } })
  page.on('console', (m) => { if (m.type() === 'error') console.error('page:', m.text().slice(0, 200)) })
  await page.goto(`http://127.0.0.1:1420/?token=devtoken&port=8766#shots/${shot}/performance`)
  await page.waitForTimeout(7000)
  await page.locator('.perf-cards button', { hasText: 'Final shot' }).click()
  await page.waitForTimeout(1500)
  await page.locator('.final-section button', { hasText: /^Make the final shot/ }).click()
  const dialog = page.locator('.modal.ask')
  console.log('make:', (await dialog.innerText()).replace(/\s+/g, ' ').slice(0, 400))
  await dialog.locator('button.primary').click()
  let fin = null
  for (let i = 0; i < 120 && !fin; i++) { await sleep(2000); fin = (await api('GET', `/finals?stage_id=${sv.stage_id}`)).items.find((f) => !before.has(f.id) && f.layers.every((l) => l.status !== 'pending')) ?? null }
  if (!fin) throw new Error('no new final')
  console.log('final', fin.id, fin.frames, 'f at', fin.rate, '·', fin.layers.map((l) => `${l.kind}:${l.name}:${l.status}`).join(' '))
  const lay = fin.layers.find((l) => l.kind === 'figure' && l.name === who)
  if (!lay) throw new Error(`no layer for ${who}`)
  const row = page.locator(`.final-section li[data-kind="figure"]`).filter({ hasText: who })
  await row.locator('button', { hasText: /^Perform/ }).first().click()
  await sleep(800)
  if (await dialog.isVisible().catch(() => false)) { console.log('perform:', (await dialog.innerText()).replace(/\s+/g, ' ').slice(0, 300)); await dialog.locator('button.primary').click() }
  const t0 = Date.now()
  for (;;) {
    await sleep(10000)
    const l = (await api('GET', `/finals/${fin.id}`)).layers.find((x) => x.id === lay.id)
    process.stdout.write(`\r${Math.round((Date.now() - t0) / 1000)} s · ${l.status} ${l.frames_done}/${fin.frames}   `)
    if (l.status === 'done' || l.status === 'failed' || Date.now() - t0 > 40 * 60000) { console.log(); break }
  }
  const done = await api('GET', `/finals/${fin.id}`)
  fs.writeFileSync(path.join(OUT, 'run.json'), JSON.stringify({ shot, who, final: done.id, layer: lay.id, seconds: Math.round((Date.now() - t0) / 1000), layers: done.layers }, null, 1))
  console.log('layer', lay.id, done.layers.find((x) => x.id === lay.id).status, Math.round((Date.now() - t0) / 1000), 's')
  await b.close()
})().catch((e) => { console.error(e); process.exit(1) })
