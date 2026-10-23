// P13 / ST1 (D81): the three.js engine behind the Stage viewport — its own WebGL2 renderer and canvas (separate from Pixi; Edit may
// be on WebGPU), a free camera with OrbitControls, the render camera built from the document's active camera (focal mm on a 36 mm
// sensor at the project aspect, letterboxed when looked through), TransformControls as the gizmo, raycast picking and placement,
// and `sync(doc)` that makes the scene follow the document (objects by id: create, update, remove). The engine never owns project
// data: edits go out through the hooks to the store, and the store's document comes back in through `sync`.
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { TransformControls } from 'three/examples/jsm/controls/TransformControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import { api } from '../../api/client'
import type { StageCamera, StageDoc, StageObject } from '../../api/types'
import { applyPose, clay, JOINTS, mannequin, POSES, prop, set as buildSet, setMaterial, vfovFor, type Body, type Joint, type Mannequin } from './builders'
import { CHAINS, eulerDeg, figureChain, solveTwoBone, type Chain } from './ik'
import { makeDetailed, type Detailed, type HandPreset } from './detailed'
import { measure } from './motion/path'
import { bindProxy, type Proxy } from './proxy'
import { depthMaterial, depthRange, drawPose, maskColour, projectMarkers, toBlob, type Keypoint, type PassName, type WholeBody } from './passes'
import type { RenderedPasses, Tool, Transform, View } from './stageStore'

export interface EngineHooks {
  onPick: (id: string | null) => void
  onTransformed: (id: string, t: Transform) => void
  /** ST2: a joint was rotated or a hand / foot dragged — the figure's full joint map in degrees (YXZ). */
  onPosed: (id: string, joints: Record<string, number[]>) => void
  onDetailError?: (id: string, message: string) => void          // CA1: the Detailed mannequin could not load (the figure stays Simple)
  onFreeCameraMoved?: () => void
  /** P18: a mesh asset's GLB arrived and a fitted view of it is ready — the store may make it the asset's thumbnail. */
  onMeshThumb?: (assetId: string, view: Blob) => void
  /** D119 (SC1): a camera's body was clicked in the free view, or dragged there (its new position; the store moves its target along). */
  onPickCamera?: (id: string) => void
  onCameraMoved?: (id: string, pos: number[]) => void
  onCameraTurned?: (id: string, target: number[], roll: number) => void     // the camera's body turned with the rotate tool: a new target at the old distance, the roll about it
}
export interface Pick { id: string | null; joint?: Joint; ik?: Chain; camera?: string }

interface Entry { holder: THREE.Group; body: THREE.Object3D; doc: StageObject; figure?: Mannequin; pickers?: THREE.Object3D[]; detailed?: Detailed; proxy?: Proxy }

const deg = THREE.MathUtils.radToDeg, rad = THREE.MathUtils.degToRad
const BEAUTY_ENV = 0.8                            // D109: the beauty pass's room-environment intensity (E28c: the models read near the plate's brightness)

export class StageEngine {
  readonly renderer: THREE.WebGLRenderer
  readonly scene = new THREE.Scene()
  readonly free = new THREE.PerspectiveCamera(50, 1, 0.05, 500)
  readonly orbit: OrbitControls
  readonly gizmo: TransformControls
  private shot = new THREE.PerspectiveCamera(40, 16 / 9, 0.05, 500)   // the render camera (the document's active camera)
  private entries = new Map<string, Entry>()
  private camHelpers = new Map<string, THREE.Object3D>()
  private camTargets = new Map<string, number[]>()                   // each camera's target as last synced (the turn keeps its distance)
  private selection = new THREE.BoxHelper(new THREE.Object3D(), 0xf0b040)
  private floor = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0)
  private ray = new THREE.Raycaster()
  private view: View = 'free'
  private pip = false                                              // D121 (AW4): the active camera's picture in the free view's corner
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
  // ST2: posing — pickers show on the selected figure in pose mode; a joint takes the rotate gizmo, a hand / foot a translate proxy
  private poseMode = false
  private posing: { id: string; joint: Joint } | null = null
  private ik: { id: string; chain: Chain; proxy: THREE.Object3D } | null = null
  private pickerMat = new THREE.MeshBasicMaterial({ color: 0xf0b040, depthTest: false, transparent: true, opacity: 0.9 })
  private ikMat = new THREE.MeshBasicMaterial({ color: 0x5ad0ff, depthTest: false, transparent: true, opacity: 0.95 })
  // P18: which mesh objects have their GLB in the scene (the smoke test and the rig ask)
  readonly meshesLoaded = new Set<string>()
  readonly meshesFailed = new Map<string, string>()
  // ST3: the pass materials and the helpers that stay out of the passes
  private grid: THREE.GridHelper
  private passClay = new THREE.MeshLambertMaterial({ color: 0xd8d8d8 })
  private hemi = new THREE.HemisphereLight(0xdde3ff, 0x44403a, 1.1)
  private key = new THREE.DirectionalLight(0xffffff, 1.6)
  private passDepth = depthMaterial()
  private passNormal = new THREE.MeshNormalMaterial()
  // D110 (PS4): the scene's lights — one sun per visible light object (the first three with shadows cast them), each with its aim line;
  // and the viewport's room environment, so a model's PBR material reads as itself (Pixal3D bakes metalness: black without one)
  private lights = new Map<string, { light: THREE.DirectionalLight; aim: THREE.Line }>()
  private aimMat = new THREE.LineDashedMaterial({ color: 0xffd060, dashSize: 0.15, gapSize: 0.1 })
  private viewEnv: THREE.Texture
  readonly canvas: HTMLCanvasElement
  private hooks: EngineHooks

  constructor(canvas: HTMLCanvasElement, hooks: EngineHooks) {
    this.canvas = canvas
    this.hooks = hooks
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true })
    this.renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1))
    this.scene.background = new THREE.Color(0x1d1e22)
    this.scene.add(this.hemi)
    const pm = new THREE.PMREMGenerator(this.renderer)
    this.viewEnv = pm.fromScene(new RoomEnvironment(), 0.04).texture
    pm.dispose()
    this.scene.environment = this.viewEnv; this.scene.environmentIntensity = BEAUTY_ENV
    // E23c (D103): the key light — fixed above and to the front until the stage has a `light` object; then it shines from that light
    // towards the set's middle and casts shadows (the clay pass shows them: the white set's light, contact and shadows)
    this.key.position.set(4, 8, 6); this.scene.add(this.key, this.key.target)
    this.key.shadow.mapSize.set(2048, 2048)
    Object.assign(this.key.shadow.camera, { left: -7, right: 7, top: 7, bottom: -7, near: 0.5, far: 40 })
    this.key.shadow.bias = -0.0004; this.key.shadow.normalBias = 0.02
    this.renderer.shadowMap.enabled = true; this.renderer.shadowMap.type = THREE.PCFShadowMap
    this.grid = new THREE.GridHelper(40, 40, 0x555a66, 0x33363d); this.grid.position.y = 0.001; this.scene.add(this.grid)
    this.selection.visible = false
    this.scene.add(this.selection)
    this.free.position.set(5, 3.5, 7)
    this.orbit = new OrbitControls(this.free, canvas)
    this.orbit.target.set(0, 1, 0)
    this.orbit.enableDamping = false
    this.orbit.addEventListener('change', () => { this.dirty = true; this.hooks.onFreeCameraMoved?.() })
    this.gizmo = new TransformControls(this.free, canvas)
    this.gizmo.addEventListener('dragging-changed', (e) => { this.orbit.enabled = !(e as unknown as { value: boolean }).value; this.dirty = true })
    this.gizmo.addEventListener('objectChange', () => { if (this.ik) this.solveIk(); this.followAll(); this.dirty = true })
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
    for (const l of this.lights.values()) { l.light.shadow.map?.dispose(); l.aim.geometry.dispose() }
    this.viewEnv.dispose()
    this.renderer.dispose()
  }

  // ---- views and cameras ----------------------------------------------------------------------------------------------------------
  setView(view: View): void { this.view = view; this.gizmo.camera = view === 'camera' ? this.shot : this.free; this.orbit.enabled = view === 'free'; if (this.selectedCamId) this.selectCamera(this.selectedCamId); for (const l of this.lights.values()) l.aim.visible = view === 'free'; this.dirty = true }
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
  private tool: Tool = 'select'
  private modeOf(): 'translate' | 'rotate' | 'scale' { return this.tool === 'rotate' ? 'rotate' : this.tool === 'scale' ? 'scale' : 'translate' }
  setTool(tool: Tool, snap: boolean): void {
    this.tool = tool
    if (tool === 'select' || tool === 'path') { this.gizmo.enabled = false; this.gizmo.detach() }
    else if (this.posing) { this.selectJoint(this.posing.id, this.posing.joint) }                                   // the author, 2026-10-22: a joint keeps its rotate gizmo under every tool button
    else if (this.ik) { this.gizmo.setMode('translate'); this.gizmo.setSpace('world'); this.gizmo.enabled = true; this.gizmo.attach(this.ik.proxy) }
    else {
      this.gizmo.setMode(this.modeOf())
      this.gizmo.enabled = true
      const sel = this.selectedId
      if (sel) this.attach(sel)
      else if (this.selectedCamId) this.selectCamera(this.selectedCamId)                 // D119: a camera's body only moves — translate whatever the tool
    }
    this.gizmo.setTranslationSnap(snap ? 0.25 : null)
    this.gizmo.setRotationSnap(snap ? rad(15) : null)
    this.gizmo.setScaleSnap(snap ? 0.1 : null)
    this.dirty = true
  }
  private selectedId: string | null = null
  private selectedCamId: string | null = null
  select(id: string | null): void {
    if (this.selectedId !== id || this.ik) this.endPosing()
    this.selectedId = id
    if (id) this.selectedCamId = null
    const e = id ? this.entries.get(id) : undefined
    if (e && this.gizmo.enabled && !e.doc.locked && !this.posing) this.attach(id!); else if (!this.posing && !this.selectedCamId) this.gizmo.detach()
    this.selection.visible = !!e
    if (e) { this.selection.setFromObject(e.holder) }
    this.showPickers()
    this.dirty = true
  }
  /** D119 (SC1): a camera as the selection — its body takes the translate gizmo in the free view and the selection box. */
  selectCamera(id: string | null): void {
    this.selectedCamId = id
    if (id) { this.endPosing(); this.selectedId = null; this.showPickers() }
    const h = id ? this.camHelpers.get(id) : undefined
    if (h && this.gizmo.enabled && this.view === 'free') { this.gizmo.setMode(this.tool === 'rotate' ? 'rotate' : 'translate'); this.gizmo.setSpace('world'); this.gizmo.showXYZE = true; this.gizmo.attach(h) }   // the author, 2026-10-22: the body turns under Rotate; scale moves
    else if (!this.selectedId && !this.posing) this.gizmo.detach()
    this.selection.visible = !!h && this.view === 'free'
    if (h) this.selection.setFromObject(h)
    this.dirty = true
  }
  /** D119 (SC1): where a camera's body is on the canvas (client px), for a click to land on it — null when it is off screen or hidden. */
  cameraScreen(id: string): { x: number; y: number } | null {
    const h = this.camHelpers.get(id)
    if (!h || !h.visible) return null
    const p = h.position.clone().project(this.camera())
    if (p.z > 1) return null
    const r = this.canvas.getBoundingClientRect()
    return { x: r.left + (p.x + 1) / 2 * r.width, y: r.top + (1 - p.y) / 2 * r.height }
  }
  /** The object takes the gizmo in the tool's mode — a camera's body (translate whatever the tool) or a joint (rotate, local) may have left it
   *  in theirs (the author, 2026-10-22: the rotate tool moved an object selected after a camera). */
  private attach(id: string): void {
    const e = this.entries.get(id)
    if (e && !e.doc.locked) { this.gizmo.setMode(this.modeOf()); this.gizmo.setSpace('world'); this.gizmo.showXYZE = true; this.gizmo.attach(e.holder) }
  }
  /** The gizmo's mode now (the dev hook; the e2e reads it). */
  gizmoMode(): string { return this.gizmo.object ? this.gizmo.mode : 'none' }
  private commitGizmo(): void {
    if (this.posing || this.ik) { this.commitPose(); return }
    const o = this.gizmo.object as THREE.Group | undefined
    if (!o) return
    const camId = o.userData.cameraId as string | undefined
    if (camId) {                                                                                             // D119: a camera's body moved — or turned (the rotate tool)
      if (this.gizmo.mode === 'rotate') {
        const t = this.camTargets.get(camId) ?? [o.position.x, o.position.y, o.position.z - 1]
        const dist = Math.max(0.05, Math.hypot(t[0] - o.position.x, t[1] - o.position.y, t[2] - o.position.z))
        const target = new THREE.Vector3(0, 0, 1).applyQuaternion(o.quaternion).multiplyScalar(dist).add(o.position)
        const ref = new THREE.Object3D(); ref.position.copy(o.position); ref.lookAt(target)                 // what sync would set with roll 0
        const d = ref.quaternion.clone().invert().multiply(o.quaternion)                                   // what is left: a turn about the glyph's own +Z
        let roll = -deg(2 * Math.atan2(d.z, d.w))
        roll = ((roll + 540) % 360) - 180
        this.hooks.onCameraTurned?.(camId, [target.x, target.y, target.z].map((v) => +v.toFixed(4)), +roll.toFixed(2))
        return
      }
      this.hooks.onCameraMoved?.(camId, [o.position.x, o.position.y, o.position.z].map((v) => +v.toFixed(4)))
      return
    }
    const id = [...this.entries.entries()].find(([, e]) => e.holder === o)?.[0]
    if (!id) return
    const r = o.rotation
    this.hooks.onTransformed(id, { pos: [o.position.x, o.position.y, o.position.z].map((v) => +v.toFixed(4)), rot: [deg(r.x), deg(r.y), deg(r.z)].map((v) => +v.toFixed(2)), scale: [o.scale.x, o.scale.y, o.scale.z].map((v) => +v.toFixed(4)) })
  }

  // ---- ST2: posing ----------------------------------------------------------------------------------------------------------------
  setPoseMode(on: boolean): void { this.poseMode = on; if (!on) this.endPosing(); this.showPickers(); this.dirty = true }
  private showPickers(): void {
    for (const [id, e] of this.entries) e.pickers?.forEach((p) => { p.visible = this.poseMode && id === this.selectedId && e.doc.visible })
  }
  /** The rotate gizmo on one joint (local space): dragging it is FK; the commit writes every joint back. */
  selectJoint(id: string, joint: Joint | null): void {
    if (!joint && this.ik?.id === id) return                       // clearing the joint while a hand / foot handle is live keeps that handle
    this.endIk()
    const e = this.entries.get(id)
    if (!e?.figure || !joint) { this.posing = null; if (this.gizmo.enabled && e && !e.doc.locked) this.attach(id); else this.gizmo.detach(); this.dirty = true; return }
    this.posing = { id, joint }
    this.gizmo.setMode('rotate')
    this.gizmo.setSpace('local')
    this.gizmo.showXYZE = false                                    // no free-rotate ball: it would cover the neighbouring pickers (a joint is ~30 px from the next)
    this.gizmo.enabled = true
    this.gizmo.attach(e.figure.joints[joint])
    this.dirty = true
  }
  /** A hand or a foot: a translate proxy at the end, the two bones follow while it moves. */
  startIk(id: string, chain: Chain): void {
    const e = this.entries.get(id)
    if (!e?.figure) return
    this.endPosing()
    const c = figureChain(e.figure.limbs, chain)
    const lower = e.figure.joints[c.lower]
    const proxy = new THREE.Object3D()
    proxy.position.copy(lower.localToWorld(new THREE.Vector3(0, -c.b, 0)))
    this.scene.add(proxy)
    this.ik = { id, chain, proxy }
    this.gizmo.setMode('translate')
    this.gizmo.setSpace('world')
    this.gizmo.enabled = true
    this.gizmo.attach(proxy)
    this.dirty = true
  }
  private solveIk(): void {
    if (!this.ik) return
    const e = this.entries.get(this.ik.id)
    if (!e?.figure) return
    const c = figureChain(e.figure.limbs, this.ik.chain)
    const upper = e.figure.joints[c.upper], lower = e.figure.joints[c.lower]
    const parent = upper.parent!
    parent.updateWorldMatrix(true, false)
    const target = parent.worldToLocal(this.ik.proxy.getWorldPosition(new THREE.Vector3()))
    const s = solveTwoBone(upper.position, target, c.a, c.b, new THREE.Vector3(...c.bend))
    upper.rotation.set(rad(s.upper[0]), rad(s.upper[1]), rad(s.upper[2]), 'YXZ')
    lower.rotation.set(rad(s.lower[0]), rad(s.lower[1]), rad(s.lower[2]), 'YXZ')
    this.selection.setFromObject(e.holder)
  }
  /** Every joint of the figure, degrees YXZ — what the document stores. */
  jointsOf(id: string): Record<string, number[]> | null {
    const e = this.entries.get(id)
    if (!e?.figure) return null
    const out: Record<string, number[]> = {}
    for (const j of JOINTS) out[j] = eulerDeg(e.figure.joints[j].quaternion)
    return out
  }
  private commitPose(): void {
    const id = this.posing?.id ?? this.ik?.id
    if (!id) return
    const joints = this.jointsOf(id)
    if (joints) this.hooks.onPosed(id, joints)
    if (this.ik) this.endIk()
  }
  private endIk(): void { if (this.ik) { this.scene.remove(this.ik.proxy); this.ik = null; this.gizmo.detach(); this.gizmo.enabled = false } }
  private endPosing(): void { this.endIk(); if (this.posing) { this.posing = null; this.gizmo.detach() } }

  // ---- picking and placement ----------------------------------------------------------------------------------------------------
  /** Client → NDC of the camera being looked through: the whole canvas in the free view, the letterboxed frame in the camera view. */
  private ndc(x: number, y: number): THREE.Vector2 {
    const r = this.canvas.getBoundingClientRect()
    const f = this.view === 'camera' ? this.frameRect() : { x: 0, y: 0, w: this.w, h: this.h }
    return new THREE.Vector2(((x - r.left - f.x) / f.w) * 2 - 1, -((y - r.top - f.y) / f.h) * 2 + 1)
  }
  /** Client-space position of a joint or an IK handle of the selected figure (the dev hook and the smoke test drive the mouse with it). */
  screenOf(at: Joint | Chain): { x: number; y: number } | null {
    const e = this.selectedId ? this.entries.get(this.selectedId) : undefined
    if (!e?.figure) return null
    e.holder.updateWorldMatrix(true, true)
    const c = at in CHAINS ? figureChain(e.figure.limbs, at as Chain) : undefined
    const p = c ? e.figure.joints[c.lower].localToWorld(new THREE.Vector3(0, -c.b, 0)) : e.figure.joints[at as Joint].getWorldPosition(new THREE.Vector3())
    p.project(this.camera())
    const r = this.canvas.getBoundingClientRect()
    const f = this.view === 'camera' ? this.frameRect() : { x: 0, y: 0, w: this.w, h: this.h }
    return { x: r.left + f.x + ((p.x + 1) / 2) * f.w, y: r.top + f.y + ((1 - p.y) / 2) * f.h }
  }
  private camera(): THREE.Camera { return this.view === 'camera' ? this.shot : this.free }
  /** What is under a client-space point: an object, a joint picker or an IK handle of the selected figure, or nothing. */
  pick(x: number, y: number): Pick {
    this.ray.setFromCamera(this.ndc(x, y), this.camera())
    // pose mode: the selected figure's pickers first — a joint sphere sits inside its limb, so the body would always win on distance
    const sel = this.selectedId ? this.entries.get(this.selectedId) : undefined
    if (this.poseMode && sel?.pickers && sel.doc.visible) {
      const hit = this.ray.intersectObjects(sel.pickers.filter((p) => p.visible), false)[0]
      if (hit) return hit.object.userData.joint ? { id: this.selectedId, joint: hit.object.userData.joint as Joint } : { id: this.selectedId, ik: hit.object.userData.ik as Chain }
    }
    const hits = this.ray.intersectObjects([...[...this.entries.values()].map((e) => e.body), ...this.camHelpers.values()], true)   // D119: the cameras' bodies too
    for (const h of hits) {
      let hidden = false
      for (let p: THREE.Object3D | null = h.object; p; p = p.parent) if (!p.visible) { hidden = true; break }
      if (hidden || h.object.userData.joint || h.object.userData.ik) continue
      for (let o: THREE.Object3D | null = h.object; o; o = o.parent) {
        const id = o.userData.stageId as string | undefined
        if (id) return { id }
        const cam = o.userData.cameraId as string | undefined
        if (cam) return { id: null, camera: cam }
      }
    }
    return { id: null }
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
      if (!e || e.doc.kind !== o.kind || e.doc.preset !== o.preset || e.doc.asset_id !== o.asset_id || JSON.stringify((e.doc as { body?: unknown }).body ?? null) !== JSON.stringify((o as { body?: unknown }).body ?? null)
        || (e.doc.detail ?? null) !== (o.detail ?? null) || (e.doc.shadow_proxy ?? null) !== (o.shadow_proxy ?? null) || (e.doc.floor_y ?? null) !== (o.floor_y ?? null)) {
        if (e) { this.scene.remove(e.holder); e.proxy?.dispose() }
        e = this.build(o)
        this.entries.set(o.id, e)
        this.scene.add(e.holder)
      }
      const t = o.transform
      e.holder.position.set(t.pos[0], t.pos[1], t.pos[2])
      e.holder.rotation.set(rad(t.rot[0]), rad(t.rot[1]), rad(t.rot[2]))
      e.holder.scale.set(t.scale[0], t.scale[1], t.scale[2])
      e.holder.visible = o.visible
      e.proxy?.meshes.forEach((m) => { m.visible = o.visible })                     // E23d: a hidden figure's proxy casts nothing
      if (e.figure && o.pose && !this.ik && (e.doc.pose?.preset !== o.pose.preset || JSON.stringify(e.doc.pose?.joints) !== JSON.stringify(o.pose.joints))) {
        applyPose(e.figure.joints, POSES[o.pose.preset ?? 'stand'] ?? POSES.stand, o.pose.joints)
      }
      e.doc = o
    }
    for (const [id, e] of [...this.entries]) if (!seen.has(id)) { this.scene.remove(e.holder); e.proxy?.dispose(); this.entries.delete(id); if (this.selectedId === id) this.select(null) }
    this.syncLight(doc)
    this.followAll()
    this.syncPaths(doc)
    // cameras: helpers for the inactive ones, the active one drives the render camera
    const cams = new Set(doc.cameras.map((c) => c.id))
    for (const [id, h] of [...this.camHelpers]) if (!cams.has(id)) { this.scene.remove(h); this.camHelpers.delete(id) }
    for (const c of doc.cameras) {
      let h = this.camHelpers.get(c.id)
      if (!h) { h = this.cameraGlyph(c.id); this.camHelpers.set(c.id, h); this.scene.add(h) }
      this.camTargets.set(c.id, c.target)
      if (!(this.gizmo.dragging && this.gizmo.object === h)) {                                              // D119: not under the hand that drags or turns it
        h.position.set(c.pos[0], c.pos[1], c.pos[2])
        h.lookAt(c.target[0], c.target[1], c.target[2])
        h.rotateZ(rad(-c.roll))                                                                            // the glyph looks down +Z, the camera down −Z: the roll turns the other way
      }
      h.visible = this.view === 'free'
      ;(h.children[0] as THREE.Mesh).material = c.id === doc.active_camera ? this.camActiveMat : this.camMat
    }
    if (this.selectedCamId && !cams.has(this.selectedCamId)) this.selectCamera(null)
    else if (this.selectedCamId) { const h = this.camHelpers.get(this.selectedCamId); if (h) this.selection.setFromObject(h); this.selection.visible = this.view === 'free' }
    this.applyShot(doc.cameras.find((c) => c.id === doc.active_camera) ?? doc.cameras[0] ?? null)
    if (this.selectedId && this.entries.has(this.selectedId)) this.selection.setFromObject(this.entries.get(this.selectedId)!.holder)
    this.dirty = true
  }
  /** E23c, D110 (PS4): each visible `light` object is a sun from its position towards its aim, with its strength, colour and shadow (the
   *  first three that cast one; its softness the shadow map's blur radius); a light without settings shines as E23c's key (2.3, white,
   *  hard, a metre above the origin). The sky (hemisphere) is the stage's ambient level — 0.85 under lights, 1.1 without. With no light,
   *  the fixed key of before, without shadows. */
  private syncLight(doc: StageDoc): void {
    const on = doc.objects.filter((o) => o.kind === 'light' && o.visible)
    for (const [id, l] of [...this.lights]) if (!on.some((o) => o.id === id)) { this.scene.remove(l.light, l.light.target, l.aim); l.light.shadow.map?.dispose(); l.aim.geometry.dispose(); this.lights.delete(id) }
    let shadows = 0
    for (const o of on) {
      let l = this.lights.get(o.id)
      if (!l) {
        const light = new THREE.DirectionalLight(0xffffff, 2.3)
        light.shadow.mapSize.set(2048, 2048)
        Object.assign(light.shadow.camera, { left: -7, right: 7, top: 7, bottom: -7, near: 0.5, far: 40 })
        light.shadow.bias = -0.0004; light.shadow.normalBias = 0.02
        const aim = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]), this.aimMat)
        aim.userData.helper = true
        l = { light, aim }
        this.lights.set(o.id, l)
        this.scene.add(light, light.target, aim)
      }
      const s = o.light ?? { intensity: 2.3, colour: '#ffffff', softness: 0, shadows: true, target: [0, 1, 0] }
      const p = o.transform.pos, t = s.target
      l.light.position.set(p[0], p[1], p[2]); l.light.target.position.set(t[0], t[1], t[2]); l.light.target.updateMatrixWorld()
      l.light.intensity = s.intensity; l.light.color.set(s.colour)
      l.light.castShadow = s.shadows && shadows < 3
      if (l.light.castShadow) shadows++
      l.light.shadow.radius = 1 + s.softness * 7
      l.aim.geometry.setFromPoints([new THREE.Vector3(p[0], p[1], p[2]), new THREE.Vector3(t[0], t[1], t[2])]); l.aim.computeLineDistances()
      l.aim.visible = this.view === 'free'
    }
    this.key.visible = !on.length; this.key.castShadow = false
    this.key.position.set(4, 8, 6); this.key.target.position.set(0, 0, 0); this.key.intensity = 1.6; this.key.target.updateMatrixWorld()
    this.hemi.intensity = doc.ambient ?? (on.length ? 0.85 : 1.1)
  }
  private camMat = new THREE.MeshBasicMaterial({ color: 0x8899bb, wireframe: true })
  private camActiveMat = new THREE.MeshBasicMaterial({ color: 0xf0b040, wireframe: true })
  private cameraGlyph(id: string): THREE.Object3D {
    const g = new THREE.Group()
    g.userData.cameraId = id                                           // D119 (SC1): picked and dragged like an object
    const body = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.16, 0.3), this.camMat); g.add(body)
    const lens = new THREE.Mesh(new THREE.ConeGeometry(0.1, 0.2, 4, 1, true), this.camMat); lens.rotation.x = -Math.PI / 2; lens.position.z = 0.25; g.add(lens)
    return g
  }
  private build(o: StageObject): Entry {
    const holder = new THREE.Group()
    holder.userData.stageId = o.id
    let body: THREE.Object3D
    let figure: Mannequin | undefined
    let pickers: THREE.Object3D[] | undefined
    if (o.kind === 'mannequin') {
      figure = mannequin(this.clayMat, POSES[o.pose?.preset ?? 'stand'] ?? POSES.stand, o.pose?.joints, (o as { body?: Body | null }).body)   // CA0: the bound character's body
      body = figure.root
      // ST2: a picker sphere on every joint (FK) and a handle at each hand and foot (IK), hidden until pose mode
      pickers = []
      for (const j of JOINTS) {
        const m = new THREE.Mesh(new THREE.SphereGeometry(0.045, 10, 8), this.pickerMat)
        m.userData.joint = j; m.renderOrder = 10; m.visible = false
        figure.joints[j].add(m); pickers.push(m)
      }
      for (const [chain, c] of Object.entries(CHAINS)) {
        const m = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.07, 0.07), this.ikMat)
        m.position.set(0, -figureChain(figure.limbs, chain as Chain).b, 0); m.userData.ik = chain; m.renderOrder = 11; m.visible = false
        figure.joints[c.lower].add(m); pickers.push(m)
      }
    } else if (o.kind === 'set' && o.preset === 'image' && o.asset_id) body = this.buildImageSet(o)
    else if (o.kind === 'set') body = buildSet(o.preset ?? 'empty', this.setMat)
    else if (o.kind === 'prop') body = prop(o.preset ?? 'block', this.clayMat)
    else if (o.kind === 'mesh' && o.asset_id) {
      // P18 (D84): a GLB prop from the Catalogue — a placeholder box until the file arrives, then the model stood on the floor at its own size
      const group = new THREE.Group()
      const stub = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.5, 0.5), new THREE.MeshBasicMaterial({ color: 0x8899bb, wireframe: true }))
      stub.position.y = 0.25
      group.add(stub)
      const id = o.id
      new GLTFLoader().loadAsync(api.assetUrl(o.asset_id)).then((gltf) => {
        const e = this.entries.get(id)
        if (!e || e.body !== group || this.disposed) return
        const model = gltf.scene
        const box = new THREE.Box3().setFromObject(model, true)                 // SC3d: its vertices, not its boxes turned (D109's upright turn inflates those)
        const c = box.getCenter(new THREE.Vector3())
        model.position.sub(new THREE.Vector3(c.x, box.min.y, c.z))             // centred on its footprint, standing on the floor
        model.traverse((m) => { m.userData.stageId = id; const mm = m as THREE.Mesh; if (mm.isMesh) { mm.castShadow = true; mm.receiveShadow = true } })   // D109: the model arrives after build() set the body's shadow flags
        group.remove(stub)
        group.add(model)
        this.meshesLoaded.add(id)
        if (this.selectedId === id) this.selection.setFromObject(e.holder)
        this.dirty = true
        if (this.hooks.onMeshThumb && o.asset_id) { const aid = o.asset_id; void this.thumbnailOf(model).then((b) => this.hooks.onMeshThumb?.(aid, b)).catch(() => {}) }
      }).catch((err: unknown) => { this.meshesFailed.set(id, String(err)); this.dirty = true })
      body = group
    }
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
    } else if (o.kind === 'light') {
      const g = new THREE.Group()
      const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.12, 12, 8), new THREE.MeshBasicMaterial({ color: 0xffd060 }))
      bulb.userData.helper = true; g.add(bulb)
      body = g
    } else body = prop('block', this.clayMat)
    body.traverse((c) => { c.userData.stageId = o.id; const m = c as THREE.Mesh; if (m.isMesh && !c.userData.helper && o.kind !== 'plane' && !c.userData.unlit) { m.castShadow = true; m.receiveShadow = true } })
    holder.add(body)
    const entry: Entry = { holder, body, doc: o, figure, pickers }
    if (figure && o.detail) this.attachDetailed(entry, o.detail)
    if (figure && o.shadow_proxy) this.attachProxy(entry, o.shadow_proxy)
    return entry
  }
  /** SC3 (D120): a picture of a place as its relief (E30) — the GLB in the picture camera's frame (that camera at the origin looking down
   *  −Z), raised so the relief's floor meets the stage floor; unlit, since the picture is already lit (it is the plate); it casts no shadow
   *  (a shell around everything would darken the whole set). SC3b: it catches the figures' shadows — in the lit passes (the clay takes the
   *  relief's shape) and, through a shadow-only copy of the relief over the picture, in the viewport and the beauty pass; and the picture
   *  itself stands as a backdrop at the far depth, so what MoGe masked (the sky) and the seams a move opens show the picture, not the dark
   *  (D120: the masked pixels as a backdrop). A wire floor stands in until it loads. */
  private buildImageSet(o: StageObject): THREE.Object3D {
    const group = new THREE.Group()
    const lift = -(o.floor_y ?? -1)
    const stub = new THREE.Mesh(new THREE.BoxGeometry(4, 0.02, 4), new THREE.MeshBasicMaterial({ color: 0x8899bb, wireframe: true }))
    stub.position.set(0, 0.01, -3)
    group.add(stub)
    const id = o.id
    new GLTFLoader().loadAsync(api.assetUrl(o.asset_id!)).then((gltf) => {
      const e = this.entries.get(id)
      if (!e || e.body !== group || this.disposed) return
      const model = gltf.scene
      model.position.y = lift
      const surfaces: THREE.Mesh[] = []
      model.traverse((m) => {
        m.userData.stageId = id
        const mm = m as THREE.Mesh
        if (!mm.isMesh) return
        const was = mm.material as THREE.MeshStandardMaterial
        mm.material = new THREE.MeshBasicMaterial({ map: was.map ?? null, color: was.map ? 0xffffff : 0x9a9a9a, side: THREE.DoubleSide })
        mm.castShadow = false; mm.receiveShadow = true; mm.userData.unlit = true      // SC3b: the lit passes' override material shows the shadows
        surfaces.push(mm)
      })
      for (const mm of surfaces) {                                                    // SC3b: the shadow-only copy over the picture
        const c = new THREE.Mesh(mm.geometry, this.catcherMat)
        c.position.copy(mm.position); c.quaternion.copy(mm.quaternion); c.scale.copy(mm.scale)
        c.receiveShadow = true; c.castShadow = false; c.renderOrder = 1
        Object.assign(c.userData, { stageId: id, unlit: true, catcher: true })
        mm.parent?.add(c)
      }
      group.remove(stub)
      group.add(model)
      if (o.plate_asset_id) this.attachBackdrop(id, group, model, o.plate_asset_id, o.lens_deg ?? 60, lift)
      this.meshesLoaded.add(id)
      if (this.selectedId === id) this.selection.setFromObject(e.holder)
      this.dirty = true
    }).catch((err: unknown) => { this.meshesFailed.set(id, String(err)); this.dirty = true })
    return group
  }
  /** SC3b: shadows only, over a picture set's relief (transparent elsewhere); drawn just in front of the relief it copies. */
  private catcherMat = new THREE.ShadowMaterial({ opacity: 0.42, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1, depthWrite: false })
  /** SC3b (D120): the picture as a backdrop just behind the relief's farthest point, filling the picture camera's view at that depth (the
   *  lens and the picture's aspect) — what MoGe masked (the sky) and a seam a move opens show the picture. Out of the set's bounds and
   *  picking (an empty bounding box), unlit, no shadows; the clay, depth, normal and mask passes leave it out (hideBackdrops). */
  private attachBackdrop(id: string, group: THREE.Group, model: THREE.Object3D, plateId: string, lensDeg: number, lift: number): void {
    new THREE.TextureLoader().loadAsync(api.assetUrl(plateId)).then((tex) => {
      const e = this.entries.get(id)
      if (!e || e.body !== group || this.disposed) { tex.dispose(); return }
      tex.colorSpace = THREE.SRGBColorSpace
      const img = tex.image as { width: number; height: number }
      const box = new THREE.Box3().setFromObject(model)                              // the relief in the set's own frame (the picture camera at y = lift)
      const far = Math.max(2, -box.min.z) * 1.02
      const hfov = rad(Math.min(150, Math.max(20, lensDeg)))
      const w = 2 * far * Math.tan(hfov / 2), h = w * (img.height / Math.max(1, img.width))
      const geo = new THREE.PlaneGeometry(w, h)
      geo.boundingBox = new THREE.Box3()                                              // empty: never in the set's box, the framing or a pick
      const backdrop = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ map: tex }))
      backdrop.position.set(0, lift, -far)
      Object.assign(backdrop.userData, { stageId: id, unlit: true, backdrop: true })
      group.add(backdrop)
      this.dirty = true
    }).catch((err: unknown) => this.hooks.onDetailError?.(id, `the picture behind the set: ${err instanceof Error ? err.message : String(err)}`))
  }
  /** SC3b: the picture sets' backdrops out of a pass (they belong to the viewport and the beauty pass); returns the undo. */
  private hideBackdrops(): () => void {
    const hidden: THREE.Object3D[] = []
    for (const e of this.entries.values()) e.body.traverse((c) => { if (c.userData.backdrop && c.visible) { c.visible = false; hidden.push(c) } })
    return () => { for (const c of hidden) c.visible = true }
  }
  /** SC3b, for the tests: what a picture set's relief carries (its surfaces, their shadow copies, the backdrop and its size). */
  imageSetLayers(id: string): { surfaces: number; catchers: number; backdrop: { w: number; h: number; z: number } | null } | null {
    const e = this.entries.get(id)
    if (!e || e.doc.preset !== 'image') return null
    let surfaces = 0, catchers = 0
    let backdrop: { w: number; h: number; z: number } | null = null
    e.body.traverse((c) => {
      const m = c as THREE.Mesh
      if (!m.isMesh) return
      if (c.userData.catcher) catchers++
      else if (c.userData.backdrop) { const g = m.geometry as THREE.PlaneGeometry; backdrop = { w: +g.parameters.width.toFixed(3), h: +g.parameters.height.toFixed(3), z: +c.position.z.toFixed(3) } }
      else if (c.userData.unlit && m.material instanceof THREE.MeshBasicMaterial && (m.material as THREE.MeshBasicMaterial).wireframe !== true) surfaces++
    })
    return { surfaces, catchers, backdrop }
  }
  /** E23d (D105): the figure's shadow proxy — a mesh asset bound to its joints, seen by the light only; the dummy then casts nothing. */
  private attachProxy(e: Entry, assetId: string): void {
    const id = e.doc.id
    new GLTFLoader().loadAsync(api.assetUrl(assetId)).then((gltf) => {
      if (this.disposed || this.entries.get(id) !== e || !e.figure) return
      e.holder.updateMatrixWorld(true)
      const px = bindProxy(gltf.scene, e.figure.joints, e.figure.limbs, e.holder, e.doc.pose ?? null)
      for (const m of px.meshes) this.scene.add(m)
      e.proxy = px
      e.holder.traverse((c) => { const m = c as THREE.Mesh; if (m.isMesh) m.castShadow = false })
      this.followAll()
      this.dirty = true
    }).catch((err) => this.hooks.onDetailError?.(id, `shadow proxy: ${err instanceof Error ? err.message : String(err)}`))
  }
  /** CA1: the Detailed level — the starter set's mannequin, loaded once and cloned, follows the figure's joints; the Simple shapes hide
   *  (the joints, pickers and markers stay: they drive the pose and carry the pose pass). Until it loads, or without it, the figure is Simple. */
  private attachDetailed(e: Entry, kind: 'male' | 'female'): void {
    const id = e.doc.id
    void import('./motion/mannequins').then((m) => m.mannequinClone(kind, this.clayMat)).then(({ root, rig }) => {
      if (this.disposed || this.entries.get(id) !== e || !e.figure) return
      e.holder.updateMatrixWorld(true)
      const d = makeDetailed(root, rig, e.figure.joints.root.parent!, e.figure.joints, e.figure.limbs, { hands: e.doc.body?.hands, feet: e.doc.body?.feet })
      d.object.traverse((c) => { c.userData.stageId = id; const m = c as THREE.Mesh; if (m.isMesh) { m.castShadow = !e.proxy; m.receiveShadow = true } })
      const inside = (o: THREE.Object3D) => { for (let p: THREE.Object3D | null = o; p; p = p.parent) if (p === d.object) return true; return false }
      e.figure.root.traverse((c) => { const mesh = c as THREE.Mesh; if (mesh.isMesh && !mesh.userData.joint && !mesh.userData.ik && !inside(mesh)) mesh.visible = false })
      e.detailed = d
      d.follow(e.figure.joints, e.doc.pose?.extra)
      this.dirty = true
    }).catch((err) => this.hooks.onDetailError?.(id, err instanceof Error ? err.message : String(err)))
  }
  /** CA1: a hand preset as the figure's `extra` bone turns — null while the figure is Simple (or its mannequin is still loading). */
  handPreset(id: string, side: 'r' | 'l', preset: HandPreset): Record<string, number[]> | null {
    return this.entries.get(id)?.detailed?.handPreset(side, preset) ?? null
  }
  // CA1: each figure's floor path, smoothed as a clip walks it, with its clicked points — a viewport guide, never in the passes
  private paths = new Map<string, { key: string; obj: THREE.Object3D }>()
  private pathMat = new THREE.LineBasicMaterial({ color: 0x5ad0ff })
  private pathDot = new THREE.MeshBasicMaterial({ color: 0x5ad0ff })
  private syncPaths(doc: StageDoc): void {
    const seen = new Set<string>()
    for (const o of doc.objects) {
      const pts = (o.path ?? []) as number[][]
      if (o.kind !== 'mannequin' || !pts.length) continue
      seen.add(o.id)
      const key = JSON.stringify(pts)
      if (this.paths.get(o.id)?.key === key) continue
      const old = this.paths.get(o.id)
      if (old) this.scene.remove(old.obj)
      const g = new THREE.Group(); g.userData.helper = 'path'
      const smooth = measure(pts.map((p) => [p[0], p[1]] as [number, number])).points
      g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(smooth.map(([x, z]) => new THREE.Vector3(x, 0.01, z))), this.pathMat))
      for (const [x, z] of pts) { const d = new THREE.Mesh(new THREE.SphereGeometry(0.035, 8, 6), this.pathDot); d.position.set(x, 0.02, z); g.add(d) }
      this.scene.add(g)
      this.paths.set(o.id, { key, obj: g })
    }
    for (const [id, p] of [...this.paths]) if (!seen.has(id)) { this.scene.remove(p.obj); this.paths.delete(id) }
  }
  /** CA1: every Detailed figure after its joints (a key, a gizmo drag, the IK, a sampled frame). */
  followAll(): void {
    for (const e of this.entries.values()) if (e.detailed && e.figure) { e.holder.updateMatrixWorld(true); e.detailed.follow(e.figure.joints, e.doc.pose?.extra) }
  }

  // ---- ST3: the passes ------------------------------------------------------------------------------------------------------------
  /** The five passes of a camera at a size (16 §7), rendered off the viewport in a renderer of their own: clay (everything in grey
   *  Lambert — image planes become grey cards, D81), depth (linear disparity around the subject), normals, the object-ID masks (a flat
   *  colour per object, the legend returned) and the pose (every figure's COCO-18 in OpenPose colours). Helpers, pickers and the gizmo
   *  stay out; hidden objects too. The viewport's own renderer and state are untouched. */
  async renderPasses(cam: StageCamera, w: number, h: number): Promise<RenderedPasses> {
    const r = this.passRenderer(w, h)
    const camera = this.shotCamera(cam, w / h)
    const restore = this.hideHelpers(camera)
    const showBackdrops = this.hideBackdrops()                                       // SC3b: the picture behind a set is the viewport's and the beauty's
    const swapped: [THREE.Mesh, THREE.Material | THREE.Material[]][] = []
    try {
      this.scene.updateMatrixWorld(true)
      const blobs: Partial<Record<PassName, Blob>> = {}
      blobs.clay = await this.shotWith(r, camera, this.passClay, 0xb8b8b8)
      blobs.depth = await this.shotWith(r, camera, this.depthFor(cam), 0x000000)
      blobs.normal = await this.shotWith(r, camera, this.passNormal, 0x8080ff)
      // masks: one flat colour per object, swapped in by hand (an override material cannot differ per object)
      const legend: Record<string, string> = {}
      let i = 0
      for (const e of this.entries.values()) {
        if (!e.doc.visible) continue
        const hex = maskColour(i++); legend[hex] = e.doc.id
        const m = new THREE.MeshBasicMaterial({ color: hex })
        e.holder.traverse((o) => { const mesh = o as THREE.Mesh; if (mesh.isMesh && !mesh.userData.joint && !mesh.userData.ik) { swapped.push([mesh, mesh.material]); mesh.material = m } })   // CA1: the holder, so a Detailed mannequin is in its mask
      }
      blobs.mask = await this.shotWith(r, camera, null, 0x000000)
      for (const [mesh, mat] of swapped) mesh.material = mat
      swapped.length = 0
      const keypoints = this.keypoints(camera, w, h)
      blobs.pose = await toBlob(drawPose(keypoints, w, h, this.wholebody(camera, w, h)))   // D101: a Detailed figure's hands and feet
      return { size: { w, h }, blobs: blobs as Record<PassName, Blob>, keypoints, legend }
    } finally {
      for (const [mesh, mat] of swapped) mesh.material = mat
      restore(); showBackdrops()
      r.dispose(); r.forceContextLoss()
      this.dirty = true
    }
  }
  /** ST4 (16 §8): one pass per frame of an animated range — the scene synced to each frame's sampled document and camera (anim.ts),
   *  the depth (the IC-LoRA guide, D76) or the pose sequence, with every frame's COCO-18 keypoints for the rig's scoring. The scene
   *  is left at `restoreDoc` (the frame the viewport shows). */
  async renderSequence(frames: { cam: StageCamera; doc: StageDoc }[], w: number, h: number, kind: 'depth' | 'pose' | 'clay' | 'proxy' | 'proxymask' | 'beauty', restoreDoc: StageDoc,
                       onProgress?: (done: number, total: number) => void): Promise<{ blobs: Blob[]; keypoints: Keypoint[][][]; wholebody: (WholeBody | null)[][] }> {
    const r = this.passRenderer(w, h)
    let restore = () => {}
    // D109: a mesh prop's PBR material (Pixal3D bakes metalness) reflects its surroundings — without an environment it renders near
    // black. The beauty pass lights them with three's neutral room (PMREM, made per pass renderer; Lambert clay ignores it)
    let env: THREE.Texture | null = null
    if (kind === 'beauty') { const pm = new THREE.PMREMGenerator(r); env = pm.fromScene(new RoomEnvironment(), 0.04).texture; pm.dispose() }
    try {
      const blobs: Blob[] = []
      const keypoints: Keypoint[][][] = []
      const wholebody: (WholeBody | null)[][] = []                                   // CA1b: the hands and feet the pose pass draws, for measuring
      for (let i = 0; i < frames.length; i++) {
        const { cam, doc } = frames[i]
        this.sync(doc)
        const camera = this.shotCamera(cam, w / h)
        restore(); restore = this.hideHelpers(camera)
        if (kind !== 'beauty') { const helpers = restore, back = this.hideBackdrops(); restore = () => { back(); helpers() } }   // SC3b
        this.scene.updateMatrixWorld(true)
        const kp = this.keypoints(camera, w, h)
        keypoints.push(kp)
        const wb = this.wholebody(camera, w, h)
        wholebody.push(wb)
        if (kind === 'proxymask') { blobs.push(await this.proxyMask(r, camera)); onProgress?.(i + 1, frames.length); continue }   // E23e: the proxies' silhouette
        if (kind === 'beauty') {                                                     // D109: every object in its own material (a mesh prop textured), lit, on black
          blobs.push(await this.shotWith(r, camera, null, 0x000000, false, env))
          onProgress?.(i + 1, frames.length); continue
        }
        blobs.push(kind === 'depth' ? await this.shotWith(r, camera, this.depthFor(cam), 0x000000) : kind === 'clay' || kind === 'proxy' ? await this.shotWith(r, camera, this.passClay, 0xb8b8b8, kind === 'proxy')   // E23c: the lit clay (the light object's shadows)
          : await toBlob(drawPose(kp, w, h, wb)))
        onProgress?.(i + 1, frames.length)
      }
      return { blobs, keypoints, wholebody }
    } finally {
      restore()
      env?.dispose()
      r.dispose(); r.forceContextLoss()
      this.sync(restoreDoc)
      this.dirty = true
    }
  }
  /** D111 (PS5b): the plate projected along the camera path — the still (a Stage shot of the bare set at the first frame) cast from that
   *  frame's camera onto the set's surfaces and a far backdrop (so a part of the picture no surface of the set holds stays on the plate),
   *  rendered through each frame's camera: a camera move gives the plate's parallax, a still camera the still. The frames' documents
   *  show the set alone (the caller hides the actors). */
  async renderProjected(frames: { cam: StageCamera; doc: StageDoc }[], w: number, h: number, plate: TexImageSource, proj: StageCamera, projAspect: number,
                        restoreDoc: StageDoc, onProgress?: (done: number, total: number) => void): Promise<Blob[]> {
    const r = this.passRenderer(w, h)
    const tex = new THREE.Texture(plate as HTMLImageElement)
    tex.colorSpace = THREE.NoColorSpace; tex.needsUpdate = true                    // the plate's own sRGB values, written as they are
    const pc = this.shotCamera(proj, projAspect)
    const projVP = new THREE.Matrix4().multiplyMatrices(pc.projectionMatrix, pc.matrixWorldInverse)
    const mat = new THREE.ShaderMaterial({
      uniforms: { plate: { value: tex }, projVP: { value: projVP } }, side: THREE.DoubleSide,
      vertexShader: 'varying vec4 vWorld; void main() { vWorld = modelMatrix * vec4(position, 1.0); gl_Position = projectionMatrix * viewMatrix * vWorld; }',
      fragmentShader: 'uniform sampler2D plate; uniform mat4 projVP; varying vec4 vWorld; void main() { vec4 c = projVP * vWorld; if (c.w <= 0.0) { gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0); return; } vec2 uv = clamp(c.xy / c.w * 0.5 + 0.5, 0.0, 1.0); gl_FragColor = texture2D(plate, uv); }',
    })
    const backdrop = new THREE.Mesh(new THREE.SphereGeometry(80, 48, 24), mat)
    backdrop.position.set(proj.pos[0], proj.pos[1], proj.pos[2])
    this.scene.add(backdrop)
    let restore = () => {}
    try {
      const blobs: Blob[] = []
      for (let i = 0; i < frames.length; i++) {
        const { cam, doc } = frames[i]
        this.sync(doc)
        const camera = this.shotCamera(cam, w / h)
        restore(); restore = this.hideHelpers(camera)
        { const helpers = restore, back = this.hideBackdrops(); restore = () => { back(); helpers() } }   // SC3b: PS5b's own backdrop sphere holds the far
        this.scene.updateMatrixWorld(true)
        blobs.push(await this.shotWith(r, camera, mat, 0x000000))
        onProgress?.(i + 1, frames.length)
      }
      return blobs
    } finally {
      restore()
      this.scene.remove(backdrop); backdrop.geometry.dispose(); mat.dispose(); tex.dispose()
      r.dispose(); r.forceContextLoss()
      this.sync(restoreDoc)
      this.dirty = true
    }
  }
  /** P18: a lit three-quarter view of a model with the camera fitted to its bounding sphere (the E14 renderer's framing) — the thumbnail the
   *  engine's RenderMesh cannot make (its camera sits inside some props). */
  async thumbnailOf(model: THREE.Object3D, size = 512): Promise<Blob> {
    const r = this.passRenderer(size, size)
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x2a2a2e)
    const clone = model.clone()
    const box = new THREE.Box3().setFromObject(clone)
    const centre = box.getCenter(new THREE.Vector3())
    const radius = Math.max(1e-3, box.getSize(new THREE.Vector3()).length() / 2)
    scene.add(clone, new THREE.HemisphereLight(0xffffff, 0x777777, 1.4))
    const key = new THREE.DirectionalLight(0xffffff, 2.0); key.position.set(centre.x + radius, centre.y + 2 * radius, centre.z + 3 * radius); scene.add(key)
    const fill = new THREE.DirectionalLight(0xffffff, 0.7); fill.position.set(centre.x - 2 * radius, centre.y + radius, centre.z - radius); scene.add(fill)
    const fov = 35
    const cam = new THREE.PerspectiveCamera(fov, 1, radius / 100, radius * 100)
    const dist = (radius / Math.tan(THREE.MathUtils.degToRad(fov / 2))) * 1.15
    const yaw = THREE.MathUtils.degToRad(35), pitch = THREE.MathUtils.degToRad(20)
    cam.position.set(centre.x + dist * Math.sin(yaw) * Math.cos(pitch), centre.y + dist * Math.sin(pitch), centre.z + dist * Math.cos(yaw) * Math.cos(pitch))
    cam.lookAt(centre); cam.updateProjectionMatrix(); cam.updateMatrixWorld()
    try {
      r.render(scene, cam)
      return await toBlob(r.domElement)
    } finally { r.dispose(); r.forceContextLoss() }
  }
  private passRenderer(w: number, h: number): THREE.WebGLRenderer {
    const r = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true })
    r.setPixelRatio(1); r.setSize(w, h, false)
    r.shadowMap.enabled = true; r.shadowMap.type = THREE.PCFShadowMap                      // E23c: the light object's shadows in the clay pass
    return r
  }
  /** The render camera of a document camera at an aspect (36 mm sensor, roll), as applyShot builds the viewport's. */
  private shotCamera(cam: StageCamera, aspect: number): THREE.PerspectiveCamera {
    const camera = new THREE.PerspectiveCamera(vfovFor(cam.focal_mm, cam.sensor_mm, aspect), aspect, 0.05, 500)
    camera.position.set(cam.pos[0], cam.pos[1], cam.pos[2]); camera.up.set(0, 1, 0); camera.lookAt(cam.target[0], cam.target[1], cam.target[2])
    camera.rotateZ(rad(cam.roll)); camera.updateProjectionMatrix(); camera.updateMatrixWorld()
    return camera
  }
  /** Helpers, pickers and the gizmo out of the picture (hidden objects stay out), billboards faced; returns the undo. */
  private hideHelpers(camera: THREE.Camera): () => void {
    const hidden: THREE.Object3D[] = []
    const hide = (o: THREE.Object3D | undefined) => { if (o && o.visible) { o.visible = false; hidden.push(o) } }
    hide(this.grid); hide(this.selection); hide(this.gizmo.getHelper())
    for (const e of this.entries.values()) if (e.doc.kind === 'light') hide(e.body)                  // E23c: a light's marker is a guide
    for (const p of this.paths.values()) hide(p.obj)                                  // CA1: the floor paths are a guide
    for (const l of this.lights.values()) hide(l.aim)                                 // D110: a light's aim line is a guide
    for (const hlp of this.camHelpers.values()) hide(hlp)
    for (const e of this.entries.values()) { e.pickers?.forEach(hide); if (e.doc.visible && e.doc.kind === 'plane' && e.doc.billboard) e.body.lookAt(camera.position) }
    const prevBg = this.scene.background, prevOverride = this.scene.overrideMaterial
    return () => { this.scene.overrideMaterial = prevOverride; this.scene.background = prevBg; for (const o of hidden) o.visible = true }
  }
  /** E23e: the shadow proxies' silhouette, white on black (everything else hidden) — the character mask a Replace layer fills. */
  private proxyMask(r: THREE.WebGLRenderer, camera: THREE.Camera): Promise<Blob> {
    const hidden: THREE.Object3D[] = []
    for (const e of this.entries.values()) if (e.holder.visible) { e.holder.visible = false; hidden.push(e.holder) }
    const keyShadow = r.shadowMap.enabled
    r.shadowMap.enabled = false
    this.scene.overrideMaterial = this.whiteMat; this.scene.background = new THREE.Color(0x000000)
    r.render(this.scene, camera)
    r.shadowMap.enabled = keyShadow
    for (const o of hidden) o.visible = true
    return toBlob(r.domElement)
  }
  private whiteMat = new THREE.MeshBasicMaterial({ color: 0xffffff })
  private shotWith(r: THREE.WebGLRenderer, camera: THREE.Camera, material: THREE.Material | null, bg: number, showProxies = false, env: THREE.Texture | null = null): Promise<Blob> {
    this.scene.overrideMaterial = material; this.scene.background = new THREE.Color(bg)
    // D110: the viewport's environment lives in the viewport's GL context; a pass renderer gets its own (the beauty pass) or none
    const viewEnv = this.scene.environment
    this.scene.environment = env
    // E23d: the shadow proxies cast but are never seen. An override material would draw them, so the shadow map is made with them and
    // the picture without them (the map kept); `showProxies` draws them (the fit check)
    const proxies = showProxies ? [] : [...this.entries.values()].flatMap((e) => e.proxy?.meshes ?? []).filter((m) => m.visible)
    if (proxies.length && r.shadowMap.enabled) {
      r.shadowMap.autoUpdate = false; r.shadowMap.needsUpdate = true
      r.render(this.scene, camera)
      for (const m of proxies) m.visible = false
      r.render(this.scene, camera)
      for (const m of proxies) m.visible = true
      r.shadowMap.autoUpdate = true
    } else r.render(this.scene, camera)
    this.scene.environment = viewEnv
    return toBlob(r.domElement)
  }
  private depthFor(cam: StageCamera): THREE.ShaderMaterial {
    const dr = depthRange(Math.hypot(cam.pos[0] - cam.target[0], cam.pos[1] - cam.target[1], cam.pos[2] - cam.target[2]))
    this.passDepth.uniforms.near.value = dr.near; this.passDepth.uniforms.far.value = dr.far
    return this.passDepth
  }
  private keypoints(camera: THREE.Camera, w: number, h: number): Keypoint[][] {
    const figures = [...this.entries.values()].filter((e) => e.figure && e.doc.visible).map((e) => e.figure!.markers)
    return projectMarkers(figures, camera, w, h)
  }
  /** D101: per figure (the order of `keypoints`), the Detailed figure's hands and feet, projected; null for a Simple figure. */
  private wholebody(camera: THREE.Camera, w: number, h: number): (WholeBody | null)[] {
    return [...this.entries.values()].filter((e) => e.figure && e.doc.visible).map((e) => {
      const wb = e.detailed?.wholebody
      if (!wb) return null
      const [feet, left, right] = projectMarkers([wb.feet, wb.left, wb.right], camera, w, h)
      return { feet, left, right }
    })
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
      this.renderPip()
    }
  }

  // ---- D121 (AW4): the picture-in-picture of the active camera -------------------------------------------------------------------
  setPip(on: boolean): void { this.pip = on; this.dirty = true }
  /** Where the PiP sits (CSS px from the viewport's top left): the bottom right of the free view, at most 320 px wide at the shot's aspect. */
  pipRect(): { x: number; y: number; w: number; h: number } | null {
    if (!this.pip || this.view !== 'free' || !this.activeCam) return null
    const w = Math.round(Math.min(320, this.w * 0.3)), h = Math.round(w / this.aspect)
    if (w < 80 || h + 24 > this.h) return null
    return { x: this.w - w - 12, y: this.h - h - 12, w, h }
  }
  /** The shot camera's view into the PiP's corner, as the camera view draws it (helpers, glyphs, gizmo and light aims out, billboards facing
   *  it) — reusing the frame's shadow map, so the second picture costs its draw calls, not another shadow pass. */
  private renderPip(): void {
    const p = this.pipRect()
    if (!p) return
    const r = this.renderer
    const hidden: THREE.Object3D[] = []
    const hide = (o: THREE.Object3D | undefined) => { if (o && o.visible) { o.visible = false; hidden.push(o) } }
    hide(this.selection); hide(this.gizmo.getHelper())
    for (const h of this.camHelpers.values()) hide(h)
    for (const l of this.lights.values()) hide(l.aim)
    for (const e of this.entries.values()) e.pickers?.forEach(hide)                                     // pose mode's joint pickers and handles
    if (this.ik) hide(this.ik.proxy)
    for (const e of this.entries.values()) if (e.doc.kind === 'plane' && e.doc.billboard) { e.body.lookAt(this.shot.position); e.body.updateMatrixWorld() }
    const y = this.h - p.y - p.h
    r.setViewport(p.x, y, p.w, p.h); r.setScissor(p.x, y, p.w, p.h); r.setScissorTest(true)
    r.setClearColor(0x1d1e22, 1); r.clear()
    const auto = r.shadowMap.autoUpdate, mats = this.scene.matrixWorldAutoUpdate
    r.shadowMap.autoUpdate = false; r.shadowMap.needsUpdate = false
    this.scene.matrixWorldAutoUpdate = false                         // the frame's render brought every matrix up to date (the billboards just above)
    r.render(this.scene, this.shot)
    this.scene.matrixWorldAutoUpdate = mats
    r.shadowMap.autoUpdate = auto
    r.setScissorTest(false); r.setViewport(0, 0, this.w, this.h)
    for (const o of hidden) o.visible = true
    for (const e of this.entries.values()) if (e.doc.kind === 'plane' && e.doc.billboard) e.body.lookAt(this.free.position)
  }
  /** AW4's measurement: the viewport's frame time in ms (CPU and GPU — a one-pixel read-back after each render waits for the frame;
   *  gl.finish returned at once in Edge), the PiP as set: five batches of `n` frames, the median batch over `n` (the browser's clock
   *  steps by 0.1 ms, too coarse for one frame). */
  measureFrame(n = 60): number {
    const gl = this.renderer.getContext()
    const px = new Uint8Array(4)
    const batches: number[] = []
    for (let b = 0; b < 5; b++) {
      const t0 = performance.now()
      for (let i = 0; i < n; i++) { this.renderNow(); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px) }
      batches.push((performance.now() - t0) / n)
    }
    batches.sort((a, b) => a - b)
    return batches[2]
  }
}
