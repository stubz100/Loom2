// E10 Stage → image spike runner (D74), the pass half: renders bench/stage/scenes.json in Edge through spikes.html#e10 (Vite dev on
// 127.0.0.1:1420, WebGL2) and writes engine/spikes/out/e10/passes/<id>_{clay,depth,normal,pose}.png plus keypoints.json — the conditioning
// inputs and the ground truth the methods are scored against (engine/spikes/e10_stage.py).
//   node e2e/spikes/e10.run.mjs            (from frontend/)
import { chromium } from '@playwright/test'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const repo = resolve(here, '..', '..', '..')
const doc = JSON.parse(readFileSync(join(repo, 'bench', 'stage', 'scenes.json'), 'utf-8'))
const out = join(repo, 'engine', 'spikes', 'out', 'e10', 'passes')
mkdirSync(out, { recursive: true })

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } })
page.on('pageerror', (e) => console.log('pageerror', e.message))
await page.addInitScript((d) => { window.__e10Input = d }, doc)
await page.goto('http://127.0.0.1:1420/spikes.html#e10')
const res = await (await page.waitForFunction(() => window.__e10, null, { timeout: 120_000 })).jsonValue()
await page.screenshot({ path: join(out, '..', 'passes_page.png'), fullPage: true })
await browser.close()
const keypoints = {}
for (const s of res.scenes) {
  for (const [k, url] of Object.entries(s.passes)) writeFileSync(join(out, `${s.id}_${k}.png`), Buffer.from(url.split(',')[1], 'base64'))
  keypoints[s.id] = { prompt: s.prompt, figures: s.keypoints }
}
writeFileSync(join(out, 'keypoints.json'), JSON.stringify({ size: res.size, coco: res.coco, scenes: keypoints }, null, 1))
console.log(`${res.scenes.length} scenes → ${out}`)
