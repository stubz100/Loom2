// RG2b check (D188): frontend/src/spikes/rg2Feet.ts on the dev page in a visible Edge for one character of the open project — its right
// foot from the side through a library clip, the shoe and the guide's toes turned by the clip's foot turns and held, to
// engine/spikes/out/rg2/<name>_feet_*.png and <name>_feet.json.
// Run from frontend/ (Playwright is there): node ../engine/spikes/rg2_feet.cjs <character> [clip] [frames]   — Vite on 1420, the orchestrator on 8766.
const { chromium } = require('@playwright/test')
const fs = require('fs')
const path = require('path')
const BASE = 'http://127.0.0.1:8766', TOKEN = process.env.LOOM2_TOKEN || 'devtoken'
const OUT = path.join(__dirname, 'out', 'rg2')
fs.mkdirSync(OUT, { recursive: true })
const [want, clip = 'Walk_Loop', fr = '0,6,12,18,24', shapeJson] = process.argv.slice(2)   // a foot shape as JSON (hands.FootShape) when the version has none yet
async function api(p) { const r = await fetch(BASE + p, { headers: { 'X-Loom-Token': TOKEN } }); if (!r.ok) throw new Error(`${p}: ${r.status}`); return r.json() }

;(async () => {
  const p = (await api('/story/profiles')).items.find((x) => x.name === want && x.cls === 'character')
  if (!p) throw new Error(`no character ${want}`)
  const v = p.versions.find((x) => x.id === p.current) || p.versions[0]
  const browser = await chromium.launch({ channel: 'msedge', headless: false })
  const page = await browser.newPage({ viewport: { width: 1000, height: 800 } })
  page.on('console', (m) => { if (m.type() === 'error') console.error('page:', m.text().slice(0, 300)) })
  await page.goto(`http://127.0.0.1:1420/?token=${TOKEN}&port=8766`)
  await page.waitForTimeout(3000)
  const r = await page.evaluate(async (inp) => {
    const [m, c] = await Promise.all([import('/src/spikes/rg2Feet.ts'), import('/src/api/client.ts')])
    return m.feetWalking({ body: inp.body, points: inp.points, meshUrl: c.api.assetUrl(inp.mesh), clip: inp.clip, frames: inp.frames, footShape: inp.shape })
  }, { body: v.body || {}, points: v.body_points || null, mesh: v.shell_asset_id, clip, frames: fr.split(',').map(Number), shape: shapeJson ? { right: JSON.parse(shapeJson), left: null } : null })
  const slug = want.replace(/\W+/g, '_')
  for (const [k, b64] of Object.entries(r.views)) fs.writeFileSync(path.join(OUT, `${slug}_feet_${k}.png`), Buffer.from(b64, 'base64'))
  delete r.views
  fs.writeFileSync(path.join(OUT, `${slug}_feet.json`), JSON.stringify(r, null, 1))
  console.log(JSON.stringify(r))
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
