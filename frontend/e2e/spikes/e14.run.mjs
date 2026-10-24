// E14 image → mesh spike runner (D74), the view half: serves the generated GLBs listed in engine/spikes/out/e14/meshes.json through
// public/spikes/e14/ (gitignored), renders them in Edge through spikes.html#e14 (Vite dev on 127.0.0.1:1420, WebGL2) and writes
// engine/spikes/out/e14/views/<tag>_{front,right,back,left}.png, <tag>_sil_<yaw>.png and views.json (triangle counts);
// engine/spikes/e14_mesh.py score does the silhouette IoU and the sheets (and runs this itself unless --no-render).
//   node e2e/spikes/e14.run.mjs            (from frontend/; E14_OUT=e33 for E33's meshes)
import { chromium } from '@playwright/test'
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const repo = resolve(here, '..', '..', '..')
const outDir = join(repo, 'engine', 'spikes', 'out', process.env.E14_OUT || 'e14')        // E33 scores its meshes here too (E14_OUT=e33)
const meshes = JSON.parse(readFileSync(join(outDir, 'meshes.json'), 'utf-8')) // [{tag, path}]
const pub = join(repo, 'frontend', 'public', 'spikes', 'e14')
mkdirSync(pub, { recursive: true })
mkdirSync(join(outDir, 'views'), { recursive: true })
const input = {
  size: 512,
  meshes: meshes.map((m) => {
    copyFileSync(m.path, join(pub, `${m.tag}.glb`))
    return { tag: m.tag, url: `/spikes/e14/${m.tag}.glb` }
  }),
}

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } })
page.on('pageerror', (e) => console.log('pageerror', e.message))
await page.addInitScript((d) => { window.__e14Input = d }, input)
await page.goto('http://127.0.0.1:1420/spikes.html#e14')
const res = await (await page.waitForFunction(() => window.__e14, null, { timeout: 300_000 })).jsonValue()
await browser.close()
const png = (url) => Buffer.from(url.split(',')[1], 'base64')
const summary = {}
for (const r of res.results) {
  for (const [k, url] of Object.entries(r.views)) writeFileSync(join(outDir, 'views', `${r.tag}_${k}.png`), png(url))
  for (const [k, url] of Object.entries(r.sil)) writeFileSync(join(outDir, 'views', `${r.tag}_sil_${k}.png`), png(url))
  summary[r.tag] = { faces: r.faces, error: r.error }
  console.log(`${r.tag}: ${r.error ? 'ERROR ' + r.error : `${r.faces} triangles`}`)
}
writeFileSync(join(outDir, 'views', 'views.json'), JSON.stringify(summary, null, 1))
