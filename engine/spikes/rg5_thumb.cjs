// RG5 check (D191): frontend/src/spikes/rg5Thumb.ts on the dev page in a visible Edge — where each hand preset takes a character's thumb and
// index tips in its palm's frame, with its own hand shape (and the mannequin's for comparison); close-ups to engine/spikes/out/rg5/.
// Run from frontend/ (Playwright is there): node ../engine/spikes/rg5_thumb.cjs <profile json> [tag]   — Vite on 1420, the orchestrator on 8766.
const { chromium } = require('@playwright/test')
const fs = require('fs')
const path = require('path')
const OUT = path.join(__dirname, 'out', 'rg5')
fs.mkdirSync(OUT, { recursive: true })
const [file, tag = 'now'] = process.argv.slice(2)

;(async () => {
  const p = JSON.parse(fs.readFileSync(file, 'utf8'))
  const v = p.versions.find((x) => x.id === p.current) || p.versions[0]
  const browser = await chromium.launch({ channel: 'msedge', headless: false })
  const page = await browser.newPage({ viewport: { width: 900, height: 700 } })
  page.on('console', (m) => { if (m.type() === 'error') console.error('page:', m.text().slice(0, 300)) })
  await page.goto('http://127.0.0.1:1420/?token=devtoken&port=8766')
  await page.waitForTimeout(3000)
  const res = {}
  for (const own of [true, false]) {
    const r = await page.evaluate(async (inp) => (await import('/src/spikes/rg5Thumb.ts')).thumbCurl(inp), { body: v.body || {}, points: v.body_points || null, own, views: own })
    const slug = `${p.name.replace(/\W+/g, '_')}_${tag}_${own ? 'own' : 'mannequin'}`
    for (const [k, b64] of Object.entries(r.views)) fs.writeFileSync(path.join(OUT, `${slug}_${k}.png`), Buffer.from(b64, 'base64'))
    res[own ? 'own' : 'mannequin'] = r.measures
  }
  fs.writeFileSync(path.join(OUT, `${p.name.replace(/\W+/g, '_')}_${tag}_thumb.json`), JSON.stringify(res, null, 1))
  for (const [k, m] of Object.entries(res)) for (const side of ['r', 'l']) for (const [preset, row] of Object.entries(m[side]))
    console.log(k.padEnd(9), side, preset.padEnd(8), 'thumb moved [x y n]', JSON.stringify(row.thumb_moved).padEnd(18), 'index moved', JSON.stringify(row.index_moved).padEnd(18), 'last seg·n', row.last_seg_n, 'thumb→index', row.thumb_tip_to_index_tip)
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
