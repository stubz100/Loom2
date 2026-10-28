// D155: the detached loupe / player window (07 §3f) — the Catalogue loupe's viewer in its own window, for a second monitor. It boots
// against the backend on its own (the shell's handshake, or the token / port its URL carries), follows the main window's loupe or
// selection over the channel unless held, and offers Fit / 1:1, full screen and close. Nothing edits here: the verbs stay in the main window.
import { Expand, Pause, Play, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { http, setBackend, setMediaKey, unwrap } from '../api/client'
import type { Asset } from '../api/types'
import { discoverBackend, isTauri } from '../shell/tauri'
import { Playable, useZoomPan, xfStyle } from '../suites/catalogue/Loupe'
import { loupeMedia } from '../suites/catalogue/media'
import { onLoupe, postLoupe } from './loupeLink'
import '../suites/catalogue/catalogue.css'

async function setFullscreen(on: boolean): Promise<void> {
  if (isTauri()) {
    const { getCurrentWindow } = await import('@tauri-apps/api/window')
    await getCurrentWindow().setFullscreen(on)
  } else if (on) await document.documentElement.requestFullscreen?.()
  else if (document.fullscreenElement) await document.exitFullscreen()
}

async function closeWindow(): Promise<void> {
  if (isTauri()) {
    const { getCurrentWindow } = await import('@tauri-apps/api/window')
    await getCurrentWindow().close()
  } else window.close()
}

export default function DetachedLoupe() {
  const [status, setStatus] = useState<'connecting' | 'ready' | string>('connecting')
  const [assetId, setAssetId] = useState<string | null>(new URLSearchParams(location.search).get('asset'))
  const [asset, setAsset] = useState<Asset | null>(null)
  const [hold, setHold] = useState(false)
  const [full, setFull] = useState(false)
  const holdRef = useRef(hold)
  useEffect(() => { holdRef.current = hold }, [hold])
  useEffect(() => {
    let dead = false
    void (async () => {
      try {
        const b = await discoverBackend()
        setBackend(b)
        setMediaKey((await unwrap(http.GET('/session'))).media_key)
        if (!dead) setStatus('ready')
      } catch (e) { if (!dead) setStatus((e as Error).message || 'the backend is not reachable') }
    })()
    return () => { dead = true }
  }, [])
  useEffect(() => onLoupe((m) => { if (m.type === 'show' && m.assetId && !holdRef.current) setAssetId(m.assetId) }), [])
  useEffect(() => { if (status === 'ready') postLoupe({ type: 'hello' }) }, [status])
  useEffect(() => {
    const bye = () => postLoupe({ type: 'closed' })
    window.addEventListener('pagehide', bye)
    return () => window.removeEventListener('pagehide', bye)
  }, [])
  useEffect(() => {
    if (status !== 'ready' || !assetId) return
    let dead = false
    unwrap(http.GET('/assets/{asset_id}', { params: { path: { asset_id: assetId } } })).then((a) => { if (!dead) setAsset(a as Asset) }).catch(() => { if (!dead) setAsset(null) })
    return () => { dead = true }
  }, [status, assetId])
  useEffect(() => { document.title = asset ? `loom2 — ${asset.model_id ?? asset.suite} · ${asset.id.slice(-6)}` : 'loom2 — loupe' }, [asset])
  const dims = useMemo(() => (asset?.w && asset?.h ? { w: asset.w, h: asset.h } : null), [asset])   // one object per asset: `fit` keeps its identity
  const { xf, ref, fit, one, handlers } = useZoomPan(dims)
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === '0') { e.preventDefault(); if (e.altKey) one(); else fit() }   // the loupe's own accelerators (D72)
      else if (e.key === 'Escape' && full) { void setFullscreen(false); setFull(false) }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [fit, one, full])
  const m = asset ? loupeMedia(asset) : null
  const toggleFull = async () => { await setFullscreen(!full); setFull(!full) }
  return (
    <div className="detached-loupe" data-asset={asset?.id ?? ''} data-following={hold ? 'held' : 'following'}>
      <div className={`view${m?.zoom ? '' : ' play'}`} ref={ref} {...(m?.zoom ? handlers : {})}>
        {status === 'connecting' ? <p className="muted">connecting…</p>
          : status !== 'ready' ? <p className="error">{status}</p>
          : !asset ? <p className="muted">{assetId ? 'loading…' : 'nothing to show yet — open an image or a clip in the main window'}</p>
          : m!.zoom ? <img src={m!.src} alt="" style={xfStyle(xf)} draggable={false} /> : <Playable m={m!} />}
      </div>
      <div className="bar" role="toolbar" aria-label="Detached loupe">
        {asset && <><span>{asset.model_id ?? asset.suite}</span>{asset.kind !== 'audio' && <span>{asset.w}×{asset.h}</span>}{asset.duration_s ? <span>{asset.duration_s} s</span> : null}{asset.seed != null && <span>seed {asset.seed}</span>}</>}
        <span className="spacer" />
        {m?.zoom && <><span>{Math.round(xf.s * 100)}%</span><button className="quiet" title="Fit to view (Ctrl+0)" onClick={fit}>Fit</button><button className="quiet" title="Actual pixels (Ctrl+Alt+0)" onClick={one}>1:1</button></>}
        <button className={`quiet latch${hold ? ' active' : ''}`} aria-pressed={hold} title={hold ? 'Held: the main window no longer changes this view — press to follow it again' : 'Following the main window\'s loupe or selection — press to hold this image'} onClick={() => setHold(!hold)}>
          {hold ? <Play size={14} /> : <Pause size={14} />} {hold ? 'Held' : 'Following'}
        </button>
        <button className="quiet" title="Full screen (Esc leaves it)" onClick={() => void toggleFull()}><Expand size={14} /> {full ? 'Leave full screen' : 'Full screen'}</button>
        <button className="quiet" title="Close this window" onClick={() => void closeWindow()}><X size={14} /> Close</button>
      </div>
    </div>
  )
}
