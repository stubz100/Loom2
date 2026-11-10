// Shell-fit check: frontend/src/spikes/shellFit.ts on the dev page (headless Edge, 2D canvas drawings) for each character with a shell and
// fitted points in the given projects — the skeleton's markers against the picture's points, the posed shell's stretch; to
// engine/spikes/out/shell_fit/. Run from frontend/ (Playwright is there): node ../engine/spikes/shell_fit.cjs <project dir>...
// Vite on SHELL_FIT_PORT (default 1420); SHELL_FIT_TAG names the run; SHELL_FIT_BODIES a JSON of body fields laid over each version's.
const { chromium } = require('@playwright/test')
const fs = require('fs')
const path = require('path')
const OUT = path.join(__dirname, 'out', 'shell_fit')
fs.mkdirSync(OUT, { recursive: true })
const port = process.env.SHELL_FIT_PORT || '1420'
const tag = process.env.SHELL_FIT_TAG || 'now'
const overrides = process.env.SHELL_FIT_BODIES ? JSON.parse(fs.readFileSync(process.env.SHELL_FIT_BODIES, 'utf8')) : {}   // {name: body fields} (the sole body.py solves)

;(async () => {
  const chars = []
  for (const dir of process.argv.slice(2)) {
    const pd = path.join(dir, 'story', 'profiles')
    if (!fs.existsSync(pd)) continue
    const find = (id, ext) => fs.readdirSync(path.join(dir, 'assets')).map((m) => path.join(dir, 'assets', m, `${id}.${ext}`)).find((x) => fs.existsSync(x))
    for (const f of fs.readdirSync(pd).filter((x) => x.endsWith('.json'))) {
      const p = JSON.parse(fs.readFileSync(path.join(pd, f), 'utf8'))
      if (p.cls !== 'character') continue
      for (const v of p.versions) {
        if (!v.shell_asset_id || !v.body_points) continue
        const glb = find(v.shell_asset_id, 'glb'), pic = find(v.shell_from || v.body_fit_from, 'png')
        const name = `${path.basename(dir)}_${p.name}_${v.id}`
        if (glb && pic) chars.push({ name, body: { ...(v.body || {}), ...(overrides[name] || {}) }, points: v.body_points, glb, pic })
      }
    }
  }
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const page = await browser.newPage()
  page.on('console', (m) => { if (m.type() === 'error') console.error('page:', m.text().slice(0, 300)) })
  await page.goto(`http://127.0.0.1:${port}/?token=devtoken&port=8766`)
  await page.waitForTimeout(2500)
  const out = {}
  for (const c of chars) {
    const r = await page.evaluate(async (inp) => (await import('/src/spikes/shellFit.ts')).shellFit(inp),
      { body: c.body, points: c.points, glb: fs.readFileSync(c.glb).toString('base64'), picture: fs.readFileSync(c.pic).toString('base64') })
    for (const k of ['bind_png', 'posed_png']) {
      fs.writeFileSync(path.join(OUT, `${c.name}_${tag}_${k.replace('_png', '')}.png`), Buffer.from(r[k].split(',')[1], 'base64'))
      delete r[k]
    }
    out[c.name] = r
    console.log(c.name, JSON.stringify(r, null, 1))
  }
  fs.writeFileSync(path.join(OUT, `fit_${tag}.json`), JSON.stringify(out, null, 1))
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
