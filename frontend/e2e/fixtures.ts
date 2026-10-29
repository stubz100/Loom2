// Shared helpers of the end-to-end smoke and perf runs (D68): the run's environment (set by global-setup.ts), an authenticated API
// helper for arranging and checking state, the app URL, and a `page` fixture that fails a test on any uncaught page error or error toast.
import { test as base, expect, type Locator, type Page } from '@playwright/test'
import { PREVIEW_PORT } from '../playwright.config'

export interface E2EEnv { port: number; enginePort: number; token: string; state: string; project: string; assets: number; variant: 'full' | 'open' }

export const env = (): E2EEnv => {
  const raw = process.env.LOOM2_E2E
  if (!raw) throw new Error('LOOM2_E2E is not set: run through `npm run test:e2e` / `npm run perf` (global-setup.ts)')
  return JSON.parse(raw) as E2EEnv
}

/** The orchestrator's API with the run's token (D67), for arranging state and checking outcomes — never for the action under test. */
export async function api<T = unknown>(method: string, path: string, body?: unknown): Promise<T> {
  const e = env()
  const r = await fetch(`http://127.0.0.1:${e.port}${path}`, {
    method, headers: { 'X-Loom-Token': e.token, ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) throw new Error(`${method} ${path} → ${r.status} ${await r.text()}`)
  return (await r.json()) as T
}

/** The app in a browser: the token and port in the query (shell/tauri.ts discoverBackend), plus deep links (`suite`, `tab`, `renderer`). */
export function appUrl(params: Record<string, string> = {}): string {
  const e = env()
  return `http://127.0.0.1:${PREVIEW_PORT}/?${new URLSearchParams({ token: e.token, port: String(e.port), ...params })}`
}

/** Per page: what went wrong while it ran (page errors, console errors, failed requests, HTTP ≥ 400) — attached to a failed
 *  `openApp`, so a CI failure says why the app did not come up (2026-10-11: a bare "`.frame` not visible" could not be explained). */
const DIAG = new WeakMap<Page, string[]>()
export const diagnostics = (page: Page): string[] => (DIAG.get(page) ?? []).slice(-40)

/** Open the app and wait until the frame is up and the project is open. */
export async function openApp(page: Page, params: Record<string, string> = {}): Promise<void> {
  try {
    await page.goto(appUrl(params))
    await expect(page.locator('.frame')).toBeVisible()
    await page.waitForFunction(() => !!(window as unknown as { __loom2Session?: { getState: () => { project?: { open?: boolean } } } }).__loom2Session?.getState().project?.open)
  } catch (e) {
    const body = (await page.locator('body').innerText({ timeout: 2000 }).catch(() => '(no body)')).slice(0, 600)
    throw new Error(`${(e as Error).message}\n--- page diagnostics ---\n${diagnostics(page).join('\n') || '(none)'}\n--- page text ---\n${body}`)
  }
}

/** The centre of an element in page coordinates (for mouse gestures). */
export async function centre(l: Locator): Promise<{ x: number; y: number }> {
  await l.scrollIntoViewIfNeeded()
  const b = await l.boundingBox()
  if (!b) throw new Error('element has no box')
  return { x: b.x + b.width / 2, y: b.y + b.height / 2 }
}

/** Right-click `target` and choose the context-menu entry labelled exactly `label` (with the mouse, as the author works: D32). */
export async function contextChoose(page: Page, target: Locator, label: string): Promise<void> {
  await target.click({ button: 'right' })
  const item = page.locator('.ctx-menu button.item').filter({ has: page.locator('.lbl', { hasText: new RegExp(`^${label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`) }) })
  await expect(item).toBeEnabled()
  await item.click()
}

/** Tiles of the Catalogue grid, and a wait until the first `n` visible thumbnails have decoded (naturalWidth > 0). */
export const tiles = (page: Page) => page.locator('.cat-grid .tile')
/** D125: the Catalogue is the fourth top tab — the tab, then Places on its rail if the panel is folded (a click on the rail button of the
 *  section already showing folds the panel, so it is clicked only while the Places panel is not up). */
export async function openCatalogue(page: Page): Promise<void> {
  await page.locator('nav.tabs button.tab', { hasText: 'Catalogue' }).click()
  const rail = page.locator('nav.rail button[aria-label="Places"]')
  await expect(rail).toBeVisible()
  const places = page.locator('.panel .place-row').first()
  if (!(await places.isVisible().catch(() => false))) await rail.click()
  await expect(places).toBeVisible()
  await expect(page.locator('.cat-grid, .page-world').first()).toBeVisible()
}
export async function thumbsLoaded(page: Page, n: number, sel = '.cat-grid .tile img'): Promise<number> {
  const handle = await page.waitForFunction(([want, q]) => {
    const imgs = [...document.querySelectorAll<HTMLImageElement>(q)].slice(0, want)
    return imgs.length >= Math.min(want, 1) && imgs.every((i) => i.complete && i.naturalWidth > 0) ? imgs.length : 0
  }, [n, sel] as const)
  return (await handle.jsonValue()) as number
}

/** B2a (D159): the new shell at a place — `bin`, `world/…`, `shots/…`, `episode` — once the project is open. */
export async function openShell(page: Page, place = 'world', params: Record<string, string> = {}): Promise<void> {
  try {
    await page.goto(`${appUrl({ ui: '2', ...params })}#${place}`)
    await expect(page.locator('.frame.ui2')).toBeVisible()
    await page.waitForFunction(() => !!(window as unknown as { __loom2Session?: { getState: () => { project?: { open?: boolean } } } }).__loom2Session?.getState().project?.open)
  } catch (e) {
    const body = (await page.locator('body').innerText({ timeout: 2000 }).catch(() => '(no body)')).slice(0, 600)
    throw new Error(`${(e as Error).message}\n--- page diagnostics ---\n${diagnostics(page).join('\n') || '(none)'}\n--- page text ---\n${body}`)
  }
}
/** The tiles of the Bin layer's grid. */
export const binTiles = (page: Page) => page.locator('[data-testid="bin-grid"] .w-tile')
/** A home of the Bin's tree opened, its parents unfolded (`imports`, `world/sketches`, `world/character/<id>/v1` …). */
export async function openHome(page: Page, path: string, kind?: 'pictures' | 'clips' | 'audio' | 'models'): Promise<void> {
  const parts = path.split('/')
  for (let i = 1; i < parts.length; i++) {
    const chev = page.locator(`[data-testid="bin-tree"] .b-node[data-path="${parts.slice(0, i).join('/')}"] > .b-chev[aria-label="Unfold"]`)
    if (await chev.count()) await chev.click()
  }
  await page.locator(`[data-testid="bin-tree"] .b-node[data-path="${path}"] .b-open`).click()
  await expect(page.locator('[data-testid="bin-grid"] .w-path')).not.toHaveText('bin/')
  await expect(page.locator('[data-testid="bin-count"]')).toBeVisible()
  if (kind) {                                                                         // the kind chips filter on the server: wait for the read
    await page.locator('[data-testid="bin-grid"] .w-chips button', { hasText: kind }).click()
    await expect(page.locator('[data-testid="bin-grid"] .w-chips button.active')).toHaveText(kind)
    await expect(page.locator('[data-testid="bin-count"]')).toBeVisible()
  }
}

export const test = base.extend<{ page: Page }>({
  page: async ({ page }, run) => {
    const errors: string[] = []
    const diag: string[] = []
    DIAG.set(page, diag)
    page.on('pageerror', (e) => { errors.push(`pageerror: ${e.message}`); diag.push(`pageerror: ${e.message}`) })
    page.on('console', (m) => { if (m.type() === 'error') diag.push(`console: ${m.text().slice(0, 300)}`) })
    page.on('requestfailed', (r) => diag.push(`request failed: ${r.url()} — ${r.failure()?.errorText ?? '?'}`))
    page.on('response', (r) => { if (r.status() >= 400) diag.push(`HTTP ${r.status()} ${r.request().method()} ${r.url()}`) })
    await run(page)
    const toasts = await page.locator('.toast.error').allTextContents().catch(() => [])
    errors.push(...toasts.map((t) => `error toast: ${t}`))
    expect(errors, 'page errors / error toasts during the test').toEqual([])
  },
})
export { expect }
