// U3 (D157, proto01_UI2 03 §2): the readiness line — what an entity version still needs before Clay can use it. Each item is done, owed or
// optional; the line ends in "Ready for Clay" or "N to go". Pure, from the version's record and its reference count.
import type { Profile, ProfileVersion } from '../../api/types'

export interface ReadyItem { id: string; label: string; state: 'done' | 'owed' | 'optional'; detail?: string }
export interface Readiness { items: ReadyItem[]; owed: number; line: string }

const item = (id: string, label: string, done: boolean, detail?: string, optional = false): ReadyItem =>
  ({ id, label, state: done ? 'done' : optional ? 'optional' : 'owed', ...(detail ? { detail } : {}) })

/** D168 (M9): a body as the readiness chip says it — the figure, the height, the build ("♂ 1.80 m · heavy"). */
export const bodyText = (b: { figure?: string | null; height_m: number; build: string }): string => `${b.figure === 'male' ? '♂' : '♀'} ${b.height_m.toFixed(2)} m · ${b.build}`

export function readiness(p: Pick<Profile, 'cls' | 'voice_id'>, v: ProfileVersion, refs: number): Readiness {
  let items: ReadyItem[]
  if (p.cls === 'character') {
    items = [
      item('hero', 'hero', !!v.hero_asset_id),
      item('references', 'references', refs > 0, String(refs)),
      item('a_pose_front', 'A-pose front', !!v.anim_ref_asset_id),
      item('a_pose_back', 'A-pose back', !!v.anim_ref_back_asset_id, undefined, true),
      item('body', 'body fitted', !!v.body_fit_from, v.body_fit_from && v.body ? bodyText(v.body) : undefined),   // D168: what the body is, so a wrong one shows
      item('voice', 'voice', !!p.voice_id, undefined, true),
    ]
  } else if (p.cls === 'prop') {
    items = [item('hero', 'hero', !!v.hero_asset_id), item('model', '3D model', !!v.model_asset_id), item('height', 'height', !!v.height_m, v.height_m ? `${v.height_m} m` : undefined)]
  } else {
    const ps = v.place_set, faces = ps?.faces ?? []
    const ok = faces.filter((f) => f.filled || !f.bad).length
    const pct = faces.length ? Math.round((100 * ok) / faces.length) : 0
    items = [item('set_picture', 'set picture', !!ps?.sources.length), item('set', 'set built', faces.length > 0),
      item('faces', 'faces filled', faces.length > 0 && ok === faces.length, faces.length ? `${pct} %` : undefined)]
  }
  const owed = items.filter((x) => x.state === 'owed').length
  return { items, owed, line: owed ? `${owed} to go` : 'Ready for Clay' }
}
