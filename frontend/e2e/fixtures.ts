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

/** Open the app and wait until the frame is up and the project is open. */
export async function openApp(page: Page, params: Record<string, string> = {}): Promise<void> {
  await page.goto(appUrl(params))
  await expect(page.locator('.frame')).toBeVisible()
  await page.waitForFunction(() => !!(window as unknown as { __loom2Session?: { getState: () => { project?: { open?: boolean } } } }).__loom2Session?.getState().project?.open)
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
export async function thumbsLoaded(page: Page, n: number): Promise<number> {
  const handle = await page.waitForFunction((want) => {
    const imgs = [...document.querySelectorAll<HTMLImageElement>('.cat-grid .tile img')].slice(0, want)
    return imgs.length >= Math.min(want, 1) && imgs.every((i) => i.complete && i.naturalWidth > 0) ? imgs.length : 0
  }, n)
  return (await handle.jsonValue()) as number
}

export const test = base.extend<{ page: Page }>({
  page: async ({ page }, run) => {
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`))
    await run(page)
    const toasts = await page.locator('.toast.error').allTextContents().catch(() => [])
    errors.push(...toasts.map((t) => `error toast: ${t}`))
    expect(errors, 'page errors / error toasts during the test').toEqual([])
  },
})
export { expect }
