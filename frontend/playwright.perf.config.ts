// Perf baselines (D68, ArtCraft P6 §4): `npm run perf` (after `npm run build:e2e`). Same harness as the smoke run (global-setup.ts,
// `vite preview` on 1420, headless Edge on WebGL2) over a 10 000-asset synthetic project (LOOM2_PERF_ASSETS overrides; the project is
// built once — about three minutes — and kept in the temp folder while its inputs are unchanged). Results go to
// bench/perf/<yyyy-mm-dd>.json; `python scripts/perf_compare.py` prints the deltas against the previous file. Numbers feed P5 and P10.
import { defineConfig } from '@playwright/test'
import { edgeUse, previewServer } from './playwright.config'

export default defineConfig({
  testDir: './e2e',
  testMatch: 'perf.spec.ts',
  outputDir: './node_modules/.e2e/perf',
  globalSetup: './e2e/global-setup.ts',
  metadata: { assets: Number(process.env.LOOM2_PERF_ASSETS ?? 10_000) },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 300_000,
  globalTimeout: 1_200_000,
  expect: { timeout: 30_000 },
  reporter: 'list',
  // uncapped animation frames: headless Edge otherwise paces requestAnimationFrame at ~30 Hz here, which hides any frame under 33 ms;
  // uncapped, the scroll's frame rate measures the work per frame
  use: { ...edgeUse, launchOptions: { args: [...edgeUse.launchOptions.args, '--disable-frame-rate-limit', '--disable-gpu-vsync'] }, trace: 'off', screenshot: 'only-on-failure' },
  webServer: previewServer,
})
