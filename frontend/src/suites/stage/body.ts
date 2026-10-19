// CA0 (D94, proto01_animate 01 §9): a character's body — on the Cast sheet, copied onto the bound Stage figure, where builders.mannequin
// shapes the dummy from it. No three.js here: Cast (Story's bundle) draws its silhouette from the same numbers the dummy is built with.
/** CA0 (01 §9): a character's body from its Cast sheet (the server's `body.Body`) — height in metres, proportions as factors of the default
 *  dummy, a build, rigid attachments. */
export interface Body {
  height_m: number; build: 'slim' | 'average' | 'broad' | 'heavy'; head: number; torso: number; shoulders: number; arms: number; legs: number
  neck: number; hands: number; feet: number                                // CA1b (D104): fitted from the animation reference
  attachments: { kind: 'tail' | 'horns' | 'ears' | 'wings' | 'antennae' | 'hat' | 'backpack' | 'other'; joint: string | null; size: number; note: string }[]
}
export const DEFAULT_BODY: Body = { height_m: 1.75, build: 'average', head: 1, torso: 1, shoulders: 1, arms: 1, legs: 1, neck: 1, hands: 1, feet: 1, attachments: [] }
export const BUILD_WIDTH: Record<Body['build'], number> = { slim: 0.85, average: 1, broad: 1.15, heavy: 1.3 }
export type Limbs = { upper_arm: number; forearm: number; thigh: number; shin: number }

/** The body's dimensions in the dummy's own units (before the height scale): limb lengths, the standing hip height, the head top. */
export function bodyDims(b: Body | null | undefined) {
  const x = b ?? DEFAULT_BODY
  const limbs: Limbs = { upper_arm: 0.29 * x.arms, forearm: 0.27 * x.arms, thigh: 0.44 * x.legs, shin: 0.43 * x.legs }
  const hip = b ? 0.07 + 0.88 * x.legs : 0.95
  const top = hip + 0.06 + 0.44 * x.torso + 0.06 * (x.neck ?? 1) + 0.221 * x.head
  return { limbs, hip, top, scale: b ? x.height_m / top : 1 }
}
