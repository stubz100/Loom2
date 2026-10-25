// proto01_UIcast CW1: the Ideas board's menus and confirmations (kept apart from Ideas.tsx, a components-only file).
import { sep, type MenuItem } from '../../frame/commands'
import { askConfirm } from '../../store/session'
import { focusOf, useIdeas, type Idea } from './ideasStore'
import { CLASS_LABEL, useStory } from './storyStore'

const ideas = () => useIdeas.getState()

/** The right-click of an idea (its row, its bench's head): what the bench's verbs do, on the variant in focus. */
export function ideaMenu(i: Idea): MenuItem[] {
  const v = focusOf(i)
  const profiles = useStory.getState().profiles.filter((p) => p.cls === i.cls)
  return [
    { cmd: 'story.idea.explore' }, { cmd: 'story.idea.clay' }, sep,
    { cmd: 'story.idea.keep' },
    { label: 'Keep as a new version of', items: profiles.length && v ? profiles.map((p): MenuItem => ({ label: `${p.name} (now ${p.current})`, run: () => void ideas().keep(i.id, v.id, p.id) }))
      : [{ heading: `No ${CLASS_LABEL[i.cls]} in Cast yet — Keep ▶ makes one` } as MenuItem] },
    sep, { cmd: 'story.idea.rename' }, { cmd: 'story.idea.delete' }, sep, { cmd: 'story.idea.new' },
  ]
}

/** The delete's confirmation words. */
export const confirmDelete = (i: Idea) => askConfirm({ title: `Delete the idea "${i.name}"?`, text: `Its page "${i.name} · idea" and its ${i.variants.length} picture${i.variants.length === 1 ? '' : 's'} stay in the album; what was kept stays in Cast.`, okLabel: 'Delete', danger: true })
