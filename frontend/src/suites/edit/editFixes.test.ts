// The review of 2026-10-27: V90 — an all-zero selection is no selection (a subtract or intersect with nothing selected, a Quick Mask left
// with nothing painted, used to leave one that showed no ants while every verb did nothing until Esc); V95 — the two-minute autosave
// never writes a half-painted stroke (it waits while a gesture is under way).
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import { useSession } from '../../store/session'

vi.mock('./layerPixels', async (importOriginal) => {
  const real = await importOriginal<typeof import('./layerPixels')>()
  /** A canvas-less LayerPixels: its pixels as one RGBA array the 2D-context verbs the selection helpers use read and write. */
  class FakePixels {
    width: number; height: number; grey: boolean; dirty = false; version = 1
    data: Uint8ClampedArray
    readonly canvas = {} as HTMLCanvasElement
    readonly ctx: CanvasRenderingContext2D
    constructor(width: number, height: number, grey = false) {
      this.width = width; this.height = height; this.grey = grey
      this.data = new Uint8ClampedArray(width * height * 4)
      const self = this  // eslint-disable-line @typescript-eslint/no-this-alias
      this.ctx = {
        drawImage: () => undefined,
        getImageData: () => ({ data: self.data, width, height }),
        createImageData: (w: number, h: number) => ({ data: new Uint8ClampedArray(w * h * 4), width: w, height: h }),
        putImageData: (img: { data: Uint8ClampedArray }) => { self.data.set(img.data) },
      } as unknown as CanvasRenderingContext2D
    }
    static fromRaw(width: number, height: number, _bytes: Uint8Array, channels: 1 | 4) { return new FakePixels(width, height, channels === 1) }
    refresh() { this.version++ }
    destroy() { /* nothing on the GPU */ }
  }
  return { ...real, LayerPixels: FakePixels }
})

import { ensureEditorAutosave, setInteracting, useEditor, type DocumentStack } from './editorStore'

const stack = (): DocumentStack => ({ schema_version: 1, id: 'doc_1', name: 'Doc', w: 8, h: 8, background: 'transparent', revision: 1, source_asset_id: null, meta: {},
  layers: [{ kind: 'raster', id: 'a', name: 'a', opacity: 1, blend: 'normal', visible: true, locked: false, clip: false, mask: null, x: 0, y: 0, w: 8, h: 8 }] } as unknown as DocumentStack)

describe('editor fixes', () => {
  beforeEach(() => {
    vi.stubGlobal('ImageData', class {                                                        // jsdom has none; the tile snapshots make them
      data: Uint8ClampedArray; width: number; height: number
      constructor(a: Uint8ClampedArray | number, b: number, c?: number) {
        if (typeof a === 'number') { this.width = a; this.height = b; this.data = new Uint8ClampedArray(a * b * 4) }
        else { this.data = a; this.width = b; this.height = c ?? a.length / 4 / b }
      }
    })
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 200, headers: { 'content-type': 'application/json' } })))
    setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
    useSession.setState({ toasts: [] })
    useEditor.setState({ doc: stack(), pixels: new Map(), masks: new Map(), selection: null, quickMask: false, history: [], future: [], revision: 0 })
  })
  afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })

  it('V90: a subtract or intersect with nothing selected, or one that empties the selection, leaves no selection', () => {
    const all = new Uint8Array(64).fill(255)
    const ed = useEditor.getState()
    ed.applySelectionShape(all, 'subtract', 'test')
    expect(useEditor.getState().selection).toBeNull()
    ed.applySelectionShape(all, 'intersect', 'test')
    expect(useEditor.getState().selection).toBeNull()
    ed.applySelectionShape(all, 'replace', 'test')
    expect(useEditor.getState().selection).not.toBeNull()
    expect(useEditor.getState().history.at(-1)?.sel).toEqual({ had: false, has: true })
    ed.applySelectionShape(all, 'subtract', 'test')                                           // everything taken away
    expect(useEditor.getState().selection).toBeNull()
    expect(useEditor.getState().history.at(-1)?.sel).toEqual({ had: true, has: false })
    useEditor.setState({ quickMask: true })
    useEditor.getState().ensureSelection()                                                    // Quick Mask entered, nothing painted …
    expect(useEditor.getState().selection).not.toBeNull()
    useEditor.getState().setView({ quickMask: false })                                        // … and left
    expect(useEditor.getState().selection).toBeNull()
  })

  it('V95: the autosave waits while a gesture is under way', () => {
    vi.useFakeTimers()
    const save = vi.fn(async () => undefined)
    useEditor.setState({ docDirty: true, saving: false, save } as never)
    ensureEditorAutosave()
    setInteracting(true)
    vi.advanceTimersByTime(120_000)
    expect(save).not.toHaveBeenCalled()
    setInteracting(false)
    vi.advanceTimersByTime(120_000)
    expect(save).toHaveBeenCalledWith({ quiet: true })
  })
})
