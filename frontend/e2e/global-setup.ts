// Global setup of the end-to-end smoke and perf runs (D68, ArtCraft P6 slices 3–5). Starts, in this order:
//   1. scripts/e2e_setup.py — a temp app state (fake Klein 4B weights, app.json pointing the engine at the fake), the synthetic project;
//   2. orchestrator/tests/fake_comfy.py as a standalone fake ComfyUI ("success": every prompt returns a magenta PNG);
//   3. the orchestrator (`python -m loom2.main`) with LOOM2_TOKEN, LOOM2_VARIANT from the environment (default full) and the project open.
// `vite preview` of the e2e build on 1420 is Playwright's `webServer` (the orchestrator's CORS allows 127.0.0.1:1420 only).
// The tests read what they need from process.env.LOOM2_E2E (JSON, see `E2EEnv` in fixtures.ts). The returned teardown stops
// everything this setup started: POST /shutdown for the orchestrator, then the process trees, then the temp folder.
import { spawn, spawnSync, type ChildProcess } from 'node:child_process'
import { copyFileSync, createWriteStream, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync } from 'node:fs'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { FullConfig } from '@playwright/test'

const HERE = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(HERE, '..')
const REPO = resolve(FRONTEND, '..')
const TOKEN = 'e2etoken'
const PYTHON = process.env.LOOM2_PYTHON ?? (process.platform === 'win32' ? join(REPO, 'orchestrator', '.venv', 'Scripts', 'python.exe') : join(REPO, 'orchestrator', '.venv', 'bin', 'python'))

const freePort = () => new Promise<number>((ok, fail) => {
  const s = createServer()
  s.unref()
  s.on('error', fail)
  s.listen(0, '127.0.0.1', () => { const a = s.address(); const p = typeof a === 'object' && a ? a.port : 0; s.close(() => ok(p)) })
})

async function waitHttp(url: string, ms: number, proc: ChildProcess, what: string, headers: Record<string, string> = {}): Promise<void> {
  const t0 = Date.now()
  while (Date.now() - t0 < ms) {
    if (proc.exitCode !== null) throw new Error(`${what} exited with code ${proc.exitCode} before answering`)
    try { const r = await fetch(url, { headers }); if (r.ok) return } catch { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 150))
  }
  throw new Error(`${what} did not answer ${url} within ${ms} ms`)
}

function killTree(p: ChildProcess | null): void {
  if (!p || p.exitCode !== null || p.pid === undefined) return
  if (process.platform === 'win32') spawnSync('taskkill', ['/T', '/F', '/PID', String(p.pid)], { stdio: 'ignore' })
  else p.kill('SIGKILL')
}

/** The e2e build keeps the dev hooks (`DEV_HOOKS`, src/devHooks.ts); it builds into dist-e2e/, so a plain `npm run build` (dist/) cannot replace it mid-run. */
function checkBuild(): void {
  const assets = join(FRONTEND, 'dist-e2e', 'assets')
  if (!existsSync(assets)) throw new Error('frontend/dist-e2e is missing: run `npm run build:e2e` first')
  const hooked = readdirSync(assets).some((f) => f.endsWith('.js') && readFileSync(join(assets, f), 'utf8').includes('__loom2Session'))
  if (!hooked) throw new Error('frontend/dist-e2e is not an e2e build (no dev hooks): run `npm run build:e2e` first')
}

export default async function globalSetup(config: FullConfig): Promise<() => Promise<void>> {
  checkBuild()
  const assets = Number(config.metadata.assets ?? 200)
  const variant = process.env.LOOM2_VARIANT === 'open' ? 'open' : 'full'
  const tmp = mkdtempSync(join(tmpdir(), 'loom2-e2e-'))
  const state = join(tmp, 'state')
  mkdirSync(join(state, 'logs'), { recursive: true })
  // the smoke project is fresh per run; a large perf project is kept between runs (e2e_setup.py reuses it while its inputs are unchanged)
  const project = assets > 1000 ? join(tmpdir(), `loom2-perf-${assets}`) : join(tmp, 'proj')
  const [enginePort, port] = [await freePort(), await freePort()]
  const env = { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUNBUFFERED: '1' }

  const t0 = Date.now()
  const prep = spawnSync(PYTHON, [join(REPO, 'scripts', 'e2e_setup.py'), '--state', state, '--project', project, '--engine-port', String(enginePort), '--count', String(assets)],
    { env, encoding: 'utf8', timeout: 900_000 })
  if (prep.status !== 0) throw new Error(`e2e_setup.py failed (${prep.status}): ${prep.stderr || prep.stdout}`)
  const prepared = JSON.parse(prep.stdout.trim().split('\n').pop()!) as { reused: boolean }
  console.log(`[e2e] state ${state} · project ${project} (${assets} assets${prepared.reused ? ', reused' : ''}) in ${((Date.now() - t0) / 1000).toFixed(1)} s · variant ${variant}`)

  let fake: ChildProcess | null = null
  let orch: ChildProcess | null = null
  const teardown = async () => {
    if (orch && orch.exitCode === null) {
      try { await fetch(`http://127.0.0.1:${port}/shutdown`, { method: 'POST', headers: { 'X-Loom-Token': TOKEN } }) } catch { /* already gone */ }
      const t = Date.now()
      while (orch.exitCode === null && Date.now() - t < 10_000) await new Promise((r) => setTimeout(r, 100))
    }
    killTree(orch)
    killTree(fake)
    for (const f of ['fake_comfy.log', 'orchestrator.e2e.log']) {     // keep the two logs for a failed scenario's post-mortem (the state goes)
      try { mkdirSync(join(REPO, 'frontend', 'node_modules', '.e2e'), { recursive: true }); copyFileSync(join(state, 'logs', f), join(REPO, 'frontend', 'node_modules', '.e2e', f)) } catch { /* none */ }
    }
    for (let i = 0; i < 10; i++) {                                   // Windows: files may stay locked for a moment after the processes exit
      try { rmSync(tmp, { recursive: true, force: true }); break } catch { await new Promise((r) => setTimeout(r, 300)) }
    }
  }
  try {
    fake = spawn(PYTHON, [join(REPO, 'orchestrator', 'tests', 'fake_comfy.py'), '--port', String(enginePort), '--mode', 'success', '--parent-pid', String(process.pid), '--output-dir', join(state, 'engine_out'),
      '--models-root', join(state, 'models')],                                                           // LT1: the loras folder in the loader's enum
      { env, stdio: ['ignore', 'pipe', 'pipe'] })
    const fakeLog = createWriteStream(join(state, 'logs', 'fake_comfy.log'))
    fake.stdout!.pipe(fakeLog); fake.stderr!.pipe(fakeLog)
    await waitHttp(`http://127.0.0.1:${enginePort}/system_stats`, 30_000, fake, 'fake engine')

    orch = spawn(PYTHON, ['-m', 'loom2.main', '--port', String(port), '--state', state, '--project', project, '--parent-pid', String(process.pid)],   // V54: gone with a killed run
      { cwd: join(REPO, 'orchestrator'), env: { ...env, LOOM2_TOKEN: TOKEN, LOOM2_VARIANT: variant }, stdio: ['ignore', 'pipe', 'pipe'] })
    const orchLog = createWriteStream(join(state, 'logs', 'orchestrator.e2e.log'))
    orch.stdout!.pipe(orchLog); orch.stderr!.pipe(orchLog)
    await waitHttp(`http://127.0.0.1:${port}/project`, 60_000, orch, 'orchestrator', { 'X-Loom-Token': TOKEN })
  } catch (e) {
    for (const f of ['fake_comfy.log', 'orchestrator.e2e.log']) { try { console.error(`--- ${f}\n${readFileSync(join(state, 'logs', f), 'utf8').slice(-4000)}`) } catch { /* none */ } }
    await teardown()
    throw e
  }
  console.log(`[e2e] fake engine :${enginePort} · orchestrator :${port} up after ${((Date.now() - t0) / 1000).toFixed(1)} s`)
  process.env.LOOM2_E2E = JSON.stringify({ port, enginePort, token: TOKEN, state, project, assets, variant })
  return teardown
}
