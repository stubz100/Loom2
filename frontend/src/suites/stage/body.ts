// CA0 (D94, proto01_animate 01 §9): a character's body — on the Cast sheet, copied onto the bound Stage figure, where builders.mannequin
// shapes the dummy from it. No three.js here: Cast (Story's bundle) draws its silhouette from the same numbers the dummy is built with.
/** CA0 (01 §9): a character's body from its Cast sheet (the server's `body.Body`) — height in metres, proportions as factors of the default
 *  dummy, a build, rigid attachments. */
export interface Body {
  height_m: number; build: 'slim' | 'average' | 'broad' | 'heavy'; head: number; torso: number; shoulders: number; arms: number; legs: number
  neck: number; hands: number; feet: number                                // CA1b (D104): fitted from the animation reference
  hips: number; elbow: number; knee: number                                // proto01_UIcast CS1 (S6, S7): the hips' width, the elbow's and knee's places
  figure: 'female' | 'male'                                                // U18: the Detailed mannequin (the Simple dummy retired)
  hand_rest: { preset: 'open' | 'relaxed' | 'fist' | 'point' | 'grip' | 'pinch'; curl: number; spread: number; thumb: number }   // S2 (CS2: spread, thumb)
  head_forward: number; shoulder_drop: number; feet_out: number             // CS2: the head carried forward (°), the shoulders' drop (×), the feet out (°)
  locks: string[]                                                          // CS2: the factors *Fit again* leaves as the author set them
  attachments: { kind: 'tail' | 'horns' | 'ears' | 'wings' | 'antennae' | 'hat' | 'backpack' | 'other'; joint: string | null; size: number; note: string }[]
}
/** S6: the upper arm's and the thigh's shares of their limbs at ×1 (0.29 + 0.27, 0.44 + 0.43): body.py ELBOW_AT, KNEE_AT. */
export const ELBOW_AT = 29 / 56, KNEE_AT = 44 / 87
export const DEFAULT_BODY: Body = { height_m: 1.75, build: 'average', head: 1, torso: 1, shoulders: 1, arms: 1, legs: 1, neck: 1, hands: 1, feet: 1,
  hips: 1, elbow: ELBOW_AT, knee: KNEE_AT, figure: 'female', hand_rest: { preset: 'relaxed', curl: 1, spread: 0, thumb: 0 }, head_forward: 0, shoulder_drop: 1,
  feet_out: 0, locks: [], attachments: [] }
export const BUILD_WIDTH: Record<Body['build'], number> = { slim: 0.85, average: 1, broad: 1.15, heavy: 1.3 }
export type Limbs = { upper_arm: number; forearm: number; thigh: number; shin: number }

/** The body's dimensions in the dummy's own units (before the height scale): limb lengths, the standing hip height, the head top. */
export function bodyDims(b: Body | null | undefined) {
  const x = b ?? DEFAULT_BODY
  const elbow = x.elbow ?? ELBOW_AT, knee = x.knee ?? KNEE_AT                // S6 (a body stored before CS1 has neither: ×1's places)
  const limbs: Limbs = { upper_arm: 0.29 * x.arms * (elbow / ELBOW_AT), forearm: 0.27 * x.arms * ((1 - elbow) / (1 - ELBOW_AT)),   // ×1's 0.29 / 0.27 exactly
    thigh: 0.44 * x.legs * (knee / KNEE_AT), shin: 0.43 * x.legs * ((1 - knee) / (1 - KNEE_AT)) }
  const hip = b ? 0.07 + 0.88 * x.legs : 0.95
  const lean = Math.cos(((x.head_forward ?? 0) * Math.PI) / 180)          // CS2: a head carried forward stands a little lower
  const top = hip + 0.06 + 0.44 * x.torso + 0.12 * (x.neck ?? 1) * lean + 0.161 * x.head    // S3: the neck to the head's pivot, the head's top above it
  return { limbs, hip, top, scale: b ? x.height_m / top : 1 }
}
