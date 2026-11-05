// D190 (proto01_rig 00 §15): the skeleton panel's pictures to pick a hand or feet picture from — kept apart from RigPanel.tsx, a
// components-only file.
import type { components } from '../../api/schema'
import type { Profile } from '../../api/types'

export type BinItem = components['schemas']['BinItem']
export type Part = 'hand' | 'feet'
type Version = Profile['versions'][number]

/** A part's pictures to pick from: those made as one (the newest first), the A-pose views (the side view first for the feet: E62 c read a
 *  side-view figure's feet at 0.78–0.92), and the version's other pictures. */
export function picturesFor(items: BinItem[], v: Pick<Version, 'anim_ref_asset_id' | 'anim_ref_back_asset_id' | 'anim_ref_side_asset_id'>, part: Part) {
  const imgs = items.filter((x) => x.asset.kind === 'image')
  const madeAs = (x: BinItem) => x.asset.origin?.surface === 'anim_ref' && (x.asset.origin.payload as { side?: string } | null)?.side === part
  const made = imgs.filter(madeAs).sort((a, b) => String(b.asset.created_at ?? '').localeCompare(String(a.asset.created_at ?? '')))
  const viewIds = (part === 'feet' ? [v.anim_ref_side_asset_id, v.anim_ref_asset_id, v.anim_ref_back_asset_id] : []).filter(Boolean) as string[]   // a hand is read from a close-up
  const views = viewIds.map((id) => imgs.find((x) => x.asset.id === id)).filter((x): x is BinItem => !!x && !madeAs(x))
  const others = imgs.filter((x) => !madeAs(x) && !viewIds.includes(x.asset.id))
  return { made, views, others }
}
