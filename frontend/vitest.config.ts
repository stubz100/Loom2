// Vitest (D68, ArtCraft P6 slices 1–2): the unit suites under jsdom. Separate from vite.config.ts so `npm run build` never reads it;
// the test files sit under src/ and tsc -b type-checks them with the app (they import their API from 'vitest', no globals).
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  worker: { format: 'es' },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    restoreMocks: true,
    unstubGlobals: true,
  },
})
