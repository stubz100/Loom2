// End-to-end smoke (D68, ArtCraft P6 §3): each scenario drives the real UI with the mouse in headless Edge against the e2e build, a real
// orchestrator and the fake engine, and checks the outcome on the page and through the API. Scenarios are independent: each opens a
// fresh page and picks its own assets; they share one project (global-setup.ts), so none relies on another's leftovers.
import { writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { api, appUrl, binTiles, centre, contextChoose, env, expect, openHome, openShell, test, thumbsLoaded } from './fixtures'

interface AssetLite { id: string; job_id: string | null }
interface Group { id: string; name: string; items: { kind: string; id: string }[] }

test('open the project: the Bin shows tiles and their thumbnails load; the Project menu, the layer tabs, Models & engine in ☰ (B2a, D159)', async ({ page }) => {
  expect((await api<{ variant: string }>('GET', '/health')).variant).toBe(env().variant)          // LOOM2_VARIANT reached the orchestrator
  await openShell(page, 'bin')
  await openHome(page, 'world/sketches')
  await expect(binTiles(page).first()).toBeVisible()
  expect(await thumbsLoaded(page, 12)).toBeGreaterThanOrEqual(Math.min(12, env().assets))
  // the Project menu leads the tabs: the open project's name, New / Open / Close and the recents
  const projectTab = page.locator('nav.tabs button.project-tab')
  await expect(page.locator('nav.tabs > button').first()).toHaveClass(/project-tab/)
  await expect(projectTab.locator('.project-name')).not.toHaveText('none open')
  await projectTab.click()
  await expect(page.locator('.menu.project-menu button', { hasText: 'New project' })).toBeVisible()
  await expect(page.locator('.menu.project-menu button', { hasText: /^Close / })).toBeVisible()
  await page.screenshot({ path: 'node_modules/.e2e/project-menu.png', clip: { x: 0, y: 0, width: 1100, height: 260 } })
  await projectTab.click()
  await expect(page.locator('.menu.project-menu')).toHaveCount(0)
  // D157: the layers in the work's order; Models & engine is a sheet in ☰
  await expect(page.locator('nav.tabs button.tab:not(.project-tab)')).toHaveText([/^World/, /^Shots/, /^Episode/, /^Bin/])
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Bin/)
  await page.locator('button[aria-label="app menu"]').click()
  await page.locator('.menu button', { hasText: 'Models & engine' }).click()
  await expect(page.locator('.modal.models-sheet table.grid tbody tr').first()).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.locator('.modal.models-sheet')).toHaveCount(0)
})

test('no keep / reject and no ratings (D122): not in the Bin\'s tile menu, its Inspector or the asset (B2a)', async ({ page }) => {
  await openShell(page, 'bin')
  await openHome(page, 'world/sketches')
  const tile = binTiles(page).nth(3)
  const id = (await tile.getAttribute('data-id'))!
  await tile.click({ button: 'right' })
  const items = page.locator('.ctx-menu button.item')
  await expect(items.filter({ hasText: /^Tag…/ })).toHaveCount(1)
  for (const gone of [/^Keep/, /^Reject/, /^Clear keep/, /^Rate/]) await expect(items.filter({ hasText: gone })).toHaveCount(0)
  await page.keyboard.press('Escape')
  await page.locator(`[data-testid="bin-grid"] .w-tile[data-id="${id}"]`).click()
  const insp = page.locator('[data-testid="bin-inspector"]')
  await expect(insp).toContainText('home')
  await expect(insp.locator('.judge, .stars-edit')).toHaveCount(0)
  for (const gone of ['Keep', 'Reject', 'Rate']) await expect(insp.getByRole('button', { name: gone, exact: true })).toHaveCount(0)
  await page.keyboard.press('k')                                                         // K and X are no keys in the Bin
  await page.keyboard.press('x')
  const a = await api<Record<string, unknown>>('GET', `/assets/${id}`)
  expect('state' in a || 'rating' in a).toBe(false)
  await expect(api('GET', '/assets?sort=rating_desc')).rejects.toThrow(/422/)
})

test('drag a tile onto a home in the Bin\'s tree with the mouse: it moves into that home; a heading takes none (B2a, D159)', async ({ page }) => {
  await api('POST', '/bin/homes', { path: 'world/look' })
  await openShell(page, 'bin')
  await openHome(page, 'world/sketches')                                                                   // B4: the free pictures' home
  const tile = binTiles(page).nth(1)
  const id = (await tile.getAttribute('data-id'))!
  const row = page.locator('[data-testid="bin-tree"] .b-node[data-path="world/look"]')
  const heading = page.locator('[data-testid="bin-tree"] .b-node[data-path="world"]')
  // a real pointer drag (frame/drag.ts: pointer events, never HTML5 drag and drop): press, pass the 5 px threshold, carry, release
  const from = await centre(tile), to = await centre(row), over = await centre(heading)
  await page.mouse.move(from.x, from.y)
  await page.mouse.down()
  await page.mouse.move(from.x + 12, from.y + 8, { steps: 3 })
  await expect(page.locator('.drag-ghost')).toBeVisible()
  await page.mouse.move(over.x, over.y, { steps: 8 })
  await expect(page.locator('.drag-ghost')).toContainText('a heading holds no things')
  await page.mouse.move(to.x, to.y, { steps: 8 })
  await expect(row).toHaveClass(/drop-over/)
  await page.mouse.up()
  await expect(page.locator('.drag-ghost')).toHaveCount(0)
  await expect.poll(async () => (await api<{ path: string }>('GET', `/bin/things/${id}`)).path, { timeout: 10_000 }).toBe('world/look')
  await expect(page.locator(`[data-testid="bin-grid"] .w-tile[data-id="${id}"]`)).toHaveCount(0)        // it left the Sketches
})

test('Make with Klein 4B in Sketches: the fake engine answers, the job runs the model picked in the column and the picture lands in Sketches (B2a)', async ({ page }) => {
  await openShell(page, 'world/sketches')
  const col = page.locator('[data-testid="world-sketches"]')
  await expect(col).toBeVisible()
  await col.locator('#gen-sec-model').scrollIntoViewIfNeeded()
  await col.locator('.model-card').filter({ has: page.locator('span', { hasText: /^Klein 4B$/ }) }).click()
  await expect(col.locator('.model-card.active span').first()).toHaveText('Klein 4B')
  await col.locator('#gen-sec-prompt').scrollIntoViewIfNeeded()
  await col.locator('#gen-sec-prompt .segmented button', { hasText: /^Text$/ }).click()
  await col.locator('.text-prompt textarea').fill('a lighthouse on a cliff at dusk, storm clouds, wide shot')
  const go = col.locator('button', { hasText: /^Make \d+ sketch/ })
  await expect(go).toBeEnabled()
  const count = Number((await go.textContent())!.match(/Make (\d+)/)![1])
  const before = new Set((await api<{ items: { id: string }[] }>('GET', '/jobs')).items.map((j) => j.id))
  await go.click()
  // the job ran the model chosen in the UI (its id comes from /capabilities, D65 — no model id in the test)
  const caps = await api<{ models: Record<string, { label: string }> }>('GET', '/capabilities')
  const klein4b = Object.entries(caps.models).find(([, m]) => m.label === 'Klein 4B')![0]
  type JobLite = { id: string; status: string; recipe: { model_id?: string }; origin: { surface?: string } | null; result: { asset_ids?: string[] } | null }
  const jobOf = async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => !before.has(j.id) && j.origin?.surface === 'sketch')
  await expect.poll(async () => (await jobOf())?.status, { timeout: 45_000 }).toBe('done')
  const job = (await jobOf())!
  expect(job.recipe.model_id).toBe(klein4b)
  expect(count).toBeGreaterThanOrEqual(1)
  expect(job.result?.asset_ids?.length).toBeGreaterThanOrEqual(1)                                       // a sketch is a job each
  const newest = job.result!.asset_ids![0]
  await expect.poll(async () => (await api<{ path: string }>('GET', `/bin/things/${newest}`)).path, { timeout: 10_000 }).toBe('world/sketches')
  const tile = page.locator(`.w-tile[data-id="${newest}"]`)
  await expect(tile).toBeVisible()
  await expect.poll(() => tile.locator('img').evaluate((i: HTMLImageElement) => i.complete && i.naturalWidth > 0)).toBe(true)
})

test('Edit opens from a Bin tile on WebGL2 (B2a): a mouse stroke dirties the document, its foot says so, and Save beside it puts the new version in the picture\'s home', async ({ page }) => {
  await openShell(page, 'bin', { renderer: 'webgl' })
  await openHome(page, 'world/sketches')
  const tile = binTiles(page).nth(5)
  const src = (await tile.getAttribute('data-id'))!
  await contextChoose(page, tile, 'Open in Edit')
  await expect(page.locator('[data-testid="world-edit"]')).toBeVisible()                                  // World's Edit, a free edit over the Sketches
  await expect(page.locator('.badge-renderer')).toHaveText(/WebGL2/)
  const canvas = page.locator('.edit-canvas canvas')
  await expect(canvas).toBeVisible()
  await page.waitForFunction(() => !!(window as unknown as { __loom2Editor: { getState: () => { doc: { id: string } | null } } }).__loom2Editor.getState().doc?.id)
  await page.locator('#edit-sec-tools').scrollIntoViewIfNeeded()
  await page.locator('button[title^="Brush"]').first().click()
  const box = (await canvas.boundingBox())!
  const [cx, cy] = [box.x + box.width / 2, box.y + box.height / 2]
  await page.mouse.move(cx - 120, cy - 20)
  await page.mouse.down()
  for (let i = 1; i <= 24; i++) await page.mouse.move(cx - 120 + i * 10, cy - 20 + Math.sin(i / 3) * 30)
  await page.mouse.up()
  const save = page.locator('.w-edit-foot button.primary')
  await expect(save).toHaveText('Save beside it •')
  await save.click()
  await expect(save).toHaveText('Save beside it')
  const home = (await api<{ path: string }>('GET', `/bin/things/${src}`)).path
  await expect.poll(async () => {
    const kids = (await api<{ children: { to_id: string }[] }>('GET', `/lineage/${src}`)).children
    return kids.length ? (await api<{ path: string }>('GET', `/bin/things/${kids[kids.length - 1].to_id}`)).path : null
  }, { timeout: 15_000 }).toBe(home)
  await expect(page.locator('.w-edit-foot').getByRole('button', { name: /Export PNG/ })).toBeVisible()  // Edit's own foot
})

test('Performance: the drawer\'s right-click fills the start and the end slots of Image to video (B2a)', async ({ page }) => {
  const tag = Date.now().toString(36)
  const a = await api<{ shot_id: string }>('POST', '/story/flow/shots', { title: `Slots ${tag}`, scene: 'new' })
  await openShell(page, `shots/${a.shot_id}/performance`)
  await page.locator('.perf-cards button', { hasText: 'Image to video' }).click()
  await expect(page.locator('.perf-cards button.active')).toHaveText('Image to video')
  await page.locator('.dock .dock-tabs button', { hasText: 'Bin' }).click()
  await drawerHome(page, 'world/sketches')
  await page.locator('.dock .bin-bar .segmented button', { hasText: 'pictures' }).click()
  const grid = page.locator('.dock .bin-grid')
  const [ta, tb] = [grid.locator('.w-tile').nth(2), grid.locator('.w-tile').nth(3)]
  const [idA, idB] = [await ta.getAttribute('data-id'), await tb.getAttribute('data-id')]
  await contextChoose(page, ta, 'Set as the start frame (Performance)')
  const slots = page.locator('.slots .slot')
  await expect(slots.nth(0).locator('img')).toBeVisible()
  await contextChoose(page, grid.locator(`.w-tile[data-id="${idB}"]`), 'Use as the end frame (Performance)')
  await expect(slots.nth(1).locator('img')).toBeVisible()
  for (const [k, id] of [[0, idA], [1, idB]] as const) {
    await expect.poll(() => slots.nth(k).locator('img').evaluate((i: HTMLImageElement) => i.complete && i.naturalWidth > 0)).toBe(true)
    expect(await slots.nth(k).locator('img').getAttribute('src')).toContain(`/thumbs/${id}/`)
  }
})

/** B4 (D159): the newest pictures in World › Sketches, where the free ones live (the newest Unprocessed ones before), newest first. */
async function sketchPics(n: number): Promise<AssetLite[]> {
  type N = { id: string; path: string; children: N[] }
  const find = (ns: N[]): N | undefined => { for (const x of ns) { if (x.path === 'world/sketches') return x; const k = find(x.children); if (k) return k } return undefined }
  const s = find((await api<{ homes: N[] }>('GET', '/bin/tree')).homes)!
  return (await api<{ items: { asset: AssetLite & { kind: string } }[] }>('GET', `/bin/homes/${s.id}/items?limit=${Math.max(n * 3, 20)}`)).items.map((x) => x.asset).filter((a) => a.kind === 'image').slice(0, n)
}

/** B4: a home of the Dock's drawer opened, its parents unfolded (`world/sketches`). */
async function drawerHome(page: import('@playwright/test').Page, path: string): Promise<void> {
  const homes = page.locator('[data-testid="bin-drawer-homes"]')
  const parts = path.split('/')
  for (let i = 1; i < parts.length; i++) {
    const chev = homes.locator(`.b-node[data-path="${parts.slice(0, i).join('/')}"] > .b-chev[aria-label="Unfold"]`)
    if (await chev.count()) await chev.click()
  }
  await homes.locator(`.b-node[data-path="${path}"] .b-open`).click()
}

/** D119 (SC2): the Library's presets sit behind each group's + — open the group's panel and click the tile by its name; the panel closes
 *  with the next click elsewhere. `group`: figures | sets | standins | templates (the Scene section), poses (the Motion section). */
async function libAdd(page: import('@playwright/test').Page, group: string, name: string): Promise<void> {
  const row = page.locator(`.lib-row[data-group="${group}"]`)
  if (!(await row.locator('[data-preset-panel-btn][aria-expanded="true"]').count())) await row.locator('[data-preset-panel-btn]').click()
  await page.locator(`[data-preset-panel] button.preset-icon[aria-label^="${name}"]`).click()
}

/** B2a (D159): a shot on a scene of its own with its Clay open — its stage named `name` (the old shell's *New stage…*). */
async function clayShot(page: import('@playwright/test').Page, name: string): Promise<{ shot: string; stage: string }> {
  const a = await api<{ shot_id: string }>('POST', '/story/flow/shots', { title: name, scene: 'new' })
  const sid = (await api<{ versions: { stage_id: string }[] }>('GET', `/story/shots/${a.shot_id}`)).versions[0].stage_id
  const st = await api<Record<string, unknown>>('GET', `/stages/${sid}`)
  if (st.name !== name) await api('PUT', `/stages/${sid}`, { ...st, name })
  await openShell(page, `shots/${a.shot_id}/clay`)
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await freeView(page)
  return { shot: a.shot_id, stage: sid }
}
/** B2a: a shot on a stage made through the API, its Clay open (the shot linked to the stage and its first camera). */
async function clayOn(page: import('@playwright/test').Page, stageId: string, title = 'Shot'): Promise<string> {
  const a = await api<{ shot_id: string }>('POST', '/story/flow/shots', { title, scene: 'new' })
  const st = await api<{ cameras: { id: string }[] }>('GET', `/stages/${stageId}`)
  await api('PUT', `/story/shots/${a.shot_id}/versions/v1/source`, { stage_id: stageId, camera_id: st.cameras[0]?.id ?? null })
  await openShell(page, `shots/${a.shot_id}/clay`)
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await freeView(page)
  return a.shot_id
}
/** B2a: a still from the open shot's stage — World's Sketches with its source *From a stage* (the frame form, Render frame in its foot). */
async function fromStageIn(page: import('@playwright/test').Page): Promise<void> {
  await page.locator('nav.tabs button.tab', { hasText: 'World' }).click()
  await page.locator('.w-rail-btn[aria-label="Sketches"]').click()
  await page.locator('[data-testid="world-sketches"] .gen-source .segmented button', { hasText: 'From a stage' }).click()
  await expect(page.locator('.shot-tab')).toBeVisible()
}
/** B2a: Clay's free view (Shots opens Clay through the shot's camera; the old shell opened the free view). */
async function freeView(page: import('@playwright/test').Page): Promise<void> {
  await expect(page.locator('.cam-pill .cam-pill-main')).toBeVisible()
  if (await page.locator('.frame-guides').count()) await page.locator('.cam-pill .cam-pill-main').click()
  await expect(page.locator('.frame-guides')).toHaveCount(0)
}
/** B2a: a section of the level's column in view (the old rail scrolled to it). */
async function section(page: import('@playwright/test').Page, id: string): Promise<void> {
  await page.locator(`#anim-sec-${id}`).evaluate((el) => el.scrollIntoView({ block: 'start' }))
}
/** B2a: the open shot's level, from the rail. */
async function toLevel(page: import('@playwright/test').Page, level: 'clay' | 'performance' | 'final'): Promise<void> {
  if (!(await page.locator('[data-testid="shots-layer"]').isVisible())) await page.locator('nav.tabs button.tab', { hasText: 'Shots' }).click()
  await page.locator(`.w-rail-btn[data-level="${level}"]`).click()
  await expect(page.locator('[data-testid="shots-layer"]')).toHaveAttribute('data-level', level)
}
/** B2a: a card of the open shot's Performance — Image to video, Stage clip or Final shot (the foot follows the card). */
async function perfCardOf(page: import('@playwright/test').Page, card: 'Image to video' | 'Stage clip' | 'Final shot'): Promise<void> {
  await toLevel(page, 'performance')
  await section(page, 'performance')
  await page.locator('.perf-cards button', { hasText: card }).click()
  await expect(page.locator('.perf-cards button.active')).toHaveText(card)
}

/** B2a (D159): an entity version's Sheet in World — its whole card (the sheet, the body, the animation reference, the model or the set). */
async function openBuild(page: import('@playwright/test').Page, cls: 'character' | 'prop' | 'place', id: string, version = 'v1'): Promise<void> {
  await openShell(page, `world/${cls}/${id}/${version}`)
  await expect(page.locator('[data-testid="world-header"]')).toBeVisible()
  await page.locator('.w-mode button', { hasText: 'Build' }).click()                                      // D161: what Clay needs
  await expect(page.locator('[data-testid="world-build"]')).toBeVisible()
}

/** D161: World's Make — the sheet's words at its top, then the picture settings. */
async function openMake(page: import('@playwright/test').Page, cls: 'character' | 'prop' | 'place', id: string, version = 'v1'): Promise<void> {
  await openShell(page, `world/${cls}/${id}/${version}`)
  await expect(page.locator('[data-testid="world-sheet"] .cast-sheet')).toBeVisible()
}

type EdWin = { __loom2Editor?: { getState: () => { doc?: { id: string }; tool: string } }; __loom2AiPanel?: { getState: () => { op: string; selMode: string } } }
const editorTool = (page: import('@playwright/test').Page) => page.evaluate(() => { const w = window as unknown as EdWin; const ed = w.__loom2Editor?.getState(); const ai = w.__loom2AiPanel?.getState()
  return ed ? { doc: !!ed.doc, tool: ed.tool, op: ai?.op, sel: ai?.selMode } : null })

test('quick starts (D71, B2a): "Select subject…" on a Bin picture reaches World\'s Edit with AI Select · Subject in one click; the deep link does too', async ({ page }) => {
  await openShell(page, 'bin')
  await openHome(page, 'world/sketches', 'pictures')
  await binTiles(page).nth(8).click()
  await page.locator('[data-testid="bin-inspector"] button', { hasText: 'Start from it' }).click()
  await page.locator('.ctx-menu button.item', { hasText: 'Select subject…' }).click()
  await expect.poll(() => editorTool(page), { timeout: 30_000 }).toEqual({ doc: true, tool: 'ai', op: 'select', sel: 'subject' })
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^World/)
  await expect(page.locator('[data-testid="world-edit"]')).toBeVisible()
  const pic = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  await openShell(page, 'world', { suite: 'edit', tool: 'ai', ai: 'upscale', asset: pic })
  await expect.poll(() => editorTool(page), { timeout: 30_000 }).toMatchObject({ doc: true, tool: 'ai', op: 'upscale' })
  await expect(page.locator('[data-testid="world-edit"]')).toBeVisible()
})

test("Instruct (D151): the AI tab's edit by instruction — the deep link opens it, it refuses without an instruction and runs with one; the canvas menu shows it (in World's Edit, B2a)", async ({ page }) => {
  await openShell(page, 'bin')
  await openHome(page, 'world/sketches', 'pictures')
  await binTiles(page).nth(8).click({ button: 'right' })
  await page.locator('.ctx-menu button.item', { hasText: /^Select subject…/ }).click()                    // World's Edit with a document (D71)
  await expect.poll(() => editorTool(page), { timeout: 30_000 }).toMatchObject({ doc: true, tool: 'ai' })
  await page.getByRole('button', { name: 'Instruct', exact: true }).click()
  await expect.poll(() => editorTool(page), { timeout: 10_000 }).toMatchObject({ op: 'instruct' })
  const run = page.getByRole('button', { name: /^AI ▶ Instruct/ })
  await expect(run).toBeDisabled()
  await expect(page.locator('p.hint', { hasText: 'say what to change' })).toBeVisible()
  await page.locator('textarea[placeholder^="what to change"]').fill('make it dusk, the lamps lit')
  await expect(run).toBeEnabled()
  await expect(run).toHaveText(/×2$/)                                                                     // two candidates by default (≈ 32 s each)
  await page.screenshot({ path: 'node_modules/.e2e/d151-instruct.png' })
  const pic = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  await openShell(page, 'world', { suite: 'edit', tool: 'ai', ai: 'instruct', asset: pic })
  await expect.poll(() => editorTool(page), { timeout: 30_000 }).toMatchObject({ tool: 'ai', op: 'instruct' })
})

test("the reference deck (D152): Inpaint and Refine show the model's slots in the AI tab, Remove shows none; the deck keeps its shape across operations (in World's Edit, B2a)", async ({ page }) => {
  await openShell(page, 'bin')
  await openHome(page, 'world/sketches', 'pictures')
  await binTiles(page).nth(8).click({ button: 'right' })
  await page.locator('.ctx-menu button.item', { hasText: /^Select subject…/ }).click()                    // World's Edit with a document (D71)
  await expect.poll(() => editorTool(page), { timeout: 30_000 }).toMatchObject({ doc: true, tool: 'ai' })
  await page.getByRole('button', { name: 'Inpaint', exact: true }).click()
  const slots = page.locator('.ref-slots.ai-refs')
  await expect(slots).toBeVisible()
  const max = Number(await slots.getAttribute('data-max'))
  expect(max).toBeGreaterThanOrEqual(1)
  await expect(slots.locator('.ref-slot')).toHaveCount(max)
  await expect(slots.locator('.ref-slot').first()).toHaveAttribute('title', /drop a picture from the Bin here/)
  await page.screenshot({ path: 'node_modules/.e2e/d152-refs.png' })
  await page.locator('.tool-opts select').first().selectOption('remove')                                 // Remove: no references
  await expect(page.locator('.ref-slots.ai-refs')).toHaveCount(0)
  await page.locator('.tool-opts select').first().selectOption('fill')
  await page.getByRole('button', { name: 'Refine', exact: true }).click()
  await expect(page.locator('.ref-slots.ai-refs')).toHaveCount(1)
})

test('text layers (D154): the Text tool places text typed in place; the layer is marked and editable in Properties; Rasterize text drops the block (in World’s Edit, B2a)', async ({ page }) => {
  await openShell(page, 'bin')
  await openHome(page, 'world/sketches', 'pictures')
  await binTiles(page).nth(8).click({ button: 'right' })
  await page.locator('.ctx-menu button.item', { hasText: /^Select subject…/ }).click()                    // World's Edit with a document (D71)
  await expect.poll(() => editorTool(page), { timeout: 30_000 }).toMatchObject({ doc: true, tool: 'ai' })
  await page.locator('#edit-sec-tools').scrollIntoViewIfNeeded()                                       // the toolbox, in the column (no rail)
  await page.getByRole('button', { name: 'T Text', exact: true }).click()                                   // the toolbox button (its key and label)
  await expect.poll(() => editorTool(page)).toMatchObject({ tool: 'text' })
  const box = (await page.locator('.edit-canvas').boundingBox())!
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)                                 // a click: point text, the inline editor opens
  const ta = page.locator('.text-edit textarea')
  await expect(ta).toBeVisible()
  await ta.fill('Scene 1')
  await page.locator('.text-edit-bar button[title^="Apply text"]').click()
  await expect(page.locator('.text-edit')).toHaveCount(0)
  const row = page.locator('.layer-row', { hasText: 'Scene 1' })
  await expect(row).toBeVisible()
  await expect(row.locator('.kind')).toContainText('T ·')
  await page.locator('.tabs2 button', { hasText: 'properties' }).click()
  await expect(page.locator('.props .text-content')).toHaveValue('Scene 1')
  await page.screenshot({ path: 'node_modules/.e2e/d154-text.png' })
  await page.getByRole('button', { name: 'Rasterize text' }).click()
  await expect(page.locator('.props .text-content')).toHaveCount(0)
  await page.locator('.tabs2 button', { hasText: 'layers' }).click()
  await expect(row.locator('.kind')).not.toContainText('T ·')
})

test('the detachable loupe (D155, B2a): Detach ↗ in the Bin\'s large view opens a second window that follows the Bin until it is held', async ({ page, context }) => {
  await openShell(page, 'bin')
  await openHome(page, 'world/sketches')
  await binTiles(page).nth(7).dblclick()
  const loupe = page.locator('[data-testid="bin-loupe"]')
  await expect(loupe).toBeVisible()
  const [popup] = await Promise.all([context.waitForEvent('page'), loupe.locator('.facts').getByRole('button', { name: /^Detach/ }).click()])
  await popup.waitForLoadState()
  const img = popup.locator('.detached-loupe .view img')
  await expect(img).toBeVisible({ timeout: 30_000 })
  const src0 = (await img.getAttribute('src'))!
  expect(src0).toContain('/assets/')
  await loupe.locator('.facts').getByRole('button', { name: 'Next', exact: true }).click()          // the main window moves on: the second follows
  await expect.poll(() => img.getAttribute('src')).not.toBe(src0)
  await popup.getByRole('button', { name: /^Following/ }).click()                                  // held: it stays
  const held = await img.getAttribute('src')
  await loupe.locator('.facts').getByRole('button', { name: 'Next', exact: true }).click()
  await page.waitForTimeout(600)
  expect(await img.getAttribute('src')).toBe(held)
  await expect(popup.locator('.detached-loupe')).toHaveAttribute('data-following', 'held')
  await popup.screenshot({ path: 'node_modules/.e2e/d155-detached.png' })
  await popup.close()
})

test('the camera move (D156): the camera model shows a camera control under the preset; the plain model shows none (Shots, B2a)', async ({ page }) => {
  await clayShot(page, `Camera ${Date.now().toString(36)}`)
  await perfCardOf(page, 'Image to video')                                                               // the model cards sit in the Performance section
  const cam = page.locator('.model-card').filter({ has: page.locator('b', { hasText: /^Camera/ }) })
  await expect(cam).toBeVisible()
  await cam.click()
  const move = page.locator('select[aria-label="camera move"]')
  await expect(move).toBeVisible()
  await move.selectOption('pan_left')
  await expect(page.locator('input[aria-label="camera speed"]')).toHaveValue('1')
  await page.screenshot({ path: 'node_modules/.e2e/d156-camera.png' })
  await page.locator('.model-card').filter({ has: page.locator('b', { hasText: /^Wan\b/ }) }).first().click()
  await expect(page.locator('select[aria-label="camera move"]')).toHaveCount(0)
})

test('remappable keys (D72, B2a): the Bin\'s Pin for compare to T is refused (Tag… has it); to J — menu, tooltip and help show J, J pins, C does not, it survives a reload', async ({ page }) => {
  await openShell(page, 'bin')
  await openHome(page, 'world/sketches')
  const openKeys = async () => {
    await page.locator('button[aria-label="app menu"]').click()
    await page.locator('.menu button', { hasText: /^Settings…/ }).click()
    const row = page.locator('.keys-row[data-cmd="bin.item.pin"]')
    await row.scrollIntoViewIfNeeded()
    return row
  }
  const closeSettings = () => page.locator('.modal-backdrop').click({ position: { x: 4, y: 4 } })
  let row = await openKeys()
  await expect(row.locator('.keys-chord')).toHaveText('C')
  await row.locator('.keys-chord').click()
  await expect(row.locator('.keys-chord')).toHaveText('press a key…')
  await page.keyboard.press('t')                                                         // T is Tag…'s — refused, with its name
  await expect(row.locator('.keys-note.error')).toContainText('“Tag…”')
  await expect(row.locator('.keys-chord')).toHaveText('C')
  await row.locator('.keys-chord').click()
  await page.keyboard.press('j')
  await expect(row.locator('.keys-chord')).toHaveText('J')
  await expect(row.locator('.keys-note')).toHaveText('now J')
  await closeSettings()

  const [a, b] = [binTiles(page).nth(10), binTiles(page).nth(11)]
  await a.click({ button: 'right' })                                                     // the tile menu shows J
  await expect(page.locator('.ctx-menu button.item', { hasText: /^Pin for compare/ }).locator('kbd')).toHaveText('J')
  await page.keyboard.press('Escape')
  await expect(page.locator('.ctx-menu')).toHaveCount(0)
  await a.click()
  await expect(page.locator('[data-testid="bin-inspector"] button[aria-label="Pin for compare"]')).toHaveAttribute('title', /\(J\)/)
  await page.keyboard.press('j')                                                          // J pins
  await expect(a.locator('.b-pin')).toHaveText('A')
  await b.click()
  await page.keyboard.press('c')                                                          // C does nothing now
  await page.waitForTimeout(500)
  await expect(b.locator('.b-pin')).toHaveCount(0)
  await page.keyboard.press('?')                                                          // help lists Pin for compare with J
  await expect(page.locator('.cmd-help .row', { hasText: /^Pin for compare/ }).first().locator('kbd')).toHaveText('J')
  await page.keyboard.press('Escape')

  await page.reload()                                                                     // a restart keeps it
  await expect(page.locator('.frame.ui2')).toBeVisible()
  row = await openKeys()
  await expect(row.locator('.keys-chord')).toHaveText('J')
  await expect(row).toHaveClass(/changed/)
  await row.getByRole('button', { name: 'Reset the key of Pin for compare' }).click()
  await expect(row.locator('.keys-chord')).toHaveText('C')
})

test('@mentions (D73, in Sketches since B2a): "@hero walks into @tavern" — both groups give references in the preview, and the job records both at their revisions', async ({ page }) => {
  const tag = Date.now().toString(36)
  const [heroName, tavernName] = [`hero ${tag}`, `tavern ${tag}`]                   // names with a space, as people write them
  const hero = await api<Group>('POST', '/groups', { name: heroName }), tavern = await api<Group>('POST', '/groups', { name: tavernName })
  const free = (await sketchPics(40))
  await api('POST', '/groups/move', { items: free.slice(0, 3).map((a) => ({ kind: 'asset', id: a.id })), to: hero.id })
  await api('POST', '/groups/move', { items: free.slice(3, 5).map((a) => ({ kind: 'asset', id: a.id })), to: tavern.id })
  await openShell(page, 'world/sketches')
  const col = page.locator('[data-testid="world-sketches"]')
  await col.locator('#gen-sec-model').scrollIntoViewIfNeeded()
  await col.locator('.model-card').filter({ has: page.locator('span', { hasText: /^Klein 4B$/ }) }).click()   // takes 4 references
  await col.locator('#gen-sec-prompt').scrollIntoViewIfNeeded()
  await col.locator('#gen-sec-prompt .segmented button', { hasText: /^Text$/ }).click()
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
  const go = col.locator('button', { hasText: /^Make \d+ sketch/ })
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

test('a part whose code fails to load says so and recovers (no blank window, B2a): World\'s Edit refused, then a reload', async ({ page }) => {
  test.setTimeout(150_000)                                                             // the reload + WebGL boot takes long on the CI runners
  const refused = /(EditSuite|WorldEdit)-[\w-]+\.js$/
  await page.route(refused, (r) => r.abort('failed'))                                  // the network refuses Edit's code (the idle preload hits it too)
  await openShell(page, 'bin')
  await openHome(page, 'world/sketches', 'pictures')
  await contextChoose(page, binTiles(page).nth(2), 'Open in Edit')
  await expect(page.locator('.w-centre .render-error')).toContainText("Edit's code could not be loaded")
  await expect(page.locator('.render-error')).toHaveCount(1)                          // one explanation, in the middle; the column says one line
  await expect(page.locator('.render-error-line')).toContainText('Edit is not available')
  await expect(page.locator('.frame.ui2 nav.tabs')).toBeVisible()                    // the rest of the app stays
  await expect(page.locator('.dock')).toBeVisible()
  await page.unroute(refused)
  await page.locator('.w-centre .render-error').getByRole('button', { name: 'Reload the app' }).click()   // the browser keeps a failed module: reload
  await expect(page.locator('.frame.ui2')).toBeVisible()
  await openShell(page, 'bin')
  await openHome(page, 'world/sketches', 'pictures')
  await contextChoose(page, binTiles(page).nth(2), 'Open in Edit')
  await expect(page.locator('[data-testid="world-edit"] .edit-canvas')).toBeVisible({ timeout: 90_000 })   // the code loads this time
})

test('a new angle (P14, D82; B2a): "New angle…" on a Bin picture opens the sheet with the source, the pad picks the move, the job lands with reangle lineage', async ({ page }) => {
  await openShell(page, 'bin')
  await openHome(page, 'world/sketches', 'pictures')
  const srcId = (await binTiles(page).nth(8).getAttribute('data-id'))!   // pinned by id
  await page.locator(`[data-testid="bin-grid"] .w-tile[data-id="${srcId}"]`).click()
  await page.locator('[data-testid="bin-inspector"] button', { hasText: 'Start from it' }).click()
  await page.locator('.ctx-menu button.item', { hasText: 'New angle…' }).click()
  const sheet = page.locator('.modal.angle-sheet')                                                    // a sheet over the Bin, no layer switch
  await expect(sheet).toBeVisible()
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Bin/)
  await expect(sheet.locator('.angle-tab .ref-slot.source img')).toBeVisible()
  await sheet.locator('.angle-pad button[aria-label="Wide"]').click()                             // D90: the moves are icons
  const go = sheet.locator('.foot button.primary', { hasText: /^New angle/ })
  await expect(go).toBeEnabled({ timeout: 15_000 })
  await expect(sheet.locator('.foot .estimate')).toContainText(/Klein/)                        // auto: a framing move runs Klein (D77)
  await go.click()
  await expect(sheet).toHaveCount(0)                                                                  // queueing closes the sheet
  type JobLite = { id: string; status: string; recipe: { kind: string; move?: string }; result: { asset_ids?: string[] } | null }
  const jobOf = async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.recipe?.kind === 'reangle')
  await expect.poll(async () => (await jobOf())?.status, { timeout: 45_000 }).toBe('done')
  const job = (await jobOf())!
  expect(job.recipe).toMatchObject({ kind: 'reangle', move: 'wide' })
  expect(job.result?.asset_ids).toHaveLength(1)
  const newest = await api<AssetLite & { parents: string[]; lineage_kind: string | null }>('GET', `/assets/${job.result!.asset_ids![0]}`)
  expect(newest.parents).toEqual([srcId])                                                               // lineage: the source …
  expect(newest.lineage_kind).toBe('reangle')
  const edges = await api<{ parents: { from_id: string; kind: string }[] }>('GET', `/lineage/${newest.id}`)
  expect(edges.parents.map((p) => [p.from_id, p.kind])).toEqual([[srcId, 'reangle']])                   // … and the edge kind
})

test('a sequence (P17, D83 — in Story · Episode since 17 SY4): a fake-engine clip goes on a new lane from the bin, the document saves with its revision, the EDL is written (Episode, B2a)', async ({ page }) => {
  // a fake-engine clip (Performance's image to video, through the API: the scenarios of Performance cover its card)
  const caps = await api<{ defaults: { i2v: string } }>('GET', '/capabilities')
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const job = (await api<{ jobs: { id: string }[] }>('POST', '/jobs', { recipe: { kind: 'i2v', model_id: caps.defaults.i2v, start_asset: img, width: 832, height: 480, frames: 9, fps: 16, prompt_text: 'a sequence' }, stage: false,
    origin: { suite: 'animate', surface: 'clip' } })).jobs[0]
  await expect.poll(async () => (await api<{ items: { id: string; status: string }[] }>('GET', '/jobs')).items.find((j) => j.id === job.id)?.status, { timeout: 60_000 }).toBe('done')
  await openShell(page, 'episode')                                                        // 17 SY4 (D85) → D157: the lane is Episode's
  await expect(page.locator('.seq-bin:not(.shots-bin) .seq-clip-card').first()).toBeVisible({ timeout: 120_000 })    // the clip lands when its proxy is ready (clip.ready)
  await page.locator('.seq-list-head button[title^="New cut"]').click()
  const dialog = page.locator('.modal.ask')
  await dialog.locator('input').fill('Reel one')
  await dialog.locator('button.primary').click()
  await expect(page.locator('.seq-row.active')).toContainText('Reel one')
  await page.locator('.seq-bin:not(.shots-bin) .seq-clip-card button').first().click()    // + : add the clip to the end of the lane
  await expect(page.locator('.cut-clip.k-take')).toHaveCount(1)                           // CE2 (D126): a cut is a FilmCraft project — its tracks, V1 holding the take
  await expect(page.locator('.cut-view img')).toBeVisible()                                // FilmCraft's frame at the playhead
  const thumb = page.locator('.cut-clip .cut-thumbs img').first()                          // C24 frame thumbnails across the block
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
  // RC3: the movie — an MP4 named after the cut in its folder, a Catalogue video (not a clip), Reveal beside it
  await page.locator('.seq-insp button', { hasText: /^Render the movie$/ }).click()
  const movie = page.getByTestId('seq-movie')
  await expect(movie).toContainText('reel-one.mp4', { timeout: 120_000 })
  await expect(movie.locator('span[title]', { hasText: 'reel-one.mp4' })).toHaveAttribute('title', `timelines/${tl.id}/reel-one/reel-one.mp4`)
  await expect(movie.locator('button[title^="Reveal the movie"]')).toBeEnabled()
  await expect(page.locator('.seq-bin:not(.shots-bin) .seq-clip-card')).toHaveCount(2)
  const jobs = await api<{ items: { recipe: { kind: string; movie?: boolean }; result: { asset_ids?: string[]; revision?: number } }[] }>('GET', '/jobs')
  const mj = jobs.items.find((j) => j.recipe.kind === 'render' && j.recipe.movie)!
  const mv = await api<{ kind: string; lineage_kind: string | null; parents: string[]; params: { movie?: boolean } }>('GET', `/assets/${mj.result.asset_ids![0]}`)
  expect([mv.kind, mv.lineage_kind, mv.params.movie, mv.parents.length]).toEqual(['video', 'render', true, 1])
})
test("the cut's tracks (CE2–CE3, D126): a FilmCraft cut shows its every track and FilmCraft's frame; the razor cuts a take, the right-click sets its speed, undo and redo are the cut's own, a ripple trim closes up, a track is renamed from its header; a sound's gain and fade from its right-click, the cut's mix in the viewer; D127: the audio tracks' roles, a strip set from a header and from the Inspector's sliders, an effect added, edited, bypassed and printed; CE4: a preset, a scene's grade, a value, a look, a match, a reset; CE5: a caption added, edited and moved, a marker, the movie as ProRes with its captions (Episode, B2a)", async ({ page }) => {
  test.setTimeout(120_000)
  // a take from the fake engine, on a new cut's V1 (through the API: the bins' + is the sequence scenario's)
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const caps = await api<{ defaults: { i2v: string } }>('GET', '/capabilities')
  type JobLite = { id: string; status: string; result: { clip_id?: string } }
  const job = (await api<{ jobs: { id: string }[] }>('POST', '/jobs', { recipe: { kind: 'i2v', model_id: caps.defaults.i2v, start_asset: img, width: 832, height: 480, frames: 33, fps: 16, prompt_text: 'tracks clip' }, stage: false, origin: { suite: 'animate', surface: 'clip' } })).jobs[0]
  await expect.poll(async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.id === job.id)?.status, { timeout: 60_000 }).toBe('done')
  const clipId = (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.id === job.id)!.result.clip_id!
  const name = `Tracks ${Date.now().toString(36)}`
  const tl = await api<{ id: string; revision: number; file: string | null }>('POST', '/timelines', { name })
  expect(tl.file).toBe('cut.fcproj')
  const placed = await api<{ timeline: { revision: number } }>('POST', `/timelines/${tl.id}/place`, { revision: tl.revision, clip_id: clipId, track: 'V1', frame: 0 })
  // CE3: a sound on A2 — a line voiced on the fake runner, its audio placed as music
  const voice = await api<{ id: string }>('POST', '/story/voices', { name: `Tr voice ${name}`, voice: 'af_heart' })
  const vn = await api<{ id: string; revision: number }>('POST', '/story/flow/nodes', { type: 'dialogue', title: `${name} cue`, x: 960, y: 640 })
  await api('PATCH', `/story/flow/nodes/${vn.id}`, { revision: vn.revision, lines: [{ speaker: null, text: 'A short cue.' }] })
  const tts = await api<{ job_ids: string[] }>('POST', `/story/flow/nodes/${vn.id}/lines/0/voice`, { voice_id: voice.id })
  await expect.poll(async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.id === tts.job_ids[0])?.status, { timeout: 60_000 }).toBe('done')
  const cue = (await api<{ nodes: { id: string; lines: { audio_asset_id: string | null }[] }[] }>('GET', '/story/flow')).nodes.find((n) => n.id === vn.id)!.lines[0].audio_asset_id!
  await api('POST', `/timelines/${tl.id}/place`, { revision: placed.timeline.revision, asset_id: cue, track: 'A2', frame: 0 })
  type Tracks = { video: { name: string; items: { id: number; start: number; duration: number; speed: number }[] }[]; audio: { items: { gain_db: number }[]; transitions: unknown[] }[] }
  const tracks = () => api<Tracks>('GET', `/timelines/${tl.id}/tracks`)
  await openShell(page, 'episode')
  await page.locator('.seq-row', { hasText: name }).click()
  await expect(page.locator('.cut-row')).toHaveCount(5)                                          // V2 V1 · A1 A2 A3
  const takes = page.locator('.cut-clip.k-take')
  await expect(takes).toHaveCount(1)
  await expect(page.locator('.cut-view img')).toBeVisible()                                      // FilmCraft's frame at the playhead
  // the razor: a click in the take cuts it there
  await page.locator('.transport button[title^="Razor tool"]').click()
  const box = (await takes.first().boundingBox())!
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
  await expect(takes).toHaveCount(2)
  // back to Select with its key (the Episode answers the cut's tools), then the right-click: Speed… at 50 %
  await page.keyboard.press('v')
  await expect(page.locator('.transport button[title^="Select tool"]')).toHaveClass(/\bactive\b/)
  await contextChoose(page, takes.first(), 'Speed…')
  await page.locator('.modal.ask input').fill('50')
  await page.locator('.modal.ask button.primary').click()
  await expect(takes.first()).toContainText('50 %')
  // the cut's undo and redo (the transport)
  await page.locator('.transport button[title^="Undo (cut)"]').click()
  await expect(takes.first()).not.toContainText('50 %')
  await page.locator('.transport button[title^="Redo (cut)"]').click()
  await expect(takes.first()).toContainText('50 %')
  // Ripple: the first piece's out edge dragged left — the second piece follows it
  const before = (await tracks()).video[0].items.map((i) => i.start)
  await page.locator('.transport button[title^="Ripple trim tool"]').click()
  const b1 = (await takes.first().boundingBox())!
  await page.mouse.move(b1.x + b1.width - 2, b1.y + b1.height / 2)
  await page.mouse.down()
  await page.mouse.move(b1.x + b1.width - 32, b1.y + b1.height / 2, { steps: 4 })
  await page.mouse.up()
  await expect.poll(async () => (await tracks()).video[0].items[1].start, { timeout: 10_000 }).toBeLessThan(before[1])
  // a track's header: Rename the track…
  await contextChoose(page, page.locator('.cut-head', { hasText: 'Video 2' }), 'Rename the track…')
  await page.locator('.modal.ask input').fill('Inserts')
  await page.locator('.modal.ask button.primary').click()
  await expect(page.locator('.cut-head', { hasText: 'Inserts' })).toHaveCount(1)
  expect((await tracks()).video[1].name).toBe('Inserts')
  // CE3: the sound's right-click — Gain… and Fade in; the cut's mix reaches the viewer
  const sound = page.locator('.cut-clip.k-sound')
  await expect(sound).toHaveCount(1)
  await contextChoose(page, sound, 'Gain…')
  await page.locator('.modal.ask input').fill('-6')
  await page.locator('.modal.ask button.primary').click()
  await expect(sound).toContainText('−6 dB')
  await contextChoose(page, sound, 'Fade in (12 frames)')
  await expect.poll(async () => (await tracks()).audio[1].transitions.length, { timeout: 10_000 }).toBe(1)
  expect((await tracks()).audio[1].items[0].gain_db).toBe(-6)
  await expect(page.getByTestId('cut-mix')).toHaveAttribute('src', /^blob:/, { timeout: 15_000 })
  // D127: a new cut's audio tracks are the roles with Settings › Audio's strips; a header's right-click sets a strip setting and a role
  await expect(page.locator('.cut-head', { hasText: 'Music' })).toContainText('gain −6 dB')
  const fx = page.locator('.cut-head', { hasText: 'Effects' })
  await expect(fx).toContainText('gain −3 dB')
  await contextChoose(page, fx, 'Pan…')
  await page.locator('.modal.ask input').fill('-40')
  await page.locator('.modal.ask button.primary').click()
  await expect(fx).toContainText('70 % L · 30 % R')
  await contextChoose(page, fx, 'Volume…')
  await page.locator('.modal.ask input').fill('+18')
  await page.locator('.modal.ask button.primary').click()
  await expect(fx).toContainText('vol +18 dB')
  type Strip = { audio: { name: string; role: string | null; gain_db: number; volume_db: number; pan: number }[] }
  expect((await api<Strip>('GET', `/timelines/${tl.id}/tracks`)).audio[2]).toMatchObject({ role: 'effects', gain_db: -3, volume_db: 18, pan: -40 })
  await fx.click({ button: 'right' })
  await page.locator('.ctx-menu .item.sub', { hasText: /^Role/ }).hover()
  await page.locator('.ctx-menu .ctx-menu button.item', { hasText: /^Music$/ }).click()
  await expect.poll(async () => (await api<Strip>('GET', `/timelines/${tl.id}/tracks`)).audio[2], { timeout: 10_000 }).toMatchObject({ name: 'Music', role: 'music', gain_db: -6, volume_db: 0, pan: 0 })
  await expect(page.locator('.cut-head', { hasText: 'Music' })).toHaveCount(2)
  // AU2: a header's click shows the track in the Inspector — a slider let go is FilmCraft's value, the role from its list
  await page.locator('.cut-head', { hasText: 'Dialogue' }).click()
  const ti = page.getByTestId('track-inspector')
  await expect(ti).toContainText('dialogue track')
  const width = ti.getByLabel('Dialogue width')
  await width.focus()
  await page.keyboard.press('End')                                                             // the slider's far end, committed on the key's release
  await expect.poll(async () => (await api<Strip & { audio: { width: number }[] }>('GET', `/timelines/${tl.id}/tracks`)).audio[0].width, { timeout: 10_000 }).toBe(200)
  await expect(ti.locator('.strip-val').nth(3)).toHaveText('200 %')
  await ti.getByLabel("the track's role").selectOption('effects')
  await expect.poll(async () => (await api<Strip>('GET', `/timelines/${tl.id}/tracks`)).audio[0], { timeout: 10_000 }).toMatchObject({ name: 'Effects', role: 'effects', gain_db: -3 })
  await expect(page.locator('.cut-head.selected')).toContainText('Effects')
  // AU4: an effect on the sound's track from the Inspector's list (the fake host's two), its window, a bypass; the track prints before the mix
  type Fx = { audio: { chain: { name: string; state: string | null; bypass: boolean }[]; printed: string }[] }
  const fxOf = async () => (await api<Fx>('GET', `/timelines/${tl.id}/tracks`)).audio[1]
  const soundHead = page.locator('.cut-row', { has: page.locator('.cut-clip.k-sound') }).locator('.cut-head')
  await soundHead.click()
  await ti.getByRole('button', { name: 'Add an effect…' }).click()
  const picker = page.getByTestId('fx-picker')
  await expect(picker.locator('.fx-list li')).toHaveCount(2, { timeout: 15_000 })
  await picker.getByLabel('find an effect').fill('tape')
  await expect(picker.locator('.fx-list li')).toHaveCount(1)
  await picker.locator('.fx-list button', { hasText: 'Tape Gain' }).click()
  await expect(ti.getByTestId('fx-chain')).toContainText('Tape Gain')
  await ti.getByRole('button', { name: 'Tape Gain window' }).click()
  await expect.poll(async () => (await fxOf()).chain[0]?.state ?? '', { timeout: 10_000 }).toMatch(/^fx\//)
  await ti.getByLabel('Tape Gain on').click()                                                    // the box follows the cut's answer
  await expect.poll(async () => (await fxOf()).chain[0]?.bypass, { timeout: 10_000 }).toBe(true)
  await expect(ti.getByLabel('Tape Gain on')).not.toBeChecked()
  await ti.getByLabel('Tape Gain on').click()
  await expect(ti.getByLabel('Tape Gain on')).toBeChecked()
  await expect(soundHead).toContainText('1 fx')
  await expect.poll(async () => (await fxOf()).printed, { timeout: 20_000 }).toBe('current')        // the page's mix printed it
  await expect(page.getByTestId('cut-mix')).toHaveAttribute('src', /^blob:/, { timeout: 15_000 })
  // CE4: colour — a preset on a take, its scene's grade (an adjustment layer on the Grade track), a value, a match, a reset
  type Col = { video: { name: string; items: { id: number; kind: string; grade: { look: string; values: Record<string, number>; matched: boolean } | null }[] }[] }
  const col = () => api<Col>('GET', `/timelines/${tl.id}/tracks`)
  await takes.first().click({ position: { x: 6, y: 8 } })
  const gi = page.getByTestId('grade-inspector')
  await expect(gi).toContainText('as shot')
  await gi.getByLabel('apply a preset').selectOption('Golden Dusk')
  await expect.poll(async () => (await col()).video[0].items[0].grade?.values.temperature, { timeout: 10_000 }).toBe(35)
  await expect(takes.first()).toContainText('graded')
  await contextChoose(page, takes.first(), 'Grade its scene')
  await expect(page.locator('.cut-head', { hasText: 'Grade' })).toHaveCount(1)
  await expect(page.locator('.cut-clip.k-adjustment')).toHaveCount(1)
  await expect(page.locator('.cut-clip.k-adjustment')).toHaveClass(/\bselected\b/)
  await expect(gi).toContainText("the scene's grade")
  await gi.getByLabel('exposure').focus()
  await page.keyboard.press('End')
  await expect.poll(async () => (await col()).video.at(-1)!.items[0].grade?.values.exposure, { timeout: 10_000 }).toBe(5)
  await gi.getByLabel('the look').selectOption({ label: 'Teal & Orange' })
  await expect.poll(async () => (await col()).video.at(-1)!.items[0].grade?.look, { timeout: 10_000 }).toBe('builtin:look-teal-orange')
  await takes.nth(1).click({ button: 'right', position: { x: 6, y: 8 } })
  await page.locator('.ctx-menu .item.sub', { hasText: /^Match its colour to/ }).hover()
  await page.locator('.ctx-menu .ctx-menu button.item').first().click()
  await expect.poll(async () => (await col()).video[0].items[1].grade?.matched, { timeout: 10_000 }).toBe(true)
  await expect(takes.nth(1)).toContainText('matched')
  await contextChoose(page, takes.nth(1), 'Reset its colour')
  await expect.poll(async () => (await col()).video[0].items[1].grade, { timeout: 10_000 }).toBeNull()
  // RC2f: the first take leaves its scene's grade — the layer cut away over it, the scene's grade its own Lumetri
  await contextChoose(page, takes.first(), 'Make its grade independent')
  await expect.poll(async () => (await col()).video[0].items[0].grade?.values.exposure, { timeout: 10_000 }).toBe(5)
  await expect.poll(async () => (await col()).video.at(-1)!.items.every((i) => i.kind === 'adjustment'), { timeout: 10_000 }).toBe(true)
  // CE5: a caption at the playhead (the caption row), edited and moved; a marker on the ruler; the movie as ProRes with the captions beside it
  type Cap = { captions: { name: string; captions: { id: number; text: string; start: number }[] }[]; markers: { id: number; name: string; kind: string }[] }
  const capOf = () => api<Cap>('GET', `/timelines/${tl.id}/tracks`)
  await page.keyboard.press('Home')
  const space = page.locator('.cut-tracks')
  await space.click({ button: 'right', position: { x: 600, y: 8 } })
  await page.locator('.ctx-menu button.item', { hasText: /^Add a caption at the playhead…$/ }).click()
  await page.locator('.modal.ask input').fill('Over here.')
  await page.locator('.modal.ask button.primary').click()
  const cap = page.locator('.cut-cap')
  await expect(cap).toHaveCount(1)
  await expect(cap).toContainText('Over here.')
  await contextChoose(page, cap, 'Edit the caption…')
  await page.locator('.modal.ask input').fill('Over there.')
  await page.locator('.modal.ask button.primary').click()
  await expect(cap).toContainText('Over there.')
  await expect(page.getByTestId('caption-text')).toHaveText('Over there.')
  const cb = (await cap.boundingBox())!
  await page.mouse.move(cb.x + cb.width / 2, cb.y + cb.height / 2)
  await page.mouse.down()
  await page.mouse.move(cb.x + cb.width / 2 + 30, cb.y + cb.height / 2, { steps: 4 })
  await page.mouse.up()
  await expect.poll(async () => (await capOf()).captions[0].captions[0].start, { timeout: 10_000 }).toBeGreaterThan(0)
  await space.click({ button: 'right', position: { x: 600, y: 8 } })
  await page.locator('.ctx-menu button.item', { hasText: /^Add a marker at the playhead…$/ }).click()
  await page.locator('.modal.ask input').fill('check the light')
  await page.locator('.modal.ask button.primary').click()
  await expect(page.locator('.cut-marker:not(.chapter)')).toHaveCount(1)
  await contextChoose(page, page.locator('.cut-marker:not(.chapter)'), 'Delete the marker')
  await expect(page.locator('.cut-marker:not(.chapter)')).toHaveCount(0)
  const del = page.getByTestId('delivery')
  await del.getByLabel("the movie's format").selectOption('prores')
  await del.getByRole('checkbox', { name: 'captions burned in' }).check()
  await del.getByLabel('captions beside it').selectOption('srt')
  type MovieJob = { id: string; status: string; recipe: { delivery?: string; burn_captions?: boolean; captions_file?: string | null }; result: { path?: string; captions_file?: string | null } }
  const jobsBefore = (await api<{ items: MovieJob[] }>('GET', '/jobs')).items.map((j) => j.id)
  await page.getByRole('button', { name: 'Render the movie' }).click()
  await expect.poll(async () => (await api<{ items: MovieJob[] }>('GET', '/jobs')).items.find((j) => !jobsBefore.includes(j.id))?.status, { timeout: 60_000 }).toBe('done')
  const movie = (await api<{ items: MovieJob[] }>('GET', '/jobs')).items.find((j) => !jobsBefore.includes(j.id))!
  expect(movie.result.path).toMatch(/\.mov$/)
  expect(movie.result.captions_file).toMatch(/\.srt$/)
})

test("Settings › Audio (D127): the loudness target and a track role's strip are set in the general Settings and saved (B2a)", async ({ page }) => {
  type Audio = { audio: { loudness_lufs: number | null; music: { gain_db: number; volume_db: number; pan: number; width: number } } }
  const before = (await api<Audio>('GET', '/settings')).audio
  await openShell(page, 'bin')
  await page.locator('button[aria-label="app menu"]').click()
  await page.locator('.menu button', { hasText: /^Settings…/ }).click()
  const loud = page.getByLabel('loudness target')
  await loud.scrollIntoViewIfNeeded()
  await expect(loud).toHaveValue(String(before.loudness_lufs))
  await loud.fill('-14')
  await page.getByLabel('music gain').fill('-9')
  await page.getByLabel('music width').fill('140')
  await page.locator('.modal .foot button.primary', { hasText: 'Save' }).click()
  await expect(page.locator('.modal-backdrop')).toHaveCount(0)
  const after = (await api<Audio>('GET', '/settings')).audio
  expect([after.loudness_lufs, after.music.gain_db, after.music.width, after.music.volume_db]).toEqual([-14, -9, 140, 0])
  await api('PUT', '/settings', { audio: before })                                          // the other scenarios' cuts keep the defaults
})

test('a stage (P13 / ST1, D81): a new stage gets a set and a figure from the Library, the Outliner lists them, the document saves and survives a reload (Shots, B2a)', async ({ page }) => {
  await clayShot(page, 'Alley at night')
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await page.locator('.stage-empty button', { hasText: /^Add set · room$/ }).click()
  await libAdd(page, 'figures', 'Adult')                        // the Library's figure card
  await section(page, 'scene')
  await expect(page.locator('.outl-row[data-row="object"]')).toHaveCount(2)                                              // D119 (SC1): one outliner — the stage, the objects, the cameras
  await expect(page.locator('.outl-row[data-row="camera"]')).toHaveCount(1)
  await expect(page.locator('.outl-row.active .name')).toHaveText('Figure 1')                                            // the last added is selected; its editor under its row
  await expect(page.locator('.w-panel .stage-insp h4')).toContainText('Figure 1')
  await expect.poll(async () => (await api<{ items: { name: string; revision: number; objects: { kind: string }[] }[] }>('GET', '/stages')).items.find((s) => s.name === 'Alley at night')?.objects.length ?? 0, { timeout: 10_000 }).toBe(2)
  const before = (await api<{ items: { id: string; name: string; revision: number }[] }>('GET', '/stages')).items.find((s) => s.name === 'Alley at night')!
  expect(before.revision).toBeGreaterThanOrEqual(1)
  // camera view shows the framing rectangle; the free view does not (D121 AW4: the camera pill over the viewport looks through)
  await expect(page.locator('.frame-guides')).toHaveCount(0)
  await page.locator('.cam-pill .cam-pill-main').click()
  await expect(page.locator('.frame-guides')).toBeVisible()
  await expect(page.locator('.cam-pill .cam-pill-main')).toContainText('35 mm')
  await page.screenshot({ path: 'node_modules/.e2e/stage-camera-view.png' })                     // a look for the journal: the framing rectangle over the set
  await page.reload()
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Shots/)
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await freeView(page)                                                                                      // reopened through its camera
  await section(page, 'scene')
  await expect(page.locator('.outl-row[data-row="object"]')).toHaveCount(2)
  // D119 (SC1): the camera is an object — its row opens its editor and its body in the free view is clicked to select it
  await page.locator('.outl-row[data-row="camera"]').first().click()
  await expect(page.locator('.outl-row[data-row="camera"].active .row-editor h4')).toContainText('Camera 1')
  await page.locator('.outl-row[data-row="camera"] .name').first().click()                                               // again (on its name: the editor is part of the row): closed
  await expect(page.locator('.row-editor')).toHaveCount(0)
  await page.locator('.outl-row[data-row="stage"]').click()
  await expect(page.locator('.outl-row[data-row="stage"] .row-editor')).toContainText('the project format')
  const camId = (await api<{ items: { name: string; cameras: { id: string }[] }[] }>('GET', '/stages')).items.find((s) => s.name === 'Alley at night')!.cameras[0].id
  await page.locator('canvas.stage-canvas').hover()
  const at = await page.evaluate((id) => (window as unknown as { __loom2Stage: { cameraScreen: (id: string) => { x: number; y: number } | null } }).__loom2Stage.cameraScreen(id), camId)
  expect(at).not.toBeNull()
  await page.mouse.click(at!.x, at!.y)
  await expect(page.locator('.outl-row[data-row="camera"].active .row-editor h4')).toContainText('Camera 1')
  // the rotate tool after a camera (the author, 2026-10-22: it moved the object instead): the object's gizmo follows the tool
  const mode = () => page.evaluate(() => (window as unknown as { __loom2Stage: { gizmoMode: () => string } }).__loom2Stage.gizmoMode())
  await page.locator('button.cmd-btn[aria-label^="Rotate"]').first().click()
  await expect.poll(mode).toBe('rotate')                                                                                      // the camera's body turns under Rotate (the author, later that day)
  await page.locator('.outl-row[data-row="object"] .name').first().click()
  await expect.poll(mode).toBe('rotate')
  await page.locator('button.cmd-btn[aria-label^="Move"]').first().click()
  await expect.poll(mode).toBe('translate')
})

test('posing (P13 / ST2, D81): the Poses tab applies a preset, mirrors it, edits one joint by number and saves the pose to the project library (Shots, B2a)', async ({ page }) => {
  await clayShot(page, 'Crossing')
  const dialog = page.locator('.modal.ask')
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await page.locator('.stage-empty button', { hasText: /Adult/ }).click()                       // the empty-stage card adds (and selects) a figure
  await section(page, 'motion')
  await expect(page.locator('#anim-sec-motion .stage-panel:not(.motion-lib) .head b')).toHaveText('Figure 1')
  type Doc = { name: string; objects: { kind: string; pose: { preset: string; joints: Record<string, number[]> } | null }[] }
  const figure = async () => (await api<{ items: Doc[] }>('GET', '/stages')).items.find((s) => s.name === 'Crossing')?.objects.find((o) => o.kind === 'mannequin')   // the save is debounced: may be absent at first
  const WALK: Record<string, number[]> = { r_shoulder: [22, 0, -6], r_elbow: [0, 0, 0] }                                 // builders.ts POSES.walk (the right arm)
  await libAdd(page, 'poses', 'walk')
  await expect.poll(async () => (await figure())?.pose?.preset, { timeout: 10_000 }).toBe('walk')
  // D121: pose mode by the selected figure's pill over the viewport (the pickers no longer follow the Motion section on screen)
  await page.locator('.pose-pill button').click()
  await expect(page.locator('.pose-pill button')).toHaveClass(/active/)
  // the mouse on the figure: a click on the elbow's picker selects that joint (the rotate gizmo moves there)
  const at = async (what: string) => (await page.evaluate((w) => (window as unknown as { __loom2Stage: { screenOf: (at: string) => { x: number; y: number } | null } }).__loom2Stage.screenOf(w), what))!
  const elbow = await at('r_elbow')
  await page.mouse.click(elbow.x, elbow.y)
  await expect(page.locator('#anim-sec-motion .stage-panel:not(.motion-lib) select').last()).toHaveValue('r_elbow')
  // the author, 2026-10-22: the tool buttons leave the joint alone, and selecting the same figure again keeps it
  await page.locator('button.cmd-btn[aria-label^="Rotate"]').first().click()
  await expect(page.locator('#anim-sec-motion .stage-panel:not(.motion-lib) select').last()).toHaveValue('r_elbow')
  await expect.poll(() => page.evaluate(() => (window as unknown as { __loom2Stage: { gizmoMode: () => string } }).__loom2Stage.gizmoMode())).toBe('rotate')
  await page.evaluate(() => { const w = window as unknown as { __loom2Stage: { select: (id: string) => void; state: () => { current: { objects: { id: string }[] } } } }; w.__loom2Stage.select(w.__loom2Stage.state().current.objects[0].id) })
  await expect(page.locator('#anim-sec-motion .stage-panel:not(.motion-lib) select').last()).toHaveValue('r_elbow')
  // a click on the right hand's handle puts a translate gizmo there; dragging its centre moves the hand, the forearm and upper arm follow (two-bone IK)
  const hand = await at('r_arm')
  await page.mouse.click(hand.x, hand.y)
  await expect(page.locator('#anim-sec-motion .stage-panel:not(.motion-lib) select').last()).toHaveValue('')
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
  await page.locator('#anim-sec-motion .stage-panel:not(.motion-lib) select').last().selectOption('r_elbow')
  const x = page.locator('#anim-sec-motion .stage-panel .vec input').first()                                 // the joint's field (D119 SC1: the figure's editor under its row has vecs too)
  await x.fill('-90'); await x.dispatchEvent('change')
  await expect.poll(async () => (await figure())?.pose?.joints.r_elbow?.[0], { timeout: 10_000 }).toBe(-90)
  // save it to the project's library and see it back as a card
  await page.locator('.stage-panel button', { hasText: /^Save pose/ }).click()
  await dialog.locator('input').fill('crossing step')
  await dialog.locator('button.primary').click()
  await page.locator('.lib-row[data-group="poses"] [data-preset-panel-btn]').click()
  await expect(page.locator('[data-preset-panel] button.preset-icon[aria-label="crossing step"]')).toBeVisible()
  const lib = await api<{ poses: Record<string, { preset: string | null; joints: Record<string, number[]> }> }>('GET', '/stages/poses')
  expect(lib.poses['crossing step'].preset).toBe('walk')
  expect(lib.poses['crossing step'].joints.r_elbow[0]).toBe(-90)
  await page.screenshot({ path: 'node_modules/.e2e/stage-poses.png' })
})

test("the pose editor (AP1b, D141): a crouch stands on the character's feet, the feet pinned stay as the hips turn, Save for ‹character› keeps it in Cast, the crouch preset then takes it, the bench lists it (Shots and World’s Sheet, B2a)", async ({ page }) => {
  test.setTimeout(90_000)
  const name = `Mara ${Date.now().toString(36)}`
  type Pose = { preset: string; joints: Record<string, number[]>; ground: number; pins: Record<string, number[]>; contacts: Record<string, { object_id: string; joint: string | null }>; gaze: { camera: boolean } | null }
  type ProfileLite = { id: string; versions: { id: string; poses: Record<string, Pose> }[] }
  const p = await api<ProfileLite>('POST', '/story/profiles', { name, cls: 'character', appearance: `${name}, a fisher` })
  const st = await api<{ id: string } & Record<string, unknown>>('POST', '/stages', { name: `Quay ${name}` })
  await api('PUT', `/stages/${st.id}`, { ...st, objects: [{ id: 'obj_mara', kind: 'mannequin', name, preset: 'adult', profile_id: p.id, version: null, body: null }] })
  const figure = async () => (await api<{ objects: { pose: Pose | null }[] }>('GET', `/stages/${st.id}`)).objects[0].pose
  await clayOn(page, st.id, `Quay ${name}`)
  await page.locator('.outl-row[data-row="object"]').filter({ has: page.locator('.name', { hasText: name }) }).click()
  await section(page, 'motion')
  await libAdd(page, 'poses', 'crouch')
  await expect.poll(async () => (await figure())?.ground ?? 0, { timeout: 10_000 }).toBeGreaterThan(0.05)    // AP1a: the crouch's drop onto its feet
  // the pins: both feet from the Pins row's chips
  const pins = page.locator('.lib-row[data-group="pins"]')
  await pins.locator('button[data-end="r_foot"]').click()
  await pins.locator('button[data-end="l_foot"]').click()
  await expect(pins.locator('button[aria-pressed="true"]')).toHaveCount(2)
  await expect.poll(async () => Object.keys((await figure())?.pins ?? {}).sort().join(), { timeout: 10_000 }).toBe('l_foot,r_foot')
  // AP1b, the rest: the right hand pinned and held to the figure's own hips (the Held-to row), the look at the camera (the Looks-at row)
  await pins.locator('button[data-end="r_hand"]').click()
  await page.locator('.lib-row[data-group="contacts"] select[data-end="r_hand"]').selectOption('self:root')
  await expect.poll(async () => (await figure())?.contacts?.r_hand?.object_id ?? null, { timeout: 10_000 }).toBe('self')
  expect((await figure())!.contacts.r_hand.joint).toBe('root')
  await page.locator('.lib-row[data-group="gaze"] select').selectOption('camera')
  await expect.poll(async () => (await figure())?.gaze?.camera ?? false, { timeout: 10_000 }).toBe(true)
  await page.locator('.lib-row[data-group="gaze"]').scrollIntoViewIfNeeded()
  await page.screenshot({ path: 'node_modules/.e2e/ap1b-contacts-rows.png' })
  await page.locator('.pose-pill button').click()                                                           // Pose: the rings at the pins with the pickers
  const at = async (what: string) => (await page.evaluate((w) => (window as unknown as { __loom2Stage: { screenOf: (at: string) => { x: number; y: number } | null } }).__loom2Stage.screenOf(w), what))!
  const foot = await at('r_leg'), hip0 = (await figure())!.joints.r_hip
  // the hips turned by number: the pinned legs bend to keep the feet where they were
  await page.locator('.stage-panel select').last().selectOption('root')
  const y = page.locator('#anim-sec-motion .stage-panel .vec input').nth(1)
  await y.fill('30'); await y.dispatchEvent('change')
  await expect.poll(async () => (await figure())?.joints.root?.[1], { timeout: 10_000 }).toBe(30)
  expect((await figure())!.joints.r_hip).not.toEqual(hip0)
  await expect.poll(async () => { const now = await at('r_leg'); return Math.hypot(now.x - foot.x, now.y - foot.y) }, { timeout: 5_000 }).toBeLessThan(3)
  // a look: the figure framed from its right-click, the joint let go (the gizmo away), the rings at the pinned feet
  await page.locator('.stage-panel select').last().selectOption('')
  await page.locator('.outl-row[data-row="object"]').filter({ has: page.locator('.name', { hasText: name }) }).click({ button: 'right' })
  await page.locator('.ctx-menu button.item', { hasText: 'Frame the selection' }).click()
  await page.waitForTimeout(600)
  await page.screenshot({ path: 'node_modules/.e2e/ap1b-pins.png' })
  await page.locator('.lib-row[data-group="pins"]').scrollIntoViewIfNeeded()
  await page.screenshot({ path: 'node_modules/.e2e/ap1b-pins-row.png' })
  // Save for ‹character›: the character's own crouch
  await page.locator('.stage-panel button', { hasText: `Save for ${name}…` }).click()
  const dialog = page.locator('.modal.ask')
  await expect(dialog.locator('input')).toHaveValue('crouch')
  await dialog.locator('button.primary').click()
  await expect.poll(async () => (await api<ProfileLite>('GET', `/story/profiles/${p.id}`)).versions[0].poses.crouch?.joints.root?.[1] ?? null, { timeout: 10_000 }).toBe(30)
  {                                                                                                         // AP1b, the rest: the saved pose keeps the hold to its own hips and the look at the camera
    const saved = (await api<ProfileLite>('GET', `/story/profiles/${p.id}`)).versions[0].poses.crouch
    expect(saved.contacts.r_hand).toEqual({ object_id: 'self', joint: 'root' }); expect(saved.gaze?.camera).toBe(true)
  }
  // a stand, then the crouch preset again: on this character it is its own
  await page.locator('.stage-panel button', { hasText: /^Reset$/ }).click()
  await expect.poll(async () => Object.keys((await figure())?.pins ?? {}).length, { timeout: 10_000 }).toBe(0)
  await libAdd(page, 'poses', 'crouch')
  await expect.poll(async () => (await figure())?.joints.root?.[1], { timeout: 10_000 }).toBe(30)
  expect(Object.keys((await figure())!.pins).sort()).toEqual(['l_foot', 'r_foot', 'r_hand'])
  expect((await figure())!.contacts.r_hand.object_id).toBe('self')
  // the skeleton bench (World's Sheet) lists the character's poses
  await openBuild(page, 'character', p.id)
  await page.locator('.cast-body button', { hasText: 'body' }).click()                                    // a body of its own (the default adult's)
  await page.locator('.cast-body button', { hasText: /^Skeleton…/ }).click()
  await expect(page.locator('.skel-parts [data-group="poses"] [data-pose="crouch"]')).toContainText('its starter pose · 3 pinned')
  await page.locator('.skel-parts [data-group="poses"]').scrollIntoViewIfNeeded()
  await page.screenshot({ path: 'node_modules/.e2e/ap1b-bench-poses.png' })
})

test('a shot (P13 / ST3, D81): the Shot tab renders the five passes as stage-pass assets on the stage\'s album page, then the fake engine makes a shot with lineage to the clay pass (Shots, B2a)', async ({ page }) => {
  await clayShot(page, 'Courtyard')
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await page.locator('.stage-empty button', { hasText: /Add set · room/ }).click()
  await libAdd(page, 'figures', 'Adult')
  await fromStageIn(page)                                                                                     // D121: the frame is made in Image
  await expect(page.locator('.shot-tab .method.active b')).toHaveText('Clay reference')
  await expect(page.locator('[data-testid="world-sketches"] .w-foot .estimate')).toContainText(/Klein/, { timeout: 15_000 })      // the preview names the method's model
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
  const go = page.locator('[data-testid="world-sketches"] .w-foot button.primary', { hasText: /^Render frame/ })
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

test('a clip (P13 / ST4, D81): the camera is keyed on the timeline, the depth sequence renders as a video asset, and the fake engine animates the shot through the IC-LoRA with lineage to both (Shots, B2a)', async ({ page }) => {
  await clayShot(page, 'Dolly')
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await page.locator('.stage-empty button', { hasText: /Adult/ }).click()
  // a shot first (the clip starts from it) — D121: made in Image › From a stage
  await fromStageIn(page)
  const go = page.locator('[data-testid="world-sketches"] .w-foot button.primary', { hasText: /^Render frame/ })
  await expect(go).toBeEnabled({ timeout: 15_000 })
  await go.click()
  await expect(page.locator('.shot-tab .shot-thumb')).toHaveCount(1, { timeout: 45_000 })
  await page.locator('.shot-tab .shot-thumb').first().click()                                               // the clip starts from this shot
  await expect(page.locator('.shot-tab .shot-thumb.start')).toHaveCount(1)
  // keys: the camera at frame 0, then a move at frame 8 (a keyed camera takes the edit as a key); the range is 0–8 (9 frames = 8n + 1)
  await toLevel(page, 'clay')
  const tl = page.locator('.stage-timeline')
  await tl.locator('button', { hasText: /^Key camera$/ }).click()
  await tl.locator('.frame-field').fill('8'); await tl.locator('.frame-field').dispatchEvent('change')
  await section(page, 'camera')
  const box = (await page.locator('canvas.stage-canvas').boundingBox())!
  await page.mouse.click(box.x + 60, box.y + box.height - 40)                                                // empty floor, bottom-left (the gizmo bar sits top-left; toasts bottom-right, over the viewport since AN1): nothing selected, Selection shows the camera
  await section(page, 'scene')
  await page.locator('.outl-row[data-row="camera"]').first().click()                                        // D119 (SC1): the camera's editor under its row
  await expect(page.locator('.w-panel .stage-insp h4', { hasText: 'Camera 1' })).toBeVisible()            // D95 (AN1): Selection shows the stage, then its active camera
  const z = page.locator('.w-panel .stage-insp .vec input').nth(2)                                           // the camera's position z
  await z.fill('2'); await z.dispatchEvent('change')
  const rangeEnd = tl.locator('.range-field input').nth(1)
  await rangeEnd.fill('8'); await rangeEnd.dispatchEvent('change')
  type Doc = { id: string; name: string; revision: number; range: { start: number; end: number }; keyframes: { camera: Record<string, { frame: number; pos: number[] }[]> }; passes: { guides?: Record<string, { asset_id: string; frames: number; fps: number }> }[] }
  const doc = async () => (await api<{ items: Doc[] }>('GET', '/stages')).items.find((s) => s.name === 'Dolly')!
  await expect.poll(async () => { const d = await doc(); const ks = Object.values(d.keyframes.camera)[0] ?? []; return ks.map((k) => k.frame).join(',') + '|' + d.range.end }, { timeout: 10_000 }).toBe('0,8|8')
  expect((Object.values((await doc()).keyframes.camera)[0])[1].pos[2]).toBe(2)
  expect(tl.locator('.key-mark')).toHaveCount(2)
  // the sequence: nine depth frames become one video asset on the album page, recorded under the camera's passes entry (D121: the Stage clip card)
  await perfCardOf(page, 'Stage clip')
  await expect(page.locator('.stage-clip .shot-thumb.start')).toHaveCount(1)                                // the start picked in Image
  await page.locator('.stage-clip button', { hasText: /^Render sequence$/ }).click()
  await expect.poll(async () => (await doc()).passes[0]?.guides?.depth?.frames ?? 0, { timeout: 60_000 }).toBe(9)
  const guide = (await doc()).passes[0].guides!.depth
  const gasset = await api<AssetLite & { kind: string; lineage_kind: string | null; frames: number | null; fps: number | null; params: { pass: string; keypoints: unknown[] } }>('GET', `/assets/${guide.asset_id}`)
  expect(gasset.kind).toBe('video'); expect(gasset.lineage_kind).toBe('stage-pass'); expect(gasset.frames).toBe(9); expect(gasset.params.pass).toBe('depth-sequence'); expect(gasset.params.keypoints).toHaveLength(9)
  await expect(page.locator('.stage-clip .guide-state')).toContainText('9 frames')
  // Render clip ▶ (the foot): the I2V job with the guide; the fake engine decodes nine frames; the clip carries lineage to the shot and the guide
  const animate = page.locator('.s-foot button.primary', { hasText: /^Render clip/ })
  if (JSON.parse(process.env.LOOM2_E2E ?? '{}').variant === 'open') {                                       // D26: LTX-2.3 is full-only — the section says so
    await expect(page.locator('.stage-clip .clip-section')).toContainText('No clip model in this build')
    await expect(animate).toBeDisabled()
    return
  }
  await expect(animate).toBeEnabled()
  await animate.click()
  await expect(page.locator('.stage-clip .clip-thumb')).toHaveCount(1, { timeout: 120_000 })
  const startId = await page.locator('.stage-clip .shot-thumb.start').getAttribute('src')
  const clips = (await api<{ items: (AssetLite & { kind: string; parents: string[]; lineage_kind: string | null; frames: number | null; origin: { suite: string; surface: string } | null; params: { recipe: { guide: { kind: string } } } })[] }>('GET', '/assets?suite=stage&sort=created_desc&limit=20')).items.filter((a) => a.kind === 'video' && a.lineage_kind === 'stage-shot')
  expect(clips).toHaveLength(1)
  expect(clips[0].frames).toBe(9); expect(clips[0].origin).toMatchObject({ suite: 'stage', surface: 'clip' }); expect(clips[0].params.recipe.guide.kind).toBe('depth')
  expect(clips[0].parents).toContain(guide.asset_id); expect(clips[0].parents.length).toBe(2)
  expect(startId).toContain(clips[0].parents[0])                                                              // the start shot is the first parent
  await page.screenshot({ path: 'node_modules/.e2e/stage-clip.png' })
})

test("a pose-driven shot (19 / CN4, D87): the Render tab's Animate method takes the pose sequence on Wan's grid, and the fake engine performs it with the picked result as the character — lineage to both, in both variants (Shots, B2a)", async ({ page }) => {
  const name = `Perform ${Date.now().toString(36)}`
  await clayShot(page, name)
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await page.locator('.stage-empty button', { hasText: /Adult/ }).click()
  await fromStageIn(page)                                                                                     // D121: the frame in Image
  const go = page.locator('[data-testid="world-sketches"] .w-foot button.primary', { hasText: /^Render frame/ })
  await expect(go).toBeEnabled({ timeout: 15_000 })
  await go.click()
  await expect(page.locator('.shot-tab .shot-thumb')).toHaveCount(1, { timeout: 45_000 })
  await page.locator('.shot-tab .shot-thumb').first().click()                                               // the character: the picked result
  await toLevel(page, 'clay')
  const rangeEnd = page.locator('.stage-timeline .range-field input').nth(1)
  await rangeEnd.fill('8'); await rangeEnd.dispatchEvent('change')                                          // 9 frames: 4n + 1 on Wan's grid
  // the method: Animate — the guide is the pose sequence (Depth is disabled), at the model's grid (D121: the Stage clip card)
  await perfCardOf(page, 'Stage clip')
  await page.locator('.stage-clip button[aria-label="clip method animate"]').click()
  await expect(page.locator('.stage-clip button[aria-label="clip method animate"]')).toHaveClass(/active/)
  await expect(page.locator('.stage-clip .segmented button', { hasText: /^Depth$/ })).toBeDisabled()
  await expect(page.locator('.stage-clip .clip-section .hint').last()).toContainText('for 77 frames')                 // the E19 note sits in its ? (D116)
  type Doc = { id: string; name: string; passes: { guides?: Record<string, { asset_id: string; frames: number; size: { w: number; h: number } }> }[] }
  const doc = async () => (await api<{ items: Doc[] }>('GET', '/stages')).items.find((s) => s.name === name)!
  await page.locator('.stage-clip button', { hasText: /^Render sequence$/ }).click()
  await expect.poll(async () => (await doc()).passes[0]?.guides?.pose?.frames ?? 0, { timeout: 60_000 }).toBe(9)
  const guide = (await doc()).passes[0].guides!.pose
  expect(guide.size.w % 16).toBe(0); expect(guide.size.h).toBe(480)                                        // Wan's 480p, on the 16 grid
  await page.locator('.s-foot button.primary', { hasText: /^Render clip/ }).click()
  await expect(page.locator('.stage-clip .clip-thumb')).toHaveCount(1, { timeout: 120_000 })
  type Clip = AssetLite & { kind: string; parents: string[]; model_id: string | null; frames: number | null; params: { recipe: { guide: { kind: string } } } }
  const caps = await api<{ stage: { animate: { model_id: string } } }>('GET', '/capabilities')
  const clips = (await api<{ items: Clip[] }>('GET', '/assets?kind=video&suite=stage&sort=created_desc&limit=20')).items.filter((a) => a.model_id === caps.stage.animate.model_id)
  expect(clips.length).toBeGreaterThanOrEqual(1)
  expect(clips[0].frames).toBe(9); expect(clips[0].params.recipe.guide.kind).toBe('pose'); expect(clips[0].parents).toContain(guide.asset_id)
})

test('a 3D prop (P18, D84): "Make a 3D prop…" on a tile says its cost, the fake engine answers with a GLB, the mesh asset lands with lineage and a thumbnail, and the Stage library places it (the Bin and Shots, B2a)', async ({ page }) => {
  const srcId = (await sketchPics(6)).at(-1)!.id   // a plain picture in the Sketches (B4)
  await openShell(page, 'bin')
  await openHome(page, 'world/sketches', 'pictures')
  await page.locator(`[data-testid="bin-grid"] .w-tile[data-id="${srcId}"]`).click()
  const starts = async () => { await page.locator('[data-testid="bin-inspector"] button', { hasText: 'Start from it' }).click() }
  if (JSON.parse(process.env.LOOM2_E2E ?? '{}').variant === 'open') {                                       // D17 / D26: DINOv3 keeps Pixal3D full-only
    await starts()
    await expect(page.locator('.ctx-menu button.item', { hasText: 'New angle…' })).toBeEnabled()
    await expect(page.locator('.ctx-menu button.item', { hasText: 'Make a 3D prop…' })).toBeDisabled()         // the entry stays, greyed: no model in this build
    const mc = await api<{ model_id: string | null; why: string | null }>('GET', '/capabilities').then((c) => (c as unknown as { mesh: { model_id: string | null; why: string | null } }).mesh)
    expect(mc.model_id).toBeNull(); expect(mc.why).toContain('DINOv3')
    return
  }
  await starts()
  await page.locator('.ctx-menu button.item', { hasText: 'Make a 3D prop…' }).click()
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
  expect((await api<{ path: string }>('GET', `/bin/things/${m.id}`)).path).toBe('world/sketches')          // B4: the model lands beside its picture
  // the Stage library lists it; one click places it; the viewport loads the GLB
  await clayShot(page, `Props ${Date.now().toString(36)}`)
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await libAdd(page, 'meshes', '3D model')                                                                // the Scene's Meshes + (proto01_UIcast CF9: named by source)
  await expect(page.locator('.w-panel .stage-insp h4')).toContainText('Mesh 1')
  await expect.poll(() => page.evaluate(() => (window as unknown as { __loom2Stage: { meshes: () => { loaded: string[]; failed: Record<string, string> } } }).__loom2Stage.meshes().loaded.length), { timeout: 15_000 }).toBe(1)
  await expect.poll(async () => (await api<{ params: { thumb_source?: string } }>('GET', `/assets/${m.id}`)).params.thumb_source, { timeout: 15_000 }).toBe('client')   // the viewport's fitted view became the thumbnail
  await page.screenshot({ path: 'node_modules/.e2e/stage-prop.png' })
  // proto01_UIcast CF8: the loose mesh becomes a Cast prop from its editor — the model its, the picture it was made from its hero, the object bound
  await page.locator('.w-panel button[data-verb="cast-prop"]').click()
  await page.locator('.ctx-menu button.item', { hasText: 'New prop…' }).click()
  await dialog.locator('input').fill('Lamp')
  await dialog.locator('button.primary').click()
  await expect(page.locator('.toast', { hasText: 'Lamp is a Cast prop' })).toBeVisible()
  type PropLite = { id: string; name: string; cls: string; versions: { model_asset_id: string | null; hero_asset_id: string | null }[] }
  const lamp = async () => (await api<{ items: PropLite[] }>('GET', '/story/profiles')).items.find((p) => p.name === 'Lamp')
  await expect.poll(async () => (await lamp())?.versions[0].model_asset_id, { timeout: 10_000 }).toBe(m.id)
  expect((await lamp())!.cls).toBe('prop')
  await expect.poll(async () => (await lamp())?.versions[0].hero_asset_id, { timeout: 10_000 }).toBe(srcId)
  await expect(page.locator('.outl-group[data-group-rows="props"] .outl-row[data-row="object"]')).toHaveCount(1)   // bound: under Props now
  await expect(page.locator('.outl-group[data-group-rows="meshes"] .outl-row[data-row="object"]')).toHaveCount(0)
})

test('a prop (D110 PS1–PS2, D125): Cast\'s props class lists the props (the old Props link opens it, the characters class hides them); "Make the 3D model…" says its cost, the fake engine\'s GLB lands stood upright as the version\'s model, and the page shows it turning (World’s Sheet and Shots, B2a)', async ({ page }) => {
  test.setTimeout(120_000)
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const name = `Crate ${Date.now().toString(36)}`
  const prop = await api<{ id: string; current: string }>('POST', '/story/profiles', { name, cls: 'prop', hero_asset_id: img, appearance: 'an old wooden slatted crate' })
  await openBuild(page, 'prop', prop.id)                                                                    // D157: World's Props, the prop's Sheet
  await expect(page.locator('.w-rail-btn[aria-label="Props"]')).toHaveClass(/active/)
  await expect(page.locator('[data-testid="world-header"]')).toContainText(name)
  const section = page.locator('[data-testid="world-build"] .prop-model')
  await expect(section).toBeVisible()
  await expect(section.locator('.model-view.empty')).toBeVisible()
  const make = section.locator('button', { hasText: 'Make the 3D model' })
  if (JSON.parse(process.env.LOOM2_E2E ?? '{}').variant === 'open') {                                       // D128: no image → 3D model under open (E33 owed) …
    await expect(make).toBeDisabled()
    await expect(section.locator('[data-status]')).toContainText('import its model as a GLB')
    await expect(section.locator('button', { hasText: 'Import a 3D model (GLB)' })).toBeEnabled()           // … the import is there in every build
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
  await clayShot(page, 'Props scene')
  await libAdd(page, 'props', name)                                                                        // the Scene's Props +
  await expect(page.locator('.w-panel .stage-insp h4')).toContainText(name)
  await expect(page.locator('.stage-insp [aria-label="the mesh\'s prop"] button[aria-pressed="true"]')).toHaveAttribute('aria-label', name)
  await expect.poll(() => page.evaluate(() => (window as unknown as { __loom2Stage: { meshes: () => { loaded: string[] } } }).__loom2Stage.meshes().loaded.length), { timeout: 15_000 }).toBe(1)
  await expect(page.locator('.outl-row .bound-tag', { hasText: name })).toBeVisible()
  await expect.poll(async () => {
    const stages = await api<{ items: { name: string; objects: { kind: string; asset_id: string | null; profile_id: string | null }[] }[] }>('GET', '/stages')
    const s = stages.items.find((x) => x.name === 'Props scene')
    return s?.objects.filter((o) => o.kind === 'mesh').map((o) => `${o.profile_id} ${o.asset_id}`).join(',')
  }, { timeout: 10_000 }).toBe(`${prop.id} ${v.model_asset_id}`)                                           // saved bound, with the version's model
})

test('a final shot (D111 PS5a–c): "Make the final shot…" splits a scene into its layers — the plate, a character, a prop, the shadows — and their passes land in a final record at F16; the plate is a Stage shot of the bare set, projected by Stage into its frames; the character layer is performed by Wan Animate and matted by SAM 3; the assembly makes the clip (Shots, B2a)', async ({ page }) => {
  test.setTimeout(120_000)
  const made = await clayShot(page, 'Final scene')
  const dialog = page.locator('.modal.ask')
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  // a character with an animation reference, bound to the figure (PS5c performs it)
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const who = await api<{ id: string; name: string }>('POST', '/story/profiles', { name: `Fin ${Date.now().toString(36)}`, cls: 'character', hero_asset_id: img, appearance: 'a courier' })
  await api('PUT', `/story/profiles/${who.id}/versions/v1/anim-ref`, { side: 'front', asset_id: img })
  await libAdd(page, 'sets', 'room')
  await libAdd(page, 'figures', 'Adult')
  await page.locator(`.w-panel [aria-label="the figure's character"] button[aria-label="${who.name}"]`).click()
  await libAdd(page, 'standins', 'crate')
  await page.locator('.lib-row[data-group="lights"] button', { hasText: /^Add light$/ }).click()
  await page.evaluate(() => (window as unknown as { __loom2Stage: { setRange: (a: number, b: number) => void } }).__loom2Stage.setRange(0, 12))   // half a second: 9 frames at F16
  await perfCardOf(page, 'Final shot')                                                                        // D121: the layered route is Performance's
  await expect(page.locator('.s-foot button.primary')).toHaveText(/^Make the final shot/)              // the foot: the final shot's next step
  await page.locator('.final-section button', { hasText: /^Make the final shot/ }).click()
  await expect(dialog).toContainText(/4 layers/)
  await expect(dialog).toContainText(/9 frames/)
  await expect(dialog).toContainText(/The plate is its still projected along the path: the camera moves little/)   // CA3: the camera's travel advises
  await page.screenshot({ path: 'node_modules/.e2e/ca3-make-confirm.png' })
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
  expect(job.recipe.kind).toBe('stage_shot'); expect(job.recipe.prompt_text).toMatch(/^The place is empty/)   // U4d (F38): the lead names no room
  const pf = await fetch(`http://127.0.0.1:${env().port}/finals/${fin.id}/layers/plate/frames/8`, { headers: { 'X-Loom-Token': env().token } })
  expect(pf.status).toBe(200)
  await expect(page.locator('.final-section li[data-kind="plate"] .status')).toHaveText(/done · 9 frames/)
  await expect(page.locator('.final-section li[data-kind="plate"] img.still')).toBeVisible()
  // CA3 (D130): the plate's method on its row — generated along the path from the same still (LTX-2.3 on the bare set's depth, the fake engine)
  const chip = page.locator('.final-section li[data-kind="plate"] .plate-method')
  await expect(chip).toHaveText(/projected/)                                                              // the camera does not move: projected
  await chip.click()
  if (env().variant === 'open') {                                                                           // D26: LTX-2.3 is full-only — offered, not runnable
    await expect(page.locator('.ctx-menu button.item', { hasText: /^Generate it along the path \(no depth-guided video model here\)$/ })).toBeDisabled()
    await page.mouse.click(1100, 700)
  } else {
    await page.locator('.ctx-menu button.item', { hasText: /^Generate it along the path$/ }).click()
    type Gen = Lay & { method: string; clip_id: string | null }
    await expect.poll(async () => { const p = await plateOf() as Gen; return `${p.method} ${p.status} ${p.frames_done} ${!!p.clip_id}` }, { timeout: 60_000 }).toBe('generated done 9 true')
    const ltxId = (await plateOf()).job_ids.at(-1)
    const ltx = (await api<{ items: { id: string; recipe: { kind: string; guide?: { kind: string } | null; start_asset: string; frames: number } }[] }>('GET', '/jobs')).items.find((j) => j.id === ltxId)!
    expect(ltx.recipe.kind).toBe('i2v'); expect(ltx.recipe.guide?.kind).toBe('depth'); expect(ltx.recipe.start_asset).toBe(plate.still_asset_id); expect(ltx.recipe.frames).toBe(9)
    await expect(chip).toHaveText(/along the path/)
    await expect(page.locator('.final-section li[data-kind="plate"] .status')).toHaveText(/done · 9 frames/)
    await page.screenshot({ path: 'node_modules/.e2e/ca3-plate-method.png' })
  }
  // CA4: the batch plan before the performance — one batch owed, its cost; the final's line offers to stage the performances
  await expect(page.locator('.final-section li[data-kind="figure"] [data-batch="0"]')).toHaveClass(/b-owed/)
  await expect(page.locator('.final-section [data-plan] .hint')).toContainText(/owe ≈ \d+ min/)
  await expect(page.locator('.final-section [data-stage-runs]')).toBeVisible()
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
  await expect(page.locator('.final-section li[data-kind="figure"] [data-batch="0"]')).toHaveClass(/b-done/, { timeout: 15_000 })   // CA4: the plan follows
  const matteJob = (await api<{ items: { id: string; kind: string; status: string }[] }>('GET', '/jobs')).items.find((j) => fig.job_ids.includes(j.id) && j.kind === 'matte_sequence')
  expect(matteJob?.status).toBe('done')                                                                    // PS5d: SAM 3 on the layer's frames, by itself
  // D125 (A1, WB1/WB2): a Story shot on the final's camera — the final was made without the For chip, so its clips follow the camera
  const linked = { id: made.shot }                                                                          // Shots makes the final for the shot itself (no link by camera, D157)
  // PS5e: the assembly — the layers composited into a clip on the final
  await expect(page.locator('.s-foot button.primary')).toHaveText(/^Assemble/)                          // D121: the next step, in the foot too
  await page.locator('.final-section .final-foot button', { hasText: 'Assemble the shot' }).click()
  type Done = { clip_id: string | null; assembly: { frames: number; conform?: string } | null }
  await expect.poll(async () => (await api<Done>('GET', `/finals/${fin.id}`)).clip_id, { timeout: 60_000 }).toBeTruthy()
  const done = await api<Done>('GET', `/finals/${fin.id}`)
  expect(done.assembly?.frames).toBe(9)
  type ShotLite = { versions: { clip_id: string | null; takes: { kind: string; id: string }[] }[] }
  await expect.poll(async () => (await api<ShotLite>('GET', `/story/shots/${linked.id}`)).versions[0].takes.map((t) => t.id), { timeout: 15_000 }).toContain(done.clip_id)
  expect((await api<ShotLite>('GET', `/story/shots/${linked.id}`)).versions[0].clip_id).toBeNull()        // the assembly is a take, never the clip by itself
  const clip = await api<{ frames: number; fps: number }>('GET', `/clips/${done.clip_id}`)
  expect([`${clip.frames}@${clip.fps}`]).toContain(done.assembly?.conform ? '13@24' : '9@16')                // RIFE when the local tool is there (D27)
  await expect(page.locator('.final-section [data-play]')).toBeVisible()
  // AE1 / AP1 thin (D114): the composition (an EffectCraft project beside the final — the fake session), scrubbed at the Final level, rendered
  await page.locator('.final-section [data-compose]').click()
  await expect(page.locator('.final-section [data-comp-rev]')).toHaveText(/composition · revision 0/)
  type Comp = { revision: number; stack: string[]; clip_id: string | null; layers: { id: string }[] }
  const comp = await api<Comp>('GET', `/finals/${fin.id}/composition`)
  expect(comp.layers.map((l) => l.id)).toEqual(['plate', 'shadows', ...comp.stack])
  await page.screenshot({ path: 'node_modules/.e2e/d121-performance-final-shot.png' })                  // D121: a look for the author — Performance's Final shot card
  await page.locator('.final-section [data-open-final]').click()
  await expect(page.locator('[data-testid="shots-layer"]')).toHaveAttribute('data-level', 'final')            // B2: the Shots rail is the levels
  await expect(page.locator('#anim-sec-shot .final-pick.active')).toContainText(fin.name)                  // D121: the Final level's own column — the final open
  await expect(page.locator('#anim-sec-performance')).toHaveCount(0)                                        // and nothing of the other levels
  await expect(page.locator('.final-viewer img.final-frame')).toBeVisible()
  await expect(page.locator('.final-viewer .final-chip')).toHaveText(/^\d+ %$/)                           // the number alone (UX9 U2)
  await page.locator('.final-viewer .frame-field').fill('4')                                               // D121 (AW2): the one transport's frame field
  await expect(page.locator('.final-viewer .counter')).toHaveText(/^frame 4 \//)
  await expect.poll(async () => page.locator('.final-viewer img.final-frame').getAttribute('data-side'), { timeout: 10_000 }).toBe('full')   // at rest: the full frame
  await page.screenshot({ path: 'node_modules/.e2e/d121-final.png' })                                     // D121: the Final level with its composition open
  // AE2: the editor — Layers and Properties in the column; each edit one engine command, the viewer following the new revision
  await expect(page.locator('#anim-sec-layers .comp-layer-list li')).toHaveCount(5)                       // the character, her matte, the prop, the shadows, the plate
  const row = (name: RegExp) => page.locator('#anim-sec-layers .comp-layer-list li').filter({ has: page.locator('.name', { hasText: name }) })   // by the name, not the selects' options
  await row(/^Shadows$/).locator('button.sw[title^="Video"]').click()
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 1/)
  const figName = fin.layers[1].name                                                                        // the figure's layer carries the Stage figure's name (her matte is "… · matte")
  await row(new RegExp(`^${figName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`)).locator('.name').click()   // its name: the column is narrower in Shots
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
  await expect(page.locator('.final-viewer .final-view')).toHaveClass(/masking/)                                    // the tool is on: the frame takes the clicks, not a mask's path
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
  await expect(page.locator('.final-viewer .final-view')).toHaveClass(/masking/)                                    // the tool is on: the frame takes the clicks, not a mask's path
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
  await expect(page.locator('.final-viewer .final-view')).toHaveClass(/masking/)                                    // the tool is on: the frame takes the clicks, not a mask's path
  const pic = (await page.locator('.final-viewer img.final-frame').boundingBox())!
  await page.locator('.final-viewer img.final-frame').click({ position: { x: pic.width * 0.5, y: pic.height * 0.5 } })   // the frame itself: waits until no toast covers the point
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
  // D118 (AE4a): a pass on the layer — Clean up queued (the fake engine answers the frames), its take lands as the layer's source and the
  // composition follows; the original shown again; the take dropped
  await editor.locator('.segmented button', { hasText: 'Passes' }).click()
  await editor.locator('.pass-tile[data-pass="cleanup"]').click()
  await editor.locator('.verbs button[title^="Run the pass"]').click()
  await expect.poll(async () => (await api<{ items: { kind: string; status: string }[] }>('GET', '/jobs')).items.filter((j) => j.kind === 'layer_pass').map((j) => j.status).join(','), { timeout: 90_000 }).toBe('done')
  await expect(editor.locator('.take-list li[data-take^="take_"]')).toHaveCount(1, { timeout: 15_000 })
  await expect(editor.locator('.take-list li[data-take^="take_"]')).toHaveClass(/shown/)
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 18/, { timeout: 15_000 })   // the composition took the layer's new source (the effect's removal was 17)
  await settled()
  await editor.locator('.take-list li[data-take="original"] button[title^="Show the original"]').click()
  await expect(editor.locator('.take-list li[data-take="original"]')).toHaveClass(/shown/)
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 19/)
  await settled()
  await editor.locator('.take-list li[data-take^="take_"] button[title^="Drop"]').click()
  await expect(editor.locator('.take-list li[data-take^="take_"]')).toHaveCount(0)
  // D118 (AE4c): the Face pass — the head tracked from the figure's keypoints, one Animate batch on the fake engine (9 frames), the take
  // "the head" shown with her matte following; Lip-sync waits for a line on the layer; the take dropped
  await expect(editor.locator('.pass-tile[data-pass="lipsync"]')).toBeDisabled()
  await expect(editor.locator('.verbs label', { hasText: 'strength' })).toHaveCount(1)
  await editor.locator('.pass-tile[data-pass="face"]').click()
  await expect(editor.locator('.verbs label', { hasText: 'strength' })).toHaveCount(0)                   // no strength for the face pass
  await editor.locator('.verbs button[title^="Run the pass"]').click()
  await expect.poll(async () => (await api<{ items: { kind: string; status: string; recipe: { preset: string } }[] }>('GET', '/jobs')).items.filter((j) => j.kind === 'layer_pass' && j.recipe.preset === 'face').map((j) => j.status).join(','), { timeout: 90_000 }).toBe('done')
  await expect(editor.locator('.take-list li[data-take^="take_"]')).toHaveCount(1, { timeout: 15_000 })
  await expect(editor.locator('.take-list li[data-take^="take_"]')).toHaveClass(/shown/)
  await expect(editor.locator('.take-list li[data-take^="take_"] .name')).toContainText('Face')
  await expect(editor.locator('.take-list li[data-take^="take_"] .name')).toContainText('the head')
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 20/, { timeout: 15_000 })   // the composition took the take (and her matte)
  await settled()
  await editor.locator('.take-list li[data-take^="take_"] button[title^="Drop"]').click()
  await expect(editor.locator('.take-list li[data-take^="take_"]')).toHaveCount(0)
  await expect(page.locator('.final-viewer [data-comp-state]')).toHaveText(/revision 21/)
  await settled()
  // D118 (AE4b): the line picker — this shot has no voiced line, so the menu says so
  await page.locator('#anim-sec-layers button[data-attach-line]').click()
  await expect(page.locator('.ctx-menu')).toContainText('No voiced line in this shot')
  await page.locator('#anim-sec-layers button[data-attach-line]').click()                // a second press on the opener closes it
  await expect(page.locator('.ctx-menu')).toHaveCount(0)
  // D118 (AE4e): a processing layer — Clean up over the stack from Mara's layer down (the fake CLI renders it apart, the fake engine
  // answers the pass), brought in above her on sync; its row reads the record in Passes; removed
  await expect(editor.locator('.segmented[data-scope] button', { hasText: 'everything below' })).toBeVisible()
  await editor.locator('.segmented[data-scope] button', { hasText: 'everything below' }).click()
  await expect(editor.locator('.comp-passes')).toHaveAttribute('data-scope', 'below')
  await expect(editor.locator('.pass-tile[data-pass="face"]')).toBeDisabled()                                   // the face pass needs a character layer
  await editor.locator('.pass-tile[data-pass="cleanup"]').click()
  await editor.locator('.verbs button[title^="Run the pass"]').click()
  await expect.poll(async () => (await api<{ items: { kind: string; status: string; recipe: { scope?: string } }[] }>('GET', '/jobs')).items.filter((j) => j.kind === 'layer_pass' && j.recipe.scope === 'below').map((j) => j.status).join(','), { timeout: 90_000 }).toBe('done')
  await expect(page.locator('#anim-sec-layers li[data-processing="true"]')).toHaveCount(1, { timeout: 15_000 })
  await expect(page.locator('#anim-sec-layers li[data-processing="true"] .name')).toContainText('Processed · Clean up')
  await settled()
  await page.locator('#anim-sec-layers li[data-processing="true"]').click()
  await expect(editor.locator('.comp-processing')).toBeVisible()
  await expect(editor.locator('.comp-processing')).not.toHaveAttribute('data-stale', 'true')
  await editor.locator('.verbs button[title^="Remove the processing layer"]').click()
  await expect(page.locator('#anim-sec-layers li[data-processing="true"]')).toHaveCount(0, { timeout: 15_000 })
  await settled()
  // AE5: the render settings and output modules in the Output section — half the size, a ProRes 4444 beside the master
  const out = page.locator('#anim-sec-output [data-render-settings]')
  await out.getByLabel('render resolution').selectOption('half')
  await out.getByRole('checkbox', { name: 'ProRes 4444 beside it' }).click()
  await expect.poll(async () => (await api<{ render: { resolution: string; prores: boolean } }>('GET', `/finals/${fin.id}`)).render, { timeout: 10_000 }).toMatchObject({ resolution: 'half', prores: true })
  await page.locator('.s-foot button.primary', { hasText: /^Render the finished shot/ }).click()          // D121: the Final level's foot
  await expect.poll(async () => (await api<Comp>('GET', `/finals/${fin.id}/composition`)).clip_id, { timeout: 60_000 }).toBeTruthy()
  type RenderJob = { kind: string; status: string; recipe: { final_id: string; settings: { resolution: string; prores: boolean } }; result: { prores?: string } }
  const rj = (await api<{ items: RenderJob[] }>('GET', '/jobs')).items.find((j) => j.kind === 'comp_render' && j.recipe.final_id === fin.id && j.status === 'done')!
  expect(rj.recipe.settings).toMatchObject({ resolution: 'half', prores: true })
  expect(rj.result.prores).toMatch(/master_4444\.mov$/)
  const finished = await api<Done>('GET', `/finals/${fin.id}`)
  expect(finished.clip_id).toBe((await api<Comp>('GET', `/finals/${fin.id}/composition`)).clip_id)                // the finished shot is the final's clip
  await expect(page.locator('#anim-sec-output [data-render-state]')).toHaveText(/rendered at revision \d+/, { timeout: 15_000 })   // the revision the render saw (the edits above moved it)
})

test('a world\'s look (SY0, B2a): the Look adds a style written in its Inspector; Make a sample image gives it its face; Sketches\' Style picker appends the fragment, which the job records', async ({ page }) => {
  const tag = Date.now().toString(36)
  const sname = `Ink wash ${tag}`
  await openShell(page, 'world/look')
  await page.locator('[data-testid="world-look"] button', { hasText: 'Add style' }).click()                 // the column's verb (D32)
  await expect(page.locator('.style-grid .style-tile.active')).toBeVisible()                                // a tile, selected; written in the Inspector
  const insp = page.locator('[data-testid="world-look-inspector"]')
  await insp.locator('input[aria-label="selected style name"]').fill(sname)
  await insp.locator('textarea[aria-label="selected style fragment"]').fill('ink and wash storyboard, loose brush')
  await expect(page.locator('.style-grid .style-tile.active .name')).toHaveText(sname)
  type WorldLite = { revision: number; styles: { id: string; name: string; fragment: string; group_id: string | null }[] }
  await expect.poll(async () => (await api<WorldLite>('GET', '/story/world')).styles.find((x) => x.name === sname)?.fragment, { timeout: 10_000 }).toBe('ink and wash storyboard, loose brush')
  // D90 (02 §4.1): Make a sample image — one job on the swatch model into the style's own group, whose cover becomes the style's face
  await insp.locator('button', { hasText: 'Make a sample image' }).click()
  await expect(page.locator('.style-grid .style-tile.active .face img')).toBeVisible({ timeout: 45_000 })
  const style = (await api<WorldLite>('GET', '/story/world')).styles.find((x) => x.name === sname)!
  const sample = Object.values((await api<{ assets: Record<string, { params: { style_id?: string | null } }> }>('GET', `/groups/${style.group_id}`)).assets)
  expect(sample.length === 1 && sample[0].params.style_id === style.id).toBe(true)                             // the sample ran under the style, on its group
  // Sketches: the picker lists it and says what it appends; the job records the style and the text that ran
  await openShell(page, 'world/sketches')
  const col = page.locator('[data-testid="world-sketches"]')
  await col.locator('#gen-sec-model').scrollIntoViewIfNeeded()
  await col.locator('.model-card').filter({ has: page.locator('span', { hasText: /^Klein 4B$/ }) }).click()
  await col.locator('#gen-sec-prompt').scrollIntoViewIfNeeded()
  await col.locator('#gen-sec-prompt .segmented button', { hasText: /^Text$/ }).click()
  const pick = col.locator(`.style-pick button[aria-label="${sname}"]`)
  await pick.scrollIntoViewIfNeeded()
  await pick.click()                                                                                      // D90: styles are picked by their sample tile
  await expect(pick).toHaveAttribute('aria-pressed', 'true')
  await expect(pick).toHaveAttribute('title', /ink and wash storyboard, loose brush/)
  await col.locator('.text-prompt textarea').fill('a courier on a rooftop at dawn')
  const before = new Set((await api<{ items: { id: string }[] }>('GET', '/jobs')).items.map((j) => j.id))
  await col.locator('button', { hasText: /^Make \d+ sketch/ }).click()
  type JobLite = { id: string; status: string; origin: { surface?: string } | null; result: { asset_ids?: string[] } | null }
  const jobOf = async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => !before.has(j.id) && j.origin?.surface === 'sketch')
  await expect.poll(async () => (await jobOf())?.status, { timeout: 45_000 }).toBe('done')
  type Made = AssetLite & { prompt_text: string | null; params: { style_id?: string | null; style_text?: string | null } }
  const made = await api<Made>('GET', `/assets/${(await jobOf())!.result!.asset_ids![0]}`)
  expect(made.params.style_id).toBe(style.id)
  expect(made.params.style_text).toBe('ink and wash storyboard, loose brush')
  expect(made.prompt_text).toContain('a courier on a rooftop at dawn. ink and wash storyboard, loose brush')
})

test('a character from a picture (SY1, B2a): "Make a character…" on a Bin picture opens it in World with the picture as its hero; a candidate made a reference; Mark final makes the album refuse; @name resolves to the version', async ({ page }) => {
  test.setTimeout(90_000)
  const name = `Mara ${Date.now().toString(36)}`                                       // unique: the project is reused between runs
  const src = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const [heroId, candId] = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [src, src] })).ids
  await api('POST', '/groups/move', { items: [heroId, candId].map((id) => ({ kind: 'asset', id })), to: null })   // both on no page: Imports
  await openShell(page, 'bin')
  await openHome(page, 'imports')                                                                                // on no page: Imports shows them (B4: a stray until the next open)
  await page.locator(`[data-testid="bin-grid"] .w-tile[data-id="${heroId}"]`).click({ button: 'right' })
  await page.locator('.ctx-menu .item.sub', { hasText: 'Make an entity from it' }).hover()
  await page.locator('.ctx-menu .ctx-menu button.item', { hasText: 'Make a character…' }).click()
  const dialog = page.locator('.modal.ask')
  await expect(dialog).toContainText(/Make a character/)
  await dialog.locator('input').fill(name)
  await dialog.locator('button.primary').click()
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^World/)
  await expect(page.locator('[data-testid="world-header"]')).toContainText(name)
  type Version = { id: string; state: string; group_id: string; hero_asset_id: string | null }
  type ProfileLite = { id: string; name: string; versions: Version[] }
  const profile = (await api<{ items: ProfileLite[] }>('GET', '/story/profiles')).items.find((p) => p.name === name)!
  expect(profile.versions[0].hero_asset_id).toBe(heroId)
  const gid = profile.versions[0].group_id
  expect((await api<{ group: { cover_id: string | null } }>('GET', `/groups/${gid}`)).group.cover_id).toBe(heroId)   // the hero on the reference page as its cover
  await expect(page.locator(`[data-testid="world-bin"] .w-tile[data-id="${heroId}"] .w-badge`)).toHaveText('★')
  // a candidate in its bin, made a reference by its right-click
  await api('POST', `/story/profiles/${profile.id}/versions/v1/add`, { asset_ids: [candId], role: 'candidate' })
  const cand = page.locator(`[data-testid="world-bin"] .w-tile[data-id="${candId}"]`)
  await expect(cand).toBeVisible({ timeout: 10_000 })
  await contextChoose(page, cand, 'Use as a reference')
  await expect.poll(async () => (await api<{ group: { items: { id: string }[] } }>('GET', `/groups/${gid}`)).group.items.map((i) => i.id), { timeout: 10_000 }).toContain(candId)
  await expect(page.locator('[data-testid="world-readiness"]')).toContainText('✓ hero')
  // Mark final from the version menu: the album refuses a move on the reference page
  await page.locator('[data-testid="world-header"] button', { hasText: /^v1/ }).click()
  await page.locator('.ctx-menu button.item', { hasText: /^Mark final/ }).click()
  if (await dialog.count()) await dialog.locator('button.primary').click()
  await expect.poll(async () => (await api<{ items: ProfileLite[] }>('GET', '/story/profiles')).items.find((p) => p.id === profile.id)?.versions[0].state, { timeout: 10_000 }).toBe('final')
  await expect(api('POST', '/groups/move', { items: [{ kind: 'asset', id: candId }], to: null })).rejects.toThrow(/423/)
  // the mention: the preview resolves @name to v1's reference set with the hero first
  type Preview = { mentions: { profile_id: string | null; version: string | null; group_id: string }[]; ref_list: { asset_id: string | null }[] }
  const klein4bId = Object.entries((await api<{ models: Record<string, { label: string }> }>('GET', '/capabilities')).models).find(([, m]) => m.label === 'Klein 4B')![0]
  const pv = await api<Preview>('POST', '/recipes/preview', { recipe: { kind: 't2i', model_id: klein4bId, prompt_mode: 'text', prompt_text: `@${name} at the gate`, mentions: [{ profile_id: profile.id, name }] } })
  expect(`${pv.mentions[0]?.profile_id}/${pv.mentions[0]?.version}/${pv.mentions[0]?.group_id}/${pv.ref_list[0]?.asset_id}`).toBe(`${profile.id}/v1/${gid}/${heroId}`)
  await api('POST', '/assets/duplicate', { ids: [src] })                          // the scenarios after take "the newest image": one on no page, not locked in Mara's final set
})

test('a shot from the camera (SY2, B2a): Clay\'s New shot from this camera makes a shot through that camera; the stage\'s still made in Sketches from a stage lands as the frame of the shot open in Shots; the new shot opens there', async ({ page }) => {
  test.setTimeout(120_000)
  const name = `Gate ${Date.now().toString(36)}`
  const made = await clayShot(page, `Gatehouse ${name.slice(-5)}`)
  const dialog = page.locator('.modal.ask')
  await page.locator('.stage-empty button', { hasText: /Add set · room/ }).click()
  await libAdd(page, 'figures', 'Adult')
  await section(page, 'camera')
  await page.locator('#anim-sec-camera button[aria-label^="New shot from this camera"]').click()        // the Camera section's verb (D32)
  await expect(dialog).toContainText(/New shot from this camera/)
  await dialog.locator('input').fill(name)
  await dialog.locator('button.primary').click()
  type Version = { id: string; stage_id: string | null; camera_id: string | null; frame_asset_id: string | null; takes: { kind: string; id: string }[] }
  type Shot = { id: string; name: string; versions: Version[] }
  await expect.poll(async () => (await api<{ items: Shot[] }>('GET', '/story/shots')).items.find((x) => x.name === name)?.versions[0].camera_id ?? null, { timeout: 10_000 }).toBeTruthy()
  const shot = (await api<{ items: Shot[] }>('GET', '/story/shots')).items.find((x) => x.name === name)!
  expect(shot.versions[0].stage_id).toBeTruthy()
  // the stage's still (Sketches, From a stage): the passes, then Render frame (the fake engine answers) → the shot's frame, by its camera
  await fromStageIn(page)
  await page.locator('.shot-tab button', { hasText: /^Render passes$/ }).click()
  await page.locator('.shot-tab .shot-prompt').fill('a gatehouse at dawn')
  const go = page.locator('[data-testid="world-sketches"] .w-foot button.primary', { hasText: /^Render frame/ })
  await expect(go).toBeEnabled({ timeout: 30_000 })
  await go.click()
  const shotOf = async () => api<Shot>('GET', `/story/shots/${shot.id}`)
  const open = async () => api<Shot>('GET', `/story/shots/${made.shot}`)
  await expect.poll(async () => (await open()).versions[0].frame_asset_id, { timeout: 60_000 }).toBeTruthy()   // made for the shot open in Shots (its For)
  expect((await open()).versions[0].takes.map((t) => t.kind)).toEqual(['image'])
  expect((await shotOf()).versions[0].frame_asset_id).toBeNull()                                         // not the other shot on the same camera
  // the shot in Shots: its storyboard card, its header
  await openShell(page, `shots/${shot.id}/clay`)
  await expect(page.locator('[data-testid="shots-layer"] .w-head, [data-testid="shot-header"]').first()).toContainText(name)
})

test('a flow (17 / SY3, D85; U2 G5: a Shot with lines): the Strip adds Start, Shot and Choice nodes, handle drags connect them, the Inspector edits the line and the options and spawns a shot, Validate lists the advisory problem, and Play walks both branches without queuing a job (Shots, B2a)', async ({ page }) => {
  test.setTimeout(120_000)
  await openShell(page, 'shots/flow')
  await expect(page.locator('[data-testid="flow-canvas"]')).toBeVisible()
  type FlowLite = { graph: { edges: { from: string; port: string; to: string }[]; start: string | null }; nodes: { id: string; type: string; shot_id: string | null }[] }
  for (const n of (await api<FlowLite>('GET', '/story/flow')).nodes) await api('DELETE', `/story/flow/nodes/${n.id}?shot=delete`)   // a clean slate (the project is reused between runs; RC2a: a kept shot would stay as a node)
  type Hook = { loadFlow: () => Promise<void> }
  await page.evaluate(() => (window as unknown as { __loom2Story: Hook }).__loom2Story.loadFlow())
  await expect(page.locator('.flow-node')).toHaveCount(0)
  const jobsBefore = (await api<{ items: unknown[] }>('GET', '/jobs')).items.length
  // the palette on the Strip (D32): three nodes, laid out in a row
  await page.locator('[data-testid="shots-flow-strip"] button[aria-label="Add Start"]').click()
  await expect(page.locator('.flow-node.t-start')).toHaveCount(1)
  await page.locator('[data-testid="shots-flow-strip"] button[aria-label="Add Shot"]').click()                          // U2 (G5): a Dialogue is a Shot with lines
  await page.locator('[data-testid="shots-flow-strip"] button[aria-label="Add Choice"]').click()
  await expect(page.locator('.flow-node')).toHaveCount(3)
  const start = page.locator('.flow-node.t-start'), choice = page.locator('.flow-node.t-choice')
  let dlg = page.locator('.flow-node.t-shot')
  // the nodes landed stepped at the view's centre (they overlap on a small window): lay them out through the index, then one mouse drag
  type Graph = { graph: { revision: number; nodes: { id: string; x: number; y: number }[]; edges: unknown[]; start: string | null } }
  const g0 = (await api<Graph>('GET', '/story/flow')).graph
  const ids = { start: (await start.getAttribute('data-id'))!, dlg: (await dlg.getAttribute('data-id'))!, choice: (await choice.getAttribute('data-id'))! }
  dlg = page.locator(`.flow-node[data-id="${ids.dlg}"]`)                                         // the speaking Shot by its id: a shot made below is a Shot node too
  await api('PUT', '/story/flow/graph', { revision: g0.revision, nodes: [{ id: ids.start, x: 0, y: 0 }, { id: ids.dlg, x: 340, y: 0 }, { id: ids.choice, x: 680, y: 0 }], edges: g0.edges, start: g0.start })
  await page.evaluate(() => (window as unknown as { __loom2Story: Hook }).__loom2Story.loadFlow())
  await page.locator('[data-testid="shots-flow-strip"] button[aria-label="Fit the graph"]').click()
  await expect.poll(async () => (await api<Graph>('GET', '/story/flow')).graph.nodes.find((n) => n.id === ids.choice)?.x).toBe(680)
  const before = await centre(choice.locator('.head'))
  await page.mouse.move(before.x, before.y); await page.mouse.down(); await page.mouse.move(before.x + 10, before.y + 6, { steps: 3 }); await page.mouse.move(before.x + 10, before.y + 90, { steps: 10 }); await page.mouse.up()   // a drag saves on drop
  await expect.poll(async () => (await api<Graph>('GET', '/story/flow')).graph.nodes.find((n) => n.id === ids.choice)?.y ?? 0, { timeout: 10_000 }).toBeGreaterThan(40)
  // the Inspector: the Shot's title and line, the Choice's two options (each an out-port)
  await dlg.locator('.head').click()
  await page.locator('.s-insp input[aria-label="node title"]').fill('Hello')
  await page.locator('.s-insp button', { hasText: '+ line' }).click()
  await page.locator('.s-insp input[aria-label="line 1"]').fill('Hi there.')
  await expect(dlg.locator('.line')).toContainText('Hi there.')
  await choice.locator('.head').click()
  await page.locator('.s-insp button', { hasText: '+ option' }).click()
  await page.locator('.s-insp input[aria-label="option 1"]').fill('Go')
  await page.locator('.s-insp button', { hasText: '+ option' }).click()
  await page.locator('.s-insp input[aria-label="option 2"]').fill('Stay')
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
  // D125 (#4): the Shot was made with its own shot (loom R146), which took the title "Hello" with it; the panel shows the node, then the
  // shot; no "New shot for this node…" any more. Validate: the shot is not final yet — one advisory problem
  await dlg.locator('.head').click()
  await expect(page.locator('.s-insp [data-testid="node-shot-panel"] .shot-head')).toHaveText('Shot · Hello')
  await expect(page.locator('.s-insp button[aria-label^="Make its shot"]')).toHaveCount(0)
  await expect.poll(async () => (await api<{ items: { name: string; owner_node: string | null }[] }>('GET', '/story/shots')).items.find((s) => s.name === 'Hello')?.owner_node).toBeTruthy()
  await page.locator('[data-testid="shots-flow-strip"] button[aria-label="Validate"]').click()
  await expect(page.locator('[data-testid="shots-flow-strip"] .hint')).toContainText(/1 problem/)
  expect((await api<{ problems: { code: string }[] }>('POST', '/story/flow/validate')).problems.map((p) => p.code)).toEqual(['shot_open'])
  // play: the line shows, Next → the two options, Go loops to Hello, Stay ends; no job was queued (loom R143)
  await page.locator('[data-testid="shots-flow-strip"] button[aria-label="Play"]').click()
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
  await page.locator('[data-testid="shots-flow-strip"] button[aria-label="Stop playing"]').click()
  await expect(page.locator('[data-testid="flow-canvas"]')).toBeVisible()
  // the files are the truth: after a reload the nodes, the edges and the bound shot come back
  await page.reload()
  await expect(page.locator('.flow-node')).toHaveCount(3)
  await expect(dlg.locator('.shot img, .shot span')).toHaveCount(1)
  expect((await api<FlowLite>('GET', '/story/flow')).nodes.find((n) => n.id === ids.dlg)!.shot_id).toBeTruthy()
  // RC2a (proto01_animate 31 §3b): one record — a shot made elsewhere is a Shot node outside the routes; the speaking Shot takes it from its panel,
  // the bare node goes (the speaking Shot's own shot was empty: it is dropped), and the shot's name is the node's title
  const made = await api<{ id: string; owner_node: string }>('POST', '/story/shots', { name: 'From the camera' })
  await expect(page.locator('.flow-node')).toHaveCount(4)
  await dlg.locator('.head').click()
  await page.locator('.s-insp select[aria-label="bind shot"]').selectOption({ label: 'From the camera' })
  await expect(page.locator('.flow-node')).toHaveCount(3)
  await expect(page.locator('.s-insp [data-testid="node-shot-panel"] .shot-head')).toHaveText('Shot · Hello')
  expect((await api<FlowLite>('GET', '/story/flow')).nodes.find((n) => n.id === ids.dlg)!.shot_id).toBe(made.id)
  // RC2c: a scene of the speaking Shot from its right-click, its frame on the canvas; New Shot from this Shot puts a sibling in it
  const dlgNode = dlg
  await dlgNode.locator('.head').click({ button: 'right' })
  await page.locator('.ctx-menu button.item', { hasText: /^Make a scene of it…$/ }).click()
  await page.locator('.modal.ask input').fill('At the gate')
  await page.locator('.modal.ask button.primary').click()
  await expect(page.locator('.scene-frame[data-scene="At the gate"]')).toBeVisible()
  await dlgNode.locator('.head').click({ button: 'right' })
  await page.locator('.ctx-menu button.item', { hasText: /^New Shot from this Shot$/ }).click()
  await expect(page.locator('.flow-node', { hasText: 'Hello · 2' })).toHaveCount(1)
  type ScenesLite = { items: { name: string; node_ids: string[] }[] }
  await expect.poll(async () => (await api<ScenesLite>('GET', '/story/scenes')).items.find((s) => s.name === 'At the gate')?.node_ids.length).toBe(2)
  // RC2e: Save as a template… keeps it in World › Presets; the Flow's right-click places one from it
  await dlgNode.locator('.head').click({ button: 'right' })
  await page.locator('.ctx-menu button.item', { hasText: /^Save as a template…$/ }).click()
  await page.locator('.modal.ask input').fill('Gate talk')
  await page.locator('.modal.ask button.primary').click()
  await expect.poll(async () => (await api<{ items: { name: string }[] }>('GET', '/story/shot-templates')).items.map((t) => t.name)).toContain('Gate talk')
  const pane = page.locator('.react-flow__pane')
  await pane.click({ button: 'right', position: { x: 30, y: 30 } })
  await page.locator('.ctx-menu .item.sub', { hasText: /^New Shot from a template/ }).hover()
  await page.locator('.ctx-menu button.item', { hasText: /^Gate talk$/ }).click()
  await expect(page.locator('.flow-node', { hasText: 'Gate talk' })).toHaveCount(1)
  // RC2d: the Shots list orders by scene (the scene's name heads its rows) and finds a shot by a word
  await page.locator('[data-testid="shots-flow-strip"] button', { hasText: 'List' }).click()                                              // D157 Q11: the Flow's List view
  await page.locator('select[aria-label="shot order"]').selectOption('scene')
  await expect(page.locator('.shots-board tr.grp', { hasText: 'At the gate' })).toHaveCount(1)
  await page.locator('input[aria-label="search shots"]').fill('Hello · 2')
  await expect(page.locator('.shots-board tr.row')).toHaveCount(1)
  for (const t of (await api<{ items: { id: string; name: string }[] }>('GET', '/story/shot-templates')).items) if (t.name === 'Gate talk') await api('DELETE', `/story/shot-templates/${t.id}`)
})

test("a plate projected and filled (D135 · PF1): a moving camera's final shot makes its plate projected and filled — Stage places keyframes along the path, the server fills what none saw (an Edit document's Fill on the fake engine), the frames are made from them; the plate row's chip and its heal tick (Shots, B2a)", async ({ page }) => {
  test.setTimeout(150_000)
  await clayShot(page, 'Filled plate')
  const dialog = page.locator('.modal.ask')
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await libAdd(page, 'sets', 'room')
  type Hook = { setRange: (a: number, b: number) => void; setFrame: (f: number) => void; keyCamera: () => void; updateCamera: (id: string, p: object) => void
    state: () => { current: { cameras: { id: string; pos: number[] }[] } } }
  await page.evaluate(() => {                                                                              // the camera swings 3 m sideways over half a second
    const h = (window as unknown as { __loom2Stage: Hook }).__loom2Stage
    h.setRange(0, 12); h.setFrame(0); h.keyCamera()
    const cam = h.state().current.cameras[0]
    h.setFrame(12); h.updateCamera(cam.id, { pos: [cam.pos[0] + 3, cam.pos[1], cam.pos[2] - 1] }); h.keyCamera()
  })
  await perfCardOf(page, 'Final shot')
  await page.locator('.final-section button', { hasText: /^Make the final shot/ }).click()
  await expect(dialog).toContainText(/The plate is projected and filled .*: the camera turns \d+°/)            // D135: the camera's travel advises it
  await page.screenshot({ path: 'node_modules/.e2e/pf1-make-confirm.png' })
  await dialog.locator('button.primary').click()
  await expect(page.locator('.final-section .final-row')).toBeVisible({ timeout: 60_000 })
  const stage = (await api<{ items: { id: string; name: string }[] }>('GET', '/stages')).items.find((s) => s.name === 'Filled plate')!
  const fin = (await api<{ items: { id: string; layers: { id: string; method: string }[] }[] }>('GET', `/finals?stage_id=${stage.id}`)).items[0]
  expect(fin.layers.find((l) => l.id === 'plate')!.method).toBe('filled')
  await page.locator('.final-section li[data-kind="plate"] button', { hasText: 'Make the plate' }).click()
  type Key = { frame: number; asset_id: string | null; job_id: string | null }
  type Plate = { status: string; frames_done: number; keys: Key[]; heal: boolean }
  const plateOf = async () => (await api<{ layers: (Plate & { id: string })[] }>('GET', `/finals/${fin.id}`)).layers.find((l) => l.id === 'plate')!
  await expect.poll(async () => { const p = await plateOf(); return `${p.status} ${p.frames_done}` }, { timeout: 120_000 }).toBe('done 9')
  const plate = await plateOf()
  expect(plate.keys.length).toBeGreaterThan(0); expect(plate.keys.at(-1)!.frame).toBe(8)                    // the last frame is a keyframe
  expect(plate.keys.every((k) => !!k.asset_id)).toBe(true)
  expect(plate.keys.some((k) => !!k.job_id)).toBe(true)                                                      // at least one keyframe was filled
  const pf = await fetch(`http://127.0.0.1:${env().port}/finals/${fin.id}/layers/plate/frames/8`, { headers: { 'X-Loom-Token': env().token } })
  expect(pf.status).toBe(200)
  const chip = page.locator('.final-section li[data-kind="plate"] .plate-method')
  await expect(chip).toHaveText(/^filled ▾/)
  await expect(page.locator('.final-section li[data-kind="plate"] .status')).toHaveText(/done · 9 frames/)
  await chip.click()                                                                                         // Q29: the heal, a tick on the plate's row
  await page.locator('.ctx-menu button.item', { hasText: /^Heal the frames between$/ }).click()
  await expect.poll(async () => (await plateOf()).heal).toBe(true)
  await expect(chip).toHaveText(/^filled · heal ▾/)
  await chip.click()
  await expect(page.locator('.ctx-menu button.item', { hasText: /Project and fill again$/ })).toBeVisible()        // ticked: the method it is
  await page.screenshot({ path: 'node_modules/.e2e/pf1-plate-menu.png' })
  await page.mouse.click(1100, 700)
})

test("an episode (17 / SY4, D85): the Shots bin lists a final shot and adds it stamped; the checklist names the plain clip; Export asks, writes the FCPXML with a chapter marker and markers.txt, and the SRT carries the node's line; the old deep link redirects (Shots and Episode, B2a)", async ({ page }) => {
  test.setTimeout(120_000)
  // a final shot: a clip at the project format (the fake engine), a Dialogue node bound to it
  const fmt = (await api<{ format: { width: number; height: number } }>('GET', '/project')).format
  const img = (await sketchPics(1))[0].id
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
  // RC2b (D96): the node's Shot card carries its length — 9 frames at 16 fps from its clip
  await openShell(page, 'shots/flow')
  await expect(page.locator(`.flow-node[data-id="${node.id}"] [data-length]`)).toHaveText('0.6 s')
  await openShell(page, 'episode')
  await expect(page.locator('nav.tabs button.tab.active')).toHaveText(/^Episode/)
  await page.locator('.seq-list-head button[title^="New cut"]').click()
  const dialog = page.locator('.modal.ask')
  await dialog.locator('input').fill(name)
  await dialog.locator('button.primary').click()
  await expect(page.locator('.seq-row.active')).toContainText(name)
  const card = page.locator(`.shots-bin .seq-clip-card[data-shot="${shot.id}"]`)
  await expect(card).toHaveClass(/\bfinal\b/)
  await expect(card).toContainText(`${name} node`)
  await card.locator('button[aria-label^="add shot"]').click()                                // + : stamped with the shot, its version and its node
  await expect(page.locator('.cut-clip.k-take')).toHaveCount(1)
  await page.locator('.seq-bin:not(.shots-bin) .seq-clip-card button').first().click()         // a plain clip beside it
  await expect(page.locator('.cut-clip.k-take')).toHaveCount(2)
  type TL = { id: string; name: string; clips: { clip_id: string; shot_id: string | null; shot_version: string | null; node_id: string | null }[] }
  await expect.poll(async () => (await api<{ items: TL[] }>('GET', '/timelines')).items.find((t) => t.name === name)?.clips.length, { timeout: 10_000 }).toBe(2)
  const tl = (await api<{ items: TL[] }>('GET', '/timelines')).items.find((t) => t.name === name)!
  expect(tl.clips[0]).toMatchObject({ clip_id: clipId, shot_id: shot.id, shot_version: 'v1', node_id: node.id })
  expect(tl.clips[1].shot_id).toBeNull()
  await expect(page.locator('.seq-insp .seq-check li.warn')).toHaveCount(1)                   // clip 2: a plain clip
  await expect(page.locator('[data-testid="episode-layer"] .s-foot .estimate')).toContainText('1 of 2 clips not final shots')
  // Export for Resolve ▶ (the panel foot, D125 S14): the checklist asks once, then one folder named after the cut holds the FCPXML with the
  // marker, the EDL, the SRT and markers.txt
  await page.locator('[data-testid="episode-layer"] .s-foot button.primary', { hasText: /^Export for Resolve/ }).click()
  await expect(dialog).toContainText(/1 of 2 clips listed/)
  await dialog.locator('button.primary').click()
  await expect(page.locator('.seq-insp .hint', { hasText: 'last:' })).toContainText(`timelines/${tl.id}/`)
  const fx = await api<{ text: string; path: string }>('POST', `/timelines/${tl.id}/export`, { format: 'fcpxml' })
  expect(fx.text).toContain(`value="${name} node"`)
  expect(fx.text.match(/<(chapter-)?marker /g)).toHaveLength(1)                              // CE2: a FilmCraft cut's FCPXML is FilmCraft's (chapter-marker)
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
})

test('a voice (19 / CN2, D87): a draft voice from the Cast Inspector\'s form speaks for the character; the Flow Inspector voices a line on the fake runner — the line gets its ▶, an audio asset with a waveform thumbnail lands, "Voice all lines" takes the fallback voice for the speakerless line (World and Shots, B2a)', async ({ page }) => {
  test.setTimeout(120_000)
  // a character with a hero and a Dialogue node with two lines (through the API; the Cast and Flow scenarios cover those mouse paths)
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const name = `Vo ${Date.now().toString(36)}`
  const prof = await api<{ id: string; revision: number }>('POST', '/story/profiles', { name, cls: 'character', hero_asset_id: img, appearance: 'a courier' })
  const node = await api<{ id: string; revision: number }>('POST', '/story/flow/nodes', { type: 'dialogue', title: `${name} says`, x: 1200, y: 900 })
  await api('PATCH', `/story/flow/nodes/${node.id}`, { revision: node.revision, lines: [{ speaker: prof.id, text: 'Hi there, come in.' }, { speaker: null, text: 'Thank you.' }] })
  await openShell(page, `world/character/${prof.id}/v1`)
  const voices = page.locator('[data-testid="world-inspector"] .voices')
  await expect(voices.locator('select[aria-label="profile voice"]')).toHaveValue('')
  await page.locator('[data-testid="world-inspector"] button[title^="New voice"]').click()             // the form (D32: a button)
  const form = voices.locator('[aria-label="new voice"]')
  await form.locator('input[aria-label="voice name"]').fill(`Narrator ${name}`)
  await expect(form.locator('select[aria-label="kokoro voice"] option')).not.toHaveCount(0)
  await form.locator('select[aria-label="kokoro voice"]').selectOption('am_adam')
  await form.locator('button[aria-label="create voice"]').click()
  await expect(form).toHaveCount(0)
  await expect(voices.locator('select[aria-label="profile voice"] option:checked')).toContainText(`Narrator ${name} · draft`)   // the character speaks with its first voice
  await expect(voices).toContainText('am_adam')
  // Shots' Flow: the node's Inspector — 🎙 on line 1 → the fake runner speaks it → ▶ and the audio asset
  const shotOf = (await api<{ nodes: { id: string; shot_id: string | null }[] }>('GET', '/story/flow')).nodes.find((n) => n.id === node.id)!.shot_id!
  await openShell(page, `shots/${shotOf}/clay`)                                                         // its shot open: the Flow comes up on it
  await page.locator('.w-rail-btn[data-level="flow"]').click()
  await expect(page.locator('[data-testid="flow-canvas"]')).toBeVisible()
  await page.waitForFunction(() => !!(window as unknown as { __loom2Story?: unknown }).__loom2Story)                  // the Flow's Inspector loaded Story's parts
  await page.evaluate(async (id) => { const h = (window as unknown as { __loom2Story: { loadFlow: () => Promise<void>; selectNode: (id: string) => void } }).__loom2Story; await h.loadFlow(); h.selectNode(id) }, node.id)   // the node selected (the canvas holds many)
  await expect(page.locator('.s-insp input[aria-label="line 1"]')).toHaveValue('Hi there, come in.')
  await expect(page.locator('.s-insp button[aria-label="play line 1"]')).toHaveCount(0)
  await page.locator('.s-insp button[aria-label="voice line 1"]').click()
  await expect(page.locator('.s-insp button[aria-label="play line 1"]')).toBeVisible({ timeout: 60_000 })
  type Line = { text: string; audio_asset_id: string | null; audio_text: string | null }
  const lines = async () => (await api<{ nodes: { id: string; lines: Line[] }[] }>('GET', '/story/flow')).nodes.find((n) => n.id === node.id)!.lines
  expect((await lines())[0]).toMatchObject({ text: 'Hi there, come in.', audio_text: 'Hi there, come in.' })
  const audioId = (await lines())[0].audio_asset_id!
  const asset = await api<{ kind: string; duration_s: number | null; thumb_status: string; parents: string[] }>('GET', `/assets/${audioId}`)
  expect(asset.kind).toBe('audio')
  expect(asset.duration_s).toBeGreaterThan(0.5)
  expect(asset.thumb_status).toBe('done')
  // line 2 has no speaker: "Voice all lines" is refused until a fallback voice is picked, then both lines are covered (line 1 again by its speaker's voice)
  const sel = page.locator('.s-insp select[aria-label="fallback voice"]')
  await sel.selectOption({ label: `Narrator ${name} · draft` })
  await page.locator('.s-insp button[title^="Voice all lines"]').click()
  await expect(page.locator('.s-insp button[aria-label="play line 2"]')).toBeVisible({ timeout: 60_000 })
  await expect.poll(async () => (await lines())[1].audio_asset_id).toBeTruthy()
  // the Catalogue lists it under Type · Audio with its badge
  const audio = await api<{ items: { id: string }[] }>('GET', '/assets?kind=audio&limit=10')
  expect(audio.items.map((a) => a.id)).toContain(audioId)
})

test("experimental extension and lip-sync (D88): Animate's Extend ▶ continues a clip from its own end with the caveat shown; a shot version's Lip-sync ▶ stages a talking take from a voiced line, which lands on the version (Shots, B2a)", async ({ page }) => {
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
  await clayShot(page, `Extend ${Date.now().toString(36)}`)
  await toLevel(page, 'performance')                                                                     // Performance: Animate's clips and their Selection
  type AnimateHook = { getState: () => { loadClips: () => Promise<void>; select: (id: string) => void } }
  await page.evaluate(async (id) => { const an = (window as unknown as { __loom2Animate: AnimateHook }).__loom2Animate.getState(); await an.loadClips(); an.select(id) }, parent)
  await expect(page.locator('.w-panel .badge.experimental').first()).toBeVisible()                        // D95 (AN1): Selection's Clip fold
  await page.locator('.w-panel .anim-exp > summary').click()                                                // D90 (02 §9): Extend sits under the Experimental fold
  await page.locator('.w-panel button[aria-label^="Extend"]').click()
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
  await openShell(page, `shots/${shot.id}/clay`)
  await page.locator('.w-rail-btn[data-level="flow"]').click()                                             // the node's Inspector in Shots' Flow
  await page.waitForFunction(() => !!(window as unknown as { __loom2Story?: unknown }).__loom2Story)
  await page.evaluate(async (id) => { const h = (window as unknown as { __loom2Story: { loadFlow: () => Promise<void>; selectNode: (id: string) => void } }).__loom2Story; await h.loadFlow(); h.selectNode(id) }, node.id)
  const block = page.locator('.s-insp .lipsync')
  await expect(block.locator('.badge.experimental')).toBeVisible()
  await expect(block.locator('select[aria-label="lip-sync line"] option')).toContainText([`${name} node`])
  await block.locator('select[aria-label="lip-sync preset"]').selectOption('fast')
  await page.locator('.s-insp button[aria-label^="Lip-sync"]').click()
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

test('lora slots (18 / LT1, D25): the Model tab lists the loras folder\'s file for Klein 4B, a slot with a strength rides the recipe, the job\'s compiled summary names the loader\'s file and the manifest records the slot (in Sketches, B2a)', async ({ page }) => {
  await openShell(page, 'world/sketches')
  const col = page.locator('[data-testid="world-sketches"]')
  await col.locator('#gen-sec-model').scrollIntoViewIfNeeded()
  await page.locator('.model-card').filter({ has: page.locator('span', { hasText: /^Klein 4B$/ }) }).click()
  await page.locator('[data-testid="world-sketches"] summary', { hasText: /^LoRAs/ }).click()                                         // D90: the slots fold away until one is used
  const slot = page.locator('[data-testid="world-sketches"] select[aria-label="LoRA slot 1"]')
  await expect(slot.locator('option', { hasText: 'smoke/mara_smoke' })).toHaveCount(1)                   // the e2e tree's file LoRA (e2e_setup.py)
  if (JSON.parse(process.env.LOOM2_E2E ?? '{}').variant === 'open') {                                       // D26: a file declares no licence — listed, disabled, with the sentence
    await expect(slot.locator('option[disabled]', { hasText: 'smoke/mara_smoke' })).toContainText('open variant')
    await expect(slot.locator('option:not([disabled])', { hasText: '· file' })).toHaveCount(0)              // no file is enabled (the project's own trained LoRA may be)
    return
  }
  await slot.selectOption('file:smoke/mara_smoke.safetensors')
  const strength = page.locator('[data-testid="world-sketches"] input[aria-label="LoRA strength 1"]')
  await expect(strength).toBeVisible()
  await strength.fill('0.7')
  await expect(page.locator('[data-testid="world-sketches"] select[aria-label="LoRA slot 2"]')).toBeEnabled()                       // the next slot opens
  await col.locator('#gen-sec-prompt').scrollIntoViewIfNeeded()
  await col.locator('#gen-sec-prompt .segmented button', { hasText: /^Text$/ }).click()
  await page.locator('[data-testid="world-sketches"] textarea').fill('a courier in the trained look')
  const known = new Set((await api<{ items: { id: string }[] }>('GET', '/jobs')).items.map((j) => j.id))
  const go = page.locator('[data-testid="world-sketches"] button', { hasText: /^Make \d+ sketch/ })
  await expect(go).toBeEnabled()
  const count = Number((await go.textContent())!.match(/Make (\d+)/)![1])
  await go.click()
  type Sketch = { id: string; status: string; origin: { surface?: string } | null; result: { asset_ids?: string[] } | null }
  const mine = async () => (await api<{ items: Sketch[] }>('GET', '/jobs')).items.filter((j) => !known.has(j.id) && j.origin?.surface === 'sketch')
  await expect.poll(async () => (await mine()).filter((j) => j.status === 'done').length, { timeout: 45_000 }).toBe(count)   // the sketches land in Sketches
  type Made = AssetLite & { params: { recipe: { loras: { model_id: string; strength: number }[] } } }
  const newest = await api<Made>('GET', `/assets/${(await mine())[0].result!.asset_ids![0]}`)
  expect(newest.params.recipe.loras).toEqual([{ model_id: 'file:smoke/mara_smoke.safetensors', strength: 0.7 }])
  type JobLite = { id: string; status: string; result: { compiled?: { loras?: { model_id: string; strength: number; lora_name: string | null }[] } } | null }
  const jobOf = async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.id === newest.job_id)!
  await expect.poll(async () => (await jobOf()).status, { timeout: 15_000 }).toBe('done')         // the asset lands a moment before its job is marked done
  const job = await jobOf()
  expect(job.result?.compiled?.loras?.[0]).toEqual({ model_id: 'file:smoke/mara_smoke.safetensors', strength: 0.7, lora_name: 'smoke/mara_smoke.safetensors' })
  // the slot is cleared by its own select; a model the file does not fit never lists it under the open variant (the backend's 422 covers the rest)
  await col.locator('#gen-sec-model').scrollIntoViewIfNeeded()
  await page.locator('[data-testid="world-sketches"] select[aria-label="LoRA slot 1"]').selectOption('')
  await expect(page.locator('[data-testid="world-sketches"] input[aria-label="LoRA strength 1"]')).toHaveCount(0)
})

test('a subject is a Cast character (D92 · UI7): the subject card picks a profile by its hero, shows its sheet (D93 B4: no copy), and the job carries its references through the profile mention (in Sketches, B2a)', async ({ page }) => {
  test.setTimeout(90_000)
  const name = `Ines ${Date.now().toString(36)}`
  const src = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0]
  const hero = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [src.id] })).ids[0]            // a copy: no other scenario's image moves
  type ProfileLite = { id: string; name: string; current: string; versions: { id: string; group_id: string }[] }
  const prof = await api<ProfileLite>('POST', '/story/profiles', { name, cls: 'character', hero_asset_id: hero, appearance: `${name}, a lighthouse keeper in a yellow oilskin` })
  await openShell(page, 'world/sketches')
  const col = page.locator('[data-testid="world-sketches"]')
  await col.locator('#gen-sec-model').scrollIntoViewIfNeeded()
  await col.locator('.model-card').filter({ has: page.locator('span', { hasText: /^Klein 4B$/ }) }).click()   // takes references
  await col.locator('#gen-sec-prompt').scrollIntoViewIfNeeded()
  await col.locator('#gen-sec-prompt .segmented button', { hasText: /^Tree$/ }).click()
  type GenHook = { getState: () => { panel: { tree: Record<string, unknown> }; set: (p: Record<string, unknown>) => void } }
  await page.evaluate(() => { const g = (window as unknown as { __loom2Generate: GenHook }).__loom2Generate.getState(); g.set({ tree: { ...g.panel.tree, subjects: [] }, mentions: [] }) })   // World seeds Make with the entity open: start from none
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
  const go = col.locator('button', { hasText: /^Make \d+ sketch/ })
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

test('Add to World ▸ (D93 · A2, B2a): a character without a look takes a Bin picture as its hero from the picture\'s right-click; World shows it', async ({ page }) => {
  const name = `Noor ${Date.now().toString(36)}`
  type Version = { id: string; group_id: string; hero_asset_id: string | null; appearance: string }
  type ProfileLite = { id: string; versions: Version[] }
  const prof = await api<ProfileLite>('POST', '/story/profiles', { name, cls: 'character' })              // no hero, no references
  expect(prof.versions[0].appearance).toBe('')                                                            // A9: the sheet starts empty
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const pic = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [img] })).ids[0]        // a copy, on no page: Imports
  await api('POST', '/groups/move', { items: [{ kind: 'asset', id: pic }], to: null })
  await openShell(page, 'bin')
  await openHome(page, 'imports')                                                                                // on no page: Imports shows them (B4: a stray until the next open)
  const tile = page.locator(`[data-testid="bin-grid"] .w-tile[data-id="${pic}"]`)
  await tile.click({ button: 'right' })
  await page.locator('.ctx-menu .item.sub', { hasText: 'Add to World' }).hover()
  await page.locator('.ctx-menu .ctx-menu > .item.sub', { hasText: `${name} · v1` }).first().hover()
  await page.locator('.ctx-menu .ctx-menu .ctx-menu button.item', { hasText: 'as the hero' }).click()
  await expect(page.locator('.toast', { hasText: `is ${name}'s hero` })).toBeVisible()
  await expect.poll(async () => (await api<ProfileLite>('GET', `/story/profiles/${prof.id}`)).versions[0].hero_asset_id).toBe(pic)
  const ref = (await api<{ group: { cover_id: string | null; items: { id: string }[] } }>('GET', `/groups/${prof.versions[0].group_id}`)).group
  expect(ref.cover_id).toBe(pic)                                                                           // onto the reference set, as its cover
  await expect(tile).toHaveCount(0)                                                                         // it left Imports
  await openShell(page, `world/character/${prof.id}/v1`)
  await expect(page.locator(`[data-testid="world-bin"] .w-tile[data-id="${pic}"] .w-badge`)).toHaveText('★')
})

test('a live character sheet (D93 · B4, B5): an outfit edited in Cast shows on the linked subject and rides the job; the version chip switches the job to that version\'s references (the Sheet and Sketches, B2a)', async ({ page }) => {
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
  await openMake(page, 'character', p1.id, 'v2')                                                         // D161: the sheet's words are Make's
  await expect(page.locator('[data-testid="world-header"]')).toContainText('v2 · winter')
  await page.locator('#cast-outfit').fill('a yellow oilskin')
  await page.locator('.cast-sheet button', { hasText: 'colour' }).click()
  await page.locator('.cast-sheet input[aria-label="colour 1: what it colours"]').fill('oilskin')
  await expect(page.locator('.cast-sheet .sheet-sent')).toContainText('wearing a yellow oilskin, #C0392B oilskin')
  await expect.poll(async () => { const v = (await api<ProfileLite>('GET', `/story/profiles/${p1.id}`)).versions[1]; return `${v.outfit}|${v.colours.map((c) => `${c.hex} ${c.object}`).join()}` }).toBe('a yellow oilskin|#C0392B oilskin')
  await page.screenshot({ path: 'node_modules/.e2e/d93b-smoke-cast.png' })
  // Generate: the subject linked to the character shows the edited sheet, the chip says the version
  await openShell(page, 'world/sketches')
  const col = page.locator('[data-testid="world-sketches"]')
  await col.locator('#gen-sec-model').scrollIntoViewIfNeeded()
  await col.locator('.model-card').filter({ has: page.locator('span', { hasText: /^Klein 4B$/ }) }).click()   // takes references
  await col.locator('#gen-sec-prompt').scrollIntoViewIfNeeded()
  await col.locator('#gen-sec-prompt .segmented button', { hasText: /^Tree$/ }).click()
  type GenHook = { getState: () => { panel: { tree: Record<string, unknown> }; set: (p: Record<string, unknown>) => void } }
  await page.evaluate(() => { const g = (window as unknown as { __loom2Generate: GenHook }).__loom2Generate.getState(); g.set({ tree: { ...g.panel.tree, subjects: [] }, mentions: [] }) })   // World seeds Make with the entity open: start from none
  await page.locator('.gen-tree .full button', { hasText: 'subject' }).click()
  const card = page.locator('.gen-tree .subject').last()
  await card.locator(`[aria-label^="subject"][aria-label$="from the Cast"] button[aria-label="${name}"]`).click()
  await expect(card.locator('.subject-sheet')).toContainText('a yellow oilskin')
  await expect(card.locator('.version-chip')).toHaveText(/v2 · winter/)
  await col.locator('#gen-sec-preview summary').click()
  await expect(page.locator('.preview-composed')).toContainText(`${name}, a tall woman with silver hair, wearing a yellow oilskin, #C0392B oilskin`)   // T8: as sent
  await expect(page.locator('.preview-box')).toContainText('wearing a yellow oilskin, #C0392B oilskin')
  const go = col.locator('button', { hasText: /^Make \d+ sketch/ })
  type JobLite = { id: string; status: string; recipe: { prompt_json?: { subjects?: { description?: string }[] }; refs?: { asset_id: string; mention?: string | null }[]; mentions?: { profile_id?: string | null; version?: string | null; group_id: string; asset_ids: string[]; composed?: string | null }[] } }
  const jobsFor = async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.filter((j) => j.recipe.mentions?.some((m) => m.profile_id === p1.id))
  await expect(go).toBeEnabled({ timeout: 30_000 })
  await go.click()
  await expect.poll(async () => { const js = await jobsFor(); return js.length > 0 && js.every((j) => j.status === 'done') }, { timeout: 60_000 }).toBe(true)
  const first = (await jobsFor())[0]
  const m1 = first.recipe.mentions!.find((m) => m.profile_id === p1.id)!
  expect(first.recipe.prompt_json?.subjects?.[0].description).toContain('wearing a yellow oilskin, #C0392B oilskin')   // the job's prompt carries the sheet's edit
  expect(m1.version).toBe('v2')
  expect(m1.group_id).toBe(v2.group_id)
  expect(m1.composed).toBe(first.recipe.prompt_json?.subjects?.[0].description)
  // the version chip: v1 (rain gear) — its sheet on the card, and the next job takes v1's references
  await card.locator('.version-chip').click()
  await page.locator('.ctx-menu button.item', { hasText: 'v1 · rain gear' }).click()
  await expect(card.locator('.version-chip')).toHaveText(/v1 · rain gear/)
  await expect(card.locator('.subject-sheet')).toContainText('a grey wool coat')
  await expect(page.locator('.preview-composed')).toContainText('wearing a grey wool coat', { timeout: 20_000 })
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

test('a shot\'s place (D93 · C6, B2a): the Flow Inspector sets where a shot with lines happens, from World\'s places; the node\'s card says it', async ({ page }) => {
  test.setTimeout(150_000)
  const tag = Date.now().toString(36)
  const src = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0]
  const copies = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [src.id, src.id, src.id] })).ids   // copies: no other scenario's image moves
  type ProfileLite = { id: string; name: string; versions: { id: string; group_id: string }[] }
  const mk = (name: string, cls: string, hero: string, appearance: string) => api<ProfileLite>('POST', '/story/profiles', { name, cls, hero_asset_id: hero, appearance })
  const mara = await mk(`Mara ${tag}`, 'character', copies[0], `Mara ${tag}, a wiry courier`)
  const joe = await mk(`Joe ${tag}`, 'character', copies[1], 'a tall fisherman with a grey beard')
  const quay = await mk(`Quay ${tag}`, 'place', copies[2], 'a stone quay at dusk, fishing boats')
  const node = await api<{ id: string }>('POST', '/story/flow/nodes', { type: 'dialogue', title: `At the gate ${tag}`, x: 2400, y: 1600 })
  await api('POST', `/story/flow/nodes/${node.id}/shot`, { name: `Gate ${tag}` })
  type NodeLite = { id: string; revision: number; place_id: string | null }
  const nodeOf = async () => (await api<{ nodes: NodeLite[] }>('GET', '/story/flow')).nodes.find((n) => n.id === node.id)!
  await api('PATCH', `/story/flow/nodes/${node.id}`, { revision: (await nodeOf()).revision, lines: [{ speaker: mara.id, text: '"We go at dawn."' }, { speaker: joe.id, text: 'Not without the key.' }, { speaker: mara.id, text: 'Then find it.' }] })
  // Shots' Flow: the node's Inspector — where (a place of World)
  await openShell(page, 'shots/flow')
  type Hook = { loadFlow: () => Promise<void>; selectNode: (id: string | null) => void }
  await page.waitForFunction(() => !!(window as unknown as { __loom2Story?: unknown }).__loom2Story)
  await page.evaluate(async (id) => { const h = (window as unknown as { __loom2Story: Hook }).__loom2Story; await h.loadFlow(); h.selectNode(id) }, node.id)
  await page.locator('.s-insp select[aria-label="where (a Cast place)"]').selectOption(quay.id)
  await expect.poll(async () => (await nodeOf()).place_id).toBe(quay.id)
  await expect(page.locator(`.flow-node[data-id="${node.id}"] .place`)).toHaveText(`@ ${quay.name}`)
})

test('figures bound to characters (D93 · C8): a figure picks a character in the Inspector or by right-click, the Outliner says who, the Render tab\'s deck shows each figure\'s slot, and the frame\'s job carries their references and sheets left to right (Shots, B2a)', async ({ page }) => {
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
  await clayOn(page, st0.id, `Figures ${tag}`)
  type StageHook = { open: (id: string) => Promise<void> }
  await expect.poll(async () => page.evaluate(() => !!(window as unknown as { __loom2Stage?: StageHook }).__loom2Stage), { timeout: 30_000 }).toBe(true)
  await page.evaluate(async (id) => { await (window as unknown as { __loom2Stage: StageHook }).__loom2Stage.open(id) }, st0.id)
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await section(page, 'scene')
  // the left figure: the Inspector's tiles (the Cast's characters by their heroes)
  await page.locator('.outl-row[data-row="object"]').filter({ has: page.locator('.name', { hasText: 'Left one' }) }).click()
  const tile = page.locator(`.w-panel [aria-label="the figure's character"] button[aria-label="${ana.name}"]`)   // D95 (AN1): the Selection section
  await expect(tile.locator('img')).toBeVisible()
  await tile.click()
  await expect(page.locator('.outl-row[data-row="object"]').filter({ has: page.locator('.name', { hasText: 'Left one' }) }).locator('.bound-tag')).toContainText(ana.name)
  // the right figure: right-click ▸ Bind to a character ▸ Bo
  await page.locator('.outl-row[data-row="object"]').filter({ has: page.locator('.name', { hasText: 'Right one' }) }).click({ button: 'right' })
  await page.locator('.ctx-menu .item.sub', { hasText: 'Bind to a character' }).hover()
  await page.locator('.ctx-menu button.item', { hasText: bo.name }).click()
  await expect(page.locator('.outl-row[data-row="object"]').filter({ has: page.locator('.name', { hasText: 'Right one' }) }).locator('.bound-tag')).toContainText(bo.name)
  await expect.poll(async () => (await api<StageLite>('GET', `/stages/${st0.id}`)).objects.map((o) => [o.id, o.profile_id]), { timeout: 10_000 }).toEqual([['fig_r', bo.id], ['fig_l', ana.id]])
  // the frame form (D121: Image › From a stage): the deck's figure slots (image 2 the left figure's, image 3 the right's) and the lines
  await fromStageIn(page)
  await expect(page.locator('.shot-tab .figure-slot')).toHaveCount(2, { timeout: 20_000 })
  await expect(page.locator('.shot-tab .figure-slot').nth(0).locator('.fig-badge')).toHaveText(`fig 1 · ${ana.name}`)
  await expect(page.locator('.shot-tab .figure-lines')).toContainText(`figure 1 · ${ana.name} → image 2`)
  await expect(page.locator('.shot-tab .prompt-preview')).toContainText(`figure 1 is ${ana.name} (reference image 2), a short woman in a red raincoat; figure 2 is ${bo.name} (reference image 3)`)
  await page.locator('.shot-tab button', { hasText: /^Render passes$/ }).click()
  const go = page.locator('[data-testid="world-sketches"] .w-foot button.primary', { hasText: /^Render frame/ })
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

test('Flatten image (D90 · UI6): the canvas menu\'s Layer ▸ folds a group, a blend mode and an adjustment into one layer, exactly as the server flattens; Undo brings the layers back; Save (D95: the document and a Catalogue version) still matches (World’s Edit, B2a)', async ({ page }) => {
  type Ed = { getState: () => { doc: { id: string; layers: { id: string; name: string; kind: string }[] } | null; addLayer: (k: string, extra?: Record<string, unknown>) => unknown; updateNode: (id: string, p: Record<string, unknown>) => void; groupNodes: (ids: string[]) => void; duplicateNodes: (ids: string[]) => void; undo: () => void; save: () => Promise<boolean>; docDirty: boolean } }
  const ed = () => page.evaluate(() => { const s = (window as unknown as { __loom2Editor: Ed }).__loom2Editor.getState(); return { layers: s.doc!.layers.map((n) => ({ id: n.id, name: n.name, kind: n.kind })), dirty: s.docDirty } })
  const raw = async (docId: string): Promise<Buffer> => {
    const e = env()
    const r = await fetch(`http://127.0.0.1:${e.port}/documents/${docId}/export`, { method: 'POST', headers: { 'X-Loom-Token': e.token, 'Content-Type': 'application/json' }, body: JSON.stringify({ format: 'raw' }) })
    expect(r.status).toBe(200)
    return Buffer.from(await r.arrayBuffer())
  }
  await openShell(page, 'bin', { renderer: 'webgl' })
  await openHome(page, 'world/sketches', 'pictures')
  const photo = (await sketchPics(8)).at(-1)!.id   // a plain photo (a saved document has layers)
  await contextChoose(page, page.locator(`[data-testid="bin-grid"] .w-tile[data-id="${photo}"]`), 'Open in Edit')
  const docId = await page.waitForFunction(() => (window as unknown as { __loom2Editor?: Ed }).__loom2Editor?.getState().doc?.id ?? null).then((h) => h.jsonValue() as Promise<string>)
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
  await expect(page.locator('.toast', { hasText: /^Saved · a new version in the Bin/ })).toBeVisible()
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

test('the drawer (D95 · AN1, B2a): the Dock\'s Bin in World\'s Sketches and Shots\' Performance — a double-click adds a reference in Make and sets the start frame in Performance; a tile dragged onto a reference slot takes it', async ({ page }) => {
  const tag = Date.now().toString(36)
  const a = await api<{ shot_id: string }>('POST', '/story/flow/shots', { title: `Drawer ${tag}`, scene: 'new' })
  await openShell(page, 'world/sketches')
  await page.locator('.dock .dock-tabs button', { hasText: 'Bin' }).click()
  const grid = page.locator('.dock .bin-grid')
  await drawerHome(page, 'world/sketches')
  await page.locator('.dock .bin-bar .segmented button', { hasText: 'pictures' }).click()
  const tile = grid.locator('.w-tile').first()
  await expect(tile).toBeVisible()
  const id = (await tile.getAttribute('data-id'))!
  await page.locator('[data-testid="world-sketches"] #gen-sec-refs').scrollIntoViewIfNeeded()
  await tile.dblclick()                                                                                      // Make: a reference
  await expect(page.locator('.ref-slots .ref-slot img').first()).toHaveAttribute('src', new RegExp(id))
  // a tile dragged onto an empty reference slot takes it (frame/drag.ts)
  const second = grid.locator('.w-tile').nth(1)
  const id2 = (await second.getAttribute('data-id'))!
  const slot = page.locator('.ref-slots .ref-slot:not(:has(img))').first()
  const from = await centre(second), to = await centre(slot)
  await page.mouse.move(from.x, from.y); await page.mouse.down()
  await page.mouse.move(from.x + 12, from.y - 8, { steps: 3 })
  await page.mouse.move(to.x, to.y, { steps: 12 })
  await page.mouse.up()
  await expect(page.locator(`.ref-slots .ref-slot img[src*="${id2}"]`)).toHaveCount(1)
  await page.goto(`${appUrl()}#shots/${a.shot_id}/performance`)
  await page.locator('.perf-cards button', { hasText: 'Image to video' }).click()
  await expect(page.locator('.perf-cards button.active')).toHaveText('Image to video')
  await expect(page.locator('.dock .bin')).toBeVisible()                                                    // the drawer stays open across the layers
  await page.locator('.dock .bin-grid .w-tile').nth(1).dblclick()                                           // Performance: the start frame
  await expect(page.locator('.slots .slot').first().locator('img')).toBeVisible()
  await page.locator('nav.tabs button.tab', { hasText: 'Bin' }).click()
  await expect(page.locator('.dock .dock-tabs button', { hasText: 'Bin' })).toHaveCount(0)                  // the Bin layer is the Bin itself
})

test("the Bin's Trash (B2a): a tile's right-click moves it to the trash, which counts it; there Restore puts it back and Delete permanently… removes it (asked first); the drawer's double-click restores", async ({ page }) => {
  await openShell(page, 'bin')
  await openHome(page, 'world/sketches')
  await page.locator('[data-testid="bin-grid"] .w-chips button', { hasText: 'pictures' }).click()
  await expect(page.locator('[data-testid="bin-count"]')).toBeVisible()
  const id = (await binTiles(page).last().getAttribute('data-id'))!
  const tile = page.locator(`[data-testid="bin-grid"] .w-tile[data-id="${id}"]`)                     // by its id: a landing asset moves the others
  const trashedAt = async () => (await api<{ trashed_at: string | null }>('GET', `/assets/${id}`)).trashed_at
  await contextChoose(page, tile, 'Trash')
  await expect.poll(trashedAt, { timeout: 10_000 }).toBeTruthy()
  await expect(tile).toHaveCount(0)                                                                  // gone from Imports
  const trash = page.locator('[data-testid="bin-tree"] .b-node[data-path="trash"]')
  await expect(trash.locator('.n')).toHaveText(/^[1-9]\d*$/)
  await trash.locator('.b-open').click()
  await expect(trash).toHaveClass(/active/)
  const there = page.locator(`[data-testid="bin-grid"] .w-tile[data-id="${id}"]`)
  await expect(there).toBeVisible()
  await expect(page.locator('[data-testid="bin-grid"] .w-bin-head button', { hasText: /Empty trash/ })).toBeEnabled()
  await page.screenshot({ path: 'node_modules/.e2e/bin-trash.png' })
  await contextChoose(page, there, 'Restore')
  await expect.poll(trashedAt, { timeout: 10_000 }).toBeNull()
  await expect(there).toHaveCount(0)
  // trashed again; the drawer's double-click restores it (D95)
  await api('POST', '/assets/trash', { ids: [id] })
  await page.locator('nav.tabs button.tab', { hasText: 'World' }).click()
  await page.locator('.dock .dock-tabs button', { hasText: 'Bin' }).click()
  await page.locator('[data-testid="bin-drawer-homes"] .b-node[data-path="trash"] .b-open').click()
  await page.locator(`.dock .bin-grid .w-tile[data-id="${id}"]`).dblclick()
  await expect.poll(trashedAt, { timeout: 10_000 }).toBeNull()
  // trashed again, then deleted permanently from its right-click
  await api('POST', '/assets/trash', { ids: [id] })
  await page.locator('nav.tabs button.tab', { hasText: 'Bin' }).click()
  await page.locator('[data-testid="bin-tree"] .b-node[data-path="trash"] .b-open').click()
  await contextChoose(page, there, 'Delete permanently…')
  const dialog = page.locator('.modal.ask')
  await expect(dialog).toContainText('cannot be undone')
  await dialog.locator('button', { hasText: /^Delete permanently$/ }).click()
  await expect.poll(async () => { try { await trashedAt(); return 'there' } catch { return 'gone' } }, { timeout: 10_000 }).toBe('gone')
  await expect(there).toHaveCount(0)
})

test('AN1 step 5 (D95): the Clay level adds an image plane from the Bin, renames it by right-click, shows the passes in Scene; Image · Make has From a stage (Shots, B2a)', async ({ page }) => {
  await clayShot(page, 'Plane test')
  const dialog = page.locator('.modal.ask')
  await section(page, 'scene')
  await expect(page.locator('.s-foot [data-passes-state]')).toContainText('No passes yet for')         // #16: the passes at a glance (D121: in the Clay foot)
  await page.locator('.lib-row[data-group="planes"] button', { hasText: /^Add image plane/ }).click()                           // #18: opens the Bin
  const bin = page.locator('.dock .bin')
  await expect(bin).toBeVisible()
  await drawerHome(page, 'world/sketches')
  await bin.locator('.bin-bar .segmented button', { hasText: 'pictures' }).click()
  await bin.locator('.bin-grid .w-tile').first().dblclick()                                                    // the Clay level's verb: an image plane
  const row = page.locator('.outl-row', { has: page.locator('.kind', { hasText: 'plane' }) })
  await expect(row).toHaveCount(1)
  await row.click({ button: 'right' })
  await page.locator('.ctx-menu button.item', { hasText: /^Rename/ }).click()                                // D32: rename has a mouse placement
  await dialog.locator('input').fill('Backdrop')
  await dialog.locator('button.primary').click()
  await expect(row.locator('.name')).toHaveText('Backdrop')
  await fromStageIn(page)                                                                                    // #5: stills from the stage, in Sketches
  await expect(page.locator('.from-stage select[aria-label="the stage"] option:checked')).toHaveText('Plane test')
  await expect(page.locator('.from-stage select[aria-label="the camera"]')).toBeVisible()
  await page.locator('[data-testid="world-sketches"] .gen-source .segmented button', { hasText: 'Prompt' }).click()
  await expect(page.locator('.from-stage')).toHaveCount(0)
})

test("the bench and a prop's height (D142, CW4): Bench ▶ opens Clay for the character, bound, with its chip and the way back; a prop's height is read from its name, edited in Cast, and its model stands at it on its bench beside a 1.75 m figure (World’s Sheet, B2a)", async ({ page }) => {
  test.setTimeout(120_000)
  const tag = Date.now().toString(36)
  type V = { id: string; height_m: number | null; model_asset_id: string | null }
  type ProfileLite = { id: string; current: string; versions: V[] }
  type StageLite = { id: string; name: string; purpose: string; bound: { profile_id: string; version: string } | null; objects: { id: string; kind: string; profile_id: string | null; height_m: number | null; body: { height_m: number } | null }[] }
  const mara = await api<ProfileLite>('POST', '/story/profiles', { name: `Mara ${tag}`, cls: 'character', appearance: 'a fisher' })
  await api('PATCH', `/story/profiles/${mara.id}`, { revision: 0, versions: [{ id: 'v1', body: { height_m: 1.62 } }] })
  await openBuild(page, 'character', mara.id)
  await page.locator('.cast-body button', { hasText: /^Bench/ }).first().click()
  await expect(page.locator('[data-testid="world-clay"] canvas').first()).toBeVisible({ timeout: 20_000 })   // the bench, inside World
  await expect(page.locator('.w-mode button.active')).toHaveText('Clay')
  const benches = async () => (await api<{ items: StageLite[] }>('GET', '/stages?purpose=bench')).items
  await expect.poll(async () => (await benches()).some((b) => b.bound?.profile_id === mara.id), { timeout: 10_000 }).toBe(true)
  const bench = (await benches()).find((b) => b.bound?.profile_id === mara.id)!
  expect(bench.objects[0].profile_id).toBe(mara.id)
  expect(bench.objects[0].body?.height_m).toBe(1.62)
  expect((await api<{ items: StageLite[] }>('GET', '/stages')).items.map((s) => s.id)).not.toContain(bench.id)          // out of the stage list
  await page.screenshot({ path: 'node_modules/.e2e/cw3-bench.png' })
  await page.locator('.w-mode button', { hasText: 'Build' }).click()
  await expect(page.locator('[data-testid="world-build"]')).toBeVisible()
  // CW4: a prop's height — read from its name, edited in Cast; its bench stands the model at it
  const cup = await api<ProfileLite>('POST', '/story/profiles', { name: `Grandma cup ${tag}`, cls: 'prop' })
  expect(cup.versions[0].height_m).toBe(0.1)
  const glb = `${process.cwd().replace(/\\/g, '/')}/../orchestrator/tests/fixtures/motion/test_rig.glb`      // a GLB import (D128): both builds, no job
  await api('POST', `/story/profiles/${cup.id}/versions/v1/model/import`, { path: glb })
  await openBuild(page, 'prop', cup.id)
  const h = page.locator('.prop-height input')
  await expect(h).toHaveValue('0.1')
  await h.fill('0.12'); await h.press('Enter')
  await expect.poll(async () => (await api<ProfileLite>('GET', `/story/profiles/${cup.id}`)).versions[0].height_m, { timeout: 10_000 }).toBe(0.12)
  await page.locator('.prop-model button', { hasText: /^Bench/ }).click()
  await expect(page.locator('.w-mode button.active')).toHaveText('Clay')
  const pb = (await benches()).find((b) => b.bound?.profile_id === cup.id)!
  expect(pb.objects.map((o) => o.kind)).toEqual(['mesh', 'mannequin'])
  expect(pb.objects[0].height_m).toBe(0.12)
  const drawn = async (id: string) => page.evaluate((x) => (window as unknown as { __loom2Stage: { heightOf: (id: string) => number | null } }).__loom2Stage.heightOf(x), id)
  await expect.poll(async () => drawn(pb.objects[0].id), { timeout: 20_000 }).toBeCloseTo(0.12, 2)          // the model at its height (the GLB arrives)
  await expect.poll(async () => (await drawn(pb.objects[1].id)) ?? 0, { timeout: 10_000 }).toBeGreaterThan(1.6)   // the figure beside it
  await page.screenshot({ path: 'node_modules/.e2e/cw4-prop-bench.png' })
})

test("a place's set (CW6, D143): Build the set ▶ queues MoGe on the set picture and says when the relief fits nothing; a fitted set is drawn over its picture and baked on its own; a wall's foot dragged deepens the room; the kind is one click; a face's material is named; Fill ▶ paints the faces one after another; Bench ▶ opens Clay on the set from the picture's camera (World’s Sheet, B2a)", async ({ page }) => {
  test.setTimeout(180_000)
  const tag = Date.now().toString(36)
  type Face = { id: string; texture_asset_id: string | null; baked_asset_id: string | null; seen: number | null; bad: number | null; filled: boolean; material: string; fill_job_id: string | null;
    crowd?: { status: string; from_m: number; to_m: number; clip_id: string | null } | null; walkers?: { status: string; kept: number; asset_id: string | null }[] }
  type PS = { kind: string; sizes: Record<string, number>; parts: Record<string, boolean>; faces: Face[]; sources: { asset_id: string; camera: { pos: number[]; target: number[] } }[]; baked_key: string | null }
  type ProfileLite = { id: string; revision: number; versions: { id: string; place_set: PS | null; anim_ref_asset_id: string | null }[] }
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const place = await api<ProfileLite>('POST', '/story/profiles', { name: `Farm kitchen ${tag}`, cls: 'place', appearance: 'a farmhouse kitchen, whitewashed walls' })
  await api('PUT', `/story/profiles/${place.id}/versions/v1/anim-ref`, { side: 'front', asset_id: img })                 // the set picture
  const prof = async () => api<ProfileLite>('GET', `/story/profiles/${place.id}`)
  const ps = async () => (await prof()).versions[0].place_set
  await openBuild(page, 'place', place.id)
  const sec = page.locator('section.place-set')
  await expect(sec.locator('[data-status]')).toHaveText('no set yet')
  // Build the set ▶: MoGe on the set picture; the fake engine's relief is a bare triangle — the fit says so, and nothing is set
  await sec.locator('button', { hasText: /^Build the set/ }).click()
  await expect(sec.locator('[data-status]')).toContainText('not fitted', { timeout: 30_000 })
  const jobs = (await api<{ items: { origin: { surface: string; ref: string; payload: Record<string, unknown> } | null; recipe: { kind: string; asset_id: string } }[] }>('GET', '/jobs')).items
  const fit = jobs.find((j) => j.origin?.surface === 'set_fit' && j.origin.ref === place.id)!
  expect(fit.recipe).toMatchObject({ kind: 'image_to_set', asset_id: img })
  expect(fit.origin!.payload).toMatchObject({ version: 'v1', camera_height_m: 1.6 })
  expect(await ps()).toBeNull()
  // a set as a fit leaves it (a room seen from near its front, the camera at eye level): drawn over the picture, then baked here
  const p0 = await prof()
  await api('PUT', `/story/profiles/${place.id}/versions/v1/set`, { revision: p0.revision, place_set: { kind: 'room', sizes: { width: 5, depth: 6, height: 2.8 }, parts: {}, faces: [], baked_key: null,
    sources: [{ asset_id: img, camera: { pos: [0.3, 1.6, 2], target: [0.1, 1.3, -3], roll: 0, focal_mm: 24, sensor_mm: 36 }, relief_asset_id: null, assumed: ['front', 'height'], lens_deg: 73.7 }] } })
  await expect(sec.locator('.set-overlay polygon.face')).not.toHaveCount(0, { timeout: 10_000 })
  await expect(sec.locator('[data-handle="back"]')).toHaveCount(1)
  await expect(sec.locator('[data-handle="top_back"].assumed')).toHaveCount(1)                                         // the height was guessed: dashed
  await expect.poll(async () => (await ps())?.faces.filter((f) => f.baked_asset_id).length ?? 0, { timeout: 30_000 }).toBe(5)   // the front wall is off
  const baked = (await ps())!
  expect(baked.baked_key).toBeTruthy()
  expect(baked.faces.find((f) => f.id === 'wall_back')!.seen ?? 0).toBeGreaterThan(0.95)                               // the back wall seen whole (the fake's small pictures: coarse, so still to fill)
  await expect(sec.locator('.set-face')).toHaveCount(5)
  // a wall's foot dragged up the picture: the back wall further away, the room deeper
  const foot = sec.locator('[data-handle="back"] .hit')
  await sec.locator('.set-view').scrollIntoViewIfNeeded()
  const box = (await foot.boundingBox())!
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2 - 30, { steps: 6 })
  await page.mouse.up()
  await expect.poll(async () => (await ps())?.sizes.depth ?? 0, { timeout: 10_000 }).toBeGreaterThan(6.5)
  await expect(sec.locator('[data-status]')).toHaveText('changed since the bake')
  await page.screenshot({ path: 'node_modules/.e2e/cw6-set-builder.png' })
  // the kind is one click, and back; Bake again ▶ bakes the set as it is now
  await sec.locator('.set-kind button', { hasText: /^Corridor$/ }).click()
  await expect.poll(async () => (await ps())?.kind, { timeout: 10_000 }).toBe('corridor')
  await sec.locator('.set-kind button', { hasText: /^Room$/ }).click()
  await expect.poll(async () => (await ps())?.kind, { timeout: 10_000 }).toBe('room')
  await sec.locator('button', { hasText: /^Bake again/ }).click()
  await expect.poll(async () => (await ps())?.faces.filter((f) => f.baked_asset_id).length ?? 0, { timeout: 30_000 }).toBe(5)
  await expect(sec.locator('[data-status]')).toContainText('to fill')
  // a face's material, named for its Fill
  const wall = sec.locator('.set-face[data-face="wall_left"] input')
  await wall.fill('pale ochre plaster'); await wall.press('Enter')
  await expect.poll(async () => (await ps())?.faces.find((f) => f.id === 'wall_left')?.material, { timeout: 10_000 }).toBe('pale ochre plaster')
  // Fill ▶: face after face (the fake engine paints them), each its own texture
  const toFill = (await ps())!.faces.filter((f) => (f.bad ?? 0) >= 0.002).length
  expect(toFill).toBeGreaterThan(0)
  await sec.locator('button', { hasText: /^Fill what the picture never saw/ }).click()
  await expect.poll(async () => (await ps())?.faces.filter((f) => f.filled).length ?? 0, { timeout: 90_000 }).toBe(toFill)
  const filled = (await ps())!.faces.filter((f) => f.filled)
  expect(filled.every((f) => f.texture_asset_id !== f.baked_asset_id && !f.fill_job_id)).toBe(true)
  await expect(sec.locator('[data-status]')).toHaveText('baked and filled')
  // D173: a crowd along the back wall — Crowd ▶ opens the stretch, Make ▶ queues the picture then its loop (the fake engine makes both), the row says it
  const crowdRow = sec.locator('[data-testid="crowd-wall_back"]')
  await crowdRow.locator('button', { hasText: /^Crowd/ }).click()
  await crowdRow.locator('input[aria-label="wall_back: the crowd to (m)"]').fill('4')
  await crowdRow.locator('button', { hasText: /^Make/ }).click()
  await expect.poll(async () => (await ps())?.faces.find((f) => f.id === 'wall_back')?.crowd?.status, { timeout: 120_000 }).toBe('done')
  await expect(crowdRow).toContainText('crowd · 0–4 m')
  expect((await ps())!.faces.find((f) => f.id === 'wall_back')!.crowd!.clip_id).toBeTruthy()
  // D174: walkers along the back wall too — Walkers ▶, Make ▶: the picture, its loop, SAM 3 (the fake: a standing figure), the walkers packed
  const walkRow = sec.locator('[data-testid="walkers-wall_back"]')
  await walkRow.locator('button', { hasText: /^Walkers/ }).click()
  await walkRow.locator('input[aria-label="wall_back: the walkers to (m)"]').fill('4')
  await walkRow.locator('button', { hasText: /^Make/ }).click()
  await expect.poll(async () => (await ps())?.faces.find((f) => f.id === 'wall_back')?.walkers?.[0]?.status, { timeout: 120_000 }).toBe('done')
  await expect(walkRow).toContainText('walkers · 0–4 m')
  expect((await ps())!.faces.find((f) => f.id === 'wall_back')!.walkers![0].kept).toBeGreaterThan(0)
  // Bench ▶: Clay on the set, bound to the place, from the picture's camera
  await sec.locator('button', { hasText: /^Bench/ }).click()
  await expect(page.locator('.w-mode button.active')).toHaveText('Clay')                                    // Clay on the set, inside World
  type StageLite = { bound: { profile_id: string } | null; objects: { kind: string; preset: string | null; profile_id: string | null; place_set: PS | null }[]; cameras: { pos: number[] }[] }
  const bench = (await api<{ items: StageLite[] }>('GET', '/stages?purpose=bench')).items.find((b) => b.bound?.profile_id === place.id)!
  expect(bench.objects[0]).toMatchObject({ kind: 'set', preset: 'built', profile_id: place.id })
  expect(bench.objects[0].place_set!.faces.filter((f) => f.filled)).toHaveLength(toFill)
  expect(bench.cameras[0].pos).toEqual((await ps())!.sources[0].camera.pos)
  await page.waitForTimeout(1500)                                                                // the faces' textures arrive
  await page.screenshot({ path: 'node_modules/.e2e/cw6-bench.png' })
})

test("places in Clay (CW7): Sets' + lists the Cast places that have a set — a click adds it bound, tagged with its place; a free copy stands beside it; the final shot's plate is the built set, rendered with no Klein still; a picture set becomes a Cast place with its set being built (Shots, B2a)", async ({ page }) => {
  test.setTimeout(180_000)
  const tag = Date.now().toString(36)
  type Obj = { id: string; kind: string; preset: string | null; name: string; profile_id: string | null; plate_asset_id: string | null }
  type StageLite = { id: string; name: string; revision: number; objects: Obj[]; cameras: { id: string }[] }
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const place = await api<{ id: string; revision: number }>('POST', '/story/profiles', { name: `Dock house ${tag}`, cls: 'place' })
  const cam = { pos: [0.3, 1.6, 2], target: [0.1, 1.3, -3], roll: 0, focal_mm: 24, sensor_mm: 36 }
  const face = (id: string) => ({ id, texture_asset_id: img, baked_asset_id: img, coverage_asset_id: null, texel_m: 0.01, seen: 1, bad: 0, filled: false, material: '', fill_job_id: null })
  await api('PUT', `/story/profiles/${place.id}/versions/v1/set`, { revision: place.revision, place_set: { kind: 'room', sizes: { width: 5, depth: 6, height: 2.8 }, parts: {}, baked_key: 'k',
    faces: ['floor', 'wall_back', 'wall_left', 'wall_right', 'ceiling'].map(face), sources: [{ asset_id: img, camera: cam, relief_asset_id: null, assumed: [], lens_deg: 73.7 }] } })
  await clayShot(page, `Dock ${tag}`)
  const dialog = page.locator('.modal.ask')
  await section(page, 'scene')
  const doc = async () => (await api<{ items: StageLite[] }>('GET', '/stages')).items.find((s) => s.name === `Dock ${tag}`)!
  // the place's card in Sets' +: its set, bound
  await libAdd(page, 'sets', `Dock house ${tag}`)
  await page.keyboard.press('Escape')                                                              // the + panel stays open for more; it would cover the rows
  await expect.poll(async () => (await doc()).objects.filter((o) => o.kind === 'set').map((o) => `${o.preset} ${o.profile_id}`), { timeout: 10_000 }).toEqual([`built ${place.id}`])
  const bound = (await doc()).objects.find((o) => o.kind === 'set')!
  const row = page.locator(`.outl-row[data-id="${bound.id}"]`)
  await expect(row.locator('.bound-tag')).toContainText(`Dock house ${tag}`)
  await page.waitForTimeout(800)                                                                   // the faces' textures arrive
  await page.screenshot({ path: 'node_modules/.e2e/cw7-clay-set.png' })
  // a free copy beside it
  await row.locator('.name').click({ button: 'right' })
  await page.locator('.ctx-menu button.item', { hasText: /^Make a free copy/ }).click()
  await expect.poll(async () => (await doc()).objects.filter((o) => o.kind === 'set').map((o) => o.profile_id), { timeout: 10_000 }).toEqual([place.id, null])
  // the final shot: the plate is the built set, Stage renders it (no Klein still)
  await page.evaluate(() => (window as unknown as { __loom2Stage: { setRange: (a: number, b: number) => void } }).__loom2Stage.setRange(0, 3))
  const shotJobs = async () => (await api<{ items: { kind: string }[] }>('GET', '/jobs')).items.filter((j) => j.kind === 'stage_shot').length
  const before = await shotJobs()
  await perfCardOf(page, 'Final shot')
  await page.locator('.final-section button', { hasText: /^Make the final shot/ }).click()
  await expect(dialog).toContainText(/the plate from the built set/)
  await dialog.locator('button.primary').click()
  type FinP = { id: string; frames: number; layers: { id: string; method: string; status: string; frames_done: number; still_asset_id: string | null }[] }
  const st0 = await doc()
  const finOf = async () => (await api<{ items: FinP[] }>('GET', `/finals?stage_id=${st0.id}`)).items[0]
  await expect.poll(async () => { const f = await finOf(); const p = f?.layers.find((x) => x.id === 'plate'); return p ? `${p.method} ${p.status} ${p.frames_done}/${f.frames}` : '' }, { timeout: 60_000 })
    .toBe('set done 3/3')
  expect((await finOf()).layers.find((x) => x.id === 'plate')!.still_asset_id).toBe(img)
  expect(await shotJobs()).toBe(before)
  // a picture set becomes a Cast place: its picture the set picture, its set being built
  const made = await api<{ job_id: string }>('POST', `/stages/${st0.id}/image-set`, { asset_id: img, lens_deg: 70 })
  await expect.poll(async () => (await api<{ items: { id: string; status: string }[] }>('GET', '/jobs')).items.find((j) => j.id === made.job_id)?.status, { timeout: 60_000 }).toBe('done')
  await page.evaluate(async (id) => { await (window as unknown as { __loom2Stage: { open: (id: string) => Promise<void> } }).__loom2Stage.open(id) }, st0.id)
  await toLevel(page, 'clay')
  await section(page, 'scene')
  const pic = (await doc()).objects.find((o) => o.kind === 'set' && o.preset === 'image')!
  await page.locator(`.outl-row[data-id="${pic.id}"] .name`).click({ button: 'right' })
  await page.locator('.ctx-menu button.item', { hasText: /^Make it a Cast place/ }).click()
  await dialog.locator('input').fill(`Quay ${tag}`)
  await dialog.locator('button.primary').click()
  type ProfileLite = { id: string; name: string; cls: string; versions: { anim_ref_asset_id: string | null }[] }
  await expect.poll(async () => (await api<{ items: ProfileLite[] }>('GET', '/story/profiles')).items.find((p) => p.name === `Quay ${tag}`)?.versions[0].anim_ref_asset_id ?? null, { timeout: 10_000 })
    .toBe(pic.plate_asset_id)
  const quay = (await api<{ items: ProfileLite[] }>('GET', '/story/profiles')).items.find((p) => p.name === `Quay ${tag}`)!
  expect(quay.cls).toBe('place')
  const fits = (await api<{ items: { origin: { surface: string; ref: string } | null }[] }>('GET', '/jobs')).items.filter((j) => j.origin?.surface === 'set_fit' && j.origin.ref === quay.id)
  expect(fits).toHaveLength(1)
})

test("Cast in Clay and the line-up (CW3, CW5): a Cast character's card adds its figure bound; Make a free copy frees one with its body; Line-up ▶ stands the characters side by side and Send to a stage ▸ copies them into a new stage (Shots’ Clay and World, B2a)", async ({ page }) => {
  test.setTimeout(120_000)
  const tag = Date.now().toString(36)
  type StageLite = { id: string; name: string; purpose: string; objects: { id: string; kind: string; name: string; profile_id: string | null; preset: string | null; body: { height_m: number } | null }[] }
  const ines = await api<{ id: string }>('POST', '/story/profiles', { name: `Ines ${tag}`, cls: 'character' })
  await api('PATCH', `/story/profiles/${ines.id}`, { revision: 0, versions: [{ id: 'v1', body: { height_m: 1.58 } }] })
  const shot = await api<{ shot_id: string }>('POST', '/story/flow/shots', { title: `Market ${tag}`, scene: 'new' })
  const st = { id: (await api<{ versions: { stage_id: string }[] }>('GET', `/story/shots/${shot.shot_id}`)).versions[0].stage_id }
  await openShell(page, `shots/${shot.shot_id}/clay`)
  await page.locator('#anim-sec-scene').scrollIntoViewIfNeeded()
  // CW3: Cast's characters are cards in Figures' +: a click adds the character's figure, bound
  await libAdd(page, 'figures', `Ines ${tag}`)
  await page.keyboard.press('Escape')                                                              // the + panel stays open for more; it would cover the rows
  const doc = async () => api<StageLite>('GET', `/stages/${st.id}`)
  await expect.poll(async () => (await doc()).objects.find((o) => o.profile_id === ines.id)?.body?.height_m ?? null, { timeout: 10_000 }).toBe(1.58)
  // Make a free copy (the figure's right-click): free, its body as it is
  await page.locator('.outl-row[data-row="object"] .name', { hasText: `Ines ${tag}` }).first().click({ button: 'right' })   // the row's name (its editor opens under it)
  await page.locator('.ctx-menu button.item', { hasText: 'Make a free copy' }).click()
  await expect.poll(async () => (await doc()).objects.filter((o) => o.kind === 'mannequin').length, { timeout: 10_000 }).toBe(2)
  const free = (await doc()).objects.find((o) => o.kind === 'mannequin' && !o.profile_id)!
  expect(free.body?.height_m).toBe(1.58)
  expect(free.name).toBe(`Ines ${tag} (free)`)
  // CW5: Line-up ▶ in World's Sheet — the class's characters side by side before 0.5 m marks, the one open first; Send to a stage ▸ copies them
  await openBuild(page, 'character', ines.id)
  await page.locator('[data-testid="world-build"] button', { hasText: /^Line-up/ }).click()
  const chip = page.locator('[data-testid="bench-chip"]')
  await expect(chip).toContainText('Line-up ·')
  await expect(page.locator('.w-mode button.active')).toHaveText('Clay')                                    // inside World
  const lineup = (await api<{ items: StageLite[] }>('GET', '/stages?purpose=lineup')).items[0]
  expect(lineup.objects[0].preset ?? lineup.objects[0].kind).toBe('lineup')
  expect(lineup.objects[1].profile_id).toBe(ines.id)                                                       // the one open first
  await page.screenshot({ path: 'node_modules/.e2e/cw5-lineup.png' })
  await chip.locator('button', { hasText: 'Send to a stage' }).click()
  await page.locator('.ctx-menu button.item', { hasText: 'Send to a new stage…' }).click()
  const dialog = page.locator('.modal.ask')
  await dialog.locator('input').fill(`From the line-up ${tag}`)
  await dialog.locator('button.primary').click()
  await expect(chip).toHaveCount(0)                                                                  // the new stage is a stage, not the line-up
  await expect.poll(async () => (await api<{ items: StageLite[] }>('GET', '/stages')).items.find((s) => s.name === `From the line-up ${tag}`)?.objects.map((o) => o.profile_id) ?? [], { timeout: 10_000 }).toContain(ines.id)
})

test('a body on the Cast sheet (CA0, 01 §9): height, build and an attachment saved with the sheet; a stage figure bound to the character takes the body when the stage opens (World’s Sheet, B2a)', async ({ page }) => {
  const name = `Grak ${Date.now().toString(36)}`
  const src = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0]
  const hero = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [src.id] })).ids[0]
  type Body = { height_m: number; build: string; attachments: { kind: string }[] }
  type ProfileLite = { id: string; versions: { id: string; body: Body | null }[] }
  const p = await api<ProfileLite>('POST', '/story/profiles', { name, cls: 'character', hero_asset_id: hero, appearance: `${name}, a hulking ogre` })
  expect(p.versions[0].body).toBeNull()
  await openBuild(page, 'character', p.id)
  await page.locator('.cast-body button', { hasText: 'body' }).click()
  await page.locator('.cast-body input[aria-label="height in metres"]').fill('2.4')
  await page.locator('.cast-body .segmented button', { hasText: 'heavy' }).click()
  await page.locator('.cast-body button', { hasText: 'attachment' }).click()
  await page.locator('.cast-body select[aria-label="attachment 1"]').selectOption('horns')
  await expect(page.locator('svg.body-silhouette')).toHaveAttribute('aria-label', 'silhouette, 2.40 m')
  await expect.poll(async () => { const b = (await api<ProfileLite>('GET', `/story/profiles/${p.id}`)).versions[0].body; return b ? `${b.height_m}|${b.build}|${b.attachments.map((a) => a.kind).join()}` : null }).toBe('2.4|heavy|horns')
  // a shot's stage with a figure bound to the character, no body yet: opening it in Shots › Clay gives the figure the sheet's body
  const shot = await api<{ shot_id: string }>('POST', '/story/flow/shots', { title: `Cave ${name}`, scene: 'new' })
  const sid = (await api<{ versions: { stage_id: string }[] }>('GET', `/story/shots/${shot.shot_id}`)).versions[0].stage_id
  const st = await api<{ id: string; objects: unknown[] } & Record<string, unknown>>('GET', `/stages/${sid}`)
  const fig = { id: 'obj_grak', kind: 'mannequin', name: 'Grak', preset: 'adult', profile_id: p.id, version: null, body: null }
  await api('PUT', `/stages/${st.id}`, { ...st, objects: [...st.objects, fig] })
  await openShell(page, `shots/${shot.shot_id}/clay`)
  const grak = async () => (await api<{ objects: { id: string; body: Body | null }[] }>('GET', `/stages/${st.id}`)).objects.find((o) => o.id === 'obj_grak')
  await expect.poll(async () => (await grak())?.body?.height_m ?? null, { timeout: 15_000 }).toBe(2.4)
  await page.locator('#anim-sec-scene').scrollIntoViewIfNeeded()
  await page.locator('.outl-row[data-row="object"]').filter({ has: page.locator('.name', { hasText: /^Grak$/ }) }).click()
  await expect(page.locator('.outl-row[data-row="object"].active .row-editor')).toContainText('from Cast — 2.40 m · heavy · horns')   // D119 (SC1): the figure's editor under its row
  await page.evaluate(async (id) => { await (window as unknown as { __loom2Stage: { open: (id: string) => Promise<void> } }).__loom2Stage.open(id) }, st.id)   // reopened: the body stays
  await page.waitForTimeout(500)
  await page.screenshot({ path: 'node_modules/.e2e/ca0-body-stage.png' })                  // a look for the journal: the ogre beside nothing, 2.4 m
})

test('an animation reference picked by hand (CA0 → D161): Make reference candidates ▶ queues two and fills no slot; the author picks the front and the back from the candidates, a slot\'s ✕ clears it (the picture stays a candidate), Discard trashes one (World\'s Build)', async ({ page }) => {
  test.setTimeout(90_000)
  const name = `Ines ${Date.now().toString(36)}`
  const src = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0]
  const hero = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [src.id] })).ids[0]
  type ProfileLite = { id: string; versions: { id: string; anim_ref_asset_id: string | null; anim_ref_back_asset_id: string | null }[] }
  const p = await api<ProfileLite>('POST', '/story/profiles', { name, cls: 'character', hero_asset_id: hero, appearance: `${name}, a dancer in a red dress` })
  await openBuild(page, 'character', p.id)
  await expect(page.locator('.anim-ref-slot[data-side="front"]')).toContainText('none yet')
  await page.locator('.anim-ref button', { hasText: /^Make reference candidates/ }).click()
  const cands = page.locator('[data-testid="anim-ref-candidates"] .anim-ref-cand')
  await expect(cands).toHaveCount(2, { timeout: 60_000 })                                                  // both land as candidates
  const ver = async () => (await api<ProfileLite>('GET', `/story/profiles/${p.id}`)).versions[0]
  expect((await ver()).anim_ref_asset_id).toBeNull()                                                       // nothing is picked for the author
  await expect(page.locator('.anim-ref-slot[data-side="front"]')).toContainText('none yet')
  const [a, b] = [(await cands.nth(0).getAttribute('data-id'))!, (await cands.nth(1).getAttribute('data-id'))!]
  await cands.nth(0).locator('button', { hasText: 'Front' }).click()
  await expect.poll(async () => (await ver()).anim_ref_asset_id).toBe(a)
  await expect(page.locator('.anim-ref-slot[data-side="front"] img')).toHaveAttribute('src', new RegExp(a))
  await expect(cands).toHaveCount(1)                                                                       // a picked one leaves the strip
  await page.locator(`[data-testid="anim-ref-candidates"] .anim-ref-cand[data-id="${b}"]`).click({ button: 'right' })
  await page.locator('.ctx-menu button.item', { hasText: /^Use as the A-pose back/ }).click()
  await expect.poll(async () => (await ver()).anim_ref_back_asset_id).toBe(b)
  await expect(page.locator('.anim-ref-slot[data-side="back"] img')).toHaveAttribute('src', new RegExp(b))
  // ✕ on the back slot clears it: the picture is a candidate again
  await page.locator('.anim-ref-slot[data-side="back"] .slot-clear button').click()
  await expect.poll(async () => (await ver()).anim_ref_back_asset_id).toBeNull()
  await expect(page.locator(`[data-testid="anim-ref-candidates"] .anim-ref-cand[data-id="${b}"]`)).toBeVisible()
  // Discard: the candidate goes to the Trash
  await page.locator(`[data-testid="anim-ref-candidates"] .anim-ref-cand[data-id="${b}"] button[aria-label="Discard"]`).click()
  await expect(page.locator(`[data-testid="anim-ref-candidates"] .anim-ref-cand[data-id="${b}"]`)).toHaveCount(0)
  await expect.poll(async () => (await api<{ trashed_at: string | null }>('GET', `/assets/${b}`)).trashed_at).toBeTruthy()
})

test('the body fitted to the animation reference (CA1b, D104): Fit the body measures the reference and the proportions follow, the height stays (World’s Sheet, B2a)', async ({ page }) => {
  test.setTimeout(90_000)
  const name = `Ines ${Date.now().toString(36)}`
  const src = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0]
  const ref = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [src.id] })).ids[0]
  type ProfileLite = { id: string; versions: { id: string; body_fit_from: string | null; body_points: { pose: number[][] } | null; anim_ref_note: string | null
    body: { height_m: number; neck: number; shoulders: number; hips: number; elbow: number; figure: string; hand_rest: { preset: string } } | null }[] }
  const p = await api<ProfileLite>('POST', '/story/profiles', { name, cls: 'character', appearance: `${name}, a mechanic` })
  await api('PUT', `/story/profiles/${p.id}/versions/v1/anim-ref`, { side: 'front', asset_id: ref })           // the author's pick (D161: an untouched body is fitted at once)
  await openBuild(page, 'character', p.id)
  await expect.poll(async () => (await api<ProfileLite>('GET', `/story/profiles/${p.id}`)).versions[0].body_fit_from, { timeout: 60_000 }).toBe(ref)
  type JobLite = { status: string; origin: { surface: string; ref: string } | null }
  const fits = async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.filter((j) => j.origin?.surface === 'body_fit' && j.origin.ref === p.id)
  await page.locator('.cast-body button', { hasText: /^Fit the body to the animation reference/ }).click()   // and by hand, again
  await expect.poll(async () => (await fits()).map((j) => j.status).join(','), { timeout: 60_000 }).toBe('done,done')
  const body = (await api<ProfileLite>('GET', `/story/profiles/${p.id}`)).versions[0].body!
  expect(body.height_m).toBe(1.75)                                                                    // the author's: unchanged
  expect(body.neck).toBeGreaterThan(1.3)                                                              // the fake reference's long neck (0.16 of the height; ×1 an adult's, S3)
  expect(body.elbow).toBeCloseTo(0.5, 2)                                                              // CS1 (S6): the fake's elbows halfway
  const v = (await api<ProfileLite>('GET', `/story/profiles/${p.id}`)).versions[0]
  expect(v.body_points?.pose.length).toBe(18); expect(v.anim_ref_note).toBeNull()                     // CS1: the points kept; the fake stands in the A-pose (S8)
  await expect(page.locator('.cast-body')).toContainText('Proportions fitted to the animation reference')
  await expect(page.locator('.cast-body')).toContainText(`×${body.neck.toFixed(2)}`)                     // the neck slider shows the fitted factor
  // CS1 (U18, S2): the character's figure and its hands at rest are on the sheet
  await expect(page.locator('.cast-body [aria-label="figure"] button[aria-pressed="true"]')).toHaveText('♀')
  await page.locator('.cast-body select[aria-label="hands at rest"]').selectOption('fist')
  await expect.poll(async () => (await api<ProfileLite>('GET', `/story/profiles/${p.id}`)).versions[0].body?.hand_rest.preset, { timeout: 10_000 }).toBe('fist')
})

test('the skeleton bench (proto01_UIcast CS2): Skeleton… opens the reference with SDPose\'s points and the figure\'s, a hip dragged and Fit again refits the body, a part locked stays, the guide follows a motion (World’s Sheet, B2a)', async ({ page }) => {
  test.setTimeout(120_000)
  const name = `Bea ${Date.now().toString(36)}`
  const src = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0]
  const ref = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [src.id] })).ids[0]
  type Body = { torso: number; legs: number; neck: number; locks: string[] }
  type ProfileLite = { id: string; versions: { id: string; body_fit_from: string | null; body: Body | null; body_points: { pose: number[][]; sdpose?: { pose: number[][] } } | null }[] }
  const p = await api<ProfileLite>('POST', '/story/profiles', { name, cls: 'character', appearance: `${name}, a baker` })
  await api('PUT', `/story/profiles/${p.id}/versions/v1/anim-ref`, { side: 'front', asset_id: ref })
  await openBuild(page, 'character', p.id)
  await page.locator('.cast-body button', { hasText: /^Fit the body to the animation reference/ }).click()
  const prof = async () => (await api<ProfileLite>('GET', `/story/profiles/${p.id}`)).versions[0]
  await expect.poll(async () => (await prof()).body_points?.pose.length ?? 0, { timeout: 60_000 }).toBe(18)
  const fitted = (await prof()).body!, read = (await prof()).body_points!.pose[8][1]
  await page.locator('.cast-body button', { hasText: /^Skeleton…/ }).click()
  const bench = page.locator('.skel-bench')
  await expect(bench.locator('.skel-ref circle.white')).toHaveCount(18 + 42, { timeout: 15_000 })   // the body's 18 and both hands' 21 (the fake has no feet)
  await expect(bench.locator('.skel-ref circle.blue')).toHaveCount(18)
  await expect(page.locator('.skel-parts h4')).toContainText(`${name}'s skeleton`)
  await expect(page.locator('.skel-parts .skel-row[data-row="neck"] .mono')).toContainText('cm')
  // a hip dragged down (SDPose put it high), then Fit again: a longer torso, shorter legs
  for (const k of [8, 11]) {                                                                          // by the white ring's edge (the figure's blue dot sits in its middle)
    const box = (await bench.locator(`.skel-ref circle.white[data-k="${k}"]`).first().boundingBox())!
    await page.mouse.move(box.x + box.width * 0.15, box.y + box.height / 2); await page.mouse.down()
    await page.mouse.move(box.x + box.width * 0.15, box.y + box.height / 2 + 25, { steps: 5 }); await page.mouse.up()
  }
  await expect(bench.locator('.skel-foot')).toContainText('2 points moved')
  await bench.locator('.skel-foot button', { hasText: /^Fit again/ }).click()
  await expect.poll(async () => (await prof()).body!.torso, { timeout: 10_000 }).toBeGreaterThan(fitted.torso)
  expect((await prof()).body!.legs).toBeLessThan(fitted.legs)
  expect((await prof()).body_points!.pose[8][1]).toBeGreaterThan(read + 5)                           // the author's point kept…
  expect((await prof()).body_points!.sdpose!.pose[8][1]).toBeCloseTo(read, 1)                         // …and SDPose's own read beside it
  // a part locked keeps its value through Fit again; the others refit around it (the factors only fix proportions)
  const movedTorso = (await prof()).body!.torso
  await page.locator('.skel-parts .skel-row[data-row="neck"] button.lock').click()
  await expect.poll(async () => (await prof()).body!.locks, { timeout: 10_000 }).toContain('neck')
  const neck = (await prof()).body!.neck
  await bench.locator('.skel-foot button', { hasText: /^Back to SDPose/ }).click()
  await bench.locator('.skel-foot button', { hasText: /^Fit again/ }).click()
  await expect.poll(async () => (await prof()).body!.torso, { timeout: 10_000 }).toBeLessThan(movedTorso - 0.1)   // SDPose's hips again: the torso back down
  expect((await prof()).body!.neck).toBe(neck)
  // the shell (D136 U6): Pixal3D on the reference in the background under full; greyed under open (DINOv3)
  if (env().variant === 'open') await expect(bench.locator('.skel-foot button', { hasText: /^Make the shell/ })).toBeDisabled()   // greyed: no model in this build
  else {
    await bench.locator('.skel-foot button', { hasText: /^Make the shell/ }).click()
    await expect.poll(async () => ((await prof()) as unknown as { shell_asset_id: string | null }).shell_asset_id, { timeout: 30_000 }).toBeTruthy()
    await expect(bench.locator('.skel-foot')).toContainText('shell')
    await expect(bench.locator('.skel-pane.ref .tools button', { hasText: 'shell' })).toBeEnabled()          // D140: the shell over the picture
  }
  // the guide follows a motion; the bench closes back to the sheet
  await bench.locator('.skel-motions button', { hasText: 'walk' }).click()
  await expect(bench.locator('.skel-guide img.pose')).toHaveCount(1, { timeout: 20_000 })
  await page.screenshot({ path: 'node_modules/.e2e/cs2-bench.png' })
  await bench.locator('.skel-strip button', { hasText: /^Back to the sheet/ }).click()
  await expect(page.locator('[data-testid="world-build"]')).toBeVisible()
  await expect(page.locator('[data-testid="world-bin"]')).toBeVisible()                                       // the bin back in the centre
})

test("the skeleton changed (proto01_UIcast CS3, D136 U19): a final's character layer stamps its body per frame; Cast's skeleton changing under it shows on the layer, nothing done by itself — Re-render draws the guide again and performs it; Apply from the playhead keys the skeleton (the frames before it held) and performs again (Shots, B2a)", async ({ page }) => {
  test.setTimeout(150_000)
  const stageName = `Skeleton ${Date.now().toString(36)}`
  await clayShot(page, stageName)
  const dialog = page.locator('.modal.ask')
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  type Prof = { id: string; name: string; revision: number; versions: { id: string; body: Record<string, unknown> | null }[] }
  const who = await api<Prof>('POST', '/story/profiles', { name: `Skel ${Date.now().toString(36)}`, cls: 'character', hero_asset_id: img, appearance: 'a courier' })
  const setNeck = async (neck: number) => {
    const p = await api<Prof>('GET', `/story/profiles/${who.id}`)
    await api('PATCH', `/story/profiles/${who.id}`, { revision: p.revision, versions: [{ id: 'v1', body: { ...(p.versions[0].body ?? { height_m: 1.7 }), neck } }] })
  }
  await setNeck(1.0)                                                                                        // the body first: a touched body is not fitted to the pick (D161)
  await api('PUT', `/story/profiles/${who.id}/versions/v1/anim-ref`, { side: 'front', asset_id: img })
  await libAdd(page, 'sets', 'room')
  await libAdd(page, 'figures', 'Adult')
  await page.locator(`.w-panel [aria-label="the figure's character"] button[aria-label="${who.name}"]`).click()
  await page.evaluate(() => (window as unknown as { __loom2Stage: { setRange: (a: number, b: number) => void } }).__loom2Stage.setRange(0, 12))   // 9 frames at F16: one batch
  await perfCardOf(page, 'Final shot')
  await page.locator('.final-section button', { hasText: /^Make the final shot/ }).click()
  await dialog.locator('button.primary').click()
  await expect(page.locator('.final-section .final-row')).toBeVisible({ timeout: 60_000 })
  type Lay = { id: string; kind: string; object_id: string | null; status: string; frames_done: number; body: Record<string, unknown> | null; body_hashes: string[]; batches: { job_id: string }[]; job_ids: string[]; guide_asset_id: string | null }
  const stage = (await api<{ items: { id: string; name: string }[] }>('GET', '/stages')).items.find((x) => x.name === stageName)!
  const fin = (await api<{ items: { id: string; layers: Lay[] }[] }>('GET', `/finals?stage_id=${stage.id}`)).items[0]
  const figOf = async () => (await api<{ layers: Lay[] }>('GET', `/finals/${fin.id}`)).layers.find((l) => l.kind === 'figure')!
  const first = await figOf()
  expect(first.body?.neck).toBe(1.0); expect(first.body_hashes).toHaveLength(9); expect(new Set(first.body_hashes).size).toBe(1)
  const row = page.locator('.final-section li[data-kind="figure"]')
  await expect(row.locator('.skeleton-changed')).toHaveCount(0)
  await row.locator('button', { hasText: 'Perform' }).click()
  await expect.poll(async () => { const p = await figOf(); return `${p.status} ${p.frames_done}` }, { timeout: 60_000 }).toBe('done 9')
  // Cast's skeleton changes under the drawn layer: the layer says so, nothing runs by itself
  const performed = await figOf()
  await setNeck(1.4)
  await expect(row.locator('.skeleton-changed')).toBeVisible({ timeout: 15_000 })
  expect((await figOf()).job_ids).toEqual(performed.job_ids)                                                 // nothing queued by itself
  await page.screenshot({ path: 'node_modules/.e2e/cs3-skeleton-changed.png' })
  // Re-render with the new skeleton: the guide drawn again (the server encodes it again) and the whole layer performed again
  const guide1 = (await figOf()).guide_asset_id
  await expect(row.locator('.status')).toHaveText(/done · 9 frames/, { timeout: 15_000 })                   // the panel has caught up with the run
  await row.locator('.skeleton-changed').click()
  await page.locator('.ctx-menu button.item', { hasText: /^Re-render with the new skeleton/ }).click()
  await expect.poll(async () => (await figOf()).body?.neck, { timeout: 30_000 }).toBe(1.4)
  await expect.poll(async () => { const p = await figOf(); return `${p.status} ${p.frames_done} ${p.batches[0].job_id !== performed.batches[0].job_id}` }, { timeout: 60_000 }).toBe('done 9 true')
  const rerendered = await figOf()
  expect(rerendered.guide_asset_id).not.toBe(guide1)
  await expect(row.locator('.skeleton-changed')).toHaveCount(0)
  // changed again, applied from the playhead: the frames before it keep the skeleton they were drawn with (keys), Cast's from it
  await setNeck(0.8)
  await expect(row.locator('.skeleton-changed')).toBeVisible({ timeout: 15_000 })
  await page.evaluate(() => (window as unknown as { __loom2Stage: { setFrame: (f: number) => void } }).__loom2Stage.setFrame(6))
  await expect(row.locator('.status')).toHaveText(/done · 9 frames/, { timeout: 15_000 })
  await row.locator('.skeleton-changed').click()
  await page.locator('.ctx-menu button.item', { hasText: /^Apply from the playhead \(frame 6\)/ }).click()
  await expect(dialog).toContainText(/keep the skeleton they were drawn with/)
  await dialog.locator('button.primary').click()
  await expect.poll(async () => { const p = await figOf(); return `${p.status} ${p.frames_done} ${p.batches[0].job_id !== rerendered.batches[0].job_id}` }, { timeout: 60_000 }).toBe('done 9 true')
  const after = await figOf()
  expect(after.body_hashes.slice(0, 4)).toEqual(Array(4).fill(after.body_hashes[0])); expect(after.body_hashes[4]).not.toBe(after.body_hashes[0])   // F16: frame 6 is the 5th
  type Doc = { objects: { id: string; kind: string }[]; keyframes: { skeleton?: Record<string, { frame: number; body: { neck?: number } | null }[]> } }
  const doc = await api<Doc>('GET', `/stages/${stage.id}`)
  const fid = doc.objects.find((o) => o.kind === 'mannequin')!.id
  expect(doc.keyframes.skeleton?.[fid]?.map((k) => [k.frame, k.body?.neck ?? null])).toEqual([[0, 1.4], [6, null]])
  await expect(row.locator('.skeleton-changed')).toHaveCount(0)
  await toLevel(page, 'clay')
  await expect(page.locator('.stage-tl .tl-row', { hasText: /skeleton/ })).toBeVisible()                   // the keys on the figure's skeleton row (Clay's timeline)
  await page.screenshot({ path: 'node_modules/.e2e/cs3-skeleton-keys.png' })
})

test('a test animation in Cast (CA0, 01 step 2): Test it draws a turn on the spot from the body here, the pose-driven model performs it with the reference, the clip lands beside the reference (World’s Sheet, B2a)', async ({ page }) => {
  test.setTimeout(120_000)
  const name = `Bram ${Date.now().toString(36)}`
  const src = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0]
  const ref = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [src.id] })).ids[0]
  type ProfileLite = { id: string; revision: number; versions: { id: string; anim_test_clip_id: string | null }[] }
  const p = await api<ProfileLite>('POST', '/story/profiles', { name, cls: 'character', appearance: `${name}, an old captain` })
  await api('PATCH', `/story/profiles/${p.id}`, { revision: p.revision, versions: [{ id: 'v1', body: { height_m: 1.9, build: 'broad', head: 1, torso: 1, shoulders: 1, arms: 1, legs: 1, attachments: [] } }] })
  await api('PUT', `/story/profiles/${p.id}/versions/v1/anim-ref`, { side: 'front', asset_id: ref })
  await openBuild(page, 'character', p.id)
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

test('the motion library (CA1, 01 step 5; U5b G8): the starter folder\'s clips listed in the Motion section, one previewed and applied to a figure at the playhead as a clip block with its root motion — no keys baked, the range as it was (Shots, B2a)', async ({ page }) => {
  await clayShot(page, 'Motion test')
  await libAdd(page, 'figures', 'Adult')                       // a figure, selected
  await section(page, 'motion')
  const lib = page.locator('.motion-lib')
  await lib.locator('.motion-file-head', { hasText: 'test_rig' }).click()                       // the e2e tree's starter folder holds the test rig
  await expect(lib.locator('.motion-clip')).toHaveCount(2)
  await lib.locator('.motion-clip', { hasText: 'Walk_RM' }).click()
  await expect(lib.locator('.motion-clip', { hasText: 'Walk_RM' })).toContainText('moves')
  await expect(lib.locator('.motion-preview')).toContainText('25 frames at 24 fps · unreal · 0.96 m')
  await lib.locator('label', { hasText: /^ ?foot lock/ }).locator('input').uncheck()               // the test rig's hips glide without stepping: the root motion as made
  type Doc = { id: string; name: string; range: { end: number }; objects: { id: string; transform: { pos: number[] } }[]; keyframes: { objects: Record<string, unknown[]> }
    tracks: Record<string, { source: { kind: string; clip: string }; start: number; length: number; foot_lock: boolean }[]> }
  const doc = async () => (await api<{ items: Doc[] }>('GET', '/stages')).items.find((s) => s.name === 'Motion test')!
  const range = (await doc()).range.end
  await lib.locator('button', { hasText: /^Apply to Figure 1 at the playhead/ }).click()
  await expect.poll(async () => Object.values((await doc()).tracks ?? {})[0]?.length ?? 0, { timeout: 15_000 }).toBe(1)
  const d = await doc()
  const b = Object.values(d.tracks)[0][0]
  expect([b.source.kind, b.source.clip, b.start, b.length, b.foot_lock]).toEqual(['library', 'Walk_RM', 0, 25, false])
  expect(Object.keys(d.keyframes.objects ?? {})).toHaveLength(0)                                // a block, not baked keys
  expect(d.range.end).toBe(range)                                                               // F37: the range never moves by itself
  type Fig = { transform: { pos: number[] }; pose: { joints: Record<string, number[]> } }
  const at = (f: number) => page.evaluate((fr) => (window as unknown as { __loom2Stage: { sampleAt: (f: number) => Promise<{ objects: Fig[] }> } }).__loom2Stage.sampleAt(fr), f)
  const [p0, p24] = [(await at(0)).objects[0], (await at(24)).objects[0]]
  expect(p24.transform.pos[2] - p0.transform.pos[2]).toBeCloseTo(0.958, 2)                      // 1 m of the rig's hips, scaled by the hip heights
  expect(Object.keys(p24.pose.joints)).toHaveLength(12)
  await expect(page.locator('.tl-bar.block', { hasText: 'Walk_RM' })).toBeVisible()                // the block on the figure's track
  await page.screenshot({ path: 'node_modules/.e2e/ca1-motion-library.png' })
})

test('the Detailed level (CA1, 01 §9a; U18 every figure): a figure switched to ♂ follows its joints with the starter set\'s mannequin, a fist is keyed as its own bones, and the passes still render (Shots, B2a)', async ({ page }) => {
  await clayShot(page, 'Detail test')
  await libAdd(page, 'figures', 'Adult')
  type Doc = { name: string; objects: { detail: string | null; pose: { extra: Record<string, number[]> } | null }[] }
  const doc = async () => (await api<{ items: Doc[] }>('GET', '/stages')).items.find((s) => s.name === 'Detail test')!
  await expect.poll(async () => (await doc())?.objects[0]?.detail ?? null, { timeout: 10_000 }).toBe('female')   // U18 (proto01_UIcast): a new figure is the Detailed ♀
  await section(page, 'motion')
  await expect(page.locator('.detail-level .segmented button')).toHaveText(['♀', '♂'])                            // no Simple level any more
  await page.locator('.detail-level .segmented button', { hasText: '♂' }).click()
  await expect.poll(async () => (await doc())?.objects[0]?.detail ?? null, { timeout: 10_000 }).toBe('male')
  // the mannequin loads from the starter folder (the e2e tree's test rig carries a skinned mesh); then the fist is the finger bones' turns
  await expect.poll(async () => {
    await page.locator('.detail-level .kv', { hasText: 'right hand' }).locator('button', { hasText: /^fist$/ }).click()
    return Object.keys((await doc())?.objects[0]?.pose?.extra ?? {}).sort().join(',')
  }, { timeout: 15_000 }).toBe('index_01_r,index_02_r,index_03_r,pinky_01_r')
  // the passes render with the mannequin in them (D121: the Clay level's foot)
  await toLevel(page, 'clay')
  await page.locator('.s-foot button.primary', { hasText: /^Render passes/ }).click()
  await expect(page.locator('.s-foot [data-passes-state]')).toContainText(/\d+ passes at \d+×\d+/, { timeout: 30_000 })   // rendered: 'Camera 1 · 5 passes at 1280×720 · current'
  await page.screenshot({ path: 'node_modules/.e2e/ca1-detailed.png' })
})

test('a floor path (CA1, 01 step 5): the Path tool adds the floor points clicked to the selected figure\'s path, and a clip applied along it walks it with the feet locked (Shots, B2a)', async ({ page }) => {
  await clayShot(page, 'Path test')
  await libAdd(page, 'figures', 'Adult')                       // a figure, selected
  await page.locator('button.cmd-btn[aria-label^="Path (click the floor"]').first().click()
  const canvas = page.locator('canvas.stage-canvas')
  const box = (await canvas.boundingBox())!
  for (const [fx, fy] of [[0.45, 0.8], [0.5, 0.7], [0.6, 0.65]]) await page.mouse.click(box.x + box.width * fx, box.y + box.height * fy)
  type Doc = { name: string; objects: { path: number[][] | null; transform: { pos: number[] } }[]; keyframes: { objects: Record<string, { frame: number; transform: { pos: number[]; rot: number[] } }[]> } }
  const doc = async () => (await api<{ items: Doc[] }>('GET', '/stages')).items.find((s) => s.name === 'Path test')
  await expect.poll(async () => (await doc())?.objects[0]?.path?.length ?? 0, { timeout: 10_000 }).toBe(3)
  await section(page, 'motion')
  const lib = page.locator('.motion-lib')
  await lib.locator('.motion-file-head', { hasText: 'test_rig' }).click()
  await lib.locator('.motion-clip', { hasText: 'Walk_RM' }).click()
  await expect(lib.locator('label', { hasText: /^ ?along Figure 1's path/ })).toBeVisible()
  await lib.locator('button', { hasText: /^Apply to Figure 1 at the playhead/ }).click()
  await expect.poll(async () => Object.values(((await doc()) as unknown as { tracks?: Record<string, unknown[]> })?.tracks ?? {})[0]?.length ?? 0, { timeout: 15_000 }).toBe(1)   // U5b: a clip block
  const d = (await doc())!
  const first = await page.evaluate(() => (window as unknown as { __loom2Stage: { sampleAt: (f: number) => Promise<{ objects: { transform: { pos: number[] } }[] }> } }).__loom2Stage.sampleAt(0))
  const p0 = d.objects[0].path![0]
  expect(Math.hypot(first.objects[0].transform.pos[0] - p0[0], first.objects[0].transform.pos[2] - p0[1])).toBeLessThan(0.05)   // it starts at the path's start
  await expect(page.locator('.toast')).toContainText(/along its path, feet locked/)
  // a pose preset on the keyed figure is a key at the playhead (before CA1 it changed only the unkeyed pose, which the keys hide)
  type Key = { frame: number; pose: { preset: string; joints: Record<string, number[]> } | null }
  await libAdd(page, 'poses', 'point')                                                       // the pose tiles sit behind the Motion section's + (D119 SC2)
  await expect.poll(async () => { const k = Object.values((await doc())?.keyframes.objects ?? {})[0] as unknown as Key[]; return k?.find((x) => x.frame === 0)?.pose?.preset ?? null }, { timeout: 10_000 }).toBe('point')
  const k0 = (Object.values((await doc())!.keyframes.objects)[0] as unknown as Key[]).find((x) => x.frame === 0)!
  expect(Object.keys(k0.pose!.joints)).toHaveLength(12)                                       // spelled out, so it blends with the clip's keys
})

test('a set from an image (D120, SC3): a Bin picture becomes a relief set on the stage with the picture camera active, its lens and budget in its row (Shots, B2a)', async ({ page }) => {
  const photo = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_asc&limit=1')).items[0].id   // the project's first photo
  await api('POST', '/assets/duplicate', { ids: [photo] })                                                                   // its copy the newest in Imports: no other scenario's picture is picked
  const made = await clayShot(page, 'Relief test')
  const dialog = page.locator('.modal.ask')
  await section(page, 'scene')
  const setJobsBefore = (await api<{ items: { kind: string }[] }>('GET', '/jobs')).items.filter((j) => j.kind === 'image_to_set').length
  await page.locator('.lib-row[data-group="sets"] button', { hasText: /^From an image/ }).click()                          // opens the Bin with the hint
  const bin = page.locator('.dock .bin')
  await expect(bin).toBeVisible()
  await drawerHome(page, 'world/sketches')
  await bin.locator('.bin-bar .segmented button', { hasText: 'pictures' }).click()
  const picking = bin.locator('.bin-bar .picking')
  await expect(picking).toContainText('picking for: Add to the stage (a set from this image)')                               // the pick started from the panel
  const tile = bin.locator('.bin-grid .w-tile').first()
  await expect(tile).toBeVisible()
  const corner = tile.locator('.b-corner[aria-label="Add to the stage (a set from this image)"]')
  await expect(corner).toBeVisible()
  await page.keyboard.press('Escape')                                                                                         // Escape ends the pick
  await expect(picking).toHaveCount(0)
  await expect(corner).toHaveCount(0)
  await page.locator('.lib-row[data-group="sets"] button', { hasText: /^From an image/ }).click()                          // again
  await expect(picking).toHaveCount(1)
  await tile.click({ button: 'right' })                                                                                       // a right-click ends it too — and still opens every verb
  await expect(page.locator('.ctx-menu button.item', { hasText: /a set from this image/ })).toBeVisible()
  await expect(picking).toHaveCount(0)
  await page.keyboard.press('Escape')
  await expect(page.locator('.ctx-menu')).toHaveCount(0)
  await page.locator('.lib-row[data-group="sets"] button', { hasText: /^From an image/ }).click()                          // a third time: the corner button
  await corner.click()
  const ask = page.locator('.modal.ask')                                                                                      // D123: the lens is asked first
  await expect(ask).toContainText("A set from this image — the picture's lens")
  await page.keyboard.press('Escape')                                                                                         // cancelled: nothing queued
  await expect(ask).toHaveCount(0)
  await page.waitForTimeout(300)
  expect((await api<{ items: { kind: string }[] }>('GET', '/jobs')).items.filter((j) => j.kind === 'image_to_set').length).toBe(setJobsBefore)
  await page.locator('.lib-row[data-group="sets"] button', { hasText: /^From an image/ }).click()
  await corner.click()
  await ask.locator('input').fill('5 mm wide')                                                                                // not a lens: said, and asked again
  await ask.locator('button.primary').click()
  await expect(ask).toContainText('"5 mm wide" is not a lens')                                                             // said in the question asked again
  await expect(ask.locator('input')).toHaveValue('5 mm wide')
  await ask.locator('input').fill('')                                                                                         // empty: MoGe reads it
  await ask.locator('button.primary', { hasText: 'Make the set' }).click()                                                    // the job through the fake engine
  await expect(bin.locator('.bin-bar .picking')).toHaveCount(0)                                                                // the pick ends with it
  const row = page.locator('.outl-row[data-row="object"]', { has: page.locator('.kind', { hasText: 'set' }) })
  await expect(row).toHaveCount(1, { timeout: 30_000 })                                                                      // the stage reloaded with it
  await expect(row.locator('.name')).toHaveText('Picture set')
  const cam = page.locator('.outl-row[data-row="camera"]', { has: page.locator('.name', { hasText: 'Picture camera' }) })
  await expect(cam).toHaveCount(1)
  await expect(cam).toHaveClass(/cam-active/)                                                                                 // the picture's camera is the active one
  await row.locator('.name').click()
  const editor = page.locator('.row-editor.stage-insp')
  await expect(editor).toContainText(/° wide · Picture camera/)                                                               // the default lens: the fake's relief has no UVs
  await expect(editor.locator('[data-budget]')).toHaveAttribute('data-budget', 'within')
  await expect(editor.locator('[data-level]')).toHaveText(/^as it came/)                                                     // SC3d: no floor to lay it level by
  await editor.locator('button', { hasText: /^Look through the picture/ }).click()
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  type Doc = { objects: { id: string; plate_asset_id?: string | null; kind: string; preset: string | null; locked: boolean; asset_id: string | null; plate_camera_id: string | null; lens_deg: number | null; floor_y: number | null }[]; cameras: { id: string; name: string; focal_mm: number; pos: number[] }[]; active_camera: string }
  const doc = (await api<{ items: (Doc & { name: string })[] }>('GET', '/stages')).items.find((s) => s.name === 'Relief test')!
  const set = doc.objects.find((o) => o.kind === 'set')!
  expect(set.preset).toBe('image'); expect(set.locked).toBe(true); expect(set.asset_id).toBeTruthy(); expect(set.lens_deg).toBe(60); expect(set.floor_y).toBe(-1)
  const pc = doc.cameras.find((c) => c.id === set.plate_camera_id)!
  expect(pc.name).toBe('Picture camera'); expect(pc.pos[1]).toBe(1); expect(doc.active_camera).toBe(pc.id)
  // SC3b: the relief catches the figures' shadows (a shadow-only copy over the picture) and the picture stands behind it, at its far depth
  type Layers = { surfaces: number; catchers: number; backdrop: { w: number; h: number; z: number } | null }
  const setId = set.id
  const layers = () => page.evaluate((id) => (window as unknown as { __loom2Stage: { imageSetLayers: (i: string) => Layers | null } }).__loom2Stage.imageSetLayers(id), setId)
  await expect.poll(async () => { const l = await layers(); return !!l?.backdrop && l.catchers === l.surfaces && l.surfaces > 0 }, { timeout: 15_000 }).toBe(true)
  const l0 = (await layers())!
  const plate = await api<{ w: number; h: number }>('GET', `/assets/${set.plate_asset_id}`)
  expect(l0.backdrop!.z).toBeLessThan(0); expect(Math.abs(l0.backdrop!.w / l0.backdrop!.h - plate.w / plate.h)).toBeLessThan(0.01)   // behind the picture camera, the picture's shape
  // the lens corrected and the set rebuilt in place: the same set, a new relief, the camera's focal following
  await row.locator('.name').click()                                                                                       // its row again (Look through selected the camera)
  const lensField = page.locator('.row-editor.stage-insp input[aria-label="the picture\'s lens"]')
  await expect(lensField).toHaveValue('60')
  const rebuild = page.locator('.row-editor.stage-insp button', { hasText: /^Rebuild with this lens/ })
  await expect(rebuild).toBeDisabled()                                                                                      // nothing to change yet
  await lensField.fill('75')
  await rebuild.click()
  const stageDoc = async () => (await api<{ items: (Doc & { name: string })[] }>('GET', '/stages')).items.find((s) => s.name === 'Relief test')!
  await expect.poll(async () => (await stageDoc()).objects.find((o) => o.id === setId)?.lens_deg, { timeout: 30_000 }).toBe(75)
  const doc2 = await stageDoc()
  const set2 = doc2.objects.find((o) => o.id === setId)!
  expect(doc2.objects.filter((o) => o.kind === 'set')).toHaveLength(1); expect(set2.asset_id).not.toBe(set.asset_id)
  expect(doc2.cameras.find((c) => c.id === set.plate_camera_id)!.focal_mm).toBeLessThan(pc.focal_mm)                    // a wider lens, a shorter focal
  await expect(page.locator('.outl-row[data-row="object"]', { has: page.locator('.kind', { hasText: 'set' }) })).toHaveCount(1)
  // SC3e: the final's plate is the picture — Stage renders it with the layers' passes (no Klein still, no job), its still the set's picture
  await page.evaluate(() => (window as unknown as { __loom2Stage: { setRange: (a: number, b: number) => void } }).__loom2Stage.setRange(0, 3))   // F16: 0, 1.5, 3
  const shotJobs = async () => (await api<{ items: { kind: string }[] }>('GET', '/jobs')).items.filter((j) => j.kind === 'stage_shot').length
  const shotsBefore = await shotJobs()
  await api('PUT', `/story/shots/${made.shot}/versions/v1/source`, { stage_id: made.stage, camera_id: set2.plate_camera_id })   // Shots makes a final through the shot's camera: the picture's
  await perfCardOf(page, 'Final shot')
  await page.locator('.final-section button', { hasText: /^Make the final shot/ }).click()
  await expect(dialog).toContainText(/the plate from the picture set's picture/)
  await dialog.locator('button.primary').click()
  type FinP = { id: string; frames: number; layers: { id: string; method: string; status: string; frames_done: number; still_asset_id: string | null }[] }
  const finOf = async () => (await api<{ items: FinP[] }>('GET', `/finals?stage_id=${doc2.id}`)).items[0]
  await expect.poll(async () => { const f = await finOf(); const p = f?.layers.find((x) => x.id === 'plate'); return p ? `${p.method} ${p.status} ${p.frames_done}/${f.frames}` : '' }, { timeout: 60_000 })
    .toBe('picture done 3/3')
  const fin = await finOf()
  expect(fin.layers.find((x) => x.id === 'plate')!.still_asset_id).toBe(set2.plate_asset_id)
  expect(await shotJobs()).toBe(shotsBefore)                                                                                // no Klein still was queued
  const means = await page.evaluate(async ([port, token, fid, pic]) => {                                                    // the frame is the set's picture, not the dark
    const mean = async (path: string) => {
      const bmp = await createImageBitmap(await (await fetch(`http://127.0.0.1:${port}${path}`, { headers: { 'X-Loom-Token': token } })).blob())
      const c = new OffscreenCanvas(64, 36); const g = c.getContext('2d')!; g.drawImage(bmp, 0, 0, 64, 36)
      const px = g.getImageData(8, 6, 48, 24).data                                                                            // the middle: the edges are the backdrop's margin
      const m = [0, 0, 0]
      for (let i = 0; i < px.length; i += 4) for (let k = 0; k < 3; k++) m[k] += px[i + k] / (px.length / 4)
      return m
    }
    return [await mean(`/finals/${fid}/layers/plate/frames/0`), await mean(`/assets/${pic}/file`)]
  }, [env().port, env().token, fin.id, set2.plate_asset_id] as const)
  expect(Math.max(...means[0].map((v, k) => Math.abs(v - means[1][k])))).toBeLessThan(24)
  await expect(page.locator('.final-section li[data-kind="plate"] .status')).toHaveText(/done · 3 frames/)
  await expect(page.locator('.final-section li[data-kind="plate"] img.still')).toBeVisible()
  await expect(page.locator('.s-foot button.primary')).not.toHaveText(/plate/)                                       // the next step is past the plate
})

test('the things of a picture set (D123, SC3c): picked on the picture, kept by name, renamed; Make cleans the plate, rebuilds the relief and models each thing (Shots, B2a)', async ({ page }) => {
  test.setTimeout(150_000)
  type JobL = { id: string; kind: string; status: string; recipe: { mode?: string; points?: { label: number }[] }; origin?: { surface?: string } | null; result: Record<string, unknown> | null }
  const jobs = async () => (await api<{ items: JobL[] }>('GET', '/jobs')).items
  const name = `Things ${Date.now().toString(36)}`
  const stg = await api<{ id: string }>('POST', '/stages', { name })
  const img = (await sketchPics(40))[0]
  const made = await api<{ job_id: string }>('POST', `/stages/${stg.id}/image-set`, { asset_id: img.id, lens_deg: 70 })
  await expect.poll(async () => (await jobs()).find((j) => j.id === made.job_id)?.status, { timeout: 30_000 }).toBe('done')
  type SetDoc = { objects: { id: string; kind: string; preset: string | null; plate_asset_id?: string | null; asset_id: string | null; things?: { id: string; name: string; mesh_asset_id: string | null }[] }[] }
  const theSet = async () => (await api<SetDoc>('GET', `/stages/${stg.id}`)).objects.find((o) => o.kind === 'set' && o.preset === 'image')!
  const before = await theSet()
  await clayOn(page, stg.id, name)
  await section(page, 'scene')
  const row = page.locator('.outl-row[data-row="object"]', { has: page.locator('.kind', { hasText: 'set' }) })
  const editor = page.locator('.row-editor.stage-insp')
  const openRow = async () => { if (!(await editor.locator('.set-things').isVisible())) await row.locator('.name').click(); await expect(editor.locator('.set-things')).toBeVisible() }
  await openRow()
  await expect(editor.locator('.set-things')).toContainText('none picked')
  await expect(editor.getByRole('button', { name: /^Make the things/ })).toBeDisabled()
  await editor.getByRole('button', { name: 'Things in the picture…' }).click()
  const sheet = page.locator('.modal.things-sheet')
  await expect(sheet).toBeVisible()
  const canvas = sheet.locator('.things-pic canvas')
  await expect.poll(async () => (await canvas.boundingBox())?.width ?? 0).toBeGreaterThan(100)
  const box = (await canvas.boundingBox())!
  const status = sheet.locator('.things-status')
  await expect(status).toHaveText('click a thing')
  await canvas.click({ position: { x: box.width * 0.5, y: box.height * 0.6 } })                       // SAM 3 finds the thing (the fake engine's mask)
  await expect(status).toHaveAttribute('data-state', 'found', { timeout: 30_000 })
  await canvas.click({ position: { x: box.width * 0.1, y: box.height * 0.1 }, button: 'right' })       // a right-click: not it — found again with both points
  await expect.poll(async () => (await jobs()).filter((j) => j.kind === 'segment' && j.origin?.surface === 'set_thing_find').map((j) => (j.recipe.points ?? []).map((p) => p.label).join(',')))
    .toContain('1,0')
  await expect(status).toHaveAttribute('data-state', 'found', { timeout: 30_000 })
  await sheet.locator('input[aria-label="the thing\'s name"]').fill('Crate')
  await sheet.getByRole('button', { name: 'Keep as a thing' }).click()
  await expect(sheet.locator('.things-kept')).toContainText('1 kept')
  await expect(sheet.locator('.things-kept')).toHaveAttribute('title', 'Crate')
  await expect(sheet.locator('.things-kept')).toHaveAttribute('data-shadows', /^(shown|none)$/)          // D124: read after the keep (the fake's flat picture: none)
  await expect(status).toHaveText('click a thing')                                                     // the points cleared for the next one
  await page.keyboard.press('Escape')
  await expect(sheet).toHaveCount(0)
  expect((await theSet()).things?.map((t) => t.name)).toEqual(['Crate'])
  await openRow()
  await expect(editor.locator('.thing-row')).toHaveCount(1)
  await editor.locator('.thing-row button[aria-label="Rename Crate"]').click()                           // renamed through the dialog
  const ask = page.locator('.modal.ask')
  await ask.locator('input').fill('Wooden crate')
  await ask.locator('button.primary').click()
  await expect.poll(async () => (await theSet()).things?.[0]?.name).toBe('Wooden crate')
  await openRow()
  const make = editor.getByRole('button', { name: /^Make the things/ })
  if (JSON.parse(process.env.LOOM2_E2E ?? '{}').variant === 'open') {                                  // D17 / D26: no Pixal3D — said on the button, nothing made
    await expect(make).toBeDisabled()
    await expect(make).toHaveAttribute('title', /Pixal3D/)
    return
  }
  await expect(make).toBeEnabled()
  await make.click()                                                                                   // the Fill, then the rebuild and the model it queues
  await expect.poll(async () => (await theSet()).plate_asset_id, { timeout: 60_000 }).not.toBe(before.plate_asset_id)   // rebuilt from the clean plate
  const after = await theSet()
  expect(after.asset_id).not.toBe(before.asset_id)
  const clean = await api<{ lineage_kind: string; parents: string[] }>('GET', `/assets/${after.plate_asset_id}`)
  expect(clean.lineage_kind).toBe('clean-plate'); expect(clean.parents).toEqual([img.id])
  await expect.poll(async () => (await jobs()).find((j) => j.kind === 'image_to_mesh' && j.origin?.surface === 'set_thing_model')?.status, { timeout: 60_000 }).toBe('done')
})

test('the one timeline and transport (D121 AW2): Clay keys the camera on its row, drags a key and the range on the ruler, removes a key; the transport keys move the playhead (Shots, B2a)', async ({ page }) => {
  await clayShot(page, 'Timeline test')
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await page.locator('.stage-empty button', { hasText: /Adult/ }).click()
  type Doc = { name: string; range: { start: number; end: number }; keyframes: { camera: Record<string, { frame: number }[]> } }
  const doc = async () => (await api<{ items: Doc[] }>('GET', '/stages')).items.find((s) => s.name === 'Timeline test')!
  const camFrames = async () => (Object.values((await doc()).keyframes?.camera ?? {})[0] ?? []).map((k) => k.frame)
  const tl = page.locator('.stage-timeline')
  const camRow = tl.locator('.tl-row[data-row^="cam:"]')
  await expect(camRow.locator(".tl-key")).toHaveCount(0)                                                    // nothing keyed: U5e — the camera's track is a row of its own, empty
  await tl.locator('button', { hasText: /^Key camera$/ }).click()
  await tl.locator('.frame-field').fill('8'); await tl.locator('.frame-field').dispatchEvent('change')
  await tl.locator('button', { hasText: /^Key camera$/ }).click()
  await expect(camRow.locator('.tl-key')).toHaveCount(2)
  await expect.poll(camFrames, { timeout: 10_000 }).toEqual([0, 8])
  // the span is [0, 132] for a 0–120 range: drag the key at 8 twelve frames right on its row
  const span = 132
  const track = (await camRow.locator('.tl-track').boundingBox())!
  const kb = (await camRow.locator('.tl-key').nth(1).boundingBox())!
  await page.mouse.move(kb.x + kb.width / 2, kb.y + kb.height / 2)
  await page.mouse.down()
  await page.mouse.move(kb.x + kb.width / 2 + (12 * track.width) / span, kb.y + kb.height / 2, { steps: 6 })
  await page.mouse.up()
  await expect.poll(camFrames, { timeout: 10_000 }).toEqual([0, 20])
  // the range's end dragged on the ruler to frame 60
  const ruler = (await tl.locator('.tl-ruler').boundingBox())!
  const out = (await tl.locator('.tl-handle.out').boundingBox())!
  await page.mouse.move(out.x + out.width / 2, out.y + out.height / 2)
  await page.mouse.down()
  await page.mouse.move(ruler.x + (60 * ruler.width) / span, out.y + out.height / 2, { steps: 6 })
  await page.mouse.up()
  await expect.poll(async () => (await doc()).range.end, { timeout: 10_000 }).toBe(60)
  // the drag's menu equivalent (D32): the key at 20 moved to the playhead by its right-click
  await tl.locator('.frame-field').fill('30'); await tl.locator('.frame-field').dispatchEvent('change')
  await camRow.locator('.tl-key').nth(1).click({ button: 'right' })
  await page.locator('.ctx-menu button.item', { hasText: 'Move this key to the playhead (frame 30)' }).click()
  await expect.poll(camFrames, { timeout: 10_000 }).toEqual([0, 30])
  // a key removed by its right-click
  await camRow.locator('.tl-key').nth(1).click({ button: 'right' })
  await page.locator('.ctx-menu button.item', { hasText: 'Remove this key' }).click()
  await expect.poll(camFrames, { timeout: 10_000 }).toEqual([0])
  // the one transport's keys at Clay: End → the range's end, Home → its start, → a frame on, Alt+← back to the key at 0
  await tl.locator('.counter').click()
  await page.keyboard.press('End')
  await expect(tl.locator('.frame-field')).toHaveValue('60')
  await page.keyboard.press('Home')
  await expect(tl.locator('.frame-field')).toHaveValue('0')
  await page.keyboard.press('ArrowRight'); await page.keyboard.press('ArrowRight')
  await expect(tl.locator('.frame-field')).toHaveValue('2')
  await page.keyboard.press('Alt+ArrowLeft')
  await expect(tl.locator('.frame-field')).toHaveValue('0')
  await page.screenshot({ path: 'node_modules/.e2e/d121-timeline-clay.png' })
  // D121 (AW4): the camera chrome — the PiP of the active camera in the free view (a click looks through), the pill's lens, the readout
  const pipFrame = page.locator('.stage-host .pip-frame')
  await expect(pipFrame).toBeVisible()
  await expect(pipFrame).toContainText('Camera 1 · 35 mm')
  const hook = () => page.evaluate(() => (window as unknown as { __loom2Stage: { pipRect: () => unknown } }).__loom2Stage.pipRect())
  expect(await hook()).not.toBeNull()
  // the PiP's cost on a busier stage (a room, three figures, a stand-in): the viewport's frame time without and with it (CPU and GPU, Edge's ANGLE)
  await libAdd(page, 'sets', 'room'); await libAdd(page, 'figures', 'Adult'); await libAdd(page, 'figures', 'Child'); await libAdd(page, 'standins', 'crate')
  await page.locator('#anim-sec-shot .col-sec-head').click()
  const ms = await page.evaluate(() => { const h = (window as unknown as { __loom2Stage: { frameTime: (n: number, on: boolean) => number } }).__loom2Stage; h.frameTime(10, true); return [h.frameTime(60, false), h.frameTime(60, true), h.frameTime(60, false), h.frameTime(60, true)] })
  console.log(`[aw4] viewport frame time (headless Edge, the median of five batches of 60, twice): ${ms[0].toFixed(3)} / ${ms[2].toFixed(3)} ms without the PiP, ${ms[1].toFixed(3)} / ${ms[3].toFixed(3)} ms with it`)
  expect(Math.min(ms[1], ms[3])).toBeLessThan(Math.max(ms[0], ms[2]) * 1.5 + 0.5)                       // a loose bound here; the 20 % bar is judged on the numbers
  await page.locator('.cam-pill button[aria-label="Cameras and lens"]').click()
  await page.locator('.ctx-menu button.item', { hasText: /^50 mm$/ }).click()
  await expect(page.locator('.stage-host .lens-readout')).toHaveText('50 mm')
  await expect(page.locator('.cam-pill .cam-pill-main')).toContainText('50 mm')
  await expect(pipFrame).toContainText('Camera 1 · 50 mm')
  await pipFrame.click()                                                                                    // looks through
  await expect(page.locator('.cam-pill .cam-pill-main')).toHaveClass(/active/)
  await expect(pipFrame).toHaveCount(0)                                                                     // no PiP while looking through
  await page.locator('.cam-pill .cam-pill-main').click()                                                    // back to the free view
  await expect(pipFrame).toBeVisible()
  await page.locator('.stage-strip button[aria-label^="Picture-in-picture"]').click()                      // the strip's toggle
  await expect(pipFrame).toHaveCount(0)
  expect(await hook()).toBeNull()
  await page.locator('.stage-strip button[aria-label^="Picture-in-picture"]').click()
  await expect(pipFrame).toBeVisible()
  await page.screenshot({ path: 'node_modules/.e2e/d121-camera-chrome.png' })
})

test('the Shots board (D125 SP3): the shots in the Flow\'s order with their steps; a cell runs its step for its shot — Frame opens Image on it, Stage links a camera without a second shot, Approved marks it final; the Flow cards show the steps (the Flow\'s List view, B2a)', async ({ page }) => {
  test.setTimeout(150_000)
  const tag = Date.now().toString(36)
  type NodeLite = { id: string; shot_id: string }
  const a = await api<NodeLite>('POST', '/story/flow/nodes', { type: 'shot', title: `Board A ${tag}`, text: 'a courier at a door' })
  const b = await api<NodeLite>('POST', '/story/flow/nodes', { type: 'dialogue', title: `Board B ${tag}` })
  await api('PATCH', `/story/flow/nodes/${b.id}`, { lines: [{ speaker: null, text: 'Hello.', audio_asset_id: null, audio_text: null }] })
  const g = (await api<{ graph: { revision: number; start: string | null; edges: { from: string; port: string; to: string }[] } }>('GET', '/story/flow')).graph
  const start = g.start ?? (await api<{ id: string }>('POST', '/story/flow/nodes', { type: 'start' })).id
  const g2 = (await api<{ graph: { revision: number; edges: { from: string; port: string; to: string }[] } }>('GET', '/story/flow')).graph
  await api('PUT', '/story/flow/graph', { revision: g2.revision, edges: [...g2.edges.filter((e) => e.from !== start), { from: start, port: 'out', to: a.id }, { from: a.id, port: 'out', to: b.id }] })
  const stage = await api<{ id: string; cameras: { id: string }[] }>('POST', '/stages', { name: `Board stage ${tag}` })
  await openShell(page, 'shots/flow')
  await page.locator('[data-testid="shots-flow-strip"] button', { hasText: 'List' }).click()          // D157 Q11: the board is the Flow's List view
  const board = page.locator('[data-testid="shots-board"]')
  const ids = async () => board.locator('tr.row').evaluateAll((rs) => rs.map((r) => r.getAttribute('data-id')))
  await expect.poll(async () => { const r = await ids(); return r.indexOf(a.shot_id) >= 0 && r.indexOf(a.shot_id) < r.indexOf(b.shot_id) }).toBe(true)   // the Flow's order
  const rowA = board.locator(`tr.row[data-id="${a.shot_id}"]`), rowB = board.locator(`tr.row[data-id="${b.shot_id}"]`)
  await expect(rowA.locator('button[data-step="frame"]')).toHaveClass(/owed/)
  await expect(rowB.locator('button[data-step="lines"]')).toHaveClass(/done/)
  await expect(rowB.locator('button[data-step="voice"]')).toHaveClass(/owed/)
  // Stage: Link a stage camera… — the shot's version takes the camera, no second shot
  const before = (await api<{ items: unknown[] }>('GET', '/story/shots')).items.length
  await rowB.locator('button[data-step="stage"]').click()
  const sheet = page.locator('.modal.link-stage')
  await expect(sheet).toBeVisible()
  await sheet.locator('select#link-stage').selectOption(stage.id)
  await sheet.locator('button.primary', { hasText: 'Link' }).click()
  type ShotLite = { versions: { stage_id: string | null; camera_id: string | null; state: string; clip_id: string | null }[] }
  await expect.poll(async () => (await api<ShotLite>('GET', `/story/shots/${b.shot_id}`)).versions[0].camera_id).toBe(stage.cameras[0].id)
  expect((await api<{ items: unknown[] }>('GET', '/story/shots')).items.length).toBe(before)
  await expect(rowB.locator('button[data-step="stage"]')).toHaveClass(/done/)
  // Approved: a clip on A (the fake engine), then the cell marks it final — at its draft size (D125 #6)
  const caps = await api<{ defaults: { i2v: string } }>('GET', '/capabilities')
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const job = (await api<{ jobs: { id: string }[] }>('POST', '/jobs', { recipe: { kind: 'i2v', model_id: caps.defaults.i2v, start_asset: img, width: 832, height: 480, frames: 9, fps: 16, prompt_text: 'board' }, stage: false, origin: { suite: 'story', surface: 'for_shot', payload: { shot_id: a.shot_id, version: 'v1' } } })).jobs[0]
  await expect.poll(async () => (await api<ShotLite>('GET', `/story/shots/${a.shot_id}`)).versions[0].clip_id, { timeout: 60_000 }).toBeTruthy()
  await expect(rowA.locator('button[data-step="clip"]')).toHaveClass(/done/, { timeout: 15_000 })
  expect(job.id).toBeTruthy()
  await rowA.locator('button[data-step="approved"]').click()
  await page.locator('.modal.ask button.primary').click()
  await expect.poll(async () => (await api<ShotLite>('GET', `/story/shots/${a.shot_id}`)).versions[0].state).toBe('final')
  await expect(rowA.locator('button[data-step="approved"]')).toHaveClass(/done/)
  // the Flow: the node cards show the steps
  await page.locator('[data-testid="shots-flow-strip"] button', { hasText: 'Canvas' }).click()
  await expect(page.locator(`.flow-node[data-id="${a.id}"] .pill`, { hasText: 'approved' })).toHaveClass(/done/)
})

test('readiness in World (D125 SP5, B2a): the header says what the character owes; the Inspector lists the shots that use it and how, a click opens one in Shots; the voice item makes a voice that is the character\'s — a second one too', async ({ page }) => {
  test.setTimeout(90_000)
  const tag = Date.now().toString(36)
  type NodeLite = { id: string; shot_id: string }
  type StageLite = { id: string; cameras: { id: string }[]; objects: unknown[] }
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const name = `Ready ${tag}`
  const prof = await api<{ id: string }>('POST', '/story/profiles', { name, cls: 'character', hero_asset_id: img, appearance: 'a wiry courier in a grey coat' })
  const talk = await api<NodeLite>('POST', '/story/flow/nodes', { type: 'dialogue', title: `Talk ${tag}` })
  await api('PATCH', `/story/flow/nodes/${talk.id}`, { lines: [{ speaker: prof.id, text: 'Hello.', audio_asset_id: null, audio_text: null }] })
  const walk = await api<NodeLite>('POST', '/story/flow/nodes', { type: 'shot', title: `Walk ${tag}` })
  const st = await api<StageLite>('POST', '/stages', { name: `Ready stage ${tag}` })
  await api('PUT', `/stages/${st.id}`, { ...st, objects: [{ id: `obj_${tag}`, kind: 'mannequin', preset: 'adult', name, profile_id: prof.id }] })
  await api('PUT', `/story/shots/${walk.shot_id}/versions/v1/source`, { stage_id: st.id, camera_id: st.cameras[0].id })
  await openShell(page, `world/character/${prof.id}/v1`)
  const ready = page.locator('[data-testid="world-readiness"]')
  await expect(ready).toContainText('✓ hero')
  await expect(ready.locator('.w-ready-item.owed', { hasText: 'A-pose front' })).toBeVisible()
  await expect(ready.locator('.w-ready-item', { hasText: 'voice' })).not.toContainText('✓')                     // optional: not made yet
  const uses = page.locator('[data-testid="world-uses"]')
  await expect(uses).toContainText(`Walk ${tag}`)
  await expect(uses.locator('li', { hasText: `Walk ${tag}` })).toContainText('on its stage')
  await expect(uses.locator('li', { hasText: `Talk ${tag}` })).toContainText('speaks')
  // the voice: the form in the Inspector; the voice made there is the character's, and so is a second one (S5: no second select)
  const voices = page.locator('[data-testid="world-inspector"] .voices')
  const form = voices.locator('[aria-label="new voice"]')
  const make = async (vname: string) => {
    await page.locator('[data-testid="world-inspector"] button[title^="New voice"]').click()
    await form.locator('input[aria-label="voice name"]').fill(vname)
    await form.locator('select[aria-label="kokoro voice"]').selectOption('am_adam')
    await form.locator('button[aria-label="create voice"]').click()
    await expect(form).toHaveCount(0)
    await expect(voices.locator('select[aria-label="profile voice"] option:checked')).toContainText(`${vname} · draft`)
  }
  await make(`First ${tag}`)
  await expect(ready.locator('.w-ready-item', { hasText: 'voice' })).toContainText('✓')
  await make(`Second ${tag}`)
  // a use opens its shot in Shots
  await uses.locator('button', { hasText: `Walk ${tag}` }).click()
  await expect(page.locator('[data-testid="shots-layer"]')).toBeVisible()
  await expect.poll(() => new URL(page.url()).hash, { timeout: 10_000 }).toContain(`#shots/${walk.shot_id}`)
})

test('the cut from the Flow (D125 SP6): Assemble from the Flow… asks at the Choice and lays the route\'s shots in order, stamped; a newer take marks a lane clip changed and its badge updates it; Assemble again takes the other route; Export for Resolve writes one folder (Episode, B2a)', async ({ page }) => {
  test.setTimeout(180_000)
  const tag = Date.now().toString(36)
  type NodeLite = { id: string; shot_id: string }
  type JobLite = { id: string; status: string; result: { clip_id?: string } }
  type ShotLite = { versions: { clip_id: string | null }[] }
  const a = await api<NodeLite>('POST', '/story/flow/nodes', { type: 'shot', title: `Gate ${tag}`, text: 'the gate opens' })
  const choice = await api<{ id: string }>('POST', '/story/flow/nodes', { type: 'choice', title: `Stay or go ${tag}` })
  await api('PATCH', `/story/flow/nodes/${choice.id}`, { options: [{ id: 'stay', label: 'Stay', require: null, set: [] }, { id: 'leave', label: 'Leave', require: null, set: [] }] })
  const b = await api<NodeLite>('POST', '/story/flow/nodes', { type: 'dialogue', title: `Talk ${tag}` })
  const c = await api<NodeLite>('POST', '/story/flow/nodes', { type: 'shot', title: `Road ${tag}`, text: 'she walks away' })
  const g = (await api<{ graph: { revision: number; start: string | null; edges: { from: string; port: string; to: string }[] } }>('GET', '/story/flow')).graph
  const start = g.start ?? (await api<{ id: string }>('POST', '/story/flow/nodes', { type: 'start' })).id
  const g2 = (await api<{ graph: { revision: number; edges: { from: string; port: string; to: string }[] } }>('GET', '/story/flow')).graph
  await api('PUT', '/story/flow/graph', { revision: g2.revision, start, edges: [...g2.edges.filter((e) => e.from !== start), { from: start, port: 'out', to: a.id }, { from: a.id, port: 'out', to: choice.id },
    { from: choice.id, port: 'opt:stay', to: b.id }, { from: choice.id, port: 'opt:leave', to: c.id }] })
  const caps = await api<{ defaults: { i2v: string } }>('GET', '/capabilities')
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const clipFor = async (sid: string, use = false) => {
    const job = (await api<{ jobs: { id: string }[] }>('POST', '/jobs', { recipe: { kind: 'i2v', model_id: caps.defaults.i2v, start_asset: img, width: 832, height: 480, frames: 9, fps: 16, prompt_text: sid }, stage: false,
      origin: { suite: 'story', surface: 'for_shot', payload: { shot_id: sid, version: 'v1', ...(use ? { use: true } : {}) } } })).jobs[0]
    await expect.poll(async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.id === job.id)?.status, { timeout: 60_000 }).toBe('done')
    return (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.id === job.id)!.result.clip_id!
  }
  const clipA = await clipFor(a.shot_id), clipB = await clipFor(b.shot_id), clipC = await clipFor(c.shot_id)
  for (const sid of [a.shot_id, b.shot_id, c.shot_id]) {                                                  // D157 (U7b): a cut takes finals — a one-pass shot's clip is its final
    const sh = await api<{ revision: number }>('GET', `/story/shots/${sid}`)
    await api('PATCH', `/story/shots/${sid}`, { revision: sh.revision, versions: [{ id: 'v1', method: 'start_still' }] })
  }
  await api('POST', `/story/shots/${a.shot_id}/versions/v1/finalize`)
  await openShell(page, 'episode')
  // Assemble from the Flow… (the foot): the sheet asks at the Choice; Stay → the gate, then the talk
  await page.locator('[data-testid="episode-layer"] .s-foot button.primary', { hasText: /^Assemble from the Flow/ }).click()
  const sheet = page.locator('.modal.assemble')
  await expect(sheet).toBeVisible()
  await sheet.locator(`select#pick-${choice.id}`).selectOption('stay')
  await expect(sheet.locator('[data-testid="assemble-what"]')).toHaveText(/^2 shots/)
  await expect(sheet.locator('input#assemble-name')).toHaveValue(/ · Stay$/)
  const name = `Cut ${tag} · Stay`
  await sheet.locator('input#assemble-name').fill(name)
  await sheet.locator('button.primary', { hasText: /^Assemble$/ }).click()
  await expect(page.locator('.seq-row.active')).toContainText(name)
  await expect(page.locator('.cut-clip.k-take')).toHaveCount(2)
  type TL = { id: string; name: string; route: Record<string, string> | null; clips: { clip_id: string; shot_id: string | null; shot_version: string | null; node_id: string | null }[] }
  const cut = async () => (await api<{ items: TL[] }>('GET', '/timelines')).items.find((t) => t.name === name)!
  await expect.poll(async () => (await cut())?.clips.length, { timeout: 10_000 }).toBe(2)
  expect((await cut()).clips.map((x) => [x.clip_id, x.shot_id, x.node_id])).toEqual([[clipA, a.shot_id, a.id], [clipB, b.shot_id, b.id]])
  expect((await cut()).route).toEqual({ [choice.id]: 'stay' })
  // a newer take of the talk (used as its clip) marks its lane clip changed; the badge updates it
  const clipB2 = await clipFor(b.shot_id, true)
  await expect.poll(async () => (await api<ShotLite>('GET', `/story/shots/${b.shot_id}`)).versions[0].clip_id).toBe(clipB2)
  const badge = page.locator('.cut-clip .seq-changed')
  await expect(badge).toHaveCount(1, { timeout: 15_000 })
  await expect(page.locator('.seq-insp .seq-check li.warn', { hasText: 'newer approved take' })).toHaveCount(1)
  await badge.click()
  await expect(badge).toHaveCount(0)
  await expect.poll(async () => (await cut()).clips[1].clip_id, { timeout: 10_000 }).toBe(clipB2)
  // Assemble again… (the Inspector) with Leave: the gate, then the road
  await page.locator('.seq-insp button[title^="Assemble again"]').click()
  await expect(sheet.locator('input#assemble-name')).toHaveCount(0)
  await sheet.locator(`select#pick-${choice.id}`).selectOption('leave')
  await sheet.locator('button.primary', { hasText: /^Assemble again$/ }).click()
  await expect.poll(async () => (await cut()).clips.map((x) => x.clip_id), { timeout: 10_000 }).toEqual([clipA, clipC])
  expect((await cut()).route).toEqual({ [choice.id]: 'leave' })
  // Export for Resolve ▶: the road is not final — the checklist asks once; one folder named after the cut
  await page.locator('[data-testid="episode-layer"] .s-foot button.primary', { hasText: /^Export for Resolve/ }).click()
  const dialog = page.locator('.modal.ask')
  await expect(dialog).toContainText(/1 of 2 clips listed/)
  await dialog.locator('button.primary').click()
  await expect(page.locator('.seq-insp .hint', { hasText: 'last:' })).toContainText(`timelines/${(await cut()).id}/cut-`)
  const out = await api<{ path: string; text: string }>('POST', `/timelines/${(await cut()).id}/export`, { format: 'resolve' })
  expect(out.text.split('\n').map((f) => f.split('.').pop()).sort()).toEqual(['edl', 'fcpxml', 'srt', 'txt'])
})

test('the recipe graph in Animate (RC1b): Graph shows the For chip\'s shot as its parts — the character bound on the stage, the camera, the figure\'s motion, the clip, the take — and a node opens where it is made (the motion: Clay › Motion on the figure) (Shots, B2a)', async ({ page }) => {
  test.setTimeout(120_000)
  const tag = Date.now().toString(36)
  type NodeLite = { id: string; shot_id: string }
  type StageLite = { id: string; cameras: { id: string }[] }
  type JobLite = { id: string; status: string }
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const mara = await api<{ id: string }>('POST', '/story/profiles', { name: `Gm ${tag}`, cls: 'character', hero_asset_id: img, appearance: 'a courier' })
  const st = await api<StageLite>('POST', '/stages', { name: `Graph ${tag}` })
  const fig = `fig_${tag}`
  await api('PUT', `/stages/${st.id}`, { ...st, objects: [{ id: fig, kind: 'mannequin', preset: 'adult', name: 'Walker', profile_id: mara.id }],
    keyframes: { camera: {}, objects: { [fig]: [{ frame: 0, transform: { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] } }, { frame: 24, transform: { pos: [1, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] } }] } } })
  const n = await api<NodeLite>('POST', '/story/flow/nodes', { type: 'shot', title: `Graph ${tag}` })
  await api('PUT', `/story/shots/${n.shot_id}/versions/v1/source`, { stage_id: st.id, camera_id: st.cameras[0].id })
  const caps = await api<{ defaults: { i2v: string } }>('GET', '/capabilities')
  const job = (await api<{ jobs: { id: string }[] }>('POST', '/jobs', { recipe: { kind: 'i2v', model_id: caps.defaults.i2v, start_asset: img, width: 832, height: 480, frames: 9, fps: 16, prompt_text: 'graph' },
    stage: false, origin: { suite: 'story', surface: 'for_shot', payload: { shot_id: n.shot_id, version: 'v1' } } })).jobs[0]
  await expect.poll(async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.id === job.id)?.status, { timeout: 60_000 }).toBe('done')
  // the graph record
  type G = { route: string; nodes: { id: string; state: string }[]; edges: { from: string; to: string }[] }
  const g = await api<G>('GET', `/story/shots/${n.shot_id}/graph`)
  const state = Object.fromEntries(g.nodes.map((x) => [x.id, x.state]))
  expect(state[`character:${mara.id}`]).toBe('done')
  expect(state[`motion:${fig}`]).toBe('done')
  expect([state['step:clip'], state.take, state.camera]).toEqual(['done', 'done', 'done'])
  expect(g.edges).toContainEqual({ from: 'step:clip', to: 'take' })
  // the shot open at Performance in Shots → the rail's Graph
  await openShell(page, `shots/${n.shot_id}/performance`)
  await expect(page.locator('[data-testid="shots-layer"]')).toHaveAttribute('data-level', 'performance')
  await page.locator('.w-rail-btn[data-level="graph"]').click()
  const graph = page.locator('[data-testid="animate-graph"]')
  await expect(graph).toBeVisible()
  await expect(graph.locator('.recipe-strip')).toContainText(`Graph ${tag}`)
  for (const id of [`character:${mara.id}`, 'camera', `motion:${fig}`, 'step:clip', 'take']) await expect(graph.locator(`.recipe-node[data-id="${id}"]`)).toBeVisible()
  await expect(graph.locator(`.recipe-node[data-id="motion:${fig}"] .badge`)).toHaveText('done')
  // the motion opens Clay's Motion on its figure; the graph stays over the viewer until its pill turns it off
  await graph.locator(`.recipe-node[data-id="motion:${fig}"]`).click()
  await expect(page.locator('[data-testid="shots-layer"]')).toHaveAttribute('data-level', 'clay')
  await expect.poll(() => page.evaluate(() => (window as unknown as { __loom2Stage: { state: () => { selected: string | null } } }).__loom2Stage.state().selected)).toBe(fig)
  await expect(graph).toBeVisible()
  await page.locator('.w-rail-btn[data-level="graph"]').click()
  await expect(graph).toHaveCount(0)
})

test('the recipe graph in Story and the Catalogue (RC1c): Open its recipe shows the node\'s shot in place of the Flow\'s canvas, the shot page has a Recipe section, a take\'s Show its recipe opens its shot, and Open the graph in Animate turns Animate\'s Graph on (Shots, B2a)', async ({ page }) => {
  test.setTimeout(120_000)
  const tag = Date.now().toString(36)
  type NodeLite = { id: string; shot_id: string }
  type JobLite = { id: string; status: string; result: { clip_id?: string } }
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const n = await api<NodeLite>('POST', '/story/flow/nodes', { type: 'shot', title: `Rec ${tag}`, x: 4000, y: 4000 })
  const caps = await api<{ defaults: { i2v: string } }>('GET', '/capabilities')
  const job = (await api<{ jobs: { id: string }[] }>('POST', '/jobs', { recipe: { kind: 'i2v', model_id: caps.defaults.i2v, start_asset: img, width: 832, height: 480, frames: 9, fps: 16, prompt_text: 'recipe' },
    stage: false, origin: { suite: 'story', surface: 'for_shot', payload: { shot_id: n.shot_id, version: 'v1' } } })).jobs[0]
  await expect.poll(async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.id === job.id)?.status, { timeout: 60_000 }).toBe('done')
  const clipId = (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.id === job.id)!.result.clip_id!
  const clipAsset = (await api<{ asset_id: string }>('GET', `/clips/${clipId}`)).asset_id
  // the Flow: the node's Open its recipe, in place of the canvas; The Flow brings the canvas back
  await openShell(page, `shots/${n.shot_id}/clay`)
  await page.locator('.w-rail-btn[data-level="flow"]').click()
  await page.waitForFunction(() => !!(window as unknown as { __loom2Story?: unknown }).__loom2Story)
  type Hook = { loadFlow: () => Promise<void>; selectNode: (id: string) => void }
  await page.evaluate(async (id) => { const h = (window as unknown as { __loom2Story: Hook }).__loom2Story; await h.loadFlow(); h.selectNode(id) }, n.id)   // the Flow loaded first
  await page.locator('.s-insp button[title^="Open its recipe"]').click()
  const pane = page.locator('[data-testid="flow-recipe"]')
  await expect(pane).toBeVisible()
  await expect(page.locator('[data-testid="flow-canvas"]')).toHaveCount(0)
  for (const id of ['step:frame', 'step:clip', 'take']) await expect(pane.locator(`.recipe-node[data-id="${id}"]`)).toBeVisible()
  await expect(pane.locator('.recipe-node[data-id="step:clip"] .badge')).toHaveText('done')
  await expect(pane.locator('.recipe-node[data-id="step:frame"] .badge')).toHaveText('owed')
  await pane.locator('.recipe-strip button[title^="The Flow"]').click()
  await expect(page.locator('[data-testid="flow-canvas"]')).toBeVisible()
  // the List view: the picked shot's Recipe under the board
  await page.locator('[data-testid="shots-flow-strip"] button', { hasText: 'List' }).click()
  await page.locator(`.shots-board tr.row[data-id="${n.shot_id}"] td.name`).click()
  await expect(page.locator('.shot-recipe .recipe-node[data-id="take"]')).toBeVisible()
  // the Bin: the clip is in its shot's home, and Open its shot ▸ opens it (U2e, U8)
  expect((await api<{ path: string }>('GET', `/bin/things/${clipAsset}`)).path).toBe(`shots/${n.shot_id}/v1`)
  // Open the graph in Animate: the For chip on the shot and the Graph on
  await page.locator(`.shots-board tr.row[data-id="${n.shot_id}"] td.name`).click({ button: 'right' })
  await page.locator('.ctx-menu button.item', { hasText: 'Open its graph' }).click()
  await expect(page.locator('[data-testid="animate-graph"]')).toBeVisible()
  await expect(page.locator('[data-testid="animate-graph"] .recipe-strip')).toContainText(`Rec ${tag}`)
  await page.locator('.w-rail-btn[data-level="graph"]').click()
})

test('a prop held in a hand (D129 · HP1): a prop goes into a figure\'s right hand from its right-click, follows the hand when the pose changes, and is taken out where it stands (Shots, B2a)', async ({ page }) => {
  test.setTimeout(90_000)
  const tag = Date.now().toString(36)
  type Obj = { id: string; name: string; parent: string | null; parent_joint: string | null; transform: { pos: number[] } }
  type StageLite = { id: string; revision: number; objects: Obj[] }
  const st0 = await api<StageLite>('POST', '/stages', { name: `Held ${tag}` })
  await api('PUT', `/stages/${st0.id}`, { ...st0, objects: [
    { id: 'fig_m', kind: 'mannequin', name: 'Mara', preset: 'adult', transform: { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] }, pose: { preset: 'stand', joints: {} }, colour_id: 1 },
    { id: 'prop_c', kind: 'prop', name: 'Cup', preset: 'block', transform: { pos: [1.5, 0, 0], rot: [0, 0, 0], scale: [0.1, 0.1, 0.1] }, colour_id: 2 }],
    cameras: [{ id: 'cam_1', name: 'Camera 1', pos: [0, 1.5, 5], target: [0, 1, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }], active_camera: 'cam_1' })
  await clayOn(page, st0.id, `Held ${tag}`)
  type StageHook = { open: (id: string) => Promise<void>; worldOf: (id: string) => { pos: number[] } | null }
  await expect.poll(async () => page.evaluate(() => !!(window as unknown as { __loom2Stage?: StageHook }).__loom2Stage), { timeout: 30_000 }).toBe(true)
  await page.evaluate(async (id) => { await (window as unknown as { __loom2Stage: StageHook }).__loom2Stage.open(id) }, st0.id)
  await expect(page.locator('canvas.stage-canvas')).toBeVisible()
  await section(page, 'scene')
  const cupRow = page.locator('.outl-row[data-row="object"]').filter({ has: page.locator('.name', { hasText: 'Cup' }) })
  await cupRow.click({ button: 'right' })
  await page.locator('.ctx-menu .item.sub', { hasText: 'Hold in a hand' }).hover()
  await page.locator('.ctx-menu button.item', { hasText: 'Mara · right hand' }).click()
  await expect.poll(async () => { const o = (await api<StageLite>('GET', `/stages/${st0.id}`)).objects.find((x) => x.id === 'prop_c')!; return `${o.parent} ${o.parent_joint}` }, { timeout: 10_000 }).toBe('fig_m r_hand')
  const world = () => page.evaluate(() => (window as unknown as { __loom2Stage: StageHook }).__loom2Stage.worldOf('prop_c'))
  await expect.poll(async () => (await world())!.pos[0], { timeout: 10_000 }).toBeLessThan(0)          // at Mara's right hand (her right is −x), no longer at 1.5
  const low = (await world())!.pos[1]
  await page.locator('.outl-row[data-row="object"]').filter({ has: page.locator('.name', { hasText: 'Mara' }) }).click()
  await page.locator('.row-editor select').filter({ has: page.locator('option[value="wave"]') }).first().selectOption('wave')
  await expect.poll(async () => (await world())!.pos[1] - low, { timeout: 10_000 }).toBeGreaterThan(0.5)   // up with the waving hand
  await cupRow.click()
  await expect(page.locator('.row-editor [data-held]')).toContainText("Mara's right hand")
  const at = (await world())!.pos
  await page.locator('.row-editor [data-held] button', { hasText: 'Take it out of the hand' }).click()            // the Inspector's (also under Hold in a hand ▸)
  await expect.poll(async () => (await api<StageLite>('GET', `/stages/${st0.id}`)).objects.find((x) => x.id === 'prop_c')!.parent_joint, { timeout: 10_000 }).toBeNull()
  const out = (await api<StageLite>('GET', `/stages/${st0.id}`)).objects.find((x) => x.id === 'prop_c')!.transform.pos
  out.forEach((v, i) => expect(Math.abs(v - at[i])).toBeLessThan(0.01))                                 // where it was in the hand
  // proto01_UIcast CB4: any object as a parent — the Cup picks Mara and stays where it stands, then moves with her
  await page.locator('.row-editor select').filter({ has: page.locator('option[value="fig_m"]') }).first().selectOption('fig_m')
  await expect.poll(async () => (await api<StageLite>('GET', `/stages/${st0.id}`)).objects.find((x) => x.id === 'prop_c')!.parent, { timeout: 10_000 }).toBe('fig_m')
  const kept = (await world())!.pos
  kept.forEach((v, i) => expect(Math.abs(v - out[i])).toBeLessThan(0.01))                                // no jump
  const doc = await api<StageLite & Record<string, unknown>>('GET', `/stages/${st0.id}`)
  await api('PUT', `/stages/${st0.id}`, { ...doc, objects: doc.objects.map((o) => (o.id === 'fig_m' ? { ...o, transform: { ...o.transform, pos: [2, 0, 0] } } : o)) })
  await page.evaluate(async (id) => { await (window as unknown as { __loom2Stage: StageHook }).__loom2Stage.open(id) }, st0.id)
  await expect.poll(async () => (await world())!.pos[0] - kept[0], { timeout: 10_000 }).toBeGreaterThan(1.9)   // two metres with Mara
})

test('World in the new shell (U3a, D157 · proto01_UI2 03): a character\'s header, readiness and one bin with its roles; a reference made the hero from the Inspector', async ({ page }) => {
  const tag = Date.now().toString(36)
  const imgs = (await sketchPics(2))
  const name = `Wren ${tag}`
  type ProfileLite = { id: string; versions: { id: string; hero_asset_id: string | null }[] }
  const prof = await api<ProfileLite>('POST', '/story/profiles', { name, cls: 'character', hero_asset_id: imgs[0].id })
  await api('POST', `/story/profiles/${prof.id}/versions/v1/add`, { asset_ids: [imgs[1].id], role: 'reference' })
  await page.goto(`${appUrl()}#world/character/${prof.id}/v1`)
  const head = page.locator('[data-testid="world-header"]')
  await expect(head).toContainText(name)
  await expect(page.locator('[data-testid="world-readiness"]')).toContainText('✓ hero')
  await expect(page.locator('[data-testid="world-readiness"]')).toContainText('references 2')
  await expect(page.locator('[data-testid="world-readiness"]')).toContainText('to go')                      // no A-pose, no body yet
  const tile = (id: string) => page.locator(`.w-tile[data-id="${id}"]`)
  await expect(tile(imgs[0].id).locator('.w-badge')).toHaveText('★')
  await expect(tile(imgs[1].id).locator('.w-badge')).toHaveText('ref')
  await tile(imgs[1].id).click()
  await page.locator('[data-testid="world-inspector"] button', { hasText: 'Make it the hero' }).click()
  await expect.poll(async () => (await api<ProfileLite>('GET', `/story/profiles/${prof.id}`)).versions[0].hero_asset_id).toBe(imgs[1].id)
  await expect(tile(imgs[1].id).locator('.w-badge')).toHaveText('★')
  await page.locator('.w-chips button', { hasText: 'references' }).click()
  await expect(page.locator('.w-tile')).toHaveCount(2)                                                  // the hero is a reference too
  expect(new URL(page.url()).hash).toBe(`#world/character/${prof.id}/v1`)
})

test('World\'s Make (U3b, D157 · proto01_UI2 03 §3): the panel is the entity\'s own — seeded with it, a framing, words for this picture; Give a look lands the pictures as its candidates in its bin', async ({ page }) => {
  test.setTimeout(120_000)
  const tag = Date.now().toString(36)
  const name = `Odile ${tag}`
  type ProfileLite = { id: string; versions: { id: string; candidates_group_id: string | null }[] }
  const prof = await api<ProfileLite>('POST', '/story/profiles', { name, cls: 'character', appearance: 'a tall woman in her sixties, silver hair in a bun' })
  await page.goto(`${appUrl()}#world/character/${prof.id}/v1`)
  const make = page.locator('[data-testid="world-make"]')
  await expect(make).toBeVisible()
  const caps = await api<{ models: Record<string, { label: string; recipes?: { t2i?: unknown } }> }>('GET', '/capabilities')
  const present = (await api<{ items: { id: string; health: string }[] }>('GET', '/models')).items.find((m) => m.health !== 'missing' && caps.models[m.id]?.recipes?.t2i)!
  const label = caps.models[present.id].label
  await make.locator('#gen-sec-model .model-card').filter({ has: page.locator('span', { hasText: new RegExp(`^${label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`) }) }).click()   // a model the fixture has weights for (the column's Model section, 2026-10-29)
  await expect(make.locator('#gen-sec-model summary', { hasText: 'Sampling' })).toBeVisible()             // its sampling, LoRAs and advanced settings
  // the Prompt's JSON (FLUX.2's JSON prompt): the entity's sheet written in; back in Tree the entity is the subject again
  await make.locator('#gen-sec-prompt .segmented button', { hasText: 'JSON' }).click()
  await expect(make.locator('textarea[aria-label="prompt JSON"]')).toHaveValue(/silver hair in a bun/)
  await make.locator('#gen-sec-prompt .segmented button', { hasText: 'Tree' }).click()
  // D162: the framing row — a chip fills the framing words and queues nothing; the A-pose makes the run an A-pose; words of the author's own
  const framing = make.locator('textarea[aria-label="framing words"]')
  const jobsNow = (await api<{ items: unknown[] }>('GET', '/jobs')).items.length
  await make.locator('.w-framing button', { hasText: 'A-pose front' }).click()
  await expect(framing).toHaveValue(/neutral A-pose/)
  await expect(make.locator('.w-framing button', { hasText: 'A-pose front' })).toHaveAttribute('aria-pressed', 'true')
  await expect(make.locator('.w-foot button.primary')).toContainText(`Make ${name}'s A-pose front ▶`)
  expect((await api<{ items: unknown[] }>('GET', '/jobs')).items.length).toBe(jobsNow)                     // nothing queued by the chip
  await framing.fill('three-quarter view from below')                                                     // D169: its words edited, the A-pose stays on
  await expect(make.locator('.w-framing button', { hasText: 'A-pose front' })).toHaveAttribute('aria-pressed', 'true')
  await expect(make.locator('.w-foot button.primary')).toContainText(`Make ${name}'s A-pose front ▶`)
  await make.locator('.w-framing button', { hasText: 'A-pose front' }).click()                            // a second click turns it off
  await expect(make.locator('.w-framing button[aria-pressed="true"]')).toHaveCount(0)                      // the author's own framing
  await expect(framing).toHaveValue('three-quarter view from below')
  await expect(make.locator('.w-foot button.primary')).toContainText(`Give ${name} a look`)
  await make.locator('button', { hasText: 'full body' }).click()
  await expect(framing).toHaveValue('full body, head to feet in frame')
  await make.locator('textarea[aria-label="this picture only"]').fill('a grey wool coat, wind in her hair')
  while ((await make.locator('#gen-sec-size b[aria-label="count"]').innerText()) !== '1') await make.locator('#gen-sec-size button[aria-label="fewer"]').click()
  const before = (await api<{ items: unknown[] }>('GET', '/jobs')).items.length
  await make.locator('.w-foot button.primary', { hasText: `Give ${name} a look` }).click()
  await expect.poll(async () => (await api<{ items: { status: string; origin: { surface: string; ref: string } | null }[] }>('GET', '/jobs')).items.filter((j) => j.origin?.surface === 'cast' && j.origin.ref === prof.id && j.status === 'done').length, { timeout: 60_000 }).toBe(1)
  expect((await api<{ items: unknown[] }>('GET', '/jobs')).items.length).toBe(before + 1)
  await expect(page.locator('.w-tile')).toHaveCount(1)                                                    // in its bin, as a candidate
  await page.locator('.w-chips button', { hasText: 'candidates' }).click()
  await expect(page.locator('.w-tile')).toHaveCount(1)
  const job = (await api<{ items: { origin: { surface: string; ref: string } | null; recipe: { prompt_json?: unknown; prompt_text?: string } }[] }>('GET', '/jobs')).items.find((j) => j.origin?.surface === 'cast' && j.origin.ref === prof.id)!
  expect(JSON.stringify(job.recipe)).toContain('a grey wool coat, wind in her hair')                     // this picture's words went in
  // D162: with A-pose front on, the run is the A-pose's make: its picture lands in Build's candidates, nothing picked
  await page.locator('.w-chips button', { hasText: 'all' }).click()
  await make.locator('.w-framing button', { hasText: 'A-pose front' }).click()
  await make.locator('.w-foot button.primary', { hasText: `Make ${name}'s A-pose front` }).click()
  await expect.poll(async () => (await api<{ items: { status: string; origin: { surface: string; ref: string } | null }[] }>('GET', '/jobs')).items.filter((j) => j.origin?.surface === 'anim_ref' && j.origin.ref === prof.id && j.status === 'done').length, { timeout: 60_000 }).toBe(1)
  await page.locator('.w-mode button', { hasText: 'Build' }).click()
  await expect(page.locator('[data-testid="anim-ref-candidates"] .anim-ref-cand')).toHaveCount(1)
  expect((await api<{ versions: { anim_ref_asset_id: string | null }[] }>('GET', `/story/profiles/${prof.id}`)).versions[0].anim_ref_asset_id).toBeNull()
})

test('World\'s Edit (U3c, D157 · proto01_UI2 03 §4): the selected creation opens in the editor inside World; Save as a reference puts the edited picture into the bin', async ({ page }) => {
  test.setTimeout(120_000)
  const tag = Date.now().toString(36)
  const img = (await sketchPics(1))[0]
  type ProfileLite = { id: string }
  type BinLite = { items: { asset: { id: string }; roles: string[] }[] }
  const prof = await api<ProfileLite>('POST', '/story/profiles', { name: `Pell ${tag}`, cls: 'character', hero_asset_id: img.id })
  await page.goto(`${appUrl({ renderer: 'webgl' })}#world/character/${prof.id}/v1`)
  await page.locator(`.w-tile[data-id="${img.id}"]`).click()
  await page.locator('[data-testid="world-inspector"]').getByRole('button', { name: 'Edit', exact: true }).click()
  await expect(page.locator('[data-testid="world-edit"]')).toBeVisible()
  type Ed = { getState: () => { doc: { id: string } | null; addLayer: (k: string, extra?: Record<string, unknown>) => unknown } }
  await page.waitForFunction(() => !!(window as unknown as { __loom2Editor?: Ed }).__loom2Editor?.getState().doc, null, { timeout: 30_000 })
  await page.evaluate(() => (window as unknown as { __loom2Editor: Ed }).__loom2Editor.getState().addLayer('adjustment', { type: 'invert', params: {}, opacity: 0.4 }))   // an edit
  await page.locator('[data-testid="world-edit"] button', { hasText: 'Save as a reference' }).click()
  const bin = () => api<BinLite>('GET', `/story/profiles/${prof.id}/versions/v1/bin`)
  await expect.poll(async () => (await bin()).items.filter((x) => x.roles.includes('reference')).length, { timeout: 30_000 }).toBe(1)
  const made = (await bin()).items.find((x) => x.roles.includes('reference'))!.asset.id
  expect(made).not.toBe(img.id)
  await page.locator('.w-mode button', { hasText: 'Make' }).click()
  await expect(page.locator(`.w-tile[data-id="${made}"] .w-badge`)).toHaveText('ref')
  expect(new URL(page.url()).hash).toBe(`#world/character/${prof.id}/v1`)                             // World all along
})

test('World\'s Look and Sketches (U3d, D157 · proto01_UI2 03 §6–7): the Look keeps the project\'s sample scene; a sketch made with the whole column lands in Sketches and becomes a draft character\'s hero', async ({ page }) => {
  test.setTimeout(120_000)
  const tag = Date.now().toString(36)
  await page.goto(`${appUrl()}#world/look`)
  const look = page.locator('[data-testid="world-look"]')
  await expect(look).toBeVisible()
  await look.locator('textarea[aria-label="sample scene"]').fill(`a ferry at the pier ${tag}`)
  await expect.poll(async () => (await api<{ sample_scene: string }>('GET', '/story/world')).sample_scene, { timeout: 10_000 }).toBe(`a ferry at the pier ${tag}`)
  // Sketches: the whole column, a model the fixture has, one picture
  await page.locator('.w-rail-btn[aria-label="Sketches"]').click()
  await expect(page.locator('[data-testid="world-sketches"]')).toBeVisible()
  const caps = await api<{ models: Record<string, { recipes?: { t2i?: unknown } }> }>('GET', '/capabilities')
  const present = (await api<{ items: { id: string; health: string }[] }>('GET', '/models')).items.find((m) => m.health !== 'missing' && caps.models[m.id]?.recipes?.t2i)!
  type Gen = { getState: () => { set: (p: Record<string, unknown>) => void } }
  await page.evaluate(([m, t]) => (window as unknown as { __loom2Generate: Gen }).__loom2Generate.getState().set({ model_id: m, count: 1, prompt_mode: 'text', text: `an old lighthouse keeper ${t}` }), [present.id, tag])
  await page.locator('[data-testid="world-sketches"] button', { hasText: /^Make 1 sketch/ }).click()
  const tile = page.locator('.w-tile').first()
  await expect.poll(async () => (await api<{ items: { status: string; origin: { surface: string } | null }[] }>('GET', '/jobs')).items.filter((j) => j.origin?.surface === 'sketch' && j.status === 'done').length, { timeout: 60_000 }).toBeGreaterThan(0)
  await expect(tile).toBeVisible()
  const sketch = await tile.getAttribute('data-id')
  await tile.click()
  await page.locator('[data-testid="world-sketch-inspector"] button', { hasText: 'Prototype a character' }).click()
  await page.locator('.modal.ask input').fill(`Keeper ${tag}`)
  await page.locator('.modal.ask button.primary').click()
  await expect(page.locator('[data-testid="world-header"]')).toContainText(`Keeper ${tag}`)
  await expect(page.locator(`.w-tile[data-id="${sketch}"] .w-badge`)).toHaveText('★')                 // the sketch is its hero
})

test('World\'s Look words and the ideas brought in (U3e, D157 · G3, G4): a Library art style joins a style\'s words; an idea of the old board becomes a draft character with its pictures', async ({ page }) => {
  const tag = Date.now().toString(36)
  const imgs = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=2')).items
  type WorldLite = { revision: number; styles: { id: string; name: string; fragment: string }[] }
  const w0 = await api<WorldLite>('GET', '/story/world')
  const sid = `sty_${tag}`
  await api('PUT', '/story/world', { revision: w0.revision, styles: [...w0.styles, { id: sid, name: `Grey ${tag}`, fragment: 'soft grey light' }] })
  const idea = await api<{ id: string }>('POST', '/story/ideas', { cls: 'character', asset_id: imgs[0].id })
  await api('POST', `/story/ideas/${idea.id}/variants`, { asset_id: imgs[1].id })
  await page.goto(`${appUrl()}#world/look`)
  await page.locator(`.style-grid .style-tile[data-id="${sid}"]`).click()
  const words = page.locator('[data-testid="world-look-words"]')
  await expect(words).toBeVisible()
  const preset = words.locator('.w-chips button').first()
  const text = (await preset.getAttribute('title'))!
  await preset.click()
  await expect.poll(async () => (await api<WorldLite>('GET', '/story/world')).styles.find((s) => s.id === sid)?.fragment, { timeout: 10_000 }).toBe(`soft grey light, ${text}`)
  await page.locator('.w-rail-btn[aria-label="Sketches"]').click()
  await page.locator('.w-bin-head button', { hasText: 'Bring the ideas in' }).click()
  await page.locator('.modal.ask button.primary').click()
  await expect.poll(async () => (await api<{ kept: { profile_id: string }[] }>('GET', `/story/ideas/${idea.id}`)).kept.length, { timeout: 15_000 }).toBe(1)
  const pid = (await api<{ kept: { profile_id: string }[] }>('GET', `/story/ideas/${idea.id}`)).kept[0].profile_id
  const roles = async () => (await api<{ items: { roles: string[] }[] }>('GET', `/story/profiles/${pid}/versions/v1/bin`)).items.map((x) => x.roles[0]).sort()
  await expect.poll(roles, { timeout: 10_000 }).toEqual(['candidate', 'hero'])                          // the fold keeps the idea first, then adds its candidates
})

test('Shots in the new shell (U4a–d, D157 · proto01_UI2 04 §2–3, §6–7): the storyboard, the header, Clay on the shot\'s stage through its camera; the Flow\'s double-click, New shot in the same scene, the header\'s New scene, range and words', async ({ page }) => {
  test.setTimeout(90_000)
  const tag = Date.now().toString(36)
  type NodeLite = { id: string; shot_id: string | null }
  type ShotLite = { id: string; owner_node: string | null; versions: { stage_id: string | null; camera_id: string | null }[] }
  const a = await api<NodeLite>('POST', '/story/flow/shots', { title: `Quay ${tag}`, scene: 'new' })
  const b = await api<NodeLite>('POST', '/story/flow/shots', { title: `Pier ${tag}`, after: a.id, scene: 'same' })
  await page.goto(`${appUrl()}#shots/${a.shot_id}/clay`)
  const head = page.locator('[data-testid="shots-header"]')
  await expect(head).toContainText(`Quay ${tag}`)
  await expect(page.locator('[data-testid="shots-layer"]')).toHaveAttribute('data-level', 'clay')
  await expect(page.locator('[data-testid="shots-scene"] button').first()).toHaveText(new RegExp(`Quay ${tag}`))   // the scene's stage and the shot's camera, by name
  await expect(page.locator('[data-testid="shots-scene"] button').nth(1)).toHaveText(/Camera 1/)
  await expect(page.locator('.s-clay canvas').first()).toBeVisible()
  const card = (id: string) => page.locator(`.s-card[data-id="${id}"]`)
  await expect(card(a.shot_id!)).toHaveClass(/active/)
  await card(b.shot_id!).click()                                                                            // a card opens the shot at the level last used
  await expect(head).toContainText(`Pier ${tag}`)
  await expect.poll(() => new URL(page.url()).hash).toBe(`#shots/${b.shot_id}/clay`)
  await page.locator('.w-rail-btn[data-level="flow"]').click()
  await expect(page.locator('[data-testid="flow-canvas"]')).toBeVisible()
  await page.locator(`.react-flow__node[data-id="${a.id}"]`).dblclick()                                    // a Shot node's double-click opens it in Clay
  await expect(page.locator('[data-testid="shots-layer"]')).toHaveAttribute('data-level', 'clay')
  await expect(head).toContainText(`Quay ${tag}`)
  await page.locator('.s-new button').click()
  await page.locator('.ctx-menu button', { hasText: 'New shot in the same scene' }).click()
  const shots = async () => (await api<{ items: ShotLite[] }>('GET', '/story/shots')).items
  const stage = (await shots()).find((s) => s.id === a.shot_id)!.versions[0].stage_id
  await expect.poll(async () => (await shots()).filter((s) => s.versions[0].stage_id === stage).length, { timeout: 10_000 }).toBe(3)   // coverage: a third camera on the scene's stage
  const cams = (await shots()).filter((s) => s.versions[0].stage_id === stage).map((s) => s.versions[0].camera_id)
  expect(new Set(cams).size).toBe(3)                                                                        // each shot its own camera
  await expect(page.locator('.s-card.active')).not.toHaveAttribute('data-id', a.shot_id!)                  // the new shot is open
  // U4c (04 §2.1): the header's scene menu gives the open shot a scene of its own; its range on the scene's timeline
  const c = (await shots()).find((s) => s.versions[0].stage_id === stage && s.id !== a.shot_id && s.id !== b.shot_id)!
  await expect(page.locator('.s-card.active')).toHaveAttribute('data-id', c.id)
  await page.locator('[data-testid="shots-scene"] button').first().click()
  await page.locator('.ctx-menu button', { hasText: /^New scene/ }).click()
  await expect.poll(async () => (await shots()).find((s) => s.id === c.id)!.versions[0].stage_id, { timeout: 10_000 }).not.toBe(stage)
  const end = page.locator('[data-testid="shots-range"] input[aria-label="range end"]')
  await end.fill('48'); await end.press('Enter')
  await expect.poll(async () => (await api<{ items: (ShotLite & { versions: { range: unknown }[] })[] }>('GET', '/story/shots')).items.find((s) => s.id === c.id)!.versions[0].range, { timeout: 10_000 }).toEqual({ start: 0, end: 48 })
  await expect(page.locator('[data-testid="shots-range"]')).toContainText('2.0 s')
  // U4d (G13, 04 §6): this shot's own words, kept with its version, are a part of what its pictures are told — shown with their source
  await page.locator('[data-testid="shots-words"] button', { hasText: 'Show the words' }).click()
  const mine = page.locator(`textarea[aria-label="this shot's words"]`)
  await mine.fill('rain on the planks'); await mine.blur()
  await expect.poll(async () => (await api<{ items: (ShotLite & { versions: { words: string }[] })[] }>('GET', '/story/shots')).items.find((s) => s.id === c.id)!.versions[0].words, { timeout: 10_000 }).toBe('rain on the planks')
  await expect(page.locator('.s-parts li[data-part="shot"]')).toContainText('rain on the planks')
  await page.locator('[data-testid="shots-words"] .w-chips button', { hasText: 'the plate' }).click()
  await expect(page.locator('.s-parts li[data-part="shot"]')).toContainText('rain on the planks')            // the plate is told it too (no cast, no action)
  // U5d (F39, 04 §2.1 · §3.2): a line longer than the shot — the header says so and extends the range only when asked; the line on Clay's track
  const nodeId = (await shots()).find((s) => s.id === c.id)!.owner_node!
  const line = 'Do you know whose seal this is, and why it was pressed in green wax on a ferry ticket?'
  const nodeRev = (await api<{ nodes: { id: string; revision: number }[] }>('GET', '/story/flow')).nodes.find((n) => n.id === nodeId)!.revision
  await api('PATCH', `/story/flow/nodes/${nodeId}`, { revision: nodeRev, lines: [{ speaker: null, text: line, audio_asset_id: null, audio_text: null }] })
  await page.evaluate(() => (window as unknown as { __loom2Story: { loadFlow: () => Promise<void> } }).__loom2Story.loadFlow())
  const outlast = page.locator('[data-testid="shots-outlast"]')
  await expect(outlast).toContainText('the lines run')
  await expect(outlast).toContainText('the shot 2.0 s')
  await outlast.locator('button', { hasText: 'Extend to the lines' }).click()
  const words = line.split(/\s+/).length
  await expect.poll(async () => (await api<{ items: (ShotLite & { versions: { range: { start: number; end: number } | null }[] })[] }>('GET', '/story/shots')).items.find((s) => s.id === c.id)!.versions[0].range?.end ?? 0, { timeout: 10_000 })
    .toBe(Math.round((words / 2.6) * 24) - 1)                                                              // the unvoiced line timed by its words, from frame 0
  await expect(outlast).toHaveCount(0)
  await expect(page.locator('.tl-bar.line')).toContainText('narrator: Do you know whose seal')
})

test('the animation editor (U5c, D157 G8 G9 · proto01_UI2 04 §3.2): a clip block looped from its right-click and moved by a drag (the range as it was), saved as an animation under Mine and into the library, then baked to keys (Shots, B2a)', async ({ page }) => {
  test.setTimeout(90_000)
  await clayShot(page, 'Editor test')
  const dialog = page.locator('.modal.ask')
  await libAdd(page, 'figures', 'Adult')
  await section(page, 'motion')
  const lib = page.locator('.motion-lib')
  await lib.locator('.motion-file-head', { hasText: 'test_rig' }).click()
  await lib.locator('.motion-clip', { hasText: 'Walk_RM' }).click()
  await lib.locator('button', { hasText: /^Apply to Figure 1 at the playhead/ }).click()
  type Block = { id: string; start: number; loops: number; length: number }
  type Doc = { name: string; range: { start: number; end: number }; tracks: Record<string, Block[]>; keyframes: { objects: Record<string, unknown[]> } }
  const doc = async () => (await api<{ items: Doc[] }>('GET', '/stages')).items.find((s) => s.name === 'Editor test')!
  const block = async () => Object.values((await doc()).tracks ?? {})[0]?.[0] ?? null
  await expect.poll(async () => (await block())?.length ?? 0, { timeout: 15_000 }).toBe(25)
  const range = (await doc()).range
  const bar = page.locator('.tl-bar.block')
  await bar.click({ button: 'right' })
  await page.locator('.ctx-menu .item.sub', { hasText: 'Loops' }).hover()
  await page.locator('.ctx-menu button', { hasText: /^✓?2×$/ }).click()
  await expect.poll(async () => (await block())?.loops, { timeout: 15_000 }).toBe(2)
  expect((await block())!.length).toBeGreaterThan(25)                                            // re-flowed: two loops of the clip
  const box = (await bar.boundingBox())!
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2); await page.mouse.down()
  await page.mouse.move(box.x + box.width / 2 + 60, box.y + box.height / 2, { steps: 8 }); await page.mouse.up()
  await expect.poll(async () => (await block())?.start ?? 0, { timeout: 15_000 }).toBeGreaterThan(0)   // moved along the track
  expect((await doc()).range).toEqual(range)                                                     // F37: the range never moves by itself
  await bar.click({ button: 'right' })
  await page.locator('.ctx-menu button', { hasText: 'Save as animation…' }).click()
  await dialog.locator('input').fill('Walk twice')
  await dialog.locator('button.primary').click()
  type Anim = { id: string; name: string; frames: number }
  await expect.poll(async () => (await api<{ items: Anim[] }>('GET', '/stages/animations')).items.map((x) => x.name), { timeout: 10_000 }).toEqual(['Walk twice'])
  await lib.locator('.segmented button', { hasText: 'Mine' }).click()
  const mine = lib.locator('.motion-clip.mine', { hasText: 'Walk twice' })
  await expect(mine).toBeVisible()
  await mine.locator('button', { hasText: 'To my library' }).click()
  await expect.poll(async () => (await api<{ library: Anim[] }>('GET', '/stages/animations')).library.map((x) => x.name), { timeout: 10_000 }).toEqual(['Walk twice'])
  await bar.click({ button: 'right' })
  await page.locator('.ctx-menu button', { hasText: 'Bake to keys' }).click()
  await expect.poll(async () => Object.keys((await doc()).tracks ?? {}).length, { timeout: 15_000 }).toBe(0)
  expect(Object.values((await doc()).keyframes.objects)[0].length).toBeGreaterThan(1)          // its frames are the figure's keys now
  expect((await doc()).range).toEqual(range)
})

test('World\'s owed parts (U3f, D157 · proto01_UI2 03 §2, §5, §8): a character\'s voice in the header, its facts in the Inspector (used in shots, versions), See in clay ▶ — its bench — inside World', async ({ page }) => {
  test.setTimeout(90_000)
  const tag = Date.now().toString(36)
  type ProfileLite = { id: string }
  const prof = await api<ProfileLite>('POST', '/story/profiles', { name: `Maren ${tag}`, cls: 'character', appearance: 'a lighthouse keeper in a yellow oilskin' })
  await page.goto(`${appUrl()}#world/character/${prof.id}/v1`)
  const head = page.locator('[data-testid="world-header"]')
  await expect(head.locator('select')).toHaveCount(0)                                                        // the header: the entity and its version (2026-10-29)
  await expect(page.locator('[data-testid="world-inspector"] select[aria-label="profile voice"]')).toBeVisible()   // the voice, in the Inspector
  const insp = page.locator('[data-testid="world-inspector"]')
  await expect(insp.locator('[data-testid="world-uses"]')).toContainText('none yet')
  await expect(insp).toContainText('v1')
  await expect(insp.locator('button', { hasText: `Delete Maren ${tag}…` })).toBeVisible()
  await head.locator('button', { hasText: 'See in clay ▶' }).click()
  await expect(page.locator('[data-testid="world-clay"] canvas').first()).toBeVisible({ timeout: 20_000 })
  await expect(page.locator('.w-mode button.active')).toHaveText('Clay')
  expect(new URL(page.url()).hash).toMatch(/^#world/)                                                     // the bench opens inside World
  type StageLite = { purpose: string; bound: { profile_id: string } | null }
  await expect.poll(async () => (await api<{ items: StageLite[] }>('GET', '/stages?purpose=bench')).items.some((s) => s.bound?.profile_id === prof.id), { timeout: 10_000 }).toBe(true)
  await page.locator('.w-mode button', { hasText: 'Make' }).click()
  await expect(page.locator('[data-testid="world-make"]')).toBeVisible()
})

test('Performance and Final in Shots (U6b–c, D157 · proto01_UI2 04 §4–5): the open shot\'s levels — the For chip its version, the Layered method by default and kept on the shot\'s record, To Final ▸', async ({ page }) => {
  test.setTimeout(90_000)
  const tag = Date.now().toString(36)
  const a = await api<{ id: string; shot_id: string }>('POST', '/story/flow/shots', { title: `Lantern ${tag}`, scene: 'new' })
  await page.goto(`${appUrl()}#shots/${a.shot_id}/performance`)
  await expect(page.locator('[data-testid="shots-layer"]')).toHaveAttribute('data-level', 'performance')
  await expect(page.locator('.for-chip').first()).toContainText(`Lantern ${tag} · v1`)                          // this shot's takes (F41)
  await expect(page.locator('.perf-cards button[aria-pressed="true"]')).toHaveText('Final shot')                 // Layered, the default
  await page.locator('.perf-cards button', { hasText: 'Image to video' }).click()
  await page.locator('.w-rail-btn[data-level="clay"]').click()
  await page.locator('.w-rail-btn[data-level="performance"]').click()
  await expect(page.locator('.perf-cards button[aria-pressed="true"]')).toHaveText('Image to video')             // the shot's method, kept
  await expect.poll(async () => (await api<{ items: { id: string; versions: { method: string | null }[] }[] }>('GET', '/story/shots')).items.find((s) => s.id === a.shot_id)!.versions[0].method,
    { timeout: 10_000 }).toBe('start_still')                                                                        // U6c: on the shot version's record
  await page.locator('.s-foot button', { hasText: 'To Final ▸' }).click()
  await expect(page.locator('[data-testid="shots-layer"]')).toHaveAttribute('data-level', 'final')
  await expect(page.locator('[data-testid="shots-final"]')).toBeVisible()
  await expect(page.locator('.s-foot button', { hasText: 'Mark the shot final ✓' })).toBeVisible()
  expect(new URL(page.url()).hash).toBe(`#shots/${a.shot_id}/final`)
})

test('Episode (U7a, D157 · proto01_UI2 05 §1): the cut editor in its own layer, the route\'s finals listed beside it — a shot owes its final, a click opens it in Shots at Final', async ({ page }) => {
  test.setTimeout(60_000)
  const tag = Date.now().toString(36)
  const a = await api<{ id: string; shot_id: string }>('POST', '/story/flow/shots', { title: `Quay ${tag}`, scene: 'new' })
  const name = `Cut ${tag}`
  await api('POST', '/timelines', { name })
  await page.goto(`${appUrl()}#episode`)
  const row = page.locator(`[data-testid="episode-finals"] li[data-id="${a.shot_id}"]`)
  await expect(row).toHaveAttribute('data-final', 'owed')                                          // no final yet: owed, not "not on this route"
  await page.locator('.seq-row', { hasText: name }).click()
  await expect(page.locator('.e-stage .cut-row')).toHaveCount(5)                                   // V2 V1 · A1 A2 A3, inside the layer
  const stage = (await page.locator('.e-stage').boundingBox())!, cut = (await page.locator('.cut-stage').boundingBox())!
  expect(cut.x).toBeGreaterThanOrEqual(stage.x - 1)                                                // not over the left column
  expect(cut.width).toBeLessThanOrEqual(stage.width + 1)
  await row.locator('button').click()
  await expect(page.locator('[data-testid="shots-layer"]')).toHaveAttribute('data-level', 'final')
  expect(new URL(page.url()).hash).toBe(`#shots/${a.shot_id}/final`)
})

test('Assemble in Episode (U7b, D157 · proto01_UI2 05 §1, F33, F40): each shot of the route at its final, a shot without one left out and counted; Assemble again keeps the author\'s edit and places only the new final; the clips named after their shots', async ({ page }) => {
  test.setTimeout(150_000)
  const tag = Date.now().toString(36)
  type NodeLite = { id: string; shot_id: string }
  type JobLite = { id: string; status: string; result: { clip_id?: string } }
  const [a, b, c] = await Promise.all(['Gate', 'Road', 'Pier'].map((t) => api<NodeLite>('POST', '/story/flow/nodes', { type: 'shot', title: `${t} ${tag}` })))
  const g = (await api<{ graph: { revision: number; start: string | null; edges: { from: string; port: string; to: string }[] } }>('GET', '/story/flow')).graph
  const start = g.start ?? (await api<{ id: string }>('POST', '/story/flow/nodes', { type: 'start' })).id
  const g2 = (await api<{ graph: { revision: number; edges: { from: string; port: string; to: string }[] } }>('GET', '/story/flow')).graph
  await api('PUT', '/story/flow/graph', { revision: g2.revision, start, edges: [...g2.edges.filter((e) => e.from !== start), { from: start, port: 'out', to: a.id }, { from: a.id, port: 'out', to: b.id }, { from: b.id, port: 'out', to: c.id }] })
  const caps = await api<{ defaults: { i2v: string } }>('GET', '/capabilities')
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const finalFor = async (sid: string) => {                                    // a clip made from the start still: the version's final (one pass)
    const job = (await api<{ jobs: { id: string }[] }>('POST', '/jobs', { recipe: { kind: 'i2v', model_id: caps.defaults.i2v, start_asset: img, width: 832, height: 480, frames: 9, fps: 16, prompt_text: sid }, stage: false,
      origin: { suite: 'story', surface: 'for_shot', payload: { shot_id: sid, version: 'v1', use: true } } })).jobs[0]
    await expect.poll(async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.id === job.id)?.status, { timeout: 60_000 }).toBe('done')
    const sh = await api<{ revision: number }>('GET', `/story/shots/${sid}`)
    await api('PATCH', `/story/shots/${sid}`, { revision: sh.revision, versions: [{ id: 'v1', method: 'start_still' }] })
  }
  await finalFor(a.shot_id)
  await finalFor(b.shot_id)
  await page.goto(`${appUrl()}#episode`)
  await page.locator('[data-testid="episode-layer"] button.primary', { hasText: /^Assemble from the Flow/ }).click()
  const sheet = page.locator('.modal.assemble')
  await expect(sheet.locator('[data-testid="assemble-what"]')).toHaveText(`3 shots on this route · 1 without a final (left out): Pier ${tag}`)   // F33
  const name = `Cut ${tag}`
  await sheet.locator('input#assemble-name').fill(name)
  await sheet.locator('button.primary', { hasText: /^Assemble$/ }).click()
  await expect(page.locator('.e-stage .cut-clip.k-take')).toHaveCount(2)
  type Tracks = { video: { items: { id: number; name: string; speed: number; start: number; media_path: string | null }[] }[] }
  const tl = async () => (await api<{ items: { id: string; name: string; revision: number }[] }>('GET', '/timelines')).items.find((t) => t.name === name)!
  const v1 = async () => (await api<Tracks>('GET', `/timelines/${(await tl()).id}/tracks`)).video[0].items
  expect((await v1()).map((i) => i.name)).toEqual([`Gate ${tag}`, `Road ${tag}`])                                         // F40
  const conform = !!(await api<{ cut?: { conform: boolean } }>('GET', '/capabilities')).cut?.conform                     // U7c: RIFE here (not in CI)
  const conformed = async (n: number) => { if (conform) await expect.poll(async () => (await v1()).filter((i) => (i.media_path ?? '').includes('conform24')).length, { timeout: 60_000 }).toBe(n) }
  await conformed(2)                                                                                                        // the 16 fps takes conformed as they land
  // the author slows the gate; the pier's final lands; Assemble again keeps the gate's speed and places the pier after the road
  const gate = (await v1())[0].id
  await api('POST', `/timelines/${(await tl()).id}/edit`, { revision: (await tl()).revision, steps: [{ id: 'clip.speedDuration', params: { clips: [gate], speed: 50 } }] })
  await finalFor(c.shot_id)
  await page.locator('.seq-row', { hasText: name }).click()
  await page.locator('.seq-insp button[title^="Assemble again"]').click()
  await expect(sheet.locator('[data-testid="assemble-what"]')).toHaveText('3 shots on this route')
  await sheet.locator('button.primary', { hasText: /^Assemble again$/ }).click()
  await expect.poll(async () => (await v1()).map((i) => i.name), { timeout: 15_000 }).toEqual([`Gate ${tag}`, `Road ${tag}`, `Pier ${tag}`])
  await conformed(3)
  expect((await v1())[0]).toMatchObject({ id: gate, speed: 0.5 })                                                         // the author's edit kept
})

test('pages in homes (B3, D159 Q2): a page asked for on the album lands in the Sketches; New page… makes a folder of the open home, a thing moved into it stays there, Rename… and Delete the page… (its things go to the home) from its right-click and the grid head', async ({ page }) => {
  const tag = Date.now().toString(36)
  type Node = { id: string; path: string; name: string; page: boolean; total: number; children: Node[] }
  const find = (ns: Node[], f: (n: Node) => boolean): Node | undefined => { for (const n of ns) { if (f(n)) return n; const k = find(n.children, f); if (k) return k } return undefined }
  const treeNow = async () => (await api<{ homes: Node[] }>('GET', '/bin/tree')).homes
  const loose = await api<{ id: string }>('POST', '/groups', { name: `Loose ${tag}`, parent_id: 'album' })   // the album's root holds the homes only
  const sketches = find(await treeNow(), (n) => n.path === 'world/sketches')!
  expect(find(await treeNow(), (n) => n.id === loose.id)).toMatchObject({ page: true, path: `world/sketches/${loose.id}` })
  await openShell(page, 'bin')
  await openHome(page, 'world/sketches')
  const dialog = page.locator('.modal.ask')
  await page.locator('[data-testid="bin-grid"] .w-bin-head button[aria-label="New page…"]').click()
  await dialog.locator('input').fill(`Picks ${tag}`)
  await dialog.locator('button.primary').click()
  await expect.poll(async () => find(await treeNow(), (n) => n.name === `Picks ${tag}`)?.path ?? '').toMatch(/^world\/sketches\/grp_/)
  const picks = find(await treeNow(), (n) => n.name === `Picks ${tag}`)!
  const folder = page.locator(`[data-testid="bin-tree"] .b-node.page[data-path="${picks.path}"]`)
  await expect(folder).toBeVisible()
  await expect(page.locator('[data-testid="bin-grid"] .w-path')).toContainText(`Picks ${tag}`)            // the new page is open
  // a thing moved into it stays in the page (a folder of the Sketches)
  const src = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_asc&limit=1')).items[0]
  const copy = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [src.id] })).ids[0]
  await api('POST', '/bin/move', { ids: [copy], to: picks.id })
  await expect(binTiles(page)).toHaveCount(1)
  await expect(folder.locator('.n')).toHaveText('1')
  // Rename… from its right-click
  await folder.click({ button: 'right' })
  await page.locator('.ctx-menu button.item', { hasText: 'Rename the page…' }).click()
  await dialog.locator('input').fill(`Best ${tag}`)
  await dialog.locator('button.primary').click()
  await expect(folder.locator('.b-open')).toContainText(`Best ${tag}`)
  // Delete the page… from the grid head: its thing goes to the Sketches, nothing is deleted
  await page.locator('[data-testid="bin-grid"] .w-bin-head button[aria-label="Delete the page…"]').click()
  await expect(dialog).toContainText(`1 thing and the pages inside it go to ${sketches.name}`)
  await dialog.locator('button', { hasText: 'Delete the page' }).click()
  await expect(folder).toHaveCount(0)
  await expect.poll(async () => (await api<{ home_id: string }>('GET', `/bin/things/${copy}`)).home_id).toBe(sketches.id)
  await expect(page.locator('[data-testid="bin-grid"] .w-path')).toHaveText('bin/world/sketches')           // the home is open again
})

test('the Bin (U8, D157 · proto01_UI2 05 §2): a take made for a shot is in its shot\'s home — the tree, the grid, its home and roles in the Inspector, Tag…, Open its shot ▸; the Dock\'s drawer in World shows the homes', async ({ page }) => {
  test.setTimeout(90_000)
  const tag = Date.now().toString(36)
  type JobLite = { id: string; status: string; result: { asset_ids?: string[] } }
  const a = await api<{ id: string; shot_id: string }>('POST', '/story/flow/shots', { title: `Quay ${tag}`, scene: 'new' })
  const caps = await api<{ defaults: { i2v: string } }>('GET', '/capabilities')
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const job = (await api<{ jobs: { id: string }[] }>('POST', '/jobs', { recipe: { kind: 'i2v', model_id: caps.defaults.i2v, start_asset: img, width: 832, height: 480, frames: 9, fps: 16, prompt_text: `quay ${tag}` }, stage: false,
    origin: { suite: 'story', surface: 'for_shot', payload: { shot_id: a.shot_id, version: 'v1' } } })).jobs[0]
  await expect.poll(async () => (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.id === job.id)?.status, { timeout: 60_000 }).toBe('done')
  const take = (await api<{ items: JobLite[] }>('GET', '/jobs')).items.find((j) => j.id === job.id)!.result.asset_ids![0]
  await page.goto(`${appUrl()}#bin`)
  const shot = page.locator(`[data-testid="bin-tree"] .b-node[data-path="shots/${a.shot_id}"]`)
  await expect(shot).toContainText(`Quay ${tag}`)
  await shot.locator('.b-open').click()
  const tile = page.locator(`[data-testid="bin-grid"] .w-tile[data-id="${take}"]`)
  await expect(tile).toHaveCount(1)
  await expect(page.locator('[data-testid="bin-grid"] .w-path')).toHaveText(`bin/shots/Quay ${tag}`)
  await tile.dblclick()                                                                                       // U8b: seen large, Esc closes it
  await expect(page.locator('[data-testid="bin-loupe"]')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.locator('[data-testid="bin-loupe"]')).toHaveCount(0)
  await tile.click()
  const insp = page.locator('[data-testid="bin-inspector"]')
  await expect(insp).toContainText(`shots/Quay ${tag}/v1`)                                                   // its home, by its names
  await expect(insp).toContainText('clip')                                                                    // its role: the shot's clip
  await insp.locator('button', { hasText: 'Tag…' }).click()
  await page.locator('.modal.ask input').fill(`quay, ${tag}`)
  await page.locator('.modal.ask button.primary').click()
  await expect.poll(async () => (await api<AssetLite & { tags: string[] }>('GET', `/assets/${take}`)).tags, { timeout: 10_000 }).toEqual(['quay', tag])
  await insp.locator('button', { hasText: 'Open its shot ▸' }).click()
  await expect(page.locator('[data-testid="shots-layer"]')).toBeVisible()
  await expect.poll(() => new URL(page.url()).hash, { timeout: 10_000 }).toContain(`#shots/${a.shot_id}`)            // once the shots are read
  // the drawer: World's Dock offers the Bin with the homes in place of the old places
  await page.goto(`${appUrl()}#world`)
  await page.locator('.dock .dock-tabs button', { hasText: 'Bin' }).click()
  const homes = page.locator('[data-testid="bin-drawer-homes"]')
  await expect(homes).toContainText('Shots')
  await homes.locator(`.b-node[data-path="shots/${a.shot_id}"] .b-open`).click()
  await expect(page.locator(`.dock .bin-grid [data-id="${take}"]`)).toHaveCount(1)
})

test("the Bin holds up (B0, D159 · proto01_UI2 11 R2–R6): a home of 262 things draws only the rows in view and reads its next page at the end; Move to… of the hero asks, naming the role, and the version lets go of it; a deleted character's home says so and gives its things to the Sketches", async ({ page }) => {
  test.setTimeout(120_000)
  const tag = Date.now().toString(36)
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const [hero, cand] = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [img, img] })).ids
  await api('POST', '/bin/homes', { path: 'world/sketches' })
  const mara = await api<{ id: string }>('POST', '/story/profiles', { name: `Mara ${tag}`, cls: 'character', hero_asset_id: hero })
  type Node = { id: string; path: string; children: Node[] }
  const find = (ns: Node[], path: string): Node | undefined => ns.map((n) => (n.path === path ? n : find(n.children, path))).find(Boolean)
  const vpath = `world/character/${mara.id}/v1`
  const vh = find((await api<{ homes: Node[] }>('GET', '/bin/tree')).homes, vpath)!
  const many = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: Array(260).fill(cand) })).ids    // 260 events at once
  await api('POST', '/groups/move', { items: [cand, ...many].map((id) => ({ kind: 'asset', id })), to: vh.id })
  await page.goto(`${appUrl()}#bin`)
  await page.locator('[data-testid="bin-tree"] .b-node[data-path="world/character"] .b-chev').click()          // Characters unfolded
  const node = page.locator(`[data-testid="bin-tree"] .b-node[data-path="world/character/${mara.id}"]`)
  await node.locator('.b-open').click()                                                                     // her home: v1 below it
  await expect(page.locator('[data-testid="bin-count"]')).toHaveText('262')
  const tiles = page.locator('[data-testid="bin-grid"] .w-tile')
  await expect(tiles.first()).toBeVisible()
  expect(await tiles.count()).toBeLessThan(120)                                                              // only the rows in view
  const grid = page.locator('[data-testid="bin-grid"] .b-grid')
  await expect.poll(async () => {                                                                           // to the end: the next page comes
    await grid.evaluate((el) => { el.scrollTop = el.scrollHeight })
    return page.locator(`[data-testid="bin-grid"] .w-tile[data-id="${hero}"]`).count()
  }, { timeout: 15_000 }).toBe(1)
  expect(await tiles.count()).toBeLessThan(120)
  // Move to… of the hero asks first, naming the role; the version lets go of it
  await page.locator(`[data-testid="bin-grid"] .w-tile[data-id="${hero}"]`).click()
  await page.locator('[data-testid="bin-inspector"] button', { hasText: 'Move to…' }).click()
  await page.locator('.ctx-menu button.item', { hasText: 'Sketches' }).click()
  await expect(page.locator('.modal.ask')).toContainText('the hero')
  await page.locator('.modal.ask button', { hasText: 'Move' }).click()
  await expect.poll(async () => (await api<{ versions: { hero_asset_id: string | null }[] }>('GET', `/story/profiles/${mara.id}`)).versions[0].hero_asset_id, { timeout: 10_000 }).toBeNull()
  await expect(page.locator('[data-testid="bin-count"]')).toHaveText('261')
  // deleted, her home says so and gives its things to the Sketches
  await api('DELETE', `/story/profiles/${mara.id}`)
  await expect(node).toContainText('deleted')
  await node.locator('.b-open').click()
  await expect(page.locator('[data-testid="bin-gone"]')).toContainText(`Mara ${tag} was deleted`)
  await page.locator('[data-testid="bin-gone"] button', { hasText: 'Give its things to the Sketches' }).click()
  await expect(node).toHaveCount(0)
  await expect(page.locator('[data-testid="bin-grid"] .w-path')).toHaveText('bin/world/sketches')
})

/** A 1×1 PNG to bring in from the disk. */
const PNG_1PX = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==', 'base64')

test("one Bin (B1, D159 · proto01_UI2 11 §3): two selected and tagged at once; the keys move, show large and pin; two pinned side by side; the hero's Inspector says who uses it; Import… lands in the open home; the drawer in World offers the verbs of where you are", async ({ page }) => {
  test.setTimeout(120_000)
  const tag = Date.now().toString(36)
  const img = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&kind=image&sort=created_desc&limit=1')).items[0].id
  const [hero, a1, a2] = (await api<{ ids: string[] }>('POST', '/assets/duplicate', { ids: [img, img, img] })).ids
  const lia = await api<{ id: string }>('POST', '/story/profiles', { name: `Lia ${tag}`, cls: 'character', hero_asset_id: hero })
  type Node = { id: string; path: string; children: Node[] }
  const find = (ns: Node[], path: string): Node | undefined => ns.map((n) => (n.path === path ? n : find(n.children, path))).find(Boolean)
  const vh = find((await api<{ homes: Node[] }>('GET', '/bin/tree')).homes, `world/character/${lia.id}/v1`)!
  await api('POST', '/groups/move', { items: [a1, a2].map((id) => ({ kind: 'asset', id })), to: vh.id })
  await page.goto(`${appUrl()}#bin`)
  await page.locator('[data-testid="bin-tree"] .b-node[data-path="world/character"] .b-chev').click()
  await page.locator(`[data-testid="bin-tree"] .b-node[data-path="world/character/${lia.id}"] .b-open`).click()
  await expect(page.locator('[data-testid="bin-count"]')).toHaveText('3')
  const tile = (id: string) => page.locator(`[data-testid="bin-grid"] .w-tile[data-id="${id}"]`)
  const insp = page.locator('[data-testid="bin-inspector"]')
  // two selected, tagged at once
  await tile(a1).click()
  await tile(a2).click({ modifiers: ['Control'] })
  await expect(page.locator('[data-testid="bin-selected"]')).toContainText('2 selected')
  await expect(insp).toContainText('2 selected')
  await insp.locator('button', { hasText: 'Tag…' }).click()
  await page.locator('.modal.ask input').fill(`dusk-${tag}`)
  await page.locator('.modal.ask button.primary').click()
  for (const id of [a1, a2]) await expect.poll(async () => (await api<{ tags: string[] }>('GET', `/assets/${id}`)).tags, { timeout: 10_000 }).toContain(`dusk-${tag}`)
  // the keys: Space shows it large, → the next, Esc closes; C pins
  await tile(a2).click()
  await page.keyboard.press('Space')
  const loupe = page.locator('[data-testid="bin-loupe"]')
  await expect(loupe).toBeVisible()
  const at = await loupe.locator('.facts').innerText()
  await page.keyboard.press('ArrowRight')
  await expect.poll(() => loupe.locator('.facts').innerText()).not.toBe(at)
  await page.keyboard.press('Escape')
  await expect(loupe).toHaveCount(0)
  await tile(a1).click()
  await page.keyboard.press('c')
  await tile(a2).click()
  await page.keyboard.press('c')
  await expect(tile(a1).locator('.b-pin')).toHaveText('A')
  await page.locator('[data-testid="bin-grid"] button', { hasText: 'Compare 2' }).click()
  const compare = page.locator('[data-testid="bin-compare"]')
  await expect(compare.locator('.cell')).toHaveCount(2)
  await page.keyboard.press('Escape')
  await expect(compare).toHaveCount(0)
  // the hero's Inspector: what uses it
  await tile(hero).click()
  await expect(insp.locator('[data-testid="bin-uses"]')).toContainText(`Lia ${tag} v1`)
  await expect(insp.locator('[data-testid="bin-uses"]')).toContainText('the hero')
  // Import… lands in the open home
  const file = join(tmpdir(), `bin-import-${tag}.png`)
  writeFileSync(file, PNG_1PX)
  await page.locator('[data-testid="bin-grid"] .w-bin-head button[aria-label="Import…"], [data-testid="bin-grid"] .w-bin-head button[title^="Import…"]').first().click()
  await page.locator('.modal.ask input').fill(file)
  await page.locator('.modal.ask button.primary').click()
  await expect(page.locator('[data-testid="bin-count"]')).toHaveText('4')
  const brought = (await api<{ items: AssetLite[] }>('GET', '/assets?folder=all&sort=created_desc&limit=1')).items[0].id
  expect((await api<{ path: string }>('GET', `/bin/things/${brought}`)).path).toBe(`world/character/${lia.id}/v1`)
  // the drawer in World: the same Bin — where the layer was (Lia's home, the pins) — the verbs of where you are first
  await page.goto(`${appUrl()}#world`)
  await page.locator('.dock .dock-tabs button', { hasText: 'Bin' }).click()
  await expect(page.locator(`[data-testid="bin-drawer-homes"] .b-node.active[data-path="world/character/${lia.id}"]`)).toBeVisible()
  await expect(page.locator(`.dock .bin-grid [data-id="${a1}"] .b-pin`)).toHaveText('A')
  await page.locator(`.dock .bin-grid [data-id="${a1}"]`).click({ button: 'right' })
  await expect(page.locator('.ctx-menu button.item').first()).toContainText('Use as a reference (Make)')
  await expect(page.locator('.ctx-menu')).toContainText('Tag…')
  await page.keyboard.press('Escape')
})

/** Half a second of silence as a 16-bit mono WAV at 24 kHz (a sound to bring in). */
function silentWav(seconds: number): Buffer {
  const rate = 24000, n = Math.round(rate * seconds), data = n * 2
  const b = Buffer.alloc(44 + data)
  b.write('RIFF', 0); b.writeUInt32LE(36 + data, 4); b.write('WAVE', 8); b.write('fmt ', 12); b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22)
  b.writeUInt32LE(rate, 24); b.writeUInt32LE(rate * 2, 28); b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34); b.write('data', 36); b.writeUInt32LE(data, 40)
  return b
}

test("Episode's Sound (U8b, D157 · proto01_UI2 05 §1): a sound brought in is in Episode's Sound — a line's voice is not — and its + places it on Music at the playhead", async ({ page }) => {
  test.setTimeout(60_000)
  const tag = Date.now().toString(36)
  const wav = join(tmpdir(), `loom2-e2e-sound-${tag}.wav`)
  writeFileSync(wav, silentWav(0.5))
  const sound = (await api<{ items: { id: string; kind: string }[] }>('POST', '/assets/import', { paths: [wav] })).items[0]
  expect(sound.kind).toBe('audio')
  const name = `Sound cut ${tag}`
  const tl = await api<{ id: string }>('POST', '/timelines', { name })
  await page.goto(`${appUrl()}#episode`)
  await page.locator('.seq-row', { hasText: name }).click()
  const place = page.locator(`[data-testid="episode-sounds"] button[aria-label="place sound ${sound.id}"]`)
  await expect(place).toBeEnabled()
  await place.click()
  type Tracks = { audio: { items: { asset_id: string | null }[] }[] }
  await expect.poll(async () => (await api<Tracks>('GET', `/timelines/${tl.id}/tracks`)).audio[1].items.map((i) => i.asset_id), { timeout: 10_000 }).toEqual([sound.id])   // A2, Music
})
