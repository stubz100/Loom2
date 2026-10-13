// P13 / ST1 (D81): the three.js engine behind the Stage viewport — its own WebGL2 renderer and canvas (separate from Pixi; Edit may
// be on WebGPU), a free camera with OrbitControls, the render camera built from the document's active camera (focal mm on a 36 mm
// sensor at the project aspect, letterboxed when looked through), TransformControls as the gizmo, raycast picking and placement,
// and `sync(doc)` that makes the scene follow the document (objects by id: create, update, remove). The engine never owns project
// data: edits go out through the hooks to the store, and the store's document comes back in through `sync`.
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { TransformControls } from 'three/examples/jsm/controls/TransformControls.js'
import { api } from '../../api/client'
import type { StageCamera, StageDoc, StageObject } from '../../api/types'
import { applyPose, clay, mannequin, POSES, prop, set as buildSet, setMaterial, vfovFor, type Mannequin } from './builders'
import type { Tool, Transform, View } from './stageStore'

export interface EngineHooks {
  onPick: (id: string | null) => void
  onTransformed: (id: string, t: Transform) => void
  onFreeCameraMoved?: () => void
}

interface Entry { holder: THREE.Group; body: THREE.Object3D; doc: StageObject; figure?: Mannequin }

const deg = THREE.MathUtils.radToDeg, rad = THREE.MathUtils.degToRad

export class StageEngine {
  readonly renderer: THREE.WebGLRenderer
  readonly scene = new THREE.Scene()
  readonly free = new THREE.PerspectiveCamera(50, 1, 0.05, 500)
  readonly orbit: OrbitControls
  readonly gizmo: TransformControls
  private shot = new THREE.PerspectiveCamera(40, 16 / 9, 0.05, 500)   // the render camera (the document's active camera)
  private entries = new Map<string, Entry>()
  private camHelpers = new Map<string, THREE.Object3D>()
  private selection = new THREE.BoxHelper(new THREE.Object3D(), 0xf0b040)
  private floor = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0)
  private ray = new THREE.Raycaster()
  private view: View = 'free'
  private aspect = 16 / 9
  private dirty = true
  private raf = 0
  private running = false
  private w = 1
  private h = 1
  private clayMat = clay()
  private setMat = setMaterial()
  private texLoader = new THREE.TextureLoader()
  private disposed = false
  activeCam: StageCamera | null = null
  readonly canvas: HTMLCanvasElement
  private hooks: EngineHooks

  constructor(canvas: HTMLCanvasElement, hooks: EngineHooks) {
    this.canvas = canvas
    this.hooks = hooks
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true })
    this.renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1))
    this.scene.background = new THREE.Color(0x1d1e22)
    this.scene.add(new THREE.HemisphereLight(0xdde3ff, 0x44403a, 1.1))
    const key = new THREE.DirectionalLight(0xffffff, 1.6); key.position.set(4, 8, 6); this.scene.add(key)
    const grid = new THREE.GridHelper(40, 40, 0x555a66, 0x33363d); grid.position.y = 0.001; this.scene.add(grid)
    this.selection.visible = false
    this.scene.add(this.selection)
    this.free.position.set(5, 3.5, 7)
    this.orbit = new OrbitControls(this.free, canvas)
    this.orbit.target.set(0, 1, 0)
    this.orbit.enableDamping = false
    this.orbit.addEventListener('change', () => { this.dirty = true; this.hooks.onFreeCameraMoved?.() })
    this.gizmo = new TransformControls(this.free, canvas)
    this.gizmo.addEventListener('dragging-changed', (e) => { this.orbit.enabled = !(e as unknown as { value: boolean }).value; this.dirty = true })
    this.gizmo.addEventListener('objectChange', () => { this.dirty = true })
    this.gizmo.addEventListener('mouseUp', () => this.commitGizmo())
    this.scene.add(this.gizmo.getHelper())
    this.gizmo.enabled = false
  }

  // ---- lifecycle ----------------------------------------------------------------------------------------------------------------
  start(): void { if (!this.running) { this.running = true; this.tick() } }
  stop(): void { this.running = false; cancelAnimationFrame(this.raf) }
  private tick = (): void => {
    if (!this.running || this.disposed) return
    if (this.dirty) { this.dirty = false; this.renderNow() }
    this.raf = requestAnimationFrame(this.tick)
  }
  invalidate(): void { this.dirty = true }
  resize(w: number, h: number): void {
    this.w = Math.max(1, w); this.h = Math.max(1, h)
    this.renderer.setSize(this.w, this.h, false)
    this.free.aspect = this.w / this.h
    this.free.updateProjectionMatrix()
    this.dirty = true
  }
  dispose(): void {
    this.disposed = true
    this.stop()
    this.gizmo.dispose(); this.orbit.dispose()
    this.scene.traverse((o) => { const m = o as THREE.Mesh; if (m.isMesh) { m.geometry?.dispose(); const mat = m.material as THREE.Material | THREE.Material[]; (Array.isArray(mat) ? mat : [mat]).forEach((x) => x?.dispose()) } })
    this.renderer.dispose()
  }

  // ---- views and cameras ----------------------------------------------------------------------------------------------------------
  setView(view: View): void { this.view = view; this.gizmo.camera = view === 'camera' ? this.shot : this.free; this.orbit.enabled = view === 'free'; this.dirty = true }
  setAspect(aspect: number): void { this.aspect = aspect; this.dirty = true }
  /** The rectangle (canvas px) the render camera's frame occupies — the framing guides draw over it. */
  frameRect(): { x: number; y: number; w: number; h: number } {
    const cw = this.w, ch = this.h
    let w = cw, h = cw / this.aspect
    if (h > ch) { h = ch; w = ch * this.aspect }
    return { x: (cw - w) / 2, y: (ch - h) / 2, w, h }
  }
  private applyShot(cam: StageCamera | null): void {
    this.activeCam = cam
    if (!cam) return
    this.shot.fov = vfovFor(cam.focal_mm, cam.sensor_mm, this.aspect)
    this.shot.aspect = this.aspect
    this.shot.position.set(cam.pos[0], cam.pos[1], cam.pos[2])
    this.shot.up.set(0, 1, 0)
    this.shot.lookAt(cam.target[0], cam.target[1], cam.target[2])
    this.shot.rotateZ(rad(cam.roll))
    this.shot.updateProjectionMatrix()
  }
  /** The free view's pose, for "Set from view". */
  freePose(): { pos: number[]; target: number[] } {
    const p = this.free.position, t = this.orbit.target
    return { pos: [+p.x.toFixed(3), +p.y.toFixed(3), +p.z.toFixed(3)], target: [+t.x.toFixed(3), +t.y.toFixed(3), +t.z.toFixed(3)] }
  }
  /** Move the free view onto a camera (Look through, then edit from there). */
  freeToCamera(cam: StageCamera): void {
    this.free.position.set(cam.pos[0], cam.pos[1], cam.pos[2])
    this.orbit.target.set(cam.target[0], cam.target[1], cam.target[2])
    this.orbit.update()
    this.dirty = true
  }
  /** Fit the free view to objects (or everything). */
  frame(ids: string[] | null): void {
    const box = new THREE.Box3()
    const list = ids ? ids.map((i) => this.entries.get(i)?.holder).filter((x): x is THREE.Group => !!x) : [...this.entries.values()].map((e) => e.holder)
    if (!list.length) { box.set(new THREE.Vector3(-3, 0, -3), new THREE.Vector3(3, 2, 3)) } else list.forEach((o) => box.expandByObject(o))
    const c = box.getCenter(new THREE.Vector3()), r = Math.max(0.5, box.getSize(new THREE.Vector3()).length() / 2)
    const dir = this.free.position.clone().sub(this.orbit.target).normalize()
    if (!dir.lengthSq()) dir.set(0.6, 0.5, 1).normalize()
    this.orbit.target.copy(c)
    this.free.position.copy(c).add(dir.multiplyScalar(r / Math.tan(rad(this.free.fov / 2)) * 1.1))
    this.orbit.update()
    this.dirty = true
  }

  // ---- tools --------------------------------------------------------------------------------------------------------------------
  setTool(tool: Tool, snap: boolean): void {
    if (tool === 'select') { this.gizmo.enabled = false; this.gizmo.detach() } else {
      this.gizmo.setMode(tool === 'move' ? 'translate' : tool === 'rotate' ? 'rotate' : 'scale')
      this.gizmo.enabled = true
      const sel = this.selectedId
      if (sel) this.attach(sel)
    }
    this.gizmo.setTranslationSnap(snap ? 0.25 : null)
    this.gizmo.setRotationSnap(snap ? rad(15) : null)
    this.gizmo.setScaleSnap(snap ? 0.1 : null)
    this.dirty = true
  }
  private selectedId: string | null = null
  select(id: string | null): void {
    this.selectedId = id
    const e = id ? this.entries.get(id) : undefined
    if (e && this.gizmo.enabled && !e.doc.locked) this.attach(id!); else this.gizmo.detach()
    this.selection.visible = !!e
    if (e) { this.selection.setFromObject(e.holder) }
    this.dirty = true
  }
  private attach(id: string): void {
    const e = this.entries.get(id)
    if (e && !e.doc.locked) this.gizmo.attach(e.holder)
  }
  private commitGizmo(): void {
    const o = this.gizmo.object as THREE.Group | undefined
    if (!o) return
    const id = [...this.entries.entries()].find(([, e]) => e.holder === o)?.[0]
    if (!id) return
    const r = o.rotation
    this.hooks.onTransformed(id, { pos: [o.position.x, o.position.y, o.position.z].map((v) => +v.toFixed(4)), rot: [deg(r.x), deg(r.y), deg(r.z)].map((v) => +v.toFixed(2)), scale: [o.scale.x, o.scale.y, o.scale.z].map((v) => +v.toFixed(4)) })
  }

  // ---- picking and placement ----------------------------------------------------------------------------------------------------
  private ndc(x: number, y: number): THREE.Vector2 {
    const r = this.canvas.getBoundingClientRect()
    return new THREE.Vector2(((x - r.left) / r.width) * 2 - 1, -((y - r.top) / r.height) * 2 + 1)
  }
  private camera(): THREE.Camera { return this.view === 'camera' ? this.shot : this.free }
  /** The object under a client-space point, or null. */
  pick(x: number, y: number): string | null {
    this.ray.setFromCamera(this.ndc(x, y), this.camera())
    const hits = this.ray.intersectObjects([...this.entries.values()].map((e) => e.body), true)
    for (const h of hits) {
      let o: THREE.Object3D | null = h.object
      while (o) { const id = o.userData.stageId as string | undefined; if (id) return id; o = o.parent }
    }
    return null
  }
  /** Where a client-space point lands: the first object surface hit, else the floor; null when the ray misses the floor too. */
  place(x: number, y: number): number[] | null {
    this.ray.setFromCamera(this.ndc(x, y), this.camera())
    const hits = this.ray.intersectObjects([...this.entries.values()].filter((e) => e.doc.kind === 'set').map((e) => e.body), true)
    if (hits.length) { const p = hits[0].point; return [+p.x.toFixed(3), +Math.max(0, p.y).toFixed(3), +p.z.toFixed(3)] }
    const p = new THREE.Vector3()
    if (this.ray.ray.intersectPlane(this.floor, p)) return [+p.x.toFixed(3), 0, +p.z.toFixed(3)]
    return null
  }
  /** The viewport's centre on the floor — where "Add" puts things. */
  centre(): number[] { const r = this.canvas.getBoundingClientRect(); return this.place(r.left + r.width / 2, r.top + r.height / 2) ?? [0, 0, 0] }

  // ---- the document → the scene ---------------------------------------------------------------------------------------------------
  sync(doc: StageDoc): void {
    const seen = new Set<string>()
    for (const o of doc.objects) {
      seen.add(o.id)
      let e = this.entries.get(o.id)
      if (!e || e.doc.kind !== o.kind || e.doc.preset !== o.preset || e.doc.asset_id !== o.asset_id) {
        if (e) { this.scene.remove(e.holder) }
        e = this.build(o)
        this.entries.set(o.id, e)
        this.scene.add(e.holder)
      }
      const t = o.transform
      e.holder.position.set(t.pos[0], t.pos[1], t.pos[2])
      e.holder.rotation.set(rad(t.rot[0]), rad(t.rot[1]), rad(t.rot[2]))
      e.holder.scale.set(t.scale[0], t.scale[1], t.scale[2])
      e.holder.visible = o.visible
      if (e.figure && o.pose && (e.doc.pose?.preset !== o.pose.preset || JSON.stringify(e.doc.pose?.joints) !== JSON.stringify(o.pose.joints))) {
        applyPose(e.figure.joints, POSES[o.pose.preset ?? 'stand'] ?? POSES.stand, o.pose.joints)
      }
      e.doc = o
    }
    for (const [id, e] of [...this.entries]) if (!seen.has(id)) { this.scene.remove(e.holder); this.entries.delete(id); if (this.selectedId === id) this.select(null) }
    // cameras: helpers for the inactive ones, the active one drives the render camera
    const cams = new Set(doc.cameras.map((c) => c.id))
    for (const [id, h] of [...this.camHelpers]) if (!cams.has(id)) { this.scene.remove(h); this.camHelpers.delete(id) }
    for (const c of doc.cameras) {
      let h = this.camHelpers.get(c.id)
      if (!h) { h = this.cameraGlyph(); this.camHelpers.set(c.id, h); this.scene.add(h) }
      h.position.set(c.pos[0], c.pos[1], c.pos[2]); h.lookAt(c.target[0], c.target[1], c.target[2])
      h.visible = this.view === 'free'
      ;(h.children[0] as THREE.Mesh).material = c.id === doc.active_camera ? this.camActiveMat : this.camMat
    }
    this.applyShot(doc.cameras.find((c) => c.id === doc.active_camera) ?? doc.cameras[0] ?? null)
    if (this.selectedId && this.entries.has(this.selectedId)) this.selection.setFromObject(this.entries.get(this.selectedId)!.holder)
    this.dirty = true
  }
  private camMat = new THREE.MeshBasicMaterial({ color: 0x8899bb, wireframe: true })
  private camActiveMat = new THREE.MeshBasicMaterial({ color: 0xf0b040, wireframe: true })
  private cameraGlyph(): THREE.Object3D {
    const g = new THREE.Group()
    const body = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.16, 0.3), this.camMat); g.add(body)
    const lens = new THREE.Mesh(new THREE.ConeGeometry(0.1, 0.2, 4, 1, true), this.camMat); lens.rotation.x = -Math.PI / 2; lens.position.z = 0.25; g.add(lens)
    return g
  }
  private build(o: StageObject): Entry {
    const holder = new THREE.Group()
    holder.userData.stageId = o.id
    let body: THREE.Object3D
    let figure: Mannequin | undefined
    if (o.kind === 'mannequin') {
      figure = mannequin(this.clayMat, POSES[o.pose?.preset ?? 'stand'] ?? POSES.stand, o.pose?.joints)
      body = figure.root
    } else if (o.kind === 'set') body = buildSet(o.preset ?? 'empty', this.setMat)
    else if (o.kind === 'prop') body = prop(o.preset ?? 'block', this.clayMat)
    else if (o.kind === 'plane' && o.asset_id) {
      const mat = new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide, transparent: true })
      const mesh = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 0.9), mat)
      mesh.position.y = 0.9
      this.texLoader.load(api.assetUrl(o.asset_id), (tex) => {
        tex.colorSpace = THREE.SRGBColorSpace
        mat.map = tex; mat.needsUpdate = true
        const img = tex.image as { width?: number; height?: number }
        if (img?.width && img?.height) { mesh.scale.set(1, (img.height / img.width) / (0.9 / 1.6), 1) }
        this.dirty = true
      })
      body = mesh
    } else body = prop('block', this.clayMat)
    body.traverse((c) => { c.userData.stageId = o.id })
    holder.add(body)
    return { holder, body, doc: o, figure }
  }

  // ---- render ---------------------------------------------------------------------------------------------------------------------
  private renderNow(): void {
    const r = this.renderer
    for (const e of this.entries.values()) if (e.doc.kind === 'plane' && e.doc.billboard) e.body.lookAt(this.camera().position)
    if (this.view === 'camera' && this.activeCam) {
      const f = this.frameRect()
      r.setScissorTest(false); r.setViewport(0, 0, this.w, this.h); r.setClearColor(0x0a0a0c, 1); r.clear()
      r.setViewport(f.x, this.h - f.y - f.h, f.w, f.h); r.setScissor(f.x, this.h - f.y - f.h, f.w, f.h); r.setScissorTest(true)
      r.setClearColor(0x1d1e22, 1)
      for (const h of this.camHelpers.values()) h.visible = false
      r.render(this.scene, this.shot)
      r.setScissorTest(false)
    } else {
      r.setViewport(0, 0, this.w, this.h); r.setClearColor(0x1d1e22, 1)
      for (const h of this.camHelpers.values()) h.visible = true
      r.render(this.scene, this.free)
    }
  }
}
