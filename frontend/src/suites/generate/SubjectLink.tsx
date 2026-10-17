// D93 phase A: what a subject card linked to a Cast profile says about the link — its slots in the prompt (A3, "refs 1–3"), the casting
// button (A1, "Give <name> a look" / "More looks for <name>") and the warnings under the description (A9: only the name; A1: describe the
// look first). Presentational: the card (GenerateColumn.tsx) passes what the stores hold, so the test renders it without them.
import { Sparkles } from 'lucide-react'
import type { CastOffer } from './subjectCast'

export function SubjectSlots({ slots }: { slots: { label: string; left: number } | null }) {
  if (!slots) return null
  return <span className={`subject-slots${slots.left ? ' cut' : ''}`} title={slots.left ? `${slots.left} of its reference set did not fit the model's limit` : 'the reference images this subject is bound to in the prompt'}>
    {slots.label}{slots.left ? ` · ${slots.left} left out` : ''}</span>
}

export function CastButton({ offer, onCast }: { offer: CastOffer | null; onCast: () => void }) {
  if (!offer) return null
  return <button type="button" className={`subject-cast${offer.kind === 'give' ? ' primary' : ' quiet'}`} disabled={!!offer.disabled} title={offer.disabled ?? offer.hint}
    data-cast={offer.kind} onClick={onCast}><Sparkles size={12} /> {offer.label}</button>
}

/** The line under the description: the casting run's ask first, else the name-only warning. */
export function SubjectWarn({ name, nameOnly, ask, refs }: { name: string; nameOnly: boolean; ask: boolean; refs: number }) {
  if (ask) return <p className="subject-warn ask" role="status">describe {name}'s look first — the casting run renders these words</p>
  if (!nameOnly) return null
  return <p className="subject-warn" role="status">the model only sees the name{refs ? ' (and its reference images)' : ''} — describe the look</p>
}
