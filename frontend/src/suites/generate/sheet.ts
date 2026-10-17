// D93 phase B (B4, B5): a Cast character's sheet as Generate reads it — the composition rule (the server's story.compose_sheet, held to the
// same cases: orchestrator/tests/fixtures/sheet_compose.json), the version a linked subject uses (its chip — a costume, an age, a look), the
// words the chip and Cast's selector show, and what becomes of an old panel's copied description. Pure: the tests read it without a store.
import type { Profile, ProfileVersion } from '../../api/types'
import { sep, type MenuItem } from '../../frame/commands'

export type Sheet = Pick<ProfileVersion, 'appearance' | 'outfit' | 'colours' | 'marks'>
export interface ShotWords { outfit?: string; note?: string }
export const SHEET_KEYS = ['appearance', 'outfit', 'colours', 'marks'] as const

const clause = (s: string | null | undefined) => (s ?? '').trim().replace(/^[,;\s]+|[,;\s]+$/g, '').replace(/\.+$/, '').trim()
const WORN = /^(wearing|in|dressed|clad)\b/i

/** The colours that go into the prompt: those bound to an object ("#C0392B rain jacket"); a colour alone stays on the sheet. */
export const sentColours = (v: Partial<Sheet>): string[] => (v.colours ?? []).filter((c) => clause(c.object)).map((c) => `${c.hex.toUpperCase()} ${clause(c.object)}`)

/** D93 (B4) the composition rule: appearance, the outfit (this shot's, else the sheet's — "wearing …" unless it says how), the bound
 *  colours, the marks, this shot's line — joined by ", "; empty → the name. D93 (C6): a place or a prop wears nothing (no outfit sent). */
export function composeSheet(v: Partial<Sheet> | undefined, shot?: ShotWords | null, name = '', cls: string = 'character'): string {
  const outfit = cls === 'character' ? clause(shot?.outfit) || clause(v?.outfit) : ''
  const parts = [clause(v?.appearance), outfit && !WORN.test(outfit) ? `wearing ${outfit}` : outfit, sentColours(v ?? {}).join(', '), clause(v?.marks), clause(shot?.note)]
  return parts.filter(Boolean).join(', ') || name.trim()
}

/** The sheet says nothing of the look (the casting run needs words, A1). */
export const sheetEmpty = (v: Partial<Sheet> | undefined, cls = 'character'): boolean => !composeSheet(v, null, '', cls)

/** D93 (B5): the version a linked subject uses — the one its chip picked, else the profile's current one. */
export const versionOf = (p: Profile | undefined, vid?: string | null): ProfileVersion | undefined =>
  p?.versions.find((x) => x.id === (vid && p.versions.some((y) => y.id === vid) ? vid : p.current))

/** "v1 · rain gear", or "v1" while the label is the id (the chip, Cast's version selector). */
export const versionName = (v: Pick<ProfileVersion, 'id' | 'label'>): string => (v.label && v.label.trim() && v.label.trim() !== v.id ? `${v.id} · ${v.label.trim()}` : v.id)

/** A linked card's leftover description (a panel saved before B4 copied the stub into it): the words beyond the sheet's appearance go to
 *  "this shot"; a plain copy (the appearance, the composed sheet or the name) is dropped. Null when there is nothing to adopt. */
export function adoptDescription(description: string | undefined, v: ProfileVersion | undefined, name: string, note = ''): { note: string } | null {
  const d = (description ?? '').trim()
  if (!d || !v) return null
  const low = (s: string) => clause(s).toLowerCase()
  const known = [v.appearance, composeSheet(v), name].map(low).filter(Boolean)
  if (known.includes(low(d))) return { note }
  const a = clause(v.appearance)
  const rest = a && d.toLowerCase().startsWith(a.toLowerCase()) ? clause(d.slice(a.length)) : clause(d)
  return { note: [clause(note), rest].filter(Boolean).join(', ') }
}

/** D93 (B5) the version chip's menu: each version by its name ("v2 · winter", the current one and a final one said), the one in use
 *  checked; picking the current one follows it from then on. `more`: the entries after (Edit the sheet in Cast). */
export function versionItems(p: Profile, chosen: string | undefined, pick: (vid: string | undefined) => void, more: MenuItem[] = []): MenuItem[] {
  const using = versionOf(p, chosen)?.id
  return [
    { heading: `${p.name}'s versions — costumes, ages, looks` },
    ...p.versions.map((v): MenuItem => ({ label: `${versionName(v)}${v.id === p.current ? ' · current' : ''}${v.state === 'final' ? ' · final' : ''}`, checked: v.id === using,
      run: () => pick(v.id === p.current ? undefined : v.id) })),
    ...(more.length ? [sep, ...more] : []),
  ]
}
