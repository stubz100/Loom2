// V65 (review 2026-10-27): EventsSocket remembers the last frame it applied and the hub's run; a reconnect's auth names them, and the
// hello's `recent` (the frames missed meanwhile) goes through onEvent in order before anything live — or `gap` says they are gone.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { EventsSocket, setBackend, type HelloInfo } from './client'
import type { EventFrame } from './types'

class FakeSocket {
  static instances: FakeSocket[] = []
  sent: string[] = []
  binaryType = ''
  onopen: (() => void) | null = null
  onmessage: ((ev: { data: string | ArrayBuffer }) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  url: string
  constructor(url: string) { this.url = url; FakeSocket.instances.push(this) }
  send(s: string) { this.sent.push(s) }
  close() { this.onclose?.() }
  /** The server's side: a JSON frame arrives. */
  frame(f: unknown) { this.onmessage?.({ data: JSON.stringify(f) }) }
}

const frame = (seq: number, type = 'asset.updated') => ({ seq, type, t: 0, data: { seq } })

let events: EventFrame[]
let hellos: HelloInfo[]
let status: string[]

beforeEach(() => {
  vi.useFakeTimers()
  FakeSocket.instances = []
  vi.stubGlobal('WebSocket', FakeSocket)
  setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
  events = []; hellos = []; status = []
})
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })

const open = () => {
  const s = new EventsSocket((f) => events.push(f), () => undefined, (st) => status.push(st), (h) => hellos.push(h))
  s.connect()
  const ws = FakeSocket.instances.at(-1)!
  ws.onopen?.()
  return { s, ws }
}

describe('EventsSocket replay (V65)', () => {
  it('a first connect names nothing; the frames seen set what the next auth names', () => {
    const { s, ws } = open()
    expect(JSON.parse(ws.sent[0])).toEqual({ type: 'auth', token: 't' })
    ws.frame({ seq: 0, type: 'hello', t: 0, data: { version: 'x', run: 'r1', recent: [], gap: false } })
    expect(hellos).toEqual([{ first: true, replayed: 0, gap: false }])
    ws.frame(frame(1)); ws.frame(frame(2)); ws.frame(frame(3))
    ws.frame({ type: 'pong' })
    expect(events.map((f) => f.seq)).toEqual([0, 1, 2, 3])
    expect(s.since).toBe(3)
    ws.close()                                                              // the orchestrator went away …
    expect(status).toEqual(['open', 'closed'])
    vi.advanceTimersByTime(500)                                             // … and the socket comes back
    const ws2 = FakeSocket.instances.at(-1)!
    expect(ws2).not.toBe(ws)
    ws2.onopen?.()
    expect(JSON.parse(ws2.sent[0])).toEqual({ type: 'auth', token: 't', since: 3, run: 'r1' })
  })

  it('the hello’s recent frames are delivered in order before live ones, and onHello says how many', () => {
    const { s, ws } = open()
    ws.frame({ seq: 0, type: 'hello', t: 0, data: { version: 'x', run: 'r1', recent: [], gap: false } })
    ws.frame(frame(1)); ws.frame(frame(2))
    ws.close(); vi.advanceTimersByTime(500)
    const ws2 = FakeSocket.instances.at(-1)!
    ws2.onopen?.()
    ws2.frame({ seq: 5, type: 'hello', t: 0, data: { version: 'x', run: 'r1', recent: [frame(3), frame(4), frame(5)], gap: false } })
    ws2.frame(frame(6))
    expect(events.map((f) => f.seq)).toEqual([0, 1, 2, 5, 3, 4, 5, 6])    // the hello recorded, then the missed three, then live
    expect(events.map((f) => f.type)).toEqual(['hello', 'asset.updated', 'asset.updated', 'hello', 'asset.updated', 'asset.updated', 'asset.updated', 'asset.updated'])
    expect(hellos.at(-1)).toEqual({ first: false, replayed: 3, gap: false })
    expect(s.since).toBe(6)
  })

  it('a gap: nothing replayed, the hello’s seq becomes the last seen (the fetch covers the rest)', () => {
    const { s, ws } = open()
    ws.frame({ seq: 0, type: 'hello', t: 0, data: { version: 'x', run: 'r1', recent: [], gap: false } })
    ws.frame(frame(1))
    ws.close(); vi.advanceTimersByTime(500)
    const ws2 = FakeSocket.instances.at(-1)!
    ws2.onopen?.()
    ws2.frame({ seq: 2, type: 'hello', t: 0, data: { version: 'x', run: 'r2', recent: [], gap: true } })   // another run of the orchestrator
    expect(hellos.at(-1)).toEqual({ first: false, replayed: 0, gap: true })
    expect(s.since).toBe(2)
    ws2.close(); vi.advanceTimersByTime(1000)
    const ws3 = FakeSocket.instances.at(-1)!
    ws3.onopen?.()
    expect(JSON.parse(ws3.sent[0])).toEqual({ type: 'auth', token: 't', since: 2, run: 'r2' })   // the new run is what it names now
  })
})
