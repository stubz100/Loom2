// RG1 (D187, D188): the hand and feet slots' read state, in a few words (rule 11) — shared by the slots (CastParts) and their tests.
import type { Job, Profile } from '../../api/types'

/** RG1: what a hand or feet picture's read says — reading, read (a few words of what), failed (the note), or not read. The feet are read
 *  from the A-pose side view while there is no feet picture. */
export function partRead(v: Profile['versions'][number], part: 'hand' | 'feet', jobs: Record<string, Job> | Job[], pid: string): { state: 'reading' | 'read' | 'failed' | 'unread'; text: string; note?: string } {
  const surface = part === 'hand' ? 'hand_fit' : 'feet_fit'
  const busy = Object.values(jobs).some((j) => j.origin?.surface === surface && j.origin.ref === pid && (j.origin.payload as { version?: string } | null)?.version === v.id && !['done', 'failed', 'cancelled'].includes(j.status))
  if (busy) return { state: 'reading', text: 'reading…' }
  const note = part === 'hand' ? v.hand_note : v.feet_note
  if (note) return { state: 'failed', text: 'not read', note }
  const pts = (part === 'hand' ? v.hand_points : v.feet_points) as { from?: string } | null
  const src = part === 'hand' ? v.hand_ref_asset_id : v.feet_ref_asset_id ?? v.anim_ref_side_asset_id
  if (!pts || !src || pts.from !== src) return { state: 'unread', text: 'not read' }
  const b = v.body
  if (part === 'hand' && b?.hand_shape) {
    const mid = b.hand_shape.right.fingers.middle?.lengths.reduce((a, x) => a + x, 0) ?? 0
    return { state: 'read', text: `${b.hand_shape.right.count} fingers · middle ${mid.toFixed(2)} palms` }
  }
  if (part === 'feet' && b?.foot_shape) return { state: 'read', text: `read${!v.feet_ref_asset_id ? ' from the side view' : ''} · pitch ${Math.round(b.foot_shape.right.pitch)}°` }
  return { state: 'read', text: 'read' }
}
