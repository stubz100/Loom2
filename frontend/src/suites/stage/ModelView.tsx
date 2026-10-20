// D110 (PS2): a prop's 3D model turning on its Story page — the GLB lit by three's room environment (Pixal3D bakes metallic PBR, which
// renders near black without one, E28c), turning slowly; a drag turns it by hand. Loaded lazily, so three.js stays out of Story's bundle.
import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import { api } from '../../api/client'

const TURN = 0.45                                 // rad/s while nobody holds it

export default function ModelView({ assetId, width = 288, height = 216 }: { assetId: string; width?: number; height?: number }) {
  const host = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = host.current
    if (!el) return
    const r = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    r.setPixelRatio(Math.min(2, window.devicePixelRatio || 1)); r.setSize(width, height, false)
    r.domElement.className = 'model-view-canvas'
    el.appendChild(r.domElement)
    const scene = new THREE.Scene()
    const pm = new THREE.PMREMGenerator(r)
    const env = pm.fromScene(new RoomEnvironment(), 0.04).texture
    pm.dispose()
    scene.environment = env; scene.environmentIntensity = 0.8
    const key = new THREE.DirectionalLight(0xffffff, 1.2); key.position.set(2, 3, 2.5); scene.add(key, new THREE.HemisphereLight(0xffffff, 0x666666, 0.4))
    const cam = new THREE.PerspectiveCamera(30, width / height, 0.01, 100)
    cam.position.set(0, 0.6, 3); cam.lookAt(0, 0.4, 0)
    const pivot = new THREE.Group(); scene.add(pivot)
    let disposed = false, yaw = 0.6, raf = 0, last = performance.now()
    let drag: { x: number; yaw: number } | null = null
    new GLTFLoader().loadAsync(api.assetUrl(assetId)).then((gltf) => {
      if (disposed) return
      const model = gltf.scene
      const box = new THREE.Box3().setFromObject(model)
      const c = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3())
      model.position.sub(new THREE.Vector3(c.x, box.min.y, c.z))                  // stood on its footprint, as Stage places it
      pivot.add(model)
      const radius = Math.max(1e-3, size.length() / 2)
      const dist = (radius / Math.tan(THREE.MathUtils.degToRad(15))) * 1.1
      cam.position.set(0, size.y * 0.5 + dist * 0.3, dist); cam.lookAt(0, size.y * 0.45, 0)
      cam.near = dist / 100; cam.far = dist * 10; cam.updateProjectionMatrix()
    }).catch(() => { el.dataset.failed = '1' })
    const frame = (t: number) => {
      if (disposed) return
      if (!drag) yaw += ((t - last) / 1000) * TURN
      last = t
      pivot.rotation.y = yaw
      r.render(scene, cam)
      raf = requestAnimationFrame(frame)
    }
    raf = requestAnimationFrame(frame)
    const down = (e: PointerEvent) => { drag = { x: e.clientX, yaw }; r.domElement.setPointerCapture(e.pointerId) }
    const move = (e: PointerEvent) => { if (drag) yaw = drag.yaw + (e.clientX - drag.x) * 0.012 }
    const up = () => { drag = null }
    r.domElement.addEventListener('pointerdown', down); r.domElement.addEventListener('pointermove', move); r.domElement.addEventListener('pointerup', up)
    return () => {
      disposed = true
      cancelAnimationFrame(raf)
      pivot.traverse((o) => { const m = o as THREE.Mesh; if (m.isMesh) { m.geometry.dispose(); for (const mat of ([] as THREE.Material[]).concat(m.material)) mat.dispose() } })
      env.dispose(); r.dispose(); r.forceContextLoss(); r.domElement.remove()
    }
  }, [assetId, width, height])
  return <div ref={host} className="model-view" style={{ width, height }} title="The 3D model — drag to turn it" />
}
