// REST + WebSocket client for the orchestrator (06 §2/§6). Bytes are fetched by URL (loopback HTTP), never base64.
// D38: JSON calls go through `http`, an openapi-fetch client typed by schema.d.ts (generated from the orchestrator's OpenAPI
// document): paths, path/query parameters, bodies and replies are all checked. `unwrap` turns its result into the reply or
// an ApiError, as the old untyped helpers did.
import createClient, { type Client } from 'openapi-fetch'
import type { paths } from './schema'
import type { Backend, EventFrame } from './types'

export class ApiError extends Error {
  status: number
  detail: string
  constructor(status: number, detail: string) { super(`${status}: ${detail}`); this.status = status; this.detail = detail }
}

let backend: Backend | null = null
/** D67: the per-launch read-only key the media URLs carry (`?k=`): <img> / <video> cannot send the token header. */
let mediaKey = ''
export const setMediaKey = (k: string) => { mediaKey = k }
/** A media URL with the key: thumbnails, asset files, clip proxies and frames, document thumbnails, blobs. */
const withKey = (url: string) => (mediaKey ? `${url}${url.includes('?') ? '&' : '?'}k=${encodeURIComponent(mediaKey)}` : url)
export const getBackend = () => backend
export const baseUrl = () => backend ? `http://${backend.host}:${backend.port}` : ''

/** The typed client for the discovered backend (a live binding: replaced by setBackend). */
export let http: Client<paths> = createClient<paths>()
export const setBackend = (b: Backend) => {
  backend = b
  http = createClient<paths>({ baseUrl: baseUrl() })
  http.use({ onRequest: ({ request }) => { request.headers.set('X-Loom-Token', b.token); return request } })
}

/** The reply of an openapi-fetch call, or an ApiError carrying the server's `detail`. */
export async function unwrap<R extends { data?: unknown; error?: unknown; response: Response }>(call: Promise<R>): Promise<Exclude<R['data'], undefined>> {
  if (!backend) throw new ApiError(0, 'backend not discovered yet')
  const { data, error, response } = await call
  if (!response.ok) {
    const d = (error as { detail?: unknown } | undefined)?.detail
    throw new ApiError(response.status, typeof d === 'string' ? d : d !== undefined ? JSON.stringify(d) : JSON.stringify(error ?? response.statusText))
  }
  return data as Exclude<R['data'], undefined>
}

/** Query parameters of GET /assets and /assets/groups (AssetQuery). */
export type AssetQueryParams = NonNullable<paths['/assets']['get']['parameters']['query']>

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

/** Byte transfers and URLs (D4: pixels never go through JSON). JSON calls use `unwrap(http.GET(…))` and friends (D38). */
export const api = {
  putBlob: async (sha256: string, bytes: ArrayBuffer | Blob) => call<{ sha256: string; bytes: number }>('PUT', `/blobs/${sha256}`, undefined, bytes),
  putThumbnail: async (assetId: string, png: Blob) => call<unknown>('PUT', `/assets/${assetId}/thumbnail`, undefined, png),   // P18: a client-rendered view
  /** CA1: a file the client parses itself (a motion library glb / fbx), fetched with the token. */
  getBytes: async (path: string): Promise<ArrayBuffer> => {
    if (!backend) throw new ApiError(0, 'backend not discovered yet')
    const res = await fetch(baseUrl() + path, { headers: { 'X-Loom-Token': backend.token } })
    if (!res.ok) throw new ApiError(res.status, res.statusText)
    return res.arrayBuffer()
  },
  fileUrl: (path: string) => withKey(baseUrl() + path),
  thumbUrl: (assetId: string, size: 256 | 512 | 1024 = 256) => withKey(`${baseUrl()}/thumbs/${assetId}/${size}`),
  assetUrl: (assetId: string) => withKey(`${baseUrl()}/assets/${assetId}/file`),
}

export async function sha256Hex(data: ArrayBuffer): Promise<string> {
  const h = await crypto.subtle.digest('SHA-256', data)
  return [...new Uint8Array(h)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

export interface BinaryFrame { header: Record<string, unknown>; payload: Blob }
/** V65: what the hello said — `first` on the first connect, else the missed frames were replayed (`replayed`) or are gone (`gap`). */
export interface HelloInfo { first: boolean; replayed: number; gap: boolean }

/** `/events` with reconnect; JSON frames → onEvent, binary previews → onBinary. V65: the socket remembers the last frame it applied and
 *  the hub's run; a reconnect's auth names them, and the hello's `recent` (the frames missed meanwhile) goes through onEvent in order
 *  before anything live — or `gap` says they are gone, and onHello's caller fetches. */
export class EventsSocket {
  private ws: WebSocket | null = null
  private closed = false
  private backoff = 500
  private lastSeq = 0
  private run: string | null = null
  private onEvent: (f: EventFrame) => void
  private onBinary: (f: BinaryFrame) => void
  private onStatus: (s: 'open' | 'closed') => void
  private onHello: ((h: HelloInfo) => void) | undefined
  constructor(onEvent: (f: EventFrame) => void, onBinary: (f: BinaryFrame) => void, onStatus: (s: 'open' | 'closed') => void, onHello?: (h: HelloInfo) => void) {
    this.onEvent = onEvent; this.onBinary = onBinary; this.onStatus = onStatus; this.onHello = onHello
  }

  /** The last seq applied (0 before any frame). */
  get since(): number { return this.lastSeq }

  private deliver(f: EventFrame): void {
    if (typeof f.seq === 'number' && f.seq > this.lastSeq) this.lastSeq = f.seq
    this.onEvent(f)
  }

  connect(): void {
    if (!backend || this.closed) return
    const token = backend.token
    const ws = new WebSocket(`ws://${backend.host}:${backend.port}/events`)       // D67: no credential in the URL
    ws.binaryType = 'arraybuffer'
    this.ws = ws
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'auth', token, ...(this.lastSeq ? { since: this.lastSeq, run: this.run } : {}) }))   // V65: what this client last saw
      this.backoff = 500
      this.onStatus('open')
    }
    ws.onmessage = (ev) => {
      if (typeof ev.data === 'string') {
        let f: EventFrame | { type: 'pong' }
        try { f = JSON.parse(ev.data) as EventFrame | { type: 'pong' } } catch { return }   // one bad frame must not take the app down
        if (f.type === 'pong') return
        if (f.type === 'hello') {                                               // V65: the frames missed while the socket was down, in order
          const d = f.data as unknown as { run?: string; recent?: EventFrame[]; gap?: boolean }
          const first = this.run === null
          const recent = Array.isArray(d.recent) ? d.recent : []
          this.onEvent(f)
          for (const r of recent) this.deliver(r)
          this.run = typeof d.run === 'string' ? d.run : this.run
          if (typeof f.seq === 'number' && f.seq > this.lastSeq) this.lastSeq = f.seq   // a gap: the fetch covers everything before the hello
          this.onHello?.({ first, replayed: recent.length, gap: !!d.gap })
          return
        }
        this.deliver(f)
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
