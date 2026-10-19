// CA1 (proto01_animate 01 step 5): the motion library in the client — the files the orchestrator lists (`GET /motion/files`: the CC0
// starter set and the author's local folder), loaded with three.js (GLTFLoader for glb / gltf, FBXLoader for Mixamo's FBX), their clips
// listed, and one clip retargeted onto a figure. A file is loaded once per session and kept (the starter glbs are 1.4–8 MB).
import * as THREE from 'three'
import { http, api, unwrap } from '../../../api/client'
import type { components } from '../../../api/schema'
import { detectRig, retarget, type RetargetOptions, type Retargeted, type RigName } from './retarget'

export type MotionFile = components['schemas']['MotionFile']
export interface MotionClip { file: MotionFile; name: string; duration: number; rig: RigName | null; rootMotion: boolean }
interface Loaded { root: THREE.Object3D; clips: THREE.AnimationClip[]; rig: RigName | null }

const cache = new Map<string, Promise<Loaded>>()

export async function listFiles(): Promise<{ items: MotionFile[]; starter_dir: string | null; local_dir: string | null }> {
  return unwrap(http.GET('/motion/files'))
}

async function parse(file: MotionFile): Promise<Loaded> {
  const bytes = await api.getBytes(`/motion/files/${file.id}`)
  let root: THREE.Object3D, clips: THREE.AnimationClip[]
  if (file.ext === 'fbx') {
    const { FBXLoader } = await import('three/examples/jsm/loaders/FBXLoader.js')
    const g = new FBXLoader().parse(bytes, '')
    root = g; clips = g.animations
  } else {
    const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js')
    const gltf = await new GLTFLoader().parseAsync(bytes, '')
    root = gltf.scene; clips = gltf.animations
  }
  const names: string[] = []
  root.traverse((o) => names.push(o.name))
  return { root, clips, rig: detectRig(names) }
}

export function load(file: MotionFile): Promise<Loaded> {
  let p = cache.get(file.id)
  if (!p) { p = parse(file); cache.set(file.id, p); p.catch(() => cache.delete(file.id)) }
  return p
}

/** The hips' travel over a clip, in the source's units: a clip that moves (Quaternius' `_RM`, a Mixamo walk without "In Place"). */
function hasRootMotion(clip: THREE.AnimationClip): boolean {
  const t = clip.tracks.find((x) => /(hips|pelvis)\.position$/i.test(x.name))
  if (!t || t.values.length < 6) return false
  const n = t.values.length
  const dx = t.values[n - 3] - t.values[0], dz = t.values[n - 1] - t.values[2]
  const span = Math.max(...t.values.filter((_, i) => i % 3 === 1)) || 1
  return Math.hypot(dx, dz) > 0.2 * Math.abs(span)                     // more than a fifth of the hip height
}

/** The clips of a file (the rest pose `A_TPose` left out). */
export async function clipsOf(file: MotionFile): Promise<MotionClip[]> {
  const l = await load(file)
  return l.clips.filter((c) => !/^A_TPose$/i.test(c.name) && c.duration > 0.05)
    .map((c) => ({ file, name: c.name === 'mixamo.com' || !c.name ? file.name : c.name, duration: c.duration, rig: l.rig, rootMotion: hasRootMotion(c) }))
}

/** One clip retargeted onto a figure. */
export async function retargetClip(clip: MotionClip, opts: RetargetOptions): Promise<Retargeted> {
  const l = await load(clip.file)
  const c = l.clips.find((x) => x.name === clip.name) ?? (l.clips.length === 1 ? l.clips[0] : undefined)
  if (!c) throw new Error(`no clip "${clip.name}" in ${clip.file.name}`)
  return retarget(l.root, c, opts)
}
