// C0 (D181, propo02 04 §4.2): the Clay readiness of an entity version — what its 3D still needs before it can stand in a scene. World's
// line says the pictures (ui2/world/readiness.ts); this one the body, the model and the set made from them. Pure, from the version's record.
import type { Profile, ProfileVersion } from '../../api/types'
import { bodyText, type ReadyItem } from '../world/readiness'

export interface ClayReadiness { items: ReadyItem[]; owed: number; line: string }

const item = (id: string, label: string, done: boolean, detail?: string, optional = false): ReadyItem =>
  ({ id, label, state: done ? 'done' : optional ? 'optional' : 'owed', ...(detail ? { detail } : {}) })

/** The 3D readiness: a figure's A-pose (a World picture), body and shell; a prop's picture, model and height; a set's picture, build and fills. */
export function clayReadiness(p: Pick<Profile, 'cls'>, v: ProfileVersion): ClayReadiness {
  let items: ReadyItem[]
  if (p.cls === 'character') {
    items = [
      item('a_pose', 'A-pose', !!v.anim_ref_asset_id, v.anim_ref_asset_id ? undefined : '— in World'),
      item('body', 'body fitted', !!v.body_fit_from, v.body_fit_from && v.body ? bodyText(v.body) : v.anim_ref_note === 'not_whole' ? '— the A-pose is cut'
        : v.anim_ref_note === 'several' ? '— the A-pose shows more than one figure' : undefined),
      item('shell', 'shell', !!v.shell_asset_id),
      item('back', 'back view', !!v.anim_ref_back_asset_id, undefined, true),
    ]
  } else if (p.cls === 'prop') {
    items = [item('picture', 'picture', !!(v.anim_ref_asset_id || v.hero_asset_id), v.anim_ref_asset_id || v.hero_asset_id ? undefined : '— in World'),
      item('model', '3D model', !!v.model_asset_id), item('height', 'height', !!v.height_m, v.height_m ? `${v.height_m} m` : undefined)]
  } else {
    const ps = v.place_set, faces = ps?.faces ?? []
    const ok = faces.filter((f) => f.filled || !f.bad).length
    const pct = faces.length ? Math.round((100 * ok) / faces.length) : 0
    items = [item('set_picture', 'set picture', !!ps?.sources.length, ps?.sources.length ? undefined : '— in World'), item('set', 'set built', faces.length > 0),
      item('faces', 'faces filled', faces.length > 0 && ok === faces.length, faces.length ? `${pct} %` : undefined)]
  }
  const owed = items.filter((x) => x.state === 'owed').length
  return { items, owed, line: owed ? `${owed} to go` : 'Ready for a scene' }
}
