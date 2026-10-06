import react from '@vitejs/plugin-react'
import { resolve } from 'node:path'
import { defineConfig } from 'vite'

// Dev server pinned to the loopback origin the Tauri shell and the orchestrator's CORS allowlist expect.
// Two pages: the app (index.html) and the M0 spike harness (spikes.html).
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: { host: '127.0.0.1', port: 1420, strictPort: true },
  worker: { format: 'es' },
  // ag-psd is only imported when a PSD is exported; pre-bundle it so the first export in a dev session does not hit
  // Vite's "Outdated Optimize Dep" reload (the export failed and the page reloaded, 2026-10-06)
  optimizeDeps: { include: ['ag-psd'] },
  build: { target: 'es2022', rollupOptions: { input: { main: resolve(__dirname, 'index.html'), spikes: resolve(__dirname, 'spikes.html') } } },
})
