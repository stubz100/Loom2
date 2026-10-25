// proto01_UIcast CF9 (CW0): a Catalogue mesh named by where it came from, and a picture set's relief kept out of Clay's Meshes.
import { describe, expect, it } from 'vitest'
import type { Asset, Profile } from '../../api/types'
import { meshLabel, propMeshes } from './meshes'

const mesh = (id: string, extra: Partial<Asset> = {}) => ({ id, lineage_kind: 'image-to-mesh', origin: null, params: {}, created_at: '2026-10-20T07:51:50+00:00', ...extra }) as Asset
const prop = (id: string, name: string, models: (string | null)[]) => ({ id, name, cls: 'prop', versions: models.map((m, i) => ({ id: `v${i + 1}`, model_asset_id: m })) }) as unknown as Profile

describe("a mesh's name (proto01_UIcast CF9)", () => {
  const profiles = [prop('prf_lamp', 'Lantern', ['ast_old', 'ast_lamp']), { id: 'prf_mara', name: 'Mara', cls: 'character', versions: [] } as unknown as Profile]
  it("a Cast prop's model is named by its prop (any version's)", () => {
    expect(meshLabel(mesh('ast_lamp'), profiles)).toMatchObject({ source: 'prop', label: 'Lantern', profileId: 'prf_lamp' })
    expect(meshLabel(mesh('ast_old'), profiles).label).toBe('Lantern')
  })
  it('a model made for a prop and since replaced says so', () => {
    const m = mesh('ast_gone', { origin: { suite: 'story', surface: 'prop_model', ref: 'prf_lamp', payload: {} } })
    expect(meshLabel(m, profiles)).toMatchObject({ source: 'prop', label: 'Lantern · earlier model' })
  })
  it("a picture set's thing takes the name its stage gives it; an imported GLB its file's", () => {
    const thing = mesh('ast_cup', { origin: { suite: 'stage', surface: 'set_thing_model', ref: 'stg_1', payload: {} } })
    expect(meshLabel(thing, profiles, new Map([['ast_cup', 'Teacup']]))).toMatchObject({ source: 'thing', label: 'Teacup' })
    expect(meshLabel(thing, profiles).label).toBe('a thing')
    expect(meshLabel(mesh('ast_imp', { lineage_kind: null, params: { imported_from: 'D:\\models\\Old chair.glb' } }), profiles)).toMatchObject({ source: 'import', label: 'Old chair' })
  })
  it('a picture\'s "Make a 3D prop…" is dated; a relief is a set and leaves Clay\'s Meshes', () => {
    const l = meshLabel(mesh('ast_new'), profiles)
    expect(l.source).toBe('picture')
    expect(l.label).toMatch(/^3D model · \S/)                                          // the day it was made, in the locale's words
    const relief = mesh('ast_rel', { lineage_kind: 'image-to-set' })
    expect(meshLabel(relief, profiles).source).toBe('relief')
    expect(propMeshes([mesh('a'), relief, mesh('b')]).map((m) => m.id)).toEqual(['a', 'b'])
  })
})
