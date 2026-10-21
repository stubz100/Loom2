// End-to-end smoke (D68, ArtCraft P6 §3): each scenario drives the real UI with the mouse in headless Edge against the e2e build, a real
// orchestrator and the fake engine, and checks the outcome on the page and through the API. Scenarios are independent: each opens a
// fresh page and picks its own assets; they share one project (global-setup.ts), so none relies on another's leftovers.
import { api, centre, contextChoose, env, expect, openApp, openCatalogue, test, thumbsLoaded, tiles } from './fixtures'

interface AssetLite { id: string; state: string; job_id: string | null }
interface Group { id: string; name: string; items: { kind: string; id: string }[] }

test('open the project: the Catalogue grid shows tiles and their thumbnails load', async ({ page }) => {
  expect((await api<{ variant: string }>('GET', '/health')).variant).toBe(env().variant)          // LOOM2_VARIANT reached the orchestrator
  await openApp(page, { suite: 'catalogue' })
  await expect(tiles(page).first()).toBeVisible()
  expect(await thumbsLoaded(page, 12)).toBeGreaterThanOrEqual(Math.min(12, env().assets))
  await expect(page.locator('.place-row', { hasText: 'Library' }).locator('.n')).toHaveText(/^\d+$/)
  // the Project menu leads the suite tabs: the open project's name, New / Open / Close and the recents
  const projectTab = page.locator('nav.tabs button.project-tab')
  await expect(page.locator('nav.tabs > button').first()).toHaveClass(/project-tab/)
  await expect(projectTab.locator('.project-name')).not.toHaveText('none open')
  await projectTab.click()
  await expect(page.locator('.menu.project-menu button', { hasText: 'New project' })).toBeVisible()
  await expect(page.locator('.menu.project-menu button', { hasText: /^Close / })).toBeVisible()
  await page.screenshot({ path: 'node_modules/.e2e/project-menu.png', clip: { x: 0, y: 0, width: 1100, height: 260 } })
  await projectTab.click()
  await expect(page.locator('.menu.project-menu')).toHaveCount(0)
  // D90 (02 §3): Story leads the tabs and holds the Catalogue (active under it); Models & engine is a sheet in ☰
  await expect(page.locator('nav.tabs button.tab:not(.project-tab)')).toHaveText([/^Story/, /^Image/, /^Animate/])
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Story/)
  await expect(page.locator('nav.rail button[aria-label="Catalogue"]')).toHaveClass(/active/)
  await page.locator('button[aria-label="app menu"]').click()
  await page.locator('.menu button', { hasText: 'Models & engine' }).click()
  await expect(page.locator('.modal.models-sheet table.grid tbody tr').first()).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.locator('.modal.models-sheet')).toHaveCount(0)
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
  await openCatalogue(page)
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
  await contextChoose(page, a, 'Animate from this frame')
  const slots = page.locator('.slots .slot')
  await expect(slots.nth(0).locator('img')).toBeVisible()
  await openCatalogue(page)
  await contextChoose(page, page.locator(`.cat-grid .tile[data-id="${idB}"]`), 'Use as the end frame')
  await expect(slots.nth(1).locator('img')).toBeVisible()
  for (const [k, id] of [[0, idA], [1, idB]] as const) {
    await expect.poll(() => slots.nth(k).locator('img').evaluate((i: HTMLImageElement) => i.complete && i.naturalWidth > 0)).toBe(true)
    expect(await slots.nth(k).locator('img').getAttribute('src')).toContain(`/thumbs/${id}/`)
  }
})

test('send-to by drag (D71): a tile held on the Image tab opens it (Make), the ghost says what a drop adds, a slot takes it, a repeat is refused', async ({ page }) => {
  await openApp(page, { suite: 'catalogue' })
  const tile = tiles(page).nth(3)
  const id = (await tile.getAttribute('data-id'))!
  const tab = page.locator('nav.tabs button.tab', { hasText: 'Image' })
  const hint = page.locator('.drag-ghost .drop-hint')
  const from = await centre(tile), onTab = await centre(tab)
  await page.mouse.move(from.x, from.y)
  await page.mouse.down()
  await page.mouse.move(from.x + 12, from.y + 8, { steps: 3 })
  await page.mouse.move(onTab.x, onTab.y, { steps: 10 })
  await expect(hint).toHaveText(/^✓ Add as reference 1 of \d+ — or hold to open Image$/)
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
  await openCatalogue(page)
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

/** D95 (IM1): Image's modes — the Image tab, then the panel head's Make | Edit switch. */
async function openImage(page: import('@playwright/test').Page, mode: 'Make' | 'Edit'): Promise<void> {
  await page.locator('nav.tabs button.tab', { hasText: 'Image' }).click()
  await page.locator('.panel .head .image-mode .segmented button', { hasText: mode }).click()
  await expect(page.locator('.panel .head .image-mode .segmented button.active')).toHaveText(mode)
}

/** D95 (AN1): Animate's viewer levels — the Animate tab, then the strip's Clay | Performance switch. */
async function openAnimate(page: import('@playwright/test').Page, level: 'Clay' | 'Performance'): Promise<void> {
  await page.locator('nav.tabs button.tab', { hasText: 'Animate' }).click()
  await page.locator('.animate-levels button', { hasText: level }).click()
  await expect(page.locator('.animate-levels button.active')).toHaveText(level)
}

/** D95 (AN1): go to a section of Animate's one column — the rail button unless it is already the active one (clicking the active rail
 *  button folds the panel, D90), then the section into view. */
async function openSection(page: import('@playwright/test').Page, title: string): Promise<void> {
  const btn = page.locator(`nav.rail button[title^="${title}"]`)
  if (await page.locator('.panel.closed').count()) await btn.click()                                          // a folded panel: the button opens it at the section
  await expect(page.locator('.panel.closed')).toHaveCount(0)
  await page.locator(`#anim-sec-${title.toLowerCase()}`).evaluate((el) => el.scrollIntoView({ block: 'start' }))   // what the rail does, without its fold toggle
  await expect(btn).toHaveClass(/active/)                                                                      // the rail follows the scroll (useColumnSync)
}

/** D95 (AN1): the stage's render form — Animate's Performance section, its From the stage card (Stage's old Render tab). */
async function stageRoute(page: import('@playwright/test').Page): Promise<void> {
  await openSection(page, 'Performance')
  await page.locator('.col-sec-head .segmented button', { hasText: 'From the stage' }).click()
  await expect(page.locator('.shot-tab')).toBeVisible()
}

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

  await openImage(page, 'Edit')                                                          // D95: the Image tab springs open on its last mode
  await openCatalogue(page)
  await carryAndHold(page, await centre(tiles(page).nth(6)), 'Image', '.edit-empty')
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
  await expect(page.locator('.ctx-menu button.item', { hasText: 'Use as the end frame' })).toBeVisible()
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

test('quick actions (D71): "Select subject" in the Inspector reaches Edit with AI Select · Subject in one click; the deep link does too', async ({ page }) => {
  await openApp(page, { suite: 'catalogue' })
  await tiles(page).nth(8).click()
  const card = page.locator('.insp .quick-card', { hasText: 'Select subject' })
  await expect(card).toBeEnabled()
  await card.click()
  await expect.poll(() => editorTool(page), { timeout: 30_000 }).toEqual({ doc: true, tool: 'ai', op: 'select', sel: 'subject' })
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Image/)
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
  // D93 (A3): then each group's images together — hero 1–2, tavern 3–4
  await expect(page.locator('.preview-box')).toContainText(`${heroName} walks into ${tavernName}. Image 1 shows ${heroName}. Image 2 shows ${heroName}. Image 3 shows ${tavernName}.`)
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
  await openImage(page, 'Edit')
  await expect(page.locator('.stage .render-error')).toContainText("Edit's code could not be loaded")
  await expect(page.locator('.render-error')).toHaveCount(1)                          // one explanation, in the middle; the panel says one line
  await expect(page.locator('.render-error-line')).toContainText('Edit is not available')
  await expect(page.locator('.frame')).toBeVisible()                                  // the rest of the app stays
  await openCatalogue(page)
  await expect(tiles(page).first()).toBeVisible()
  await page.unroute(/EditSuite-[\w-]+\.js$/)
  await openImage(page, 'Edit')
  await page.locator('.stage .render-error').getByRole('button', { name: 'Reload the app' }).click()   // the browser keeps a failed module: reload
  await expect(page.locator('.frame')).toBeVisible()
  await openImage(page, 'Edit')
  await expect(page.locator('.edit-empty')).toBeVisible({ timeout: 90_000 })         // the code loads this time (the CI runner takes long over the reload + WebGL boot; 45 s failed once on the open runner, 2026-10-13)
})

test('a new angle (P14, D82; a sheet since D90): "New angle" on a tile opens the sheet with the source, the pad picks the move, the job lands with reangle lineage', async ({ page }) => {
  const before = (await api<Record<string, number>>('GET', '/assets/counts')).unprocessed ?? 0
  await openApp(page, { suite: 'catalogue' })
  const srcId = await tiles(page).nth(8).getAttribute('data-id')                                     // pinned by id: a late asset can reorder the grid between two reads
  await page.locator(`.tile[data-id="${srcId}"]`).click()
  await page.locator('.insp .quick-card', { hasText: 'New angle' }).click()
  const sheet = page.locator('.modal.angle-sheet')                                                    // D90: a sheet over the Catalogue, no suite switch
  await expect(sheet).toBeVisible()
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Story/)
  await expect(sheet.locator('.angle-tab .ref-slot.source img')).toBeVisible()
  await sheet.locator('.angle-pad button[aria-label="Wide"]').click()                             // D90: the moves are icons
  const go = sheet.locator('.foot button.primary', { hasText: /^New angle/ })
  await expect(go).toBeEnabled({ timeout: 15_000 })
  await expect(sheet.locator('.foot .estimate')).toContainText(/Klein/)                        // auto: a framing move runs Klein (D77)
  await go.click()
  await expect(sheet).toHaveCount(0)                                                                  // queueing closes the sheet
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

test('a sequence (P17, D83 — in Story · Episode since 17 SY4): a fake-engine clip goes on a new lane from the bin, the document saves with its revision, the EDL is written', async ({ page }) => {
  await openApp(page, { suite: 'catalogue' })
  await contextChoose(page, tiles(page).nth(6), 'Animate from this frame')
  const go = page.locator('.panel .foot button.primary', { hasText: /^Animate/ })
  await expect(go).toBeEnabled({ timeout: 20_000 })
  await go.click()
  await page.locator('nav.tabs button.tab', { hasText: 'Story' }).click()                 // 17 SY4 (D85): the lane lives in Story · Episode now
  await page.locator('nav.rail button[title^="Episode"]').click()
  await expect(page.locator('.seq-bin:not(.shots-bin) .seq-clip-card')).toHaveCount(1, { timeout: 120_000 })    // the clip lands when its proxy is ready (clip.ready)
  await page.locator('.seq-list-head button[title^="New cut"]').click()
  const dialog = page.locator('.modal.ask')
  await dialog.locator('input').fill('Reel one')
  await dialog.locator('button.primary').click()
  await expect(page.locator('.seq-row.active')).toContainText('Reel one')
  await page.locator('.seq-bin:not(.shots-bin) .seq-clip-card button').first().click()    // + : add the clip to the end of the lane
  await expect(page.locator('.seq-clip')).toHaveCount(1)
  await expect(page.locator('.seq-canvas')).toBeVisible()
  const thumb = page.locator('.seq-clip .seq-thumbs img').first()                          // C24 frame thumbnails across the block
  await expect(thumb).toBeAttached()
  await expect.poll(() => thumb.evaluate((i: HTMLImageElement) => i.complete && i.naturalWidth > 0), { timeout: 15_000 }).toBe(true)
  await expect.poll(async () => (await api<{ items: { name: string; revision: number; clips: unknown[] }[] }>('GET', '/timelines')).items.find((t) => t.name === 'Reel one')?.revision ?? 0, { timeout: 10_000 }).toBeGreaterThanOrEqual(1)
  const tl = (await api<{ items: { id: string; name: string; clips: { out: number }[] }[] }>('GET', '/timelines')).items.find((t) => t.name === 'Reel one')!
  expect(tl.clips).toHaveLength(1)
  await page.locator('.seq-insp button', { hasText: /^EDL$/ }).click()
  await page.locator('.modal.ask button.primary', { hasText: /^Export anyway$/ }).click()  // the checklist: a plain clip is not a final shot (advisory)
  await expect(page.locator('.seq-insp .hint', { hasText: 'last:' })).toContainText('.edl')
  const exported = await api<{ format: string; text: string; path: string }>('POST', `/timelines/${tl.id}/export`, { format: 'edl' })
  expect(exported.text).toContain('TITLE: Reel one')
  expect(exported.text).toContain('V     C')
  // the draft render: a CPU job that becomes a second clip in the bin, with lineage to the first
  await page.locator('.seq-insp button', { hasText: /^Render draft$/ }).click()
  await expect(page.locator('.seq-bin:not(.shots-bin) .seq-clip-card')).toHaveCount(2, { timeout: 120_000 })
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
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Animate/)
  await page.locator('.placeholder button', { hasText: /^New stage/ }).click()
  const dialog = page.locator('.modal.ask')
  await dialog.locator('input').fill('Alley at night')
  await dialog.locator('button.primary').click()
  await expect(page.locator('.stage-row.active')).toContainText('Alley at night')
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await page.locator('.stage-empty button', { hasText: /^Add set · room$/ }).click()
  await page.locator('.lib-grid button', { hasText: /^Adult/ }).click()                        // the Library's figure card
  await openSection(page, 'Scene')
  await expect(page.locator('.outl-row .kind')).toHaveCount(2)
  await expect(page.locator('.outl-row.active', { has: page.locator('.kind') }).locator('.name')).toHaveText('Figure 1')   // the last added is selected (the camera row is "active" in its own sense)
  await expect(page.locator('.panel .stage-insp h4')).toContainText('Figure 1')
  await expect.poll(async () => (await api<{ items: { name: string; revision: number; objects: { kind: string }[] }[] }>('GET', '/stages')).items.find((s) => s.name === 'Alley at night')?.objects.length ?? 0, { timeout: 10_000 }).toBe(2)
  const before = (await api<{ items: { id: string; name: string; revision: number }[] }>('GET', '/stages')).items.find((s) => s.name === 'Alley at night')!
  expect(before.revision).toBeGreaterThanOrEqual(1)
  // camera view shows the framing rectangle; the free view does not
  await openSection(page, 'Camera')
  await page.locator('.stage-panel button', { hasText: /^Look through$/ }).click()
  await expect(page.locator('.frame-guides')).toBeVisible()
  await expect(page.locator('.view-tag')).toContainText('35 mm')
  await page.screenshot({ path: 'node_modules/.e2e/stage-camera-view.png' })                     // a look for the journal: the framing rectangle over the set
  await page.reload()
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Animate/)
  await page.locator('.stage-row', { hasText: 'Alley at night' }).click()
  await openSection(page, 'Scene')
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
  await openSection(page, 'Motion')
  await expect(page.locator('#anim-sec-motion .stage-panel:not(.motion-lib) .head b')).toHaveText('Figure 1')
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
  await stageRoute(page)
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
  const go = page.locator('.panel .foot button.primary', { hasText: /^Render frame/ })
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
  await stageRoute(page)
  const go = page.locator('.panel .foot button.primary', { hasText: /^Render frame/ })
  await expect(go).toBeEnabled({ timeout: 15_000 })
  await go.click()
  await expect(page.locator('.shot-tab .shot-thumb')).toHaveCount(1, { timeout: 45_000 })
  await page.locator('.shot-tab .shot-thumb').first().click()                                               // the clip starts from this shot
  await expect(page.locator('.shot-tab .shot-thumb.start')).toHaveCount(1)
  // keys: the camera at frame 0, then a move at frame 8 (a keyed camera takes the edit as a key); the range is 0–8 (9 frames = 8n + 1)
  const tl = page.locator('.stage-timeline')
  await tl.locator('button', { hasText: /^Key camera$/ }).click()
  await tl.locator('.frame-field').fill('8'); await tl.locator('.frame-field').dispatchEvent('change')
  await openSection(page, 'Camera')
  const box = (await page.locator('canvas.stage-canvas').boundingBox())!
  await page.mouse.click(box.x + 60, box.y + box.height - 40)                                                // empty floor, bottom-left (the gizmo bar sits top-left; toasts bottom-right, over the viewport since AN1): nothing selected, Selection shows the camera
  await expect(page.locator('.panel .stage-insp h4', { hasText: 'Camera 1' })).toBeVisible()            // D95 (AN1): Selection shows the stage, then its active camera
  const z = page.locator('.panel .stage-insp .vec input').nth(2)                                           // the camera's position z
  await z.fill('2'); await z.dispatchEvent('change')
  const rangeEnd = tl.locator('.range-field input').nth(1)
  await rangeEnd.fill('8'); await rangeEnd.dispatchEvent('change')
  type Doc = { id: string; name: string; revision: number; range: { start: number; end: number }; keyframes: { camera: Record<string, { frame: number; pos: number[] }[]> }; passes: { guides?: Record<string, { asset_id: string; frames: number; fps: number }> }[] }
  const doc = async () => (await api<{ items: Doc[] }>('GET', '/stages')).items.find((s) => s.name === 'Dolly')!
  await expect.poll(async () => { const d = await doc(); const ks = Object.values(d.keyframes.camera)[0] ?? []; return ks.map((k) => k.frame).join(',') + '|' + d.range.end }, { timeout: 10_000 }).toBe('0,8|8')
  expect((Object.values((await doc()).keyframes.camera)[0])[1].pos[2]).toBe(2)
  expect(tl.locator('.key-mark')).toHaveCount(2)
  // the sequence: nine depth frames become one video asset on the album page, recorded under the camera's passes entry
  await stageRoute(page)
  await page.locator('.shot-tab button', { hasText: /^Render sequence$/ }).click()
  await expect.poll(async () => (await doc()).passes[0]?.guides?.depth?.frames ?? 0, { timeout: 60_000 }).toBe(9)
  const guide = (await doc()).passes[0].guides!.depth
  const gasset = await api<AssetLite & { kind: string; lineage_kind: string | null; frames: number | null; fps: number | null; params: { pass: string; keypoints: unknown[] } }>('GET', `/assets/${guide.asset_id}`)
  expect(gasset.kind).toBe('video'); expect(gasset.lineage_kind).toBe('stage-pass'); expect(gasset.frames).toBe(9); expect(gasset.params.pass).toBe('depth-sequence'); expect(gasset.params.keypoints).toHaveLength(9)
  await expect(page.locator('.shot-tab .guide-state')).toContainText('9 frames')
  // Animate ▶: the I2V job with the guide; the fake engine decodes nine frames; the clip carries lineage to the shot and the guide
  const animate = page.locator('.shot-tab button', { hasText: /^Render clip/ })
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

test("a pose-driven shot (19 / CN4, D87): the Render tab's Animate method takes the pose sequence on Wan's grid, and the fake engine performs it with the picked result as the character — lineage to both, in both variants", async ({ page }) => {
  await openApp(page, { suite: 'stage' })
  await page.locator('.placeholder button', { hasText: /^New stage/ }).click()
  const dialog = page.locator('.modal.ask')
  const name = `Perform ${Date.now().toString(36)}`
  await dialog.locator('input').fill(name)
  await dialog.locator('button.primary').click()
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await page.locator('.stage-empty button', { hasText: /Adult/ }).click()
  await stageRoute(page)
  const go = page.locator('.panel .foot button.primary', { hasText: /^Render frame/ })
  await expect(go).toBeEnabled({ timeout: 15_000 })
  await go.click()
  await expect(page.locator('.shot-tab .shot-thumb')).toHaveCount(1, { timeout: 45_000 })
  await page.locator('.shot-tab .shot-thumb').first().click()                                               // the character: the picked result
  const rangeEnd = page.locator('.stage-timeline .range-field input').nth(1)
  await rangeEnd.fill('8'); await rangeEnd.dispatchEvent('change')                                          // 9 frames: 4n + 1 on Wan's grid
  // the method: Animate — the guide is the pose sequence (Depth is disabled), at the model's grid
  await page.locator('.shot-tab button[aria-label="clip method animate"]').click()
  await expect(page.locator('.shot-tab button[aria-label="clip method animate"]')).toHaveClass(/active/)
  await expect(page.locator('.shot-tab .segmented button', { hasText: /^Depth$/ })).toBeDisabled()
  await expect(page.locator('.shot-tab .clip-section .hint').last()).toContainText('for 77 frames')                 // the E19 note sits in its ? (D116)
  type Doc = { id: string; name: string; passes: { guides?: Record<string, { asset_id: string; frames: number; size: { w: number; h: number } }> }[] }
  const doc = async () => (await api<{ items: Doc[] }>('GET', '/stages')).items.find((s) => s.name === name)!
  await page.locator('.shot-tab button', { hasText: /^Render sequence$/ }).click()
  await expect.poll(async () => (await doc()).passes[0]?.guides?.pose?.frames ?? 0, { timeout: 60_000 }).toBe(9)
  const guide = (await doc()).passes[0].guides!.pose
  expect(guide.size.w % 16).toBe(0); expect(guide.size.h).toBe(480)                                        // Wan's 480p, on the 16 grid
  await page.locator('.shot-tab button', { hasText: /^Render clip/ }).click()
  await expect(page.locator('.shot-tab .clip-thumb')).toHaveCount(1, { timeout: 120_000 })
  type Clip = AssetLite & { kind: string; parents: string[]; model_id: string | null; frames: number | null; params: { recipe: { guide: { kind: string } } } }
  const caps = await api<{ stage: { animate: { model_id: string } } }>('GET', '/capabilities')
  const clips = (await api<{ items: Clip[] }>('GET', '/assets?kind=video&suite=stage&sort=created_desc&limit=20')).items.filter((a) => a.model_id === caps.stage.animate.model_id)
  expect(clips.length).toBeGreaterThanOrEqual(1)
  expect(clips[0].frames).toBe(9); expect(clips[0].params.recipe.guide.kind).toBe('pose'); expect(clips[0].parents).toContain(guide.asset_id)
})

test('a 3D prop (P18, D84): "Make a 3D prop…" on a tile says its cost, the fake engine answers with a GLB, the mesh asset lands with lineage and a thumbnail, and the Stage library places it', async ({ page }) => {
  await openApp(page, { suite: 'catalogue' })
  const src = tiles(page).filter({ hasNot: page.locator('.badge-dot[title="clip"], .badge-dot[title^="a spoken"], .badge-dot[title^="3D prop"]') }).nth(5)   // an image: earlier scenarios add clips and lines at the top
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
  await openAnimate(page, 'Clay')
  await page.locator('.placeholder button', { hasText: /^New stage/ }).click()
  await dialog.locator('input').fill('Props')
  await dialog.locator('button.primary').click()
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await page.locator('.lib-grid .mesh-card').first().click()
  await expect(page.locator('.panel .stage-insp h4')).toContainText('Mesh 1')
  await expect.poll(() => page.evaluate(() => (window as unknown as { __loom2Stage: { meshes: () => { loaded: string[]; failed: Record<string, string> } } }).__loom2Stage.meshes().loaded.length), { timeout: 15_000 }).toBe(1)
  await expect.poll(async () => (await api<{ params: { thumb_source?: string } }>('GET', `/assets/${m.id}`)).params.thumb_source, { timeout: 15_000 }).toBe('client')   // the viewport's fitted view became the thumbnail
  await page.screenshot({ path: 'node_modules/.e2e/stage-prop.png' })
})

test('a prop (D110 PS1–PS2): Story\'s Props tab lists the props (Cast no longer does); "Make the 3D model…" says its cost, the fake engine\'s GLB lands stood upright as the version\'s model, and the page shows it turning', async ({ page }) => {
  test.setTimeout(120_000)
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const name = `Crate ${Date.now().toString(36)}`
  const prop = await api<{ id: string; current: string }>('POST', '/story/profiles', { name, cls: 'prop', hero_asset_id: img, appearance: 'an old wooden slatted crate' })
  await openApp(page, { suite: 'story', tab: 'props' })
  const row = page.locator(`.props-panel .story-row.profile-row[data-id="${prop.id}"]`)
  await expect(row).toBeVisible()
  await row.click()
  await expect(page.locator('.cast-page h2')).toContainText(name)
  const section = page.locator('.cast-page .prop-model')
  await expect(section).toBeVisible()
  await expect(section.locator('.model-view.empty')).toBeVisible()
  await page.locator('nav.rail button[title^="Cast"]').click()                                             // Cast keeps characters and places
  await expect(page.locator(`.cast-panel .story-row.profile-row[data-id="${prop.id}"]`)).toHaveCount(0)
  await page.locator('nav.rail button[title^="Props"]').click()
  await expect(page.locator('.cast-page h2')).toContainText(name)
  const make = section.locator('button', { hasText: 'Make the 3D model' })
  if (JSON.parse(process.env.LOOM2_E2E ?? '{}').variant === 'open') {                                       // Q22: no image → 3D model under open
    await expect(make).toBeDisabled()
    await expect(section.locator('[data-status]')).toContainText('DINOv3')
    return
  }
  await make.click()
  const dialog = page.locator('.modal.ask')
  await expect(dialog).toContainText(/upright/)
  await expect(dialog).toContainText(/min/)                                                                 // the cost, before the job is queued
  await dialog.locator('button.primary').click()
  type Ver = { id: string; model_asset_id: string | null; model_from: string | null }
  const ver = async () => (await api<{ versions: Ver[] }>('GET', `/story/profiles/${prop.id}`)).versions.find((v) => v.id === prop.current)!
  await expect.poll(async () => (await ver()).model_asset_id, { timeout: 90_000 }).not.toBeNull()
  const v = await ver()
  expect(v.model_from).toBe(img)                                                                            // made from the hero (no animation reference yet)
  const mesh = await api<{ kind: string; params: { upright_deg: number[] | null } }>('GET', `/assets/${v.model_asset_id}`)
  expect(mesh.kind).toBe('mesh'); expect(mesh.params.upright_deg).toEqual([0, 0, 0])                         // the fake's flat triangle needs no turn
  await expect(section.locator('.model-view canvas.model-view-canvas')).toBeVisible({ timeout: 15_000 })
  await expect(section.locator('[data-status]')).toContainText('Animate places it')
  await page.screenshot({ path: 'node_modules/.e2e/prop-model.png' })
  // PS3: Animate's library lists the prop; a click places its model bound to the prop; the viewport loads it; the Outliner names the prop
  await openAnimate(page, 'Clay')
  await page.locator('.placeholder button', { hasText: /^New stage/ }).click()
  await dialog.locator('input').fill('Props scene')
  await dialog.locator('button.primary').click()
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await page.locator(`.lib-grid .prop-card[data-id="${prop.id}"]`).click()
  await expect(page.locator('.panel .stage-insp h4')).toContainText(name)
  await expect(page.locator('.stage-insp [aria-label="the mesh\'s prop"] button[aria-pressed="true"]')).toHaveAttribute('aria-label', name)
  await expect.poll(() => page.evaluate(() => (window as unknown as { __loom2Stage: { meshes: () => { loaded: string[] } } }).__loom2Stage.meshes().loaded.length), { timeout: 15_000 }).toBe(1)
  await expect(page.locator('.outl-row .bound-tag', { hasText: name })).toBeVisible()
  await expect.poll(async () => {
    const stages = await api<{ items: { name: string; objects: { kind: string; asset_id: string | null; profile_id: string | null }[] }[] }>('GET', '/stages')
    const s = stages.items.find((x) => x.name === 'Props scene')
    return s?.objects.filter((o) => o.kind === 'mesh').map((o) => `${o.profile_id} ${o.asset_id}`).join(',')
  }, { timeout: 10_000 }).toBe(`${prop.id} ${v.model_asset_id}`)                                           // saved bound, with the version's model
})

test('a final shot (D111 PS5a–c): "Make the final shot…" splits a scene into its layers — the plate, a character, a prop, the shadows — and their passes land in a final record at F16; the plate is a Stage shot of the bare set, projected by Stage into its frames; the character layer is performed by Wan Animate and matted by SAM 3; the assembly makes the clip', async ({ page }) => {
  test.setTimeout(120_000)
  await openApp(page)
  await openAnimate(page, 'Clay')
  await page.locator('.placeholder button', { hasText: /^New stage/ }).click()
  const dialog = page.locator('.modal.ask')
  await dialog.locator('input').fill('Final scene')
  await dialog.locator('button.primary').click()
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  // a character with an animation reference, bound to the figure (PS5c performs it)
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const who = await api<{ id: string; name: string }>('POST', '/story/profiles', { name: `Fin ${Date.now().toString(36)}`, cls: 'character', hero_asset_id: img, appearance: 'a courier' })
  await api('PUT', `/story/profiles/${who.id}/versions/v1/anim-ref`, { side: 'front', asset_id: img })
  await page.locator('.lib-grid button', { hasText: /^room$/ }).click()
  await page.locator('.lib-grid button', { hasText: /^Adult/ }).click()
  await page.locator(`.panel [aria-label="the figure's character"] button[aria-label="${who.name}"]`).click()
  await page.locator('.lib-grid button', { hasText: /^crate$/ }).click()
  await page.locator('.lib-grid button', { hasText: /^Add light$/ }).click()
  await page.evaluate(() => (window as unknown as { __loom2Stage: { setRange: (a: number, b: number) => void } }).__loom2Stage.setRange(0, 12))   // half a second: 9 frames at F16
  await page.locator('.final-section button', { hasText: /^Make the final shot/ }).click()
  await expect(dialog).toContainText(/4 layers/)
  await expect(dialog).toContainText(/9 frames/)
  await dialog.locator('button.primary').click()
  await expect(page.locator('.final-section .final-row')).toBeVisible({ timeout: 60_000 })
  type Fin = { id: string; frames: number; rate: number; stage_id: string; layers: { id: string; kind: string; method: string; passes: Record<string, number>; keypoints: boolean; status: string }[] }
  const stages = await api<{ items: { id: string; name: string }[] }>('GET', '/stages')
  const stage = stages.items.find((s) => s.name === 'Final scene')!
  const fin = (await api<{ items: Fin[] }>('GET', `/finals?stage_id=${stage.id}`)).items[0]
  expect(fin.frames).toBe(9); expect(fin.rate).toBe(16)
  expect(fin.layers.map((l) => `${l.kind}/${l.method}`)).toEqual(['plate/projected', 'figure/move', 'prop/rendered', 'shadows/stage'])
  expect(fin.layers.every((l) => Object.values(l.passes).every((n) => n === 9) && l.status === 'passes')).toBe(true)
  expect(fin.layers[1].keypoints).toBe(true)                                                                // the figure's keypoints, for where it starts
  const r = await fetch(`http://127.0.0.1:${env().port}/finals/${fin.id}/layers/${fin.layers[1].id}/pose/0`, { headers: { 'X-Loom-Token': env().token } })
  expect(r.status).toBe(200); expect(r.headers.get('content-type')).toContain('image/png')
  await expect(page.locator('.final-section .final-layers li')).toHaveCount(4)
  // PS5b: the plate — a Stage shot of the bare set on the fake engine, then Stage projects it along the camera path into the layer's frames
  await page.locator('.final-section li[data-kind="plate"] button', { hasText: 'Make the plate' }).click()
  type Lay = { id: string; status: string; still_asset_id: string | null; frames_done: number; job_ids: string[] }
  const plateOf = async () => (await api<{ layers: Lay[] }>('GET', `/finals/${fin.id}`)).layers.find((l) => l.id === 'plate')!
  await expect.poll(async () => { const p = await plateOf(); return `${p.status} ${p.frames_done}` }, { timeout: 60_000 }).toBe('done 9')
  const plate = await plateOf()
  expect(plate.still_asset_id).toBeTruthy(); expect(plate.job_ids).toHaveLength(1)
  const job = (await api<{ items: { id: string; recipe: { kind: string; prompt_text: string } }[] }>('GET', '/jobs')).items.find((j) => j.id === plate.job_ids[0])!
  expect(job.recipe.kind).toBe('stage_shot'); expect(job.recipe.prompt_text).toMatch(/^The room is empty/)
  const pf = await fetch(`http://127.0.0.1:${env().port}/finals/${fin.id}/layers/plate/frames/8`, { headers: { 'X-Loom-Token': env().token } })
  expect(pf.status).toBe(200)
  await expect(page.locator('.final-section li[data-kind="plate"] .status')).toHaveText(/done · 9 frames/)
  await expect(page.locator('.final-section li[data-kind="plate"] img.still')).toBeVisible()
  // PS5c: the character layer — its reference (the anim ref; not keyable off a plain ground here, so padded), Wan Animate on the fake engine, one batch of 9
  await page.locator('.final-section li[data-kind="figure"] button', { hasText: 'Perform' }).click()
  type Fig = Lay & { batches: { k: number; job_id: string; clip_id: string | null }[]; guide_asset_id: string | null; reference_asset_id: string | null }
  const figOf = async () => (await api<{ layers: Fig[] }>('GET', `/finals/${fin.id}`)).layers.find((l) => l.id === fin.layers[1].id)!
  await expect.poll(async () => { const p = await figOf(); return `${p.status} ${p.frames_done}` }, { timeout: 60_000 }).toBe('done 9')
  const fig = await figOf()
  expect(fig.batches).toHaveLength(1); expect(fig.batches[0].clip_id).toBeTruthy(); expect(fig.guide_asset_id).toBeTruthy()
  const perf = (await api<{ items: { id: string; recipe: { kind: string; guide: { kind: string }; chain: { offset: number } | null; frames: number } }[] }>('GET', '/jobs')).items.find((j) => j.id === fig.batches[0].job_id)!
  expect(perf.recipe.guide.kind).toBe('pose'); expect(perf.recipe.chain?.offset).toBe(0); expect(perf.recipe.frames).toBe(9)
  await expect(page.locator('.final-section li[data-kind="figure"] button', { hasText: 'Re-take' })).toBeVisible()
  const matteJob = (await api<{ items: { id: string; kind: string; status: string }[] }>('GET', '/jobs')).items.find((j) => fig.job_ids.includes(j.id) && j.kind === 'matte_sequence')
  expect(matteJob?.status).toBe('done')                                                                    // PS5d: SAM 3 on the layer's frames, by itself
  // PS5e: the assembly — the layers composited into a clip on the final
  await page.locator('.final-section .final-foot button', { hasText: 'Assemble the shot' }).click()
  type Done = { clip_id: string | null; assembly: { frames: number; conform?: string } | null }
  await expect.poll(async () => (await api<Done>('GET', `/finals/${fin.id}`)).clip_id, { timeout: 60_000 }).toBeTruthy()
  const done = await api<Done>('GET', `/finals/${fin.id}`)
  expect(done.assembly?.frames).toBe(9)
  const clip = await api<{ frames: number; fps: number }>('GET', `/clips/${done.clip_id}`)
  expect([`${clip.frames}@${clip.fps}`]).toContain(done.assembly?.conform ? '13@24' : '9@16')                // RIFE when the local tool is there (D27)
  await expect(page.locator('.final-section [data-play]')).toBeVisible()
  // AE1 / AP1 thin (D114): the composition (an EffectCraft project beside the final — the fake session), scrubbed at the Final level, rendered
  await page.locator('.final-section [data-compose]').click()
  await expect(page.locator('.final-section [data-comp-rev]')).toHaveText(/composition · revision 0/)
  type Comp = { revision: number; stack: string[]; clip_id: string | null; layers: { id: string }[] }
  const comp = await api<Comp>('GET', `/finals/${fin.id}/composition`)
  expect(comp.layers.map((l) => l.id)).toEqual(['plate', 'shadows', ...comp.stack])
  await page.locator('.final-section [data-open-final]').click()
  await expect(page.locator('.animate-levels button[aria-pressed="true"]')).toHaveText(/Final/)
  await expect(page.locator('.final-viewer img.final-frame')).toBeVisible()
  await expect(page.locator('.final-viewer .final-chip')).toHaveText(/^\d+ %$/)                           // the number alone (UX9 U2)
  await page.locator('.final-viewer .final-scrub').fill('4')
  await expect(page.locator('.final-viewer .counter')).toHaveText(/^frame 4 \//)
  await expect.poll(async () => page.locator('.final-viewer img.final-frame').getAttribute('data-side'), { timeout: 10_000 }).toBe('full')   // at rest: the full frame
  // AE2: the editor — Layers and Properties in the column; each edit one engine command, the viewer following the new revision
  await expect(page.locator('#anim-sec-layers .comp-layer-list li')).toHaveCount(5)                       // the character, her matte, the prop, the shadows, the plate
  const row = (name: RegExp) => page.locator('#anim-sec-layers .comp-layer-list li').filter({ has: page.locator('.name', { hasText: name }) })   // by the name, not the selects' options
  await row(/^Shadows$/).locator('button.sw[title^="Video"]').click()
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 1/)
  const figName = fin.layers[1].name                                                                        // the figure's layer carries the Stage figure's name (her matte is "… · matte")
  await row(new RegExp(`^${figName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`)).click()
  const editor = page.locator('#anim-sec-layers li.selected .layer-editor')                                 // UX9 U1: the editor under the selected row
  await expect(page.locator('#anim-sec-layers li.selected .name')).toHaveText(figName)
  await expect(editor.locator('.segmented button[aria-pressed="true"]')).toHaveText('Properties')
  const opacity = editor.locator('.prop-row[data-path="transform/opacity"] input')
  await expect(opacity).toHaveValue('100')
  await opacity.fill('50')
  await opacity.press('Enter')
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 2/)
  await editor.locator('.prop-row[data-path="transform/opacity"] button.key').click()                     // a keyframe at the playhead (frame 4)
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 3/)
  await expect(editor.locator('.prop-row[data-path="transform/opacity"] ul.keys li')).toHaveCount(1)
  await page.locator('#anim-sec-layers .verbs button[title^="Undo"]').click()
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 4/)
  await expect(editor.locator('.prop-row[data-path="transform/opacity"] ul.keys li')).toHaveCount(0)
  await page.locator('#anim-sec-layers .verbs button[title^="Undo"]').click()
  await expect(opacity).toHaveValue('100')
  // AE2c: a rectangle mask drawn on the frame with the tool, its outline over the frame (UX9 U3); AE2d: the layer's out trimmed to the playhead, the lanes
  await editor.locator('.segmented button', { hasText: 'Masks' }).click()
  await editor.locator('.verbs button[title^="Mask: rectangle"]').click()
  const box = (await page.locator('.final-viewer img.final-frame').boundingBox())!
  await page.mouse.move(box.x + box.width * 0.2, box.y + box.height * 0.2)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width * 0.6, box.y + box.height * 0.7, { steps: 6 })
  await page.mouse.up()
  await expect(editor.locator('.comp-mask-list li')).toHaveCount(1)
  await expect(page.locator('.final-viewer svg.mask-overlay g.mask.selected path')).toHaveCount(1)       // drawn on the frame, selected
  await expect(page.locator('.final-viewer svg.mask-overlay g.mask.selected circle.vertex')).toHaveCount(4)
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 6/)
  // a shape from points (the pen): three clicks, the first point again closes it
  await editor.locator('.verbs button[title^="Mask: pen"]').click()
  for (const [fx, fy] of [[0.7, 0.2], [0.9, 0.3], [0.8, 0.6]]) await page.mouse.click(box.x + box.width * fx, box.y + box.height * fy)
  await expect(page.locator('.final-viewer svg.mask-overlay g.mask.drawing circle')).toHaveCount(3)
  await page.mouse.click(box.x + box.width * 0.7, box.y + box.height * 0.2)
  await expect(editor.locator('.comp-mask-list li')).toHaveCount(2)
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 7/)
  await editor.locator('.comp-mask-list li').nth(1).locator('button[title^="Remove"]').click()
  await expect(editor.locator('.comp-mask-list li')).toHaveCount(1)
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 8/)
  // D116: the masks filled instead of outlined; a mask from the layer's content (her matte), keyed over the shot; followed by the tracker; an Object Matte by a click
  await editor.locator('.verbs button[title^="Mask fill"]').click()
  await expect(page.locator('.final-viewer svg.mask-overlay')).toHaveAttribute('data-view', 'fill')
  await editor.locator('.verbs button[title^="Mask fill"]').click()
  await expect(page.locator('.final-viewer svg.mask-overlay')).toHaveAttribute('data-view', 'lines')
  await editor.locator('.verbs button[title^="Mask: from the layer"]').click()
  await expect(editor.locator('.comp-mask-list li')).toHaveCount(2)
  await expect(editor.locator('.comp-mask-list li').nth(1)).toHaveAttribute('data-animated', 'true')                 // keyed on every frame: it follows
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 9/)
  const settled = () => expect(page.locator('.final-viewer')).not.toHaveAttribute('data-editing', 'true')          // the edit's reloads done: the next command is not dropped
  await settled()
  await editor.locator('.comp-mask-list li').nth(0).locator('button[title^="Follow the motion"]').click()            // the rectangle tracked from the playhead
  await expect(editor.locator('.comp-mask-list li').nth(0)).toHaveAttribute('data-animated', 'true')
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 10/)
  await settled()
  await editor.locator('.verbs button[title^="Mask: object"]').click()
  await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.5)
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 11/)
  await editor.locator('.segmented button', { hasText: 'Effects' }).click()
  await expect(editor.locator('.comp-effect-list li')).toHaveCount(1)                                                 // the Object Matte is an effect on the layer
  await expect(editor.locator('.comp-effect-list li').first()).toContainText('Object Matte')
  await editor.locator('.comp-effect-list li button[title^="Remove"]').click()
  await expect(editor.locator('.comp-effect-list li')).toHaveCount(0)
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 12/)
  await editor.locator('.segmented button', { hasText: 'Masks' }).click()
  await editor.locator('.comp-mask-list li').nth(1).locator('button[title^="Remove"]').click()
  await expect(editor.locator('.comp-mask-list li')).toHaveCount(1)
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 13/)
  await page.locator('#anim-sec-layers .verbs button[title^="Trim out to the playhead"]').click()   // at frame 4: out = 5 / 16 s
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 14/)
  type CompLayer = { id: number; name: string; out: number }
  const trimmed = (await api<{ items: CompLayer[] }>('GET', `/finals/${fin.id}/composition/layers`)).items.find((l) => l.name === figName)!
  expect(trimmed.out).toBeCloseTo(5 / 16, 5)
  await expect(page.locator('.final-viewer .final-lanes .lane')).toHaveCount(5)
  // AE3: an effect from the curated tiles on the selected layer, a dial set, Before toggled (nothing saved), the effect removed
  await editor.locator('.segmented button', { hasText: 'Effects' }).click()
  await editor.locator('.fx-tile[data-effect="Gaussian Blur"]').click()
  await expect(editor.locator('.comp-effect-list li')).toHaveCount(1)
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 15/)
  const blur = editor.locator('.comp-effect-list li .dial[data-param="effects/#1/blurriness"] input')
  await blur.fill('4')
  await blur.press('Enter')
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 16/)
  await page.locator('.final-transport button[title^="Before"]').click()
  await expect(page.locator('.final-viewer img.final-frame')).toHaveAttribute('data-before', 'true')
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 16/)                 // nothing saved
  await page.locator('.final-transport button[title^="Before"]').click()
  await expect(page.locator('.final-viewer img.final-frame')).not.toHaveAttribute('data-before', 'true')
  await editor.locator('.comp-effect-list li button[title^="Remove"]').click()
  await expect(editor.locator('.comp-effect-list li')).toHaveCount(0)
  await page.locator('.final-section [data-render]').click()
  await expect.poll(async () => (await api<Comp>('GET', `/finals/${fin.id}/composition`)).clip_id, { timeout: 60_000 }).toBeTruthy()
  const finished = await api<Done>('GET', `/finals/${fin.id}`)
  expect(finished.clip_id).toBe((await api<Comp>('GET', `/finals/${fin.id}/composition`)).clip_id)                // the finished shot is the final's clip
  await expect(page.locator('.final-section [data-comp-rev]')).toHaveText(/rendered at revision \d+/)   // the revision the render saw (the edits above moved it)
})

test('a world (17 / SY0, D85): the Story suite\'s World tab adds a style and a logline that save with their revision; Generate\'s Style picker appends the fragment, which the job records', async ({ page }) => {
  await openApp(page, { suite: 'story' })
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Story/)
  await expect(page.locator('.world-editor')).toBeVisible()
  await page.locator('.world-editor textarea[aria-label="logline"]').fill('A courier must cross the city before dawn.')
  await page.locator('.story-panel button', { hasText: 'Add style' }).click()                                 // the panel's verb (D32)
  await expect(page.locator('.world-editor .style-tile.active')).toBeVisible()                               // D90 (02 §4.1): a tile, selected; written in the Inspector only
  await page.locator('.inspector input[aria-label="selected style name"]').fill('Ink wash')
  await page.locator('.inspector textarea[aria-label="selected style fragment"]').fill('ink and wash storyboard, loose brush')   // folded open while empty
  await expect(page.locator('.inspector .story-insp h4', { hasText: 'Style' })).toContainText('Ink wash')     // the new style is selected
  await expect(page.locator('.world-editor .style-tile.active .name')).toHaveText('Ink wash')
  type WorldLite = { revision: number; logline: string; default_style: string | null; styles: { id: string; name: string; fragment: string; group_id: string | null }[] }
  await expect.poll(async () => (await api<WorldLite>('GET', '/story/world')).styles.find((s) => s.name === 'Ink wash')?.fragment, { timeout: 10_000 }).toBe('ink and wash storyboard, loose brush')
  // D90 (02 §4.1): Make a sample image — one job on the swatch model into the style's own group, whose cover becomes the style's face
  await page.locator('.inspector button', { hasText: 'Make a sample image' }).click()
  await expect(page.locator('.world-editor .style-tile.active .face img')).toBeVisible({ timeout: 45_000 })
  await expect(page.locator('.inspector .style-sample img')).toBeVisible()
  const w = await api<WorldLite>('GET', '/story/world')
  expect(w.logline).toBe('A courier must cross the city before dawn.')
  expect(w.revision).toBeGreaterThanOrEqual(1)
  const style = w.styles.find((s) => s.name === 'Ink wash')!
  const sample = Object.values((await api<{ assets: Record<string, { params: { style_id?: string | null } }> }>('GET', `/groups/${style.group_id}`)).assets)
  expect(sample.length === 1 && sample[0].params.style_id === style.id).toBe(true)                             // the sample ran under the style, on its group
  expect(w.default_style).toBe(w.styles[0].id)                                                               // the first style made is the default
  // Generate: the picker lists it and says what it appends; the job records the style and the text that ran
  await openImage(page, 'Make')
  await page.locator('nav.rail button[title^="Model"]').click()                                               // Klein 4B: the one model the e2e tree holds in both variants
  await page.locator('.model-card').filter({ has: page.locator('span', { hasText: /^Klein 4B$/ }) }).click()
  await page.locator('nav.rail button[title^="Prompt"]').click()                                              // switches the tab (a click on the active tab would fold the panel)
  await page.locator('.segmented button', { hasText: /^Text$/ }).click()
  await page.locator('.panel .style-pick button[aria-label="Ink wash"]').click()                   // D90: styles are picked by their sample tile
  await expect(page.locator('.panel .style-pick button[aria-label="Ink wash"]')).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('.panel .style-pick button[aria-label="Ink wash"]')).toHaveAttribute('title', /ink and wash storyboard, loose brush/)
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
  // D115: Expand… jumps into Image with the character as the subject and Full coverage pre-picked in the Poses section; the scenario keeps
  // three close-up tiles with two expressions (six cells — the training below wants four references of one shot size) and runs Expand ▶
  await page.locator('.panel .foot button.primary', { hasText: /^Expand/ }).click()
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Image/)
  await expect(page.locator('.panel .foot .run-switch button[aria-pressed="true"]')).toHaveText('Expand')
  await expect.poll(() => page.locator('#gen-sec-poses .pose-tile.on').count()).toBeGreaterThanOrEqual(10)   // Full coverage's tiles
  await page.locator('#gen-sec-poses .gen-sec-head button', { hasText: 'clear' }).click()
  for (const x of ['serious', 'sad', 'surprised']) await page.locator(`#gen-sec-poses .pose-chips .chip[data-expression="${x}"]`).click()   // neutral and smile stay
  await expect(page.locator('#gen-sec-poses .pose-chips .chip.on')).toHaveCount(2)
  for (const a of ['front', 'three-quarter left', 'three-quarter right']) await page.locator(`#gen-sec-poses .pose-tile[data-shot="close-up"][data-angle="${a}"]`).click()
  await expect(page.locator('#gen-sec-poses .gen-sec-head')).toContainText('6 cells')
  await expect(page.locator('#gen-sec-poses [data-lands]')).toContainText(`as ${name}'s candidates`)
  await expect(page.locator('.panel .foot button.primary')).toHaveText(/^Expand \d+ ▶/)
  const n = Number((await page.locator('.panel .foot button.primary').textContent())!.match(/Expand (\d+)/)![1])   // six cells × the panel's batch count
  expect(n % 6).toBe(0)
  await expect.poll(async () => (await page.locator('.panel .foot .estimate').textContent()) ?? '', { timeout: 20_000, message: 'the foot settles (the preview answers)' }).toMatch(/≈/)
  await page.locator('.panel .foot button.primary').click()
  if (n > 8) { await expect(dialog).toContainText(new RegExp(`Queue ${n} jobs`)); await dialog.locator('button.primary').click() }   // more than 8 images ask first
  type JobLite = { id: string; batch_id: string | null; origin?: { suite: string; surface: string; ref?: string; payload?: { cell?: { shot: string } } } }
  const castJobs = async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.filter((j) => j.origin?.surface === 'cast' && j.origin.ref === profile.id)
  await expect.poll(async () => (await castJobs()).length, { timeout: 30_000 }).toBe(n)     // one job per cell × count, queued by the batch route
  const after = (await api<{ items: ProfileLite[] }>('GET', '/story/profiles')).items.find((p) => p.id === profile.id)!
  const r = { cells: n, group_id: after.versions[0].candidates_group_id! }
  const mine = await castJobs()
  expect(new Set(mine.map((j) => j.batch_id)).size).toBe(1)                            // one batch
  expect(mine.every((j) => j.origin?.suite === 'generate' && j.origin.payload?.cell?.shot === 'close-up')).toBe(true)
  type Page = { assets: Record<string, { id: string; state: string; suite: string; params: { coverage_cell?: { shot: string; angle: string } } }> }
  await expect.poll(async () => Object.keys((await api<Page>('GET', `/groups/${r.group_id}`)).assets).length, { timeout: 120_000 }).toBe(r.cells)
  const cands = Object.values((await api<Page>('GET', `/groups/${r.group_id}`)).assets)
  expect(cands.every((a) => !!a.params.coverage_cell?.shot)).toBe(true)                 // each with its pose recorded (Cast's grid reads it)
  await page.locator('nav.tabs button.tab', { hasText: /^Story/ }).click()               // back to the character's page
  await expect(page.locator('.cast-page h2')).toContainText(name)
  await expect(page.locator('.cand-card')).toHaveCount(r.cells)                       // the page followed the group.changed events
  // keep one with the mouse (the card's ✓), reject one through the context menu: the grid gains a cell, the card dims
  const first = page.locator('.cand-card').first()
  const keptId = (await first.getAttribute('data-id'))!
  await first.hover()
  await first.locator('button[aria-label="add to the reference set"]').click()
  await expect(page.locator('.cand-card')).toHaveCount(r.cells - 1)
  await expect(page.locator('.cov-grid td.one, .cov-grid td.full')).toHaveCount(1)
  expect((await api<{ group: { items: { id: string }[] } }>('GET', `/groups/${gid}`)).group.items.map((i) => i.id)).toContain(keptId)
  const second = page.locator('.cand-card').first()
  await contextChoose(page, second, 'Reject')
  await expect(second).toHaveClass(/\breject\b/)
  // LT2: four more references of the same shot size through the API (training needs 4; the Curate step stays open — one row of four)
  const keptShot = cands.find((a) => a.id === keptId)?.params.coverage_cell?.shot
  const rejectedId = (await second.getAttribute('data-id'))!
  const more = cands.filter((a) => a.id !== keptId && a.id !== rejectedId).sort((a, b) => Number(b.params.coverage_cell?.shot === keptShot) - Number(a.params.coverage_cell?.shot === keptShot)).slice(0, 4)
  await api('POST', `/story/profiles/${profile.id}/versions/v1/curate`, { asset_ids: more.map((a) => a.id), verdict: 'keep' })
  await expect(page.locator('.cand-card')).toHaveCount(r.cells - 5)
  // the bootstrap strip and the Inspector show the state; Lock through the strip → the album refuses a move on the reference page
  await expect(page.locator('.story-strip .bootstrap .bs-step.done')).toHaveCount(2)  // Cast ✓ · Expand ✓
  await page.locator('.story-strip button[title^="Mark final"]').click()
  await expect(dialog).toContainText(/Mark .* final/)
  await dialog.locator('button.primary').click()
  await expect(page.locator('.story-strip .lock-badge')).toBeVisible()
  await expect.poll(async () => (await api<{ items: ProfileLite[] }>('GET', '/story/profiles')).items.find((p) => p.id === profile.id)?.versions[0].state).toBe('final')
  await expect(api('POST', '/groups/move', { items: [{ kind: 'asset', id: keptId }], to: null })).rejects.toThrow(/423/)
  await expect(page.locator('.panel .foot .estimate')).toContainText(/is final/)
  // LT2 (18 §3c): Train from the Inspector — the readiness line, 100 steps on the fake trainer, staged → Release → the version holds the LoRA
  const training = page.locator('.inspector .training')
  await expect(training.locator('.readiness')).toContainText(/\d+ · (thin|good|strong)/)
  await training.locator('input[aria-label="train steps"]').fill('100')
  await training.locator('input[aria-label="train setting"]').fill('plain studio background')
  await page.locator('.inspector button[title^="Train a LoRA"]').click()
  await expect(dialog).toContainText(/Train .* v1\?/)
  await expect(dialog).toContainText(/100 steps at 512²/)
  await dialog.locator('button.primary').click()
  await expect(training.locator('.train-job .badge')).toHaveText('staged')
  type JobLite2 = { id: string; kind: string; status: string; result: { lora_id?: string; trigger?: string } | null }
  const trainJob = async () => (await api<{ items: JobLite2[] }>('GET', '/jobs')).items.filter((j) => j.kind === 'train_lora').sort((a, b) => (a.id < b.id ? 1 : -1))[0]
  expect((await trainJob()).status).toBe('staged')
  await page.locator('.inspector .train-job button[title^="Run now"]').click()
  await expect.poll(async () => (await trainJob()).status, { timeout: 60_000 }).toBe('done')
  const lora = (await trainJob()).result!
  expect(lora.lora_id).toMatch(/^lora_/)
  await expect(training).toContainText(`${name} v1 · 100 steps`)
  await expect(training.locator('.mono').first()).toHaveText(lora.trigger!)
  const rec = (await api<{ items: { id: string; name: string; base: string; steps: number; dataset: { count: number; setting: string } }[] }>('GET', '/story/loras')).items.find((l) => l.id === lora.lora_id)!
  expect(rec.steps).toBe(100)
  expect(rec.dataset.setting).toBe('plain studio background')
  await expect(page.locator('.story-strip .bootstrap .bs-step.done')).toHaveCount(4)  // Cast ✓ · Expand ✓ · Train ✓ · Lock ✓
  // the mention: Generate's @ picker lists the profile first; the preview resolves it to v1's reference set with the hero first
  await openImage(page, 'Make')
  await page.locator('#gen-sec-model').scrollIntoViewIfNeeded()                      // not the rail: a click on the tab the column already sits on folds the panel
  await page.locator('.model-card').filter({ has: page.locator('span', { hasText: /^Klein 4B$/ }) }).click()
  await expect(page.locator('.panel select[aria-label="LoRA slot 1"] option', { hasText: `${name} v1 · Klein 4B · 100 steps` })).toHaveCount(1)   // LT2: the trained LoRA fits the 4B base
  await page.locator('nav.rail button[title^="Prompt"]').click()
  await page.locator('.segmented button', { hasText: /^Text$/ }).click()
  await page.locator('.panel textarea').fill('at the gate')
  await page.locator('.text-prompt button[aria-label^="Mention a group"]').click()
  await page.locator('.ctx-menu button.item').filter({ hasText: `${name} · character` }).click()   // the profile's entry (its groups are named after it too)
  await expect(page.locator('.panel .mention-chips .mchip.profile')).toContainText(`@${name}`)
  await expect(page.locator('.panel .mention-chips .mchip.profile .lora-toggle.on')).toHaveText('+ LoRA')             // LT3: the version's LoRA rides along
  await expect(page.locator('.panel textarea')).toHaveValue(new RegExp(`@${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`))
  type Preview = { mentions: { profile_id: string | null; version: string | null; group_id: string; asset_ids: string[] }[]; ref_list: { asset_id: string | null; note: string | null }[] }
  const klein4bId = Object.entries((await api<{ models: Record<string, { label: string }> }>('GET', '/capabilities')).models).find(([, m]) => m.label === 'Klein 4B')![0]
  await expect.poll(async () => {
    const pv = await api<Preview>('POST', '/recipes/preview', { recipe: { kind: 't2i', model_id: klein4bId, prompt_mode: 'text', prompt_text: `@${name} at the gate`, mentions: [{ profile_id: profile.id, name }] } })
    return `${pv.mentions[0]?.profile_id}/${pv.mentions[0]?.version}/${pv.mentions[0]?.group_id}/${pv.ref_list[0]?.asset_id}`
  }).toBe(`${profile.id}/v1/${gid}/${heroId}`)
  type Preview2 = { mentions: { lora: string | null; lora_available: string | null }[]; loras: { model_id: string; strength: number; lora_name: string | null }[]; serialized_prompt: string }
  const pv2 = await api<Preview2>('POST', '/recipes/preview', { recipe: { kind: 't2i', model_id: klein4bId, prompt_mode: 'text', prompt_text: `@${name} at the gate`, mentions: [{ profile_id: profile.id, name }] } })
  expect(pv2.mentions[0].lora).toBe(lora.lora_id)                                                                   // LT3: added to the slots …
  expect(pv2.loras[0].model_id).toBe(lora.lora_id)
  expect(pv2.serialized_prompt).toContain(lora.trigger!)                                                            // … with the trigger in the prompt
  const off = await api<Preview2>('POST', '/recipes/preview', { recipe: { kind: 't2i', model_id: klein4bId, prompt_mode: 'text', prompt_text: `@${name} at the gate`, auto_lora: false, mentions: [{ profile_id: profile.id, name }] } })
  expect(off.loras).toEqual([])
  expect(off.mentions[0].lora_available).toBe(lora.lora_id)
  // the identity check: eight fake-engine images with / without, the record says the FaceSim weights are absent here
  const chk = await api<{ job_ids: string[]; model_id: string }>('POST', `/story/loras/${lora.lora_id}/check`)
  expect(chk.job_ids).toHaveLength(8)
  await expect.poll(async () => (await api<{ identity: { done?: number } | null }>('GET', `/story/loras/${lora.lora_id}`)).identity?.done ?? 0, { timeout: 90_000 }).toBe(8)
  const ident = (await api<{ identity: { status: string; with: unknown[]; without: unknown[] } }>('GET', `/story/loras/${lora.lora_id}`)).identity
  expect(ident.with).toHaveLength(4)
  expect(ident.status).toMatch(/weights missing/)
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
  await openSection(page, 'Camera')
  await page.locator('#anim-sec-camera button[aria-label^="New shot from this camera"]').click()        // the Camera section's verb (D32)
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
  await openAnimate(page, 'Clay')
  await stageRoute(page)
  await page.locator('.shot-tab button', { hasText: /^Render passes$/ }).click()
  await page.locator('.shot-tab .shot-prompt').fill('a gatehouse at dawn')
  const go = page.locator('.panel .foot button.primary', { hasText: /^Render frame/ })
  await expect(go).toBeEnabled({ timeout: 30_000 })
  await go.click()
  const shotOf = async () => (await api<Shot>('GET', `/story/shots/${shot.id}`))
  await expect.poll(async () => (await shotOf()).versions[0].frame_asset_id, { timeout: 60_000 }).toBeTruthy()
  expect((await shotOf()).versions[0].takes.map((t) => t.kind)).toEqual(['image'])
  // the board shows the frame (Story · Shots was left on the Shots tab, so the rail is not clicked — that would fold the panel)
  await page.locator('nav.tabs button.tab', { hasText: 'Story' }).click()
  await expect(page.locator('.shot-board .shot-player img')).toBeVisible()
  await expect(page.locator('.shot-board .take-card.current')).toHaveCount(1)
  await expect(page.locator('[data-testid="recipe"] .rs.fresh', { hasText: 'Start still' })).toBeVisible()   // RC0 (D96): the stage's still is a run of the recipe's frame step
  await expect(page.locator('[data-testid="recipe"] .rs.missing', { hasText: 'Performance' })).toBeVisible()
  // RC0: the stage moves on → the still is stale; Run stale asks with the plan, renders the passes here (the stage is not on screen) and makes it again
  const stg0 = await api<{ id: string }>('GET', `/stages/${shot.versions[0].stage_id}`)
  await api('PUT', `/stages/${stg0.id}`, stg0)
  await page.locator('[data-testid="recipe"] button[aria-label="check the recipe again"]').click()
  await expect(page.locator('[data-testid="recipe"] .rs.stale', { hasText: 'Start still' })).toContainText(/the stage moved on/)
  const firstFrame = (await shotOf()).versions[0].frame_asset_id
  await page.locator('[data-testid="recipe"] button', { hasText: /^Run stale/ }).click()
  await expect(dialog).toContainText(/Run the stale steps again/)
  await expect(dialog).toContainText(/the stage's passes are rendered first/)
  await dialog.locator('button.primary').click()
  await expect.poll(async () => (await shotOf()).versions[0].frame_asset_id, { timeout: 60_000 }).not.toBe(firstFrame)
  await expect(page.locator('[data-testid="recipe"] .rs.fresh', { hasText: 'Start still' })).toBeVisible({ timeout: 15_000 })
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
  await openAnimate(page, 'Performance')
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
  await expect(page.locator('.story-strip button[aria-label^="Mark final"]')).toBeDisabled()
  await expect(api('POST', `/story/shots/${shot2.id}/versions/v1/finalize`)).rejects.toThrow(/422/)
  // a clip at the format (the fake engine, nine frames) used as the clip → Finalize through the strip → final
  const fullClip = await submit(fmt.width, fmt.height)
  type Hook = { useTake: (kind: 'image' | 'clip', id: string) => Promise<void> }
  await page.evaluate((id) => (window as unknown as { __loom2Story: Hook }).__loom2Story.useTake('clip', id), fullClip)
  await expect(page.locator('.shot-board .take-card')).toHaveCount(2)
  await expect(page.locator('.panel .foot .estimate')).toContainText(/ready to mark final/)
  await page.locator('.story-strip button[aria-label^="Mark final"]').click()
  await expect(dialog).toContainText(/Mark .* final/)
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
  await expect(page.locator('.panel .foot .estimate')).toContainText(/ready to mark final/)
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
  // the nodes landed stepped at the view's centre (they overlap on a small window): lay them out through the index, then one mouse drag
  type Graph = { graph: { revision: number; nodes: { id: string; x: number; y: number }[]; edges: unknown[]; start: string | null } }
  const g0 = (await api<Graph>('GET', '/story/flow')).graph
  const ids = { start: (await start.getAttribute('data-id'))!, dlg: (await dlg.getAttribute('data-id'))!, choice: (await choice.getAttribute('data-id'))! }
  await api('PUT', '/story/flow/graph', { revision: g0.revision, nodes: [{ id: ids.start, x: 0, y: 0 }, { id: ids.dlg, x: 340, y: 0 }, { id: ids.choice, x: 680, y: 0 }], edges: g0.edges, start: g0.start })
  await page.evaluate(() => (window as unknown as { __loom2Story: Hook }).__loom2Story.loadFlow())
  await page.locator('.story-strip button[aria-label="Fit the graph"]').click()
  await expect.poll(async () => (await api<Graph>('GET', '/story/flow')).graph.nodes.find((n) => n.id === ids.choice)?.x).toBe(680)
  const before = await centre(choice.locator('.head'))
  await page.mouse.move(before.x, before.y); await page.mouse.down(); await page.mouse.move(before.x + 10, before.y + 6, { steps: 3 }); await page.mouse.move(before.x + 10, before.y + 90, { steps: 10 }); await page.mouse.up()   // a drag saves on drop
  await expect.poll(async () => (await api<Graph>('GET', '/story/flow')).graph.nodes.find((n) => n.id === ids.choice)?.y ?? 0, { timeout: 10_000 }).toBeGreaterThan(40)
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
  const edges = async () => (await api<FlowLite>('GET', '/story/flow')).graph.edges.length
  const drag = async (from: ReturnType<typeof page.locator>, to: ReturnType<typeof page.locator>) => {
    const a = await centre(from), b = await centre(to)
    await page.mouse.move(a.x, a.y); await page.mouse.down(); await page.mouse.move(a.x + 24, a.y + 4, { steps: 4 }); await page.mouse.move(b.x, b.y, { steps: 16 })
    await page.mouse.move(b.x + 1, b.y + 1); await page.mouse.move(b.x, b.y)                        // a pointermove over the handle before the drop: React Flow snaps on it
    await page.mouse.up()
  }
  // one edge at a time: a slow runner (CI) can drop a drag whose pointer events outran React Flow — the second try is the same mouse path
  const connect = async (from: ReturnType<typeof page.locator>, to: ReturnType<typeof page.locator>, want: number) => {
    await drag(from, to)
    if (await expect.poll(edges, { timeout: 4_000 }).toBe(want).then(() => true, () => false)) return
    await drag(from, to)
    await expect.poll(edges, { timeout: 10_000 }).toBe(want)
  }
  await connect(start.locator('.react-flow__handle.source'), dlg.locator('.react-flow__handle.target'), 1)
  await connect(dlg.locator('.react-flow__handle.source'), choice.locator('.react-flow__handle.target'), 2)
  await connect(choice.locator('.react-flow__handle.source').first(), dlg.locator('.react-flow__handle.target'), 3)
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

test("an episode (17 / SY4, D85): the Shots bin lists a final shot and adds it stamped; the checklist names the plain clip; Export asks, writes the FCPXML with a chapter marker and markers.txt, and the SRT carries the node's line; the old deep link redirects", async ({ page }) => {
  test.setTimeout(120_000)
  // a final shot: a clip at the project format (the fake engine), a Dialogue node bound to it
  const fmt = (await api<{ format: { width: number; height: number } }>('GET', '/project')).format
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=unprocessed&kind=image&sort=created_desc&limit=1')).items[0].id
  const caps = await api<{ defaults: { i2v: string } }>('GET', '/capabilities')
  type JobLite = { id: string; status: string; result: { clip_id?: string } }
  const job = (await api<{ jobs: { id: string }[] }>('POST', '/jobs', { recipe: { kind: 'i2v', model_id: caps.defaults.i2v, start_asset: img, width: fmt.width, height: fmt.height, frames: 9, fps: 16, prompt_text: 'episode clip' }, stage: false, origin: { suite: 'animate', surface: 'clip' } })).jobs[0]
  await expect.poll(async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.id === job.id)?.status, { timeout: 60_000 }).toBe('done')
  const clipId = (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.id === job.id)!.result.clip_id!
  const name = `Ep ${Date.now().toString(36)}`
  const shot = await api<{ id: string }>('POST', '/story/shots', { name, clip_id: clipId })
  await api('POST', `/story/shots/${shot.id}/versions/v1/finalize`)
  const node = await api<{ id: string; revision: number }>('POST', '/story/flow/nodes', { type: 'dialogue', title: `${name} node`, x: 900, y: 500 })
  await api('PATCH', `/story/flow/nodes/${node.id}`, { revision: node.revision, lines: [{ speaker: null, text: 'Open the gate.' }] })
  await api('POST', `/story/flow/nodes/${node.id}/bind`, { shot_id: shot.id })
  // the old Sequence deep link lands on Story · Episode
  await openApp(page, { suite: 'animate', tab: 'sequence' })
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Story/)
  await expect(page.locator('nav.rail button.active[title^="Episode"]')).toBeVisible()
  await page.locator('.seq-list-head button[title^="New cut"]').click()
  const dialog = page.locator('.modal.ask')
  await dialog.locator('input').fill(name)
  await dialog.locator('button.primary').click()
  await expect(page.locator('.seq-row.active')).toContainText(name)
  const card = page.locator(`.shots-bin .seq-clip-card[data-shot="${shot.id}"]`)
  await expect(card).toHaveClass(/\bfinal\b/)
  await expect(card).toContainText(`${name} node`)
  await card.locator('button[aria-label^="add shot"]').click()                                // + : stamped with the shot, its version and its node
  await expect(page.locator('.seq-clip')).toHaveCount(1)
  await page.locator('.seq-bin:not(.shots-bin) .seq-clip-card button').first().click()         // a plain clip beside it
  await expect(page.locator('.seq-clip')).toHaveCount(2)
  type TL = { id: string; name: string; clips: { clip_id: string; shot_id: string | null; shot_version: string | null; node_id: string | null }[] }
  await expect.poll(async () => (await api<{ items: TL[] }>('GET', '/timelines')).items.find((t) => t.name === name)?.clips.length, { timeout: 10_000 }).toBe(2)
  const tl = (await api<{ items: TL[] }>('GET', '/timelines')).items.find((t) => t.name === name)!
  expect(tl.clips[0]).toMatchObject({ clip_id: clipId, shot_id: shot.id, shot_version: 'v1', node_id: node.id })
  expect(tl.clips[1].shot_id).toBeNull()
  await expect(page.locator('.seq-insp .seq-check li.warn')).toHaveCount(1)                   // clip 2: a plain clip
  await expect(page.locator('.panel .foot .estimate')).toContainText('1 of 2 clips not final shots')
  // Export ▶ (the panel foot): the checklist asks, then the FCPXML carries the marker; markers.txt and the SRT follow
  await page.locator('.panel .foot button.primary', { hasText: /^Export/ }).click()
  await expect(dialog).toContainText(/1 of 2 clips not final shots/)
  await dialog.locator('button.primary').click()
  await expect(page.locator('.seq-insp .hint', { hasText: 'last:' })).toContainText('.fcpxml')
  const fx = await api<{ text: string; path: string }>('POST', `/timelines/${tl.id}/export`, { format: 'fcpxml' })
  expect(fx.text).toContain(`value="${name} node"`)
  expect(fx.text.match(/<marker /g)).toHaveLength(1)
  const srt = await api<{ text: string }>('POST', `/timelines/${tl.id}/export`, { format: 'srt' })
  expect(srt.text).toContain('Open the gate.')
  expect(srt.text).toContain('00:00:00,000 -->')
  // CN2: the line voiced on the fake runner rides the FCPXML's audio lane
  const voice = await api<{ id: string }>('POST', '/story/voices', { name: `Ep voice ${name}`, voice: 'af_heart' })
  const tts = await api<{ job_ids: string[] }>('POST', `/story/flow/nodes/${node.id}/lines/0/voice`, { voice_id: voice.id })
  await expect.poll(async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.id === tts.job_ids[0])?.status, { timeout: 60_000 }).toBe('done')
  const fx2 = await api<{ text: string; audio: number }>('POST', `/timelines/${tl.id}/export`, { format: 'fcpxml' })
  expect(fx2.audio).toBe(1)
  expect(fx2.text).toContain('lane="-1"')
  expect(fx2.text).toContain('hasAudio="1"')
  // the Animate rail no longer has the tab
  await openAnimate(page, 'Performance')
  await expect(page.locator('nav.rail button[title^="Sequence"]')).toHaveCount(0)
})

test('a voice (19 / CN2, D87): a draft voice from the Cast Inspector\'s form speaks for the character; the Flow Inspector voices a line on the fake runner — the line gets its ▶, an audio asset with a waveform thumbnail lands, "Voice all lines" takes the fallback voice for the speakerless line', async ({ page }) => {
  test.setTimeout(120_000)
  // a character with a hero and a Dialogue node with two lines (through the API; the Cast and Flow scenarios cover those mouse paths)
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const name = `Vo ${Date.now().toString(36)}`
  const prof = await api<{ id: string; revision: number }>('POST', '/story/profiles', { name, cls: 'character', hero_asset_id: img, appearance: 'a courier' })
  const node = await api<{ id: string; revision: number }>('POST', '/story/flow/nodes', { type: 'dialogue', title: `${name} says`, x: 1200, y: 900 })
  await api('PATCH', `/story/flow/nodes/${node.id}`, { revision: node.revision, lines: [{ speaker: prof.id, text: 'Hi there, come in.' }, { speaker: null, text: 'Thank you.' }] })
  await openApp(page, { suite: 'story', tab: 'cast' })
  await page.locator(`.story-row.profile-row[data-id="${prof.id}"]`).click()
  const voices = page.locator('.inspector .voices')
  await expect(voices.locator('select[aria-label="profile voice"]')).toHaveValue('')
  await page.locator('.inspector button[title^="New voice"]').click()                                   // the form (D32: a button)
  const form = voices.locator('[aria-label="new voice"]')
  await form.locator('input[aria-label="voice name"]').fill(`Narrator ${name}`)
  await expect(form.locator('select[aria-label="kokoro voice"] option')).not.toHaveCount(0)
  await form.locator('select[aria-label="kokoro voice"]').selectOption('am_adam')
  await form.locator('button[aria-label="create voice"]').click()
  await expect(form).toHaveCount(0)
  await expect(voices.locator('select[aria-label="profile voice"] option:checked')).toContainText(`Narrator ${name} · draft`)   // the character speaks with its first voice
  await expect(voices).toContainText('am_adam')
  // the Flow Inspector: 🎙 on line 1 → the fake runner speaks it → ▶ and the audio asset
  await openApp(page, { suite: 'story', tab: 'flow' })
  await page.locator(`.story-row.node-row[data-id="${node.id}"]`).click()
  await expect(page.locator('.inspector input[aria-label="line 1"]')).toHaveValue('Hi there, come in.')
  await expect(page.locator('.inspector button[aria-label="play line 1"]')).toHaveCount(0)
  await page.locator('.inspector button[aria-label="voice line 1"]').click()
  await expect(page.locator('.inspector button[aria-label="play line 1"]')).toBeVisible({ timeout: 60_000 })
  type Line = { text: string; audio_asset_id: string | null; audio_text: string | null }
  const lines = async () => (await api<{ nodes: { id: string; lines: Line[] }[] }>('GET', '/story/flow')).nodes.find((n) => n.id === node.id)!.lines
  expect((await lines())[0]).toMatchObject({ text: 'Hi there, come in.', audio_text: 'Hi there, come in.' })
  const audioId = (await lines())[0].audio_asset_id!
  const asset = await api<{ kind: string; duration_s: number | null; thumb_status: string; parents: string[] }>('GET', `/assets/${audioId}`)
  expect(asset.kind).toBe('audio')
  expect(asset.duration_s).toBeGreaterThan(0.5)
  expect(asset.thumb_status).toBe('done')
  // line 2 has no speaker: "Voice all lines" is refused until a fallback voice is picked, then both lines are covered (line 1 again by its speaker's voice)
  const sel = page.locator('.inspector select[aria-label="fallback voice"]')
  await sel.selectOption({ label: `Narrator ${name} · draft` })
  await page.locator('.inspector button[title^="Voice all lines"]').click()
  await expect(page.locator('.inspector button[aria-label="play line 2"]')).toBeVisible({ timeout: 60_000 })
  await expect.poll(async () => (await lines())[1].audio_asset_id).toBeTruthy()
  // the Catalogue lists it under Type · Audio with its badge
  const audio = await api<{ items: { id: string }[] }>('GET', '/assets?kind=audio&limit=10')
  expect(audio.items.map((a) => a.id)).toContain(audioId)
})

test("experimental extension and lip-sync (D88): Animate's Extend ▶ continues a clip from its own end with the caveat shown; a shot version's Lip-sync ▶ stages a talking take from a voiced line, which lands on the version", async ({ page }) => {
  test.setTimeout(150_000)
  type JobLite = { id: string; status: string; error: string | null; result: { clip_id?: string } | null }
  type ClipLite = { id: string; chained_from: string | null; overlap: number; audio_asset_id: string | null; model_id: string }
  const jobDone = async (id: string) => expect.poll(async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.id === id)?.status, { timeout: 60_000 }).toBe('done')
  const caps = await api<{ defaults: { i2v: string }; experimental: { extend: { models: Record<string, number>; caveat: string }; lipsync: { available: boolean } } }>('GET', '/capabilities')
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const job = (await api<{ jobs: { id: string }[] }>('POST', '/jobs', { recipe: { kind: 'i2v', model_id: caps.defaults.i2v, start_asset: img, width: 832, height: 480, frames: 17, fps: 16, prompt_text: 'she walks' } })).jobs[0]
  await jobDone(job.id)
  const parent = (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.id === job.id)!.result!.clip_id!
  // Extend ▶ in the Animate Inspector: the dialog says experimental and the caveat; the continuation records its parent and overlap
  await openApp(page, { suite: 'animate' })
  type AnimateHook = { getState: () => { loadClips: () => Promise<void>; select: (id: string) => void } }
  await page.evaluate(async (id) => { const an = (window as unknown as { __loom2Animate: AnimateHook }).__loom2Animate.getState(); await an.loadClips(); an.select(id) }, parent)
  await expect(page.locator('.panel .badge.experimental').first()).toBeVisible()                        // D95 (AN1): Selection's Clip fold
  await page.locator('.panel .anim-exp > summary').click()                                                // D90 (02 §9): Extend sits under the Experimental fold
  await page.locator('.panel button[aria-label^="Extend"]').click()
  const dialog = page.locator('.modal.ask')
  await expect(dialog).toContainText('experimental')
  await expect(dialog).toContainText(caps.experimental.extend.caveat.slice(0, 30))
  await dialog.locator('input, textarea').first().fill('she keeps walking')
  await dialog.locator('button.primary').click()
  await expect.poll(async () => (await api<{ items: ClipLite[] }>('GET', '/clips')).items.find((c) => c.chained_from === parent)?.overlap ?? -1, { timeout: 60_000 })
    .toBe(caps.experimental.extend.models[caps.defaults.i2v])
  // lip-sync: a shot whose version has a frame, bound to a node with a voiced line (the fake runner); the verb stages the job; released, the take lands
  const name = `Lip ${Date.now().toString(36)}`
  const shot = await api<{ id: string }>('POST', '/story/shots', { name, frame_asset_id: img })
  const node = await api<{ id: string; revision: number }>('POST', '/story/flow/nodes', { type: 'dialogue', title: `${name} node`, x: 1400, y: 1100 })
  await api('PATCH', `/story/flow/nodes/${node.id}`, { revision: node.revision, lines: [{ speaker: null, text: 'Hello there, nice to see you.' }] })
  await api('POST', `/story/flow/nodes/${node.id}/bind`, { shot_id: shot.id })
  const voice = await api<{ id: string }>('POST', '/story/voices', { name: `${name} voice`, voice: 'af_heart' })
  const tts = await api<{ job_ids: string[] }>('POST', `/story/flow/nodes/${node.id}/lines/0/voice`, { voice_id: voice.id })
  await jobDone(tts.job_ids[0])
  await openApp(page, { suite: 'story', tab: 'shots' })
  await page.locator(`.story-row.shot-row[data-id="${shot.id}"]`).click()
  const block = page.locator('.inspector .lipsync')
  await expect(block.locator('.badge.experimental')).toBeVisible()
  await expect(block.locator('select[aria-label="lip-sync line"] option')).toContainText([`${name} node`])
  await block.locator('select[aria-label="lip-sync preset"]').selectOption('fast')
  await page.locator('.inspector button[aria-label^="Lip-sync"]').click()
  await expect(dialog).toContainText('experimental')
  await dialog.locator('button.primary').click()
  type Lip = JobLite & { kind: string; recipe: { audio?: { asset_id: string }; preset: string }; origin: { surface: string; ref: string } | null }
  const lipJob = async () => (await api<{ items: Lip[] }>('GET', '/jobs')).items.find((j) => j.origin?.surface === 'lipsync' && j.origin.ref === shot.id)
  await expect.poll(async () => (await lipJob())?.status, { timeout: 15_000 }).toBe('staged')
  expect((await lipJob())!.recipe.preset).toBe('fast')
  await api('POST', `/jobs/${(await lipJob())!.id}/release`)
  await jobDone((await lipJob())!.id)
  const clipId = (await lipJob())!.result!.clip_id!
  const lc = (await api<{ items: ClipLite[] }>('GET', '/clips')).items.find((c) => c.id === clipId)!
  expect(lc.audio_asset_id).toBeTruthy()
  type ShotLite = { versions: { id: string; clip_id: string | null; takes: { kind: string; id: string }[] }[] }
  await expect.poll(async () => (await api<ShotLite>('GET', `/story/shots/${shot.id}`)).versions[0].takes.some((t) => t.kind === 'clip' && t.id === clipId), { timeout: 10_000 }).toBe(true)
})

test('lora slots (18 / LT1, D25): the Model tab lists the loras folder\'s file for Klein 4B, a slot with a strength rides the recipe, the job\'s compiled summary names the loader\'s file and the manifest records the slot', async ({ page }) => {
  await openApp(page, { suite: 'generate' })
  await page.locator('nav.rail button[title^="Model"]').click()
  await page.locator('.model-card').filter({ has: page.locator('span', { hasText: /^Klein 4B$/ }) }).click()
  await page.locator('.panel summary', { hasText: /^LoRAs/ }).click()                                         // D90: the slots fold away until one is used
  const slot = page.locator('.panel select[aria-label="LoRA slot 1"]')
  await expect(slot.locator('option', { hasText: 'smoke/mara_smoke' })).toHaveCount(1)                   // the e2e tree's file LoRA (e2e_setup.py)
  if (JSON.parse(process.env.LOOM2_E2E ?? '{}').variant === 'open') {                                       // D26: a file declares no licence — listed, disabled, with the sentence
    await expect(slot.locator('option[disabled]', { hasText: 'smoke/mara_smoke' })).toContainText('open variant')
    await expect(slot.locator('option:not([disabled])', { hasText: '· file' })).toHaveCount(0)              // no file is enabled (the project's own trained LoRA may be)
    return
  }
  await slot.selectOption('file:smoke/mara_smoke.safetensors')
  const strength = page.locator('.panel input[aria-label="LoRA strength 1"]')
  await expect(strength).toBeVisible()
  await strength.fill('0.7')
  await expect(page.locator('.panel select[aria-label="LoRA slot 2"]')).toBeEnabled()                       // the next slot opens
  await page.locator('nav.rail button[title^="Prompt"]').click()
  await page.locator('.segmented button', { hasText: /^Text$/ }).click()
  await page.locator('.panel textarea').fill('a courier in the trained look')
  const before = (await api<Record<string, number>>('GET', '/assets/counts')).unprocessed ?? 0
  const go = page.locator('.panel .foot button.primary', { hasText: /^Generate/ })
  await expect(go).toBeEnabled()
  const count = Number((await go.textContent())!.match(/Generate (\d+)/)![1])
  await go.click()
  await expect.poll(async () => (await api<Record<string, number>>('GET', '/assets/counts')).unprocessed ?? 0, { timeout: 45_000 }).toBe(before + count)
  type Made = AssetLite & { params: { recipe: { loras: { model_id: string; strength: number }[] } } }
  const newest = (await api<{ items: Made[] }>('GET', '/assets?folder=unprocessed&sort=created_desc&limit=1')).items[0]
  expect(newest.params.recipe.loras).toEqual([{ model_id: 'file:smoke/mara_smoke.safetensors', strength: 0.7 }])
  type JobLite = { id: string; status: string; result: { compiled?: { loras?: { model_id: string; strength: number; lora_name: string | null }[] } } | null }
  const jobOf = async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.id === newest.job_id)!
  await expect.poll(async () => (await jobOf()).status, { timeout: 15_000 }).toBe('done')         // the asset lands a moment before its job is marked done
  const job = await jobOf()
  expect(job.result?.compiled?.loras?.[0]).toEqual({ model_id: 'file:smoke/mara_smoke.safetensors', strength: 0.7, lora_name: 'smoke/mara_smoke.safetensors' })
  // the slot is cleared by its own select; a model the file does not fit never lists it under the open variant (the backend's 422 covers the rest)
  await page.locator('nav.rail button[title^="Model"]').click()
  await page.locator('.panel select[aria-label="LoRA slot 1"]').selectOption('')
  await expect(page.locator('.panel input[aria-label="LoRA strength 1"]')).toHaveCount(0)
})

test('makers in context (D90 · UI4): "Make frame ▸ in Image" on a Story shot opens Image with the For chip, the node\'s line and the board\'s image as a reference; the fake engine\'s images land as the version\'s takes, and Back returns to the shot', async ({ page }) => {
  test.setTimeout(120_000)
  const name = `For ${Date.now().toString(36)}`
  type ShotLite = { id: string; name: string; versions: { id: string; frame_asset_id: string | null; takes: { kind: string; id: string }[] }[] }
  // a Shot node with a line, its shot spawned by the node, a board (a group holding a copy of an image) on the node — all through the API
  const node = await api<{ id: string; revision: number }>('POST', '/story/flow/nodes', { type: 'shot', title: name, x: 1600, y: 1300 })
  await api('POST', `/story/flow/nodes/${node.id}/shot`, { name })
  const shot = (await api<{ items: ShotLite[] }>('GET', '/story/shots')).items.find((s) => s.name === name)!
  const src = (await api<{ items: (AssetLite & { kind: string })[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0]
  const copy = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [src.id] })).ids[0]
  const board = await api<Group>('POST', '/groups', { name: `${name} board` })
  await api('POST', '/groups/move', { items: [{ kind: 'asset', id: copy }], to: board.id })
  const rev = (await api<{ nodes: { id: string; revision: number }[] }>('GET', '/story/flow')).nodes.find((n) => n.id === node.id)!.revision   // the spawn moved it on
  await api('PATCH', `/story/flow/nodes/${node.id}`, { revision: rev, text: 'a gatehouse at dawn, wide shot', board_group_id: board.id })
  // Generate on Klein 4B first (it takes references), then Story · Shots → the shot → Make frame ▸ in Generate (a press menu: click, then the entry)
  await openApp(page, { suite: 'generate', tab: 'model' })
  await page.locator('.model-card').filter({ has: page.locator('span', { hasText: /^Klein 4B$/ }) }).click()
  await expect(page.locator('.panel [data-testid="for-chip"]')).toHaveCount(0)                                // opened from its tab: no chip
  await openApp(page, { suite: 'story', tab: 'shots' })                                                       // the panel keeps Klein 4B (persisted)
  await page.locator(`.story-row.shot-row[data-id="${shot.id}"]`).click()
  await page.locator('.shot-board .make-row button[aria-label="Make frame"]').click()
  await page.locator('.ctx-menu button.item', { hasText: 'in Image' }).click()
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Image/)
  const chip = page.locator('.panel [data-testid="for-chip"]')
  await expect(chip).toContainText(`For: ${name} · v1`)
  await page.locator('nav.rail button[title^="Prompt"]').click()
  await page.locator('.segmented button', { hasText: /^Text$/ }).click()
  await expect(page.locator('.text-prompt textarea')).toHaveValue('a gatehouse at dawn, wide shot')              // the node's line
  const go = page.locator('.panel .foot button.primary', { hasText: /^Generate/ })
  await expect(go).toBeEnabled({ timeout: 30_000 })
  const count = Number((await go.textContent())!.match(/Generate (\d+)/)![1])
  await go.click()
  // the takes arrive on v1 (the first fills the empty frame); the jobs carry the for_shot origin and the board's image as reference 1
  await expect.poll(async () => (await api<ShotLite>('GET', `/story/shots/${shot.id}`)).versions[0].takes.length, { timeout: 60_000 }).toBe(count)
  const v1 = (await api<ShotLite>('GET', `/story/shots/${shot.id}`)).versions[0]
  expect(v1.takes.every((t) => t.kind === 'image')).toBe(true)
  expect(v1.frame_asset_id).toBe(v1.takes[0].id)
  type JobLite = { id: string; recipe: { refs?: { asset_id: string }[] }; origin: { surface: string; payload: Record<string, unknown> | null } | null; result: { asset_ids?: string[] } | null }
  const job = (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.result?.asset_ids?.includes(v1.takes[0].id))!
  expect(job.origin?.surface).toBe('for_shot')
  expect(job.origin?.payload).toMatchObject({ shot_id: shot.id, version: 'v1', node_id: node.id })
  expect(job.recipe.refs?.[0]?.asset_id).toBe(copy)
  // ← Back: Story · Shots on the shot, its takes on the board; ✕ ends the context (Generate works as from its tab)
  await chip.locator('button[aria-label^="Back to"]').click()
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Story/)
  await expect(page.locator('.story-strip b')).toHaveText(name)
  await expect(page.locator('.shot-board .take-card')).toHaveCount(count)
  await openImage(page, 'Make')
  await chip.locator('button[aria-label^="Stop making for the shot"]').click()
  await expect(chip).toHaveCount(0)
})

test('the World library (D92 · UI7): an entry added in Story · World gets its picture by itself and is a tile in Generate; its right-click edits it in World; no tile shows letters', async ({ page }) => {
  test.setTimeout(90_000)
  const tag = Date.now().toString(36)
  const words = `teal shop-sign glow ${tag}`, name = `teal ${tag}`                      // unique: the project is reused between runs
  await openApp(page, { suite: 'story', tab: 'world' })
  await page.locator('.story-panel .story-row', { hasText: 'Library' }).click()
  const field = page.locator('.lib-field[data-field="lighting"]')
  await expect(field.locator('.preset-icon').first()).toBeVisible()                      // the project's library is seeded with the built-ins
  await field.locator('button.lib-add').click()
  const dialog = page.locator('.modal.ask')
  await dialog.locator('input').fill(words)
  await dialog.locator('button.primary').click()
  await expect(page.locator('.inspector textarea[aria-label="selected entry words"]')).toHaveValue(words)   // added and selected: the Inspector writes it
  await page.locator('.inspector input[aria-label="selected entry name"]').fill(name)
  type Entry = { id: string; field: string; name: string; text: string }
  await expect.poll(async () => (await api<{ entries: Entry[] }>('GET', '/story/library')).entries.find((e) => e.text === words)?.name, { timeout: 10_000 }).toBe(name)
  // its picture is made by itself (one small job on the sample model, run now) and lands on the tile
  type SwatchJob = { status: string; origin: { surface: string; payload: { field?: string; value?: string } | null } | null }
  await expect.poll(async () => (await api<{ items: SwatchJob[] }>('GET', '/jobs')).items.some((j) => j.origin?.surface === 'swatch' && j.origin.payload?.value === words), { timeout: 10_000 }).toBe(true)
  await expect(field.locator(`button[aria-label="${name}"] img`)).toBeVisible({ timeout: 45_000 })
  expect(await page.locator('.preset-icon .tile').evaluateAll((ts) => ts.filter((t) => !t.querySelector('svg, img')).length)).toBe(0)   // D92: a glyph or a picture, never letters
  // Generate: the tile in the Look section's lighting row; a click puts the words in the field
  await openImage(page, 'Make')
  await page.locator('nav.rail button[title^="Prompt"]').click()
  await page.locator('.segmented button', { hasText: /^Tree$/ }).click()
  await page.locator('nav.rail button[title^="Look"]').click()
  const row = page.locator('#gen-sec-look .field', { has: page.locator('[aria-label="lighting presets"]') })
  const tile = row.locator(`[aria-label="lighting presets"] button[aria-label="${name}"]`)
  await expect(tile.locator('img')).toBeVisible()
  await tile.click()
  await expect(row.locator('input[type=text]').first()).toHaveValue(new RegExp(words.replace(/[.*+?^${}()|[\]-]/g, '\\$&')))
  await expect(tile).toHaveAttribute('aria-pressed', 'true')
  // the field's + adds the field's words as a new entry; the tile's right-click opens it in Story · World
  await contextChoose(page, tile, 'Edit in Story · World')
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Story/)
  await expect(page.locator('.inspector input[aria-label="selected entry name"]')).toHaveValue(name)
})

test('a subject is a Cast character (D92 · UI7): the subject card picks a profile by its hero, shows its sheet (D93 B4: no copy), and the job carries its references through the profile mention', async ({ page }) => {
  test.setTimeout(90_000)
  const name = `Ines ${Date.now().toString(36)}`
  const src = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0]
  const hero = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [src.id] })).ids[0]            // a copy: no other scenario's image moves
  type ProfileLite = { id: string; name: string; current: string; versions: { id: string; group_id: string }[] }
  const prof = await api<ProfileLite>('POST', '/story/profiles', { name, cls: 'character', hero_asset_id: hero, appearance: `${name}, a lighthouse keeper in a yellow oilskin` })
  await openApp(page, { suite: 'generate', tab: 'model' })
  await page.locator('.model-card').filter({ has: page.locator('span', { hasText: /^Klein 4B$/ }) }).click()   // takes references
  await page.locator('nav.rail button[title^="Prompt"]').click()
  await page.locator('.segmented button', { hasText: /^Tree$/ }).click()
  await page.locator('.gen-tree .full button', { hasText: 'subject' }).click()
  const card = page.locator('.gen-tree .subject').last()
  const pick = card.locator(`[aria-label^="subject"][aria-label$="from the Cast"] button[aria-label="${name}"]`)
  await expect(pick.locator('img')).toBeVisible()                                         // the profile by its hero image
  await pick.click()
  await expect(card.locator('.subject-sheet')).toContainText(`${name}, a lighthouse keeper in a yellow oilskin`)   // D93 (B4): the sheet, read from Cast
  await expect(card.locator('textarea')).toHaveCount(0)                                   // … not copied into a description to edit
  await expect(card.locator('.linked-to')).toContainText(name)
  await expect(page.locator('.mention-chips .mchip', { hasText: name })).toBeVisible()  // the profile mention, recorded by the link
  await expect(page.locator('.ref-from-mentions .ref-slot').first()).toBeVisible({ timeout: 20_000 })
  const go = page.locator('.panel .foot button.primary', { hasText: /^Generate/ })
  await expect(go).toBeEnabled({ timeout: 30_000 })
  await go.click()
  type JobLite = { status: string; recipe: { refs?: { asset_id: string; mention?: string | null }[]; mentions?: { profile_id?: string | null; subject?: number | null; group_id: string; asset_ids: string[] }[] } }
  const mine = async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.recipe.mentions?.some((m) => m.profile_id === prof.id))
  await expect.poll(async () => (await mine())?.status, { timeout: 45_000 }).toBe('done')
  const job = (await mine())!
  const m = job.recipe.mentions!.find((x) => x.profile_id === prof.id)!
  expect(m.subject).toBe(0)
  expect(m.group_id).toBe(prof.versions[0].group_id)
  expect(m.asset_ids).toContain(hero)
  expect(job.recipe.refs?.some((r) => r.asset_id === hero && r.mention === m.group_id)).toBe(true)   // the hero rides as a reference
  await card.locator('button[aria-label="unlink subject 1"]').click()
  await expect(page.locator('.mention-chips .mchip', { hasText: name })).toHaveCount(0)
})

test('Cast from Generate (D93 · A1, A2): a character without a look gets candidates from Generate, and one becomes its hero via Add to character ▸', async ({ page }) => {
  test.setTimeout(120_000)
  const name = `Noor ${Date.now().toString(36)}`
  type Version = { id: string; state: string; group_id: string; candidates_group_id: string | null; hero_asset_id: string | null; appearance: string }
  type ProfileLite = { id: string; name: string; current: string; versions: Version[] }
  const prof = await api<ProfileLite>('POST', '/story/profiles', { name, cls: 'character' })              // no hero, no references
  expect(prof.versions[0].appearance).toBe('')                                                            // A9: the sheet starts empty
  await openApp(page, { suite: 'generate', tab: 'model' })
  await page.locator('.model-card').filter({ has: page.locator('span', { hasText: /^Klein 4B$/ }) }).click()
  await page.locator('nav.rail button[title^="Prompt"]').click()
  await page.locator('.segmented button', { hasText: /^Tree$/ }).click()
  await page.locator('.gen-tree .full button', { hasText: 'subject' }).click()
  const card = page.locator('.gen-tree .subject').last()
  await card.locator(`[aria-label^="subject"][aria-label$="from the Cast"] button[aria-label="${name}"]`).click()
  await expect(card.locator('.subject-sheet .sheet-empty')).toBeVisible()                                 // an empty sheet: the name alone …
  await expect(card.locator('.subject-warn')).toHaveText('the model only sees the name — describe the look in Cast')   // … and the card says so
  const cast = card.locator('button.subject-cast')
  await expect(cast).toHaveText(new RegExp(`Give ${name} a look`))
  await cast.click()                                                                                       // the run asks for the look first
  await expect(card.locator('.subject-warn.ask')).toContainText(`describe ${name}'s look in Story · Cast first`)
  await expect(card.locator('.subject-sheet')).toBeFocused()
  // D93 (B4): the look is written in Cast — the sheet's "edit in Cast" opens the version with the appearance focused
  await card.locator('.subject-sheet button', { hasText: 'edit in Cast' }).click()
  await expect(page.locator('.cast-page h2')).toContainText(name)
  await expect(page.locator('#cast-appearance')).toBeFocused()
  await page.locator('#cast-appearance').fill(`${name}, a red-haired diver in a yellow wetsuit`)
  await expect.poll(async () => (await api<ProfileLite>('GET', `/story/profiles/${prof.id}`)).versions[0].appearance).toBe(`${name}, a red-haired diver in a yellow wetsuit`)
  await openImage(page, 'Make')
  await expect(card.locator('.subject-sheet')).toContainText('a red-haired diver in a yellow wetsuit')   // the card follows Cast
  await expect(card.locator('.subject-warn')).toHaveCount(0)
  await expect(page.locator('.panel .foot button.primary', { hasText: /^Generate/ })).toBeEnabled({ timeout: 30_000 })
  await cast.click()
  const toast = page.locator('.toast', { hasText: `as ${name}'s candidates` })
  await expect(toast).toBeVisible()
  type JobLite = { id: string; status: string; origin?: { surface: string; ref?: string | null; payload?: { group_id?: string } }; result?: { asset_ids?: string[] } }
  const mine = async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.filter((j) => j.origin?.surface === 'cast' && j.origin.ref === prof.id)
  await expect.poll(async () => { const js = await mine(); return js.length > 0 && js.every((j) => j.status === 'done') }, { timeout: 60_000 }).toBe(true)
  const p1 = await api<ProfileLite>('GET', `/story/profiles/${prof.id}`)
  const cand = p1.versions[0].candidates_group_id!
  const made = (await mine()).flatMap((j) => j.result?.asset_ids ?? [])
  expect((await mine()).every((j) => j.origin?.payload?.group_id === cand)).toBe(true)
  await expect.poll(async () => Object.keys((await api<{ assets: Record<string, unknown> }>('GET', `/groups/${cand}`)).assets).sort().join()).toBe([...made].sort().join())   // all on the candidates page
  // Add to character ▸ on a result tile: the profile it was made for first, "as the hero"
  const tile = page.locator(`.cat-grid .tile[data-id="${made[0]}"]`)
  await expect(tile).toBeVisible({ timeout: 20_000 })
  await tile.click({ button: 'right' })
  await page.locator('.ctx-menu .item.sub', { hasText: 'Add to character' }).hover()
  await expect(page.locator('.ctx-menu .heading', { hasText: 'made for' })).toBeVisible()
  await page.locator('.ctx-menu .ctx-menu > .item.sub', { hasText: `${name} · v1` }).first().hover()    // the profile's own submenu (not its parent's row)
  await page.locator('.ctx-menu .ctx-menu .ctx-menu button.item', { hasText: 'as the hero' }).click()
  await expect(page.locator('.toast', { hasText: `is ${name}'s hero` })).toBeVisible()
  await expect.poll(async () => (await api<ProfileLite>('GET', `/story/profiles/${prof.id}`)).versions[0].hero_asset_id).toBe(made[0])
  const ref = (await api<{ group: { cover_id: string | null; items: { id: string }[] } }>('GET', `/groups/${p1.versions[0].group_id}`)).group
  expect(ref.cover_id).toBe(made[0])                                                                       // moved from the candidates onto the reference set
  expect(ref.items.map((i) => i.id)).toContain(made[0])
  await expect(cast).toHaveText(new RegExp(`More looks for ${name}`), { timeout: 20_000 })                // the card follows: it has a look now
  await expect(card.locator('.subject-slots')).toHaveText(/^ref 1$/)                                      // its hero is reference image 1 in the prompt
  // the toast's way to Cast: the candidates are there
  await page.locator('.toast button', { hasText: `Open ${name} in Cast` }).first().click()
  await expect(page.locator('.cast-page h2')).toContainText(name)
  await expect(page.locator('.cand-card')).toHaveCount(made.length - 1)
})

test('a live character sheet (D93 · B4, B5): an outfit edited in Cast shows on the linked subject and rides the job; the version chip switches the job to that version\'s references', async ({ page }) => {
  test.setTimeout(120_000)
  const name = `Ida ${Date.now().toString(36)}`
  const src = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0]
  const hero = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [src.id] })).ids[0]            // a copy: no other scenario's image moves
  type Version = { id: string; label: string; group_id: string; hero_asset_id: string | null; outfit: string; colours: { hex: string; object: string }[] }
  type ProfileLite = { id: string; name: string; current: string; revision: number; versions: Version[] }
  const p1 = await api<ProfileLite>('POST', '/story/profiles', { name, cls: 'character', hero_asset_id: hero, appearance: `${name}, a tall woman with silver hair`, outfit: 'a grey wool coat', label: 'rain gear' })
  const p2 = await api<ProfileLite>('POST', `/story/profiles/${p1.id}/versions`)                              // v2: a copy (its references duplicated), current
  await api('PATCH', `/story/profiles/${p1.id}`, { revision: p2.revision, versions: [{ id: 'v2', label: 'winter' }] })
  const [v1, v2] = p2.versions
  // Cast: v2's outfit and a bound colour, typed on the version page (saved after a pause)
  await openApp(page, { suite: 'story', tab: 'cast' })
  await page.locator(`.profile-row[data-id="${p1.id}"]`).click()
  await expect(page.locator('.cast-page h2')).toContainText('v2 · winter')
  await page.locator('#cast-outfit').fill('a yellow oilskin')
  await page.locator('.cast-sheet button', { hasText: 'colour' }).click()
  await page.locator('.cast-sheet input[aria-label="colour 1: what it colours"]').fill('oilskin')
  await expect(page.locator('.cast-sheet .sheet-sent')).toContainText('wearing a yellow oilskin, #C0392B oilskin')
  await expect.poll(async () => { const v = (await api<ProfileLite>('GET', `/story/profiles/${p1.id}`)).versions[1]; return `${v.outfit}|${v.colours.map((c) => `${c.hex} ${c.object}`).join()}` }).toBe('a yellow oilskin|#C0392B oilskin')
  await page.screenshot({ path: 'node_modules/.e2e/d93b-smoke-cast.png' })
  // Generate: the subject linked to the character shows the edited sheet, the chip says the version
  await openImage(page, 'Make')
  await page.locator('nav.rail button[title^="Model"]').click()
  await page.locator('.model-card').filter({ has: page.locator('span', { hasText: /^Klein 4B$/ }) }).click()   // takes references
  await page.locator('nav.rail button[title^="Prompt"]').click()
  await page.locator('.segmented button', { hasText: /^Tree$/ }).click()
  await page.locator('.gen-tree .full button', { hasText: 'subject' }).click()
  const card = page.locator('.gen-tree .subject').last()
  await card.locator(`[aria-label^="subject"][aria-label$="from the Cast"] button[aria-label="${name}"]`).click()
  await expect(card.locator('.subject-sheet')).toContainText('a yellow oilskin')
  await expect(card.locator('.version-chip')).toHaveText(/v2 · winter/)
  await card.locator('input[aria-label$="this shot only"]').fill('soaked, hood up')
  await page.locator('#gen-sec-preview summary').click()
  await expect(page.locator('.preview-composed')).toContainText(`${name}, a tall woman with silver hair, wearing a yellow oilskin, #C0392B oilskin, soaked, hood up`)   // T8: as sent
  await expect(page.locator('.preview-box')).toContainText('wearing a yellow oilskin, #C0392B oilskin, soaked, hood up')
  const go = page.locator('.panel .foot button.primary', { hasText: /^Generate/ })
  type JobLite = { id: string; status: string; recipe: { prompt_json?: { subjects?: { description?: string }[] }; refs?: { asset_id: string; mention?: string | null }[]; mentions?: { profile_id?: string | null; version?: string | null; group_id: string; asset_ids: string[]; composed?: string | null }[] } }
  const jobsFor = async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.filter((j) => j.recipe.mentions?.some((m) => m.profile_id === p1.id))
  await expect(go).toBeEnabled({ timeout: 30_000 })
  await go.click()
  await expect.poll(async () => { const js = await jobsFor(); return js.length > 0 && js.every((j) => j.status === 'done') }, { timeout: 60_000 }).toBe(true)
  const first = (await jobsFor())[0]
  const m1 = first.recipe.mentions!.find((m) => m.profile_id === p1.id)!
  expect(first.recipe.prompt_json?.subjects?.[0].description).toContain('wearing a yellow oilskin, #C0392B oilskin, soaked, hood up')   // the job's prompt carries the Cast edit
  expect(m1.version).toBe('v2')
  expect(m1.group_id).toBe(v2.group_id)
  expect(m1.composed).toBe(first.recipe.prompt_json?.subjects?.[0].description)
  // the version chip: v1 (rain gear) — its sheet on the card, and the next job takes v1's references
  await card.locator('.version-chip').click()
  await page.locator('.ctx-menu button.item', { hasText: 'v1 · rain gear' }).click()
  await expect(card.locator('.version-chip')).toHaveText(/v1 · rain gear/)
  await expect(card.locator('.subject-sheet')).toContainText('a grey wool coat')
  await expect(page.locator('.preview-composed')).toContainText('wearing a grey wool coat, soaked, hood up')
  await page.screenshot({ path: 'node_modules/.e2e/d93b-smoke-generate.png' })
  const before = new Set((await jobsFor()).map((j) => j.id))
  await expect(go).toBeEnabled({ timeout: 30_000 })
  await go.click()
  await expect.poll(async () => { const js = (await jobsFor()).filter((j) => !before.has(j.id)); return js.length > 0 && js.every((j) => j.status === 'done') }, { timeout: 60_000 }).toBe(true)
  const second = (await jobsFor()).find((j) => !before.has(j.id))!
  const m2 = second.recipe.mentions!.find((m) => m.profile_id === p1.id)!
  expect(m2.version).toBe('v1')
  expect(m2.group_id).toBe(v1.group_id)
  expect(m2.asset_ids).toContain(hero)                                                                      // v1's own hero, not v2's copy
  expect(second.recipe.refs?.filter((r) => r.mention === v1.group_id).map((r) => r.asset_id)).toContain(hero)
  expect(second.recipe.refs?.some((r) => r.mention === v2.group_id)).toBe(false)
  expect(second.recipe.prompt_json?.subjects?.[0].description).toContain('wearing a grey wool coat')
})

test('a subject per speaker, a place, a prop (D93 · C6, C7): the Flow Inspector sets where a Dialogue node happens; Make frame ▸ gives Generate one linked card per speaker and the place as the scene; holds ▸ gives a card a prop; the job\'s prompt carries all three', async ({ page }) => {
  test.setTimeout(150_000)
  const tag = Date.now().toString(36)
  const src = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0]
  const copies = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [src.id, src.id, src.id, src.id] })).ids   // copies: no other scenario's image moves
  type ProfileLite = { id: string; name: string; versions: { id: string; group_id: string }[] }
  const mk = (name: string, cls: string, hero: string, appearance: string) => api<ProfileLite>('POST', '/story/profiles', { name, cls, hero_asset_id: hero, appearance })
  const mara = await mk(`Mara ${tag}`, 'character', copies[0], `Mara ${tag}, a wiry courier`)
  const joe = await mk(`Joe ${tag}`, 'character', copies[1], 'a tall fisherman with a grey beard')
  const quay = await mk(`Quay ${tag}`, 'place', copies[2], 'a stone quay at dusk, fishing boats')
  const key = await mk(`Key ${tag}`, 'prop', copies[3], 'a brass key on a red ribbon')
  const node = await api<{ id: string }>('POST', '/story/flow/nodes', { type: 'dialogue', title: `At the gate ${tag}`, x: 2400, y: 1600 })
  await api('POST', `/story/flow/nodes/${node.id}/shot`, { name: `Gate ${tag}` })
  type NodeLite = { id: string; revision: number; place_id: string | null }
  const nodeOf = async () => (await api<{ nodes: NodeLite[] }>('GET', '/story/flow')).nodes.find((n) => n.id === node.id)!
  await api('PATCH', `/story/flow/nodes/${node.id}`, { revision: (await nodeOf()).revision, lines: [{ speaker: mara.id, text: '"We go at dawn."' }, { speaker: joe.id, text: 'Not without the key.' }, { speaker: mara.id, text: 'Then find it.' }] })
  await openApp(page, { suite: 'generate', tab: 'model' })
  await page.locator('.model-card').filter({ has: page.locator('span', { hasText: /^Klein 4B$/ }) }).click()   // takes references
  // Story · Flow: the node's Inspector — where (a Cast place), then Make frame in Generate
  await openApp(page, { suite: 'story', tab: 'flow' })
  type Hook = { loadFlow: () => Promise<void>; selectNode: (id: string | null) => void }
  await page.evaluate(async (id) => { const h = (window as unknown as { __loom2Story: Hook }).__loom2Story; await h.loadFlow(); h.selectNode(id) }, node.id)
  await page.locator('.inspector select[aria-label="where (a Cast place)"]').selectOption(quay.id)
  await expect.poll(async () => (await nodeOf()).place_id).toBe(quay.id)
  await expect(page.locator(`.flow-node[data-id="${node.id}"] .place`)).toHaveText(`@ ${quay.name}`)
  await page.locator('.inspector button', { hasText: 'Make frame in Image' }).click()
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Image/)
  await expect(page.locator('#gen-sec-prompt .segmented button.active')).toHaveText('Tree')
  const cards = page.locator('.gen-tree .subject.linked')
  await expect(cards).toHaveCount(2)
  await expect(cards.nth(0).locator('.linked-to')).toContainText(mara.name)
  await expect(cards.nth(1).locator('.linked-to')).toContainText(joe.name)
  await expect(cards.nth(0).locator('input[type=text]').nth(3)).toHaveValue('saying We go at dawn')           // the first line: its speaker's action (no quote marks)
  await expect(page.locator('.scene-linked .linked-to')).toContainText(quay.name)
  await expect(page.locator('.scene-linked .subject-sheet')).toContainText('a stone quay at dusk')
  // holds ▸ on Joe's card: the Cast's props
  await cards.nth(1).locator('.holds-btn').click()
  await page.locator('.ctx-menu button.item', { hasText: key.name }).click()
  await expect(cards.nth(1).locator('.holds-chip')).toContainText(`holds ${key.name}`)
  await page.locator('#gen-sec-preview summary').click()
  await expect(page.locator('.preview-composed')).toContainText(`the scene · ${quay.name}: a stone quay at dusk, fishing boats`)
  await expect(page.locator('.preview-composed')).toContainText(`subject 2 holds · ${key.name}: holding a brass key on a red ribbon`)
  await expect(page.locator('.preview-box')).toContainText(`${quay.name} (reference image 4), a stone quay at dusk`)   // T8: the place's range leads the scene
  const go = page.locator('.panel .foot button.primary', { hasText: /^Generate/ })
  await expect(go).toBeEnabled({ timeout: 30_000 })
  await go.click()
  type JobLite = { status: string; result: { serialized_prompt?: string } | null; recipe: { prompt_json?: { scene?: string; subjects?: { description?: string; action?: string; holding?: string }[] }; mentions?: { profile_id?: string | null; subject?: number | null; held_by?: number | null; scene?: boolean; composed?: string | null }[] } }
  const mine = async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.filter((j) => j.recipe.mentions?.some((m) => m.profile_id === quay.id))
  await expect.poll(async () => { const js = await mine(); return js.length > 0 && js.every((j) => j.status === 'done') }, { timeout: 60_000 }).toBe(true)
  const job = (await mine())[0]
  const ms = job.recipe.mentions!
  expect(ms.find((m) => m.profile_id === mara.id)?.subject).toBe(0)
  expect(ms.find((m) => m.profile_id === joe.id)?.subject).toBe(1)
  expect(ms.find((m) => m.profile_id === key.id)?.held_by).toBe(1)
  expect(ms.find((m) => m.profile_id === quay.id)).toMatchObject({ scene: true, composed: 'a stone quay at dusk, fishing boats' })
  expect(job.recipe.prompt_json?.scene).toBe('a stone quay at dusk, fishing boats')
  expect(job.recipe.prompt_json?.subjects?.[1]).toMatchObject({ description: 'a tall fisherman with a grey beard', holding: 'a brass key on a red ribbon' })
  expect(job.result?.serialized_prompt).toContain(`Joe ${tag} (reference image 2), a tall fisherman with a grey beard, holding Key ${tag} (reference image 3), a brass key on a red ribbon`)
  expect(job.result?.serialized_prompt).toContain(`scene: Quay ${tag} (reference image 4), a stone quay at dusk, fishing boats`)
})

test('figures bound to characters (D93 · C8): a figure picks a character in the Inspector or by right-click, the Outliner says who, the Render tab\'s deck shows each figure\'s slot, and the frame\'s job carries their references and sheets left to right', async ({ page }) => {
  test.setTimeout(150_000)
  const tag = Date.now().toString(36)
  const src = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0]
  const copies = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [src.id, src.id] })).ids
  type ProfileLite = { id: string; name: string; versions: { id: string; group_id: string }[] }
  const ana = await api<ProfileLite>('POST', '/story/profiles', { name: `Ana ${tag}`, cls: 'character', hero_asset_id: copies[0], appearance: 'a short woman in a red raincoat' })
  const bo = await api<ProfileLite>('POST', '/story/profiles', { name: `Bo ${tag}`, cls: 'character', hero_asset_id: copies[1], appearance: 'a lanky boy with a green cap' })
  type StageLite = { id: string; revision: number; objects: { id: string; name: string; profile_id: string | null }[] }
  const st0 = await api<StageLite>('POST', '/stages', { name: `Figures ${tag}` })
  const figure = (id: string, name: string, x: number) => ({ id, kind: 'mannequin', name, preset: 'adult', transform: { pos: [x, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] }, pose: { preset: 'stand', joints: {} }, colour_id: 1 })
  await api('PUT', `/stages/${st0.id}`, { ...st0, objects: [figure('fig_r', 'Right one', 1.2), figure('fig_l', 'Left one', -1.2)],
    cameras: [{ id: 'cam_1', name: 'Camera 1', pos: [0, 1.5, 5], target: [0, 1, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }], active_camera: 'cam_1' })
  await openApp(page, { suite: 'stage' })
  type StageHook = { open: (id: string) => Promise<void> }
  await expect.poll(async () => page.evaluate(() => !!(window as unknown as { __loom2Stage?: StageHook }).__loom2Stage), { timeout: 30_000 }).toBe(true)
  await page.evaluate(async (id) => { await (window as unknown as { __loom2Stage: StageHook }).__loom2Stage.open(id) }, st0.id)
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await openSection(page, 'Scene')
  // the left figure: the Inspector's tiles (the Cast's characters by their heroes)
  await page.locator('.outl-row', { hasText: 'Left one' }).click()
  const tile = page.locator(`.panel [aria-label="the figure's character"] button[aria-label="${ana.name}"]`)   // D95 (AN1): the Selection section
  await expect(tile.locator('img')).toBeVisible()
  await tile.click()
  await expect(page.locator('.outl-row', { hasText: 'Left one' }).locator('.bound-tag')).toContainText(ana.name)
  // the right figure: right-click ▸ Bind to a character ▸ Bo
  await page.locator('.outl-row', { hasText: 'Right one' }).click({ button: 'right' })
  await page.locator('.ctx-menu .item.sub', { hasText: 'Bind to a character' }).hover()
  await page.locator('.ctx-menu button.item', { hasText: bo.name }).click()
  await expect(page.locator('.outl-row', { hasText: 'Right one' }).locator('.bound-tag')).toContainText(bo.name)
  await expect.poll(async () => (await api<StageLite>('GET', `/stages/${st0.id}`)).objects.map((o) => [o.id, o.profile_id]), { timeout: 10_000 }).toEqual([['fig_r', bo.id], ['fig_l', ana.id]])
  // the Render tab: the deck's figure slots (image 2 the left figure's, image 3 the right's) and the lines
  await stageRoute(page)
  await expect(page.locator('.shot-tab .figure-slot')).toHaveCount(2, { timeout: 20_000 })
  await expect(page.locator('.shot-tab .figure-slot').nth(0).locator('.fig-badge')).toHaveText(`fig 1 · ${ana.name}`)
  await expect(page.locator('.shot-tab .figure-lines')).toContainText(`figure 1 · ${ana.name} → image 2`)
  await expect(page.locator('.shot-tab .prompt-preview')).toContainText(`figure 1 is ${ana.name} (reference image 2), a short woman in a red raincoat; figure 2 is ${bo.name} (reference image 3)`)
  await page.locator('.shot-tab button', { hasText: /^Render passes$/ }).click()
  const go = page.locator('.panel .foot button.primary', { hasText: /^Render frame/ })
  await expect(go).toBeEnabled({ timeout: 30_000 })
  await go.click()
  type JobLite = { status: string; result: { serialized_prompt?: string } | null; recipe: { kind: string; stage_id?: string; refs?: { asset_id: string; mention?: string | null }[]; mentions?: { figure?: string | null; profile_id?: string | null; asset_ids: string[] }[] } }
  const mine = async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.filter((j) => j.recipe.kind === 'stage_shot' && j.recipe.stage_id === st0.id)
  await expect.poll(async () => { const js = await mine(); return js.length > 0 && js.every((j) => j.status === 'done') }, { timeout: 60_000 }).toBe(true)
  const job = (await mine())[0]
  expect(job.recipe.mentions?.map((m) => [m.figure, m.profile_id])).toEqual([['fig_l', ana.id], ['fig_r', bo.id]])   // left to right, not the document's order
  expect(job.recipe.refs?.map((r) => r.asset_id)).toEqual([copies[0], copies[1]])
  expect(job.result?.serialized_prompt).toContain(`From left to right in image 1: figure 1 is ${ana.name} (reference image 2), a short woman in a red raincoat; figure 2 is ${bo.name} (reference image 3), a lanky boy with a green cap.`)
})

test('Flatten image (D90 · UI6): the canvas menu\'s Layer ▸ folds a group, a blend mode and an adjustment into one layer, exactly as the server flattens; Undo brings the layers back; Save (D95: the document and a Catalogue version) still matches', async ({ page }) => {
  type Ed = { getState: () => { doc: { id: string; layers: { id: string; name: string; kind: string }[] } | null; addLayer: (k: string, extra?: Record<string, unknown>) => unknown; updateNode: (id: string, p: Record<string, unknown>) => void; groupNodes: (ids: string[]) => void; duplicateNodes: (ids: string[]) => void; undo: () => void; save: () => Promise<boolean>; docDirty: boolean } }
  const ed = () => page.evaluate(() => { const s = (window as unknown as { __loom2Editor: Ed }).__loom2Editor.getState(); return { layers: s.doc!.layers.map((n) => ({ id: n.id, name: n.name, kind: n.kind })), dirty: s.docDirty } })
  const raw = async (docId: string): Promise<Buffer> => {
    const e = env()
    const r = await fetch(`http://127.0.0.1:${e.port}/documents/${docId}/export`, { method: 'POST', headers: { 'X-Loom-Token': e.token, 'Content-Type': 'application/json' }, body: JSON.stringify({ format: 'raw' }) })
    expect(r.status).toBe(200)
    return Buffer.from(await r.arrayBuffer())
  }
  await openApp(page, { suite: 'catalogue', renderer: 'webgl' })
  await contextChoose(page, tiles(page).nth(7), 'Open in Edit')
  const docId = await page.waitForFunction(() => (window as unknown as { __loom2Editor: Ed }).__loom2Editor.getState().doc?.id ?? null).then((h) => h.jsonValue() as Promise<string>)
  // arrange (dev hook): a copy of the photo in a group at screen, an invert adjustment on top at 40 %
  await page.evaluate(() => {
    const s = (window as unknown as { __loom2Editor: Ed }).__loom2Editor.getState()
    s.duplicateNodes([s.doc!.layers[0].id])
    const wash = (window as unknown as { __loom2Editor: Ed }).__loom2Editor.getState().doc!.layers[0]
    s.updateNode(wash.id, { blend: 'screen', opacity: 0.6 })
    s.groupNodes([wash.id])
    s.addLayer('adjustment', { type: 'invert', params: {}, opacity: 0.4 })
  })
  expect((await ed()).layers.map((n) => n.kind)).toEqual(['adjustment', 'group', 'raster'])
  const bottom = (await ed()).layers[2].name
  await page.evaluate(() => (window as unknown as { __loom2Editor: Ed }).__loom2Editor.getState().save())
  const before = await raw(docId)
  // the action: right-click the canvas → Layer ▸ → Flatten image
  const canvas = page.locator('.edit-canvas canvas')
  await canvas.click({ button: 'right', position: { x: 40, y: 40 } })
  await page.locator('.ctx-menu .item.sub', { hasText: /^Layer/ }).hover()
  const flat = page.locator('.ctx-menu .ctx-menu button.item', { hasText: 'Flatten image' })
  await expect(flat).toBeEnabled()
  await flat.click()
  await expect(page.locator('.toast', { hasText: /^Flattened 4 layers into/ })).toBeVisible()
  await expect.poll(async () => (await ed()).layers.length).toBe(1)
  const after = await ed()
  expect(after.layers[0]).toMatchObject({ kind: 'raster', name: bottom })
  expect(after.dirty).toBe(true)
  await expect(page.locator('.layer-row')).toHaveCount(1)
  await page.evaluate(() => (window as unknown as { __loom2Editor: Ed }).__loom2Editor.getState().save())
  expect((await api<{ layers: unknown[] }>('GET', `/documents/${docId}`)).layers).toHaveLength(1)
  expect((await raw(docId)).equals(before)).toBe(true)                                                 // the one layer renders what the stack rendered
  // Save after the flatten (D95: one Save writes the document and a Catalogue version): a new asset from the same pixels
  const last = async () => (await api<{ meta: { last_flatten_asset?: string } }>('GET', `/documents/${docId}`)).meta.last_flatten_asset ?? null
  const a0 = await last()
  await page.locator('.edit-canvas canvas').click({ button: 'right', position: { x: 40, y: 40 } })
  await page.locator('.ctx-menu .item.sub', { hasText: /^Document/ }).hover()
  await page.locator('.ctx-menu .ctx-menu button.item', { has: page.locator('.lbl', { hasText: /^Save$/ }) }).click()
  await expect(page.locator('.toast', { hasText: /^Saved · a new version in the Catalogue/ })).toBeVisible()
  await expect.poll(last).not.toBe(a0)
  expect((await api<{ params: { layers: number } }>('GET', `/assets/${await last()}`)).params.layers).toBe(1)                // flattened from the one-layer document
  // Undo (the layers footer's More ▾ has it too): the three layers again
  await page.evaluate(() => (window as unknown as { __loom2Editor: Ed }).__loom2Editor.getState().undo())
  expect((await ed()).layers.map((n) => n.kind)).toEqual(['adjustment', 'group', 'raster'])
  await page.evaluate(() => (window as unknown as { __loom2Editor: Ed }).__loom2Editor.getState().save())
  expect((await raw(docId)).equals(before)).toBe(true)
  // the layers footer's More ▾ lists it as well
  // a click (press + release in place) opens it and chooses nothing, although this tall menu is placed over its button (the fix in
  // ContextMenu.tsx: before, the release chose the entry under the pointer — Solo)
  await page.getByRole('button', { name: 'More', exact: true }).click()
  await expect(page.locator('.ctx-menu button.item', { hasText: 'Flatten image' })).toBeEnabled()
  expect((await ed()).layers.map((n) => n.kind)).toEqual(['adjustment', 'group', 'raster'])
  expect(await page.evaluate(() => (window as unknown as { __loom2Editor: { getState: () => { history: { label: string }[] } } }).__loom2Editor.getState().history.at(-1)?.label)).not.toMatch(/solo|visib/i)
  await page.keyboard.press('Escape')
})

test('a group\'s "used by" (D92 §4.2): a Cast version\'s reference set says so on its page and in the card\'s Inspector, the link opens Cast, and Delete group… warns', async ({ page }) => {
  const name = `Ines ${Date.now().toString(36)}`
  type ProfileLite = { id: string; versions: { id: string; group_id: string }[] }
  const prof = await api<ProfileLite>('POST', '/story/profiles', { name, cls: 'character' })
  const gid = prof.versions[0].group_id
  const users = await api<Record<string, { kind: string; name: string; extra: string }[]>>('GET', `/groups/used-by?ids=${gid}`)
  expect(users[gid]).toEqual([expect.objectContaining({ kind: 'profile_ref', name, extra: 'v1' })])
  await openApp(page, { suite: 'catalogue' })
  const row = page.locator('.place-row', { hasText: name })
  await expect(row).toBeVisible()
  await row.locator('button.place-open').click()
  const line = page.locator('.page-head .used-by')                                                     // the page's header
  await expect(line).toContainText(`used by:${name} v1 · references`)
  // the card on the Album page: its Inspector says so too
  await page.locator('.place-open.album').click()
  const card = page.locator('.pcard', { hasText: name })
  await expect(card).toBeVisible()
  await card.click()
  const used = page.locator('.insp .used-by')
  await expect(used).toContainText(`${name} v1 · references`)
  // Delete group… warns (and Cancel keeps it)
  await card.click({ button: 'right' })
  await page.locator('.ctx-menu button.item', { hasText: 'Delete group…' }).click()
  const dialog = page.locator('.modal.ask')
  await expect(dialog).toContainText(`It is used by ${name} v1 · references`)
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
  expect((await api<{ group: { id: string } }>('GET', `/groups/${gid}`)).group.id).toBe(gid)
  // the link opens the user: Story · Cast at that version
  await used.locator('button.link', { hasText: `${name} v1 · references` }).click()
  await expect(page.locator('.cast-page h2')).toContainText(name)
})

test('the Bin (D95 · AN1, 04 C1): the Dock\'s Bin tab shows the Catalogue in Image and Animate; a double-click adds a reference in Make and sets the start frame in Animate', async ({ page }) => {
  await openApp(page, { suite: 'generate' })
  await expect(page.locator('.dock .dock-tabs')).toBeVisible()
  await page.locator('.dock .dock-tabs button', { hasText: 'Bin' }).click()
  const bin = page.locator('.dock .bin')
  await expect(bin).toBeVisible()
  await bin.locator('.bin-bar .segmented button', { hasText: 'Images' }).click()
  const tile = bin.locator('.bin-grid .tile').first()
  await expect(tile).toBeVisible()
  const id = (await tile.getAttribute('data-id'))!
  await tile.dblclick()                                                                                      // Make: a reference
  await expect(page.locator('.ref-slots .ref-slot img').first()).toHaveAttribute('src', new RegExp(id))
  await openAnimate(page, 'Performance')
  await expect(page.locator('.dock .bin')).toBeVisible()                                                    // the Bin stays open across Image and Animate
  await page.locator('.dock .bin .bin-grid .tile').nth(1).dblclick()                                        // Animate: the start frame
  await expect(page.locator('.slots .slot').first().locator('img')).toBeVisible()
  await openCatalogue(page)
  await expect(page.locator('.dock .dock-tabs')).toHaveCount(0)                                             // Story has the Catalogue itself
})

test('AN1 step 5 (D95): the Clay level adds an image plane from the Bin, renames it by right-click, shows the passes in Scene; Image · Make has From a stage', async ({ page }) => {
  await openApp(page, { suite: 'stage' })
  await page.locator('.placeholder button', { hasText: /^New stage/ }).click()
  const dialog = page.locator('.modal.ask')
  await dialog.locator('input').fill('Plane test')
  await dialog.locator('button.primary').click()
  await expect(page.locator('.stage-row.active')).toContainText('Plane test')
  await openSection(page, 'Scene')
  await expect(page.locator('.passes-row')).toContainText('No passes yet for')                              // #16: the passes at a glance
  await page.locator('.lib-grid button', { hasText: /^Add image plane/ }).click()                           // #18: opens the Bin
  const bin = page.locator('.dock .bin')
  await expect(bin).toBeVisible()
  await bin.locator('.bin-bar .segmented button', { hasText: 'Images' }).click()
  await bin.locator('.bin-grid .tile').first().dblclick()                                                    // the Clay level's verb: an image plane
  const row = page.locator('.outl-row', { has: page.locator('.kind', { hasText: 'plane' }) })
  await expect(row).toHaveCount(1)
  await row.click({ button: 'right' })
  await page.locator('.ctx-menu button.item', { hasText: /^Rename/ }).click()                                // D32: rename has a mouse placement
  await dialog.locator('input').fill('Backdrop')
  await dialog.locator('button.primary').click()
  await expect(row.locator('.name')).toHaveText('Backdrop')
  await openImage(page, 'Make')                                                                              // #5: stills from the stage in Image
  await page.locator('.gen-source .segmented button', { hasText: 'From a stage' }).click()
  await expect(page.locator('.from-stage select[aria-label="the stage"] option:checked')).toHaveText('Plane test')
  await expect(page.locator('.from-stage select[aria-label="the camera"]')).toBeVisible()
  await page.locator('.gen-source .segmented button', { hasText: 'Prompt' }).click()
  await expect(page.locator('.from-stage')).toHaveCount(0)
})

test('a body on the Cast sheet (CA0, 01 §9): height, build and an attachment saved with the sheet; a stage figure bound to the character takes the body when the stage opens', async ({ page }) => {
  const name = `Grak ${Date.now().toString(36)}`
  const src = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0]
  const hero = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [src.id] })).ids[0]
  type Body = { height_m: number; build: string; attachments: { kind: string }[] }
  type ProfileLite = { id: string; versions: { id: string; body: Body | null }[] }
  const p = await api<ProfileLite>('POST', '/story/profiles', { name, cls: 'character', hero_asset_id: hero, appearance: `${name}, a hulking ogre` })
  expect(p.versions[0].body).toBeNull()
  await openApp(page, { suite: 'story', tab: 'cast' })
  await page.locator(`.profile-row[data-id="${p.id}"]`).click()
  await page.locator('.cast-body button', { hasText: 'body' }).click()
  await page.locator('.cast-body input[aria-label="height in metres"]').fill('2.4')
  await page.locator('.cast-body .segmented button', { hasText: 'heavy' }).click()
  await page.locator('.cast-body button', { hasText: 'attachment' }).click()
  await page.locator('.cast-body select[aria-label="attachment 1"]').selectOption('horns')
  await expect(page.locator('svg.body-silhouette')).toHaveAttribute('aria-label', 'silhouette, 2.40 m')
  await expect.poll(async () => { const b = (await api<ProfileLite>('GET', `/story/profiles/${p.id}`)).versions[0].body; return b ? `${b.height_m}|${b.build}|${b.attachments.map((a) => a.kind).join()}` : null }).toBe('2.4|heavy|horns')
  // a stage with a figure bound to the character, no body yet: opening it in Animate · Clay gives the figure the sheet's body
  const st = await api<{ id: string } & Record<string, unknown>>('POST', '/stages', { name: `Cave ${name}` })
  const fig = { id: 'obj_grak', kind: 'mannequin', name: 'Grak', preset: 'adult', profile_id: p.id, version: null, body: null }
  await api('PUT', `/stages/${st.id}`, { ...st, objects: [fig] })
  await openAnimate(page, 'Clay')
  await page.locator('.stage-row', { hasText: `Cave ${name}` }).click()
  await expect.poll(async () => (await api<{ objects: { body: Body | null }[] }>('GET', `/stages/${st.id}`)).objects[0].body?.height_m ?? null, { timeout: 10_000 }).toBe(2.4)
  await openSection(page, 'Scene')
  await page.locator('.outl-row', { hasText: 'Grak' }).click()
  await expect(page.locator('#anim-sec-selection')).toContainText('from Cast — 2.40 m · heavy · horns')
  await page.locator('.stage-row', { hasText: `Cave ${name}` }).click()
  await page.waitForTimeout(500)
  await page.screenshot({ path: 'node_modules/.e2e/ca0-body-stage.png' })                  // a look for the journal: the ogre beside nothing, 2.4 m
})

test('an animation reference in Cast (CA0, 01 step 2): Make an animation reference queues two candidates, the first fills the front slot; a candidate\'s right-click makes it the back view', async ({ page }) => {
  test.setTimeout(90_000)
  const name = `Ines ${Date.now().toString(36)}`
  const src = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0]
  const hero = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [src.id] })).ids[0]
  type ProfileLite = { id: string; versions: { id: string; anim_ref_asset_id: string | null; anim_ref_back_asset_id: string | null }[] }
  const p = await api<ProfileLite>('POST', '/story/profiles', { name, cls: 'character', hero_asset_id: hero, appearance: `${name}, a dancer in a red dress` })
  await openApp(page, { suite: 'story', tab: 'cast' })
  await page.locator(`.profile-row[data-id="${p.id}"]`).click()
  await expect(page.locator('.anim-ref-slot[data-side="front"]')).toContainText('none yet')
  await page.locator('.anim-ref button', { hasText: /^Make an animation reference/ }).click()
  await expect.poll(async () => (await api<ProfileLite>('GET', `/story/profiles/${p.id}`)).versions[0].anim_ref_asset_id, { timeout: 60_000 }).toBeTruthy()
  const front = (await api<ProfileLite>('GET', `/story/profiles/${p.id}`)).versions[0].anim_ref_asset_id!
  await expect(page.locator('.anim-ref-slot[data-side="front"] img')).toHaveAttribute('src', new RegExp(front))
  await expect(page.locator('.story-cands .cand-card')).toHaveCount(2, { timeout: 30_000 })                         // both on the candidates page
  const other = page.locator(`.story-cands .cand-card:not([data-id="${front}"])`).first()
  const otherId = (await other.getAttribute('data-id'))!
  await other.click({ button: 'right' })
  await page.locator('.ctx-menu button.item', { hasText: /^Use as the back view/ }).click()
  await expect.poll(async () => (await api<ProfileLite>('GET', `/story/profiles/${p.id}`)).versions[0].anim_ref_back_asset_id).toBe(otherId)
  await expect(page.locator('.anim-ref-slot[data-side="back"] img')).toHaveAttribute('src', new RegExp(otherId))
})

test('the body fitted to the animation reference (CA1b, D104): Fit the body measures the reference and the proportions follow, the height stays', async ({ page }) => {
  test.setTimeout(90_000)
  const name = `Ines ${Date.now().toString(36)}`
  const src = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0]
  const ref = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [src.id] })).ids[0]
  type ProfileLite = { id: string; versions: { id: string; body_fit_from: string | null; body: { height_m: number; neck: number; shoulders: number } | null }[] }
  const p = await api<ProfileLite>('POST', '/story/profiles', { name, cls: 'character', appearance: `${name}, a mechanic` })
  await api('PUT', `/story/profiles/${p.id}/versions/v1/anim-ref`, { side: 'front', asset_id: ref })           // set by hand: no fit by itself
  await openApp(page, { suite: 'story', tab: 'cast' })
  await page.locator(`.profile-row[data-id="${p.id}"]`).click()
  await page.locator('.cast-body button', { hasText: /^Fit the body to the animation reference/ }).click()
  await expect.poll(async () => (await api<ProfileLite>('GET', `/story/profiles/${p.id}`)).versions[0].body_fit_from, { timeout: 60_000 }).toBe(ref)
  const body = (await api<ProfileLite>('GET', `/story/profiles/${p.id}`)).versions[0].body!
  expect(body.height_m).toBe(1.75)                                                                    // the author's: unchanged
  expect(body.neck).toBeGreaterThan(1.5)                                                              // the fake reference's long neck (0.16 of the height)
  await expect(page.locator('.cast-body')).toContainText('Proportions fitted to the animation reference')
  await expect(page.locator('.cast-body')).toContainText(`×${body.neck.toFixed(2)}`)                     // the neck slider shows the fitted factor
})

test('a test animation in Cast (CA0, 01 step 2): Test it draws a turn on the spot from the body here, the pose-driven model performs it with the reference, the clip lands beside the reference', async ({ page }) => {
  test.setTimeout(120_000)
  const name = `Bram ${Date.now().toString(36)}`
  const src = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0]
  const ref = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [src.id] })).ids[0]
  type ProfileLite = { id: string; revision: number; versions: { id: string; anim_test_clip_id: string | null }[] }
  const p = await api<ProfileLite>('POST', '/story/profiles', { name, cls: 'character', appearance: `${name}, an old captain` })
  await api('PATCH', `/story/profiles/${p.id}`, { revision: p.revision, versions: [{ id: 'v1', body: { height_m: 1.9, build: 'broad', head: 1, torso: 1, shoulders: 1, arms: 1, legs: 1, attachments: [] } }] })
  await api('PUT', `/story/profiles/${p.id}/versions/v1/anim-ref`, { side: 'front', asset_id: ref })
  await openApp(page, { suite: 'story', tab: 'cast' })
  await page.locator(`.profile-row[data-id="${p.id}"]`).click()
  await expect(page.locator('.anim-ref-slot[data-side="test"]')).toContainText('none yet')
  await page.locator('.anim-ref button', { hasText: /^Test it/ }).click()
  const dialog = page.locator('.modal.ask')
  await expect(dialog).toContainText(/a turn on the spot/i)
  await dialog.locator('button.primary').click()
  await expect.poll(async () => (await api<ProfileLite>('GET', `/story/profiles/${p.id}`)).versions[0].anim_test_clip_id, { timeout: 90_000 }).toBeTruthy()
  type JobLite = { recipe: { guide?: { asset_id: string; kind: string }; start_asset?: string; frames?: number }; origin: { surface: string } | null }
  const job = (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.origin?.surface === 'anim_test')!
  expect(job.recipe.start_asset).toBe(ref)
  type Guide = { kind: string; frames: number; params: { keypoints: number[][][][] } }
  const guide = await api<Guide>('GET', `/assets/${job.recipe.guide!.asset_id}`)
  expect(guide.kind).toBe('video')
  expect(guide.params.keypoints.length).toBe(guide.frames)
  expect(guide.params.keypoints.every((f) => f.length === 1)).toBe(true)                         // one figure in every frame
  await expect(page.locator('.anim-ref-slot[data-side="test"] img')).toBeVisible({ timeout: 15_000 })
})

test('the motion library (CA1, 01 step 5): the starter folder\'s clips listed in the Motion section, one previewed and applied to a figure at the playhead as keys with its root motion', async ({ page }) => {
  await openApp(page, { suite: 'stage' })
  await page.locator('.placeholder button', { hasText: /^New stage/ }).click()
  const dialog = page.locator('.modal.ask')
  await dialog.locator('input').fill('Motion test')
  await dialog.locator('button.primary').click()
  await expect(page.locator('.stage-row.active')).toContainText('Motion test')
  await page.locator('.lib-grid button', { hasText: /^Adult/ }).click()                       // a figure, selected
  await openSection(page, 'Motion')
  const lib = page.locator('.motion-lib')
  await lib.locator('.motion-file-head', { hasText: 'test_rig' }).click()                       // the e2e tree's starter folder holds the test rig
  await expect(lib.locator('.motion-clip')).toHaveCount(2)
  await lib.locator('.motion-clip', { hasText: 'Walk_RM' }).click()
  await expect(lib.locator('.motion-clip', { hasText: 'Walk_RM' })).toContainText('moves')
  await expect(lib.locator('.motion-preview')).toContainText('25 frames at 24 fps · unreal · 0.96 m')
  await lib.locator('label', { hasText: /^ ?foot lock/ }).locator('input').uncheck()               // the test rig's hips glide without stepping: the root motion as made
  await lib.locator('button', { hasText: /^Apply to Figure 1 at the playhead/ }).click()
  type Doc = { id: string; name: string; range: { end: number }; objects: { id: string; transform: { pos: number[] } }[]; keyframes: { objects: Record<string, { frame: number; transform: { pos: number[] }; pose: { joints: Record<string, number[]> } }[]> } }
  const doc = async () => (await api<{ items: Doc[] }>('GET', '/stages')).items.find((s) => s.name === 'Motion test')!
  await expect.poll(async () => Object.keys((await doc()).keyframes.objects ?? {}).length, { timeout: 10_000 }).toBe(1)
  const d = await doc()
  const keys = Object.values(d.keyframes.objects)[0]
  const base = d.objects[0].transform.pos
  expect(keys[0].frame).toBe(0)
  expect(keys[keys.length - 1].frame).toBe(24)
  expect(keys.length).toBeLessThan(25)                                                         // thinned
  expect(keys[keys.length - 1].transform.pos[2] - base[2]).toBeCloseTo(0.958, 2)               // 1 m of the rig's hips, scaled by the hip heights
  expect(Object.keys(keys[0].pose.joints)).toHaveLength(12)
  expect(d.range.end).toBeGreaterThanOrEqual(24)
  await page.screenshot({ path: 'node_modules/.e2e/ca1-motion-library.png' })
})

test('the Detailed level (CA1, 01 §9a): a figure switched to Detailed follows its joints with the starter set\'s mannequin, a fist is keyed as its own bones, and the passes still render', async ({ page }) => {
  await openApp(page, { suite: 'stage' })
  await page.locator('.placeholder button', { hasText: /^New stage/ }).click()
  const dialog = page.locator('.modal.ask')
  await dialog.locator('input').fill('Detail test')
  await dialog.locator('button.primary').click()
  await expect(page.locator('.stage-row.active')).toContainText('Detail test')
  await page.locator('.lib-grid button', { hasText: /^Adult/ }).click()
  await openSection(page, 'Motion')
  await page.locator('.detail-level .segmented button', { hasText: 'Detailed ♂' }).click()
  type Doc = { name: string; objects: { detail: string | null; pose: { extra: Record<string, number[]> } | null }[] }
  const doc = async () => (await api<{ items: Doc[] }>('GET', '/stages')).items.find((s) => s.name === 'Detail test')!
  await expect.poll(async () => (await doc())?.objects[0]?.detail ?? null, { timeout: 10_000 }).toBe('male')
  // the mannequin loads from the starter folder (the e2e tree's test rig carries a skinned mesh); then the fist is the finger bones' turns
  await expect.poll(async () => {
    await page.locator('.detail-level .kv', { hasText: 'right hand' }).locator('button', { hasText: /^fist$/ }).click()
    return Object.keys((await doc())?.objects[0]?.pose?.extra ?? {}).sort().join(',')
  }, { timeout: 15_000 }).toBe('index_01_r,index_02_r,index_03_r,pinky_01_r')
  // the passes render with the mannequin in them
  await openAnimate(page, 'Clay')
  await stageRoute(page)
  await page.locator('.shot-tab button', { hasText: /^Render passes$/ }).click()
  await expect(page.locator('.shot-tab .pass-side')).toContainText(/\d+ passes · \d+×\d+/, { timeout: 30_000 })   // rendered: '5 passes · 1280×720 · current'
  await page.screenshot({ path: 'node_modules/.e2e/ca1-detailed.png' })
})

test('a floor path (CA1, 01 step 5): the Path tool adds the floor points clicked to the selected figure\'s path, and a clip applied along it walks it with the feet locked', async ({ page }) => {
  await openApp(page, { suite: 'stage' })
  await page.locator('.placeholder button', { hasText: /^New stage/ }).click()
  const dialog = page.locator('.modal.ask')
  await dialog.locator('input').fill('Path test')
  await dialog.locator('button.primary').click()
  await expect(page.locator('.stage-row.active')).toContainText('Path test')
  await page.locator('.lib-grid button', { hasText: /^Adult/ }).click()                       // a figure, selected
  await page.locator('button.cmd-btn[aria-label^="Path (click the floor"]').first().click()
  const canvas = page.locator('canvas.stage-canvas')
  const box = (await canvas.boundingBox())!
  for (const [fx, fy] of [[0.45, 0.8], [0.5, 0.7], [0.6, 0.65]]) await page.mouse.click(box.x + box.width * fx, box.y + box.height * fy)
  type Doc = { name: string; objects: { path: number[][] | null; transform: { pos: number[] } }[]; keyframes: { objects: Record<string, { frame: number; transform: { pos: number[]; rot: number[] } }[]> } }
  const doc = async () => (await api<{ items: Doc[] }>('GET', '/stages')).items.find((s) => s.name === 'Path test')
  await expect.poll(async () => (await doc())?.objects[0]?.path?.length ?? 0, { timeout: 10_000 }).toBe(3)
  await openSection(page, 'Motion')
  const lib = page.locator('.motion-lib')
  await lib.locator('.motion-file-head', { hasText: 'test_rig' }).click()
  await lib.locator('.motion-clip', { hasText: 'Walk_RM' }).click()
  await expect(lib.locator('label', { hasText: /^ ?along Figure 1's path/ })).toBeVisible()
  await lib.locator('button', { hasText: /^Apply to Figure 1 at the playhead/ }).click()
  await expect.poll(async () => Object.values((await doc())?.keyframes.objects ?? {})[0]?.length ?? 0, { timeout: 10_000 }).toBeGreaterThan(1)
  const d = (await doc())!
  const keys = Object.values(d.keyframes.objects)[0]
  const p0 = d.objects[0].path![0]
  expect(Math.hypot(keys[0].transform.pos[0] - p0[0], keys[0].transform.pos[2] - p0[1])).toBeLessThan(0.05)   // it starts at the path's start
  await expect(page.locator('.toast')).toContainText(/along its path, feet locked/)
  // a pose preset on the keyed figure is a key at the playhead (before CA1 it changed only the unkeyed pose, which the keys hide)
  type Key = { frame: number; pose: { preset: string; joints: Record<string, number[]> } | null }
  await page.locator('#anim-sec-motion .stage-panel:not(.motion-lib) .lib-grid button', { hasText: /^point$/ }).click()
  await expect.poll(async () => { const k = Object.values((await doc())?.keyframes.objects ?? {})[0] as unknown as Key[]; return k?.find((x) => x.frame === 0)?.pose?.preset ?? null }, { timeout: 10_000 }).toBe('point')
  const k0 = (Object.values((await doc())!.keyframes.objects)[0] as unknown as Key[]).find((x) => x.frame === 0)!
  expect(Object.keys(k0.pose!.joints)).toHaveLength(12)                                       // spelled out, so it blends with the clip's keys
})
