// D92 §4.2 (owed until 2026-10-17): "used by" on album groups — a group can be a Cast version's reference set or candidates, a style's
// samples, a Flow node's board, a Stage's album page or a World library entry's pictures. The server computes it from those records
// (`GET /groups/used-by`, nothing stored); the group card's Inspector and the page's header show it with links that open the user,
// and deleting or ungrouping a used group says so in its confirm.
import { http, unwrap } from '../../api/client'
import type { GroupUser } from '../../api/types'
import { askConfirm, useSession } from '../../store/session'
import { goToStory } from '../../store/origin'

/** One user in words: "Mara v1 · references", "Style · Ink wash", "Flow · Arrival · board", "Stage · Pier", "Library · dusk". */
export function userLabel(u: GroupUser): string {
  switch (u.kind) {
    case 'profile_ref': return `${u.name} ${u.extra} · references`
    case 'profile_candidates': return `${u.name} ${u.extra} · candidates`
    case 'style': return `Style · ${u.name}`
    case 'flow_board': return `Flow · ${u.name} · board`
    case 'stage': return `Stage · ${u.name}`
    case 'library': return `Library · ${u.name}`
  }
}

/** Where a link goes, for its tooltip. */
export function userPlace(u: GroupUser): string {
  return u.kind === 'profile_ref' || u.kind === 'profile_candidates' ? 'Story · Cast' : u.kind === 'style' ? 'Story · World › Styles'
    : u.kind === 'library' ? 'Story · World › Library' : u.kind === 'flow_board' ? 'Story · Flow' : 'Stage'
}

/** "used by: Mara v1 · references; Style · Ink wash" (empty when nothing uses the group). */
export function usedByText(users: GroupUser[] | undefined): string {
  return users?.length ? `used by: ${users.map(userLabel).join('; ')}` : ''
}

/** The sentence a delete / ungroup confirm adds: who loses the group (a delete also takes the groups inside with it). */
export function usedByWarning(users: GroupUser[], action: 'delete' | 'ungroup', gid: string): string {
  if (!users.length) return ''
  const own = users.filter((u) => u.group_id === gid), inner = users.filter((u) => u.group_id !== gid)
  const parts = [own.length ? `It is used by ${own.map(userLabel).join('; ')}` : '', inner.length ? `${own.length ? 'and' : 'Groups'} inside it by ${inner.map(userLabel).join('; ')}` : ''].filter(Boolean)
  const lose = action === 'delete' ? 'they lose these images (the records stay; pick or make another group for them)' : 'they lose this group (its images stay on the page above)'
  return `${parts.join(' ')} — ${lose}.`
}

/** Open the user where it lives: Cast at the version, World at the style or the library, Flow at the node, the Stage. */
export function openUser(u: GroupUser): void {
  if (u.kind === 'profile_ref' || u.kind === 'profile_candidates') return goToStory({ tab: 'cast', id: u.id, version: u.version })
  if (u.kind === 'style') return goToStory({ tab: 'world', id: u.id })
  if (u.kind === 'flow_board') return goToStory({ tab: 'flow', id: u.id })
  if (u.kind === 'library') {
    goToStory({ tab: 'world', id: u.id })
    void import('../story/storyStore').then((m) => setTimeout(() => { m.useStory.getState().setSection('library'); m.useStory.setState({ selected: null }) }))
    return
  }
  useSession.getState().setSuite('stage')
  void import('../stage/stageStore').then((m) => { const st = m.useStage.getState(); if (st.current?.id !== u.id) void st.open(u.id) })
}

/** The users of some groups, fresh from the server (`deep`: with the groups inside — what a delete takes). */
export async function fetchUsers(ids: string[], deep = false): Promise<Record<string, GroupUser[]>> {
  try { return await unwrap(http.GET('/groups/used-by', { params: { query: { ids, deep } } })) } catch { return {} }
}

/** Delete with a confirm that names the users of the group and the groups inside it. */
export async function confirmDeleteGroup(g: { id: string; name: string; total: number }, more = ''): Promise<boolean> {
  const users = (await fetchUsers([g.id], true))[g.id] ?? []
  return askConfirm({ title: `Delete "${g.name}"?`, text: [`Its ${g.total} photo${g.total === 1 ? '' : 's'} go back to Unprocessed; nothing is trashed.${more ? ` ${more}` : ''}`, usedByWarning(users, 'delete', g.id)].filter(Boolean).join(' '),
    okLabel: 'Delete group', danger: true })
}

/** Ungroup asks only when something uses the group (an unused one dissolves at once, as before). */
export async function confirmUngroup(g: { id: string; name: string }): Promise<boolean> {
  const users = (await fetchUsers([g.id]))[g.id] ?? []
  if (!users.length) return true
  return askConfirm({ title: `Ungroup "${g.name}"?`, text: `Its items land where its card was. ${usedByWarning(users, 'ungroup', g.id)}`, okLabel: 'Ungroup', danger: true })
}
