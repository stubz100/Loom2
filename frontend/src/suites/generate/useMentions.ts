// D73 (ArtCraft P12): @mentions in Generate's prompt fields — the @ button (mouse) or typing @ opens the album's groups; the pick goes in
// at the caret as "@name" and the panel remembers the group, which the server turns into references.
import { AtSign } from 'lucide-react'
import { createElement, useEffect, type KeyboardEvent } from 'react'
import { MenuButton } from '../../frame/CommandButton'
import type { MenuItem } from '../../frame/commands'
import { openPressMenu } from '../../frame/ContextMenu'
import { flatGroups, useAlbum } from '../../store/album'
import { profilesForMentions } from '../story/storyStore'
import { useGenerate, type MentionRef } from './generateStore'

/** The album's groups as menu entries; picking one mentions it. */
export function groupItems(pick: (m: MentionRef) => void): MenuItem[] {
  const al = useAlbum.getState()
  if (!al.tree) { void al.load(); return [{ label: 'Loading the album… open the menu again', run: () => undefined, disabled: true }] }
  const groups = flatGroups(al.tree)
  const profiles = profilesForMentions()                                   // D85: the Story's cast first — a profile's current version's reference set
  const cast: MenuItem[] = profiles.length ? [{ heading: 'Mention a character, place or prop — its reference set becomes references' },
    ...profiles.map((p) => { const v = p.versions.find((x) => x.id === p.current); return { label: `${p.name} · ${p.cls} · ${p.current}`, run: () => pick({ group_id: v?.group_id ?? '', name: p.name, profile_id: p.id }) } })] : []
  if (!groups.length && !cast.length) return [{ label: 'No groups yet — make one on the Album page', run: () => undefined, disabled: true }]
  return [...cast, { heading: 'Mention a group — its images become references' },
    ...groups.map(({ node, depth }) => ({ label: `${'  '.repeat(depth)}${node.name}`, run: () => pick({ group_id: node.id, name: node.name }) }))]
}

/** A prompt field that takes @mentions: typing @ opens the group menu at the field and the pick goes in at the caret; the @ button (the
 *  mouse way) adds "@name" at the end of the field. */
export function useMentions(value: string, onChange: (v: string) => void) {
  const addMention = useGenerate((g) => g.addMention)
  useEffect(() => { if (!useAlbum.getState().tree) void useAlbum.getState().load() }, [])   // the groups, before the first @ (the Catalogue may not have loaded them)
  const insertAt = (at: number, typed: boolean, field?: HTMLTextAreaElement) => (m: MentionRef) => {
    addMention(m)
    const before = value.slice(0, at), lead = typed || !before || /\s$/.test(before) ? '' : ' '
    const head = `${before}${lead}${typed ? '' : '@'}${m.name} `
    onChange(head + value.slice(at).replace(/^ /, ''))
    if (field) requestAnimationFrame(() => { field.focus(); field.setSelectionRange(head.length, head.length) })   // typing goes on after the name
  }
  const onKeyUp = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key !== '@') return
    const field = e.currentTarget, at = field.selectionStart
    const open = () => openPressMenu({ button: 0, currentTarget: field, preventDefault: () => undefined }, () => groupItems(insertAt(at, true, field)), true)
    if (useAlbum.getState().tree) open()
    else void useAlbum.getState().load().then(open)                     // typed before the album arrived: open the menu once it has (CI, 2026-10-11)
  }
  const button = createElement(MenuButton, { label: 'Mention a group (@)', icon: AtSign, items: () => groupItems(insertAt(value.length, false)) })
  return { onKeyUp, button }
}
