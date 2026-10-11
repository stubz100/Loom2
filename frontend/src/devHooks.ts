// Dev hooks (`window.__loom2*`, dev deep links such as `&renderer=webgl`): on in the dev server and in the end-to-end build
// (`npm run build:e2e` = `vite build --mode e2e`, D68), which the Playwright smoke and perf runs drive; off in every shipped build.
export const DEV_HOOKS: boolean = import.meta.env.DEV || import.meta.env.MODE === 'e2e'
