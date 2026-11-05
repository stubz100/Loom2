// RG4 (D187 R6): the Humanoid switch — shared by the Library's body section (CastBody) and the skeleton bench's parts; no stage code here.
import type { Body } from './body'

/** RG4 (D187 R6): a human or a humanoid — a humanoid's parts range wider (arms to ×1.8, legs from ×0.4, the head to ×3), its fit may go there,
 *  and nothing warns of an adult's range. */
export function HumanoidSwitch({ b, open, set }: { b: Body; open: boolean; set: (patch: Partial<Body>) => void }) {
  return (
    <span className="segmented" role="group" aria-label="human or humanoid" data-testid="humanoid">
      <button type="button" disabled={!open} className={!b.humanoid ? 'active' : ''} aria-pressed={!b.humanoid} onClick={() => set({ humanoid: false })} title="A human: an adult's ranges, a part outside one turns amber">human</button>
      <button type="button" disabled={!open} className={b.humanoid ? 'active' : ''} aria-pressed={!!b.humanoid} onClick={() => set({ humanoid: true })}
        title="A humanoid, not a human (a ghoul, a dwarf, a troll): the parts range wider — arms to ×1.8, legs from ×0.4, the head to ×3 — the fit may go there, and nothing warns of an adult's range">humanoid</button>
    </span>
  )
}
