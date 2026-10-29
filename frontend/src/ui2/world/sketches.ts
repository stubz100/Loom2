// U3d (D157, proto01_UI2 03 §7): the Sketches home's pictures, its selection, and the verbs on them — make free sketches into the home,
// prototype a draft entity from one (the picture becomes its hero), trash one.
import { create } from 'zustand'
import { http, unwrap } from '../../api/client'
import type { Asset } from '../../api/types'
import { registerCommands } from '../../frame/commands'
import { onRecords } from '../../store/records'
import { askConfirm, askText, useSession } from '../../store/session'
import { useGenerate } from '../../suites/generate/generateStore'
import { useStory, type ProfileClass } from '../../suites/story/storyStore'
import { useWorld } from './worldStore'

interface SketchState { home: string | null; items: Asset[]; selected: string | null; loading: boolean; ideas: number; load: () => Promise<void>; select: (id: string | null) => void }

export const useSketches = create<SketchState>()((set, get) => ({
  home: null, items: [], selected: null, loading: false, ideas: 0,
  load: async () => {
    if (!useSession.getState().project?.open) return
    set({ loading: true })
    try {
      const home = get().home ?? (await unwrap(http.POST('/bin/homes', { body: { path: 'world/sketches' } }))).id
      const page = await unwrap(http.GET('/groups/{gid}', { params: { path: { gid: home } } }))
      const items = page.group.items.filter((it) => it.kind === 'asset').map((it) => page.assets[it.id]).filter((a): a is Asset => !!a && !a.trashed_at)
      const ideas = (await unwrap(http.GET('/story/ideas'))).items.filter((i) => !i.kept.length && i.variants.length).length   // U3e (G4): the old ideas still to bring in
      set({ home, ideas, items: items.sort((x, y) => (x.created_at < y.created_at ? 1 : -1)) })
    } catch (e) { useSession.getState().toast(`Sketches: ${(e as { detail?: string }).detail ?? e}`, 'error') }
    finally { set({ loading: false }) }
  },
  select: (selected) => set({ selected }),
}))
onRecords('ui2.world.sketches', ['group.changed', 'asset.deleted'], () => { if (useSketches.getState().home) void useSketches.getState().load() })

/** A sketch's name for its prototype: the prompt's first words (a JSON prompt's scene), else the class. */
export function nameFrom(prompt: string | null | undefined, fallback: string): string {
  let t = (prompt ?? '').trim()
  if (t.startsWith('{')) { try { const j = JSON.parse(t) as { subjects?: { description?: string }[]; scene?: string }; t = j.subjects?.[0]?.description || j.scene || '' } catch { t = '' } }
  const words = t.replace(/[,.;:].*$/s, '').split(/\s+/).filter(Boolean).slice(0, 4).join(' ')
  return words ? words[0].toUpperCase() + words.slice(1) : fallback
}

const sel = () => useSketches.getState().items.find((a) => a.id === useSketches.getState().selected) ?? null
async function prototype(cls: ProfileClass): Promise<void> {
  const a = sel()
  if (!a) return
  const name = await askText({ title: `A ${cls} from this sketch`, text: 'A draft: the sketch becomes its hero; its sheet, references, body and set come next.', initial: nameFrom(a.prompt_text, cls) })
  if (!name?.trim()) return
  const p = await useStory.getState().createProfile(name.trim(), cls, a.id)
  if (!p) return
  useSketches.getState().select(null)
  useWorld.getState().setRail(cls)
  useWorld.getState().pick(p.id)
}

registerCommands([
  { id: 'world.sketch.make', scope: 'world', label: 'Make sketches ▶', placement: ['panel'], when: () => !!useSession.getState().project?.open,
    hint: 'free pictures with the whole prompt, into bin/world/sketches',
    run: () => void (async () => {
      await useSketches.getState().load()
      const home = useSketches.getState().home
      if (home) await useGenerate.getState().generate(false, { suite: 'generate', surface: 'sketch', ref: null, payload: { group_id: home } }, { text: ' — they land in Sketches' })
    })() },
  { id: 'world.sketch.character', scope: 'world', label: 'Prototype a character', placement: ['inspector', 'context'], when: () => !!sel(), run: () => void prototype('character') },
  { id: 'world.sketch.prop', scope: 'world', label: 'Prototype a prop', placement: ['inspector', 'context'], when: () => !!sel(), run: () => void prototype('prop') },
  { id: 'world.sketch.place', scope: 'world', label: 'Prototype a place', placement: ['inspector', 'context'], when: () => !!sel(), run: () => void prototype('place') },
  { id: 'world.ideas.fold', scope: 'world', label: 'Bring the ideas in', placement: ['panel'], when: () => useSketches.getState().ideas > 0,
    hint: "each idea of the old Cast board becomes a draft entity of its class — its picture in focus the hero, the others its candidates",
    run: () => void (async () => {
      const n = useSketches.getState().ideas
      const ok = await askConfirm({ title: `Bring ${n} idea${n === 1 ? '' : 's'} in?`, okLabel: 'Bring them in',
        text: 'Each becomes a draft character, prop or place: the picture in focus its hero, the other pictures its candidates. The ideas stay on the old Cast board, marked kept.' })
      if (!ok) return
      try {
        const r = await unwrap(http.POST('/story/ideas/fold'))
        await useStory.getState().loadProfiles()
        void useSketches.getState().load()
        useSession.getState().toast(r.items.length ? `${r.items.length} draft${r.items.length === 1 ? '' : 's'}: ${r.items.map((x) => x.name).join(', ')}` : 'Nothing to bring in', 'success')
      } catch (e) { useSession.getState().toast(`Bring the ideas in: ${(e as { detail?: string }).detail ?? e}`, 'error') }
    })() },
  { id: 'world.sketch.trash', scope: 'world', label: 'Trash', placement: ['inspector', 'context'], danger: true, when: () => !!sel(),
    run: () => { const a = sel(); if (a) void unwrap(http.POST('/assets/trash', { body: { ids: [a.id] } })).then(() => { useSketches.getState().select(null); void useSketches.getState().load() }) } },
])
