import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Dev server pinned to the loopback origin the Tauri shell and the E2 server's CORS allowlist expect.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: { host: '127.0.0.1', port: 1420, strictPort: true },
  worker: { format: 'es' },
  build: { target: 'es2022' },
})
