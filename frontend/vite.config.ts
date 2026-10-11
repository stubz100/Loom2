import react from '@vitejs/plugin-react'
import { resolve } from 'node:path'
import { defineConfig } from 'vite'

// Dev server pinned to the loopback origin the Tauri shell and the orchestrator's CORS allowlist expect.
// The app (index.html); the M0 spike harness (spikes.html) is built only with LOOM2_SPIKES=1 (D69: not shipped; `vite` dev serves it always).
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: { host: '127.0.0.1', port: 1420, strictPort: true },
  worker: { format: 'es' },
  // ag-psd is only imported when a PSD is exported; pre-bundle it so the first export in a dev session does not hit
  // Vite's "Outdated Optimize Dep" reload (the export failed and the page reloaded, 2026-10-06)
  optimizeDeps: { include: ['ag-psd'] },
  build: { target: 'es2022', rollupOptions: { input: { main: resolve(__dirname, 'index.html'), ...(process.env.LOOM2_SPIKES === '1' ? { spikes: resolve(__dirname, 'spikes.html') } : {}) } } },
})
