// D173 (M6, E49c): a crowd on a set's face — a loop made from the face's own texture with people along it, played over a stretch of
// the face (metres from its origin along u, its whole height) on a plane just off it. Pure: the frame mapping and the plane's place.
import * as THREE from 'three'
import type { Face } from './placeSet'

export const STAGE_FPS = 24                                                     // the stage's frames (finalShot.framesAt steps 24 / rate)

/** The clip's frame at a stage frame: the clip's rate over the stage's, looping over its first n − 1 frames (the last is the first again,
 *  the server's tone lock made it so). */
export function clipFrame(stageFrame: number, fps: number, frames: number, stageFps = STAGE_FPS): number {
  const loop = Math.max(1, frames - 1)
  const k = Math.floor((Math.max(0, stageFrame) / stageFps) * fps + 1e-6)
  return k % loop
}

/** D174: a walkers' packed clip — its colour on the left half, its mask on the right — as two textures' repeat and offset. */
export const PACKED = { colour: { repeat: [0.5, 1], offset: [0, 0] }, mask: { repeat: [0.5, 1], offset: [0.5, 0] } } as const
/** D173 / D174: how far off the face a layer's plane stands — the crowd's clip, then the walkers over it. */
export const LIFT = { crowd: 0.002, walkers: 0.003 } as const

/** Where the crowd's plane stands: over [from, to] along the face's u (clamped to the face), its whole height, `lift` metres off the face
 *  toward the inside (its normal `n`) so it draws over the face's texture. */
export function crowdPlane(f: Face, n: THREE.Vector3, fromM: number, toM: number, lift = 0.002): { centre: THREE.Vector3; w: number; h: number } {
  const a = Math.max(0, Math.min(f.w, fromM)), b = Math.max(a, Math.min(f.w, toM))
  return { centre: f.origin.clone().addScaledVector(f.u, (a + b) / 2).addScaledVector(f.v, f.h / 2).addScaledVector(n, lift), w: b - a, h: f.h }
}
