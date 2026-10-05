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
  build: { target: 'es2022', rollupOptions: { input: { main: resolve(__dirname, 'index.html'), spikes: resolve(__dirname, 'spikes.html') } } },
})
