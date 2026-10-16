// D90 (01 §11.1 B1, B8): suite key handlers ignore keys typed into fields — a letter or Delete belongs to the text, not to a tool — but a
// suite's primary action (Ctrl+Enter, Ctrl+Shift+Enter) still answers from its prompt box, where the button's tooltip promises it.
import { command, isEnabled, matchesCommand } from './commands'

/** True when the event comes from a text field, a select or an editable element (a modal owns its keys too). */
export function inField(e: KeyboardEvent): boolean {
  return !!(e.target as HTMLElement | null)?.closest?.('input, textarea, select, [contenteditable], .modal')
}

/** In a field (not a modal), run the first of `ids` whose key matches and that is enabled; true when one ran. */
export function primaryInField(e: KeyboardEvent, ids: string[]): boolean {
  if ((e.target as HTMLElement | null)?.closest?.('.modal')) return false
  for (const id of ids) {
    const c = command(id)
    if (!c || !matchesCommand(e, c) || !isEnabled(c)) continue
    e.preventDefault(); c.run()
    return true
  }
  return false
}
