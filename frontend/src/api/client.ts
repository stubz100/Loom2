// REST + WebSocket client for the orchestrator (06 §2/§6). Bytes are fetched by URL (loopback HTTP), never base64.
import type { Backend, EventFrame } from './types'

export class ApiError extends Error {
  status: number
  detail: string
  constructor(status: number, detail: string) { super(`${status}: ${detail}`); this.status = status; this.detail = detail }
}

let backend: Backend | null = null
export const setBackend = (b: Backend) => { backend = b }
export const getBackend = () => backend
export const baseUrl = () => backend ? `http://${backend.host}:${backend.port}` : ''

async function call<T>(method: string, path: string, body?: unknown, raw?: BodyInit): Promise<T> {
  if (!backend) throw new ApiError(0, 'backend not discovered yet')
  const headers: Record<string, string> = { 'X-Loom-Token': backend.token }
  let payload: BodyInit | undefined = raw
  if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body) }
  const res = await fetch(baseUrl() + path, { method, headers, body: payload })
  if (!res.ok) {
    let detail = res.statusText
    try { const j = await res.json(); detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j) } catch { /* keep statusText */ }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string) => call<T>('GET', path),
  post: <T>(path: string, body?: unknown) => call<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => call<T>('PUT', path, body),
  patch: <T>(path: string, body?: unknown) => call<T>('PATCH', path, body),
  del: <T>(path: string) => call<T>('DELETE', path),
  putBlob: async (sha256: string, bytes: ArrayBuffer | Blob) => call<{ sha256: string; bytes: number }>('PUT', `/blobs/${sha256}`, undefined, bytes),
  fileUrl: (path: string) => baseUrl() + path,
  thumbUrl: (assetId: string, size: 256 | 512 | 1024 = 256) => `${baseUrl()}/thumbs/${assetId}/${size}`,
  assetUrl: (assetId: string) => `${baseUrl()}/assets/${assetId}/file`,
}

export async function sha256Hex(data: ArrayBuffer): Promise<string> {
  const h = await crypto.subtle.digest('SHA-256', data)
  return [...new Uint8Array(h)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

export interface BinaryFrame { header: Record<string, unknown>; payload: Blob }

/** `/events` with reconnect; JSON frames → onEvent, binary previews → onBinary. */
export class EventsSocket {
  private ws: WebSocket | null = null
  private closed = false
  private backoff = 500
  private onEvent: (f: EventFrame) => void
  private onBinary: (f: BinaryFrame) => void
  private onStatus: (s: 'open' | 'closed') => void
  constructor(onEvent: (f: EventFrame) => void, onBinary: (f: BinaryFrame) => void, onStatus: (s: 'open' | 'closed') => void) {
    this.onEvent = onEvent; this.onBinary = onBinary; this.onStatus = onStatus
  }

  connect(): void {
    if (!backend || this.closed) return
    const url = `ws://${backend.host}:${backend.port}/events?token=${encodeURIComponent(backend.token)}`
    const ws = new WebSocket(url)
    ws.binaryType = 'arraybuffer'
    this.ws = ws
    ws.onopen = () => { this.backoff = 500; this.onStatus('open') }
    ws.onmessage = (ev) => {
      if (typeof ev.data === 'string') {
        let f: EventFrame
        try { f = JSON.parse(ev.data) as EventFrame } catch { return }           // one bad frame must not take the app down
        if (f.type !== 'pong') this.onEvent(f)
        return
      }
      const buf = ev.data as ArrayBuffer
      const len = new DataView(buf).getUint32(0, false)
      const header = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, len)))
      const mime = header.format === 'png' ? 'image/png' : 'image/jpeg'
      this.onBinary({ header, payload: new Blob([new Uint8Array(buf, 4 + len)], { type: mime }) })
    }
    ws.onclose = () => {
      this.onStatus('closed')
      if (this.closed) return
      setTimeout(() => this.connect(), this.backoff)
      this.backoff = Math.min(this.backoff * 2, 8000)
    }
    ws.onerror = () => ws.close()
  }

  close(): void { this.closed = true; this.ws?.close() }
}
