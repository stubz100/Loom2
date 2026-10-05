// Spike result reporting: show on the page and append to orchestrator/spikes/out/<spike>.jsonl via the E2 server.
export const E2_SERVER = 'http://127.0.0.1:8765'

export type SpikeRow = Record<string, unknown> & { spike: string }

export function hostInfo() {
  const nav = navigator as Navigator & { userAgentData?: { platform?: string } }
  const isTauri = '__TAURI_INTERNALS__' in window
  return {
    shell: isTauri ? 'tauri-webview2' : 'browser',
    ua: navigator.userAgent.slice(0, 160),
    platform: nav.userAgentData?.platform ?? navigator.platform,
    dpr: window.devicePixelRatio,
    viewport: [window.innerWidth, window.innerHeight],
    webgpu: 'gpu' in navigator,
    when: new Date().toISOString(),
  }
}

export async function report(row: SpikeRow, el?: HTMLElement | null) {
  const full = { ...row, host: hostInfo() }
  if (el) {
    const pre = document.createElement('pre')
    pre.textContent = JSON.stringify(full, null, 1)
    el.appendChild(pre)
  }
  console.log('[spike]', JSON.stringify(full))
  try {
    await fetch(`${E2_SERVER}/spike/result`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(full) })
  } catch (e) {
    console.warn('[spike] result not posted (E2 server down?)', e)
  }
  return full
}

export function stats(samples: number[]) {
  const s = [...samples].sort((a, b) => a - b)
  const q = (p: number) => s[Math.min(s.length - 1, Math.floor(p * s.length))]
  return { n: s.length, min: +s[0].toFixed(2), median: +q(0.5).toFixed(2), p95: +q(0.95).toFixed(2), max: +s[s.length - 1].toFixed(2) }
}

export function log(el: HTMLElement | null | undefined, msg: string) {
  console.log(msg)
  if (!el) return
  const d = document.createElement('div')
  d.textContent = msg
  el.appendChild(d)
}
