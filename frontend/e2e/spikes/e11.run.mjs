// E11 Stage → video spike runner (D74), the pass half: renders the five shots of frontend/src/spikes/e11Shots.ts in Edge (spikes.html#e11,
// Vite dev on 127.0.0.1:1420, WebGL2) and writes engine/spikes/out/e11/<shot>/{pose,depth}/NNNN.png, clay0.png and keypoints.json;
// engine/spikes/e11_video.py turns the sequences into the guide videos and runs the methods.
//   node e2e/spikes/e11.run.mjs            (from frontend/)
import { chromium } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const out = resolve(here, '..', '..', '..', 'engine', 'spikes', 'out', 'e11')
const png = (url) => Buffer.from(url.split(',')[1], 'base64')

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage()
page.on('pageerror', (e) => console.log('pageerror', e.message))
await page.goto('http://127.0.0.1:1420/spikes.html#e11')
const shots = await (await page.waitForFunction(() => window.__e11?.shots, null, { timeout: 60_000 })).jsonValue()
for (let i = 0; i < shots.length; i++) {
  const s = await page.evaluate((k) => window.__e11.render(k), i)
  const dir = join(out, s.id)
  for (const k of ['pose', 'depth']) {
    mkdirSync(join(dir, k), { recursive: true })
    s[k].forEach((url, f) => writeFileSync(join(dir, k, `${String(f).padStart(4, '0')}.png`), png(url)))
  }
  writeFileSync(join(dir, 'clay0.png'), png(s.clay0))
  writeFileSync(join(dir, 'keypoints.json'), JSON.stringify({ id: s.id, prompt: s.prompt, fps: s.fps, size: s.size, frames: s.keypoints }))
  console.log(`${s.id}: ${s.pose.length} frames`)
}
await browser.close()
