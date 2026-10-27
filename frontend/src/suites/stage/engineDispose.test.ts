// V78 (the review of 2026-10-27): what leaves the stage frees its GPU resources — geometries, materials and their textures, each once
// however many meshes share it; the engine's shared materials stay (a rebuild would only compile them again).
import * as THREE from 'three'
import { describe, expect, it, vi } from 'vitest'
import { disposeObject } from './engine'

describe('disposeObject (V78)', () => {
  it('frees every geometry, material and texture under the root once, and keeps the shared materials', () => {
    const tex = new THREE.Texture()
    const shared = new THREE.MeshBasicMaterial()
    const own = new THREE.MeshBasicMaterial({ map: tex })
    const box = new THREE.BoxGeometry()
    const g = new THREE.Group()
    const a = new THREE.Mesh(box, shared)
    const b = new THREE.Mesh(new THREE.PlaneGeometry(), own)
    const c = new THREE.Mesh(box, own)                                          // the box and `own` shared by two meshes
    const inner = new THREE.Group(); inner.add(c)
    g.add(a, b, inner)
    const spies = { tex: vi.spyOn(tex, 'dispose'), shared: vi.spyOn(shared, 'dispose'), own: vi.spyOn(own, 'dispose'), box: vi.spyOn(box, 'dispose'), plane: vi.spyOn(b.geometry, 'dispose') }
    expect(disposeObject(g, new Set([shared]))).toEqual({ geometries: 2, materials: 1, textures: 1 })
    expect(spies.shared).not.toHaveBeenCalled()
    expect(spies.own).toHaveBeenCalledTimes(1)
    expect(spies.tex).toHaveBeenCalledTimes(1)
    expect(spies.box).toHaveBeenCalledTimes(1)
    expect(spies.plane).toHaveBeenCalledTimes(1)
  })

  it('with nothing to keep (the engine ending) frees the shared materials too, and tolerates objects without geometry', () => {
    const shared = new THREE.MeshBasicMaterial()
    const g = new THREE.Group()
    g.add(new THREE.Mesh(new THREE.BoxGeometry(), [shared, shared]), new THREE.Object3D(), new THREE.PointLight())
    const spy = vi.spyOn(shared, 'dispose')
    expect(disposeObject(g)).toEqual({ geometries: 1, materials: 1, textures: 0 })
    expect(spy).toHaveBeenCalledTimes(1)
  })
})
