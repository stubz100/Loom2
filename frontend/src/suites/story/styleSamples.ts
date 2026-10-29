// D90 (02 §4.1): styles as images — a style's face is the cover of its group (`StoryStyle.group_id`); "Make a sample image" renders the
// style on a fixed preview scene (a person, a place and an object in one frame) as one t2i on the sample model (D91: Settings › Samples), its
// fragment appended by the server (story.resolve_style); an image dropped on a style tile becomes a sample and the cover. Pure: tested.
import type { AlbumNode, Capabilities, Job, SampleModelCaps, WorldStyle } from '../../api/types'
import type { DragItem, DragPayload, DropVerdict } from '../../frame/drag'
import type { PresetIcon } from '../../frame/PresetIcons'
import { fieldGlyph } from '../../frame/presetGlyphs'

/** The preview scene every style is shown on, so samples compare across styles — the default; Settings › Samples may change it (D90). */
export const SAMPLE_PROMPT = 'a woman in a long coat beside an old bicycle on a cobbled street at dusk, a lit shop window behind her'
export const SAMPLE_SEED = 90                                 // the first sample of every style shares a seed (a set, as the swatch pack); later ones 0 = random
export const SAMPLE_PX = 768                                  // square, a multiple of 16: big enough to read a look at 108 px and in the Inspector (a spec may say otherwise, D91)
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

/** D91: the model a sample renders on — Settings › Samples' model when this build offers it (`caps.sample_models`), else the default
 *  swatch model (the list's `default`, the server's `defaults.swatch`); the same rule as the server's preset swatches. null before caps. */
export function pickSampleModel(caps: Pick<Capabilities, 'sample_models' | 'defaults'> | null | undefined, settingId?: string | null): Pick<SampleModelCaps, 'id' | 'style_px' | 'swatch_px'> | null {
  const list = caps?.sample_models ?? []
  const hit = (settingId && list.find((m) => m.id === settingId)) || list.find((m) => m.default) || list[0]
  if (hit) return hit
  const id = caps?.defaults?.swatch || caps?.defaults?.t2i
  return id ? { id, style_px: SAMPLE_PX, swatch_px: 512 } : null
}

const fetched = (m: Pick<SampleModelCaps, 'health'>) => (m.health === 'missing' ? ' (not fetched)' : '')

/** D91: Settings › Samples › Sample model's options — "default · <the default's label>" (value '' = the setting's null), then the other
 *  sample models by the server's order; a model whose weights are not on disk says "(not fetched)". */
export function sampleOptions(list: Pick<SampleModelCaps, 'id' | 'label' | 'default' | 'health'>[] | null | undefined): { value: string; label: string }[] {
  const all = list ?? []
  const def = all.find((m) => m.default)
  return [{ value: '', label: def ? `default · ${def.label}${fetched(def)}` : 'default' },
    ...all.filter((m) => !m.default).map((m) => ({ value: m.id, label: `${m.label}${fetched(m)}` }))]
}

/** The select's value for a saved setting: '' for none, the default model or one this build does not offer (it falls back to the default). */
export function sampleValue(settingId: string | null | undefined, list: Pick<SampleModelCaps, 'id' | 'default'>[] | null | undefined): string {
  const m = settingId ? (list ?? []).find((x) => x.id === settingId) : undefined
  return m && !m.default ? m.id : ''
}

/** The one-image t2i a sample runs: text mode, the sample model, a square size (the model's, D91), the style id (its fragment appended at submit). */
/** U2 (D157, G2): the scene a style's sample is rendered on — the project's own (the Look's `sample_scene`), else Settings › Samples'. */
export const sampleScene = (world: { sample_scene?: string } | null | undefined, settingsPrompt?: string | null): string | null => world?.sample_scene?.trim() || settingsPrompt?.trim() || null

export function sampleRecipe(styleId: string, modelId: string, first: boolean, prompt?: string | null, px: number = SAMPLE_PX): Record<string, unknown> {
  return { kind: 't2i', model_id: modelId, prompt_mode: 'text', prompt_text: prompt?.trim() || SAMPLE_PROMPT, width: px, height: px, seeds: [first ? SAMPLE_SEED : 0], style_id: styleId }
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

/** The picker's tiles: default (the default style's face), none, then every style with ★ on the default; the fragment is the tooltip. D92: a
 *  style without a sample shows the palette glyph (its sample is made by hand — "Make a sample image" — never queued by itself). */
export function pickerItems(styles: WorldStyle[], defaultId: string | null | undefined, face: (s: WorldStyle) => string | null, thumb: (assetId: string) => string, none: PresetIcon['icon'] = fieldGlyph('negative')): PresetIcon[] {
  const def = styles.find((s) => s.id === defaultId)
  const img = (s: WorldStyle | undefined) => { const f = s ? face(s) : null; return f ? thumb(f) : null }
  return [
    { id: DEFAULT_ID, label: def ? `Default · ${def.name}` : 'Default · none', hint: def ? `the world's ★ style — ${tip(def)}` : 'the world has no default style', img: img(def), icon: fieldGlyph('palette'), badge: 'default' },
    { id: NONE_ID, label: 'No style', hint: 'nothing appended to the prompt', icon: none },
    ...styles.map((s): PresetIcon => ({ id: s.id, label: s.name || 'untitled', hint: tip(s), img: img(s), icon: fieldGlyph('palette'), badge: s.id === defaultId ? '★' : undefined })),
  ]
}
