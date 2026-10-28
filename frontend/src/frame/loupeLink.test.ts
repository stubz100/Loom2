// D155: the detachable loupe's link — what is followed, the second window's URL, the popup in a browser and the channel's messages.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { detachedUrl, followedAsset, loupeChannel, onLoupe, openDetached, postLoupe, resetLoupeChannel } from './loupeLink'

class FakeChannel {
  static all: FakeChannel[] = []
  name: string; closed = false; handlers: ((e: MessageEvent) => void)[] = []
  constructor(name: string) { this.name = name; FakeChannel.all.push(this) }
  postMessage(m: unknown) { for (const c of FakeChannel.all) if (c !== this && c.name === this.name && !c.closed) for (const h of c.handlers) h({ data: m } as MessageEvent) }
  addEventListener(_: string, h: (e: MessageEvent) => void) { this.handlers.push(h) }
  removeEventListener(_: string, h: (e: MessageEvent) => void) { this.handlers = this.handlers.filter((x) => x !== h) }
  close() { this.closed = true }
}

beforeEach(() => { FakeChannel.all = []; vi.stubGlobal('BroadcastChannel', FakeChannel); resetLoupeChannel() })
afterEach(() => { vi.unstubAllGlobals(); resetLoupeChannel() })

describe('the detachable loupe (D155)', () => {
  it('follows the loupe, else the primary selection', () => {
    expect(followedAsset('a', 'b')).toBe('a')
    expect(followedAsset(null, 'b')).toBe('b')
    expect(followedAsset(undefined, null)).toBeNull()
  })
  it('the second window gets this page with view=loupe, the asset and the browser mode\'s token / port / theme', () => {
    const loc = { origin: 'http://127.0.0.1:1420', pathname: '/', search: '?token=t&port=8766&suite=catalogue&theme=light' }
    expect(detachedUrl('ast_1', loc)).toBe('http://127.0.0.1:1420/?view=loupe&token=t&port=8766&theme=light&asset=ast_1')
    expect(detachedUrl(null, { origin: 'http://tauri.localhost', pathname: '/', search: '' })).toBe('http://tauri.localhost/?view=loupe')
  })
  it('in a browser the window opens once as a popup; a second press focuses it and shows the asset over the channel', async () => {
    const win = { closed: false, focus: vi.fn() }
    const open = vi.fn<(url?: string | URL, target?: string, features?: string) => Window | null>(() => win as unknown as Window)
    vi.stubGlobal('open', open)
    const other = new FakeChannel('loom2-loupe')
    const seen: unknown[] = []
    other.addEventListener('message', (e) => seen.push(e.data))
    await openDetached('ast_1')
    expect(open).toHaveBeenCalledTimes(1)
    expect(String(open.mock.calls[0][0])).toContain('view=loupe')
    expect(String(open.mock.calls[0][0])).toContain('asset=ast_1')
    expect(open.mock.calls[0][2]).toContain('popup')
    await openDetached('ast_2')
    expect(open).toHaveBeenCalledTimes(1)
    expect(win.focus).toHaveBeenCalled()
    expect(seen).toEqual([{ type: 'show', assetId: 'ast_2' }])
    win.closed = true
    await openDetached('ast_3')
    expect(open).toHaveBeenCalledTimes(2)
  })
  it('the channel carries hello / show / closed between the windows and a listener can leave', () => {
    const main = loupeChannel()!
    const detached = new FakeChannel('loom2-loupe')
    const got: unknown[] = []
    detached.addEventListener('message', (e) => got.push(e.data))
    postLoupe({ type: 'show', assetId: 'ast_9' })
    expect(got).toEqual([{ type: 'show', assetId: 'ast_9' }])
    const heard: unknown[] = []
    const off = onLoupe((m) => heard.push(m))
    detached.postMessage({ type: 'hello' })
    off()
    detached.postMessage({ type: 'closed' })
    expect(heard).toEqual([{ type: 'hello' }])
    expect(main.name).toBe('loom2-loupe')
  })
})
