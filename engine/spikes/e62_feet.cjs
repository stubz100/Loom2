// Spike E62 c (b)'s driver (D188): frontend/src/spikes/e62Feet.ts on the dev page in a visible Edge, for each character of the open project
// that has a shell (or those named): its numbers to engine/spikes/out/e62/feet.json, its side views to engine/spikes/out/e62/feet/.
// Run from frontend/ (Playwright is there): node ../engine/spikes/e62_feet.cjs [names,…]   — Vite on 1420, the orchestrator on 8766.
const { chromium } = require('@playwright/test')
const fs = require('fs')
const path = require('path')
const BASE = 'http://127.0.0.1:8766', TOKEN = process.env.LOOM2_TOKEN || 'devtoken'
const OUT = path.join(__dirname, 'out', 'e62')
fs.mkdirSync(path.join(OUT, 'feet'), { recursive: true })
const only = process.argv[2] ? process.argv[2].split(',') : null
async function api(p) { const r = await fetch(BASE + p, { headers: { 'X-Loom-Token': TOKEN } }); if (!r.ok) throw new Error(`${p}: ${r.status}`); return r.json() }

;(async () => {
  const project = await api('/project')
  const chars = (await api('/story/profiles')).items.filter((p) => p.cls === 'character' && (!only || only.includes(p.name)))
  const inputs = chars.map((p) => { const v = p.versions.find((x) => x.id === p.current) || p.versions[0]; return { name: p.name, body: v.body || {}, points: v.body_points || null, mesh: v.shell_asset_id } }).filter((x) => x.mesh)
  const browser = await chromium.launch({ channel: 'msedge', headless: false })
  const page = await browser.newPage({ viewport: { width: 1200, height: 900 } })
  page.on('console', (m) => { if (m.type() === 'error') console.error('page:', m.text().slice(0, 300)) })
  await page.goto(`http://127.0.0.1:1420/?token=${TOKEN}&port=8766`)
  await page.waitForFunction(() => !!window.__loom2Stage || document.readyState === 'complete', null, { timeout: 60000 })
  const prev = fs.existsSync(path.join(OUT, 'feet.json')) ? JSON.parse(fs.readFileSync(path.join(OUT, 'feet.json'), 'utf8')) : []
  const rows = prev.filter((r) => !inputs.some((i) => i.name === r.name))
  for (const input of inputs) {
    const t0 = Date.now()
    const r = await page.evaluate(async (inp) => {
      const [m, c] = await Promise.all([import('/src/spikes/e62Feet.ts'), import('/src/api/client.ts')])
      return m.bendFeet({ name: inp.name, body: inp.body, points: inp.points, meshUrl: c.api.assetUrl(inp.mesh) })
    }, input)
    for (const [k, v] of Object.entries(r.views || {})) fs.writeFileSync(path.join(OUT, 'feet', `${input.name.replace(/\W+/g, '_')}_${k}.png`), Buffer.from(v, 'base64'))
    delete r.views
    r.project = project.name; r.seconds = Math.round((Date.now() - t0) / 1000)
    rows.push(r)
    console.log(input.name, JSON.stringify(r.stretch), r.seconds, 's')
  }
  fs.writeFileSync(path.join(OUT, 'feet.json'), JSON.stringify(rows, null, 1))
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
