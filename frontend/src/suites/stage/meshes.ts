// proto01_UIcast CF9 (CW0): a Catalogue mesh named by where it came from — a Cast prop's model, a picture set's thing, an imported GLB, a
// picture's "Make a 3D prop…" — instead of "prop ‹id›"; and whether it is a prop at all (a picture set's relief is a set: Sets › From an
// image… places it, so Clay's Meshes leaves it out). Pure: the Bin, Clay's Meshes and the tests share it.
import type { Asset, Profile } from '../../api/types'

export type MeshSource = 'prop' | 'thing' | 'import' | 'picture' | 'relief'
export interface MeshLabel { source: MeshSource; label: string; hint: string; profileId?: string }

const day = (iso: string | null | undefined) => { const d = iso ? new Date(iso) : null; return d && !Number.isNaN(+d) ? d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' }) : '' }

/** The mesh's name and where it came from. `names` maps an asset id to the name a stage object gives it (a thing keeps its name there). */
export function meshLabel(a: Pick<Asset, 'id' | 'lineage_kind' | 'origin' | 'params' | 'created_at'>, profiles: Pick<Profile, 'id' | 'name' | 'cls' | 'versions'>[],
                          names?: ReadonlyMap<string, string>): MeshLabel {
  const owner = profiles.find((p) => p.cls === 'prop' && p.versions.some((v) => v.model_asset_id === a.id))
  if (owner) return { source: 'prop', label: owner.name, hint: `${owner.name}'s 3D model (a Cast prop)`, profileId: owner.id }
  if (a.lineage_kind === 'image-to-set') return { source: 'relief', label: 'picture-set relief', hint: "a picture set's relief (Sets › From an image…)" }
  const o = a.origin
  if (o?.surface === 'set_thing_model') return { source: 'thing', label: names?.get(a.id) ?? 'a thing', hint: "a thing of a picture set (Things in the picture…)" }
  const imported = (a.params as { imported_from?: string } | null | undefined)?.imported_from
  if (imported) return { source: 'import', label: imported.split(/[\\/]/).pop()!.replace(/\.glb$/i, ''), hint: `imported from ${imported}` }
  if (o?.surface === 'prop_model' && o.ref) {
    const p = profiles.find((x) => x.id === o.ref)
    return { source: 'prop', label: p ? `${p.name} · earlier model` : "a Cast prop's earlier model", hint: 'a model made for a Cast prop, no longer its current one', profileId: p?.id }
  }
  return { source: 'picture', label: names?.get(a.id) ?? `3D model · ${day(a.created_at)}`.replace(/ · $/, ''), hint: 'made from a picture (Make a 3D prop…)' }
}

/** Clay's Meshes: what can stand on a stage as a prop — every mesh but a picture set's relief. */
export const propMeshes = <A extends Pick<Asset, 'lineage_kind'>>(meshes: A[]): A[] => meshes.filter((m) => m.lineage_kind !== 'image-to-set')
