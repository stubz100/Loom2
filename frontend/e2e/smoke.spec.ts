// End-to-end smoke (D68, ArtCraft P6 §3): each scenario drives the real UI with the mouse in headless Edge against the e2e build, a real
// orchestrator and the fake engine, and checks the outcome on the page and through the API. Scenarios are independent: each opens a
// fresh page and picks its own assets; they share one project (global-setup.ts), so none relies on another's leftovers.
import { api, centre, contextChoose, env, expect, openApp, test, thumbsLoaded, tiles } from './fixtures'

interface AssetLite { id: string; state: string; job_id: string | null }
interface Group { id: string; name: string; items: { kind: string; id: string }[] }

test('open the project: the Catalogue grid shows tiles and their thumbnails load', async ({ page }) => {
  expect((await api<{ variant: string }>('GET', '/health')).variant).toBe(env().variant)          // LOOM2_VARIANT reached the orchestrator
  await openApp(page, { suite: 'catalogue' })
  await expect(tiles(page).first()).toBeVisible()
  expect(await thumbsLoaded(page, 12)).toBeGreaterThanOrEqual(Math.min(12, env().assets))
  await expect(page.locator('.place-row', { hasText: 'Library' }).locator('.n')).toHaveText(/^\d+$/)
})

test('Keep / Reject / Clear through the tile context menu change the tile and the asset', async ({ page }) => {
  await openApp(page, { suite: 'catalogue' })
  const tile = tiles(page).nth(3)
  const id = (await tile.getAttribute('data-id'))!
  await contextChoose(page, tile, 'Keep')
  await expect(tile.locator('.badge-dot.keep')).toBeVisible()
  await expect(tile).not.toHaveClass(/\breject\b/)
  await expect.poll(async () => (await api<AssetLite>('GET', `/assets/${id}`)).state).toBe('keep')
  await contextChoose(page, tile, 'Reject')
  await expect(tile).toHaveClass(/\breject\b/)
  await expect(tile.locator('.badge-dot.reject')).toBeVisible()
  await expect.poll(async () => (await api<AssetLite>('GET', `/assets/${id}`)).state).toBe('reject')
  await contextChoose(page, tile, 'Clear keep / reject')
  await expect(tile.locator('.badge-dot.keep, .badge-dot.reject')).toHaveCount(0)
  await expect.poll(async () => (await api<AssetLite>('GET', `/assets/${id}`)).state).toBe('none')
})

test('drag a tile onto a group in Places with the mouse: it moves onto that page', async ({ page }) => {
  const name = `drop ${Date.now().toString(36)}`
  const g = await api<Group>('POST', '/groups', { name })
  await openApp(page, { suite: 'catalogue' })
  const tile = tiles(page).nth(1)
  const id = (await tile.getAttribute('data-id'))!
  const row = page.locator('.place-row', { hasText: name })
  await expect(row).toBeVisible()
  // a real pointer drag (frame/drag.ts: pointer events, never HTML5 drag and drop): press, pass the 5 px threshold, carry, release
  const from = await centre(tile), to = await centre(row)
  await page.mouse.move(from.x, from.y)
  await page.mouse.down()
  await page.mouse.move(from.x + 12, from.y + 8, { steps: 3 })
  await expect(page.locator('.drag-ghost')).toBeVisible()
  await page.mouse.move(to.x, to.y, { steps: 12 })
  await expect(row).toHaveClass(/drop-over/)
  await page.mouse.up()
  await expect(page.locator('.drag-ghost')).toHaveCount(0)
  await expect(row.locator('.n')).toHaveText('1')
  await expect.poll(async () => (await api<{ group: Group }>('GET', `/groups/${g.id}`)).group.items.map((i) => i.id)).toEqual([id])
  await expect(page.locator(`.cat-grid .tile[data-id="${id}"]`)).toHaveCount(0)        // it left Unprocessed
})

test('Generate with Klein 4B: the fake engine answers and the new asset lands in Unprocessed', async ({ page }) => {
  const before = (await api<Record<string, number>>('GET', '/assets/counts')).unprocessed ?? 0
  await openApp(page, { suite: 'generate', tab: 'model' })
  await page.locator('.model-card').filter({ has: page.locator('span', { hasText: /^Klein 4B$/ }) }).click()
  await expect(page.locator('.model-card.active span').first()).toHaveText('Klein 4B')
  await page.locator('nav.rail button[title^="Prompt"]').click()
  await page.locator('.segmented button', { hasText: /^Text$/ }).click()
  await page.locator('.panel textarea').fill('a lighthouse on a cliff at dusk, storm clouds, wide shot')
  const go = page.locator('.panel .foot button.primary', { hasText: /^Generate/ })
  await expect(go).toBeEnabled()
  const count = Number((await go.textContent())!.match(/Generate (\d+)/)![1])
  await go.click()
  await expect.poll(async () => (await api<Record<string, number>>('GET', '/assets/counts')).unprocessed ?? 0, { timeout: 45_000 }).toBe(before + count)
  const newest = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=unprocessed&sort=created_desc&limit=1')).items[0]
  // the job ran the model chosen in the UI (its id comes from /capabilities, D65 — no model id in the test)
  const caps = await api<{ models: Record<string, { label: string }> }>('GET', '/capabilities')
  const klein4b = Object.entries(caps.models).find(([, m]) => m.label === 'Klein 4B')![0]
  const job = (await api<{ items: { id: string; status: string; recipe: { model_id?: string } }[] }>('GET', '/jobs')).items.find((j) => j.id === newest.job_id)
  expect(job?.status).toBe('done')
  expect(job?.recipe.model_id).toBe(klein4b)
  await page.locator('nav.tabs button.tab', { hasText: 'Catalogue' }).click()
  await page.locator('.place-row', { hasText: 'Unprocessed' }).locator('button.place-open').click()
  await expect(page.locator('.place-row', { hasText: 'Unprocessed' }).locator('.n')).toHaveText(String(before + count))
  const tile = page.locator(`.cat-grid .tile[data-id="${newest.id}"]`)
  await expect(tile).toBeVisible()
  await expect.poll(() => tile.locator('img').evaluate((i: HTMLImageElement) => i.complete && i.naturalWidth > 0)).toBe(true)
})

test('Edit opens from an asset on WebGL2, a mouse stroke dirties the document and Save stores it', async ({ page }) => {
  await openApp(page, { suite: 'catalogue', renderer: 'webgl' })
  const tile = tiles(page).nth(5)
  await contextChoose(page, tile, 'Open in Edit')
  await expect(page.locator('.badge-renderer')).toHaveText(/WebGL2/)
  const canvas = page.locator('.edit-canvas canvas')
  await expect(canvas).toBeVisible()
  const docId = await page.waitForFunction(() => (window as unknown as { __loom2Editor: { getState: () => { doc: { id: string } | null } } }).__loom2Editor.getState().doc?.id ?? null).then((h) => h.jsonValue() as Promise<string>)
  await page.locator('button[title^="Brush"]').first().click()
  const box = (await canvas.boundingBox())!
  const [cx, cy] = [box.x + box.width / 2, box.y + box.height / 2]
  await page.mouse.move(cx - 120, cy - 20)
  await page.mouse.down()
  for (let i = 1; i <= 24; i++) await page.mouse.move(cx - 120 + i * 10, cy - 20 + Math.sin(i / 3) * 30)
  await page.mouse.up()
  const save = page.locator('.panel .foot button.primary')
  await expect(save).toHaveText('Save •')
  await save.click()
  await expect(save).toHaveText('Save')
  await expect.poll(async () => (await api<{ saved_at: string | null }>('GET', `/documents/${docId}`)).saved_at).not.toBeNull()
})

test('Animate: the tile menu fills the start and the end slots', async ({ page }) => {
  await openApp(page, { suite: 'catalogue' })
  const [a, b] = [tiles(page).nth(6), tiles(page).nth(7)]
  const [idA, idB] = [await a.getAttribute('data-id'), await b.getAttribute('data-id')]
  await contextChoose(page, a, 'Animate from this frame (start)')
  const slots = page.locator('.slots .slot')
  await expect(slots.nth(0).locator('img')).toBeVisible()
  await page.locator('nav.tabs button.tab', { hasText: 'Catalogue' }).click()
  await contextChoose(page, page.locator(`.cat-grid .tile[data-id="${idB}"]`), 'Use as the end frame in Animate')
  await expect(slots.nth(1).locator('img')).toBeVisible()
  for (const [k, id] of [[0, idA], [1, idB]] as const) {
    await expect.poll(() => slots.nth(k).locator('img').evaluate((i: HTMLImageElement) => i.complete && i.naturalWidth > 0)).toBe(true)
    expect(await slots.nth(k).locator('img').getAttribute('src')).toContain(`/thumbs/${id}/`)
  }
})
