// Perf script (D68, ArtCraft P6 §4): startup to the first painted tile, Bin → World's Edit → Bin switch times, Edit re-entry and the
// Bin's scroll frame pacing (B2, D159: the Catalogue is gone), measured inside the page (performance.now(), requestAnimationFrame) so Playwright's own round trips stay
// out of the numbers. Written to bench/perf/<yyyy-mm-dd>.json (one file per day: a later run the same day replaces it); compare with
// `python scripts/perf_compare.py`. Headless Edge on WebGL2 (SwiftShader when there is no GPU): the numbers track change on one machine,
// they are not the author's display-presented frame times (scripts/edit_headed_check.py perf measures those in a visible window).
import { execSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { cpus, totalmem } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Page } from '@playwright/test'
import { appUrl, binTiles, contextChoose, env, expect, openHome, openShell, test } from './fixtures'

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
const RUNS = Number(process.env.LOOM2_PERF_RUNS ?? 5)

type Stat = { median: number; min: number; max: number; runs: number[] }
const stat = (xs: number[]): Stat => {
  const s = [...xs].sort((a, b) => a - b)
  const r1 = (v: number) => Math.round(v * 10) / 10
  return { median: r1(s[Math.floor(s.length / 2)]), min: r1(s[0]), max: r1(s[s.length - 1]), runs: xs.map(r1) }
}
const metrics: Record<string, unknown> = {}

test.describe.configure({ mode: 'serial' })

const TILE_IMG = '[data-testid="bin-grid"] .w-tile img'
/** Records, from navigation start, the first animation frame after a Bin tile's thumbnail has decoded — Imports opened in the page as soon as
 *  the tree shows it (the Bin opens on no home). */
const FIRST_TILE = `(() => { let opened = false; const tick = () => { const i = document.querySelector('${TILE_IMG}');
  if (!opened) { const b = document.querySelector('[data-testid="bin-tree"] .b-node[data-path="imports"] .b-open'); if (b) { opened = true; b.click() } }
  if (i && i.complete && i.naturalWidth > 0) requestAnimationFrame((t) => { window.__perfFirstTile = t }); else requestAnimationFrame(tick) }; requestAnimationFrame(tick) })()`

/** Readiness checks, installed in the page before it loads: the Bin shows a decoded thumbnail; Edit has a Pixi Application on a canvas on
 *  screen with the document's layers in its stage and a frame rendered since the switch (B2, D159: the layers unmount what they do not show,
 *  so a re-entry builds a new Application). */
const READY = `window.__perfReady = {
  bin: () => { const i = document.querySelector('${TILE_IMG}'); return !!i && i.complete && i.naturalWidth > 0 },
  edit: () => { const w = window; const app = w.__loom2App; const ed = w.__loom2Editor && w.__loom2Editor.getState(); const world = app && app.stage && app.stage.children[0]
    return !!(app && app.canvas && app.canvas.isConnected && app.canvas.getBoundingClientRect().width > 0 && w.__loom2RenderMs !== undefined && ed && ed.doc && !ed.loading && world && world.children[1] && world.children[1].children.length > 0) } }`
type PerfWindow = Window & { __perfReady: Record<string, () => boolean>; __loom2RenderMs?: number; __loom2App?: unknown }

/** Click a layer tab inside the page; resolve with the ms until the layer is ready on an animation frame, plus one more frame. */
async function switchTo(page: Page, label: string, ready: 'bin' | 'edit'): Promise<number> {
  return page.evaluate(([label, ready]) => new Promise<number>((ok, fail) => {
    const w = window as unknown as PerfWindow
    const tab = [...document.querySelectorAll<HTMLButtonElement>('nav.tabs button.tab')].find((b) => b.textContent?.startsWith(label))
    if (!tab) { fail(new Error(`no ${label} tab`)); return }
    const t0 = performance.now()
    tab.click()
    const tick = () => { if (performance.now() - t0 > 30_000) fail(new Error(`${label} not ready in 30 s`)); else if (w.__perfReady[ready]()) requestAnimationFrame(() => ok(performance.now() - t0)); else requestAnimationFrame(tick) }
    requestAnimationFrame(tick)
  }), [label, ready] as const)
}
const editReady = (page: Page) => page.waitForFunction(() => (window as unknown as PerfWindow).__perfReady.edit(), null, { timeout: 60_000 })

test('startup: navigation to the first painted Bin tile', async ({ browser }) => {
  const runs: number[] = []
  for (let i = 0; i < RUNS; i++) {
    const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 } })       // a fresh context each time: no HTTP cache, no localStorage
    const page = await ctx.newPage()
    await page.addInitScript(FIRST_TILE)
    await page.goto(`${appUrl()}#bin`)
    const h = await page.waitForFunction(() => (window as unknown as { __perfFirstTile?: number }).__perfFirstTile, null, { timeout: 60_000 })
    runs.push((await h.jsonValue()) as number)
    await ctx.close()
  }
  metrics.startup_first_tile_ms = stat(runs)
})

test('layer switches: Bin → World\'s Edit (first entry), Edit → Bin, Edit re-entry', async ({ page }) => {
  await page.addInitScript(READY)
  await openShell(page, 'bin', { renderer: 'webgl' })
  await openHome(page, 'imports', 'pictures')
  await expect(binTiles(page).first()).toBeVisible()
  const t0 = Date.now()
  await contextChoose(page, binTiles(page).nth(2), 'Open in Edit')    // creates the document and opens World's Edit (first entry, incl. the document load)
  await editReady(page)
  metrics.edit_first_open_ms = Date.now() - t0                         // wall clock incl. a Playwright round trip: indicative
  await expect(page.locator('.badge-renderer')).toHaveText(/WebGL2/)
  const toBin: number[] = [], reEnter: number[] = []
  for (let i = 0; i < RUNS; i++) {
    await page.waitForTimeout(400)
    toBin.push(await switchTo(page, 'Bin', 'bin'))
    await page.waitForTimeout(400)
    await page.evaluate(() => { (window as unknown as PerfWindow).__loom2RenderMs = undefined })   // the next rendered frame is the re-entry's
    reEnter.push(await switchTo(page, 'World', 'edit'))                                         // World keeps its Edit mode
  }
  metrics.edit_to_bin_ms = stat(toBin)
  metrics.edit_reentry_ms = stat(reEnter)
  metrics.bin_edit_bin_roundtrip_ms = stat(toBin.map((t, i) => t + reEnter[i]))
})

const SCROLL_PX_PER_S = 4000, SCROLL_S = 5                      // a steady fast fling: 20 000 px (≈ 140 rows of tiles), past several 200-item pages

test('the Bin\'s scroll frame pacing over Imports', async ({ page }) => {
  await openShell(page, 'bin')
  await openHome(page, 'imports')
  await expect(binTiles(page).first()).toBeVisible()
  await page.waitForTimeout(1000)
  const r = await page.evaluate(([speed, secs]) => new Promise<Record<string, number>>((ok) => {
    const el = document.querySelector<HTMLElement>('[data-testid="bin-grid"] .b-grid')!
    // the idle animation-frame rate first (1 s), then the scroll: scrollTop follows the clock (speed px/s), so the distance does not depend
    // on the frame rate; a long frame is over 1.5 idle frames; `starved` frames are those where the loaded rows ended before the target
    let n = 0; const i0 = performance.now()
    const h0 = el.scrollHeight
    const idle = (t: number) => {
      if (t - i0 < 1000) { n++; requestAnimationFrame(idle); return }
      const hz = n / ((t - i0) / 1000)
      const gaps: number[] = []; let last = t, starved = 0; const s0 = t
      const step = (u: number) => {
        gaps.push(u - last); last = u
        const target = ((u - s0) / 1000) * speed
        el.scrollTop = target
        if (el.scrollTop < target - 1) starved++
        if (u - s0 < secs * 1000) { requestAnimationFrame(step); return }
        const g = [...gaps].sort((x, y) => x - y)
        ok({ idle_raf_hz: hz, fps: gaps.length / ((u - s0) / 1000), p50_ms: g[Math.floor(g.length / 2)], p95_ms: g[Math.floor(g.length * 0.95)], p99_ms: g[Math.floor(g.length * 0.99)], max_ms: g[g.length - 1],
          long_frames: gaps.filter((x) => x > 1.5 * (1000 / hz)).length, frames: gaps.length, starved_frames: starved, scrolled_px: el.scrollTop, rows_height_before_px: h0, rows_height_after_px: el.scrollHeight })
      }
      requestAnimationFrame(step)
    }
    requestAnimationFrame(idle)
  }), [SCROLL_PX_PER_S, SCROLL_S] as const)
  const tilesShown = await binTiles(page).count()
  metrics.bin_scroll = { px_per_s: SCROLL_PX_PER_S, seconds: SCROLL_S, ...Object.fromEntries(Object.entries(r).map(([k, v]) => [k, Math.round(v * 10) / 10])), tiles_in_dom_after: tilesShown }
})

const EXPECTED = ['startup_first_tile_ms', 'edit_first_open_ms', 'edit_to_bin_ms', 'edit_reentry_ms', 'bin_edit_bin_roundtrip_ms', 'bin_scroll']

test.afterAll(async ({ browser }) => {
  const missing = EXPECTED.filter((k) => !(k in metrics))
  if (missing.length) {                                          // a failed or filtered (-g) run never replaces the day's baseline
    console.log(`[perf] partial run (missing ${missing.join(', ')}): bench/perf not written
${JSON.stringify(metrics, null, 2)}`)
    return
  }
  const e = env()
  const git = (cmd: string) => { try { return execSync(cmd, { cwd: REPO, encoding: 'utf8' }).trim() } catch { return null } }
  const now = new Date()
  const day = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  const out = {
    schema_version: 1, date: day, recorded_at: now.toISOString(), commit: git('git rev-parse --short HEAD'), dirty: !!git('git status --porcelain'),
    variant: e.variant, assets: e.assets, runs: RUNS, browser: `msedge ${browser.version()} headless`, renderer: 'WebGL2 (forced: ?renderer=webgl)',
    machine: { os: `${process.platform} ${process.arch}`, cpu: (cpus()[0]?.model ?? '?').trim(), cores: cpus().length, ram_gb: Math.round(totalmem() / 2 ** 30) },
    metrics,
  }
  const dir = join(REPO, 'bench', 'perf')
  mkdirSync(dir, { recursive: true })
  writeFileSync(join(dir, `${day}.json`), JSON.stringify(out, null, 2) + '\n')
  console.log(`[perf] bench/perf/${day}.json\n${JSON.stringify(metrics, null, 2)}`)
})
