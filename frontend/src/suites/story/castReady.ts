// D125 (S5, proto01_UIcomp 04 §3.3; SP5): a Cast version's readiness for the shots it is in — the row under the strip (Hero · Sheet ·
// References · Animation reference · Body / 3D model · Voice · LoRA · Final, by class), each item done, owed (a shot that uses the profile
// needs it) or open (no shot needs it yet); *In N shots* and what each shot needs; the next owed item for the foot. The uses come from the
// server (GET /story/cast/uses); the rest is read from the profile. Pure: castReady.test.ts.
import type { CastUse, Profile, ProfileVersion } from '../../api/types'
import { sheetEmpty } from '../generate/sheet'

export type ReadyItem = 'hero' | 'sheet' | 'refs' | 'animref' | 'body' | 'model' | 'voice' | 'lora' | 'final'
export type ReadyState = 'done' | 'owed' | 'open'
export interface ReadyCell { item: ReadyItem; state: ReadyState; text?: string; shots: string[] }

/** The items a class has: a place has no animation reference, body or voice; a prop has a 3D model instead of a body. */
export const ITEMS_OF: Record<Profile['cls'], ReadyItem[]> = {
  character: ['hero', 'sheet', 'refs', 'animref', 'body', 'voice', 'lora', 'final'],
  place: ['hero', 'sheet', 'refs', 'lora', 'final'],
  prop: ['hero', 'sheet', 'refs', 'animref', 'model', 'lora', 'final'],
}
export const ITEM_LABEL: Record<ReadyItem, string> = { hero: 'Hero', sheet: 'Sheet', refs: 'References', animref: 'Animation reference', body: 'Body', model: '3D model', voice: 'Voice', lora: 'LoRA', final: 'Final' }

/** What a shot needs from the profile, by how it uses it and its route: every use its hero, sheet, references and a final version; a
 *  speaker its voice; a figure on a clay route the animation reference and the body; a prop's mesh its 3D model (and on a clay route the
 *  animation reference). A LoRA is never needed (advisory). */
export function needsOf(u: Pick<CastUse, 'how' | 'route'>, cls: Profile['cls']): ReadyItem[] {
  const need = new Set<ReadyItem>(['hero', 'sheet', 'refs', 'final'])
  const clay = u.route.startsWith('clay')
  if (u.how.includes('speaker')) need.add('voice')
  if (u.how.includes('figure') && clay) { need.add('animref'); need.add('body') }
  if (u.how.includes('prop')) { need.add('model'); if (clay) need.add('animref') }
  return ITEMS_OF[cls].filter((i) => need.has(i))
}

/** Whether the version has each item (the voice is the profile's). `refs` undefined: the count is not known yet (counted as none). */
export function doneOf(p: Pick<Profile, 'cls' | 'voice_id'>, v: ProfileVersion, refs: number | undefined): Record<ReadyItem, boolean> {
  return {
    hero: !!v.hero_asset_id, sheet: !sheetEmpty(v, p.cls), refs: (refs ?? 0) > 0, animref: !!v.anim_ref_asset_id, body: !!v.body,
    model: !!v.model_asset_id, voice: !!p.voice_id, lora: !!v.lora, final: v.state === 'final',
  }
}

/** The readiness row of a version: each item of its class with the shots that need it. */
export function readinessOf(p: Pick<Profile, 'cls' | 'voice_id'>, v: ProfileVersion, uses: CastUse[], refs: number | undefined): ReadyCell[] {
  const done = doneOf(p, v, refs)
  return ITEMS_OF[p.cls].map((item) => {
    const shots = uses.filter((u) => needsOf(u, p.cls).includes(item)).map((u) => u.name)
    return { item, state: done[item] ? 'done' : shots.length ? 'owed' : 'open', shots, ...(item === 'refs' && refs !== undefined ? { text: String(refs) } : {}) }
  })
}

/** The first owed item (the foot's next step), or null. */
export const nextOwed = (cells: ReadyCell[]): ReadyCell | null => cells.find((c) => c.state === 'owed') ?? null

/** A Cast row's line: what the current version owes for its shots, or that it is ready for them. */
export function rowSummary(cells: ReadyCell[], uses: CastUse[]): string {
  const n = new Set(uses.map((u) => u.shot_id)).size
  if (!n) return 'in no shot'
  const owed = cells.filter((c) => c.state === 'owed').length
  const shots = `${n} shot${n === 1 ? '' : 's'}`
  return owed ? `${owed} owed for ${shots}` : `ready for ${shots}`
}

/** What a use needs from the profile and still lacks, in words ("clay final shot: animation reference, body"), for *In N shots*. */
export function shotNeeds(u: CastUse, cells: ReadyCell[], cls: Profile['cls']): string[] {
  const owed = new Set(cells.filter((c) => c.state !== 'done').map((c) => c.item))
  return needsOf(u, cls).filter((i) => owed.has(i)).map((i) => ITEM_LABEL[i].toLowerCase())
}
