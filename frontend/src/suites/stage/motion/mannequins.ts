// CA1 (01 §9a): the Detailed level's mannequin — the starter set's skinned figure (Quaternius UAL2: male in UAL2_Standard, female in
// Mannequin_F; the same 65-bone rig), found among the starter files by its content (a SkinnedMesh on a rig the retargeter knows), the
// female by its file name. Each figure gets its own clone (SkeletonUtils), so its bones pose independently.
import * as THREE from 'three'
import { clone as cloneSkinned } from 'three/examples/jsm/utils/SkeletonUtils.js'
import { listFiles, load, type MotionFile } from './library'
import { detectRig, type RigName } from './retarget'

export type MannequinKind = 'male' | 'female'
interface Found { file: MotionFile; root: THREE.Object3D; rig: RigName }
let found: Promise<Record<MannequinKind, Found | null>> | null = null

const isFemale = (f: MotionFile) => /(^|[_\s-])f($|[_\s-])|female|mannequin_f/i.test(f.name)

async function scan(): Promise<Record<MannequinKind, Found | null>> {
  const files = (await listFiles()).items.filter((f) => f.source === 'starter' && f.ext === 'glb')
  const out: Record<MannequinKind, Found | null> = { male: null, female: null }
  // the smallest files first: a mannequin alone loads faster than a clip library
  for (const f of [...files].sort((a, b) => a.bytes - b.bytes)) {
    const kind: MannequinKind = isFemale(f) ? 'female' : 'male'
    if (out[kind]) continue
    const l = await load(f)
    let skinned = false
    l.root.traverse((o) => { if ((o as THREE.SkinnedMesh).isSkinnedMesh) skinned = true })
    const names: string[] = []
    l.root.traverse((o) => names.push(o.name))
    const rig = detectRig(names)
    if (skinned && rig) out[kind] = { file: f, root: l.root, rig }
    if (out.male && out.female) break
  }
  return out
}

/** A fresh clone of the mannequin (the female falls back to the male when the set has none), in the given material, and its rig. */
export async function mannequinClone(kind: MannequinKind, material: THREE.Material): Promise<{ root: THREE.Object3D; rig: RigName; file: string }> {
  found ??= scan().catch((e) => { found = null; throw e })
  const f = await found
  const pick = f[kind] ?? f.male ?? f.female
  if (!pick) throw new Error('the starter set has no skinned mannequin (Quaternius UAL2) — the Detailed level needs it')
  const root = cloneSkinned(pick.root)
  root.traverse((o) => {
    const m = o as THREE.Mesh
    if (m.isMesh) { m.material = material; m.castShadow = false; m.frustumCulled = false }   // a skinned mesh's bounds are its bind pose: never culled away
  })
  return { root, rig: pick.rig, file: pick.file.name }
}
