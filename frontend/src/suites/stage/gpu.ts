// V78 / review K61: freeing what a three.js view made — the stage's engine and the rigging benches' panes (the skeleton's side view, the clay
// hand, the shoe) rebuild their content and must free the old one; a GLB a pane rebuilds from is parsed once. Pure of the engine, so a bench
// pane need not load it.
import * as THREE from 'three'

/** V78: every GPU resource under an object — its geometries, its materials and their textures, a skinned mesh's bone texture (review K61:
 *  each Detailed clone has a skeleton of its own) — freed when it leaves the scene (a rebuild, a removal, the engine's end); three.js frees
 *  nothing by itself. `keep` holds the engine's shared materials: freed, they would only be compiled again on the next frame (a CS3 body
 *  transition rebuilds a figure every frame), so they outlive their objects. Each resource is freed once however many meshes share it. */
export function disposeObject(root: THREE.Object3D, keep: ReadonlySet<THREE.Material> = new Set()): { geometries: number; materials: number; textures: number } {
  const seen = new Set<object>()
  const n = { geometries: 0, materials: 0, textures: 0 }
  root.traverse((o) => {
    const m = o as THREE.Mesh
    if (m.geometry && !seen.has(m.geometry)) { seen.add(m.geometry); m.geometry.dispose(); n.geometries++ }
    const sk = (o as THREE.SkinnedMesh).isSkinnedMesh ? (o as THREE.SkinnedMesh).skeleton : null
    if (sk && !seen.has(sk)) { seen.add(sk); sk.dispose() }
    const mats = Array.isArray(m.material) ? m.material : m.material ? [m.material] : []
    for (const mat of mats) {
      if (!mat || keep.has(mat) || seen.has(mat)) continue
      seen.add(mat)
      for (const v of Object.values(mat) as unknown[]) {
        const t = v as THREE.Texture | null
        if (t && t.isTexture && !seen.has(t)) { seen.add(t); t.dispose(); n.textures++ }
      }
      mat.dispose(); n.materials++
    }
  })
  return n
}

/** review K61: what a pane shows freed and taken out — `extra` are objects it made that do not hang under it (a shell's meshes added beside). */
export function clearContent(content: THREE.Object3D, ...extra: (THREE.Object3D | null | undefined)[]): void {
  for (const o of extra) if (o) { o.removeFromParent(); disposeObject(o) }
  disposeObject(content)
  content.clear()
}

/** review K61: a load kept for the asset it was for — a pane that rebuilds on every body change parsed the shell's GLB each time; the same id
 *  gives the same promise, another id loads afresh (a failed load is tried again next time). */
export function loadOnce<T>(slot: { current: { id: string; p: Promise<T> } | null }, id: string, load: (id: string) => Promise<T>): Promise<T> {
  if (slot.current?.id === id) return slot.current.p
  const p = load(id)
  const mine = { id, p }
  slot.current = mine
  p.catch(() => { if (slot.current === mine) slot.current = null })
  return p
}
