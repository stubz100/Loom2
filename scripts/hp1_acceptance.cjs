// D129 (HP1, proto01_animate 31 §2): a prop held in a hand, accepted on the rig — the A1 rig's stage (Mara walking her library clip) with a
// cup put in her right hand, Stage's own passes rendered at the shot camera every 8th frame of the range in a visible Edge (WebGL): the
// cup's mask (its legend colour) stays on Mara's right-wrist keypoint, and it moves with her (not where it was put down).
//
//   1. a copy of engine/spikes/out/a1/project served by the e28 harness on 8792 (token e28) — no engine, no GPU job;
//   2. Vite dev on 1420;
//   3. node scripts/hp1_acceptance.cjs   (NODE_PATH=frontend/node_modules)        → engine/spikes/out/hp1/results.json
const { chromium } = require('playwright')
const fs = require('fs')
const OUT = 'F:/source/repos/stubz003_loom2/engine/spikes/out/hp1/'
const API = 'http://127.0.0.1:8792'
const H = { 'X-Loom-Token': 'e28', 'Content-Type': 'application/json' }
const api = async (m, p, b) => { const r = await fetch(API + p, { method: m, headers: H, body: b ? JSON.stringify(b) : undefined }); if (!r.ok) throw new Error(`${m} ${p} ${r.status} ${await r.text()}`); return r.json() }
;(async () => {
  fs.mkdirSync(OUT, { recursive: true })
  const stage = (await api('GET', '/stages')).items.find((s) => s.objects.some((o) => o.id === 'fig_m'))
  const full = await api('GET', `/stages/${stage.id}`)
  const cup = { id: 'prop_cup', kind: 'prop', name: 'Cup', preset: 'block', parent: 'fig_m', parent_joint: 'r_hand',
    transform: { pos: [0, -0.04, 0.03], rot: [0, 0, 0], scale: [0.07, 0.1, 0.07] }, colour_id: 9 }
  await api('PUT', `/stages/${stage.id}`, { ...full, objects: [...full.objects.filter((o) => o.id !== 'prop_cup'), cup] })
  const browser = await chromium.launch({ channel: 'msedge', headless: false, args: ['--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding', '--disable-background-timer-throttling'] })
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } })
  await page.goto('http://127.0.0.1:1420/?token=e28&port=8792&suite=stage')
  await page.waitForFunction(() => !!window.__loom2Stage, null, { timeout: 60000 })
  await page.evaluate(async (id) => { await window.__loom2Stage.open(id) }, stage.id)
  await page.locator('canvas.stage-canvas').waitFor({ timeout: 30000 })
  await page.waitForTimeout(2500)
  const rows = await page.evaluate(async ({ start, end }) => {
    const m = await import('/src/suites/stage/stageStore.ts')
    const s = m.useStage.getState()
    const cam = s.activeCamera()
    const out = []
    for (let f = start; f <= end; f += 8) {
      m.useStage.getState().setFrame(f)
      await new Promise((r) => setTimeout(r, 120))
      const p = await m.useStage.getState().passRenderer(cam, 832, 468)
      const hex = Object.entries(p.legend).find(([, id]) => id === 'prop_cup')?.[0]
      const bmp = await createImageBitmap(p.blobs.mask)
      const c = new OffscreenCanvas(bmp.width, bmp.height); const g = c.getContext('2d'); g.drawImage(bmp, 0, 0)
      const d = g.getImageData(0, 0, bmp.width, bmp.height).data
      const want = hex ? [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)] : null
      let n = 0, sx = 0, sy = 0
      if (want) for (let i = 0; i < d.length; i += 4) if (Math.abs(d[i] - want[0]) < 3 && Math.abs(d[i + 1] - want[1]) < 3 && Math.abs(d[i + 2] - want[2]) < 3) { n++; sx += (i / 4) % bmp.width; sy += Math.floor(i / 4 / bmp.width) }
      const figs = p.keypoints
      const ids = Object.values(p.legend)
      out.push({ f, px: n, cx: n ? sx / n : null, cy: n ? sy / n : null, wrists: figs.map((k) => k[4]), legend: ids })
    }
    return out
  }, full.range)
  await page.screenshot({ path: OUT + 'hp1-stage.jpg', quality: 85 })
  await browser.close()
  // Mara's right wrist: the keypoint set whose wrist is nearest the cup (the figures in the pose pass are left to right, not by id)
  const res = rows.map((r) => {
    const ds = r.wrists.filter((w) => w && w[2] > 0).map((w) => Math.hypot(w[0] - r.cx, w[1] - r.cy))
    return { ...r, dist: r.cx === null || !ds.length ? null : Math.min(...ds) }
  })
  const seen = res.filter((r) => r.px > 0)
  const far = Math.max(...seen.map((r) => r.dist ?? 1e9))
  const path = Math.hypot(seen.at(-1).cx - seen[0].cx, seen.at(-1).cy - seen[0].cy)
  const checks = [
    ['the cup is in every sampled frame\'s mask', seen.length === res.length, `${seen.length}/${res.length} frames, ${Math.round(seen.reduce((a, r) => a + r.px, 0) / Math.max(1, seen.length))} px each`],
    ['the cup stays on the right wrist (≤ 12 px at 832 × 468)', far <= 12, `farthest ${far.toFixed(1)} px`],
    ['the cup travels with the hand', path > 20, `${path.toFixed(0)} px from the first sample to the last`],
  ]
  for (const [name, ok, detail] of checks) console.log(`${ok ? 'PASS' : 'FAIL'} ${name} ${detail}`)
  fs.writeFileSync(OUT + 'results.json', JSON.stringify({ rows: res, checks }, null, 1))
  console.log(`hp1_acceptance: ${checks.filter((c) => c[1]).length}/${checks.length}`)
  await api('PUT', `/stages/${stage.id}`, { ...(await api('GET', `/stages/${stage.id}`)), objects: full.objects })   // the copy as it was
})().catch((e) => { console.error(e); process.exit(1) })
