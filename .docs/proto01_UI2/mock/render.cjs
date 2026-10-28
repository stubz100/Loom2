// Renders ui2-mock.html's eight screens to ../img/ui-*.jpg (Playwright on Edge, headless, 1600 × 1000).
//   NODE_PATH=frontend/node_modules node .docs/proto01_UI2/mock/render.cjs
const { chromium } = require('playwright')
const path = require('path')
const screens = [['character', 'ui-1-world-character'], ['place', 'ui-2-world-place'], ['flow', 'ui-3-shots-flow'], ['clay', 'ui-4-shots-clay'],
  ['performance', 'ui-5-shots-performance'], ['final', 'ui-6-shots-final'], ['episode', 'ui-7-episode'], ['bin', 'ui-8-bin']]
;(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
  const file = 'file:///' + path.resolve(__dirname, 'ui2-mock.html').replace(/\\/g, '/')
  for (const [s, name] of screens) {
    await page.goto(`${file}?s=${s}`)
    await page.waitForTimeout(300)
    await page.screenshot({ path: path.resolve(__dirname, '..', 'img', `${name}.jpg`), type: 'jpeg', quality: 86 })
    console.log('rendered', name)
  }
  await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })
