// D90 (B2): the Story suite's keys — each tab's focusable stage dispatches its own commands only (by id prefix), so Delete on Cast
// never removes the World row still selected, P plays only on the Flow, Ctrl+Z undoes the Episode lane only on the Episode.
import { handleKeyFor, type Command } from '../../frame/commands'

export type StoryTab = 'world' | 'cast' | 'shots' | 'flow' | 'episode'
const PREFIX: Record<StoryTab, string> = { world: 'story.world.', cast: 'story.cast.', shots: 'story.shot.', flow: 'story.flow.', episode: 'story.episode.' }

/** The command belongs to the tab (its id carries the tab's prefix). */
export const ownedBy = (tab: StoryTab, c: Pick<Command, 'id'>): boolean => c.id.startsWith(PREFIX[tab])
/** The key is typed into a field (or a modal owns it), not meant for the tab's verbs — as useKeyboardMap's guard. */
export const typing = (t: EventTarget | null): boolean => !!(t as HTMLElement | null)?.closest?.('input, textarea, select, [contenteditable], .modal')

/** The tab's stage `onKeyDown`: the first enabled command of the tab whose key matches runs; true when one ran (the event is prevented). */
export function storyKey(tab: StoryTab, e: KeyboardEvent): boolean {
  if (typing(e.target)) return false
  return handleKeyFor('story', e, (c) => ownedBy(tab, c))
}
