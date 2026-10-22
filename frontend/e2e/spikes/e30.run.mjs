// E30 set-from-an-image spike runner (D119), the view half: serves the reliefs and prop models listed in engine/spikes/out/e30/scenes.json
// through public/spikes/e30/ (gitignored), renders every scene's camera moves in Edge through spikes.html#e30 (Vite dev on 127.0.0.1:1420,
// WebGL2) and writes engine/spikes/out/e30/views/<scene>_<move>_{beauty,clay,depth}.jpg for the sheet moves and views.json (the holes,
// smear and tear of every move); engine/spikes/e30_set_from_image.py render runs this, score reads it.
//   node e2e/spikes/e30.run.mjs            (from frontend/)
import { chromium } from '@playwright/test'
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { basename, dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const repo = resolve(here, '..', '..', '..')
const outDir = join(repo, 'engine', 'spikes', 'out', 'e30')
const spec = JSON.parse(readFileSync(join(outDir, 'scenes.json'), 'utf-8'))
const pub = join(repo, 'frontend', 'public', 'spikes', 'e30')
mkdirSync(pub, { recursive: true })
mkdirSync(join(outDir, 'views'), { recursive: true })
const served = new Map()
const serve = (path) => {
  if (!served.has(path)) {
    const name = `${served.size}_${basename(path)}`
    copyFileSync(path, join(pub, name))
    served.set(path, `/spikes/e30/${name}`)
  }
  return served.get(path)
}
const input = {
  size: spec.size,
  scenes: spec.scenes.map((s) => ({ ...s, relief: serve(s.relief), props: s.props.map((p) => ({ ...p, url: serve(p.file) })) })),
}

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } })
page.on('pageerror', (e) => console.log('pageerror', e.message))
page.on('console', (m) => { if (m.type() === 'error') console.log('console', m.text()) })
await page.addInitScript((d) => { window.__e30Input = d }, input)
await page.goto('http://127.0.0.1:1420/spikes.html#e30')
const res = await (await page.waitForFunction(() => window.__e30, null, { timeout: 900_000 })).jsonValue()
await browser.close()
const jpg = (url) => Buffer.from(url.split(',')[1], 'base64')
const summary = {}
for (const r of res.results) {
  const moves = []
  for (const m of r.moves) {
    const rec = { ...m }
    if (m.images) {
      rec.images = {}
      for (const [k, url] of Object.entries(m.images)) {
        const file = join(outDir, 'views', `${r.tag}_${m.name}_${k}.jpg`)
        writeFileSync(file, jpg(url))
        rec.images[k] = file
      }
    }
    moves.push(rec)
  }
  summary[r.tag] = { faces: r.faces, error: r.error, moves }
  const worst = moves.reduce((a, b) => (b.tear > a.tear ? b : a), { name: '—', tear: 0 })
  console.log(`${r.tag}: ${r.error ? 'ERROR ' + r.error : `${r.faces} triangles, worst ${worst.name} tear ${worst.tear} %`}`)
}
writeFileSync(join(outDir, 'views', 'views.json'), JSON.stringify(summary, null, 1))
