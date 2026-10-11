// E13 timeline spike runner (D74): opens spikes.html#e13 in Edge against the Vite dev server (127.0.0.1:1420), waits for the page's
// result, writes it with the exported EDL / FCPXML to engine/spikes/out/e13/, and measures the bundle growth of the timeline code (the
// lane model + view, minified and gzipped, Mediabunny excluded — the app ships it already).
//   node e2e/spikes/e13.run.mjs            (from frontend/; clips: orchestrator/spikes/e13_make_clips.py)
import { chromium } from '@playwright/test'
import { mkdirSync, writeFileSync, appendFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { gzipSync } from 'node:zlib'
import { build } from 'vite'

const here = dirname(fileURLToPath(import.meta.url))
const frontend = resolve(here, '..', '..')
const out = resolve(frontend, '..', 'engine', 'spikes', 'out', 'e13')
mkdirSync(out, { recursive: true })

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } })
page.on('pageerror', (e) => console.log('pageerror', e.message))
await page.goto('http://127.0.0.1:1420/spikes.html#e13')
const result = await (await page.waitForFunction(() => window.__e13, null, { timeout: 180_000 })).jsonValue()
const files = await page.evaluate(() => window.__e13Files)
await page.screenshot({ path: join(out, 'page.png') })
await browser.close()
for (const [name, text] of Object.entries(files)) writeFileSync(join(out, name), text)

// bundle growth: the timeline modules alone, as the app would ship them
const b = await build({
  configFile: false, root: frontend, logLevel: 'silent',
  build: { write: false, minify: true, lib: { entry: resolve(frontend, 'src/spikes/e13Timeline.ts'), formats: ['es'], fileName: 'e13' },
    rollupOptions: { external: ['mediabunny', /\/report$/] } },
})
const code = (Array.isArray(b) ? b : [b]).flatMap((x) => x.output).filter((o) => o.type === 'chunk').map((o) => o.code).join('')
result.bundle = { minified_kb: +(code.length / 1024).toFixed(1), gzip_kb: +(gzipSync(code).length / 1024).toFixed(1), pass: code.length <= 300 * 1024 }

result.when = new Date().toISOString()
appendFileSync(join(out, 'runs.jsonl'), JSON.stringify(result) + '\n')
console.log(JSON.stringify(result, null, 1))
