// D93 (A2) "Add to Cast ▸" on every result (the Catalogue / Generate tile menu, the Inspector's one-asset view, the loupe's More, the Bin):
// the Cast's profiles — the one the image was made for first, under "made for", then characters, props and places — each with "as the
// hero", "into the reference set" and "as a candidate". The entries are the commands `cat.addTo.*` run on one profile (D90's per-item
// pattern: the entry sets the profile around the command's `when` and `run`); the server moves or copies (routes/story.py profile_add).
// proto01_UIcast CF5: named "Add to Cast" (props and places are in it too); a profile with several open versions offers each.
import { UserRoundPlus } from 'lucide-react'
import type { Asset, Profile } from '../../api/types'
import type { MenuItem, OnItem } from '../../frame/commands'
import { CLASS_LABEL } from './storyStore'

/** What the `cat.addTo.*` commands act on (set by the menu entry around `when` and `run`; cleared after): the profile, the version (else
 *  its current one) and the assets (else the Catalogue's selection — the Bin names its own tile). */
export const castTarget: { pid?: string; vid?: string; ids?: string[] } = {}
export const onProfile = (pid: string, vid?: string, ids?: string[]): OnItem => (f) => {
  Object.assign(castTarget, { pid, vid, ids })
  try { return f() } finally { castTarget.pid = undefined; castTarget.vid = undefined; castTarget.ids = undefined }
}

/** The profiles an asset was made for: its recipe's profile mentions — a subject-linked one first (D92 / D93). */
export function madeFor(a: Pick<Asset, 'params'> | undefined): string[] {
  const ms = ((a?.params?.recipe as { mentions?: { profile_id?: string | null; subject?: number | null }[] } | undefined)?.mentions ?? []).filter((m) => m.profile_id)
  return [...new Set([...ms.filter((m) => typeof m.subject === 'number'), ...ms.filter((m) => typeof m.subject !== 'number')].map((m) => m.profile_id!))]
}

/** Whose commands the entries run: the Catalogue's `cat.addTo.*` (its selection) or the Bin's `bin.addTo.*` (B2a, D159: the things named). */
export type AddVia = 'cat' | 'bin'

/** The three ways in, on one version. */
const ways = (pid: string, vid: string | undefined, ids?: string[], via: AddVia = 'cat'): MenuItem[] => {
  const on = onProfile(pid, vid, ids)
  if (via === 'bin') return [{ cmd: 'bin.addTo.hero', label: 'as the hero', on }, { cmd: 'bin.addTo.reference', label: 'into the reference set', on }, { cmd: 'bin.addTo.candidate', label: 'as a candidate', on }]
  return [{ cmd: 'cat.addTo.hero', label: 'as the hero', on }, { cmd: 'cat.addTo.reference', label: 'into the reference set', on }, { cmd: 'cat.addTo.candidate', label: 'as a candidate', on }]
}

/** What a profile's entry offers: the three ways into its open version — each open version its own entry when there are several — or why
 *  it takes nothing (every version final). */
function entries(p: Profile, ids?: string[], via: AddVia = 'cat'): MenuItem[] {
  const open = p.versions.filter((v) => v.state === 'open')
  if (!open.length) return [{ heading: 'every version is final — make a new version to add to it' } as MenuItem]
  if (open.length === 1) return ways(p.id, open[0].id, ids, via)
  return open.map((v) => ({ label: `${v.id}${v.id === p.current ? ' (current)' : ''}${v.label && v.label !== v.id ? ` · ${v.label}` : ''}`, items: ways(p.id, v.id, ids, via) }))
}

/** "Add to Cast ▸": made-for first (with its heading), then characters, props and places; an empty Cast says how to start one. */
export function addToCastItems(profiles: Profile[], made: string[], ids?: string[], via: AddVia = 'cat'): MenuItem[] {
  const first = made.map((id) => profiles.find((p) => p.id === id)).filter((p): p is Profile => !!p)
  const rest = (['character', 'prop', 'place'] as const).flatMap((cls) => profiles.filter((p) => p.cls === cls && !first.includes(p)))
  const sub = (p: Profile): MenuItem => { const open = p.versions.filter((v) => v.state === 'open'); return { label: open.length > 1 ? p.name : `${p.name} · ${open[0]?.id ?? p.current}`, items: entries(p, ids, via) } }
  if (!first.length && !rest.length) return [{ heading: via === 'bin' ? 'Nothing in World yet — "Make an entity from it" starts one' : 'Nothing in the Cast yet — "Make a character… / place… / prop…" starts one' }]
  return [
    ...(first.length ? [{ heading: 'made for' } as MenuItem, ...first.map(sub)] : []),
    ...(['character', 'prop', 'place'] as const).flatMap((cls) => { const ps = rest.filter((p) => p.cls === cls); return ps.length ? [{ heading: `${CLASS_LABEL[cls][0].toUpperCase()}${CLASS_LABEL[cls].slice(1)}s` } as MenuItem, ...ps.map(sub)] : [] }),
  ]
}

export const addToCastMenu = (profiles: Profile[], made: string[], ids?: string[], via: AddVia = 'cat'): Extract<MenuItem, { items: MenuItem[] }> =>
  ({ label: via === 'bin' ? 'Add to World' : 'Add to Cast', icon: UserRoundPlus, items: addToCastItems(profiles, made, ids, via) })
