// RG2 check (D187): frontend/src/spikes/rg2Hands.ts on the dev page in a visible Edge for one character of the open project — its right
// hand close up with its own hand shape and with the mannequin's, open and at rest, its shell bound; the four views side by side to
// engine/spikes/out/rg2/<name>.png and the measures to engine/spikes/out/rg2/<name>.json.
// Run from frontend/ (Playwright is there): node ../engine/spikes/rg2_hands.cjs <character name>   — Vite on 1420, the orchestrator on 8766.
const { chromium } = require('@playwright/test')
const fs = require('fs')
const path = require('path')
const BASE = 'http://127.0.0.1:8766', TOKEN = process.env.LOOM2_TOKEN || 'devtoken'
const OUT = path.join(__dirname, 'out', 'rg2')
fs.mkdirSync(OUT, { recursive: true })
const want = process.argv[2]
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
    const [m, c] = await Promise.all([import('/src/spikes/rg2Hands.ts'), import('/src/api/client.ts')])
    return m.handCloseUps({ body: inp.body, points: inp.points, meshUrl: inp.mesh ? c.api.assetUrl(inp.mesh) : null })
  }, { body: v.body || {}, points: v.body_points || null, mesh: v.shell_asset_id })
  const slug = want.replace(/\W+/g, '_')
  for (const [k, b64] of Object.entries(r.views)) fs.writeFileSync(path.join(OUT, `${slug}_${k}.png`), Buffer.from(b64, 'base64'))
  fs.writeFileSync(path.join(OUT, `${slug}.json`), JSON.stringify(r.measures, null, 1))
  console.log(JSON.stringify(r.measures))
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
