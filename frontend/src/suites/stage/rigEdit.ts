// RG3 (D187 R4, D188 F4): the rigging screen's edits of a character's own hands and feet — pure, on the shapes the body keeps
// (body.hand_shape, body.foot_shape; orchestrator hands.py): the finger count, the claws, a finger's length and width, a foot's numbers, its
// stiff sole (D189) and its placement by hand, the left unlinked from the right or linked back (Q2). The Inspector saves the result.
import type { FingerName, FingerShape, HandShape, HandShapes } from './clayHand'
import type { FootShape, FootShapes } from './proxy'

export type Side = 'r' | 'l'
const clone = <T>(x: T): T => JSON.parse(JSON.stringify(x)) as T
const f3 = (x: number) => Math.round(x * 1000) / 1000

/** The human hand hands.py starts from (`human_fingers`): what *Start from a human hand* gives a character drawn by hand, not read. */
export function humanHand(): HandShape {
  const f = (base: [number, number], angle: number, len: number, split: [number, number, number], width: number): FingerShape =>
    ({ base, angle, lengths: split.map((s) => f3(len * s)), width, claw: null })
  const SPLIT: [number, number, number] = [0.45, 0.3, 0.25], THUMB: [number, number, number] = [0.4, 0.33, 0.27]
  return { count: 5, palm_width: 0.66, claw: 0, fingers: { thumb: f([0.3, 0.28], 45, 0.77, THUMB, 0.23), index: f([0.27, 0.96], 8, 0.67, SPLIT, 0.19),
    middle: f([0, 1], 0, 0.73, SPLIT, 0.19), ring: f([-0.2, 0.95], -8, 0.64, SPLIT, 0.18), pinky: f([-0.38, 0.86], -16, 0.48, SPLIT, 0.16) } }
}
/** hands.py FootShape's defaults: *Start from a plain foot*. */
export const plainFoot = (): FootShape => ({ pitch: 6, ankle_up: 0.44, ankle_at: 0.2, heel_up: 0.25, toe_up: 0.15, ball_at: 0.72, length_leg: null, stiff: false, place: null })

/** A side's hand as the shape keeps it: the left is the right's until it is unlinked. */
export const handOf = (h: HandShapes, side: Side): HandShape => (side === 'l' && h.left ? h.left : h.right)
export const linked = (h: { left?: unknown | null }): boolean => !h.left

function withHand(h: HandShapes, side: Side, fn: (x: HandShape) => HandShape): HandShapes {
  const next = clone(h)
  if (side === 'l' && next.left) next.left = fn(next.left)
  else next.right = fn(next.right)                                          // linked: the right is both
  return next
}

/** Q4: three, four or five fingers (the thumb counted) — a count hides the pinky, then the ring finger. */
export const setCount = (h: HandShapes, side: Side, count: 3 | 4 | 5): HandShapes => withHand(h, side, (x) => ({ ...x, count }))
/** Q5: the hand's claw, in palm lengths. */
export const setClaw = (h: HandShapes, side: Side, claw: number): HandShapes => withHand(h, side, (x) => ({ ...x, claw: f3(Math.max(0, Math.min(1, claw))) }))
/** A finger's length (its three segments scaled together), width or own claw (null: the hand's), in palm lengths. */
export function setFinger(h: HandShapes, side: Side, f: FingerName, patch: { length?: number; width?: number; claw?: number | null }): HandShapes {
  return withHand(h, side, (x) => {
    const cur = x.fingers[f]
    if (!cur) return x
    const now = cur.lengths.reduce((a, s) => a + s, 0) || 1
    const lengths = patch.length !== undefined ? cur.lengths.map((s) => f3(Math.max(0.02, (s * Math.max(0.06, Math.min(4.5, patch.length!))) / now))) : cur.lengths
    const width = patch.width !== undefined ? f3(Math.max(0.03, Math.min(0.8, patch.width))) : cur.width
    const claw = patch.claw !== undefined ? (patch.claw === null ? null : f3(Math.max(0, Math.min(1, patch.claw)))) : cur.claw
    return { ...x, fingers: { ...x.fingers, [f]: { ...cur, lengths, width, claw } } }
  })
}
/** Q2: *Unlink* — the left becomes a copy of the right, edited apart from then; *Link* — the left is the right's again. */
export const unlinkHands = (h: HandShapes): HandShapes => ({ ...clone(h), left: clone(h.right) })
export const linkHands = (h: HandShapes): HandShapes => ({ ...clone(h), left: null })

export const footOf = (f: FootShapes, side: Side): FootShape => (side === 'l' && f.left ? f.left : f.right)
/** A foot's numbers (in foot lengths), its stiff sole (D189) or its placement by hand (F4; null: found from the shape and the shell). */
export function setFoot(f: FootShapes, side: Side, patch: Partial<FootShape>): FootShapes {
  const next = clone(f)
  const fix = (x: FootShape): FootShape => {
    const out = { ...x, ...patch }
    for (const k of ['pitch', 'ankle_up', 'ankle_at', 'heel_up', 'toe_up', 'ball_at'] as const) if (patch[k] !== undefined) out[k] = f3(patch[k] as number)
    return out
  }
  if (side === 'l' && next.left) next.left = fix(next.left)
  else next.right = fix(next.right)
  return next
}
export const unlinkFeet = (f: FootShapes): FootShapes => ({ ...clone(f), left: clone(f.right) })
export const linkFeet = (f: FootShapes): FootShapes => ({ ...clone(f), left: null })

/** F4: a placement by hand — the heel, the ball and the toe as metres from the ankle in the figure's frame, the right foot's (a left foot's
 *  dragged point mirrored onto it while the feet are linked: the left is the right seen in a mirror). */
export function placeOffset(at: [number, number, number], ankle: [number, number, number], side: Side, isLinked: boolean): number[] {
  const o = [at[0] - ankle[0], at[1] - ankle[1], at[2] - ankle[2]]
  if (side === 'l' && isLinked) o[0] = -o[0]
  return o.map((x) => Math.round(Math.max(-0.6, Math.min(0.6, x)) * 10000) / 10000)
}
