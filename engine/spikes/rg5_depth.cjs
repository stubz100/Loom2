// RG5 check (D191): frontend/src/spikes/rg5Depth.ts on the dev page (headless Edge: no WebGL drawn, only rays) for every character with a
// shell and fitted points in the given projects — how the shell sits on the skeleton in depth; to engine/spikes/out/rg5/depth.json.
// Run from frontend/ (Playwright is there): node ../engine/spikes/rg5_depth.cjs <project dir>...   — Vite on 1420.
const { chromium } = require('@playwright/test')
const fs = require('fs')
const path = require('path')
const OUT = path.join(__dirname, 'out', 'rg5')
fs.mkdirSync(OUT, { recursive: true })
const shift = process.env.RG5_SHIFT ? Number(process.env.RG5_SHIFT) : null

;(async () => {
  const chars = []
  for (const dir of process.argv.slice(2)) {
    const pd = path.join(dir, 'story', 'profiles')
    if (!fs.existsSync(pd)) continue
    for (const f of fs.readdirSync(pd).filter((x) => x.endsWith('.json'))) {
      const p = JSON.parse(fs.readFileSync(path.join(pd, f), 'utf8'))
      if (p.cls !== 'character') continue
      for (const v of p.versions) {
        if (!v.shell_asset_id || !v.body_points) continue
        const glb = fs.readdirSync(path.join(dir, 'assets')).map((m) => path.join(dir, 'assets', m, `${v.shell_asset_id}.glb`)).find((x) => fs.existsSync(x))
        if (glb) chars.push({ name: `${path.basename(dir)}/${p.name}/${v.id}`, body: v.body || {}, points: v.body_points, glb })
      }
    }
  }
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const page = await browser.newPage()
  page.on('console', (m) => { if (m.type() === 'error') console.error('page:', m.text().slice(0, 300)) })
  await page.goto('http://127.0.0.1:1420/?token=devtoken&port=8766')
  await page.waitForTimeout(2500)
  const out = {}
  for (const c of chars) {
    out[c.name] = await page.evaluate(async (inp) => (await import('/src/spikes/rg5Depth.ts')).shellDepth(inp),
      { body: c.body, points: c.points, glb: fs.readFileSync(c.glb).toString('base64'), shift })
    const r = out[c.name]
    console.log(c.name, 'box_mid', r.box_mid_z_cm, 'cm · depth', r.depth_cm, 'cm · hips off', r.hip_off_cm, 'cm · outside now', r.outside_now.length, JSON.stringify(r.outside_now), '· hip-aligned', r.outside_hip_aligned.length, JSON.stringify(r.outside_hip_aligned))
  }
  fs.writeFileSync(path.join(OUT, 'depth.json'), JSON.stringify(out, null, 1))
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
