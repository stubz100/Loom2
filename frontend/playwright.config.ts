// End-to-end smoke (D68, ArtCraft P6): Playwright on the installed Edge (`channel: 'msedge'`, also on GitHub's Windows runners — no
// browser download) against `vite preview` of the e2e build (`npm run build:e2e`), a real orchestrator and the standalone fake engine
// (e2e/global-setup.ts). One worker: the scenarios share one orchestrator and project, each starts from a fresh page.
// WebGPU-specific checks stay in scripts/edit_headed_check.py; headless Edge cannot present WebGPU, so the editor runs on WebGL2.
import { defineConfig } from '@playwright/test'

export const PREVIEW_PORT = 1420                                  // the only browser origin the orchestrator's CORS allows (api.py DEV_ORIGINS)

export const edgeUse: { channel: string; headless: boolean; viewport: { width: number; height: number }; launchOptions: { args: string[] } } = {
  channel: 'msedge',
  headless: true,
  viewport: { width: 1600, height: 1000 },
  launchOptions: { args: ['--enable-unsafe-swiftshader', '--disable-background-timer-throttling', '--disable-renderer-backgrounding'] },
}

export const previewServer = {
  command: `npx vite preview --outDir dist-e2e --host 127.0.0.1 --port ${PREVIEW_PORT} --strictPort`,   // its own folder: a plain build cannot replace it mid-run
  url: `http://127.0.0.1:${PREVIEW_PORT}/`,
  reuseExistingServer: false,                                     // a busy 1420 (a dev server) fails the run instead of testing the wrong build
  timeout: 60_000,
  stdout: 'ignore',
  stderr: 'pipe',
} as const

export default defineConfig({
  testDir: './e2e',
  testMatch: 'smoke.spec.ts',
  outputDir: './node_modules/.e2e/smoke',
  globalSetup: './e2e/global-setup.ts',
  metadata: { assets: 200 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? [['list'], ['github']] : 'list',
  use: { ...edgeUse, trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  webServer: previewServer,
})
