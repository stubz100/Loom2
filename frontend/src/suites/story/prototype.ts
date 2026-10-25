// proto01_UIcast CW1 (02 §5, 06 §2.1; D136 U2, U3): *Prototype ▸* on every picture — the tile's hover button and right-click (first),
// the loupe, the Bin, the Inspector. A new character, prop or place idea with the picture copied as its first variant (its page keeps
// it; the idea named from its prompt), or the picture added to an idea — made-for ideas first (the picture's job named it, CW2), then
// the newest. The work in Image or the Catalogue is not interrupted: a toast offers *Open*.
import { FlaskConical } from 'lucide-react'
import type { Asset } from '../../api/types'
import type { MenuItem } from '../../frame/commands'
import { goToIdea } from '../../store/origin'
import { useSession } from '../../store/session'
import { useIdeas } from './ideasStore'

type Cls = 'character' | 'prop' | 'place'
const RECENT = 8

/** The idea a picture was made for (its job's origin, CW2). */
export const madeForIdea = (a: Pick<Asset, 'origin'> | undefined): string | null => {
  const v = (a?.origin?.payload as Record<string, unknown> | null | undefined)?.for_idea
  return typeof v === 'string' ? v : null
}

/** A new idea from the pictures: the first starts it (named from its prompt), the rest join as variants. */
export async function newIdeaFrom(cls: Cls, ids: string[]): Promise<void> {
  const st = useIdeas.getState()
  const idea = await st.create(cls, ids[0] ?? null)
  if (!idea) return
  let last = idea
  for (const id of ids.slice(1)) last = (await useIdeas.getState().addVariant(idea.id, id)) ?? last
  useSession.getState().toast(`New ${cls} idea “${idea.name}” with ${last.variants.length} variant${last.variants.length === 1 ? '' : 's'} on Cast's Ideas board`, 'success', { label: 'Open', run: () => goToIdea(idea.id) })
}

/** The pictures added to an idea, each a variant. */
export async function addToIdea(iid: string, ids: string[]): Promise<void> {
  let name = ''
  for (const id of ids) name = (await useIdeas.getState().addVariant(iid, id))?.name ?? name
  if (name) useSession.getState().toast(`Added to “${name}”`, 'success', { label: 'Open', run: () => goToIdea(iid) })
}

export function prototypeItems(ids: string[], made: string | null = null): MenuItem[] {
  const st = useIdeas.getState()
  if (!st.loaded) void st.load()                                          // the first menu loads them; the list is there the next time
  const first = made ? st.ideas.filter((i) => i.id === made) : []
  const rest = st.ideas.filter((i) => i.id !== made).slice(0, RECENT)
  const entry = (i: (typeof st.ideas)[number]): MenuItem => ({ label: `${i.name} · ${i.cls}`, run: () => void addToIdea(i.id, ids) })
  const plural = ids.length > 1 ? ' (the first starts it, the rest are variants)' : ''
  return [
    ...(['character', 'prop', 'place'] as const).map((cls): MenuItem => ({ label: `New ${cls} idea${plural}`, run: () => void newIdeaFrom(cls, ids) })),
    { label: 'Add to an idea', items: [
      ...(first.length ? [{ heading: 'made for' } as MenuItem, ...first.map(entry)] : []),
      ...(rest.length ? [{ heading: 'the newest' } as MenuItem, ...rest.map(entry)] : []),
      ...(!first.length && !rest.length ? [{ heading: st.loaded ? 'No ideas yet — New … idea starts one' : 'loading the ideas…' } as MenuItem] : []),
    ] },
  ]
}

export const prototypeMenu = (ids: string[], made: string | null = null): Extract<MenuItem, { items: MenuItem[] }> => ({ label: 'Prototype', icon: FlaskConical, items: prototypeItems(ids, made) })
