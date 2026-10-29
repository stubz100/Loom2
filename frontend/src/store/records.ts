// U1 (D157, proto01_UI2 06 §5.3, seam 3): the records layer owns the events socket's fan-out. `session.applyEvent` keeps the session's
// own frames (jobs, the queue, the engine, models, the project) and publishes every other frame here. Today's record holders are reached as
// the session reached them — by dynamic import, so neither the session nor this module imports a suite — and any store may subscribe to the
// kinds it keeps (the new shell's layers take the records over this way, wave by wave). A reconnect publishes `resync`.
import type { EventFrame } from '../api/types'

/** A frame for the records: one of the socket's, or `resync` after a reconnect (`gap`: frames were lost, the lists reload). */
export type RecordFrame = EventFrame | { type: 'resync'; data: { gap: boolean } }
type Kind = RecordFrame['type']
type FrameOf<K extends Kind> = Extract<RecordFrame, { type: K }>

const subs = new Map<string, { kinds: ReadonlySet<string>; h: (f: RecordFrame) => void }>()

/** A store's subscription to some kinds, under an id (registered again — a hot reload — it replaces the first). Returns the unsubscribe. */
export function onRecords<K extends Kind>(id: string, kinds: K[], h: (f: FrameOf<K>) => void): () => void {
  subs.set(id, { kinds: new Set(kinds), h: h as (f: RecordFrame) => void })
  return () => { subs.delete(id) }
}

/** A frame for the records: today's holders first, then every subscriber of its kind (one failing never stops the next). */
export function publish(f: RecordFrame): void {
  route(f)
  for (const [id, { kinds, h }] of subs) {
    if (!kinds.has(f.type)) continue
    try { h(f) } catch (e) { console.error(`[records] ${id} on ${f.type}:`, e) }
  }
}

const ids = (f: { data?: unknown }): string[] => ((f.data as { ids?: string[] } | null)?.ids) ?? []

/** Today's record holders, by kind (moved here from session.applyEvent unchanged). */
function route(f: RecordFrame): void {
  switch (f.type) {
    case 'resync':                                                 // V65: a reconnect — the editor resyncs; after a gap the lists reload
      void import('../suites/edit/editorStore').then((m) => m.useEditor.getState().resync())
      if (!f.data.gap) return
      void import('../suites/catalogue/catalogueStore').then((m) => { for (const h of m.allCatalogueStores()) { const st = h.getState(); void st.load({ keepSelection: true }); void st.refreshMeta() } })
      void import('../suites/catalogue/albumStore').then((m) => void m.useAlbum.getState().load())
      void import('../suites/story/storyStore').then((m) => void m.useStory.getState().load())
      void import('../suites/animate/animateStore').then((m) => void m.useAnimate.getState().loadClips())
      return
    case 'preset_icons.changed': void import('../suites/generate/swatches').then((m) => m.useSwatches.getState().load()); return   // D90 (02 §6.3): a swatch was made or removed
    case 'catalogue.changed':
      void import('../suites/catalogue/catalogueStore').then((m) => { for (const h of m.allCatalogueStores()) { const st = h.getState(); void st.load(); void st.refreshMeta() } })
      return
    case 'group.changed':                                         // D34: placements moved; the tree, counts and open views follow
      void import('../suites/catalogue/albumStore').then((m) => void m.useAlbum.getState().load())
      void import('../suites/story/storyStore').then((m) => m.useStory.getState().onGroupChanged(ids(f)))   // 17 SY1: a version's pages
      void import('../suites/generate/generateStore').then((m) => m.mentionsMoved({ groups: ids(f) }))   // D93: a mentioned set grew → the preview's references
      void import('../suites/catalogue/catalogueStore').then((m) => { for (const h of m.allCatalogueStores()) { const st = h.getState(); void st.refreshMeta(); if (st.q.folder === 'unprocessed' || st.q.group_id) void st.load({ keepSelection: true }) } })
      return
    case 'asset.created': case 'asset.updated': case 'asset.deleted':
      void import('../suites/catalogue/catalogueStore').then((m) => { for (const h of m.allCatalogueStores()) h.getState().applyEvent(f) })
      if (f.type === 'asset.created' && ((f.data as { origin?: { suite?: string } } | null)?.origin?.suite === 'stage' || (f.data as { kind?: string } | null)?.kind === 'mesh'))   // ST3: a shot or a pass of a stage; proto01_UIcast CB2: a mesh made anywhere joins Clay's Meshes
        void import('../suites/stage/stageStore').then((m) => m.useStage.getState().onAssetCreated(f.data as never))
      if (f.type === 'asset.deleted')
        void import('../suites/stage/stageStore').then((m) => m.useStage.getState().onAssetDeleted(String((f.data as { id?: string } | null)?.id ?? '')))
      return
    case 'clip.updated': void import('../suites/animate/animateStore').then((m) => m.useAnimate.getState().onClipUpdated(f.data)); return
    case 'timeline.updated': void import('../suites/story/episode/sequenceStore').then((m) => m.onTimelineUpdated(f.data)); return
    case 'clip.ready': void import('../suites/animate/animateStore').then((m) => m.useAnimate.getState().onClipReady(f.data)); return
    case 'document.changed': void import('../suites/edit/editorStore').then((m) => m.useEditor.getState().onDocumentChanged(f.data)); return
    case 'story.changed': {                                       // 17 (D85): the world (later profiles, shots, the flow) moved on the server
      const d = f.data as { kind?: string; id?: string } | null
      void import('../suites/story/storyStore').then((m) => m.useStory.getState().onChanged(f.data as never))
      if (d?.kind === 'shot' && d.id) { const id = d.id; void import('../suites/story/recipeTick').then((m) => m.useRecipeTick.getState().bump(id)) }   // RC0: an open recipe refetches
      void import('../suites/catalogue/albumStore').then((m) => void m.useAlbum.getState().loadUsedBy())      // D92 §4.2: a version, style, board or entry may name another group
      if (d?.kind === 'profile' && d.id) { const id = d.id; void import('../suites/generate/generateStore').then((m) => m.mentionsMoved({ profile: id })) }   // D93: a linked character got a hero
      return
    }
    case 'lora.changed':                                          // 18 (D86) LT2: a LoRA trained or deleted — the registry and the versions' slots moved
      void import('../suites/story/storyStore').then((m) => m.useStory.getState().onLoraChanged(f.data as never))
      void import('../suites/generate/generateStore').then((m) => { const g = m.useGenerate.getState(); void g.loadLoras(g.panel.model_id) })
      return
    default: return
  }
}
