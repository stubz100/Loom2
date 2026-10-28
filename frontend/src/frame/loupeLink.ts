// D155: the detachable loupe / player window — one BroadcastChannel between the main window and the detached one. The main window
// publishes which asset to show (the loupe's, else the primary selection); the detached window follows unless held, says hello when it
// opens (the main answers with the current asset) and says so when it closes. A leaf module: the Catalogue commands and the detached view
// import it; nothing here touches a store.
import { isTauri } from '../shell/tauri'

export const LOUPE_CHANNEL = 'loom2-loupe'
export const LOUPE_LABEL = 'loupe'
export type LoupeMessage = { type: 'show'; assetId: string | null } | { type: 'hello' } | { type: 'closed' }

/** What the detached window follows: the loupe's asset, else the primary selection, else nothing. */
export const followedAsset = (loupe: string | null | undefined, primary: string | null | undefined): string | null => loupe ?? primary ?? null

/** The detached window's URL: this page with `view=loupe` and the asset; a browser's token / port / host and the theme ride along. */
export function detachedUrl(assetId: string | null, loc: { origin: string; pathname: string; search: string } = location): string {
  const q = new URLSearchParams(loc.search)
  const out = new URLSearchParams()
  out.set('view', 'loupe')
  for (const k of ['token', 'port', 'host', 'theme']) { const v = q.get(k); if (v) out.set(k, v) }
  if (assetId) out.set('asset', assetId)
  return `${loc.origin}${loc.pathname}?${out.toString()}`
}

let channel: BroadcastChannel | null = null
export function loupeChannel(): BroadcastChannel | null {
  if (channel) return channel
  if (typeof BroadcastChannel === 'undefined') return null
  channel = new BroadcastChannel(LOUPE_CHANNEL)
  return channel
}
export const postLoupe = (m: LoupeMessage): void => { loupeChannel()?.postMessage(m) }
/** Listen for the other window; returns the cleanup for an effect. */
export function onLoupe(h: (m: LoupeMessage) => void): () => void {
  const c = loupeChannel()
  if (!c) return () => undefined
  const f = (e: MessageEvent<LoupeMessage>) => h(e.data)
  c.addEventListener('message', f)
  return () => c.removeEventListener('message', f)
}
/** Tests: drop the channel so the next call makes a fresh one. */
export const resetLoupeChannel = (): void => { channel?.close(); channel = null; popup = null }

let popup: Window | null = null
/** Open the detached window on the asset — or, when one is open, focus it and show the asset there. */
export async function openDetached(assetId: string | null): Promise<void> {
  const url = detachedUrl(assetId)
  if (isTauri()) {
    const { WebviewWindow } = await import('@tauri-apps/api/webviewWindow')
    const existing = await WebviewWindow.getByLabel(LOUPE_LABEL)
    if (existing) { await existing.setFocus(); postLoupe({ type: 'show', assetId }); return }
    new WebviewWindow(LOUPE_LABEL, { url, title: 'loom2 — loupe', width: 1280, height: 800, minWidth: 480, minHeight: 320 })
    return
  }
  if (popup && !popup.closed) { popup.focus(); postLoupe({ type: 'show', assetId }); return }
  popup = window.open(url, 'loom2-loupe', 'popup=yes,width=1280,height=800')
}
