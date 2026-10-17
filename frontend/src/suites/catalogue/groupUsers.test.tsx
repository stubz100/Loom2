// D92 §4.2 (owed): "used by" on album groups — the words, the confirm text a delete / ungroup adds, the component's links.
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { GroupUser } from '../../api/types'
import { useSession } from '../../store/session'
import { useAlbum } from './albumStore'
import { confirmDeleteGroup, confirmUngroup, usedByText, usedByWarning, userLabel } from './groupUsers'
import { UsedBy } from './UsedBy'

const goToStory = vi.fn()
vi.mock('../../store/origin', () => ({ goToStory: (p: unknown) => goToStory(p) }))

const u = (kind: GroupUser['kind'], name: string, extra = '', group_id = 'grp_a', more: Partial<GroupUser> = {}): GroupUser =>
  ({ kind, id: `${kind}_1`, name, extra, version: kind.startsWith('profile') ? 'v1' : null, cls: kind.startsWith('profile') ? 'character' : null, group_id, ...more })
const B = { host: '127.0.0.1', port: 8766, token: 't' }
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let host: HTMLDivElement | null = null
let root: ReturnType<typeof createRoot> | null = null
const render = (el: React.ReactElement) => {
  if (!host) { host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host) }
  act(() => root!.render(el))
  return host
}
afterEach(() => { if (root) act(() => root!.unmount()); host?.remove(); host = null; root = null })
const click = (el: Element) => act(() => { (el as HTMLElement).click() })
const byText = (h: HTMLElement, t: string) => [...h.querySelectorAll('button')].find((b) => b.textContent === t)!

describe('the words', () => {
  it('names each kind of user', () => {
    expect([u('profile_ref', 'Mara', 'v1'), u('profile_candidates', 'Mara', 'rain gear'), u('style', 'Ink wash'), u('flow_board', 'Arrival', 'dialogue'), u('stage', 'Pier'), u('library', 'dusk', 'lighting')].map(userLabel))
      .toEqual(['Mara v1 · references', 'Mara rain gear · candidates', 'Style · Ink wash', 'Flow · Arrival · board', 'Stage · Pier', 'Library · dusk'])
    expect(usedByText([u('profile_ref', 'Mara', 'v1'), u('style', 'Ink wash')])).toBe('used by: Mara v1 · references; Style · Ink wash')
    expect(usedByText([])).toBe('')
  })
  it('the confirm says who loses the group, and the groups inside for a delete', () => {
    expect(usedByWarning([], 'delete', 'grp_a')).toBe('')
    expect(usedByWarning([u('profile_ref', 'Mara', 'v1')], 'ungroup', 'grp_a')).toBe('It is used by Mara v1 · references — they lose this group (its images stay on the page above).')
    expect(usedByWarning([u('style', 'Ink wash'), u('stage', 'Pier', '', 'grp_inner')], 'delete', 'grp_a'))
      .toBe('It is used by Style · Ink wash and inside it by Stage · Pier — they lose these images (the records stay; pick or make another group for them).')
    expect(usedByWarning([u('stage', 'Pier', '', 'grp_inner')], 'delete', 'grp_a')).toMatch(/^Groups inside it by Stage · Pier/)
  })
})

describe('the confirms and the line', () => {
  let asked: { title?: string; text?: string } | null
  let reply: Record<string, GroupUser[]>
  beforeEach(() => {
    asked = null
    reply = {}
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(input instanceof Request ? input.url : String(input))
      expect(url.pathname).toBe('/groups/used-by')
      return Response.json(reply)
    }))
    setBackend(B)
    useSession.setState({ backend: B, askConfirm: vi.fn(async (o) => { asked = o; return true }) as never })
  })

  it('delete asks deep and names the users; an unused ungroup does not ask', async () => {
    reply = { grp_a: [u('profile_ref', 'Mara', 'v1')] }
    expect(await confirmDeleteGroup({ id: 'grp_a', name: 'Mara refs', total: 3 })).toBe(true)
    expect(asked!.title).toBe('Delete "Mara refs"?')
    expect(asked!.text).toBe('Its 3 photos go back to Unprocessed; nothing is trashed. It is used by Mara v1 · references — they lose these images (the records stay; pick or make another group for them).')
    const call = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as Request
    expect(new URL(call.url).searchParams.get('deep')).toBe('true')
    asked = null
    reply = { grp_b: [] }
    expect(await confirmUngroup({ id: 'grp_b', name: 'Loose' })).toBe(true)
    expect(asked).toBeNull()
    reply = { grp_b: [u('flow_board', 'Arrival', 'dialogue', 'grp_b')] }
    await confirmUngroup({ id: 'grp_b', name: 'Board' })
    expect(asked!.text).toMatch(/^Its items land where its card was\. It is used by Flow · Arrival · board/)
  })

  it('the line links each user to where it lives', () => {
    useAlbum.setState({ usedBy: { grp_a: [u('profile_ref', 'Mara', 'v1', 'grp_a', { id: 'prf_1' }), u('style', 'Ink wash', '', 'grp_a', { id: 'sty_1' })] } })
    const h = render(<UsedBy gid="grp_a" />)
    expect(h.querySelector('[data-testid="used-by"]')!.textContent).toBe('Mara v1 · references; Style · Ink wash')            // under the Inspector's "Used by" heading
    click(byText(h, 'Mara v1 · references'))
    expect(goToStory).toHaveBeenLastCalledWith({ tab: 'cast', id: 'prf_1', version: 'v1' })
    click(byText(h, 'Style · Ink wash'))
    expect(goToStory).toHaveBeenLastCalledWith({ tab: 'world', id: 'sty_1' })
    act(() => root!.render(<UsedBy gid="grp_a" compact />))
    const line = h.querySelector<HTMLElement>('[data-testid="used-by"]')!
    expect(line.textContent).toBe('used by:Mara v1 · references+1')                                     // a header: the first and how many more …
    expect(line.title).toBe('used by: Mara v1 · references; Style · Ink wash')                          // … the tooltip names them all
  })
  it('says nothing uses it in the Inspector, and nothing in a header', () => {
    useAlbum.setState({ usedBy: {} })
    const h = render(<><UsedBy gid="grp_z" /><UsedBy gid="grp_z" compact /></>)
    expect(h.textContent).toBe('Nothing in Story or Stage uses this group.')
  })
})
