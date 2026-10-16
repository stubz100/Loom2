// D90 (02 §4.1): styles as images — a style's face is the cover of its group (`StoryStyle.group_id`); "Make a sample image" renders the
// style on a fixed preview scene (a person, a place and an object in one frame) as one Draft t2i on the open-licence swatch model, its
// fragment appended by the server (story.resolve_style); an image dropped on a style tile becomes a sample and the cover. Pure: tested.
import type { AlbumNode, Job, WorldStyle } from '../../api/types'
import type { DragItem, DragPayload, DropVerdict } from '../../frame/drag'
import type { PresetIcon } from '../../frame/PresetIcons'

/** The preview scene every style is shown on, so samples compare across styles. */
export const SAMPLE_PROMPT = 'a woman in a long coat beside an old bicycle on a cobbled street at dusk, a lit shop window behind her'
export const SAMPLE_SEED = 90                                 // the first sample of every style shares a seed (a set, as the swatch pack); later ones 0 = random
export const SAMPLE_PX = 768                                  // square, a multiple of 16: big enough to read a look at 108 px and in the Inspector
export const DEFAULT_ID = '__default'
export const NONE_ID = '__none'

export const styleGroupName = (name: string) => `Style · ${name.trim() || 'untitled'}`

/** A group in the album tree by id (the tree as `useAlbum` holds it). */
export function findNode(tree: AlbumNode | null | undefined, id: string | null | undefined): AlbumNode | null {
  if (!tree || !id) return null
  if (tree.id === id) return tree
  for (const c of tree.children) { const f = findNode(c, id); if (f) return f }
  return null
}

/** The style's face: its group's cover (the chosen cover, else the page's top asset), or null while it has no sample. */
export function styleFace(s: Pick<WorldStyle, 'group_id'> | null | undefined, tree: AlbumNode | null | undefined): string | null {
  return findNode(tree, s?.group_id)?.cover_ids[0] ?? null
}

/** The newest sample job of a style still waiting or running (the tile's busy mark, the verb's `when`). */
export function sampleJob(jobs: Record<string, Job>, styleId: string): Job | undefined {
  return Object.values(jobs).filter((j) => j.origin?.suite === 'story' && j.origin.surface === 'style' && j.origin.ref === styleId && ['staged', 'queued', 'running'].includes(j.status))
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))[0]
}

/** The one-image t2i a sample runs: text mode, the swatch model, square Draft size, the style id (its fragment appended at submit). */
export function sampleRecipe(styleId: string, modelId: string, first: boolean): Record<string, unknown> {
  return { kind: 't2i', model_id: modelId, prompt_mode: 'text', prompt_text: SAMPLE_PROMPT, width: SAMPLE_PX, height: SAMPLE_PX, seeds: [first ? SAMPLE_SEED : 0], style_id: styleId }
}

/** A drop on a style tile: images become samples (copies — the originals stay where they are), the first the cover; clips are refused. */
export function sampleDrop(p: DragPayload | DragItem[], name: string): { take: string[]; verdict: DropVerdict } {
  const items = (Array.isArray(p) ? p : p.items).filter((i) => i.kind === 'asset')
  const take = [...new Set(items.filter((i) => !i.media || i.media === 'image').map((i) => i.id))]
  if (!items.length) return { take, verdict: { ok: false } }
  if (!take.length) return { take, verdict: { ok: false, reason: items.length === 1 ? "A clip can't be a style sample" : "Clips can't be style samples" } }
  return { take, verdict: { ok: true, label: take.length === 1 ? `Make it the sample of ${name}` : `Add ${take.length} samples to ${name} (the first the cover)` } }
}

/** The picker's tile id for a value: undefined = the world's default, null = none, else the style id. */
export const pickerId = (v: string | null | undefined): string => (v === undefined ? DEFAULT_ID : v === null ? NONE_ID : v)
export const pickerValue = (id: string): string | null | undefined => (id === DEFAULT_ID ? undefined : id === NONE_ID ? null : id)

const tip = (s: WorldStyle) => s.fragment.trim() || 'no prompt fragment yet'

/** The picker's tiles: default (the default style's face), none, then every style with ★ on the default; the fragment is the tooltip. */
export function pickerItems(styles: WorldStyle[], defaultId: string | null | undefined, face: (s: WorldStyle) => string | null, thumb: (assetId: string) => string, none?: PresetIcon['icon']): PresetIcon[] {
  const def = styles.find((s) => s.id === defaultId)
  const img = (s: WorldStyle | undefined) => { const f = s ? face(s) : null; return f ? thumb(f) : null }
  return [
    { id: DEFAULT_ID, label: def ? `Default · ${def.name}` : 'Default · none', hint: def ? `the world's ★ style — ${tip(def)}` : 'the world has no default style', img: img(def), badge: 'default' },
    { id: NONE_ID, label: 'No style', hint: 'nothing appended to the prompt', icon: none },
    ...styles.map((s): PresetIcon => ({ id: s.id, label: s.name || 'untitled', hint: tip(s), img: img(s), badge: s.id === defaultId ? '★' : undefined })),
  ]
}
