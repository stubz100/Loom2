// D93 (B4, B5): a Cast version's character sheet — the only place it is written. Appearance (the look), outfit (the default clothes),
// bound colours (a colour + what it colours: "#C0392B rain jacket", the way Generate's Tree prompt binds colours) and marks, and the
// version's label (a costume, an age, a look — shown on Generate's version chip). Every field shows at once and saves after a pause, one
// save at a time with the profile's revision (storyStore.setSheet, D90 B14); a final version's sheet is read-only, its label is not.
// The line under it is what a mention and every linked subject carry (the composition rule, sheet.ts), so the author sees it as sent.
// D93 (C6): a place or a prop has no outfit (the rule does not send one) — its appearance is its look, its colours and marks apply.
import { Plus, X } from 'lucide-react'
import type { Profile, ProfileVersion } from '../../api/types'
import { composeSheet } from '../generate/sheet'
import { useStory } from './storyStore'

const MAX_COLOURS = 12
/** W16: a prop's and a place's examples are their own, not a character's. */
const LABEL_EG: Record<string, string> = { character: 'rain gear, winter, aged 60 …', prop: 'new, battered, lit …', place: 'at dusk, in rain, after the fire …' }
const MARKS_EG: Record<string, string> = { character: 'a scar over the left eyebrow, round glasses', prop: 'a dent in the lid, initials scratched on the back', place: 'a broken window, a faded sign over the door' }
const NEW_COLOUR = ''                                                         // M1: no colour until the author picks one (it used to start red)

export function CastSheet({ p, v }: { p: Profile; v: ProfileVersion }) {
  const setSheet = useStory((s) => s.setSheet)
  const open = v.state === 'open'
  const colours = v.colours ?? []
  const setColour = (k: number, patch: Partial<ProfileVersion['colours'][number]>) => setSheet({ colours: colours.map((c, j) => (j === k ? { ...c, ...patch } : c)) })
  const worn = p.cls === 'character'                                       // D93 (C6): a place or a prop wears nothing
  const sent = composeSheet(v, null, '', p.cls)
  return (
    <div className="cast-sheet" role="group" aria-label={`${p.name}'s sheet`}>
      <label htmlFor="cast-label">version</label>
      <div className="sheet-label"><span className="mono">{v.id}</span>
        <input id="cast-label" type="text" value={v.label === v.id ? '' : v.label} maxLength={40} aria-label="version label" placeholder={`a label — ${LABEL_EG[p.cls] ?? LABEL_EG.character}`}
          title="Shown on Generate's version chip and in the version selector" onChange={(e) => setSheet({ label: e.target.value })} /></div>
      <label htmlFor="cast-appearance">appearance</label>
      <textarea id="cast-appearance" rows={3} value={v.appearance} readOnly={!open} aria-label="appearance" onChange={(e) => setSheet({ appearance: e.target.value })}
        placeholder={p.cls === 'place' ? `${p.name}'s look — e.g. a stone quay at dusk, fishing boats, wet cobbles` : p.cls === 'prop' ? `${p.name}'s look — e.g. a brass compass with a cracked glass`
          : `${p.name}'s look — face, hair, build: e.g. a wiry woman in her thirties, cropped black hair, olive skin`} />
      {worn && <><label htmlFor="cast-outfit">outfit</label>
        <input id="cast-outfit" type="text" value={v.outfit} readOnly={!open} aria-label="outfit" onChange={(e) => setSheet({ outfit: e.target.value })}
          placeholder="the default clothes — a shot may wear another (Generate's subject card)" /></>}
      <label>colours</label>
      <div className="sheet-colours" aria-label="bound colours">
        {colours.map((c, k) => (
          <span key={k} className={`sheet-colour${c.object.trim() && c.hex ? '' : ' unbound'}`}
            title={!c.hex ? 'pick its colour — not sent until it has one' : c.object.trim() ? `${c.hex.toUpperCase()} ${c.object.trim()}` : 'not sent until it names what it colours'}>
            <input type="color" className={c.hex ? undefined : 'unset'} value={/^#[0-9a-f]{6}$/i.test(c.hex) ? c.hex.toLowerCase() : '#888888'} disabled={!open} aria-label={`colour ${k + 1}`}
              title={c.hex ? undefined : 'pick its colour'} onChange={(e) => setColour(k, { hex: e.target.value.toUpperCase() })} />
            <input type="text" value={c.object} readOnly={!open} maxLength={80} aria-label={`colour ${k + 1}: what it colours`} placeholder="what it colours" onChange={(e) => setColour(k, { object: e.target.value })} />
            {open && <button type="button" className="quiet x" aria-label={`remove colour ${k + 1}`} title="Remove this colour" onClick={() => setSheet({ colours: colours.filter((_, j) => j !== k) })}><X size={11} /></button>}
          </span>
        ))}
        {open && colours.length < MAX_COLOURS && <button type="button" className="quiet" title={`Bind a colour to ${p.cls === 'character' ? 'something the character wears or carries' : p.cls === 'prop' ? 'a part of it' : 'a part of the place'} (a hex code before its object in the prompt)`}
          onClick={() => setSheet({ colours: [...colours, { hex: NEW_COLOUR, object: '' }] })}><Plus size={12} /> colour</button>}
      </div>
      <label htmlFor="cast-marks">marks</label>
      <input id="cast-marks" type="text" value={v.marks} readOnly={!open} aria-label="marks" onChange={(e) => setSheet({ marks: e.target.value })}
        placeholder={`distinguishing features — ${MARKS_EG[p.cls] ?? MARKS_EG.character}`} />
      <p className="sheet-sent" aria-label="as sent"><span>a @mention and every linked subject carry</span> {sent || <i>nothing yet — the model would see only the name</i>}</p>
    </div>
  )
}
