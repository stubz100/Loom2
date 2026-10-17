// D93 (A2) "Add to character ▸" on every result (the Catalogue / Generate tile menu, the Inspector's one-asset view, the loupe's More):
// the Cast's profiles — the one the image was made for first, under "made for", then characters, props and places — each with "as the
// hero", "into the reference set" and "as a candidate". The entries are the commands `cat.addTo.*` run on one profile (D90's per-item
// pattern: the entry sets the profile around the command's `when` and `run`); the server moves or copies (routes/story.py profile_add).
import { UserRoundPlus } from 'lucide-react'
import type { Asset, Profile } from '../../api/types'
import type { MenuItem, OnItem } from '../../frame/commands'
import { CLASS_LABEL } from './storyStore'

/** The profile the `cat.addTo.*` commands act on (set by the menu entry around `when` and `run`; cleared after). */
export const castTarget: { pid?: string } = {}
export const onProfile = (pid: string): OnItem => (f) => { castTarget.pid = pid; try { return f() } finally { castTarget.pid = undefined } }

/** The profiles an asset was made for: its recipe's profile mentions — a subject-linked one first (D92 / D93). */
export function madeFor(a: Pick<Asset, 'params'> | undefined): string[] {
  const ms = ((a?.params?.recipe as { mentions?: { profile_id?: string | null; subject?: number | null }[] } | undefined)?.mentions ?? []).filter((m) => m.profile_id)
  return [...new Set([...ms.filter((m) => typeof m.subject === 'number'), ...ms.filter((m) => typeof m.subject !== 'number')].map((m) => m.profile_id!))]
}

/** What a profile's entry offers: the three ways in, or the reason its current version takes nothing (final). */
function entries(p: Profile): MenuItem[] {
  const v = p.versions.find((x) => x.id === p.current)
  const on = onProfile(p.id)
  return [
    ...(v?.state === 'final' ? [{ heading: `${v.id} is final — make a new version to add to it` } as MenuItem] : []),
    { cmd: 'cat.addTo.hero', label: 'as the hero', on }, { cmd: 'cat.addTo.reference', label: 'into the reference set', on }, { cmd: 'cat.addTo.candidate', label: 'as a candidate', on },
  ]
}

/** "Add to character ▸": made-for first (with its heading), then characters, props and places; an empty Cast says how to start one. */
export function addToCastItems(profiles: Profile[], made: string[]): MenuItem[] {
  const first = made.map((id) => profiles.find((p) => p.id === id)).filter((p): p is Profile => !!p)
  const rest = (['character', 'prop', 'place'] as const).flatMap((cls) => profiles.filter((p) => p.cls === cls && !first.includes(p)))
  const sub = (p: Profile): MenuItem => ({ label: `${p.name} · ${p.current}`, items: entries(p) })
  if (!first.length && !rest.length) return [{ heading: 'No characters yet — "Make a character…" starts one' }]
  return [
    ...(first.length ? [{ heading: 'made for' } as MenuItem, ...first.map(sub)] : []),
    ...(['character', 'prop', 'place'] as const).flatMap((cls) => { const ps = rest.filter((p) => p.cls === cls); return ps.length ? [{ heading: `${CLASS_LABEL[cls][0].toUpperCase()}${CLASS_LABEL[cls].slice(1)}s` } as MenuItem, ...ps.map(sub)] : [] }),
  ]
}

export const addToCastMenu = (profiles: Profile[], made: string[]): Extract<MenuItem, { items: MenuItem[] }> => ({ label: 'Add to character', icon: UserRoundPlus, items: addToCastItems(profiles, made) })
