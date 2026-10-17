// E21 (two characters by layers), the pass half: renders the shot's blocking through the E10 spike page (spikes.html#e10, Vite dev on
// 127.0.0.1:1420, WebGL2) — the same mannequins, set and pass shaders as E10 / ST3 — in five variants from one camera: both figures, the
// empty set (the plate), each figure alone (its silhouette = the difference to the plate) and figure 1 in two more poses (the keypoints the
// speaker's pose sequence is drawn from). Writes engine/spikes/out/e21/passes/<id>_{clay,depth,normal,pose}.png + keypoints.json.
//   node engine/spikes/e21_passes.mjs        (Vite dev running on 1420)
import { createRequire } from 'node:module'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const repo = resolve(here, '..', '..')
const { chromium } = createRequire(join(repo, 'frontend', 'package.json'))('@playwright/test')
const out = join(here, 'out', 'e21', 'passes')
mkdirSync(out, { recursive: true })

const camera = { pos: [0, 1.05, 4.3], target: [0, 0.95, 0], fov: 30 }
const mara = { pose: 'stand', pos: [-1.0, 0, 0], yaw: 35 }
const ines = { pose: 'arms_crossed', pos: [1.0, 0, 0], yaw: -35 }
const scene = (id, figures) => ({ id, set: 'room', camera, figures, prompt: '' })
const doc = {
  size: [1280, 720],
  scenes: [scene('both', [mara, ines]), scene('plate', []), scene('left', [mara]), scene('right', [ines]),
    scene('left_point', [{ ...mara, pose: 'point' }]), scene('left_wave', [{ ...mara, pose: 'wave' }])],
}
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } })
page.on('pageerror', (e) => console.log('pageerror', e.message))
await page.addInitScript((d) => { window.__e10Input = d }, doc)
await page.goto('http://127.0.0.1:1420/spikes.html#e10')
const res = await (await page.waitForFunction(() => window.__e10, null, { timeout: 120_000 })).jsonValue()
await browser.close()
const keypoints = {}
for (const s of res.scenes) {
  for (const [k, url] of Object.entries(s.passes)) writeFileSync(join(out, `${s.id}_${k}.png`), Buffer.from(url.split(',')[1], 'base64'))
  keypoints[s.id] = s.keypoints
}
writeFileSync(join(out, 'keypoints.json'), JSON.stringify({ size: res.size, coco: res.coco, doc, scenes: keypoints }, null, 1))
console.log(`${res.scenes.length} scenes → ${out}`)
