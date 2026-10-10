// The PixiJS stage for the Edit suite (10 §2, 05 §3b): one Application rendered on demand, a world container
// with the document's layers as sprites (masks and isolated groups through render-texture passes, exact W3C blend
// shaders, adjustment/filter layers as per-layer filters), the selection's marching ants, the free-transform
// box, a checkerboard, and the pointer handling for the tools (brush, eraser, move/transform, hand, zoom,
// marquee, lasso, wand, fill, eyedropper).
import { Application, ColorMatrixFilter, Container, Graphics, Matrix, Rectangle, RendererType, RenderTexture, Sprite, Texture, TilingSprite } from 'pixi.js'
import 'pixi.js/advanced-blend-modes'
import { useEffect, useRef } from 'react'
import { useSession } from '../../store/session'
import { CANVAS_COLOURS } from '../../frame/theme'
import { showMenu } from '../../frame/ContextMenu'
import { ensureAdjustment } from './adjustFilters'
import { blendName, OPAQUE_BLEND } from './blendModes'
import { canvasMenu } from './editCommands'
import { findNode, useEditor, type MaskRef, type Node } from './editorStore'
import { derivedMask, maskParamsActive, outsideValue } from './maskDerived'
import { useAiPanel } from './aiPanelStore'
import { lumaOf, selectionAlphaCanvas, setPartialUpload, type LayerPixels } from './layerPixels'
import { PathWalker, Smoother, Stroke } from './brushEngine'
import { modeFor, selectionValues, type SelectionMode } from './selectionOps'
import { corners, handles, insideQuad, toLocal, type Xform } from './transform'
import { assetIds, onlyAssets, registerDropTarget } from '../../frame/drag'
import { listenFileDrop } from '../../shell/tauri'

/** Inverts RGB (keeps alpha) and adds: red where a mask/selection is black, nothing where it is white. */
function negativeAdd(): ColorMatrixFilter { const f = new ColorMatrixFilter(); f.negative(false); f.blendMode = 'add'; return f }

function checkerTexture(): Texture {
  const c = document.createElement('canvas'); c.width = c.height = 16
  const ctx = c.getContext('2d')!
  const { checkerA, checkerB } = CANVAS_COLOURS[useSession.getState().ui.theme]           // transparency checker follows the theme
  ctx.fillStyle = checkerA; ctx.fillRect(0, 0, 16, 16)
  ctx.fillStyle = checkerB; ctx.fillRect(0, 0, 8, 8); ctx.fillRect(8, 8, 8, 8)
  return Texture.from(c)
}

/** Axis-aligned boundary runs of the selection (value > 127), as [x0, y0, x1, y1, …] in document pixels. */
function outlineSegments(sel: LayerPixels): number[] {
  const W = sel.width, H = sel.height
  const d = selectionValues(sel)
  const inside = (x: number, y: number) => x >= 0 && y >= 0 && x < W && y < H && d[y * W + x] > 127
  const segs: number[] = []
  for (let y = 0; y <= H; y++) {
    let run = -1
    for (let x = 0; x <= W; x++) {
      const edge = x < W && inside(x, y) !== inside(x, y - 1)
      if (edge && run < 0) run = x
      if (!edge && run >= 0) { segs.push(run, y, x, y); run = -1 }
    }
  }
  for (let x = 0; x <= W; x++) {
    let run = -1
    for (let y = 0; y <= H; y++) {
      const edge = y < H && inside(x, y) !== inside(x - 1, y)
      if (edge && run < 0) run = y
      if (!edge && run >= 0) { segs.push(x, run, x, y); run = -1 }
    }
  }
  return segs
}

type Pt = { x: number; y: number }
/** D51: where the last stroke ended (document coordinates) and on which target — Shift-click continues from it. */
let lastPaint: { id: string; at: Pt } | null = null
/** Overlay Graphics that live across scene rebuilds (cleared and redrawn in place); everything else in the overlay is rebuilt. */
const OVERLAY_GRAPHICS = ['frame', 'ants', 'aiprompt', 'gguide', 'xform', 'preview']

export function EditorCanvas() {
  const hostRef = useRef<HTMLDivElement>(null)
  const appRef = useRef<Application | null>(null)
  const worldRef = useRef<Container | null>(null)
  const layersRef = useRef<Container | null>(null)
  const overlayRef = useRef<Container | null>(null)
  const spritesRef = useRef<Map<string, Sprite | Container>>(new Map())
  const passesRef = useRef<{ rt: RenderTexture; content: Container; transform: Matrix; dirty: boolean }[]>([])
  const derivedRef = useRef<{ raw: LayerPixels; ref: MaskRef; sprite: Sprite }[]>([])   // D52: mask sprites showing a derived mask
  const renderPending = useRef(0)
  const antsRef = useRef<{ rev: number; segs: number[] }>({ rev: -1, segs: [] })
  const negRef = useRef<ColorMatrixFilter[] | null>(null)              // C21: the two overlay filters are made once, not per rebuild
  const phaseRef = useRef(0)
  /** Render every dirty pass (inner passes were pushed first, so nesting resolves bottom-up). */
  const renderPasses = () => {
    const app = appRef.current
    if (!app) return
    for (const p of passesRef.current) {
      if (!p.dirty) continue
      // clearColor must be explicit: the default is the renderer background (opaque), not transparent
      app.renderer.render({ container: p.content, target: p.rt, clear: true, clearColor: [0, 0, 0, 0], transform: p.transform })
      p.dirty = false
    }
  }
  const markPassesDirty = () => { for (const p of passesRef.current) p.dirty = true }
  /** D52: re-derive the feathered / density masks whose raw pixels changed (a stroke on the mask) before the passes render. */
  const refreshDerived = () => { for (const d of derivedRef.current) { const t = derivedMask(d.raw, d.ref).texture; if (d.sprite.texture !== t) d.sprite.texture = t } }
  /** On-demand rendering (10 §11): one frame on the next animation frame, nothing while idle. A request made before the
   * renderer exists is dropped (init renders once itself), so a cancelled frame can never leave the flag set. */
  const requestRender = () => {
    if (!appRef.current) return
    if (renderPending.current) return
    const run = () => {
      renderPending.current = 0
      const t0 = performance.now()
      refreshDerived(); renderPasses(); appRef.current?.render()
      ;(window as unknown as { __loom2RenderMs?: number }).__loom2RenderMs = performance.now() - t0    // read by edit_headed_check.py perf
    }
    renderPending.current = requestAnimationFrame(run)
  }
  const cancelPendingRender = () => { if (renderPending.current) cancelAnimationFrame(renderPending.current); renderPending.current = 0 }
  const doc = useEditor((s) => s.doc)
  const revision = useEditor((s) => s.revision)
  const fitRequested = useEditor((s) => s.fitRequested)
  const zoom = useEditor((s) => s.zoom)
  const pan = useEditor((s) => s.pan)
  const before = useEditor((s) => s.before)
  const overlay = useEditor((s) => s.overlay)
  const quickMask = useEditor((s) => s.quickMask)
  const editingMask = useEditor((s) => s.editingMask)
  const maskView = useEditor((s) => s.maskView)
  const activeId = useEditor((s) => s.activeId)
  const pixelGrid = useEditor((s) => s.pixelGrid)
  const hasSel = useEditor((s) => !!s.selection)
  const transform = useEditor((s) => s.transform)

  // ---- overlay drawers (marching ants, transform box) ------------------------------------------------
  const drawAnts = () => {
    const ov = overlayRef.current; if (!ov) return
    let g = ov.getChildByLabel('ants') as Graphics | null
    if (!g) { g = new Graphics(); g.label = 'ants'; ov.addChild(g) }
    g.clear()
    const st = useEditor.getState()
    const segs = antsRef.current.segs
    if (!st.selection || !st.overlay || st.quickMask || !segs.length) return
    const z = st.zoom, w = 1 / z
    for (let i = 0; i < segs.length; i += 4) g.moveTo(segs[i], segs[i + 1]).lineTo(segs[i + 2], segs[i + 3])
    g.stroke({ color: 0xffffff, width: w, alpha: 0.95 })
    const dash = 4 / z, period = dash * 2, off = (phaseRef.current % 8) / 8 * period
    for (let i = 0; i < segs.length; i += 4) {
      const x0 = segs[i], y0 = segs[i + 1], x1 = segs[i + 2], y1 = segs[i + 3]
      const len = Math.abs(x1 - x0) + Math.abs(y1 - y0)
      const dx = Math.sign(x1 - x0), dy = Math.sign(y1 - y0)
      for (let s = off - period; s < len; s += period) {
        const a = Math.max(0, s), b = Math.min(len, s + dash)
        if (b <= a) continue
        g.moveTo(x0 + dx * a, y0 + dy * a).lineTo(x0 + dx * b, y0 + dy * b)
      }
    }
    g.stroke({ color: 0x000000, width: w })
  }
  /** AI Select prompts (A tool): include points green, exclude points red, the box amber; `live` is the box being dragged. */
  const drawAiPrompt = (live?: { start: Pt; last: Pt }) => {
    const ov = overlayRef.current
    if (!ov) return
    let g = ov.getChildByLabel('aiprompt') as Graphics | null
    if (!g) { g = new Graphics(); g.label = 'aiprompt'; ov.addChild(g) }
    g.clear()
    const st = useEditor.getState()
    const z = Math.max(st.zoom, 0.01)
    const r = 5 / z
    for (const q of st.aiPrompt.points) {
      g.circle(q.x, q.y, r).fill({ color: q.label ? 0x3ddc84 : 0xff4d4d, alpha: 0.9 }).stroke({ color: 0x000000, width: 1.5 / z, alpha: 0.8 })
    }
    const box = live ? [Math.min(live.start.x, live.last.x), Math.min(live.start.y, live.last.y), Math.max(live.start.x, live.last.x), Math.max(live.start.y, live.last.y)] : st.aiPrompt.box
    if (box) g.rect(box[0], box[1], box[2] - box[0], box[3] - box[1]).stroke({ color: 0xf2a93b, width: 1.5 / z })
    requestRender()
  }
  /** Gradient guide line while dragging the G tool; called without arguments to clear it. */
  const drawGuide = (a?: Pt, b?: Pt) => {
    const ov = overlayRef.current
    if (!ov) return
    let g = ov.getChildByLabel('gguide') as Graphics | null
    if (!g) { g = new Graphics(); g.label = 'gguide'; ov.addChild(g) }
    g.clear()
    if (a && b) { const z = Math.max(useEditor.getState().zoom, 0.01); g.moveTo(a.x, a.y).lineTo(b.x, b.y).stroke({ color: 0xffffff, width: 1 / z, alpha: 0.9 }); g.circle(a.x, a.y, 4 / z).fill(0xffffff); g.circle(b.x, b.y, 4 / z).fill(0x111111).stroke({ color: 0xffffff, width: 1 / z }) }
    requestRender()
  }
  const drawTransformBox = () => {
    const ov = overlayRef.current; if (!ov) return
    let g = ov.getChildByLabel('xform') as Graphics | null
    if (!g) { g = new Graphics(); g.label = 'xform'; ov.addChild(g) }
    g.clear()
    const st = useEditor.getState(); const t = st.transform
    if (!t) return
    const z = st.zoom, hs = 5 / z
    g.poly(corners(t).flatMap((p) => [p.x, p.y]), true).stroke({ color: 0xf0a63a, width: 1 / z })
    for (const p of handles(t)) g.rect(p.x - hs, p.y - hs, hs * 2, hs * 2).fill(0xffffff).stroke({ color: 0x000000, width: 1 / z })
    g.circle(t.cx, t.cy, 3 / z).stroke({ color: 0xf0a63a, width: 1 / z })
  }
  const applyTransformPreview = () => {
    const t = useEditor.getState().transform
    if (!t) return
    const obj = spritesRef.current.get(t.nodeId)
    if (!obj) return
    obj.pivot.set(t.w / 2, t.h / 2)
    obj.position.set(t.cx, t.cy)
    obj.scale.set(t.sx, t.sy)
    obj.rotation = t.rot
    markPassesDirty()                                                      // the layer may sit inside a pass (clip run, mask)
  }

  // ---- app lifecycle --------------------------------------------------------------------------
  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    let cancelled = false
    let ro: ResizeObserver | null = null
    let unsubTheme: (() => void) | null = null
    const devOverride = import.meta.env.DEV ? new URLSearchParams(location.search).get('renderer') : null      // dev deep link: &renderer=webgl|webgpu
    const pref = useEditor.getState().rendererPref
    const want: 'webgpu' | 'webgl' = devOverride === 'webgl' || (devOverride !== 'webgpu' && pref === 'webgl') ? 'webgl' : 'webgpu'
    const boot = async (preference: 'webgpu' | 'webgl') => {
      const a = new Application()
      await a.init({ preference, background: CANVAS_COLOURS[useSession.getState().ui.theme].background, antialias: false, resolution: window.devicePixelRatio || 1, autoDensity: true, resizeTo: host, powerPreference: 'high-performance', autoStart: false })
      return a
    }
    /** D3 fallback probe: draw a white 4×4 sprite and read it back through the path the exact-compare uses. A renderer
     * that initialises but yields no pixels (WebGPU in some WebView2 / headless contexts) is swapped for WebGL2. */
    const rendersPixels = (a: Application): boolean => {
      const src = document.createElement('canvas'); src.width = src.height = 4
      const sx = src.getContext('2d')!; sx.fillStyle = '#ffffff'; sx.fillRect(0, 0, 4, 4)
      const probe = new Container(); probe.addChild(new Sprite(Texture.from(src)))
      try {
        const out = a.renderer.extract.canvas({ target: probe, frame: new Rectangle(0, 0, 4, 4), resolution: 1 }) as HTMLCanvasElement
        const c = document.createElement('canvas'); c.width = c.height = 4
        const cx = c.getContext('2d')!; cx.drawImage(out, 0, 0)
        const d = cx.getImageData(1, 1, 1, 1).data
        return d[0] > 200 && d[3] > 200
      } catch { return false } finally { probe.destroy({ children: true, texture: true, textureSource: true }) }
    }
    void (async () => {
      let app: Application
      let fellBack = false
      try {
        app = await boot(want)
        const skipProbe = import.meta.env.DEV && new URLSearchParams(location.search).get('probe') === '0'   // dev deep link for bisecting
        if (!cancelled && !skipProbe && want === 'webgpu' && pref === 'auto' && app.renderer.type === RendererType.WEBGPU && !rendersPixels(app)) {
          app.destroy(true)
          if (cancelled) return
          app = await boot('webgl'); fellBack = true
        }
      } catch (e) {
        if (!cancelled) useSession.getState().toast(`The editor's renderer could not start: ${(e as Error).message}`, 'error')
        return
      }
      if (cancelled) { app.destroy(true); return }
      host.replaceChildren(app.canvas)
      app.canvas.style.touchAction = 'none'
      const world = new Container()
      const checker = new TilingSprite({ texture: checkerTexture(), width: 10, height: 10 })
      checker.label = 'checker'
      const layers = new Container()
      const overlayC = new Container()
      world.addChild(checker, layers, overlayC)
      app.stage.addChild(world)
      appRef.current = app; worldRef.current = world; layersRef.current = layers; overlayRef.current = overlayC
      if (import.meta.env.DEV) { const w = window as unknown as { __loom2App?: Application; __loom2Editor?: typeof useEditor }; w.__loom2App = app; w.__loom2Editor = useEditor }      // dev: inspect / drive the editor from DevTools or the headed check
      const kind = app.renderer.type === RendererType.WEBGPU ? 'WebGPU' : app.renderer.type === RendererType.WEBGL ? 'WebGL2' : 'canvas'
      useEditor.getState().setRenderer(fellBack ? `${kind} (fallback)` : kind)
      if (fellBack) useSession.getState().toast('WebGPU initialised but drew nothing here — the editor is using WebGL2 (the renderer badge in the strip switches)', 'info')
      // D53: sub-region texture uploads for strokes, done the way Pixi uploads a canvas (premultiplied on upload), for the changed rect
      setPartialUpload((lp, x0, y0, x1, y1) => {
        const source = lp.texture.source as unknown as { alphaMode?: string }
        const premultiplied = source.alphaMode === 'premultiply-alpha-on-upload'
        const w = x1 - x0, h = y1 - y0
        if (app.renderer.type === RendererType.WEBGPU) {
          const r = app.renderer as unknown as { texture: { getGpuSource: (s: unknown) => GPUTexture }; gpu: { device: GPUDevice } }
          const tex = r.texture.getGpuSource(lp.texture.source)
          r.gpu.device.queue.copyExternalImageToTexture({ source: lp.canvas, origin: { x: x0, y: y0 } }, { texture: tex, origin: { x: x0, y: y0 }, premultipliedAlpha: premultiplied }, { width: w, height: h })
          return true
        }
        const r = app.renderer as unknown as { gl: WebGL2RenderingContext; texture: { getGlSource: (s: unknown) => { texture: WebGLTexture; format: number; type: number; target: number }; _premultiplyAlpha: boolean; _activeTextureLocation: number; _setBoundTexture: (loc: number, s: unknown) => void } }
        const gl = r.gl
        const glTex = r.texture.getGlSource(lp.texture.source)
        gl.bindTexture(glTex.target, glTex.texture)
        r.texture._setBoundTexture(r.texture._activeTextureLocation, lp.texture.source)             // keep Pixi's binding cache true
        if (r.texture._premultiplyAlpha !== premultiplied) { r.texture._premultiplyAlpha = premultiplied; gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, premultiplied) }
        gl.texSubImage2D(glTex.target, 0, x0, y0, w, h, glTex.format, glTex.type, lp.ctx.getImageData(x0, y0, w, h))
        return true
      })
      useEditor.getState().setExtractor(() => {
        const d = useEditor.getState().doc
        if (!d || !layersRef.current) return null
        // extract.canvas() may hand back a WebGPU/bitmap canvas (no 2D context); redraw it into a plain 2D canvas,
        // which also leaves the browser to convert premultiplied → straight alpha
        refreshDerived(); markPassesDirty(); renderPasses()
        const src = app.renderer.extract.canvas({ target: layersRef.current, frame: new Rectangle(0, 0, d.w, d.h), resolution: 1 }) as HTMLCanvasElement
        const c = document.createElement('canvas'); c.width = d.w; c.height = d.h
        c.getContext('2d')!.drawImage(src, 0, 0)
        return c
      })
      ro = new ResizeObserver(() => { app.renderer.resize(host.clientWidth, host.clientHeight); requestRender() })
      unsubTheme = useSession.subscribe((s, p) => {                    // Settings › Theme while a document is open
        if (s.ui.theme === p.ui.theme) return
        app.renderer.background.color = CANVAS_COLOURS[s.ui.theme].background
        const old = checker.texture; checker.texture = checkerTexture(); old.destroy(true)
        requestRender()
      })
      ro.observe(host)
      useEditor.getState().bump()                                      // re-run the scene effects now that the renderer exists
      useEditor.getState().requestFit()
      requestRender()
    })()
    return () => {
      cancelled = true
      ro?.disconnect()
      unsubTheme?.()
      cancelPendingRender()                                              // and clear the flag: a stale id blocked every later request (2026-10-06)
      useEditor.getState().setExtractor(null)
      setPartialUpload(null)
      for (const p of passesRef.current) { p.content.destroy({ children: true }); p.rt.destroy(true) }
      passesRef.current = []
      negRef.current?.forEach((f) => f.destroy()); negRef.current = null
      appRef.current?.destroy(true, { children: true }); appRef.current = null
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ---- scene sync (doc stack → sprites) -------------------------------------------------------
  useEffect(() => {
    const layers = layersRef.current, world = worldRef.current
    if (!layers || !world || !doc) { layers?.removeChildren(); return }
    const st = useEditor.getState()
    const checker = world.getChildByLabel('checker') as TilingSprite | null
    if (checker) { checker.width = doc.w; checker.height = doc.h; checker.visible = doc.background === 'transparent' }
    for (const c of layers.removeChildren()) c.destroy({ children: true })   // C21: sprites, mask wrappers and the background rect go; the LayerPixels textures stay
    spritesRef.current.clear()
    if (doc.background !== 'transparent') {
      const g = new Graphics().rect(0, 0, doc.w, doc.h).fill(doc.background)
      layers.addChild(g)
    }
    const activeNode = findNode(doc, st.activeId)
    for (const p of passesRef.current) { p.content.destroy({ children: true }); p.rt.destroy(true) }   // C21: pass content containers too
    passesRef.current = []
    derivedRef.current = []
    let lastBlend = ''                                                   // alternate names so equal modes never batch
    const pickBlend = (mode: string) => { const a = blendName(mode, false); const name = a === lastBlend ? blendName(mode, true) : a; lastBlend = name; return name }
    const setBlend = (obj: Container, name: string) => { (obj as unknown as { blendMode: string }).blendMode = name }
    // Anything that must composite as a unit before its own blend/alpha/mask apply (masked layers, isolated groups, clip runs,
    // pass-through mixes) is rendered into its own RenderTexture (a "pass") each frame it is dirty. Pixi's cacheAsTexture and
    // sprite masks do not give advanced blend filters the right backdrop, measured in the M4 acceptance.
    const makePass = (content: Container, w: number, h: number, tx: number, ty: number): Sprite => {
      const rt = RenderTexture.create({ width: Math.max(1, w), height: Math.max(1, h), resolution: 1, antialias: false })
      passesRef.current.push({ rt, content, transform: new Matrix().translate(-tx, -ty), dirty: true })
      const sp = new Sprite(rt)
      sp.position.set(tx, ty)
      return sp
    }
    /** D52: the sprite showing a node's mask as it renders over the region (bx, by, bw, bh) — derived when density < 1 or feather > 0,
     * re-derived per frame when painted. D54: where the region reaches past the mask's extent and its default is not 0, the mask is
     * first drawn over its default value into a pass of the region's size. */
    const maskSprite = (n: Node, m: LayerPixels, bx: number, by: number, bw: number, bh: number): Sprite => {
      const ref = n.mask!
      const sp = new Sprite(derivedMask(m, ref).texture)
      if (maskParamsActive(ref)) derivedRef.current.push({ raw: m, ref, sprite: sp })
      const ox = (ref.linked ? (n.x ?? 0) : 0) + ref.x, oy = (ref.linked ? (n.y ?? 0) : 0) + ref.y
      sp.position.set(ox, oy)
      const covers = ox <= bx && oy <= by && ox + m.width >= bx + bw && oy + m.height >= by + bh
      if (!(ref.default ?? 0) || covers) return sp
      const v = outsideValue(ref)
      const c = new Container()
      c.addChild(new Graphics().rect(bx, by, bw, bh).fill({ r: v, g: v, b: v }), sp)
      return makePass(c, bw, bh, bx, by)
    }
    /** Wrap `obj` (in document coordinates) with the node's mask into a pass; returns the sprite to blend. */
    const withMask = (n: Node, obj: Container, w: number, h: number, tx: number, ty: number): Container => {
      const m = n.mask?.enabled ? st.masks.get(n.id) : undefined
      if (!m || !n.mask) return obj
      const ms = maskSprite(n, m, tx, ty, w, h)
      const content = new Container()
      content.addChild(ms, obj)
      obj.mask = ms
      return makePass(content, w, h, tx, ty)
    }
    /** The render target a node draws into: its top-first node list, and what lies under that list (the root's background
     * colour, or the copy of the backdrop a pass-through mix starts from). */
    type Target = { nodes: Node[]; underlay: Texture | null; background: string | null }
    const isolated = (nodes: Node[]): Target => ({ nodes, underlay: null, background: null })
    let register = true                                                   // false while building a backdrop copy (no sprite lookups)
    const reg = (id: string, obj: Container) => { if (register) spritesRef.current.set(id, obj) }
    const hidden = (n: Node) => !n.visible || (before && n.id === st.activeId)   // "before": hide the active layer
    const contains = (n: Node, g: Node): boolean => n.kind === 'group' && (n.children ?? []).some((c) => c === g || contains(c, g))
    /** The part of a target's tree drawn before `g` (a pass-through group inside it): the nodes below it, and its ancestors
     * reduced to their children below it. */
    const prefixOf = (list: Node[], g: Node): Node[] => {
      const i = list.findIndex((n) => n === g || contains(n, g))
      if (i < 0) return list
      const below = list.slice(i + 1)
      return list[i] === g ? below : [{ ...list[i], children: prefixOf(list[i].children ?? [], g) }, ...below]
    }
    /** A node's own pixels with its mask, unblended at full opacity (the base of a clip run, D39). */
    const buildContent = (n: Node, parent: Container) => {
      if (n.kind === 'raster') {
        const lp = st.pixels.get(n.id)
        if (!lp) return
        const sp = new Sprite(lp.texture)
        sp.position.set(n.x ?? 0, n.y ?? 0)
        const obj = withMask(n, sp, lp.width, lp.height, n.x ?? 0, n.y ?? 0)
        parent.addChild(obj); reg(n.id, obj)
      } else if (n.kind === 'group') {
        const c = new Container()
        build(n.children ?? [], c, isolated(n.children ?? []))
        const obj = withMask(n, makePass(c, doc.w, doc.h, 0, 0), doc.w, doc.h, 0, 0)
        parent.addChild(obj); reg(n.id, obj)
      }
    }
    const buildNode = (n: Node, parent: Container, target: Target) => {
      if (n.kind === 'raster') {
        const lp = st.pixels.get(n.id)
        if (!lp) return
        const sp = new Sprite(lp.texture)
        sp.position.set(n.x ?? 0, n.y ?? 0)
        const obj = withMask(n, sp, lp.width, lp.height, n.x ?? 0, n.y ?? 0)
        obj.alpha = n.opacity * (n.fill ?? 1)
        setBlend(obj, pickBlend(n.blend))
        parent.addChild(obj); reg(n.id, obj)
      } else if (n.kind === 'group') {
        // compose.py: pass-through when flagged, Normal / Pass Through and not clipped (a clip-run base never gets here)
        const passthrough = (n.passthrough ?? true) && (n.blend === 'normal' || n.blend === 'pass-through') && !n.clip
        if (passthrough && Math.abs(n.opacity - 1) < 1e-6 && !n.mask?.enabled) {
          const c = new Container()
          build(n.children ?? [], c, target)                                 // same target: the children draw onto its backdrop
          parent.addChild(c); reg(n.id, c)
        } else if (passthrough) {
          // D39: below 100 % or masked, the children still composite onto the backdrop and the result is mixed against the
          // original by opacity × mask. L = a copy of everything drawn so far in this target; M = L + the children; M is drawn
          // over the target at the group's opacity (exact over an opaque backdrop, where M is opaque too).
          const lc = new Container()
          if (target.underlay) lc.addChild(new Sprite(target.underlay))
          else if (target.background) lc.addChild(new Graphics().rect(0, 0, doc.w, doc.h).fill(target.background))
          const was = register
          register = false
          build(prefixOf(target.nodes, n), lc, target)
          register = was
          const copy = makePass(lc, doc.w, doc.h, 0, 0)
          const mc = new Container()
          mc.addChild(copy)
          lastBlend = ''
          build(n.children ?? [], mc, { nodes: n.children ?? [], underlay: copy.texture, background: null })
          const obj = withMask(n, makePass(mc, doc.w, doc.h, 0, 0), doc.w, doc.h, 0, 0)
          obj.alpha = n.opacity
          lastBlend = ''
          parent.addChild(obj); reg(n.id, obj)
        } else {
          const c = new Container()
          build(n.children ?? [], c, isolated(n.children ?? []))
          const obj = withMask(n, makePass(c, doc.w, doc.h, 0, 0), doc.w, doc.h, 0, 0)
          obj.alpha = n.opacity
          setBlend(obj, pickBlend(n.blend === 'pass-through' ? 'normal' : n.blend))
          parent.addChild(obj); reg(n.id, obj)
        }
      } else if (n.kind === 'adjustment' || n.kind === 'filter') {
        // a document-sized white sprite (or the layer's mask) carries the layer alpha; the per-layer filter registered as
        // a blend mode rewrites the backdrop in the layer's own blend mode (adjustFilters.ts)
        const m = n.mask?.enabled ? st.masks.get(n.id) : undefined
        const sp = m ? maskSprite(n, m, 0, 0, doc.w, doc.h) : new Sprite(Texture.WHITE)
        if (!m) { sp.width = doc.w; sp.height = doc.h }
        sp.alpha = n.opacity * (n.fill ?? 1)
        setBlend(sp, ensureAdjustment(n))
        lastBlend = ''
        parent.addChild(sp); reg(n.id, sp)
      }
    }
    /** D39 clipping group: pass 1 draws the base opaque (straight colour) and the clipped layers over it with their own
     * blends — "as if the base were opaque"; pass 2 masks that by the base's alpha; the unit then blends with the base's
     * mode and opacity × fill. */
    const buildClipRun = (base: Node, clipped: Node[], parent: Container) => {
      const bc = new Container()
      buildContent(base, bc)
      const opaque = makePass(bc, doc.w, doc.h, 0, 0)
      setBlend(opaque, OPAQUE_BLEND)
      const rc = new Container()
      rc.addChild(opaque)
      lastBlend = OPAQUE_BLEND
      for (const c of clipped) buildNode(c, rc, isolated([]))
      const run = makePass(rc, doc.w, doc.h, 0, 0)
      const shape = new Sprite(opaque.texture)
      const mc = new Container()
      mc.addChild(shape, run)
      run.setMask({ mask: shape, channel: 'alpha' })
      const unit = makePass(mc, doc.w, doc.h, 0, 0)
      unit.alpha = base.opacity * (base.fill ?? 1)
      lastBlend = ''
      setBlend(unit, pickBlend(base.blend === 'pass-through' ? 'normal' : base.blend))
      parent.addChild(unit)
    }
    /** Nodes are top-first (ORA order); Pixi draws children in order, so build bottom-up. A node followed (above) by
     * `clip` nodes forms a clipping group with them; a clipped node with no unclipped node below draws as an ordinary one. */
    const build = (nodes: Node[], parent: Container, target: Target) => {
      const order = nodes.slice().reverse()
      for (let i = 0; i < order.length;) {
        const base = order[i]
        let j = i + 1
        if (!base.clip) while (j < order.length && order[j].clip) j++
        const clipped = order.slice(i + 1, j).filter((c) => !hidden(c))
        i = j
        if (hidden(base)) continue
        if (!clipped.length) buildNode(base, parent, target)
        else if (base.kind === 'adjustment' || base.kind === 'filter') {
          // layers clipped to an adjustment: compose.py composites them atop the adjusted backdrop; the preview draws them
          // over it (the same when the adjustment is at 100 % without a mask over an opaque backdrop)
          buildNode(base, parent, target)
          for (const c of clipped) buildNode(c, parent, target)
        } else buildClipRun(base, clipped, parent)
      }
    }
    build(doc.layers, layers, { nodes: doc.layers, underlay: null, background: doc.background !== 'transparent' ? doc.background : null })
    // selection / quick-mask / mask-editing overlays
    const ov = overlayRef.current!
    for (const child of [...ov.children]) {                                  // C21: keep the labelled Graphics, destroy the sprites
      if (child.label && OVERLAY_GRAPHICS.includes(child.label)) continue
      ov.removeChild(child); child.destroy()
    }
    const neg = negRef.current ?? (negRef.current = [negativeAdd(), negativeAdd()])
    const sel = st.selection
    if (sel && overlay && quickMask) {
      // quick mask: additive red where NOT selected
      const s = new Sprite(sel.texture)
      s.blendMode = 'add'; s.filters = [neg[0]]; s.tint = 0xff2020; s.alpha = 0.5
      ov.addChild(s)
    }
    // D54: Alt-click on a mask thumbnail — the mask alone in grey (its default outside the extent); painting continues on it
    if (maskView === 'gray' && activeNode?.mask) {
      const m = st.masks.get(activeNode.id)
      if (m) {
        const v = activeNode.mask.default ?? 0
        const g = new Graphics().rect(0, 0, doc.w, doc.h).fill({ r: v, g: v, b: v })
        const s = new Sprite(m.texture)
        s.position.set((activeNode.mask.linked ? (activeNode.x ?? 0) : 0) + activeNode.mask.x, (activeNode.mask.linked ? (activeNode.y ?? 0) : 0) + activeNode.mask.y)
        ov.addChild(g, s)
      }
    } else if (editingMask && activeNode?.mask && overlay) {
      const m = st.masks.get(activeNode.id)
      if (m) {
        const s = new Sprite(m.texture)
        s.position.set((activeNode.mask.linked ? (activeNode.x ?? 0) : 0) + activeNode.mask.x, (activeNode.mask.linked ? (activeNode.y ?? 0) : 0) + activeNode.mask.y)
        s.blendMode = 'add'; s.filters = [neg[1]]; s.tint = 0xff2020; s.alpha = 0.45
        ov.addChild(s)
      }
    }
    for (const label of OVERLAY_GRAPHICS.slice(1)) { const g = ov.getChildByLabel(label); if (g) ov.addChild(g) }   // the kept Graphics draw above the sprites, in their old order
    // marching ants: recomputed only when the selection changed (every selection edit bumps the revision)
    if (sel) { if (antsRef.current.rev !== revision) antsRef.current = { rev: revision, segs: outlineSegments(sel) } } else antsRef.current = { rev: -1, segs: [] }
    drawAnts()
    drawAiPrompt()
    applyTransformPreview()
    drawTransformBox()
    requestRender()
  }, [doc, revision, before, overlay, quickMask, editingMask, activeId, maskView]) // eslint-disable-line react-hooks/exhaustive-deps

  // ---- view (zoom / pan / fit), document frame and pixel grid -------------------------------------
  useEffect(() => {
    const world = worldRef.current, app = appRef.current, ov = overlayRef.current, host = hostRef.current
    if (!world || !app) return
    world.scale.set(zoom); world.position.set(pan.x, pan.y)
    if (!ov || !doc || !host) return
    let g = ov.getChildByLabel('frame') as Graphics | null
    if (!g) { g = new Graphics(); g.label = 'frame'; ov.addChildAt(g, 0) }
    g.clear()
    g.rect(0, 0, doc.w, doc.h).stroke({ color: 0x555555, width: 1 / zoom })
    if (pixelGrid && zoom >= 8) {
      const x0 = Math.max(0, Math.floor(-pan.x / zoom)), y0 = Math.max(0, Math.floor(-pan.y / zoom))
      const x1 = Math.min(doc.w, Math.ceil((host.clientWidth - pan.x) / zoom)), y1 = Math.min(doc.h, Math.ceil((host.clientHeight - pan.y) / zoom))
      for (let x = x0; x <= x1; x++) g.moveTo(x, y0).lineTo(x, y1)
      for (let y = y0; y <= y1; y++) g.moveTo(x0, y).lineTo(x1, y)
      g.stroke({ color: 0xffffff, width: 1 / zoom, alpha: 0.15 })
    }
    drawAnts()
    drawAiPrompt()
    drawTransformBox()
    requestRender()
  }, [zoom, pan, revision, pixelGrid, doc]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const app = appRef.current, host = hostRef.current
    if (!app || !host || !doc) return
    const w = host.clientWidth, h = host.clientHeight
    const z = Math.min((w - 40) / doc.w, (h - 40) / doc.h)
    useEditor.getState().setView({ zoom: z, pan: { x: (w - doc.w * z) / 2, y: (h - doc.h * z) / 2 } })
  }, [fitRequested, doc?.id]) // eslint-disable-line react-hooks/exhaustive-deps
  // free-transform preview follows the live numbers
  useEffect(() => { applyTransformPreview(); drawTransformBox(); requestRender() }, [transform]) // eslint-disable-line react-hooks/exhaustive-deps
  // the ants march only while there is a selection to outline (and nothing else renders while idle)
  useEffect(() => {
    if (!hasSel || !overlay || quickMask) return
    const t = setInterval(() => { phaseRef.current = (phaseRef.current + 1) % 8; drawAnts(); requestRender() }, 120)
    return () => clearInterval(t)
  }, [hasSel, overlay, quickMask]) // eslint-disable-line react-hooks/exhaustive-deps

  // ---- input ----------------------------------------------------------------------------------------
  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const toDoc = (e: PointerEvent | WheelEvent | MouseEvent): Pt => {
      const r = host.getBoundingClientRect()
      const st = useEditor.getState()
      return { x: (e.clientX - r.left - st.pan.x) / st.zoom, y: (e.clientY - r.top - st.pan.y) / st.zoom }
    }
    type Drag = { kind: 'pan' | 'paint' | 'move' | 'marquee' | 'lasso' | 'xmove' | 'xscale' | 'xrotate' | 'aibox' | 'gradient'; start: Pt; last: Pt; startPan?: Pt; nodeStart?: Pt; pts?: Pt[]; target?: LayerPixels; t0?: Xform; hx?: number; hy?: number; a0?: number; alt?: boolean
      // D50 / D51 painting: the stroke, its smoother and dab walker (layer coordinates), straight-line mode, the pointer's last move time
      stroke?: Stroke; smoother?: Smoother; walker?: PathWalker; brushAt?: Pt; offset?: Pt; line?: boolean; movedAt?: number; targetId?: string; targetKind?: 'image' | 'mask' }
    let drag: Drag | null = null
    let spaceHeld = false
    const onKey = (e: KeyboardEvent) => { if (e.code === 'Space') { if ((e.target as HTMLElement)?.closest('input, textarea, select')) return; spaceHeld = e.type === 'keydown'; host.style.cursor = spaceHeld ? 'grab' : '' } }
    window.addEventListener('keydown', onKey); window.addEventListener('keyup', onKey)

    const paintTarget = (): { lp: LayerPixels; kind: 'image' | 'mask'; offset: Pt; id: string } | null => {
      const st = useEditor.getState()
      const doc = st.doc
      if (!doc) return null
      if (st.quickMask) return { lp: st.ensureSelection(), kind: 'mask', offset: { x: 0, y: 0 }, id: 'selection' }
      const n = findNode(doc, st.activeId)
      if (!n || n.locked) { useSession.getState().toast(n?.locked ? 'Layer is locked' : 'Select a raster layer to paint on', 'info'); return null }
      if (st.editingMask && n.mask) { const m = st.masks.get(n.id); return m ? { lp: m, kind: 'mask', offset: { x: (n.mask.linked ? (n.x ?? 0) : 0) + n.mask.x, y: (n.mask.linked ? (n.y ?? 0) : 0) + n.mask.y }, id: n.id } : null }
      // D52: masks are paintable on every node kind (groups, adjustments, filters); pixels only on rasters
      if (n.kind !== 'raster') { useSession.getState().toast(n.mask ? 'Click the mask thumbnail to paint this layer\'s mask' : 'Select a raster layer to paint on, or add a mask to paint', 'info'); return null }
      const lp = st.pixels.get(n.id)
      return lp ? { lp, kind: 'image', offset: { x: n.x ?? 0, y: n.y ?? 0 }, id: n.id } : null
    }

    /** D50: a new stroke on the paint target, with the brush options, the selection as a clip and the layer's lock transparency. */
    const beginStroke = (t: NonNullable<ReturnType<typeof paintTarget>>, erase: boolean): Stroke => {
      const st = useEditor.getState()
      const b = st.brush
      const hex = b.color.replace('#', '')
      const colour: [number, number, number] = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16) || 0) as [number, number, number]
      const n = findNode(st.doc, st.activeId)
      // D54 (PhotoCraft): on a mask or in Quick Mask the brush paints the foreground's grey, the eraser the background's
      const grey = lumaOf(erase ? b.background : b.color)
      return new Stroke({
        lp: t.lp, kind: t.kind, erase: t.kind === 'image' && erase, colour, grey, size: b.size, hardness: b.hardness, opacity: b.opacity, flow: b.flow, spacing: b.spacing,
        lockAlpha: t.kind === 'image' && !!n?.lock_alpha, offset: t.offset, docW: st.doc!.w,
        selection: st.selection && t.id !== 'selection' ? selectionValues(st.selection) : null,
      })
    }
    /** End a stroke: one history entry, the layer marked for upload, and the point Shift-click lines continue from. */
    const endStroke = (stroke: Stroke, t: { id: string; kind: 'image' | 'mask' }, endAt: Pt) => {
      const st = useEditor.getState()
      stroke.flush()
      const tiles = stroke.s.lp.endStroke()
      stroke.s.lp.dirty = true
      st.pushHistory({ label: st.tool === 'eraser' ? 'erase' : st.quickMask ? 'quick mask' : t.kind === 'mask' ? 'paint mask' : 'brush', layerId: t.id, kind: t.kind, tiles, at: Date.now() })
      lastPaint = { id: t.id, at: endAt }
      st.touch(); st.bump()
      markPassesDirty(); requestRender()
    }
    /** Dabs along a straight segment (layer coordinates), then flush. */
    const line = (stroke: Stroke, a: Pt, b: Pt) => {
      const w = new PathWalker(Math.max(1, stroke.s.size * stroke.s.spacing))
      stroke.dab(a.x, a.y)
      w.walk(a, b, (x, y) => stroke.dab(x, y))
      stroke.flush()
    }
    // the catch-up feed (D51): while the pointer rests the brush keeps moving towards it, one step per frame
    let catchRaf = 0
    const catchUp = () => {
      catchRaf = 0
      if (!drag || drag.kind !== 'paint' || !drag.stroke || !drag.smoother || drag.line) return
      if (performance.now() - (drag.movedAt ?? 0) > 30) {
        const prev = drag.brushAt!
        const pt = drag.smoother.catchUp()
        if (pt) {
          drag.walker!.walk({ x: prev.x - drag.offset!.x, y: prev.y - drag.offset!.y }, { x: pt.x - drag.offset!.x, y: pt.y - drag.offset!.y }, (x, y) => drag!.stroke!.dab(x, y))
          drag.brushAt = { ...pt }
          drag.stroke.flush(); markPassesDirty(); requestRender()
        }
      }
      catchRaf = requestAnimationFrame(catchUp)
    }

    const onDown = (e: PointerEvent) => {
      if (e.button !== 0 && e.button !== 1) return
      const st = useEditor.getState()
      if (!st.doc) return
      host.setPointerCapture(e.pointerId)
      const p = toDoc(e)
      const tool = spaceHeld || e.button === 1 || st.tool === 'hand' ? 'hand' : st.tool
      if (tool === 'hand') { drag = { kind: 'pan', start: { x: e.clientX, y: e.clientY }, last: p, startPan: { ...st.pan } }; host.style.cursor = 'grabbing'; return }
      if (st.transform) {                                               // free transform owns the pointer
        const t = st.transform
        const hit = handles(t).find((h) => Math.hypot(h.x - p.x, h.y - p.y) <= 7 / st.zoom)
        if (hit) drag = { kind: 'xscale', start: p, last: p, t0: { ...t }, hx: hit.hx, hy: hit.hy }
        else if (insideQuad(t, p)) drag = { kind: 'xmove', start: p, last: p, t0: { ...t } }
        else drag = { kind: 'xrotate', start: p, last: p, t0: { ...t }, a0: Math.atan2(p.y - t.cy, p.x - t.cx) }
        return
      }
      if (tool === 'zoom') { zoomAt(e, e.altKey ? 1 / 1.5 : 1.5); return }
      if (tool === 'eyedropper') { void pick(p); return }
      if (tool === 'brush' || tool === 'eraser') {
        // D51: Alt-click (or the armed eyedropper chip) picks the colour instead of painting
        if (e.altKey || st.pickOnce) { if (st.pickOnce) st.setView({ pickOnce: false }); void pick(p); return }
        const t = paintTarget()
        if (!t) return
        const erase = tool === 'eraser'
        const stroke = beginStroke(t, erase)
        const local = { x: p.x - t.offset.x, y: p.y - t.offset.y }
        if (e.shiftKey && lastPaint && lastPaint.id === t.id) {           // D51: Shift-click — a straight line from the last point
          line(stroke, { x: lastPaint.at.x - t.offset.x, y: lastPaint.at.y - t.offset.y }, local)
          endStroke(stroke, t, p)
          return
        }
        drag = { kind: 'paint', start: p, last: p, target: t.lp, stroke, offset: t.offset, brushAt: p, movedAt: performance.now(), targetId: t.id, targetKind: t.kind,
          line: st.brushLine, smoother: new Smoother(p, (st.brush.smoothing * 100) / Math.max(1e-3, st.zoom)), walker: new PathWalker(Math.max(1, st.brush.size * st.brush.spacing)) }
        stroke.dab(local.x, local.y); stroke.flush()
        markPassesDirty(); requestRender()
        if (!drag.line && !catchRaf) catchRaf = requestAnimationFrame(catchUp)
        return
      }
      if (tool === 'move') {
        const n = findNode(st.doc, st.activeId)
        if (!n || n.kind !== 'raster' || n.locked) return
        drag = { kind: 'move', start: p, last: p, nodeStart: { x: n.x ?? 0, y: n.y ?? 0 } }
        return
      }
      if (tool === 'marquee') { drag = { kind: 'marquee', start: p, last: p }; return }
      if (tool === 'lasso' && st.lassoKind === 'polygon') {
        // D44 polygonal lasso: each click adds a corner; clicking the first corner (or a double-click, ✓, Enter) closes it
        const poly = st.lassoPoly
        if (!poly) { st.setLassoPoly([p]); return }
        if (poly.length >= 3 && Math.hypot(p.x - poly[0].x, p.y - poly[0].y) * st.zoom <= 8) { clearPreview(); st.closeLassoPoly(modeFor(e, st.selectionMode)); return }
        st.setLassoPoly([...poly, p]); previewPoly([...poly, p], p)
        return
      }
      if (tool === 'lasso') { drag = { kind: 'lasso', start: p, last: p, pts: [p] }; return }
      if (tool === 'wand') { void wandAt(p, modeFor(e, st.selectionMode)); return }
      if (tool === 'ai') { drag = { kind: 'aibox', start: p, last: p, alt: e.altKey }; return }           // click = point, drag = box (decided on up)
      if (tool === 'fill') { if (st.fillMode === 'solid') { fillAt(p); return } drag = { kind: 'gradient', start: p, last: p }; return }
    }
    const onMove = (e: PointerEvent) => {
      const st = useEditor.getState()
      const p = toDoc(e)
      st.setCursor({ x: Math.floor(p.x), y: Math.floor(p.y) })
      if (!drag && st.tool === 'lasso' && st.lassoPoly) { previewPoly(st.lassoPoly, p); return }
      if (!drag) return
      if (drag.kind === 'pan') { st.setView({ pan: { x: drag.startPan!.x + e.clientX - drag.start.x, y: drag.startPan!.y + e.clientY - drag.start.y } }); return }
      if (drag.kind === 'xmove') { st.setTransform({ cx: drag.t0!.cx + p.x - drag.start.x, cy: drag.t0!.cy + p.y - drag.start.y }); return }
      if (drag.kind === 'xrotate') {
        let a = drag.t0!.rot + Math.atan2(p.y - drag.t0!.cy, p.x - drag.t0!.cx) - drag.a0!
        if (e.shiftKey) a = Math.round(a / (Math.PI / 12)) * (Math.PI / 12)
        st.setTransform({ rot: a }); return
      }
      if (drag.kind === 'xscale') {
        const t0 = drag.t0!
        const u = toLocal(t0, p)
        let sx = drag.hx ? u.x / (drag.hx * t0.w / 2) : t0.sx
        let sy = drag.hy ? u.y / (drag.hy * t0.h / 2) : t0.sy
        if (e.shiftKey && drag.hx && drag.hy) { const s = (Math.abs(sx) + Math.abs(sy)) / 2; sx = Math.sign(sx) * s; sy = Math.sign(sy) * s }
        st.setTransform({ sx: Math.abs(sx) < 0.01 ? 0.01 * Math.sign(sx || 1) : sx, sy: Math.abs(sy) < 0.01 ? 0.01 * Math.sign(sy || 1) : sy }); return
      }
      if (drag.kind === 'paint' && drag.stroke) {
        const o = drag.offset!
        drag.movedAt = performance.now()
        if (drag.line) {                                                 // straight-line mode: redraw start → pointer each move
          drag.stroke.reset()
          line(drag.stroke, { x: drag.start.x - o.x, y: drag.start.y - o.y }, { x: p.x - o.x, y: p.y - o.y })
          drag.last = p
        } else {
          const events = (e as PointerEvent & { getCoalescedEvents?: () => PointerEvent[] }).getCoalescedEvents?.() ?? [e]
          for (const ev of events) {
            const prev = drag.brushAt!
            const b = drag.smoother!.push(toDoc(ev))
            drag.walker!.walk({ x: prev.x - o.x, y: prev.y - o.y }, { x: b.x - o.x, y: b.y - o.y }, (x, y) => drag!.stroke!.dab(x, y))
            drag.brushAt = { ...b }
          }
          drag.last = p
          drag.stroke.flush()
        }
        markPassesDirty()                                            // strokes inside masked layers / isolated groups
        requestRender()
        return
      }
      if (drag.kind === 'move') {
        const n = findNode(st.doc, st.activeId)
        if (!n) return
        const nx = Math.round(drag.nodeStart!.x + p.x - drag.start.x), ny = Math.round(drag.nodeStart!.y + p.y - drag.start.y)
        const sp = spritesRef.current.get(n.id) as Sprite | undefined
        if (sp) { sp.position.set(nx, ny); markPassesDirty(); requestRender() }   // the layer may sit inside a pass (clip run, mask)
        drag.last = { x: nx, y: ny }
        return
      }
      if (drag.kind === 'marquee') { drag.last = p; previewMarquee(drag.start, p); return }
      if (drag.kind === 'lasso') { drag.pts!.push(p); drag.last = p; previewLasso(drag.pts!); return }
      if (drag.kind === 'aibox') { drag.last = p; drawAiPrompt({ start: drag.start, last: p }); return }
      if (drag.kind === 'gradient') { drag.last = p; drawGuide(drag.start, p); return }
    }
    const onUp = (e: PointerEvent) => {
      const st = useEditor.getState()
      if (!drag) return
      host.releasePointerCapture(e.pointerId)
      if (drag.kind === 'pan') host.style.cursor = spaceHeld ? 'grab' : ''
      if (drag.kind === 'paint' && drag.stroke) {
        if (catchRaf) { cancelAnimationFrame(catchRaf); catchRaf = 0 }
        const o = drag.offset!
        if (!drag.line && drag.smoother) {                                // catch-up on release: finish at the pointer
          const prev = drag.brushAt!
          const end = drag.smoother.finish()
          drag.walker!.walk({ x: prev.x - o.x, y: prev.y - o.y }, { x: end.x - o.x, y: end.y - o.y }, (x, y) => drag!.stroke!.dab(x, y))
        }
        endStroke(drag.stroke, { id: drag.targetId!, kind: drag.targetKind! }, drag.line ? drag.last : drag.smoother?.brush ?? drag.last)
      }
      if (drag.kind === 'move') { const n = findNode(st.doc, st.activeId); if (n && (drag.last.x !== drag.nodeStart!.x || drag.last.y !== drag.nodeStart!.y)) st.updateNode(n.id, { x: drag.last.x, y: drag.last.y }, 'move layer') }
      if (drag.kind === 'marquee') commitMarquee(drag.start, drag.last, modeFor(e, st.selectionMode))
      if (drag.kind === 'lasso') commitLasso(drag.pts!, modeFor(e, st.selectionMode))
      if (drag.kind === 'aibox') {
        const moved = Math.hypot(drag.last.x - drag.start.x, drag.last.y - drag.start.y) * st.zoom
        if (moved < 4) {                                                   // a click: one SAM 3 point (Alt = exclude)
          st.setAiPrompt({ points: [...st.aiPrompt.points, { x: Math.round(drag.start.x), y: Math.round(drag.start.y), label: drag.alt ? 0 : 1 }] })
          useAiPanel.getState().set({ selModel: 'sam3', selMode: 'points' })
        } else {
          st.setAiPrompt({ box: [Math.round(Math.min(drag.start.x, drag.last.x)), Math.round(Math.min(drag.start.y, drag.last.y)), Math.round(Math.max(drag.start.x, drag.last.x)), Math.round(Math.max(drag.start.y, drag.last.y))] })
          useAiPanel.getState().set({ selModel: 'sam3', selMode: 'box' })
        }
      }
      if (drag.kind === 'gradient') gradientFill(drag.start, drag.last)
      drag = null
    }
    const onDouble = (e: MouseEvent) => {
      const st = useEditor.getState()
      if (st.transform && insideQuad(st.transform, toDoc(e))) st.applyTransform()
      else if (st.tool === 'lasso' && st.lassoPoly) { clearPreview(); st.closeLassoPoly(modeFor(e, st.selectionMode)) }
    }
    const zoomAt = (e: { clientX: number; clientY: number }, k: number) => {
      const st = useEditor.getState()
      const r = host.getBoundingClientRect()
      const px = e.clientX - r.left, py = e.clientY - r.top
      const z = Math.max(0.02, Math.min(64, st.zoom * k))
      st.setView({ zoom: z, pan: { x: px - (px - st.pan.x) * (z / st.zoom), y: py - (py - st.pan.y) * (z / st.zoom) } })
    }
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const st = useEditor.getState()
      if (e.ctrlKey || e.metaKey || st.tool === 'zoom') zoomAt(e, Math.exp(-e.deltaY * 0.0015))
      else st.setView({ pan: { x: st.pan.x - e.deltaX, y: st.pan.y - e.deltaY } })
    }
    const pick = async (p: Pt) => {
      const app = appRef.current, layers = layersRef.current
      if (!app || !layers) return
      renderPasses()
      const px = await app.renderer.extract.pixels({ target: layers, frame: new Rectangle(Math.floor(p.x), Math.floor(p.y), 1, 1) })   // B17: Pixi copies the frame with Rectangle.copyTo
      const d = px.pixels
      const a = d[3] || 255                                                  // C30: extract hands back premultiplied RGBA
      const un = (v: number) => Math.min(255, Math.round((v * 255) / a))
      const hex = '#' + [un(d[0]), un(d[1]), un(d[2])].map((v) => v.toString(16).padStart(2, '0')).join('')
      useEditor.getState().setBrush({ color: hex })
      useSession.getState().toast(`Picked ${hex}`, 'info')
    }
    // ---- selections (CPU mask, D43 / D44): every tool renders a document-sized shape, combined into the selection by mode ----
    /** A shape drawn in white on a document-sized canvas, as values (0–255, anti-aliased edges kept). */
    const shapeFrom = (draw: (ctx: CanvasRenderingContext2D) => void): Uint8Array | null => {
      const doc = useEditor.getState().doc
      if (!doc) return null
      const c = document.createElement('canvas'); c.width = doc.w; c.height = doc.h
      const cx = c.getContext('2d', { willReadFrequently: true })!
      cx.fillStyle = '#ffffff'
      draw(cx)
      const d = cx.getImageData(0, 0, doc.w, doc.h).data
      const out = new Uint8Array(doc.w * doc.h)
      for (let i = 0, j = 3; i < out.length; i++, j += 4) out[i] = d[j]
      return out
    }
    /** The marquee rectangle for a drag from a to b under the options' style (fixed ratio follows the drag width; fixed size
     * hangs from the pointer). */
    const marqueeRect = (a: Pt, b: Pt) => {
      const st = useEditor.getState()
      if (st.marqueeStyle === 'size') return { x: b.x, y: b.y, w: Math.max(1, st.marqueeW), h: Math.max(1, st.marqueeH) }
      const w = b.x - a.x
      let h = b.y - a.y
      if (st.marqueeStyle === 'ratio') h = (h < 0 ? -1 : 1) * Math.abs(w) * (Math.max(1e-6, st.marqueeH) / Math.max(1e-6, st.marqueeW))
      return { x: Math.min(a.x, a.x + w), y: Math.min(a.y, a.y + h), w: Math.abs(w), h: Math.abs(h) }
    }
    const previewMarquee = (a: Pt, b: Pt) => drawPreview((g) => { const st = useEditor.getState(); const r = marqueeRect(a, b); if (st.marqueeShape === 'ellipse') g.ellipse(r.x + r.w / 2, r.y + r.h / 2, r.w / 2, r.h / 2); else g.rect(r.x, r.y, r.w, r.h) })
    const previewLasso = (pts: Pt[]) => drawPreview((g) => { g.poly(pts.map((q) => [q.x, q.y]).flat()) })
    const previewPoly = (pts: Pt[], cursor: Pt) => drawPreview((g) => {
      const z = useEditor.getState().zoom
      g.moveTo(pts[0].x, pts[0].y); for (const q of pts.slice(1)) g.lineTo(q.x, q.y); g.lineTo(cursor.x, cursor.y)
      g.circle(pts[0].x, pts[0].y, 5 / z)                                // the corner that closes the polygon
    })
    const drawPreview = (shape: (g: Graphics) => void) => {
      const ov = overlayRef.current; if (!ov) return
      let g = ov.getChildByLabel('preview') as Graphics | null
      if (!g) { g = new Graphics(); g.label = 'preview'; ov.addChild(g) }
      g.clear(); shape(g); g.stroke({ color: 0xffffff, width: 1 / useEditor.getState().zoom, alpha: 0.9 })
      requestRender()
    }
    const clearPreview = () => { const ov = overlayRef.current; const g = ov?.getChildByLabel('preview'); if (g) g.destroy(); requestRender() }
    const commitMarquee = (a: Pt, b: Pt, mode: SelectionMode) => {
      clearPreview()
      const st = useEditor.getState()
      const r = marqueeRect(a, b)
      const x = Math.round(r.x), y = Math.round(r.y), w = Math.round(r.w), h = Math.round(r.h)
      if (st.marqueeStyle !== 'size' && (w < 1 || h < 1)) { if (mode === 'replace') st.deselect(); return }
      const shape = shapeFrom((ctx) => { if (st.marqueeShape === 'ellipse') { ctx.beginPath(); ctx.ellipse(x + w / 2, y + h / 2, w / 2, h / 2, 0, 0, Math.PI * 2); ctx.fill() } else ctx.fillRect(x, y, w, h) })
      if (shape) st.applySelectionShape(shape, mode, st.marqueeShape === 'ellipse' ? 'elliptical marquee' : 'marquee', st.marqueeFeather)
    }
    const commitLasso = (pts: Pt[], mode: SelectionMode) => {
      clearPreview()
      if (pts.length < 3) return
      const st = useEditor.getState()
      const shape = shapeFrom((ctx) => { ctx.beginPath(); ctx.moveTo(pts[0].x, pts[0].y); for (const q of pts.slice(1)) ctx.lineTo(q.x, q.y); ctx.closePath(); ctx.fill() })
      if (shape) st.applySelectionShape(shape, mode, 'lasso', st.marqueeFeather)
    }
    /** D44 magic wand (PhotoCraft crates/algo/src/selection.rs wand rules): per-channel tolerance including alpha — a fully
     * transparent pixel matches a transparent seed whatever its hidden RGB; contiguous (4-connected flood) or global; on the active
     * raster layer or the merged composite; anti-aliased by a 3×3 average on the edge pixels only. */
    const wandAt = async (p: Pt, mode: SelectionMode) => {
      const st = useEditor.getState()
      const doc = st.doc; if (!doc) return
      const n = findNode(doc, st.activeId)
      const lp = n?.kind === 'raster' ? st.pixels.get(n.id) : null
      let img: Uint8ClampedArray, W: number, H: number, ox = 0, oy = 0
      if (st.wandMerged || !lp) {
        const c = st.extractor?.()
        if (!c) { useSession.getState().toast('The composite is not available yet', 'info'); return }
        W = c.width; H = c.height; img = c.getContext('2d', { willReadFrequently: true })!.getImageData(0, 0, W, H).data
      } else {
        W = lp.width; H = lp.height; ox = n!.x ?? 0; oy = n!.y ?? 0; img = lp.ctx.getImageData(0, 0, W, H).data
      }
      const x0 = Math.floor(p.x - ox), y0 = Math.floor(p.y - oy)
      if (x0 < 0 || y0 < 0 || x0 >= W || y0 >= H) return
      const tol = st.tolerance
      const s0 = (y0 * W + x0) * 4
      const r0 = img[s0], g0 = img[s0 + 1], b0 = img[s0 + 2], a0 = img[s0 + 3]
      const match = (j: number) => {
        const a = img[j + 3]
        if (a0 === 0 || a === 0) return Math.abs(a - a0) <= tol         // a transparent pixel's RGB is meaningless
        return Math.abs(img[j] - r0) <= tol && Math.abs(img[j + 1] - g0) <= tol && Math.abs(img[j + 2] - b0) <= tol && Math.abs(a - a0) <= tol
      }
      const out = new Uint8Array(W * H)
      let bx0 = x0, by0 = y0, bx1 = x0, by1 = y0
      const mark = (i: number) => { out[i] = 255; const x = i % W, y = (i - x) / W; if (x < bx0) bx0 = x; if (x > bx1) bx1 = x; if (y < by0) by0 = y; if (y > by1) by1 = y }
      if (st.wandContiguous) {
        const stack = [y0 * W + x0]
        const seen = new Uint8Array(W * H)
        while (stack.length) {
          const i = stack.pop()!
          if (seen[i]) continue
          seen[i] = 1
          if (!match(i * 4)) continue
          mark(i)
          const x = i % W
          if (x > 0) stack.push(i - 1); if (x < W - 1) stack.push(i + 1); if (i >= W) stack.push(i - W); if (i < W * (H - 1)) stack.push(i + W)
        }
      } else {
        for (let i = 0; i < W * H; i++) if (match(i * 4)) mark(i)
      }
      let vals = out
      if (st.wandAA) {
        vals = out.slice()
        for (let y = Math.max(0, by0 - 1); y <= Math.min(H - 1, by1 + 1); y++) for (let x = Math.max(0, bx0 - 1); x <= Math.min(W - 1, bx1 + 1); x++) {
          const i = y * W + x
          const v = out[i]
          const edge = (x > 0 && out[i - 1] !== v) || (x < W - 1 && out[i + 1] !== v) || (y > 0 && out[i - W] !== v) || (y < H - 1 && out[i + W] !== v)
          if (!edge) continue
          let sum = 0, cnt = 0
          for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) { const xx = x + dx, yy = y + dy; if (xx >= 0 && yy >= 0 && xx < W && yy < H) { sum += out[yy * W + xx]; cnt++ } }
          vals[i] = Math.round(sum / cnt)
        }
      }
      // place the result (layer pixels at the layer offset) into a document-sized shape
      const shape = new Uint8Array(doc.w * doc.h)
      for (let y = 0; y < H; y++) {
        const dy = y + oy
        if (dy < 0 || dy >= doc.h) continue
        for (let x = 0; x < W; x++) { const dx = x + ox; if (dx >= 0 && dx < doc.w) shape[dy * doc.w + dx] = vals[y * W + x] }
      }
      st.applySelectionShape(shape, mode, 'magic wand')
    }
    /** G tool in linear / radial mode: foreground → background colour from a to b (mask: white → black), inside the selection. */
    const gradientFill = (a: Pt, b: Pt) => {
      drawGuide()
      const st = useEditor.getState()
      if (Math.hypot(b.x - a.x, b.y - a.y) < 1) return
      const t = paintTarget(); if (!t) return
      const doc = st.doc!
      const tmp = document.createElement('canvas'); tmp.width = doc.w; tmp.height = doc.h
      const tc = tmp.getContext('2d')!
      const grad = st.fillMode === 'radial' ? tc.createRadialGradient(a.x, a.y, 0, a.x, a.y, Math.hypot(b.x - a.x, b.y - a.y)) : tc.createLinearGradient(a.x, a.y, b.x, b.y)
      const grey = (c: string) => { const v = lumaOf(c); return `rgb(${v}, ${v}, ${v})` }
      const [c0, c1] = t.kind === 'mask' ? [grey(st.brush.color), grey(st.brush.background)] : [st.brush.color, st.brush.background]   // D54
      grad.addColorStop(0, c0); grad.addColorStop(1, c1)
      tc.fillStyle = grad; tc.fillRect(0, 0, doc.w, doc.h)
      if (st.selection) { tc.globalCompositeOperation = 'destination-in'; tc.drawImage(selectionAlphaCanvas(st.selection), 0, 0) }
      t.lp.beginStroke(); t.lp.touch(0, 0, t.lp.width, t.lp.height)
      const ctx = t.lp.ctx
      ctx.save(); ctx.globalAlpha = st.brush.opacity; ctx.drawImage(tmp, -t.offset.x, -t.offset.y); ctx.restore()
      t.lp.refresh(); t.lp.dirty = true
      st.pushHistory({ label: `${st.fillMode} gradient`, layerId: t.id, kind: t.kind, tiles: t.lp.endStroke(), at: Date.now() })
      st.touch(); st.bump(); markPassesDirty(); requestRender()
    }
    const fillAt = (p: Pt) => {
      const st = useEditor.getState()
      const t = paintTarget(); if (!t) return
      const doc = st.doc!
      t.lp.beginStroke(); t.lp.touch(0, 0, t.lp.width, t.lp.height)
      const ctx = t.lp.ctx
      ctx.save()
      ctx.globalAlpha = st.brush.opacity
      const fv = lumaOf(st.brush.color)
      ctx.fillStyle = t.kind === 'mask' ? `rgb(${fv}, ${fv}, ${fv})` : st.brush.color   // D54: a mask takes the foreground's grey
      if (st.selection) {
        // fill only inside the selection: a canvas whose alpha is the selection value, filled with the colour
        const tmp = selectionAlphaCanvas(st.selection)
        const tc = tmp.getContext('2d')!
        tc.globalCompositeOperation = 'source-in'; tc.fillStyle = ctx.fillStyle as string; tc.fillRect(0, 0, doc.w, doc.h)
        ctx.drawImage(tmp, -t.offset.x, -t.offset.y)
      } else ctx.fillRect(0, 0, t.lp.width, t.lp.height)
      ctx.restore()
      void p
      t.lp.refresh(); t.lp.dirty = true
      st.pushHistory({ label: 'fill', layerId: t.id, kind: t.kind, tiles: t.lp.endStroke(), at: Date.now() })
      st.touch(); st.bump()
    }
    const unregDrop = registerDropTarget(host, { accept: onlyAssets, drop: (p) => assetIds(p).forEach((id) => void useEditor.getState().addLayerFromAsset(id)) })   // tiles become layers
    // D46: OS files dropped on the canvas go through the Catalogue (lineage) and land as layers; Tauri reports real paths
    const unlistenFiles = listenFileDrop({ over: (inside) => host.classList.toggle('file-over', inside), within: () => host,
      drop: (paths) => { host.classList.remove('file-over'); void useEditor.getState().dropFiles(paths) } })
    // an open polygon ends when it is closed or cancelled elsewhere (✓ / ⊘, Enter / Esc) or when the tool changes
    const unsubPoly = useEditor.subscribe((s, prev) => {
      if (prev.lassoPoly && !s.lassoPoly) clearPreview()
      if (s.lassoPoly && s.tool !== 'lasso') s.setLassoPoly(null)
    })
    host.addEventListener('pointerdown', onDown)
    host.addEventListener('pointermove', onMove)
    host.addEventListener('pointerup', onUp)
    host.addEventListener('pointercancel', onUp)
    host.addEventListener('dblclick', onDouble)
    host.addEventListener('wheel', onWheel, { passive: false })
    const onContext = (e: MouseEvent) => { e.preventDefault(); if (drag) return; showMenu(e, canvasMenu()) }
    host.addEventListener('contextmenu', onContext)
    return () => {
      unregDrop(); unlistenFiles()
      host.removeEventListener('pointerdown', onDown); host.removeEventListener('pointermove', onMove); host.removeEventListener('pointerup', onUp); host.removeEventListener('pointercancel', onUp)
      host.removeEventListener('dblclick', onDouble); unsubPoly()
      host.removeEventListener('wheel', onWheel); host.removeEventListener('contextmenu', onContext)
      window.removeEventListener('keydown', onKey); window.removeEventListener('keyup', onKey)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return <div ref={hostRef} className="edit-canvas" />
}
