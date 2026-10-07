// The PixiJS stage for the Edit suite (10 §2, 05 §3b): one Application rendered on demand, a world container
// with the document's layers as sprites (masks and isolated groups through render-texture passes, exact W3C blend
// shaders, adjustment/filter layers as per-layer filters), the selection's marching ants, the free-transform
// box, a checkerboard, and the pointer handling for the tools (brush, eraser, move/transform, hand, zoom,
// marquee, lasso, wand, fill, eyedropper).
import { Application, ColorMatrixFilter, Container, Graphics, Matrix, Rectangle, RendererType, RenderTexture, Sprite, Texture, TilingSprite } from 'pixi.js'
import 'pixi.js/advanced-blend-modes'
import { useEffect, useRef } from 'react'
import { useSession } from '../../store/session'
import { showMenu } from '../../frame/ContextMenu'
import { ensureAdjustment } from './adjustFilters'
import { blendName } from './blendModes'
import { canvasMenu } from './editCommands'
import { findNode, useEditor, type Node } from './editorStore'
import { useAiPanel } from './aiPanelStore'
import { makeDab, selectionAlphaCanvas, type LayerPixels } from './layerPixels'
import { corners, handles, insideQuad, toLocal, type Xform } from './transform'

/** Inverts RGB (keeps alpha) and adds: red where a mask/selection is black, nothing where it is white. */
function negativeAdd(): ColorMatrixFilter { const f = new ColorMatrixFilter(); f.negative(false); f.blendMode = 'add'; return f }

function checkerTexture(): Texture {
  const c = document.createElement('canvas'); c.width = c.height = 16
  const ctx = c.getContext('2d')!
  ctx.fillStyle = '#2a2a2a'; ctx.fillRect(0, 0, 16, 16)
  ctx.fillStyle = '#3a3a3a'; ctx.fillRect(0, 0, 8, 8); ctx.fillRect(8, 8, 8, 8)
  return Texture.from(c)
}

/** Axis-aligned boundary runs of the selection (value > 127), as [x0, y0, x1, y1, …] in document pixels. */
function outlineSegments(sel: LayerPixels): number[] {
  const W = sel.width, H = sel.height
  const d = sel.ctx.getImageData(0, 0, W, H).data
  const inside = (x: number, y: number) => x >= 0 && y >= 0 && x < W && y < H && d[(y * W + x) * 4] > 127
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
  /** On-demand rendering (10 §11): one frame on the next animation frame, nothing while idle. A request made before the
   * renderer exists is dropped (init renders once itself), so a cancelled frame can never leave the flag set. */
  const requestRender = () => {
    if (!appRef.current) return
    if (renderPending.current) return
    const run = () => { renderPending.current = 0; renderPasses(); appRef.current?.render() }
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
  }

  // ---- app lifecycle --------------------------------------------------------------------------
  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    let cancelled = false
    let ro: ResizeObserver | null = null
    const devOverride = import.meta.env.DEV ? new URLSearchParams(location.search).get('renderer') : null      // dev deep link: &renderer=webgl|webgpu
    const pref = useEditor.getState().rendererPref
    const want: 'webgpu' | 'webgl' = devOverride === 'webgl' || (devOverride !== 'webgpu' && pref === 'webgl') ? 'webgl' : 'webgpu'
    const boot = async (preference: 'webgpu' | 'webgl') => {
      const a = new Application()
      await a.init({ preference, background: 0x141414, antialias: false, resolution: window.devicePixelRatio || 1, autoDensity: true, resizeTo: host, powerPreference: 'high-performance', autoStart: false })
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
      useEditor.getState().setExtractor(() => {
        const d = useEditor.getState().doc
        if (!d || !layersRef.current) return null
        // extract.canvas() may hand back a WebGPU/bitmap canvas (no 2D context); redraw it into a plain 2D canvas,
        // which also leaves the browser to convert premultiplied → straight alpha
        markPassesDirty(); renderPasses()
        const src = app.renderer.extract.canvas({ target: layersRef.current, frame: new Rectangle(0, 0, d.w, d.h), resolution: 1 }) as HTMLCanvasElement
        const c = document.createElement('canvas'); c.width = d.w; c.height = d.h
        c.getContext('2d')!.drawImage(src, 0, 0)
        return c
      })
      ro = new ResizeObserver(() => { app.renderer.resize(host.clientWidth, host.clientHeight); requestRender() })
      ro.observe(host)
      useEditor.getState().bump()                                      // re-run the scene effects now that the renderer exists
      useEditor.getState().requestFit()
      requestRender()
    })()
    return () => {
      cancelled = true
      ro?.disconnect()
      cancelPendingRender()                                              // and clear the flag: a stale id blocked every later request (2026-10-06)
      useEditor.getState().setExtractor(null)
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
    let lastBlend = ''                                                   // alternate names so equal modes never batch
    const pickBlend = (mode: string, clip: boolean) => { const a = blendName(mode, clip, false); const name = a === lastBlend ? blendName(mode, clip, true) : a; lastBlend = name; return name }
    // Anything that must composite as a unit before its own blend/alpha/mask apply (masked layers, isolated groups)
    // is rendered into its own RenderTexture (a "pass") each frame it is dirty. Pixi's cacheAsTexture and sprite
    // masks do not give advanced blend filters the right backdrop, measured in the M4 acceptance.
    const makePass = (content: Container, w: number, h: number, tx: number, ty: number): Sprite => {
      const rt = RenderTexture.create({ width: Math.max(1, w), height: Math.max(1, h), resolution: 1, antialias: false })
      passesRef.current.push({ rt, content, transform: new Matrix().translate(-tx, -ty), dirty: true })
      const sp = new Sprite(rt)
      sp.position.set(tx, ty)
      return sp
    }
    /** Wrap `obj` (in document coordinates) with the node's mask into a pass; returns the sprite to blend. */
    const withMask = (n: Node, obj: Container, w: number, h: number, tx: number, ty: number): Container => {
      const m = n.mask?.enabled ? st.masks.get(n.id) : undefined
      if (!m || !n.mask) return obj
      const ms = new Sprite(m.texture)
      ms.position.set((n.mask.linked ? (n.x ?? 0) : 0) + n.mask.x, (n.mask.linked ? (n.y ?? 0) : 0) + n.mask.y)
      const content = new Container()
      content.addChild(ms, obj)
      obj.mask = ms
      return makePass(content, w, h, tx, ty)
    }
    const build = (nodes: Node[], parent: Container) => {
      // ORA order is top-first; Pixi draws children in order, so add bottom-up
      for (let i = nodes.length - 1; i >= 0; i--) {
        const n = nodes[i]
        if (!n.visible) continue
        if (before && n.id === st.activeId) continue                  // "before": hide the active layer
        if (n.kind === 'raster') {
          const lp = st.pixels.get(n.id)
          if (!lp) continue
          const sp = new Sprite(lp.texture)
          sp.position.set(n.x ?? 0, n.y ?? 0)
          const obj = withMask(n, sp, lp.width, lp.height, n.x ?? 0, n.y ?? 0)
          obj.alpha = n.opacity * (n.fill ?? 1)
          ;(obj as unknown as { blendMode: string }).blendMode = pickBlend(n.blend, n.clip)
          parent.addChild(obj)
          spritesRef.current.set(n.id, obj)
        } else if (n.kind === 'group') {
          // compose.py: pass-through only when flagged so AND normal blend AND no mask AND opacity 1 (and no clip);
          // otherwise the group composites in isolation onto transparency first
          const passthrough = (n.passthrough ?? true) && (n.blend === 'normal' || n.blend === 'pass-through') && !n.mask?.enabled && Math.abs(n.opacity - 1) < 1e-6 && !n.clip
          const c = new Container()
          build(n.children ?? [], c)
          let obj: Container = c
          if (!passthrough) {
            obj = withMask(n, makePass(c, doc.w, doc.h, 0, 0), doc.w, doc.h, 0, 0)
            obj.alpha = n.opacity
            ;(obj as unknown as { blendMode: string }).blendMode = pickBlend(n.blend === 'pass-through' ? 'normal' : n.blend, n.clip)
          }
          parent.addChild(obj)
          spritesRef.current.set(n.id, obj)
        } else if (n.kind === 'adjustment' || n.kind === 'filter') {
          // a document-sized white sprite (or the layer's mask) carries the layer alpha; the per-layer filter
          // registered as a blend mode rewrites the backdrop (adjustFilters.ts)
          const m = n.mask?.enabled ? st.masks.get(n.id) : undefined
          const sp = m ? new Sprite(m.texture) : new Sprite(Texture.WHITE)
          if (m && n.mask) sp.position.set(n.mask.x, n.mask.y)
          else { sp.width = doc.w; sp.height = doc.h }
          sp.alpha = n.opacity * (n.fill ?? 1)
          ;(sp as unknown as { blendMode: string }).blendMode = ensureAdjustment(n)
          lastBlend = ''
          parent.addChild(sp)
          spritesRef.current.set(n.id, sp)
        }
      }
    }
    build(doc.layers, layers)
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
    if (editingMask && activeNode?.mask && overlay) {
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
  }, [doc, revision, before, overlay, quickMask, editingMask, activeId]) // eslint-disable-line react-hooks/exhaustive-deps

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
    type Drag = { kind: 'pan' | 'paint' | 'move' | 'marquee' | 'lasso' | 'xmove' | 'xscale' | 'xrotate' | 'aibox' | 'gradient'; start: Pt; last: Pt; startPan?: Pt; nodeStart?: Pt; pts?: Pt[]; target?: LayerPixels; dab?: HTMLCanvasElement; dist?: number; t0?: Xform; hx?: number; hy?: number; a0?: number; alt?: boolean }
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
      if (!n || n.kind !== 'raster' || n.locked) { useSession.getState().toast(n?.locked ? 'Layer is locked' : 'Select a raster layer to paint on', 'info'); return null }
      if (st.editingMask && n.mask) { const m = st.masks.get(n.id); return m ? { lp: m, kind: 'mask', offset: { x: (n.mask.linked ? (n.x ?? 0) : 0) + n.mask.x, y: (n.mask.linked ? (n.y ?? 0) : 0) + n.mask.y }, id: n.id } : null }
      const lp = st.pixels.get(n.id)
      return lp ? { lp, kind: 'image', offset: { x: n.x ?? 0, y: n.y ?? 0 }, id: n.id } : null
    }

    const stamp = (lp: LayerPixels, dab: HTMLCanvasElement, x: number, y: number, erase: boolean, mask: boolean, flow: number) => {
      const s = dab.width
      const x0 = Math.floor(x - s / 2), y0 = Math.floor(y - s / 2)
      lp.touch(x0, y0, x0 + s, y0 + s)
      const ctx = lp.ctx
      ctx.save()
      ctx.globalAlpha = flow
      ctx.globalCompositeOperation = erase ? (mask ? 'source-over' : 'destination-out') : 'source-over'
      ctx.drawImage(dab, x0, y0)
      ctx.restore()
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
        const t = paintTarget()
        if (!t) return
        const b = st.brush
        const erase = tool === 'eraser'
        const color = t.kind === 'mask' ? (erase ? '#000000' : '#ffffff') : b.color
        const dab = makeDab(b.size, b.hardness, color, b.opacity)
        t.lp.beginStroke()
        drag = { kind: 'paint', start: p, last: p, target: t.lp, dab, dist: 0 }
        stamp(t.lp, dab, p.x - t.offset.x, p.y - t.offset.y, erase, t.kind === 'mask', b.flow)
        t.lp.refresh(); markPassesDirty(); requestRender()
        return
      }
      if (tool === 'move') {
        const n = findNode(st.doc, st.activeId)
        if (!n || n.kind !== 'raster' || n.locked) return
        drag = { kind: 'move', start: p, last: p, nodeStart: { x: n.x ?? 0, y: n.y ?? 0 } }
        return
      }
      if (tool === 'marquee') { drag = { kind: 'marquee', start: p, last: p }; return }
      if (tool === 'lasso') { drag = { kind: 'lasso', start: p, last: p, pts: [p] }; return }
      if (tool === 'wand') { void wandAt(p, e.shiftKey ? 'add' : e.altKey ? 'subtract' : st.selectionMode); return }
      if (tool === 'ai') { drag = { kind: 'aibox', start: p, last: p, alt: e.altKey }; return }           // click = point, drag = box (decided on up)
      if (tool === 'fill') { if (st.fillMode === 'solid') { fillAt(p); return } drag = { kind: 'gradient', start: p, last: p }; return }
    }
    const onMove = (e: PointerEvent) => {
      const st = useEditor.getState()
      const p = toDoc(e)
      st.setCursor({ x: Math.floor(p.x), y: Math.floor(p.y) })
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
      if (drag.kind === 'paint' && drag.target && drag.dab) {
        const t = paintTarget(); if (!t) return
        const b = st.brush
        const erase = st.tool === 'eraser'
        const events = (e as PointerEvent & { getCoalescedEvents?: () => PointerEvent[] }).getCoalescedEvents?.() ?? [e]
        const step = Math.max(1, b.size * b.spacing)
        for (const ev of events) {
          const q = toDoc(ev)
          const sm = b.smoothing
          const tx = drag.last.x + (q.x - drag.last.x) * (1 - sm * 0.6), ty = drag.last.y + (q.y - drag.last.y) * (1 - sm * 0.6)
          const dx = tx - drag.last.x, dy = ty - drag.last.y
          const d = Math.hypot(dx, dy)
          drag.dist = (drag.dist ?? 0) + d
          let acc = drag.dist
          while (acc >= step) {
            const f = 1 - (acc - step) / Math.max(d, 1e-6)
            const sx = drag.last.x + dx * f, sy = drag.last.y + dy * f
            stamp(drag.target, drag.dab, sx - t.offset.x, sy - t.offset.y, erase, t.kind === 'mask', b.flow)
            acc -= step
          }
          drag.dist = acc
          drag.last = { x: tx, y: ty }
        }
        drag.target.refresh()
        markPassesDirty()                                            // strokes inside masked layers / isolated groups
        requestRender()
        return
      }
      if (drag.kind === 'move') {
        const n = findNode(st.doc, st.activeId)
        if (!n) return
        const nx = Math.round(drag.nodeStart!.x + p.x - drag.start.x), ny = Math.round(drag.nodeStart!.y + p.y - drag.start.y)
        const sp = spritesRef.current.get(n.id) as Sprite | undefined
        if (sp) { sp.position.set(nx, ny); requestRender() }
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
      if (drag.kind === 'paint' && drag.target) {
        const tiles = drag.target.endStroke()
        drag.target.dirty = true
        const t = paintTarget()
        if (t) st.pushHistory({ label: st.tool === 'eraser' ? 'erase' : st.quickMask ? 'quick mask' : t.kind === 'mask' ? 'paint mask' : 'brush', layerId: t.id, kind: t.kind, tiles, at: Date.now() })
        st.touch(); st.bump()
      }
      if (drag.kind === 'move') { const n = findNode(st.doc, st.activeId); if (n && (drag.last.x !== drag.nodeStart!.x || drag.last.y !== drag.nodeStart!.y)) st.updateNode(n.id, { x: drag.last.x, y: drag.last.y }, 'move layer') }
      if (drag.kind === 'marquee') commitMarquee(drag.start, drag.last, e.shiftKey ? 'add' : e.altKey ? 'subtract' : st.selectionMode)
      if (drag.kind === 'lasso') commitLasso(drag.pts!, e.shiftKey ? 'add' : e.altKey ? 'subtract' : st.selectionMode)
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
    const onDouble = (e: MouseEvent) => { const st = useEditor.getState(); if (st.transform && insideQuad(st.transform, toDoc(e))) st.applyTransform() }
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
    // ---- selections (CPU mask) ----
    const applySelection = (draw: (ctx: CanvasRenderingContext2D) => void, mode: 'replace' | 'add' | 'subtract') => {
      const st = useEditor.getState()
      const sel = st.ensureSelection()
      const ctx = sel.ctx
      ctx.save()
      if (mode === 'replace') { ctx.clearRect(0, 0, sel.width, sel.height) }
      ctx.globalCompositeOperation = mode === 'subtract' ? 'destination-out' : 'source-over'
      ctx.fillStyle = '#ffffff'
      draw(ctx)
      ctx.restore()
      sel.refresh(); sel.dirty = true
      st.bump()
    }
    const previewMarquee = (a: Pt, b: Pt) => drawPreview((g) => { const st = useEditor.getState(); const x = Math.min(a.x, b.x), y = Math.min(a.y, b.y), w = Math.abs(b.x - a.x), h = Math.abs(b.y - a.y); if (st.marqueeShape === 'ellipse') g.ellipse(x + w / 2, y + h / 2, w / 2, h / 2); else g.rect(x, y, w, h) })
    const previewLasso = (pts: Pt[]) => drawPreview((g) => { g.poly(pts.map((q) => [q.x, q.y]).flat()) })
    const drawPreview = (shape: (g: Graphics) => void) => {
      const ov = overlayRef.current; if (!ov) return
      let g = ov.getChildByLabel('preview') as Graphics | null
      if (!g) { g = new Graphics(); g.label = 'preview'; ov.addChild(g) }
      g.clear(); shape(g); g.stroke({ color: 0xffffff, width: 1 / useEditor.getState().zoom, alpha: 0.9 })
      requestRender()
    }
    const clearPreview = () => { const ov = overlayRef.current; const g = ov?.getChildByLabel('preview'); if (g) g.destroy(); requestRender() }
    const commitMarquee = (a: Pt, b: Pt, mode: 'replace' | 'add' | 'subtract') => {
      clearPreview()
      const x = Math.round(Math.min(a.x, b.x)), y = Math.round(Math.min(a.y, b.y)), w = Math.round(Math.abs(b.x - a.x)), h = Math.round(Math.abs(b.y - a.y))
      if (w < 1 || h < 1) { if (mode === 'replace') useEditor.getState().clearSelection(); return }
      applySelection((ctx) => { if (useEditor.getState().marqueeShape === 'ellipse') { ctx.beginPath(); ctx.ellipse(x + w / 2, y + h / 2, w / 2, h / 2, 0, 0, Math.PI * 2); ctx.fill() } else ctx.fillRect(x, y, w, h) }, mode)
    }
    const commitLasso = (pts: Pt[], mode: 'replace' | 'add' | 'subtract') => {
      clearPreview()
      if (pts.length < 3) return
      applySelection((ctx) => { ctx.beginPath(); ctx.moveTo(pts[0].x, pts[0].y); for (const q of pts.slice(1)) ctx.lineTo(q.x, q.y); ctx.closePath(); ctx.fill() }, mode)
    }
    const wandAt = async (p: Pt, mode: 'replace' | 'add' | 'subtract') => {
      const st = useEditor.getState()
      const doc = st.doc; if (!doc) return
      const n = findNode(doc, st.activeId)
      const lp = n?.kind === 'raster' ? st.pixels.get(n.id) : null
      if (!lp) { useSession.getState().toast('Magic wand samples the active raster layer', 'info'); return }
      const x0 = Math.floor(p.x - (n!.x ?? 0)), y0 = Math.floor(p.y - (n!.y ?? 0))
      if (x0 < 0 || y0 < 0 || x0 >= lp.width || y0 >= lp.height) return
      const img = lp.ctx.getImageData(0, 0, lp.width, lp.height).data
      const tol = st.tolerance
      const W = lp.width, H = lp.height
      const idx = (x: number, y: number) => (y * W + x) * 4
      const r0 = img[idx(x0, y0)], g0 = img[idx(x0, y0) + 1], b0 = img[idx(x0, y0) + 2], a0 = img[idx(x0, y0) + 3]
      const out = new Uint8Array(W * H)
      const stack = [y0 * W + x0]
      const seen = new Uint8Array(W * H)
      while (stack.length) {
        const i = stack.pop()!
        if (seen[i]) continue
        seen[i] = 1
        const j = i * 4
        if (Math.abs(img[j] - r0) > tol || Math.abs(img[j + 1] - g0) > tol || Math.abs(img[j + 2] - b0) > tol || Math.abs(img[j + 3] - a0) > tol) continue
        out[i] = 255
        const x = i % W, y = (i - x) / W
        if (x > 0) stack.push(i - 1); if (x < W - 1) stack.push(i + 1); if (y > 0) stack.push(i - W); if (y < H - 1) stack.push(i + W)
      }
      const tmp = document.createElement('canvas'); tmp.width = W; tmp.height = H
      const tctx = tmp.getContext('2d')!
      const id = tctx.createImageData(W, H)
      for (let i = 0, j = 0; i < out.length; i++, j += 4) { id.data[j] = id.data[j + 1] = id.data[j + 2] = 255; id.data[j + 3] = out[i] }
      tctx.putImageData(id, 0, 0)
      applySelection((ctx) => ctx.drawImage(tmp, n!.x ?? 0, n!.y ?? 0), mode)
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
      const [c0, c1] = t.kind === 'mask' ? ['#ffffff', '#000000'] : [st.brush.color, st.brush.background]
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
      ctx.fillStyle = t.kind === 'mask' ? '#ffffff' : st.brush.color
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
    const onDragOver = (e: DragEvent) => { if (e.dataTransfer?.types.includes('text/loom2-assets')) { e.preventDefault(); e.dataTransfer.dropEffect = 'copy' } }
    const onDropAsset = (e: DragEvent) => { const ids = (e.dataTransfer?.getData('text/loom2-assets') || '').split(',').filter(Boolean); if (!ids.length) return; e.preventDefault(); ids.forEach((id) => void useEditor.getState().addLayerFromAsset(id)) }
    host.addEventListener('dragover', onDragOver)
    host.addEventListener('drop', onDropAsset)
    host.addEventListener('pointerdown', onDown)
    host.addEventListener('pointermove', onMove)
    host.addEventListener('pointerup', onUp)
    host.addEventListener('pointercancel', onUp)
    host.addEventListener('dblclick', onDouble)
    host.addEventListener('wheel', onWheel, { passive: false })
    const onContext = (e: MouseEvent) => { e.preventDefault(); if (drag) return; showMenu(e, canvasMenu()) }
    host.addEventListener('contextmenu', onContext)
    return () => {
      host.removeEventListener('dragover', onDragOver); host.removeEventListener('drop', onDropAsset)
      host.removeEventListener('pointerdown', onDown); host.removeEventListener('pointermove', onMove); host.removeEventListener('pointerup', onUp); host.removeEventListener('pointercancel', onUp)
      host.removeEventListener('dblclick', onDouble)
      host.removeEventListener('wheel', onWheel); host.removeEventListener('contextmenu', onContext)
      window.removeEventListener('keydown', onKey); window.removeEventListener('keyup', onKey)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return <div ref={hostRef} className="edit-canvas" />
}
