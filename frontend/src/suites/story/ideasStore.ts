// proto01_UIcast CW1–CW2 (D136 U1–U4; 06 §2.1–2.2): Cast's ideas — their own store on the server (`story/ideas/`), here the board's
// state: the ideas, the one open on the bench, the board shown (Cast's kept profiles or the Ideas), and the verbs — make one (from a
// picture: *Prototype ▸*, copied), add or drop a variant, *Make the clay ▶*, *Keep ▶*, rename, delete. `story.changed {kind: 'idea'}`
// on the socket reloads the one that moved (its clay's steps land while the bench is open).
import { create } from 'zustand'
import { ApiError, http, unwrap } from '../../api/client'
import type { Idea, Profile } from '../../api/types'
import { useSession } from '../../store/session'

export type { Idea }
type ProfileClass = Profile['cls']
export type IdeaVariant = Idea['variants'][number]
export type Board = 'cast' | 'ideas'

interface IdeasState {
  ideas: Idea[]
  loaded: boolean
  ideaId: string | null
  board: Board
  setBoard: (b: Board) => void
  load: () => Promise<void>
  select: (id: string | null) => void
  idea: () => Idea | undefined
  /** A new idea of a class — from a picture (copied; named from its prompt unless a name is given), or empty. */
  create: (cls: ProfileClass, assetId?: string | null, name?: string | null) => Promise<Idea | null>
  patch: (id: string, body: { name?: string; note?: string; cls?: ProfileClass; focus?: string | null; variants?: { id: string; note: string }[] }) => Promise<void>
  addVariant: (id: string, assetId: string) => Promise<Idea | null>
  removeVariant: (id: string, vid: string) => Promise<void>
  makeClay: (id: string, vid: string) => Promise<void>
  /** *Keep ▶*: a new Cast profile (`profileId` null) or a new version of one; Cast then opens on it. */
  keep: (id: string, vid: string, profileId?: string | null, name?: string | null) => Promise<Profile | null>
  remove: (id: string) => Promise<void>
  onChanged: (data: { id?: string; deleted?: boolean } | null) => void
}

const toast = (text: string, kind: 'error' | 'info' | 'success' = 'error') => useSession.getState().toast(text, kind)
const detail = (e: unknown) => (e as ApiError).detail ?? String(e)

export const useIdeas = create<IdeasState>()((set, get) => {
  const put = (i: Idea) => set({ ideas: [i, ...get().ideas.filter((x) => x.id !== i.id)] })
  return {
    ideas: [], loaded: false, ideaId: null, board: 'cast',
    setBoard: (board) => { set({ board }); if (board === 'ideas' && !get().loaded) void get().load() },
    load: async () => {
      try { set({ ideas: (await unwrap(http.GET('/story/ideas'))).items, loaded: true }) }
      catch (e) { if ((e as ApiError).status !== 409) toast(`Ideas: ${detail(e)}`) }
    },
    select: (ideaId) => set({ ideaId }),
    idea: () => get().ideas.find((i) => i.id === get().ideaId),
    create: async (cls, assetId, name) => {
      try {
        const i = await unwrap(http.POST('/story/ideas', { body: { cls, asset_id: assetId ?? null, name: name ?? null, note: '' } }))
        put(i); return i
      } catch (e) { toast(`New idea: ${detail(e)}`); return null }
    },
    patch: async (id, body) => {
      const cur = get().ideas.find((i) => i.id === id)
      if (!cur) return
      try { put(await unwrap(http.PATCH('/story/ideas/{iid}', { params: { path: { iid: id } }, body: { ...body, revision: cur.revision } }))) }
      catch (e) { toast(`Idea: ${detail(e)}`); void get().load() }
    },
    addVariant: async (id, assetId) => {
      try { const i = await unwrap(http.POST('/story/ideas/{iid}/variants', { params: { path: { iid: id } }, body: { asset_id: assetId } })); put(i); return i }
      catch (e) { toast(`Add a variant: ${detail(e)}`); return null }
    },
    removeVariant: async (id, vid) => {
      try { put(await unwrap(http.DELETE('/story/ideas/{iid}/variants/{vid}', { params: { path: { iid: id, vid } } }))) }
      catch (e) { toast(`Remove the variant: ${detail(e)}`) }
    },
    makeClay: async (id, vid) => {
      try {
        const r = await unwrap(http.POST('/story/ideas/{iid}/variants/{vid}/clay', { params: { path: { iid: id, vid } } }))
        put(r.idea)
        toast('Making the clay: the A-pose picture, then the fit (about a minute), then the shell in the background (minutes)', 'info')
      } catch (e) { toast(`Make the clay: ${detail(e)}`) }
    },
    keep: async (id, vid, profileId, name) => {
      try {
        const r = await unwrap(http.POST('/story/ideas/{iid}/keep', { params: { path: { iid: id } }, body: { variant_id: vid, profile_id: profileId ?? null, name: name ?? null } }))
        put(r.idea)
        const p = r.profile as Profile
        const { useStory, revealClass } = await import('./storyStore')
        await useStory.getState().loadProfiles()
        revealClass(p.cls)
        set({ board: 'cast' })
        useStory.getState().selectProfile(p.id, p.current)
        toast(profileId ? `Kept as ${p.name} ${p.current}` : `Kept: ${p.name} is in Cast — the sheet drafted from the prompt`, 'success')
        return p
      } catch (e) { toast(`Keep: ${detail(e)}`); return null }
    },
    remove: async (id) => {
      try {
        await unwrap(http.DELETE('/story/ideas/{iid}', { params: { path: { iid: id } } }))
        set({ ideas: get().ideas.filter((i) => i.id !== id), ideaId: get().ideaId === id ? null : get().ideaId })
      } catch (e) { toast(`Delete the idea: ${detail(e)}`) }
    },
    onChanged: (data) => {
      const id = data?.id
      if (!id || !get().loaded) return
      if (data?.deleted) { set({ ideas: get().ideas.filter((i) => i.id !== id), ideaId: get().ideaId === id ? null : get().ideaId }); return }
      void unwrap(http.GET('/story/ideas/{iid}', { params: { path: { iid: id } } })).then(put).catch(() => undefined)
    },
  }
})
export const ideas = () => useIdeas.getState()

/** The variant in focus (else the newest). */
export const focusOf = (i: Idea | undefined): IdeaVariant | undefined => i?.variants.find((v) => v.id === i.focus) ?? i?.variants[i.variants.length - 1]
/** A variant's clay in words for the card and the bench. */
export function clayWords(v: IdeaVariant | undefined): string {
  const c = v?.clay
  if (!c) return 'no clay yet'
  switch (c.step) {
    case 'drawing': return 'drawing the A-pose…'
    case 'fitting': return 'fitting the body…'
    case 'shell': return 'figure ready · the shell in the background…'
    case 'done': return c.shell_asset_id ? 'figure and shell' : 'figure'
    default: return c.error ? `stopped: ${c.error}` : 'stopped'
  }
}
