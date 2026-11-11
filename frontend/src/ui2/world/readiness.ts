// U3 (D157, proto01_UI2 03 §2): the readiness line — what an entity version still needs of its pictures. Each item is done, owed or
// optional; the line ends in "Pictures done" or "N to go". Pure, from the version's record and its reference count. RS1 (D197): the 3D
// (the body, the shell, the model, the set — `clayReadiness`, below) follows on the same line: `entityReadiness`.
import type { Profile, ProfileVersion } from '../../api/types'
import { sentColours } from '../../suites/generate/sheet'

export interface ReadyItem { id: string; label: string; state: 'done' | 'owed' | 'optional' | 'warn'; detail?: string }
export interface Readiness { items: ReadyItem[]; owed: number; line: string }

const item = (id: string, label: string, done: boolean, detail?: string, optional = false): ReadyItem =>
  ({ id, label, state: done ? 'done' : optional ? 'optional' : 'owed', ...(detail ? { detail } : {}) })

/** D168 (M9): a body as the readiness chip says it — the figure, the height, the build ("♂ 1.80 m · heavy"). */
export const bodyText = (b: { figure?: string | null; height_m: number; build: string }): string => `${b.figure === 'male' ? '♂' : '♀'} ${b.height_m.toFixed(2)} m · ${b.build}`

/** M3: the bound colours a prompt carries ("#C0392B apron, …"), the object (lower case) → the hex (upper case). */
export function colourClauses(text: string): Map<string, string> {
  return new Map([...text.matchAll(/#([0-9A-F]{6}) ([^,".;\n]+)/gi)].map((m) => [m[2].trim().toLowerCase(), `#${m[1].toUpperCase()}`]))   // a clause ends at a comma, or the tree's quote, or a sentence's end
}

/** M3: where a picture made from the sheet disagrees with the sheet's colours now — "apron #C0392B, the sheet #F5F5F5", "no boots colour".
 *  Empty when it agrees, or when the picture has no prompt (an import, a sketch). */
export function sheetDrift(v: Pick<ProfileVersion, 'colours'>, prompt: string | null | undefined): string[] {
  if (!prompt) return []
  const had = colourClauses(prompt)
  return [...colourClauses(sentColours(v).join(', '))].flatMap(([obj, hex]) => {
    const was = had.get(obj)
    return was === hex ? [] : [was ? `${obj} ${was}, the sheet ${hex}` : `no ${obj} colour (the sheet ${hex})`]
  })
}

const DRIFT_ROLES = [['hero', 'hero'], ['a_pose_front', 'A-pose']] as const

const WORN = /\b(tattoo|scar|bandage|ring|watch|bracelet|glove|sleeve|mark|birthmark|burn|cuff)s?\b/i
/** M4: the things a character's words have it carry ("a wicker shopping basket on her arm", "carrying a lantern") — its A-pose leaves them
 *  out (no props, the hands open for the fit), so a performance has them only from the words and they come and go. A Cast prop held in
 *  Clay keeps one. Worn things (a ring, a watch, a tattoo) are not carried; the marks are not read. */
export function carriedThings(v: Pick<ProfileVersion, 'appearance' | 'outfit'>): string[] {
  const text = [v.appearance, v.outfit].filter(Boolean).join(', ')
  const thing = String.raw`\b(an?\s+(?:(?!\ban?\s)[^,.;])+?)`
  const found = [...text.matchAll(new RegExp(String.raw`\b(?:carrying|holding|clutching|gripping)\s+` + thing + String.raw`(?=\s+(?:in|on|over|under)\s|[,.;]|$)`, 'gi')),
    ...text.matchAll(new RegExp(thing + String.raw`\s+(?:on|over|under|in)\s+(?:her|his|their)\s+(?:arms?|forearms?|hands?|fists?)\b`, 'gi'))].map((m) => m[1].trim())
  return [...new Set(found)].filter((x) => !WORN.test(x))
}

export function readiness(p: Pick<Profile, 'cls' | 'voice_id'>, v: ProfileVersion, refs: number, prompts: Partial<Record<'hero' | 'a_pose_front', string | null>> = {}): Readiness {
  let items: ReadyItem[]
  if (p.cls === 'character') {
    items = [
      item('hero', 'hero', !!v.hero_asset_id),
      item('references', 'references', refs > 0, String(refs)),
      item('a_pose_front', 'A-pose front', !!v.anim_ref_asset_id),
      item('a_pose_back', 'A-pose back', !!v.anim_ref_back_asset_id, undefined, true),
      item('a_pose_side', 'A-pose side', !!v.anim_ref_side_asset_id, undefined, true),   // D175: a character seen from the side
      item('hand_picture', 'hand picture', !!v.hand_ref_asset_id, undefined, true),         // RG1 (D187): its own hands
      item('feet_picture', 'feet picture', !!v.feet_ref_asset_id, undefined, true),         // RG1 (D188): its own feet and shoes
      ...(v.anim_ref_note === 't_pose' ? [{ id: 'tpose', label: 'A-pose is a T-pose', state: 'warn' as const, detail: 'the arms are held level, not about 30° out' }] : []),   // W11
      item('voice', 'voice', !!p.voice_id, undefined, true),
      ...DRIFT_ROLES.flatMap(([role, label]) => { const d = sheetDrift(v, prompts[role])                // M3: made before the sheet's colours took — said, not counted
        return d.length ? [{ id: `drift_${role}`, label: `${label} ≠ sheet`, state: 'warn' as const, detail: d.join('; ') }] : [] }),
      ...(carriedThings(v).length ? [{ id: 'carried', label: `carried: ${carriedThings(v).map((x) => x.replace(/^an?\s+/i, '')).join(', ')}`, state: 'warn' as const,
        detail: carriedThings(v).join('; ') }] : []),                                              // M4: the A-pose leaves it out
    ]
  } else if (p.cls === 'prop') {
    items = [item('hero', 'hero', !!v.hero_asset_id), item('reference', 'reference view', !!v.anim_ref_asset_id, undefined, true)]   // the model is made from either
  } else {
    items = [item('set_picture', 'set picture', !!(v.place_set?.sources.length || v.anim_ref_asset_id))]
  }
  const owed = items.filter((x) => x.state === 'owed').length
  return { items, owed, line: owed ? `${owed} to go` : 'Pictures done' }
}

export interface ClayReadiness { items: ReadyItem[]; owed: number; line: string }

/** C0 (D181) → RS1: the 3D readiness of an entity version — a figure's A-pose (a picture), body and shell; a prop's picture, model and
 *  height; a set's picture, build and fills. Pure, from the version's record. */
export function clayReadiness(p: Pick<Profile, 'cls'>, v: ProfileVersion): ClayReadiness {
  let items: ReadyItem[]
  if (p.cls === 'character') {
    items = [
      item('a_pose', 'A-pose', !!v.anim_ref_asset_id, v.anim_ref_asset_id ? undefined : '— in Make'),
      item('body', 'body fitted', !!v.body_fit_from, v.body_fit_from && v.body ? bodyText(v.body) : v.anim_ref_note === 'not_whole' ? '— the A-pose is cut'
        : v.anim_ref_note === 'several' ? '— the A-pose shows more than one figure' : undefined),
      item('shell', 'shell', !!v.shell_asset_id),
      item('back', 'back view', !!v.anim_ref_back_asset_id, undefined, true),
    ]
  } else if (p.cls === 'prop') {
    items = [item('picture', 'picture', !!(v.anim_ref_asset_id || v.hero_asset_id), v.anim_ref_asset_id || v.hero_asset_id ? undefined : '— in Make'),
      item('model', '3D model', !!v.model_asset_id), item('height', 'height', !!v.height_m, v.height_m ? `${v.height_m} m` : undefined)]
  } else {
    const ps = v.place_set, faces = ps?.faces ?? []
    const ok = faces.filter((f) => f.filled || !f.bad).length
    const pct = faces.length ? Math.round((100 * ok) / faces.length) : 0
    items = [item('set_picture', 'set picture', !!ps?.sources.length, ps?.sources.length ? undefined : '— in Make'), item('set', 'set built', faces.length > 0),
      item('faces', 'faces filled', faces.length > 0 && ok === faces.length, faces.length ? `${pct} %` : undefined)]
  }
  const owed = items.filter((x) => x.state === 'owed').length
  return { items, owed, line: owed ? `${owed} to go` : 'Ready for a scene' }
}

const REPEATS = ['a_pose', 'back', 'picture', 'set_picture']                 // the pictures the 3D reads: World's own items say them already
/** RS1 (D197, proto02 01 §4.2): the one readiness line of an entity version — its pictures (`readiness`), then its 3D (`clayReadiness`
 *  without the items that repeat a picture), counted together: "N to go", else "Ready for a scene". */
export function entityReadiness(p: Pick<Profile, 'cls' | 'voice_id'>, v: ProfileVersion, refs: number, prompts: Partial<Record<'hero' | 'a_pose_front', string | null>> = {}): Readiness {
  const items = [...readiness(p, v, refs, prompts).items, ...clayReadiness(p, v).items.filter((x) => !REPEATS.includes(x.id))]
  const owed = items.filter((x) => x.state === 'owed').length
  return { items, owed, line: owed ? `${owed} to go` : 'Ready for a scene' }
}
