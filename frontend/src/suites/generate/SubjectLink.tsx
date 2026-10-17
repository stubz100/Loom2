// D93 phase A: what a subject card linked to a Cast profile says about the link — its slots in the prompt (A3, "refs 1–3"), the casting
// button (A1, "Give <name> a look" / "More looks for <name>") and the warnings under the sheet (A9: only the name; A1: describe the look
// first). D93 phase B: the character's sheet, read-only (B4 — written in Story · Cast, followed live), and the version chip (B5).
// Presentational: the card (GenerateColumn.tsx) passes what the stores hold, so the test renders it without them.
import { PenLine, Sparkles } from 'lucide-react'
import type { ProfileVersion } from '../../api/types'
import type { CastOffer } from './subjectCast'
import { sentColours, sheetEmpty, versionName } from './sheet'

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

/** The line under the sheet: the casting run's ask first, else the name-only warning. D93 (B4): the look is written in Cast. */
export function SubjectWarn({ name, nameOnly, ask, refs }: { name: string; nameOnly: boolean; ask: boolean; refs: number }) {
  if (ask) return <p className="subject-warn ask" role="status">describe {name}'s look in Story · Cast first — the casting run renders the sheet</p>
  if (!nameOnly) return null
  return <p className="subject-warn" role="status">the model only sees the name{refs ? ' (and its reference images)' : ''} — describe the look in Cast</p>
}

/** D93 (B5): the version chip — which version (costume, age, look) of the character the subject uses; a press opens the versions. */
export function VersionChip({ v, pinned, onOpen }: { v: Pick<ProfileVersion, 'id' | 'label'>; pinned: boolean; onOpen: (e: React.PointerEvent<HTMLButtonElement>) => void }) {
  return <button type="button" className={`version-chip${pinned ? ' pinned' : ''}`} aria-haspopup="menu" aria-label={`version ${versionName(v)}`} onPointerDown={onOpen}
    title={pinned ? `this subject uses ${versionName(v)} — its sheet, references and LoRA` : `the current version (${versionName(v)}) — pick another for a costume, an age, a look`}>
    {versionName(v)} <span className="caret">▾</span></button>
}

/** D93 (B4): the character's sheet as Cast holds it, read-only — the appearance, the outfit (struck through when this shot wears another),
 *  the bound colours (a colour without an object is not sent, so not shown), the marks; Edit opens it in Story · Cast. */
export function SheetView({ i, v, name, outfitOverridden, onEdit, cls = 'character', domId }: { i: number; v: ProfileVersion | undefined; name: string; outfitOverridden: boolean; onEdit: () => void; cls?: string; domId?: string }) {
  const colours = (v?.colours ?? []).filter((c) => c.object.trim())
  return (
    <div className="subject-sheet" id={domId ?? `gen-subject-sheet-${i}`} tabIndex={-1} aria-label={`${name}'s sheet`}>
      <div className="sheet-head"><span>{name}'s sheet{v ? ` · ${versionName(v)}` : ''} — from Story · Cast</span>
        <button type="button" className="quiet" title={`Edit ${name}'s sheet in Story · Cast — every linked subject follows`} onClick={onEdit}><PenLine size={12} /> edit in Cast</button></div>
      {!v || sheetEmpty(v, cls) ? <p className="sheet-empty">no look yet — the sheet in Cast is empty</p> : <>
        {v.appearance.trim() && <p className="sheet-look">{v.appearance}</p>}
        {cls === 'character' && v.outfit.trim() && <p className={`sheet-row${outfitOverridden ? ' over' : ''}`}><span className="k">outfit</span> <span className="v">{v.outfit}</span></p>}
        {colours.length > 0 && <p className="sheet-row"><span className="k">colours</span> {colours.map((c, k) => <span key={k} className="colour-chip" title={sentColours({ colours: [c] })[0]}><i style={{ background: c.hex }} />{c.object}</span>)}</p>}
        {v.marks.trim() && <p className="sheet-row"><span className="k">marks</span> <span className="v">{v.marks}</span></p>}
      </>}
    </div>
  )
}
