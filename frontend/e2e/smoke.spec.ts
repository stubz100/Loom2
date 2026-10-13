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
  const jobOf = async () => (await api<{ items: { id: string; status: string; recipe: { model_id?: string } }[] }>('GET', '/jobs')).items.find((j) => j.id === newest.job_id)
  await expect.poll(async () => (await jobOf())?.status, { timeout: 10_000 }).toBe('done')                // the asset lands a beat before the job's status flips (CI, full runner)
  expect((await jobOf())?.recipe.model_id).toBe(klein4b)
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

test('send-to by drag (D71): a tile held on the Generate tab opens it, the ghost says what a drop adds, a slot takes it, a repeat is refused', async ({ page }) => {
  await openApp(page, { suite: 'catalogue' })
  const tile = tiles(page).nth(3)
  const id = (await tile.getAttribute('data-id'))!
  const tab = page.locator('nav.tabs button.tab', { hasText: 'Generate' })
  const hint = page.locator('.drag-ghost .drop-hint')
  const from = await centre(tile), onTab = await centre(tab)
  await page.mouse.move(from.x, from.y)
  await page.mouse.down()
  await page.mouse.move(from.x + 12, from.y + 8, { steps: 3 })
  await page.mouse.move(onTab.x, onTab.y, { steps: 10 })
  await expect(hint).toHaveText(/^✓ Add as reference 1 of \d+ — or hold to open Generate$/)
  // resting on the tab for 600 ms opens Generate; the drag carries on to a particular slot
  await expect(page.locator('.ref-slots')).toBeVisible()
  await expect(page.locator('.drag-ghost')).toBeVisible()
  const slot = await centre(page.locator('.ref-slots .ref-slot').nth(1))
  await page.mouse.move(slot.x, slot.y, { steps: 8 })
  await expect(hint).toHaveText(/^✓ Add as reference 1 of \d+$/)
  await page.mouse.up()
  await expect(page.locator('.drag-ghost')).toHaveCount(0)
  await expect(page.locator('.ref-slots .ref-slot img')).toHaveCount(1)
  await expect(page.locator('.ref-slots .ref-slot img').first()).toHaveAttribute('src', new RegExp(id))
  // the same tile again, onto the tab: refused, and the ghost says why; nothing changes
  await page.locator('nav.tabs button.tab', { hasText: 'Catalogue' }).click()
  const again = await centre(page.locator(`.cat-grid .tile[data-id="${id}"]`))
  await page.mouse.move(again.x, again.y)
  await page.mouse.down()
  await page.mouse.move(again.x + 12, again.y + 8, { steps: 3 })
  await page.mouse.move(onTab.x, onTab.y, { steps: 10 })
  await expect(hint).toHaveText('✕ Already a reference')
  await expect(page.locator('.drag-ghost')).toHaveClass(/refused/)
  await page.waitForTimeout(800)                                          // a refused tab does not spring open
  await expect(tab).not.toHaveClass(/active/)
  await page.mouse.up()
  await tab.click()
  await expect(page.locator('.ref-slots .ref-slot img')).toHaveCount(1)
})

/** Press on `from`, carry the tile to `tab` and rest there until its suite is up (D71 spring-loaded tabs); the pointer stays down. */
async function carryAndHold(page: import('@playwright/test').Page, from: { x: number; y: number }, tab: string, up: string): Promise<void> {
  const onTab = await centre(page.locator('nav.tabs button.tab', { hasText: tab }))
  await page.mouse.move(from.x, from.y)
  await page.mouse.down()
  await page.mouse.move(from.x + 12, from.y + 8, { steps: 3 })
  await page.mouse.move(onTab.x, onTab.y, { steps: 10 })
  await expect(page.locator(up)).toBeVisible()
  await expect(page.locator('.drag-ghost')).toBeVisible()
}

test('spring-loaded tabs (D71) in Animate and Edit: hold, then drop on the end slot / the empty stage', async ({ page }) => {
  await openApp(page, { suite: 'catalogue' })
  const tile = tiles(page).nth(5)
  const id = (await tile.getAttribute('data-id'))!
  await carryAndHold(page, await centre(tile), 'Animate', '.slots.full')
  const end = page.locator('.slots .slot').nth(1)
  const onEnd = await centre(end)
  await page.mouse.move(onEnd.x, onEnd.y, { steps: 8 })
  await expect(page.locator('.drag-ghost .drop-hint')).toHaveText('✓ Set the end frame')
  await page.mouse.up()
  await expect(end.locator('img')).toHaveAttribute('src', new RegExp(id))
  await expect(page.locator('.slots .slot').nth(0).locator('img')).toHaveCount(0)        // the end slot only

  await page.locator('nav.tabs button.tab', { hasText: 'Catalogue' }).click()
  await carryAndHold(page, await centre(tiles(page).nth(6)), 'Edit', '.edit-empty')
  const stage = await centre(page.locator('.edit-empty'))
  await page.mouse.move(stage.x, stage.y, { steps: 8 })
  await expect(page.locator('.drag-ghost .drop-hint')).toHaveText('✓ Open in Edit')
  await page.mouse.up()
  await page.waitForFunction(() => !!(window as unknown as { __loom2Editor?: { getState: () => { doc?: unknown } } }).__loom2Editor?.getState().doc, null, { timeout: 30_000 })
})

test('the loupe is the send-to hub (D71): every verb on its bar; narrow, the secondary ones fold into More', async ({ page }) => {
  await openApp(page, { suite: 'catalogue' })
  await tiles(page).nth(7).dblclick()
  const hub = page.locator('.loupe .hub')
  await expect(hub).toBeVisible()
  for (const label of ['Keep', 'Reject', 'Rate', 'Edit', 'Reference', 'Animate', 'Re-run (same seed)', 'Variations (new seeds)', 'Duplicate', 'Move to group', 'Show lineage', 'Reveal in folder', 'More'])
    await expect(hub.getByRole('button', { name: label, exact: true })).toBeVisible()
  await hub.getByRole('button', { name: 'Animate', exact: true }).click()               // a press menu: click opens it
  await expect(page.locator('.ctx-menu button.item', { hasText: 'As the end frame' })).toBeVisible()
  await hub.getByRole('button', { name: 'Animate', exact: true }).click()               // a second press on the button closes it (Esc would close the loupe too)
  await expect(page.locator('.ctx-menu')).toHaveCount(0)
  await page.setViewportSize({ width: 900, height: 800 })
  await expect(hub.getByRole('button', { name: 'Duplicate', exact: true })).toBeHidden()
  await expect(hub.getByRole('button', { name: 'More', exact: true })).toBeVisible()
  await hub.getByRole('button', { name: 'Reference', exact: true }).click()
  await expect(page.locator('.ref-slots .ref-slot img')).toHaveCount(1)                  // Reference sends it to Generate
})

type EdWin = { __loom2Editor?: { getState: () => { doc?: { id: string }; tool: string } }; __loom2AiPanel?: { getState: () => { op: string; selMode: string } } }
const editorTool = (page: import('@playwright/test').Page) => page.evaluate(() => { const w = window as unknown as EdWin; const ed = w.__loom2Editor?.getState(); const ai = w.__loom2AiPanel?.getState()
  return ed ? { doc: !!ed.doc, tool: ed.tool, op: ai?.op, sel: ai?.selMode } : null })

test('quick actions (D71): "Remove background" in the Inspector reaches Edit with AI Select · Subject in one click; the deep link does too', async ({ page }) => {
  await openApp(page, { suite: 'catalogue' })
  await tiles(page).nth(8).click()
  const card = page.locator('.insp .quick-card', { hasText: 'Remove background' })
  await expect(card).toBeEnabled()
  await card.click()
  await expect.poll(() => editorTool(page), { timeout: 30_000 }).toEqual({ doc: true, tool: 'ai', op: 'select', sel: 'subject' })
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Edit/)
  await expect(page.locator('nav.rail button.active[title^="AI"]')).toBeVisible()

  await openApp(page, { suite: 'edit', tool: 'ai', ai: 'upscale' })
  await expect.poll(() => editorTool(page), { timeout: 30_000 }).toMatchObject({ tool: 'ai', op: 'upscale' })
})

test('remappable keys (D72): Keep to G is refused (Cycle grouping has it); Keep to J — menu, tooltip and help show J, J keeps, K does not, it survives a reload', async ({ page }) => {
  await openApp(page, { suite: 'catalogue' })
  const openKeys = async () => {
    await page.locator('nav.rail').getByRole('button', { name: 'Settings…', exact: true }).click()
    const row = page.locator('.keys-row[data-cmd="cat.keep"]')
    await row.scrollIntoViewIfNeeded()
    return row
  }
  const closeSettings = () => page.locator('.modal-backdrop').click({ position: { x: 4, y: 4 } })
  let row = await openKeys()
  await expect(row.locator('.keys-chord')).toHaveText('K')
  await row.locator('.keys-chord').click()
  await expect(row.locator('.keys-chord')).toHaveText('press a key…')
  await page.keyboard.press('g')                                                         // the plan's example: G is Cycle grouping's — refused, with its name
  await expect(row.locator('.keys-note.error')).toContainText('“Cycle grouping”')
  await expect(row.locator('.keys-chord')).toHaveText('K')
  await row.locator('.keys-chord').click()
  await page.keyboard.press('j')
  await expect(row.locator('.keys-chord')).toHaveText('J')
  await expect(row.locator('.keys-note')).toHaveText('now J')
  await closeSettings()

  const [a, b] = [tiles(page).nth(10), tiles(page).nth(11)]
  const [ida, idb] = [(await a.getAttribute('data-id'))!, (await b.getAttribute('data-id'))!]
  for (const id of [ida, idb]) await api('PATCH', `/assets/${id}`, { state: 'none' })      // arranged: the synthetic project gives some tiles a state
  await a.click({ button: 'right' })                                                     // the tile menu shows J
  await expect(page.locator('.ctx-menu button.item', { hasText: /^Keep/ }).locator('kbd')).toHaveText('J')
  await a.click()                                                                         // closes the menu and selects the tile (Esc would clear it)
  await expect(page.locator('.ctx-menu')).toHaveCount(0)
  await a.dblclick()                                                                      // the loupe hub's Keep button: its tooltip says J
  await expect(page.locator('.loupe .hub button[aria-label="Keep"]')).toHaveAttribute('title', 'Keep (J)')
  await page.keyboard.press('j')                                                          // J keeps
  await expect.poll(async () => (await api<AssetLite>('GET', `/assets/${ida}`)).state).toBe('keep')
  await page.keyboard.press('Escape')
  await expect(page.locator('.loupe')).toHaveCount(0)
  await b.click()
  await page.keyboard.press('k')                                                          // K does nothing now
  await page.waitForTimeout(500)
  expect((await api<AssetLite>('GET', `/assets/${idb}`)).state).not.toBe('keep')
  await page.keyboard.press('?')                                                          // help lists Keep with J
  await expect(page.locator('.cmd-help .row', { hasText: /^Keep/ }).first().locator('kbd')).toHaveText('J')
  await page.keyboard.press('Escape')

  await page.reload()                                                                     // a restart keeps it
  await expect(page.locator('.frame')).toBeVisible()
  row = await openKeys()
  await expect(row.locator('.keys-chord')).toHaveText('J')
  await expect(row).toHaveClass(/changed/)
  await row.getByRole('button', { name: 'Reset the key of Keep' }).click()
  await expect(row.locator('.keys-chord')).toHaveText('K')
})

test('@mentions (D73): "@hero walks into @tavern" — both groups give references in the preview, and the job records both at their revisions', async ({ page }) => {
  const tag = Date.now().toString(36)
  const [heroName, tavernName] = [`hero ${tag}`, `tavern ${tag}`]                   // names with a space, as people write them
  const hero = await api<Group>('POST', '/groups', { name: heroName }), tavern = await api<Group>('POST', '/groups', { name: tavernName })
  const free = (await api<{ items: (AssetLite & { kind: string })[] }>('GET', '/assets?folder=unprocessed&limit=40')).items.filter((a) => a.kind === 'image')
  await api('POST', '/groups/move', { items: free.slice(0, 3).map((a) => ({ kind: 'asset', id: a.id })), to: hero.id })
  await api('POST', '/groups/move', { items: free.slice(3, 5).map((a) => ({ kind: 'asset', id: a.id })), to: tavern.id })
  await openApp(page, { suite: 'generate', tab: 'model' })
  await page.locator('.model-card').filter({ has: page.locator('span', { hasText: /^Klein 4B$/ }) }).click()   // takes 4 references
  await page.locator('nav.rail button[title^="Prompt"]').click()
  await page.locator('.segmented button', { hasText: /^Text$/ }).click()
  const ta = page.locator('.text-prompt textarea')
  await ta.fill('')
  await ta.click()
  const mention = async (name: string) => {
    await page.keyboard.type('@')                                                       // typing @ opens the album's groups at the field
    await page.locator('.ctx-menu button.item', { hasText: name }).click()
    await expect(ta).toBeFocused()                                                      // the pick hands the caret back to the field
  }
  await mention(heroName)
  await page.keyboard.type('walks into ')
  await mention(tavernName)
  await expect(ta).toHaveValue(`@${heroName} walks into @${tavernName} `)
  await expect(page.locator('.mention-chips .mchip')).toHaveCount(2)
  await expect(page.locator('.ref-from-mentions .ref-slot')).toHaveCount(4)             // turns: hero, tavern, hero, tavern — the model's 4
  await expect(page.locator('.mchip', { hasText: heroName })).toContainText('2 images')
  await expect(page.locator('.preview-box')).toContainText(`${heroName} walks into ${tavernName}. Image 1 shows ${heroName}. Image 2 shows ${tavernName}.`)
  const go = page.locator('.panel .foot button.primary', { hasText: /^Generate/ })
  await go.click()
  const job = await expect.poll(async () => (await api<{ items: { status: string; recipe: { mentions?: { group_id: string; revision: number; asset_ids: string[] }[] } }[] }>('GET', '/jobs')).items
    .find((j) => j.recipe.mentions?.some((m) => m.group_id === hero.id))?.status, { timeout: 45_000 }).toBe('done')
  void job
  const rec = (await api<{ items: { recipe: { mentions: { group_id: string; revision: number; asset_ids: string[] }[] } }[] }>('GET', '/jobs')).items.find((j) => j.recipe.mentions?.some((m) => m.group_id === hero.id))!.recipe
  for (const g of [hero, tavern]) {
    const m = rec.mentions.find((x) => x.group_id === g.id)!
    expect(m.revision).toBe((await api<{ group: { revision: number } }>('GET', `/groups/${g.id}`)).group.revision)
    expect(m.asset_ids).toHaveLength(2)
  }
  await page.locator('.mchip', { hasText: tavernName }).getByRole('button').click()      // the chip's ×: the name stays as plain text
  await expect(ta).toHaveValue(`@${heroName} walks into ${tavernName} `)
  await expect(page.locator('.mention-chips .mchip')).toHaveCount(1)
})

test('a suite whose code fails to load says so and recovers (no blank window): the Edit chunk refused, then a reload', async ({ page }) => {
  test.setTimeout(150_000)                                                             // the reload + WebGL boot takes long on the CI runners
  await page.route(/EditSuite-[\w-]+\.js$/, (r) => r.abort('failed'))               // the network refuses Edit's code (the idle preload hits it too)
  await openApp(page, { suite: 'catalogue' })
  await page.locator('nav.tabs button.tab', { hasText: 'Edit' }).click()
  await expect(page.locator('.stage .render-error')).toContainText("Edit's code could not be loaded")
  await expect(page.locator('.render-error')).toHaveCount(1)                          // one explanation, in the middle; the panel says one line
  await expect(page.locator('.render-error-line')).toContainText('Edit is not available')
  await expect(page.locator('.frame')).toBeVisible()                                  // the rest of the app stays
  await page.locator('nav.tabs button.tab', { hasText: 'Catalogue' }).click()
  await expect(tiles(page).first()).toBeVisible()
  await page.unroute(/EditSuite-[\w-]+\.js$/)
  await page.locator('nav.tabs button.tab', { hasText: 'Edit' }).click()
  await page.locator('.stage .render-error').getByRole('button', { name: 'Reload the app' }).click()   // the browser keeps a failed module: reload
  await expect(page.locator('.frame')).toBeVisible()
  await page.locator('nav.tabs button.tab', { hasText: 'Edit' }).click()
  await expect(page.locator('.edit-empty')).toBeVisible({ timeout: 90_000 })         // the code loads this time (the CI runner takes long over the reload + WebGL boot; 45 s failed once on the open runner, 2026-10-13)
})

test('a new angle (P14, D82): "New angle" on a tile opens the Angle tab with the source, the pad picks the move, the job lands with reangle lineage', async ({ page }) => {
  const before = (await api<Record<string, number>>('GET', '/assets/counts')).unprocessed ?? 0
  await openApp(page, { suite: 'catalogue' })
  const src = tiles(page).nth(8)
  await src.click()
  const srcId = await src.getAttribute('data-id')
  await page.locator('.insp .quick-card', { hasText: 'New angle' }).click()
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Generate/)
  await expect(page.locator('nav.rail button.active[title^="New angle"]')).toBeVisible()
  await expect(page.locator('.angle-tab .ref-slot.source img')).toBeVisible()
  await page.locator('.angle-pad button', { hasText: /^Wide$/ }).click()
  const go = page.locator('.panel .foot button.primary', { hasText: /^New angle/ })
  await expect(go).toBeEnabled({ timeout: 15_000 })
  await expect(page.locator('.panel .foot .estimate')).toContainText(/Klein/)                 // auto: a framing move runs Klein (D77)
  await go.click()
  // the result is found through its job, not as "the newest asset": on a slow runner an earlier scenario's job (the @mentions one, four
  // parents) can land in Unprocessed between the click and the poll (CI on bb1f90a, open variant)
  type JobLite = { id: string; status: string; recipe: { kind: string; move?: string }; result: { asset_ids?: string[] } | null }
  const jobOf = async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.recipe?.kind === 'reangle')
  await expect.poll(async () => (await jobOf())?.status, { timeout: 45_000 }).toBe('done')
  const job = (await jobOf())!
  expect(job.recipe).toMatchObject({ kind: 'reangle', move: 'wide' })
  expect(job.result?.asset_ids).toHaveLength(1)
  const newest = await api<AssetLite & { parents: string[]; lineage_kind: string | null; state: string }>('GET', `/assets/${job.result!.asset_ids![0]}`)
  expect(newest.parents).toEqual([srcId])                                                               // lineage: the source …
  expect(newest.lineage_kind).toBe('reangle')
  expect(newest.state).toBe('none')                                                                     // … it landed in Unprocessed
  await expect.poll(async () => (await api<Record<string, number>>('GET', '/assets/counts')).unprocessed ?? 0, { timeout: 10_000 }).toBeGreaterThanOrEqual(before + 1)
  const edges = await api<{ parents: { from_id: string; kind: string }[] }>('GET', `/lineage/${newest.id}`)
  expect(edges.parents.map((p) => [p.from_id, p.kind])).toEqual([[srcId, 'reangle']])                   // … and the edge kind
})

test('a sequence (P17, D83): a fake-engine clip goes on a new lane from the bin, the document saves with its revision, the EDL is written', async ({ page }) => {
  await openApp(page, { suite: 'catalogue' })
  await contextChoose(page, tiles(page).nth(6), 'Animate from this frame (start)')
  const go = page.locator('.panel .foot button.primary', { hasText: /^Animate/ })
  await expect(go).toBeEnabled({ timeout: 20_000 })
  await go.click()
  await page.locator('nav.rail button[title^="Sequence"]').click()
  await expect(page.locator('.seq-clip-card')).toHaveCount(1, { timeout: 120_000 })    // the clip lands when its proxy is ready (clip.ready)
  await page.locator('.seq-list-head button[title^="New sequence"]').click()
  const dialog = page.locator('.modal.ask')
  await dialog.locator('input').fill('Reel one')
  await dialog.locator('button.primary').click()
  await expect(page.locator('.seq-row.active')).toContainText('Reel one')
  await page.locator('.seq-clip-card button').first().click()                            // + : add the clip to the end of the lane
  await expect(page.locator('.seq-clip')).toHaveCount(1)
  await expect(page.locator('.seq-canvas')).toBeVisible()
  const thumb = page.locator('.seq-clip .seq-thumbs img').first()                          // C24 frame thumbnails across the block
  await expect(thumb).toBeAttached()
  await expect.poll(() => thumb.evaluate((i: HTMLImageElement) => i.complete && i.naturalWidth > 0), { timeout: 15_000 }).toBe(true)
  await expect.poll(async () => (await api<{ items: { name: string; revision: number; clips: unknown[] }[] }>('GET', '/timelines')).items.find((t) => t.name === 'Reel one')?.revision ?? 0, { timeout: 10_000 }).toBeGreaterThanOrEqual(1)
  const tl = (await api<{ items: { id: string; name: string; clips: { out: number }[] }[] }>('GET', '/timelines')).items.find((t) => t.name === 'Reel one')!
  expect(tl.clips).toHaveLength(1)
  await page.locator('.seq-insp button', { hasText: /^EDL$/ }).click()
  await expect(page.locator('.seq-insp .hint', { hasText: 'last:' })).toContainText('.edl')
  const exported = await api<{ format: string; text: string; path: string }>('POST', `/timelines/${tl.id}/export`, { format: 'edl' })
  expect(exported.text).toContain('TITLE: Reel one')
  expect(exported.text).toContain('V     C')
  // the draft render: a CPU job that becomes a second clip in the bin, with lineage to the first
  await page.locator('.seq-insp button', { hasText: /^Render draft$/ }).click()
  await expect(page.locator('.seq-clip-card')).toHaveCount(2, { timeout: 120_000 })
  const clips = await api<{ items: { id: string; model_id: string; frames: number; fps: number; asset_id: string | null }[] }>('GET', '/clips')
  const render = clips.items.find((c) => c.model_id === 'sequence')!
  const source = clips.items.find((c) => c.model_id !== 'sequence')!
  expect(render.frames).toBe(Math.round(tl.clips[0].out * 24 / source.fps))                 // a 16 fps clip takes its duration on the 24 fps lane
  expect(render.fps).toBe(24)
  const asset = await api<{ parents: string[]; lineage_kind: string | null }>('GET', `/assets/${render.asset_id}`)
  expect(asset.lineage_kind).toBe('render')
  expect(asset.parents).toHaveLength(1)
})

test('a stage (P13 / ST1, D81): a new stage gets a set and a figure from the Library, the Outliner lists them, the document saves and survives a reload', async ({ page }) => {
  await openApp(page, { suite: 'stage' })
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Stage/)
  await page.locator('.placeholder button', { hasText: /^New stage/ }).click()
  const dialog = page.locator('.modal.ask')
  await dialog.locator('input').fill('Alley at night')
  await dialog.locator('button.primary').click()
  await expect(page.locator('.stage-row.active')).toContainText('Alley at night')
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await page.locator('.stage-empty button', { hasText: /^Add set · room$/ }).click()
  await page.locator('.lib-grid button', { hasText: /^Adult/ }).click()                        // the Library's figure card
  await page.locator('nav.rail button[title^="Outliner"]').click()
  await expect(page.locator('.outl-row .kind')).toHaveCount(2)
  await expect(page.locator('.outl-row.active', { has: page.locator('.kind') }).locator('.name')).toHaveText('Figure 1')   // the last added is selected (the camera row is "active" in its own sense)
  await expect(page.locator('.inspector .stage-insp h4')).toContainText('Figure 1')
  await expect.poll(async () => (await api<{ items: { name: string; revision: number; objects: { kind: string }[] }[] }>('GET', '/stages')).items.find((s) => s.name === 'Alley at night')?.objects.length ?? 0, { timeout: 10_000 }).toBe(2)
  const before = (await api<{ items: { id: string; name: string; revision: number }[] }>('GET', '/stages')).items.find((s) => s.name === 'Alley at night')!
  expect(before.revision).toBeGreaterThanOrEqual(1)
  // camera view shows the framing rectangle; the free view does not
  await page.locator('nav.rail button[title^="Cameras"]').click()
  await page.locator('.stage-panel button', { hasText: /^Look through$/ }).click()
  await expect(page.locator('.frame-guides')).toBeVisible()
  await expect(page.locator('.view-tag')).toContainText('35 mm')
  await page.screenshot({ path: 'node_modules/.e2e/stage-camera-view.png' })                     // a look for the journal: the framing rectangle over the set
  await page.reload()
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Stage/)
  await page.locator('.stage-row', { hasText: 'Alley at night' }).click()
  await page.locator('nav.rail button[title^="Outliner"]').click()
  await expect(page.locator('.outl-row .kind')).toHaveCount(2)
})

test('posing (P13 / ST2, D81): the Poses tab applies a preset, mirrors it, edits one joint by number and saves the pose to the project library', async ({ page }) => {
  await openApp(page, { suite: 'stage' })
  await page.locator('.placeholder button', { hasText: /^New stage/ }).click()
  const dialog = page.locator('.modal.ask')
  await dialog.locator('input').fill('Crossing')
  await dialog.locator('button.primary').click()
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await page.locator('.stage-empty button', { hasText: /Adult/ }).click()                       // the empty-stage card adds (and selects) a figure
  await page.locator('nav.rail button[title^="Poses"]').click()
  await expect(page.locator('.stage-panel .head b')).toHaveText('Figure 1')
  type Doc = { name: string; objects: { kind: string; pose: { preset: string; joints: Record<string, number[]> } | null }[] }
  const figure = async () => (await api<{ items: Doc[] }>('GET', '/stages')).items.find((s) => s.name === 'Crossing')?.objects.find((o) => o.kind === 'mannequin')   // the save is debounced: may be absent at first
  const WALK: Record<string, number[]> = { r_shoulder: [22, 0, -6], r_elbow: [0, 0, 0] }                                 // builders.ts POSES.walk (the right arm)
  await page.locator('.lib-grid button', { hasText: /^walk$/ }).click()
  await expect.poll(async () => (await figure())?.pose?.preset, { timeout: 10_000 }).toBe('walk')
  // the mouse on the figure: a click on the elbow's picker selects that joint (the rotate gizmo moves there)
  const at = async (what: string) => (await page.evaluate((w) => (window as unknown as { __loom2Stage: { screenOf: (at: string) => { x: number; y: number } | null } }).__loom2Stage.screenOf(w), what))!
  const elbow = await at('r_elbow')
  await page.mouse.click(elbow.x, elbow.y)
  await expect(page.locator('.stage-panel select').last()).toHaveValue('r_elbow')
  // a click on the right hand's handle puts a translate gizmo there; dragging its centre moves the hand, the forearm and upper arm follow (two-bone IK)
  const hand = await at('r_arm')
  await page.mouse.click(hand.x, hand.y)
  await expect(page.locator('.stage-panel select').last()).toHaveValue('')
  const goal = { x: hand.x + 28, y: hand.y - 36 }
  await page.mouse.move(hand.x, hand.y); await page.mouse.down(); await page.mouse.move(goal.x, goal.y, { steps: 10 }); await page.mouse.up()
  const left = (j: Record<string, number[]> | undefined) => !!j?.r_shoulder && !!j.r_elbow && (j.r_shoulder.some((v, i) => Math.abs(v - WALK.r_shoulder[i]) > 1) || j.r_elbow.some((v, i) => Math.abs(v - WALK.r_elbow[i]) > 1))
  await expect.poll(async () => left((await figure())?.pose?.joints), { timeout: 10_000 }).toBe(true)                      // the commit writes every joint; the arm left the walk preset
  const ik = (await figure())!.pose!.joints
  expect(Object.keys(ik)).toHaveLength(12)
  const after = await at('r_arm')
  expect(Math.hypot(after.x - goal.x, after.y - goal.y)).toBeLessThan(Math.hypot(hand.x - goal.x, hand.y - goal.y) / 2)    // the hand went to (or toward, if out of reach) the goal
  // Mirror writes every joint explicitly; a second mirror is the first pose again, so the two are each other's left / right swap
  await page.locator('.stage-panel button', { hasText: /^Mirror the pose$/ }).click()
  await expect.poll(async () => JSON.stringify((await figure())?.pose?.joints) !== JSON.stringify(ik), { timeout: 10_000 }).toBe(true)
  const m1 = (await figure())!.pose!.joints
  await page.locator('.stage-panel button', { hasText: /^Mirror the pose$/ }).click()
  await expect.poll(async () => JSON.stringify((await figure())?.pose?.joints) !== JSON.stringify(m1), { timeout: 10_000 }).toBe(true)
  const m2 = (await figure())!.pose!.joints
  expect(m1.r_hip[0]).toBe(m2.l_hip[0]); expect(m1.r_hip[1]).toBe(-m2.l_hip[1] || 0); expect(m1.l_shoulder[0]).toBe(m2.r_shoulder[0])
  // one joint by number: the Joint picker then the x field
  await page.locator('.stage-panel select').last().selectOption('r_elbow')
  const x = page.locator('.stage-panel .vec input').first()
  await x.fill('-90'); await x.dispatchEvent('change')
  await expect.poll(async () => (await figure())?.pose?.joints.r_elbow?.[0], { timeout: 10_000 }).toBe(-90)
  // save it to the project's library and see it back as a card
  await page.locator('.stage-panel button', { hasText: /^Save pose/ }).click()
  await dialog.locator('input').fill('crossing step')
  await dialog.locator('button.primary').click()
  await expect(page.locator('.pose-card button', { hasText: /^crossing step$/ })).toBeVisible()
  const lib = await api<{ poses: Record<string, { preset: string | null; joints: Record<string, number[]> }> }>('GET', '/stages/poses')
  expect(lib.poses['crossing step'].preset).toBe('walk')
  expect(lib.poses['crossing step'].joints.r_elbow[0]).toBe(-90)
  await page.screenshot({ path: 'node_modules/.e2e/stage-poses.png' })
})

test('a shot (P13 / ST3, D81): the Shot tab renders the five passes as stage-pass assets on the stage\'s album page, then the fake engine makes a shot with lineage to the clay pass', async ({ page }) => {
  await openApp(page, { suite: 'stage' })
  await page.locator('.placeholder button', { hasText: /^New stage/ }).click()
  const dialog = page.locator('.modal.ask')
  await dialog.locator('input').fill('Courtyard')
  await dialog.locator('button.primary').click()
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await page.locator('.stage-empty button', { hasText: /Add set · room/ }).click()
  await page.locator('.lib-grid button', { hasText: /Adult/ }).click()
  await page.locator('nav.rail button[title^="Shot"]').click()
  await expect(page.locator('.shot-tab .method.active b')).toHaveText('Clay reference')
  await expect(page.locator('.panel .foot .estimate')).toContainText(/Klein/, { timeout: 15_000 })      // the preview names the method's model
  type Doc = { id: string; name: string; revision: number; group_id: string | null; passes: { camera_id: string; revision: number; assets: Record<string, string>; keypoints: number[][][]; legend: Record<string, string> }[] }
  const doc = async () => (await api<{ items: Doc[] }>('GET', '/stages')).items.find((s) => s.name === 'Courtyard')!
  await page.locator('.shot-tab button', { hasText: /^Render passes$/ }).click()
  await expect.poll(async () => (await doc()).passes.length, { timeout: 30_000 }).toBe(1)
  const d = await doc()
  const entry = d.passes[0]
  expect(Object.keys(entry.assets).sort()).toEqual(['clay', 'depth', 'mask', 'normal', 'pose'])
  expect(entry.keypoints).toHaveLength(1); expect(entry.keypoints[0]).toHaveLength(18)                    // one figure, COCO-18
  expect(Object.keys(entry.legend)).toHaveLength(2)                                                        // the set and the figure
  expect(d.group_id).toBeTruthy()
  const pose = await api<AssetLite & { lineage_kind: string | null; suite: string; params: { pass: string; keypoints: unknown[] }; w: number }>('GET', `/assets/${entry.assets.pose}`)
  expect(pose.lineage_kind).toBe('stage-pass'); expect(pose.suite).toBe('stage'); expect(pose.params.pass).toBe('pose'); expect(pose.w).toBe(1280)
  const pageItems = await api<{ group: { name: string; items: { id: string }[] } }>('GET', `/groups/${d.group_id}`)
  expect(pageItems.group.name).toBe('Stage · Courtyard'); expect(pageItems.group.items.map((i) => i.id).sort()).toEqual(Object.values(entry.assets).sort())
  await expect(page.locator('.shot-tab .ref-slot.source img')).toBeVisible()                                // image 1 shows the clay pass
  await expect(page.locator('.shot-tab .pass-side .hint')).toContainText('current')
  // the shot: Generate ▶ queues the StageShot job with the passes as they are; the fake engine answers; the result carries the lineage
  await page.locator('.shot-tab .shot-prompt').fill('a sunlit courtyard, a woman in a red coat')
  const go = page.locator('.panel .foot button.primary', { hasText: /^Generate/ })
  await expect(go).toBeEnabled({ timeout: 15_000 })
  await go.click()
  await expect(page.locator('.shot-tab .shot-thumb')).toHaveCount(1, { timeout: 45_000 })
  const shots = (await api<{ items: (AssetLite & { parents: string[]; lineage_kind: string | null; origin: { suite: string; surface: string; ref: string } | null; prompt_text: string | null })[] }>('GET', '/assets?suite=stage&sort=created_desc&limit=10')).items.filter((a) => a.lineage_kind === 'stage-shot')
  expect(shots).toHaveLength(1)
  expect(shots[0].parents).toEqual([entry.assets.clay])                                                    // lineage: the clay pass (no references)
  expect(shots[0].origin).toMatchObject({ suite: 'stage', surface: 'shot', ref: d.id })
  expect(shots[0].prompt_text).toContain('grey clay blocking'); expect(shots[0].prompt_text).toContain('red coat')
  const edges = await api<{ parents: { from_id: string; kind: string }[] }>('GET', `/lineage/${shots[0].id}`)
  expect(edges.parents.map((p) => [p.from_id, p.kind])).toEqual([[entry.assets.clay, 'stage-shot']])
  await page.screenshot({ path: 'node_modules/.e2e/stage-shot.png' })
})

test('a clip (P13 / ST4, D81): the camera is keyed on the timeline, the depth sequence renders as a video asset, and the fake engine animates the shot through the IC-LoRA with lineage to both', async ({ page }) => {
  await openApp(page, { suite: 'stage' })
  await page.locator('.placeholder button', { hasText: /^New stage/ }).click()
  const dialog = page.locator('.modal.ask')
  await dialog.locator('input').fill('Dolly')
  await dialog.locator('button.primary').click()
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await page.locator('.stage-empty button', { hasText: /Adult/ }).click()
  // a shot first (the clip starts from it)
  await page.locator('nav.rail button[title^="Shot"]').click()
  const go = page.locator('.panel .foot button.primary', { hasText: /^Generate/ })
  await expect(go).toBeEnabled({ timeout: 15_000 })
  await go.click()
  await expect(page.locator('.shot-tab .shot-thumb')).toHaveCount(1, { timeout: 45_000 })
  await page.locator('.shot-tab .shot-thumb').first().click()                                               // the clip starts from this shot
  await expect(page.locator('.shot-tab .shot-thumb.start')).toHaveCount(1)
  // keys: the camera at frame 0, then a move at frame 8 (a keyed camera takes the edit as a key); the range is 0–8 (9 frames = 8n + 1)
  const tl = page.locator('.stage-timeline')
  await tl.locator('button', { hasText: /^Key camera$/ }).click()
  await tl.locator('.frame-field').fill('8'); await tl.locator('.frame-field').dispatchEvent('change')
  await page.locator('nav.rail button[title^="Cameras"]').click()
  const box = (await page.locator('canvas.stage-canvas').boundingBox())!
  await page.mouse.click(box.x + box.width - 40, box.y + box.height - 40)                                    // empty floor (the gizmo bar sits top-left): nothing selected, the Inspector shows the camera
  await expect(page.locator('.inspector .stage-insp h4')).toContainText('Camera 1')
  const z = page.locator('.inspector .stage-insp .vec input').nth(2)                                           // the camera's position z
  await z.fill('2'); await z.dispatchEvent('change')
  const rangeEnd = tl.locator('.range-field input').nth(1)
  await rangeEnd.fill('8'); await rangeEnd.dispatchEvent('change')
  type Doc = { id: string; name: string; revision: number; range: { start: number; end: number }; keyframes: { camera: Record<string, { frame: number; pos: number[] }[]> }; passes: { guides?: Record<string, { asset_id: string; frames: number; fps: number }> }[] }
  const doc = async () => (await api<{ items: Doc[] }>('GET', '/stages')).items.find((s) => s.name === 'Dolly')!
  await expect.poll(async () => { const d = await doc(); const ks = Object.values(d.keyframes.camera)[0] ?? []; return ks.map((k) => k.frame).join(',') + '|' + d.range.end }, { timeout: 10_000 }).toBe('0,8|8')
  expect((Object.values((await doc()).keyframes.camera)[0])[1].pos[2]).toBe(2)
  expect(tl.locator('.key-mark')).toHaveCount(2)
  // the sequence: nine depth frames become one video asset on the album page, recorded under the camera's passes entry
  await page.locator('nav.rail button[title^="Shot"]').click()
  await page.locator('.shot-tab button', { hasText: /^Render sequence$/ }).click()
  await expect.poll(async () => (await doc()).passes[0]?.guides?.depth?.frames ?? 0, { timeout: 60_000 }).toBe(9)
  const guide = (await doc()).passes[0].guides!.depth
  const gasset = await api<AssetLite & { kind: string; lineage_kind: string | null; frames: number | null; fps: number | null; params: { pass: string; keypoints: unknown[] } }>('GET', `/assets/${guide.asset_id}`)
  expect(gasset.kind).toBe('video'); expect(gasset.lineage_kind).toBe('stage-pass'); expect(gasset.frames).toBe(9); expect(gasset.params.pass).toBe('depth-sequence'); expect(gasset.params.keypoints).toHaveLength(9)
  await expect(page.locator('.shot-tab .guide-state')).toContainText('9 frames')
  // Animate ▶: the I2V job with the guide; the fake engine decodes nine frames; the clip carries lineage to the shot and the guide
  const animate = page.locator('.shot-tab button', { hasText: /^Animate/ })
  if (JSON.parse(process.env.LOOM2_E2E ?? '{}').variant === 'open') {                                       // D26: LTX-2.3 is full-only — the section says so
    await expect(page.locator('.shot-tab .clip-section')).toContainText('No clip model in this build')
    await expect(animate).toBeDisabled()
    return
  }
  await expect(animate).toBeEnabled()
  await animate.click()
  await expect(page.locator('.shot-tab .clip-thumb')).toHaveCount(1, { timeout: 120_000 })
  const startId = await page.locator('.shot-tab .shot-thumb.start').getAttribute('src')
  const clips = (await api<{ items: (AssetLite & { kind: string; parents: string[]; lineage_kind: string | null; frames: number | null; origin: { suite: string; surface: string } | null; params: { recipe: { guide: { kind: string } } } })[] }>('GET', '/assets?suite=stage&sort=created_desc&limit=20')).items.filter((a) => a.kind === 'video' && a.lineage_kind === 'stage-shot')
  expect(clips).toHaveLength(1)
  expect(clips[0].frames).toBe(9); expect(clips[0].origin).toMatchObject({ suite: 'stage', surface: 'clip' }); expect(clips[0].params.recipe.guide.kind).toBe('depth')
  expect(clips[0].parents).toContain(guide.asset_id); expect(clips[0].parents.length).toBe(2)
  expect(startId).toContain(clips[0].parents[0])                                                              // the start shot is the first parent
  await page.screenshot({ path: 'node_modules/.e2e/stage-clip.png' })
})

test('a 3D prop (P18, D84): "Make a 3D prop…" on a tile says its cost, the fake engine answers with a GLB, the mesh asset lands with lineage and a thumbnail, and the Stage library places it', async ({ page }) => {
  await openApp(page, { suite: 'catalogue' })
  const src = tiles(page).nth(5)
  await src.click()
  const srcId = await src.getAttribute('data-id')
  if (JSON.parse(process.env.LOOM2_E2E ?? '{}').variant === 'open') {                                       // D17 / D26: DINOv3 keeps Pixal3D full-only
    await expect(page.locator('.insp .quick-card', { hasText: 'New angle' })).toBeEnabled()
    await expect(page.locator('.insp .quick-card', { hasText: '3D prop' })).toBeDisabled()                  // the card stays, greyed: no model in this build
    const mc = await api<{ model_id: string | null; why: string | null }>('GET', '/capabilities').then((c) => (c as unknown as { mesh: { model_id: string | null; why: string | null } }).mesh)
    expect(mc.model_id).toBeNull(); expect(mc.why).toContain('DINOv3')
    return
  }
  await page.locator('.insp .quick-card', { hasText: '3D prop' }).click()
  const dialog = page.locator('.modal.ask')
  await expect(dialog).toContainText(/Pixal3D/)
  await expect(dialog).toContainText(/min/)                                                                 // the cost, before the job is queued
  await dialog.locator('button.primary').click()
  type Mesh = AssetLite & { kind: string; parents: string[]; lineage_kind: string | null; thumb_status: string; params: { licences: Record<string, string>; format: string } }
  type JobLite = { id: string; status: string; progress_text: string | null; error: string | null; log_tail: string[]; recipe: { kind: string } }
  const jobOf = async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.recipe?.kind === 'image_to_mesh')
  await expect.poll(async () => { const j = await jobOf(); return j ? `${j.status} · ${j.progress_text ?? ''} · ${j.error ?? ''} · ${j.log_tail?.slice(-2).join(' | ') ?? ''}` : 'no job' }, { timeout: 90_000 }).toMatch(/^done/)
  const meshOf = async () => (await api<{ items: Mesh[] }>('GET', '/assets?kind=mesh&sort=created_desc&limit=5')).items[0]
  await expect.poll(async () => (await meshOf())?.thumb_status, { timeout: 30_000 }).toBe('done')
  const m = await meshOf()
  expect(m.kind).toBe('mesh'); expect(m.lineage_kind).toBe('image-to-mesh'); expect(m.parents).toEqual([srcId]); expect(m.params.format).toBe('glb')
  expect(Object.keys(m.params.licences)).toContain('dinov3-l')                                              // the weights' licences in the manifest
  await expect(tiles(page).first().locator('.badge-dot[title^="3D prop"]')).toBeVisible()                   // the newest tile wears the mesh badge
  // the Stage library lists it; one click places it; the viewport loads the GLB
  await page.locator('nav.tabs button.tab', { hasText: 'Stage' }).click()
  await page.locator('.placeholder button', { hasText: /^New stage/ }).click()
  await dialog.locator('input').fill('Props')
  await dialog.locator('button.primary').click()
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await page.locator('.lib-grid .mesh-card').first().click()
  await expect(page.locator('.inspector .stage-insp h4')).toContainText('Mesh 1')
  await expect.poll(() => page.evaluate(() => (window as unknown as { __loom2Stage: { meshes: () => { loaded: string[]; failed: Record<string, string> } } }).__loom2Stage.meshes().loaded.length), { timeout: 15_000 }).toBe(1)
  await expect.poll(async () => (await api<{ params: { thumb_source?: string } }>('GET', `/assets/${m.id}`)).params.thumb_source, { timeout: 15_000 }).toBe('client')   // the viewport's fitted view became the thumbnail
  await page.screenshot({ path: 'node_modules/.e2e/stage-prop.png' })
})

test('a world (17 / SY0, D85): the Story suite\'s World tab adds a style and a logline that save with their revision; Generate\'s Style picker appends the fragment, which the job records', async ({ page }) => {
  await openApp(page, { suite: 'story' })
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Story/)
  await expect(page.locator('.world-editor')).toBeVisible()
  await page.locator('.world-editor textarea[aria-label="logline"]').fill('A courier must cross the city before dawn.')
  await page.locator('.story-panel button', { hasText: 'Add style' }).click()                                 // the panel's verb (D32)
  const row = page.locator('.world-editor .style-row').last()
  await row.locator('input[aria-label="style name"]').fill('Ink wash')
  await row.locator('input[aria-label="style fragment"]').fill('ink and wash storyboard, loose brush')
  await expect(page.locator('.inspector .story-insp h4', { hasText: 'Style' })).toContainText('Ink wash')     // the new row is selected
  type WorldLite = { revision: number; logline: string; default_style: string | null; styles: { id: string; name: string; fragment: string }[] }
  await expect.poll(async () => (await api<WorldLite>('GET', '/story/world')).styles.find((s) => s.name === 'Ink wash')?.fragment, { timeout: 10_000 }).toBe('ink and wash storyboard, loose brush')
  const w = await api<WorldLite>('GET', '/story/world')
  expect(w.logline).toBe('A courier must cross the city before dawn.')
  expect(w.revision).toBeGreaterThanOrEqual(1)
  const style = w.styles.find((s) => s.name === 'Ink wash')!
  expect(w.default_style).toBe(w.styles[0].id)                                                               // the first style made is the default
  // Generate: the picker lists it and says what it appends; the job records the style and the text that ran
  await page.locator('nav.tabs button.tab', { hasText: 'Generate' }).click()
  await page.locator('nav.rail button[title^="Model"]').click()                                               // Klein 4B: the one model the e2e tree holds in both variants
  await page.locator('.model-card').filter({ has: page.locator('span', { hasText: /^Klein 4B$/ }) }).click()
  await page.locator('nav.rail button[title^="Prompt"]').click()                                              // switches the tab (a click on the active tab would fold the panel)
  await page.locator('.segmented button', { hasText: /^Text$/ }).click()
  await page.locator('.panel select[aria-label="style"]').selectOption(style.id)
  await expect(page.locator('.panel .style-pick .hint')).toContainText('appended: ink and wash storyboard, loose brush')
  await page.locator('.panel textarea').fill('a courier on a rooftop at dawn')
  const before = (await api<Record<string, number>>('GET', '/assets/counts')).unprocessed ?? 0
  const go = page.locator('.panel .foot button.primary', { hasText: /^Generate/ })
  await expect(go).toBeEnabled()
  const count = Number((await go.textContent())!.match(/Generate (\d+)/)![1])
  await go.click()
  await expect.poll(async () => (await api<Record<string, number>>('GET', '/assets/counts')).unprocessed ?? 0, { timeout: 45_000 }).toBe(before + count)
  type Made = AssetLite & { prompt_text: string | null; params: { style_id?: string | null; style_text?: string | null } }
  const newest = (await api<{ items: Made[] }>('GET', '/assets?folder=unprocessed&sort=created_desc&limit=1')).items[0]
  expect(newest.params.style_id).toBe(style.id)
  expect(newest.params.style_text).toBe('ink and wash storyboard, loose brush')
  expect(newest.prompt_text).toContain('a courier on a rooftop at dawn. ink and wash storyboard, loose brush')
})

test('a cast (17 / SY1, D85): "Make a character…" on a tile opens Story · Cast with the image as the hero; Expand says its cost and queues one fake-engine job per cell onto the candidates page; keep fills the coverage grid; Lock makes the album refuse; @name resolves to the version', async ({ page }) => {
  test.setTimeout(150_000)                                                             // ~18 fake-engine jobs on the CI runners
  const name = `Mara ${Date.now().toString(36)}`                                       // unique: the project is reused between runs
  await openApp(page, { suite: 'catalogue' })
  const heroId = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=unprocessed&kind=image&sort=created_desc&limit=1')).items[0].id   // the newest image (a clip may sit first)
  await page.locator('.place-row', { hasText: 'Unprocessed' }).locator('button.place-open').click()
  const tile = page.locator(`.cat-grid .tile[data-id="${heroId}"]`)
  await tile.click()
  await page.locator('.insp .quick-card', { hasText: 'Character' }).click()           // the Inspector's quick card (D32: a mouse home)
  const dialog = page.locator('.modal.ask')
  await expect(dialog).toContainText(/Make a character/)
  await dialog.locator('input').fill(name)
  await dialog.locator('button.primary').click()
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Story/)
  await expect(page.locator('.cast-page h2')).toContainText(name)
  await expect(page.locator('.hero-card img')).toBeVisible()
  type Version = { id: string; state: string; group_id: string; candidates_group_id: string | null; hero_asset_id: string | null }
  type ProfileLite = { id: string; name: string; current: string; versions: Version[] }
  const profile = (await api<{ items: ProfileLite[] }>('GET', '/story/profiles')).items.find((p) => p.name === name)!
  expect(profile.versions[0].hero_asset_id).toBe(heroId)
  const gid = profile.versions[0].group_id
  expect((await api<{ group: { cover_id: string | null } }>('GET', `/groups/${gid}`)).group.cover_id).toBe(heroId)   // the hero moved onto the reference page as its cover
  // Expand ▶ on the panel foot says the cost before anything is queued (the full preset); the scenario cancels and queues the small one through the hook
  await page.locator('.panel .foot button.primary', { hasText: /^Expand/ }).click()
  await expect(dialog).toContainText(/Queue \d+ jobs/)
  await expect(dialog).toContainText(/min/)
  await dialog.locator('button', { hasText: /^Cancel$/ }).click()
  type Hook = { expand: (preset: string, seeds: number, tier: string) => Promise<{ batch_id: string; job_ids: string[]; cells: number; group_id: string } | null> }
  const r = (await page.evaluate(() => (window as unknown as { __loom2Story: Hook }).__loom2Story.expand('npc', 1, 'draft')))!
  expect(r.cells).toBeGreaterThanOrEqual(15)
  expect(r.job_ids).toHaveLength(r.cells)
  const jobs = await api<{ items: { id: string; batch_id: string | null; origin?: { suite: string; surface: string; payload?: { cell?: { shot: string } } } }[] }>('GET', '/jobs')
  const mine = jobs.items.filter((j) => r.job_ids.includes(j.id))
  expect(mine.every((j) => j.batch_id === r.batch_id && j.origin?.suite === 'story' && j.origin.surface === 'expand' && !!j.origin.payload?.cell?.shot)).toBe(true)
  type Page = { assets: Record<string, { id: string; state: string; suite: string; params: { coverage_cell?: { shot: string; angle: string } } }> }
  await expect.poll(async () => Object.keys((await api<Page>('GET', `/groups/${r.group_id}`)).assets).length, { timeout: 120_000 }).toBe(r.cells)
  const cands = Object.values((await api<Page>('GET', `/groups/${r.group_id}`)).assets)
  expect(cands.every((a) => a.suite === 'story' && !!a.params.coverage_cell?.shot)).toBe(true)
  await expect(page.locator('.cand-card')).toHaveCount(r.cells)                       // the page followed the group.changed events
  // keep one with the mouse (the card's ✓), reject one through the context menu: the grid gains a cell, the card dims
  const first = page.locator('.cand-card').first()
  const keptId = (await first.getAttribute('data-id'))!
  await first.hover()
  await first.locator('button[aria-label="keep"]').click()
  await expect(page.locator('.cand-card')).toHaveCount(r.cells - 1)
  await expect(page.locator('.cov-grid td.one, .cov-grid td.full')).toHaveCount(1)
  expect((await api<{ group: { items: { id: string }[] } }>('GET', `/groups/${gid}`)).group.items.map((i) => i.id)).toContain(keptId)
  const second = page.locator('.cand-card').first()
  await contextChoose(page, second, 'Reject')
  await expect(second).toHaveClass(/\breject\b/)
  // the bootstrap strip and the Inspector show the state; Lock through the strip → the album refuses a move on the reference page
  await expect(page.locator('.story-strip .bootstrap .bs-step.done')).toHaveCount(2)  // Cast ✓ · Expand ✓
  await page.locator('.story-strip button[title^="Lock the version"]').click()
  await expect(dialog).toContainText(/Lock/)
  await dialog.locator('button.primary').click()
  await expect(page.locator('.story-strip .lock-badge')).toBeVisible()
  await expect.poll(async () => (await api<{ items: ProfileLite[] }>('GET', '/story/profiles')).items.find((p) => p.id === profile.id)?.versions[0].state).toBe('final')
  await expect(api('POST', '/groups/move', { items: [{ kind: 'asset', id: keptId }], to: null })).rejects.toThrow(/423/)
  await expect(page.locator('.panel .foot .estimate')).toContainText(/locked/)
  // the mention: Generate's @ picker lists the profile first; the preview resolves it to v1's reference set with the hero first
  await page.locator('nav.tabs button.tab', { hasText: 'Generate' }).click()
  await page.locator('nav.rail button[title^="Model"]').click()
  await page.locator('nav.rail button[title^="Prompt"]').click()
  await page.locator('.segmented button', { hasText: /^Text$/ }).click()
  await page.locator('.panel textarea').fill('at the gate')
  await page.locator('.text-prompt button[aria-label^="Mention a group"]').click()
  await page.locator('.ctx-menu button.item').filter({ hasText: `${name} · character` }).click()   // the profile's entry (its groups are named after it too)
  await expect(page.locator('.panel .mention-chips .mchip.profile')).toContainText(`@${name}`)
  await expect(page.locator('.panel textarea')).toHaveValue(new RegExp(`@${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`))
  type Preview = { mentions: { profile_id: string | null; version: string | null; group_id: string; asset_ids: string[] }[]; ref_list: { asset_id: string | null; note: string | null }[] }
  await expect.poll(async () => {
    const caps = await api<{ models: Record<string, { label: string }> }>('GET', '/capabilities')
    const klein4b = Object.entries(caps.models).find(([, m]) => m.label === 'Klein 4B')![0]
    const pv = await api<Preview>('POST', '/recipes/preview', { recipe: { kind: 't2i', model_id: klein4b, prompt_mode: 'text', prompt_text: `@${name} at the gate`, mentions: [{ profile_id: profile.id, name }] } })
    return `${pv.mentions[0]?.profile_id}/${pv.mentions[0]?.version}/${pv.mentions[0]?.group_id}/${pv.ref_list[0]?.asset_id}`
  }).toBe(`${profile.id}/v1/${gid}/${heroId}`)
})

test('a shot (17 / SY2, D85): "New shot from this camera" in Stage makes a Story shot whose frame arrives from the camera\'s generate; "Make a shot from this clip" in Animate makes another; Finalize is refused at draft size with the reason and accepted at the format', async ({ page }) => {
  test.setTimeout(150_000)
  const name = `Gate ${Date.now().toString(36)}`
  await openApp(page, { suite: 'stage' })
  await page.locator('.placeholder button', { hasText: /^New stage/ }).click()
  const dialog = page.locator('.modal.ask')
  await dialog.locator('input').fill(`Gatehouse ${name.slice(-5)}`)
  await dialog.locator('button.primary').click()
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await page.locator('.stage-empty button', { hasText: /Add set · room/ }).click()
  await page.locator('.lib-grid button', { hasText: /Adult/ }).click()
  await page.locator('nav.rail button[title^="Cameras"]').click()
  await page.locator('.stage-panel button[aria-label^="New shot from this camera"]').click()           // the Cameras tab's verb (D32)
  await expect(dialog).toContainText(/New shot from this camera/)
  await dialog.locator('input').fill(name)
  await dialog.locator('button.primary').click()
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Story/)
  await expect(page.locator('.story-strip b')).toHaveText(name)
  type Version = { id: string; state: string; stage_id: string | null; camera_id: string | null; frame_asset_id: string | null; clip_id: string | null; takes: { kind: string; id: string }[] }
  type Shot = { id: string; name: string; current: string; owner_node: string | null; versions: Version[] }
  const shot = (await api<{ items: Shot[] }>('GET', '/story/shots')).items.find((s) => s.name === name)!
  expect(shot.versions[0].stage_id).toBeTruthy()
  expect(shot.versions[0].camera_id).toBeTruthy()
  await expect(page.locator('.panel .foot .estimate')).toContainText(/no clip yet/)
  // back in Stage: the Shot tab renders the passes and generates (the fake engine answers) → the result lands on the shot as its frame
  await page.locator('nav.tabs button.tab', { hasText: 'Stage' }).click()
  await page.locator('nav.rail button[title^="Shot"]').click()
  await page.locator('.shot-tab button', { hasText: /^Render passes$/ }).click()
  await page.locator('.shot-tab .shot-prompt').fill('a gatehouse at dawn')
  const go = page.locator('.panel .foot button.primary', { hasText: /^Generate/ })
  await expect(go).toBeEnabled({ timeout: 30_000 })
  await go.click()
  const shotOf = async () => (await api<Shot>('GET', `/story/shots/${shot.id}`))
  await expect.poll(async () => (await shotOf()).versions[0].frame_asset_id, { timeout: 60_000 }).toBeTruthy()
  expect((await shotOf()).versions[0].takes.map((t) => t.kind)).toEqual(['image'])
  // the board shows the frame (Story · Shots was left on the Shots tab, so the rail is not clicked — that would fold the panel)
  await page.locator('nav.tabs button.tab', { hasText: 'Story' }).click()
  await expect(page.locator('.shot-board .shot-player img')).toBeVisible()
  await expect(page.locator('.shot-board .take-card.current')).toHaveCount(1)
  // Animate: a draft clip (the fake engine, nine frames) opened in the player → a second shot; its draft size is refused by the gate, with the reason
  const caps = await api<{ defaults: { i2v: string } }>('GET', '/capabilities')
  const start = (await shotOf()).versions[0].frame_asset_id!
  type JobLite = { id: string; status: string; error: string | null; result: { clip_id?: string } }
  const submit = async (w: number, h: number) => {
    const job = (await api<{ jobs: { id: string }[] }>('POST', '/jobs', { recipe: { kind: 'i2v', model_id: caps.defaults.i2v, start_asset: start, width: w, height: h, frames: 9, fps: 16, prompt_text: `${w}×${h}` }, stage: false, origin: { suite: 'animate', surface: 'clip' } })).jobs[0]
    await expect.poll(async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.id === job.id)?.status, { timeout: 60_000 }).toBe('done')
    return (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.id === job.id)!.result.clip_id!
  }
  const draftClip = await submit(1024, 576)
  await page.locator('nav.tabs button.tab', { hasText: 'Animate' }).click()
  type AnimateHook = { getState: () => { loadClips: () => Promise<void>; select: (id: string) => void } }
  await page.evaluate(async (id) => { const an = (window as unknown as { __loom2Animate: AnimateHook }).__loom2Animate.getState(); await an.loadClips(); an.select(id) }, draftClip)
  await page.locator('.transport button[aria-label^="Make a shot from this clip"]').click()
  await expect(dialog).toContainText(/Make a shot from this clip/)
  const name2 = `${name} clip`
  await dialog.locator('input').fill(name2)
  await dialog.locator('button.primary').click()
  await expect(page.locator('.story-strip b')).toHaveText(name2)
  const shot2 = (await api<{ items: Shot[] }>('GET', '/story/shots')).items.find((s) => s.name === name2)!
  const clipId = shot2.versions[0].clip_id!
  expect(clipId).toBe(draftClip)
  const clip = await api<{ id: string; w: number; h: number; frames: number }>('GET', `/clips/${clipId}`)
  const fmt = (await api<{ format: { width: number; height: number } }>('GET', '/project')).format
  await expect(page.locator('.shot-board .shot-player video')).toBeVisible()
  await expect(page.locator('.panel .foot .estimate')).toContainText(`Draft ${clip.w}×${clip.h} — the format is ${fmt.width}×${fmt.height}`)
  await expect(page.locator('.story-strip button[aria-label^="Finalize"]')).toBeDisabled()
  await expect(api('POST', `/story/shots/${shot2.id}/versions/v1/finalize`)).rejects.toThrow(/422/)
  // a clip at the format (the fake engine, nine frames) used as the clip → Finalize through the strip → final
  const fullClip = await submit(fmt.width, fmt.height)
  type Hook = { useTake: (kind: 'image' | 'clip', id: string) => Promise<void> }
  await page.evaluate((id) => (window as unknown as { __loom2Story: Hook }).__loom2Story.useTake('clip', id), fullClip)
  await expect(page.locator('.shot-board .take-card')).toHaveCount(2)
  await expect(page.locator('.panel .foot .estimate')).toContainText(/ready to finalize/)
  await page.locator('.story-strip button[aria-label^="Finalize"]').click()
  await expect(dialog).toContainText(/Finalize/)
  await dialog.locator('button.primary').click()
  await expect(page.locator('.story-strip .lock-badge')).toContainText('final')
  await expect.poll(async () => (await api<Shot>('GET', `/story/shots/${shot2.id}`)).versions[0].state).toBe('final')
  expect((await api<Shot>('GET', `/story/shots/${shot2.id}`)).versions[0].clip_id).toBe(fullClip)
  await expect(api('POST', `/story/shots/${shot2.id}/versions/v1/take`, { kind: 'clip', id: clipId })).rejects.toThrow(/422/)   // final: fixed
  // a new version is a retake: open, the pointers copied
  await page.locator('.story-strip button[aria-label^="New version"]').click()
  await dialog.locator('button.primary').click()
  await expect(page.locator('.story-strip select[aria-label="shot version"]')).toHaveValue('v2')
  await expect.poll(async () => (await api<Shot>('GET', `/story/shots/${shot2.id}`)).versions.length).toBe(2)
  await expect(page.locator('.panel .foot .estimate')).toContainText(/ready to finalize/)
  // the stage moves (a focal change through the API) → the version is marked stale on the strip (advisory, loom R62)
  const stg = (await api<{ items: { id: string; revision: number; cameras: { id: string; focal_mm: number }[] }[] }>('GET', '/stages')).items.find((x) => x.id === shot.versions[0].stage_id)!
  await api('PUT', `/stages/${stg.id}`, { ...stg, cameras: [{ ...stg.cameras[0], focal_mm: 50 }] })
  type Hook2 = { openShots: (id: string | null) => void; loadShots: () => Promise<void> }
  await page.evaluate(async (id) => { const h = (window as unknown as { __loom2Story: Hook2 }).__loom2Story; await h.loadShots(); h.openShots(id) }, shot.id)
  await expect(page.locator('.story-strip b')).toHaveText(name)
  await expect(page.locator('.story-strip .stale-badge')).toBeVisible()
})

test('a flow (17 / SY3, D85): the Strip adds Start, Dialogue and Choice nodes, handle drags connect them, the Inspector edits the line and the options and spawns a shot, Validate lists the advisory problem, and Play walks both branches without queuing a job', async ({ page }) => {
  test.setTimeout(120_000)
  await openApp(page, { suite: 'story', tab: 'flow' })
  await expect(page.locator('[data-testid="flow-canvas"]')).toBeVisible()
  type FlowLite = { graph: { edges: { from: string; port: string; to: string }[]; start: string | null }; nodes: { id: string; type: string; shot_id: string | null }[] }
  for (const n of (await api<FlowLite>('GET', '/story/flow')).nodes) await api('DELETE', `/story/flow/nodes/${n.id}`)   // a clean slate (the project is reused between runs)
  type Hook = { loadFlow: () => Promise<void> }
  await page.evaluate(() => (window as unknown as { __loom2Story: Hook }).__loom2Story.loadFlow())
  await expect(page.locator('.flow-node')).toHaveCount(0)
  const jobsBefore = (await api<{ items: unknown[] }>('GET', '/jobs')).items.length
  // the palette on the Strip (D32): three nodes, laid out in a row
  await page.locator('.story-strip button[aria-label="Add Start"]').click()
  await expect(page.locator('.flow-node.t-start')).toHaveCount(1)
  await page.locator('.story-strip button[aria-label="Add Dialogue"]').click()
  await page.locator('.story-strip button[aria-label="Add Choice"]').click()
  await expect(page.locator('.flow-node')).toHaveCount(3)
  const start = page.locator('.flow-node.t-start'), dlg = page.locator('.flow-node.t-dialogue'), choice = page.locator('.flow-node.t-choice')
  // the nodes landed stepped at the view's centre: drag them apart with the mouse (saved on drop), then Fit
  const move = async (node: ReturnType<typeof page.locator>, dx: number, dy: number) => { const a = await centre(node.locator('.head')); await page.mouse.move(a.x, a.y); await page.mouse.down(); await page.mouse.move(a.x + 10, a.y + 6, { steps: 3 }); await page.mouse.move(a.x + dx, a.y + dy, { steps: 12 }); await page.mouse.up() }
  await move(start, -260, -120)
  await move(choice, 260, 120)
  await page.locator('.story-strip button[aria-label="Fit the graph"]').click()
  await expect.poll(async () => { const g = (await api<FlowLite & { graph: { nodes: { id: string; x: number }[] } }>('GET', '/story/flow')).graph; return new Set(g.nodes.map((n) => Math.round(n.x / 50))).size }).toBe(3)   // three distinct columns, saved
  // the Inspector: the Dialogue's title and line, the Choice's two options (each an out-port)
  await dlg.locator('.head').click()
  await page.locator('.inspector input[aria-label="node title"]').fill('Hello')
  await page.locator('.inspector button', { hasText: '+ line' }).click()
  await page.locator('.inspector input[aria-label="line 1"]').fill('Hi there.')
  await expect(dlg.locator('.line')).toContainText('Hi there.')
  await choice.locator('.head').click()
  await page.locator('.inspector button', { hasText: '+ option' }).click()
  await page.locator('.inspector input[aria-label="option 1"]').fill('Go')
  await page.locator('.inspector button', { hasText: '+ option' }).click()
  await page.locator('.inspector input[aria-label="option 2"]').fill('Stay')
  await expect(choice.locator('.react-flow__handle.source')).toHaveCount(2)
  // connect by dragging handles: Start → Hello → Pick, Go → Hello (a loop); Stay leads nowhere (the end)
  const drag = async (from: ReturnType<typeof page.locator>, to: ReturnType<typeof page.locator>) => {
    const a = await centre(from), b = await centre(to)
    await page.mouse.move(a.x, a.y); await page.mouse.down(); await page.mouse.move(a.x + 24, a.y + 4, { steps: 4 }); await page.mouse.move(b.x, b.y, { steps: 16 }); await page.mouse.up()
  }
  await drag(start.locator('.react-flow__handle.source'), dlg.locator('.react-flow__handle.target'))
  await drag(dlg.locator('.react-flow__handle.source'), choice.locator('.react-flow__handle.target'))
  await drag(choice.locator('.react-flow__handle.source').first(), dlg.locator('.react-flow__handle.target'))
  await expect.poll(async () => (await api<FlowLite>('GET', '/story/flow')).graph.edges.length, { timeout: 10_000 }).toBe(3)
  const f = await api<FlowLite>('GET', '/story/flow')
  expect(f.graph.start).toBe(f.nodes.find((n) => n.type === 'start')!.id)
  expect(f.graph.edges.map((e) => (e.port.startsWith('opt:') ? 'opt' : e.port)).sort()).toEqual(['opt', 'out', 'out'])
  // the Dialogue gets its own shot (loom R146); Validate: the shot is not final yet — one advisory problem
  await dlg.locator('.head').click()
  await page.locator('.inspector button[aria-label^="New shot for this node"]').click()
  const dialog = page.locator('.modal.ask')
  await expect(dialog).toContainText(/New shot for this node/)
  await dialog.locator('button.primary').click()
  await expect(page.locator('.inspector .node-insp')).toContainText('Hello · v1 · open')
  await expect.poll(async () => (await api<{ items: { name: string; owner_node: string | null }[] }>('GET', '/story/shots')).items.find((s) => s.name === 'Hello')?.owner_node).toBeTruthy()
  await page.locator('.story-strip button[aria-label="Validate"]').click()
  await expect(page.locator('.story-strip .hint')).toContainText(/1 problem/)
  expect((await api<{ problems: { code: string }[] }>('POST', '/story/flow/validate')).problems.map((p) => p.code)).toEqual(['shot_open'])
  // play: the line shows, Next → the two options, Go loops to Hello, Stay ends; no job was queued (loom R143)
  await page.locator('.panel .foot button.primary', { hasText: /^Play/ }).click()
  const play = page.locator('[data-testid="play-view"]')
  await expect(play.locator('.play-lines')).toContainText('Hi there.')
  await play.locator('button.next').click()
  await expect(play.locator('button.option')).toHaveCount(2)
  await play.locator('button.option', { hasText: 'Go' }).click()
  await expect(play.locator('.play-lines')).toContainText('Hi there.')
  await play.locator('button.next').click()
  await play.locator('button.option', { hasText: 'Stay' }).click()
  await expect(play.locator('.play-card')).toContainText('The end')
  expect((await api<{ items: unknown[] }>('GET', '/jobs')).items.length).toBe(jobsBefore)
  await page.locator('.panel .foot button.primary', { hasText: /^Stop/ }).click()
  await expect(page.locator('[data-testid="flow-canvas"]')).toBeVisible()
  // the files are the truth: after a reload the nodes, the edges and the bound shot come back
  await page.reload()
  await expect(page.locator('.flow-node')).toHaveCount(3)
  await expect(page.locator('.flow-node.t-dialogue .shot img, .flow-node.t-dialogue .shot span')).toHaveCount(1)
  expect((await api<FlowLite>('GET', '/story/flow')).nodes.find((n) => n.type === 'dialogue')!.shot_id).toBeTruthy()
})
