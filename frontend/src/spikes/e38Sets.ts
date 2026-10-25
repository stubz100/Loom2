// Spike E38 (proto01_UIcast 04 §7): the set builder's browser half — a picture baked onto the set fitted to it (the product's
// stage/setBake.ts), a second picture's coverage composited, and the share of each frame of a camera move that no picture saw well.
// engine/spikes/e38_sets.py drives it through e38_browser.cjs; nothing here is shipped.
import * as THREE from 'three'
import type { StageCamera } from '../api/types'
import { bakeSet, COVERAGE_RATIO_SCALE } from '../suites/stage/setBake'
import { placeSet, type PlaceSetDoc } from '../suites/stage/placeSet'
import { sourceCamera } from '../suites/stage/setOverlay'

type Cam = Pick<StageCamera, 'pos' | 'target' | 'roll' | 'focal_mm' | 'sensor_mm'>
export interface E38Face { id: string; w: number; h: number; px: [number, number]; texel_m: number; texture: string; coverage: string }

const b64 = async (b: Blob) => { const a = new Uint8Array(await b.arrayBuffer()); let s = ''; for (let i = 0; i < a.length; i += 0x8000) s += String.fromCharCode(...a.subarray(i, i + 0x8000)); return btoa(s) }
const image = (url: string) => new Promise<HTMLImageElement>((res, rej) => { const i = new Image(); i.crossOrigin = 'anonymous'; i.onload = () => res(i); i.onerror = () => rej(new Error(`no picture at ${url}`)); i.src = url })

/** A picture baked onto a set from its matched camera: each face's texture and coverage (base64 PNGs). */
export async function bake(url: string, ps: PlaceSetDoc, cam: Cam, texel = 0.01, maxPx = 2048): Promise<E38Face[]> {
  const img = await image(url)
  const faces = await bakeSet(ps, img, cam, texel, maxPx)
  return Promise.all(faces.map(async (f) => ({ id: f.id, w: f.w, h: f.h, px: f.px, texel_m: f.texel_m, texture: await b64(f.texture), coverage: await b64(f.coverage) })))
}

/** A camera move through the set, each frame drawn with every face's coverage as its texture (red: how squarely a picture saw it; green:
 *  how coarse): per frame the share of pixels no picture saw (red < 0.05) and the share seen too coarse (green × 8 > `coarse` texels), and
 *  the frames themselves (every `keep`-th) for the sheet. */
export async function moveCoverage(ps: PlaceSetDoc, coverage: Record<string, string>, frames: Cam[], w = 384, h = 216, coarse = 2, keep = 30):
  Promise<{ unseen: number[]; coarse: number[]; shots: Record<number, string> }> {
  const tex = new Map<string, THREE.Texture>()
  for (const [id, data] of Object.entries(coverage)) {
    const t = new THREE.Texture(await image(`data:image/png;base64,${data}`))
    t.colorSpace = THREE.NoColorSpace; t.minFilter = THREE.NearestFilter; t.magFilter = THREE.NearestFilter; t.generateMipmaps = false; t.needsUpdate = true
    tex.set(id, t)
  }
  const grey = new THREE.MeshBasicMaterial({ color: 0x000000, side: THREE.DoubleSide })
  const scene = new THREE.Scene()
  scene.add(placeSet(ps, grey, (id) => (tex.has(id) ? new THREE.MeshBasicMaterial({ map: tex.get(id)!, side: THREE.DoubleSide }) : null)))
  const r = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true })
  r.setPixelRatio(1); r.setSize(w, h, false); r.setClearColor(0x000000, 1)
  r.outputColorSpace = THREE.LinearSRGBColorSpace
  const buf = new Uint8Array(w * h * 4)
  const gl = r.getContext()
  const out = { unseen: [] as number[], coarse: [] as number[], shots: {} as Record<number, string> }
  try {
    for (let i = 0; i < frames.length; i++) {
      const cam = sourceCamera(frames[i], w / h)
      r.render(scene, cam)
      gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, buf)
      let un = 0, co = 0
      for (let p = 0; p < w * h; p++) { const red = buf[p * 4] / 255, green = buf[p * 4 + 1] / 255
        if (red < 0.05) un++; else if (green * COVERAGE_RATIO_SCALE > coarse) co++ }
      out.unseen.push(+(un / (w * h)).toFixed(4)); out.coarse.push(+(co / (w * h)).toFixed(4))
      if (i % keep === 0 || i === frames.length - 1) out.shots[i] = r.domElement.toDataURL('image/png').split(',')[1]
    }
    return out
  } finally { r.dispose(); r.forceContextLoss(); for (const t of tex.values()) t.dispose() }
}

/** The set as textured by the bake, from a camera (a look for the sheet). */
export async function look(ps: PlaceSetDoc, textures: Record<string, string>, cam: Cam, w = 640, h = 360): Promise<string> {
  const scene = new THREE.Scene()
  const tex = new Map<string, THREE.Texture>()
  for (const [id, data] of Object.entries(textures)) {
    const t = new THREE.Texture(await image(`data:image/png;base64,${data}`)); t.colorSpace = THREE.SRGBColorSpace; t.needsUpdate = true; tex.set(id, t)
  }
  scene.add(placeSet(ps, new THREE.MeshBasicMaterial({ color: 0xff00ff, side: THREE.DoubleSide }), (id) => (tex.has(id) ? new THREE.MeshBasicMaterial({ map: tex.get(id)!, side: THREE.DoubleSide, transparent: true }) : null)))
  const r = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true })
  r.setPixelRatio(1); r.setSize(w, h, false); r.setClearColor(0x202024, 1)
  try { r.render(scene, sourceCamera(cam, w / h)); return r.domElement.toDataURL('image/png').split(',')[1] }
  finally { r.dispose(); r.forceContextLoss(); for (const t of tex.values()) t.dispose() }
}
