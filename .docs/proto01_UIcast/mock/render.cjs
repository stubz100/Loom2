// Renders cast-mock.html's six screens to ../img/ui-*.jpg (Playwright on Edge, 1600 × 1000).
//   node .docs/proto01_UIcast/mock/render.cjs        (NODE_PATH=frontend/node_modules)
const { chromium } = require('playwright')
const path = require('path')
const screens = [['bench', 'ui-1-character-bench'], ['image', 'ui-2-image-prototype'], ['skeleton', 'ui-3-skeleton-bench'], ['lineup', 'ui-4-line-up'],
  ['place', 'ui-5-place-bench'], ['clay', 'ui-6-clay-cast-cards']]
;(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
  const file = 'file:///' + path.resolve(__dirname, 'cast-mock.html').replace(/\\/g, '/')
  for (const [s, name] of screens) {
    await page.goto(`${file}?s=${s}`)
    await page.waitForTimeout(200)
    await page.screenshot({ path: path.resolve(__dirname, '..', 'img', `${name}.jpg`), type: 'jpeg', quality: 86 })
    console.log('rendered', name)
  }
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
