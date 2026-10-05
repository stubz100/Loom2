// The only module that imports @tauri-apps/api and plugins (06 §8): shell adapters with browser fallbacks.
import type { Backend } from '../api/types'

export const isTauri = (): boolean => typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

export interface BackendInfo { ready: boolean; port: number; token: string; host: string; error: string | null; log_tail: string[] }

export async function backendInfo(): Promise<BackendInfo | null> {
  if (!isTauri()) return null
  const { invoke } = await import('@tauri-apps/api/core')
  return invoke<BackendInfo>('backend_info')
}

/** Resolve the orchestrator address: the shell's handshake inside Tauri, env/query/localStorage in a browser. */
export async function discoverBackend(timeoutMs = 90_000): Promise<Backend> {
  if (isTauri()) {
    const t0 = performance.now()
    while (performance.now() - t0 < timeoutMs) {
      const info = await backendInfo()
      if (info?.ready) return { host: info.host, port: info.port, token: info.token }
      if (info?.error) throw new Error(info.error)
      await new Promise((r) => setTimeout(r, 300))
    }
    throw new Error('the orchestrator did not report READY in time')
  }
  const q = new URLSearchParams(location.search)
  const token = q.get('token') ?? localStorage.getItem('loom2.token') ?? ''
  if (q.get('token')) localStorage.setItem('loom2.token', q.get('token')!)
  const port = Number(q.get('port') ?? localStorage.getItem('loom2.port') ?? import.meta.env.VITE_LOOM2_PORT ?? 8765)
  if (q.get('port')) localStorage.setItem('loom2.port', String(port))
  if (!token) throw new Error('no backend token: open the app from the shell, or add ?token=…&port=… from the orchestrator READY line')
  return { host: '127.0.0.1', port, token }
}

export async function requestAppExit(): Promise<void> {
  if (!isTauri()) return
  const { invoke } = await import('@tauri-apps/api/core')
  await invoke('request_exit')
}

export async function revealPath(path: string): Promise<void> {
  if (!isTauri()) { await navigator.clipboard?.writeText(path); return }
  const { invoke } = await import('@tauri-apps/api/core')
  await invoke('reveal_path', { path })
}

/** OS folder picker (07 §1.2: the only native dialogs are OS file pickers). Returns null when cancelled or in a browser. */
export async function pickFolder(title: string, defaultPath?: string): Promise<string | null> {
  if (!isTauri()) return null
  const { open } = await import('@tauri-apps/plugin-dialog')
  const picked = await open({ directory: true, multiple: false, title, defaultPath: defaultPath || undefined })
  return typeof picked === 'string' ? picked : null
}
