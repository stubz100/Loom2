// D180 (W60): a built set's thing as a stage object of its own — its 3D model when it has one, else its card (the cut-out on an image
// plane) — standing where the set picture shows it: its base in the set's frame carried through the set object's transform, turned to
// face the picture's camera. Clay keys it like any object (the ferry sails).
import type { StageObject } from '../../api/types'

/** A thing of a place's set (the server's PlaceThing). */
export interface Thing { id: string; name: string; card_asset_id: string; mesh_asset_id: string | null; base: number[]; width_m: number; height_m: number; yaw_deg: number }

const PLANE_W = 1.6, PLANE_H = 0.9, PLANE_Y = 0.9                                        // engine.ts: an image plane is 1.6 m wide, centred 0.9 m up

/** The point of the set's frame on the stage: the set object's turn about y and its position (a built set is not scaled). */
export function onStage(set: Pick<StageObject, 'transform'>, p: number[]): number[] {
  const a = ((set.transform.rot[1] ?? 0) * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a)
  const [x, y, z] = p
  return [set.transform.pos[0] + x * c + z * s, set.transform.pos[1] + y, set.transform.pos[2] - x * s + z * c].map((v) => Math.round(v * 1000) / 1000 + 0)   // + 0: no −0
}

/** The fields of the stage object a thing becomes (the store adds its id and the rest of a new object's defaults). */
export function thingFields(t: Thing, set: Pick<StageObject, 'transform' | 'profile_id'>): Partial<StageObject> & { kind: 'mesh' | 'plane' } {
  const yaw = (set.transform.rot[1] ?? 0) + t.yaw_deg
  const base = onStage(set, t.base)
  if (t.mesh_asset_id) {
    return { kind: 'mesh', name: t.name, asset_id: t.mesh_asset_id, height_m: t.height_m, transform: { pos: base, rot: [0, yaw, 0], scale: [1, 1, 1] } }
  }
  const s = t.width_m / PLANE_W
  const k = (t.height_m / Math.max(1e-6, t.width_m)) / (PLANE_H / PLANE_W)              // the plane's height as the engine scales it to the card
  const lift = s * (PLANE_Y - (PLANE_H * k) / 2)                                          // its bottom at the base, not its centre at 0.9 m
  return { kind: 'plane', name: t.name, asset_id: t.card_asset_id, billboard: false,
    transform: { pos: [base[0], Math.round((base[1] - lift) * 1000) / 1000, base[2]], rot: [0, yaw, 0], scale: [s, s, s] } }
}
