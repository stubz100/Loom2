// Frame-accurate clip player (11 §4, E6): Mediabunny decodes the GOP-6 h264 proxy through WebCodecs and hands back one
// canvas per frame; we draw exactly the requested frame index (timestamp = (n + 0.5) / fps), so stepping, in/out and
// the filmstrip stay in lock-step with the PNG master. Onion skin overlays the start (and end) stills at 30 %.
import { ALL_FORMATS, CanvasSink, Input, UrlSource } from 'mediabunny'
import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import type { Clip } from '../../api/types'

export function Player({ clip, frame, onion = false, className = '', onDrawn }: { clip: Clip; frame: number; onion?: boolean; className?: string; onDrawn?: (frame: number) => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const sinkRef = useRef<{ input: Input; sink: CanvasSink; id: string } | null>(null)
  const seqRef = useRef(0)
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [err, setErr] = useState('')

  // open the proxy once per clip
  useEffect(() => {
    let cancelled = false
    setStatus('loading')
    const url = api.fileUrl(`/clips/${clip.id}/proxy.mp4`)
    const input = new Input({ source: new UrlSource(url), formats: ALL_FORMATS })
    void (async () => {
      try {
        const track = await input.getPrimaryVideoTrack()
        if (!track) throw new Error('the proxy has no video track')
        if (!(await track.canDecode())) throw new Error(`this browser cannot decode ${track.codec}`)
        if (cancelled) { input.dispose(); return }
        const c = canvasRef.current
        if (c) { c.width = track.displayWidth; c.height = track.displayHeight }
        sinkRef.current = { input, sink: new CanvasSink(track, { poolSize: 3 }), id: clip.id }
        setStatus('ready')
      } catch (e) {
        if (!cancelled) { setStatus('error'); setErr((e as Error).message) }
      }
    })()
    return () => { cancelled = true; input.dispose(); if (sinkRef.current?.input === input) sinkRef.current = null }
  }, [clip.id])

  // draw the requested frame; a newer request supersedes an older one still decoding
  useEffect(() => {
    if (status !== 'ready') return
    const s = sinkRef.current
    const c = canvasRef.current
    if (!s || !c || s.id !== clip.id) return
    const seq = ++seqRef.current
    void s.sink.getCanvas((frame + 0.5) / clip.fps).then((w) => {
      if (seq !== seqRef.current || !w) return
      const ctx = c.getContext('2d')
      if (!ctx) return
      ctx.drawImage(w.canvas, 0, 0, c.width, c.height)
      onDrawn?.(frame)
    }).catch(() => undefined)
  }, [frame, status, clip.id, clip.fps, onDrawn])

  return (
    <div className={`anim-player ${className}`}>
      <canvas ref={canvasRef} className="anim-canvas" />
      {onion && <img className="onion" src={api.assetUrl(clip.start_asset_id)} alt="" draggable={false} />}
      {onion && clip.end_asset_id && <img className="onion end" src={api.assetUrl(clip.end_asset_id)} alt="" draggable={false} />}
      {status === 'loading' && <div className="anim-overlay">decoding the proxy…</div>}
      {status === 'error' && <div className="anim-overlay err">player: {err}</div>}
    </div>
  )
}
