// 17 (D85): the Story suite's store — SY0: the world (L1 — logline, synopsis, styles, the spine's beats, the Flow's variables) with
// debounced saves that carry its revision (409 → reload, the last change lost and said so), the section the editor shows and the item
// the Inspector edits. Profiles (SY1), shots (SY2) and the flow (SY3) join here. Generate reads the styles for its picker (09 §3a, D85).
import { create } from 'zustand'
import { type ApiError, http, unwrap } from '../../api/client'
import type { StoryBeat, StoryVariable, World, WorldStyle } from '../../api/types'
import { useSession } from '../../store/session'

export type Section = 'logline' | 'synopsis' | 'styles' | 'spine' | 'variables'
export type Selection = { kind: 'style' | 'beat' | 'variable'; id: string } | null   // a variable's id is its name
export const SECTIONS: { id: Section; label: string }[] = [
  { id: 'logline', label: 'Logline' }, { id: 'synopsis', label: 'Synopsis' }, { id: 'styles', label: 'Styles' }, { id: 'spine', label: 'Spine' }, { id: 'variables', label: 'Variables' },
]

export interface StoryState {
  world: World | null; loading: boolean; saving: boolean
  section: Section; selected: Selection
  load: () => Promise<void>
  flush: () => Promise<void>
  setSection: (s: Section) => void
  select: (s: Selection) => void
  /** A change to the world: applied at once, saved after 300 ms with the document's revision. */
  edit: (patch: Partial<Pick<World, 'logline' | 'synopsis' | 'styles' | 'default_style' | 'spine' | 'variables'>>) => void
  addStyle: (name?: string) => string
  setStyle: (id: string, patch: Partial<WorldStyle>) => void
  removeStyle: (id: string) => void
  setDefaultStyle: (id: string | null) => void
  addBeat: (title?: string) => string
  setBeat: (id: string, patch: Partial<StoryBeat>) => void
  removeBeat: (id: string) => void
  moveBeat: (id: string, delta: -1 | 1) => void
  addVariable: (name?: string) => string
  setVariable: (name: string, patch: Partial<StoryVariable>) => void
  removeVariable: (name: string) => void
  /** The selected item goes (a style, a beat or a variable). */
  removeSelected: () => void
  /** `story.changed` on the socket: another writer moved the world — reload when nothing of ours is pending. */
  onChanged: (data: { kind?: string; revision?: number } | null) => void
}

const uid = (prefix: string) => `${prefix}_${crypto.randomUUID().replace(/-/g, '').slice(0, 8)}`
const EMPTY: World = { schema_version: 1, logline: '', synopsis: '', styles: [], default_style: null, spine: [], variables: [], revision: 0, created_at: '', updated_at: '' }

let saveTimer: number | null = null
let saveSeq = 0

async function save(get: () => StoryState, set: (p: Partial<StoryState>) => void): Promise<void> {
  const cur = get().world
  if (!cur) return
  const seq = ++saveSeq
  set({ saving: true })
  try {
    const next = await unwrap(http.PUT('/story/world', { body: cur as never }))
    if (seq === saveSeq && get().world) set({ world: { ...get().world!, revision: next.revision, updated_at: next.updated_at } })
  } catch (e) {
    const err = e as ApiError
    if (err.status === 409) {
      useSession.getState().toast('The world changed elsewhere — reloaded; your last change was not saved', 'error')
      await get().load()
    } else useSession.getState().toast(`World not saved: ${err.detail ?? e}`, 'error')
  } finally { if (seq === saveSeq) set({ saving: false }) }
}

function schedule(get: () => StoryState, set: (p: Partial<StoryState>) => void): void {
  if (saveTimer) window.clearTimeout(saveTimer)
  saveTimer = window.setTimeout(() => { saveTimer = null; void save(get, set) }, 300)
}

export const useStory = create<StoryState>()((set, get) => {
  const edit: StoryState['edit'] = (patch) => { const w = get().world ?? EMPTY; set({ world: { ...w, ...patch } }); schedule(get, set) }
  return {
    world: null, loading: false, saving: false, section: 'logline', selected: null,
    load: async () => {
      set({ loading: true })
      try { set({ world: await unwrap(http.GET('/story/world')) }) }
      catch (e) { if ((e as ApiError).status !== 409) useSession.getState().toast(`World: ${(e as ApiError).detail ?? e}`, 'error'); set({ world: null }) }
      finally { set({ loading: false }) }
    },
    flush: async () => { if (saveTimer) { window.clearTimeout(saveTimer); saveTimer = null; await save(get, set) } },
    setSection: (section) => set({ section }),
    select: (selected) => set({ selected }),
    edit,
    addStyle: (name) => {
      const w = get().world ?? EMPTY
      const id = uid('sty')
      const n = name?.trim() || `Style ${w.styles.length + 1}`
      edit({ styles: [...w.styles, { id, name: n, fragment: '', group_id: null }], default_style: w.default_style ?? (w.styles.length ? w.default_style : id) })
      set({ selected: { kind: 'style', id }, section: 'styles' })
      return id
    },
    setStyle: (id, patch) => { const w = get().world; if (w) edit({ styles: w.styles.map((s) => (s.id === id ? { ...s, ...patch } : s)) }) },
    removeStyle: (id) => {
      const w = get().world; if (!w) return
      edit({ styles: w.styles.filter((s) => s.id !== id), default_style: w.default_style === id ? null : w.default_style })
      if (get().selected?.id === id) set({ selected: null })
    },
    setDefaultStyle: (id) => edit({ default_style: id }),
    addBeat: (title) => {
      const w = get().world ?? EMPTY
      const id = uid('beat')
      edit({ spine: [...w.spine, { id, title: title?.trim() || `StoryBeat ${w.spine.length + 1}`, line: '' }] })
      set({ selected: { kind: 'beat', id }, section: 'spine' })
      return id
    },
    setBeat: (id, patch) => { const w = get().world; if (w) edit({ spine: w.spine.map((b) => (b.id === id ? { ...b, ...patch } : b)) }) },
    removeBeat: (id) => { const w = get().world; if (!w) return; edit({ spine: w.spine.filter((b) => b.id !== id) }); if (get().selected?.id === id) set({ selected: null }) },
    moveBeat: (id, delta) => {
      const w = get().world; if (!w) return
      const i = w.spine.findIndex((b) => b.id === id), j = i + delta
      if (i < 0 || j < 0 || j >= w.spine.length) return
      const spine = [...w.spine]; const [b] = spine.splice(i, 1); spine.splice(j, 0, b)
      edit({ spine })
    },
    addVariable: (name) => {
      const w = get().world ?? EMPTY
      let n = name?.trim().replace(/[^A-Za-z0-9_]/g, '_') || `flag_${w.variables.length + 1}`
      if (/^\d/.test(n)) n = `_${n}`
      while (w.variables.some((v) => v.name === n)) n = `${n}_`
      edit({ variables: [...w.variables, { name: n, type: 'bool', values: [], default: false }] })
      set({ selected: { kind: 'variable', id: n }, section: 'variables' })
      return n
    },
    setVariable: (name, patch) => {
      const w = get().world; if (!w) return
      const vars = w.variables.map((v) => {
        if (v.name !== name) return v
        const next = { ...v, ...patch }
        if (next.type === 'enum') { if (!next.values.length) next.values = ['a', 'b']; if (typeof next.default !== 'string' || !next.values.includes(next.default)) next.default = next.values[0] }
        else { next.values = []; if (typeof next.default !== 'boolean') next.default = false }
        return next
      })
      edit({ variables: vars })
      if (patch.name && get().selected?.kind === 'variable' && get().selected?.id === name) set({ selected: { kind: 'variable', id: patch.name } })
    },
    removeVariable: (name) => { const w = get().world; if (!w) return; edit({ variables: w.variables.filter((v) => v.name !== name) }); if (get().selected?.id === name) set({ selected: null }) },
    removeSelected: () => {
      const s = get().selected; if (!s) return
      if (s.kind === 'style') get().removeStyle(s.id); else if (s.kind === 'beat') get().removeBeat(s.id); else get().removeVariable(s.id)
    },
    onChanged: (data) => {
      if (data?.kind && data.kind !== 'world') return
      const w = get().world
      if (!w || saveTimer !== null || get().saving) return
      if (data?.revision !== undefined && data.revision <= w.revision) return
      void get().load()
    },
  }
})

export const sy = () => useStory.getState()

/** D85: the style Generate carries — the panel's own choice, or the world's default when it has none; null = no style. */
export function styleFor(choice: string | null | undefined): string | null {
  if (choice !== undefined) return choice
  return useStory.getState().world?.default_style ?? null
}
