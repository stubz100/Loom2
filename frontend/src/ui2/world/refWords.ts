// RG1 (D187 Q4, D188): a hand or feet picture's words — its own (the version's `hand_words` / `feet_words`), else the sheet's clauses about
// the hand (skin, nails, claws, rings, gloves) or the feet (the shoes, the hems, bare feet). The server's rule (orchestrator hands.sheet_words),
// held to the same cases (orchestrator/tests/fixtures/ref_words.json). E62 a: never the character's references or its whole sheet — those
// drew the whole person.
import type { ProfileVersion } from '../../api/types'

export type Part = 'hand' | 'feet'

const HAND_WORDS = /\b(hands?|fingers?|fingernails?|nails?|claws?|clawed|talons?|knuckles?|palms?|thumbs?|rings?|gloves?|gloved|mittens?|wrists?|bracelets?|skin|scales|scaly|fur|furred)\b/i
const FEET_WORDS = /\b(shoes?|boots?|booted|heels?|heeled|stilettos?|sandals?|sneakers?|trainers?|clogs?|slippers?|loafers?|brogues?|pumps?|barefoot|bare|feet|foot|toes?|socks?|stockings?|tights|trousers|jeans|skirts?|dress|robes?|gowns?|hems?|leggings|breeches|hooves|hoofed|paws?|skin|scales|scaly|fur|furred)\b/i

function clauses(...texts: string[]): string[] {
  return texts.flatMap((t) => (t ?? '').split(/[,;.]|\bwith\b|\band\b(?=\s+(?:a|an|the|wearing|with)\b)/).map((c) => c.trim().replace(/^[,;\s]+|[,;\s]+$/g, '').trim()).filter(Boolean))
}

/** The sheet's clauses about the hand or the feet, once each (case aside), in the sheet's order — led by what the character is when the
 *  sheet starts by saying so ("A gaunt grey ghoul": the rig drew a human hand with black nails without it), not by a name. */
export function sheetWords(appearance: string, outfit: string, marks: string, part: Part): string {
  const rx = part === 'hand' ? HAND_WORDS : FEET_WORDS
  const first = clauses(appearance)[0] ?? ''
  const seen: string[] = /^(a|an|the)\b/i.test(first) ? [first] : []
  for (const c of clauses(appearance, outfit, marks)) if (rx.test(c) && !seen.some((s) => s.toLowerCase() === c.toLowerCase())) seen.push(c)
  return seen.join(', ')
}

/** The words a version's hand or feet picture is made with: its own, else the sheet's. */
export function partWords(v: Pick<ProfileVersion, 'appearance' | 'outfit' | 'marks'> & { hand_words?: string; feet_words?: string }, part: Part): string {
  const own = (part === 'hand' ? v.hand_words : v.feet_words)?.trim() ?? ''
  return own || sheetWords(v.appearance, v.outfit, v.marks, part)
}

/** E62's measured shape (hands.part_prompt): the framing's sentence, then the words after a colon. */
export function partPrompt(sentence: string, words: string): string {
  const s = sentence.trim().replace(/[.\s]+$/, ''), w = words.trim().replace(/^[,;.\s]+|[,;.\s]+$/g, '')
  return `${s}${w ? `: ${w}` : ''}.`
}
