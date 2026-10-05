// The PixiJS stage for the Edit suite (10 §2, 05 §3b): one Application, a world container with the document's
// layers as sprites (masks as alpha masks, groups as containers, blend modes from the advanced set), a selection
// overlay, a checkerboard, and the pointer handling for the tools (brush, eraser, move, hand, zoom, marquee, lasso,
// wand, fill, eyedropper).
import { Application, ColorMatrixFilter, Container, Graphics, Matrix, Rectangle, RendererType, RenderTexture, Sprite, Texture, TilingSprite, UPDATE_PRIORITY } from 'pixi.js'
import 'pixi.js/advanced-blend-modes'
import { useEffect, useRef } from 'react'
import { useSession } from '../../store/session'
import { showMenu } from '../../frame/ContextMenu'
import { ensureAdjustment } from './adjustFilters'
import { blendName } from './blendModes'
import { canvasMenu } from './editCommands'
import { findNode, useEditor, type Node } from './editorStore'
import { makeDab, selectionAlphaCanvas, type LayerPixels } from './layerPixels'

/** Inverts RGB (keeps alpha) and adds: red where a mask/selection is black, nothing where it is white. */
function negativeAdd(): ColorMatrixFilter { const f = new ColorMatrixFilter(); f.negative(false); f.blendMode = 'add'; return f }

function checkerTexture(): Texture {
  const c = document.createElement('canvas'); c.width = c.height = 16
  const ctx = c.getContext('2d')!
  ctx.fillStyle = '#2a2a2a'; ctx.fillRect(0, 0, 16, 16)
  ctx.fillStyle = '#3a3a3a'; ctx.fillRect(0, 0, 8, 8); ctx.fillRect(8, 8, 8, 8)
  return Texture.from(c)
}

type Pt = { x: number; y: number }

export function EditorCanvas() {
  const hostRef = useRef<HTMLDivElement>(null)
  const appRef = useRef<Application | null>(null)
  const worldRef = useRef<Container | null>(null)
  const layersRef = useRef<Container | null>(null)
  const overlayRef = useRef<Container | null>(null)
  const spritesRef = useRef<Map<string, Sprite | Container>>(new Map())
  const passesRef = useRef<{ rt: RenderTexture; content: Container; transform: Matrix; dirty: boolean }[]>([])
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

  // ---- app lifecycle --------------------------------------------------------------------------
  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    let cancelled = false
    const app = new Application()
    void app.init({ preference: 'webgpu', background: 0x141414, antialias: false, resolution: window.devicePixelRatio || 1, autoDensity: true, resizeTo: host, powerPreference: 'high-performance' }).then(() => {
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
      useEditor.getState().setRenderer(app.renderer.type === RendererType.WEBGPU ? 'WebGPU' : app.renderer.type === RendererType.WEBGL ? 'WebGL2' : 'canvas')
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
      app.ticker.add(renderPasses, undefined, UPDATE_PRIORITY.HIGH)   // passes render before the stage each frame
      useEditor.getState().bump()
      useEditor.getState().requestFit()
    })
    return () => {
      cancelled = true
      useEditor.getState().setExtractor(null)
      for (const p of passesRef.current) p.rt.destroy(true)
      passesRef.current = []
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
    layers.removeChildren()
    spritesRef.current.clear()
    if (doc.background !== 'transparent') {
      const g = new Graphics().rect(0, 0, doc.w, doc.h).fill(doc.background)
      layers.addChild(g)
    }
    const activeNode = findNode(doc, st.activeId)
    for (const p of passesRef.current) p.rt.destroy(true)
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
    renderPasses()
    // selection / quick-mask / mask-editing overlays
    const ov = overlayRef.current!
    ov.removeChildren()
    const sel = st.selection
    if (sel && overlay) {
      // selection: additive orange tint on the selected area; quick mask: additive red where NOT selected
      const s = new Sprite(sel.texture)
      s.blendMode = 'add'
      if (quickMask) { s.filters = [negativeAdd()]; s.tint = 0xff2020; s.alpha = 0.5 } else { s.tint = 0xf0a63a; s.alpha = 0.25 }
      ov.addChild(s)
    }
    if (editingMask && activeNode?.mask && overlay) {
      const m = st.masks.get(activeNode.id)
      if (m) {
        const s = new Sprite(m.texture)
        s.position.set((activeNode.mask.linked ? (activeNode.x ?? 0) : 0) + activeNode.mask.x, (activeNode.mask.linked ? (activeNode.y ?? 0) : 0) + activeNode.mask.y)
        s.blendMode = 'add'; s.filters = [negativeAdd()]; s.tint = 0xff2020; s.alpha = 0.45
        ov.addChild(s)
      }
    }
  }, [doc, revision, before, overlay, quickMask, editingMask, activeId])

  // ---- view (zoom / pan / fit), document frame and pixel grid -------------------------------------
  useEffect(() => {
    const world = worldRef.current, app = appRef.current, ov = overlayRef.current, host = hostRef.current
    if (!world || !app) return
    world.scale.set(zoom); world.position.set(pan.x, pan.y)
    if (!ov || !doc || !host) return
    let g = ov.getChildByLabel('frame') as Graphics | null
    if (!g) { g = new Graphics(); g.label = 'frame'; ov.addChild(g) }
    g.clear()
    g.rect(0, 0, doc.w, doc.h).stroke({ color: 0x555555, width: 1 / zoom })
    if (pixelGrid && zoom >= 8) {
      const x0 = Math.max(0, Math.floor(-pan.x / zoom)), y0 = Math.max(0, Math.floor(-pan.y / zoom))
      const x1 = Math.min(doc.w, Math.ceil((host.clientWidth - pan.x) / zoom)), y1 = Math.min(doc.h, Math.ceil((host.clientHeight - pan.y) / zoom))
      for (let x = x0; x <= x1; x++) g.moveTo(x, y0).lineTo(x, y1)
      for (let y = y0; y <= y1; y++) g.moveTo(x0, y).lineTo(x1, y)
      g.stroke({ color: 0xffffff, width: 1 / zoom, alpha: 0.15 })
    }
  }, [zoom, pan, revision, pixelGrid, doc])
  useEffect(() => {
    const app = appRef.current, host = hostRef.current
    if (!app || !host || !doc) return
    const w = host.clientWidth, h = host.clientHeight
    const z = Math.min((w - 40) / doc.w, (h - 40) / doc.h)
    useEditor.getState().setView({ zoom: z, pan: { x: (w - doc.w * z) / 2, y: (h - doc.h * z) / 2 } })
  }, [fitRequested, doc?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  // ---- input ----------------------------------------------------------------------------------------
  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const toDoc = (e: PointerEvent | WheelEvent): Pt => {
      const r = host.getBoundingClientRect()
      const st = useEditor.getState()
      return { x: (e.clientX - r.left - st.pan.x) / st.zoom, y: (e.clientY - r.top - st.pan.y) / st.zoom }
    }
    let drag: null | { kind: 'pan' | 'paint' | 'move' | 'marquee' | 'lasso'; start: Pt; last: Pt; startPan?: Pt; nodeStart?: Pt; pts?: Pt[]; target?: LayerPixels; dab?: HTMLCanvasElement; dist?: number; spaceHeld?: boolean } = null
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
        t.lp.refresh()
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
      if (tool === 'fill') { fillAt(p); return }
    }
    const onMove = (e: PointerEvent) => {
      const st = useEditor.getState()
      const p = toDoc(e)
      st.setCursor({ x: Math.floor(p.x), y: Math.floor(p.y) })
      if (!drag) return
      if (drag.kind === 'pan') { st.setView({ pan: { x: drag.startPan!.x + e.clientX - drag.start.x, y: drag.startPan!.y + e.clientY - drag.start.y } }); return }
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
        return
      }
      if (drag.kind === 'move') {
        const n = findNode(st.doc, st.activeId)
        if (!n) return
        const nx = Math.round(drag.nodeStart!.x + p.x - drag.start.x), ny = Math.round(drag.nodeStart!.y + p.y - drag.start.y)
        const sp = spritesRef.current.get(n.id) as Sprite | undefined
        if (sp) sp.position.set(nx, ny)
        drag.last = { x: nx, y: ny }
        return
      }
      if (drag.kind === 'marquee') { drag.last = p; previewMarquee(drag.start, p); return }
      if (drag.kind === 'lasso') { drag.pts!.push(p); drag.last = p; previewLasso(drag.pts!); return }
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
      drag = null
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
      const px = await app.renderer.extract.pixels({ target: layers, frame: { x: Math.floor(p.x), y: Math.floor(p.y), width: 1, height: 1 } as never })
      const d = px.pixels
      const hex = '#' + [d[0], d[1], d[2]].map((v) => v.toString(16).padStart(2, '0')).join('')
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
    }
    const clearPreview = () => { const ov = overlayRef.current; const g = ov?.getChildByLabel('preview'); if (g) g.destroy() }
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
    host.addEventListener('pointerdown', onDown)
    host.addEventListener('pointermove', onMove)
    host.addEventListener('pointerup', onUp)
    host.addEventListener('pointercancel', onUp)
    host.addEventListener('wheel', onWheel, { passive: false })
    const onContext = (e: MouseEvent) => { e.preventDefault(); if (drag) return; showMenu(e, canvasMenu()) }
    host.addEventListener('contextmenu', onContext)
    return () => {
      host.removeEventListener('pointerdown', onDown); host.removeEventListener('pointermove', onMove); host.removeEventListener('pointerup', onUp); host.removeEventListener('pointercancel', onUp)
      host.removeEventListener('wheel', onWheel); host.removeEventListener('contextmenu', onContext)
      window.removeEventListener('keydown', onKey); window.removeEventListener('keyup', onKey)
    }
  }, [])

  return <div ref={hostRef} className="edit-canvas" />
}
