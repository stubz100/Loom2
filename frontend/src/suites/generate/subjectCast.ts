// D93 phase A (Cast ↔ subject made real): the pure rules behind a subject card linked to a Cast profile — whether it offers "Give <name> a
// look" or "More looks for <name>" (A1), the casting run's origin (results into the version's candidates), the slots the preview gave it
// (A3, "refs 1–3"), and the name-only warning (A9). Kept out of the component so the tests read them without a store.
import type { Binding, JobOrigin, Profile } from '../../api/types'
import { versionName, versionOf } from './sheet'

type CardWords = { description?: string; action?: string; pose?: string; position?: string; profile_id?: string; holds?: { profile_id: string } }
/** The subject cards the prompt keeps (cleanTree's rule): one with a description, an action, a pose or a position — D93 (B4): or a link
 *  (its words are the character's sheet, composed by the server); D93 (C6): or a prop it holds. */
export const keptSubject = (s: CardWords): boolean => !!s.profile_id || !!s.holds?.profile_id || !!(s.description || s.action || s.pose || s.position || '').trim()

/** D93 (A3): a card's index among the subjects the prompt sends (the server's `Mention.subject`), or -1 when the card is dropped. */
export function sentIndex(subjects: CardWords[], i: number): number {
  if (!subjects[i] || !keptSubject(subjects[i])) return -1
  return subjects.slice(0, i).filter(keptSubject).length
}

/** D93 (A9): the description is only the profile's name — the model sees a word, not a look. */
export const nameOnly = (description: string, name: string | undefined): boolean =>
  !!name?.trim() && description.trim().replace(/[.\s]+$/, '').toLowerCase() === name.trim().toLowerCase()

/** D93 (A1): a casting run needs words for the look. */
export const needsLook = (description: string, name: string | undefined): boolean => !description.trim() || nameOnly(description, name)

export interface CastOffer { kind: 'give' | 'more'; label: string; hint: string; disabled: string | null }
/** D93 (A1): what the linked card offers — "Give <name> a look" while the version has no hero and no references, "More looks for <name>"
 *  after; a final version cannot take candidates (a new version first). `refs`: the images its mention gives (the preview's). D93 (B5):
 *  the version the card uses (its chip), else the current one. */
export function castOffer(p: Profile | undefined, refs = 0, vid?: string | null): CastOffer | null {
  const v = versionOf(p, vid)
  if (!p || !v) return null
  const give = !v.hero_asset_id && refs === 0
  return {
    kind: give ? 'give' : 'more',
    label: give ? `Give ${p.name} a look` : `More looks for ${p.name}`,
    hint: `a casting run: the panel's images land as ${p.name} ${v.id}'s candidates in Story · Cast (keep ✓, reject ✕, make one the hero)`,
    disabled: v.state !== 'open' ? `${p.name} ${v.id} is final — make a new version to cast it again` : null,
  }
}

/** D93 (A1): the origin of a casting run — the finisher places the results on the version's candidates page (`group_id`), "Go to origin"
 *  opens the profile in Cast. */
export const castOrigin = (profileId: string, version: string, groupId: string): JobOrigin =>
  ({ suite: 'generate', surface: 'cast', ref: profileId, payload: { version, group_id: groupId, profile_id: profileId } })

/** D93 (A3): the card's slots as the preview gave them: "refs 1–3", "ref 2", "no refs"; `left` = the set's images that did not fit. D93 (C6):
 *  `role` held — the prop the card holds; scene — the place of the scene (`sent` ignored). */
export function slotsOf(bindings: Binding[] | undefined, sent: number, role: 'subject' | 'held' | 'scene' = 'subject'): { label: string; left: number; refs: number[] } | null {
  const b = role === 'scene' ? bindings?.find((x) => x.role === 'scene') : sent >= 0 ? bindings?.find((x) => x.subject === sent && (x.role ?? 'subject') === role) : undefined
  if (!b) return null
  const r = b.refs ?? []
  const run = r.length > 1 && r.every((n, k) => n === r[0] + k)
  const label = !r.length ? 'no refs' : r.length === 1 ? `ref ${r[0]}` : run ? `refs ${r[0]}–${r[r.length - 1]}` : `refs ${r.join(', ')}`
  return { label, left: b.skipped ?? 0, refs: r }
}

/** D93 (A3): the Preview's line per bound subject — what it got and what was left out (T8: said, never silent); D93 (B5): the version it
 *  uses when the profile has more than one ("Mara v2 · winter"). */
export function bindingLines(bindings: Binding[] | undefined, maxRefs: number | undefined, profiles: Profile[] = []): string[] {
  const ver = (b: Binding) => { const p = profiles.find((x) => x.id === b.profile_id); const v = p && p.versions.length > 1 ? versionOf(p, b.version) : undefined; return v ? ` ${versionName(v)}` : '' }
  const who = (b: Binding) => (b.role === 'scene' ? 'the scene' : b.role === 'held' ? `subject ${(b.subject ?? 0) + 1} holds` : `subject ${(b.subject ?? 0) + 1}`)   // D93 (C6)
  return (bindings ?? []).map((b) => `${who(b)} · ${b.name ?? 'a profile'}${ver(b)} → ${b.span ?? 'no reference images'}${b.skipped ? ` · ${b.skipped} of its set left out (the model takes ${maxRefs ?? '?'})` : ''}`)
}

/** D93 (B4): the Preview's line per linked subject — the description the server composed for it, exactly as sent in its subject. D93 (C6):
 *  and the scene a place composed, the clause of a held prop. */
export function composedLines(mentions: { subject?: number | null; name?: string | null; composed?: string | null; scene?: boolean | null; held_by?: number | null }[] | undefined): string[] {
  return (mentions ?? []).filter((m) => m.composed && (typeof m.subject === 'number' || typeof m.held_by === 'number' || m.scene))
    .map((m) => typeof m.subject === 'number' ? `subject ${m.subject + 1} · ${m.name ?? 'a profile'}: ${m.composed}`
      : typeof m.held_by === 'number' ? `subject ${m.held_by + 1} holds · ${m.name ?? 'a prop'}: holding ${m.composed}` : `the scene · ${m.name ?? 'a place'}: ${m.composed}`)
}
