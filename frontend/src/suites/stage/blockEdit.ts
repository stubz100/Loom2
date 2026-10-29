// U5c (D157 G8, G9; proto01_UI2 04 §3.2): the animation editor's verbs on clip blocks and templates — a block moved, trimmed, looped,
// re-timed or toggled (evaluated first, so its new length goes with the edit in one undo step), baked into keys, saved as an animation;
// the project's templates and the author's library (the motion library's *Mine*), a template applied as a block; a motion file imported.
import { create } from 'zustand'
import { http, unwrap } from '../../api/client'
import type { StageDoc } from '../../api/types'
import type { MenuItem } from '../../frame/commands'
import { isTauri, pickFiles } from '../../shell/tauri'
import { askText, useSession } from '../../store/session'
import { keyframesOf, sampleFigure, type ObjectKey } from './anim'
import { blockKeys, blockRuns, blocksReady, hipOf, templatesChanged, useBlocks, type AnimationTemplate, type MotionBlock } from './blocks'
import { thinKeys } from './motion/bake'
import { st } from './stageStore'

const toast = (t: string, kind: 'success' | 'error' | 'info' = 'info') => useSession.getState().toast(t, kind)
const blockOf = (doc: StageDoc | null, oid: string, bid: string) => doc?.tracks?.[oid]?.find((b) => b.id === bid) ?? null
const newId = (p: string) => `${p}_${crypto.randomUUID().replace(/-/g, '').slice(0, 8)}`

/** A block changed: evaluated with the change first, then written with its new length (one undo step); a change it cannot be evaluated
 *  with is not made. */
export async function editBlock(oid: string, bid: string, patch: Partial<MotionBlock>): Promise<boolean> {
  const doc = st().current, b = blockOf(doc, oid, bid)
  if (!doc || !b) return false
  const next = { ...b, ...patch }
  const probe = { ...doc, tracks: { ...(doc.tracks ?? {}), [oid]: (doc.tracks?.[oid] ?? []).map((x) => (x.id === bid ? next : x)) } }
  const keys = await blockKeys(probe, oid, bid)
  if (!keys?.length) { toast(`The clip was not changed: ${useBlocks.getState().errors[bid] ?? 'it could not be evaluated'}`, 'error'); return false }
  st().patchBlock(oid, bid, { ...patch, length: keys[keys.length - 1].frame - keys[0].frame + 1 })
  return true
}

/** The block's frames per loop and its seconds of clip per frame (to turn a drag into a trim or a loop count). */
const perLoop = (b: MotionBlock) => Math.max(1, Math.round(Math.max(1, b.length) / Math.max(1, b.loops || 1)))

/** A drag on a block's bar as a change to it (04 §3.2): the body moves it, the left edge trims its start, the right edge trims its end —
 *  or, on a looping clip, sets how many times it loops —, Alt slides the clip inside it. `delta` in stage frames. */
export function dragPatch(b: MotionBlock, mode: 'move' | 'in' | 'out' | 'slip', delta: number, fps: number): Partial<MotionBlock> | null {
  if (!delta) return null
  const spf = b.speed / Math.max(1, fps || 24)                          // seconds of clip a frame of the stage holds
  if (mode === 'move') return { start: Math.max(0, b.start + delta) }
  if (mode === 'in') {
    const d = Math.round(Math.max(-b.start, -b.trim_in / spf, delta))
    return d ? { start: b.start + d, trim_in: Math.max(0, b.trim_in + d * spf) } : null
  }
  if (mode === 'out') {
    if (b.loops !== 1) return { loops: Math.max(1, Math.min(30, Math.round((b.length + delta) / perLoop(b)))) }
    return { trim_out: Math.max(b.trim_in + spf, b.trim_in + (b.length - 1 + delta) * spf) }
  }
  return { trim_in: Math.max(0, b.trim_in - delta * spf), ...(b.trim_out != null ? { trim_out: Math.max(spf, b.trim_out - delta * spf) } : {}) }
}

export function dragBlock(oid: string, bid: string, mode: 'move' | 'in' | 'out' | 'slip', delta: number): void {
  const doc = st().current, b = blockOf(doc, oid, bid)
  const patch = doc && b ? dragPatch(b, mode, delta, doc.size.fps || 24) : null
  if (patch) void editBlock(oid, bid, patch)
}

/** *Bake to keys*: the block's frames become the figure's keys (thinned) and the block goes — one undo step; the range stays. */
export async function bakeBlock(oid: string, bid: string): Promise<void> {
  const doc = st().current
  if (!doc) return
  const keys = await blockKeys(doc, oid, bid)
  if (!keys?.length) { toast('The clip could not be evaluated, so it was not baked', 'error'); return }
  st().bakeBlock(oid, bid, thinKeys(keys))
}

// ---- templates: the project's and the author's library (*Mine*) ----
interface TemplatesState { revision: number; items: AnimationTemplate[]; library: AnimationTemplate[]; loaded: boolean; load: () => Promise<void> }
export const useTemplates = create<TemplatesState>()((set) => ({
  revision: 0, items: [], library: [], loaded: false,
  load: async () => {
    try { const r = await unwrap(http.GET('/stages/animations')); set({ revision: r.revision, items: r.items as unknown as AnimationTemplate[], library: r.library as unknown as AnimationTemplate[], loaded: true }) }
    catch (e) { toast(`Animations: ${(e as { detail?: string }).detail ?? e}`, 'error') }
  },
}))

async function putTemplates(items: AnimationTemplate[]): Promise<boolean> {
  try {
    const r = await unwrap(http.PUT('/stages/animations', { body: { revision: useTemplates.getState().revision, items } as never }))
    useTemplates.setState({ revision: r.revision, items: r.items as unknown as AnimationTemplate[], library: r.library as unknown as AnimationTemplate[], loaded: true })
    templatesChanged()
    return true
  } catch (e) { toast(`Animations: ${(e as { detail?: string }).detail ?? e}`, 'error'); void useTemplates.getState().load(); return false }
}

/** Keys re-based to frame 0 (a template's own time). */
const rebased = (keys: ObjectKey[]): ObjectKey[] => { const f0 = keys[0]?.frame ?? 0; return keys.map((k) => ({ ...k, frame: k.frame - f0 })) }

async function saveTemplate(name: string, keys: ObjectKey[], oid: string, from: { start: number; end: number }): Promise<void> {
  const doc = st().current, o = doc?.objects.find((x) => x.id === oid)
  if (!doc || !o || !keys.length) return
  await useTemplates.getState().load()
  const t = { id: newId('anm'), name, rig: 'mannequin', frames: keys[keys.length - 1].frame - keys[0].frame + 1, fps: doc.size.fps || 24, hip: hipOf(o), keys: rebased(keys),
    source: { stage_id: doc.id, object_id: oid, start: from.start, end: from.end } } as unknown as AnimationTemplate
  if (await putTemplates([...useTemplates.getState().items, t])) toast(`${name} saved — under Mine in the motion library; it applies to any figure`, 'success')
}

/** *Save as animation…* from a block: its evaluated frames, re-based to frame 0. */
export async function saveBlockAsAnimation(oid: string, bid: string): Promise<void> {
  const doc = st().current, b = blockOf(doc, oid, bid)
  if (!doc || !b) return
  const name = await askText({ title: 'Save as an animation', text: 'Kept in the project, in the stage\'s own keys: it applies to any figure, its root scaled to that figure\'s hips.', initial: b.source.clip || 'Animation' })
  if (!name?.trim()) return
  const keys = await blockKeys(doc, oid, bid)
  if (keys?.length) await saveTemplate(name.trim(), keys, oid, { start: b.start, end: b.start + b.length - 1 })
}

/** *Save as animation…* from a figure's track: everything it does across the shot's range (blocks, keys and corrections), a key a frame. */
export async function saveRangeAsAnimation(oid: string): Promise<void> {
  const doc = st().current, o = doc?.objects.find((x) => x.id === oid)
  if (!doc || !o) return
  const name = await askText({ title: `Save ${o.name}'s motion as an animation`, text: `Frames ${doc.range.start}–${doc.range.end}: its clips, keys and corrections, kept in the project in the stage's own keys.`, initial: `${o.name}'s motion` })
  if (!name?.trim()) return
  await blocksReady(doc)
  const layer = keyframesOf(doc).objects[oid], runs = blockRuns(doc, oid, layer)
  const keys: ObjectKey[] = []
  for (let f = doc.range.start; f <= doc.range.end; f++) { const s = sampleFigure(o, layer, runs, f); keys.push({ frame: f, ease: 'linear', transform: s.transform, pose: s.pose ?? null }) }
  await saveTemplate(name.trim(), thinKeys(keys), oid, doc.range)
}

/** A template applied as a block to the selected figure at the playhead. */
export async function applyTemplate(t: AnimationTemplate): Promise<void> {
  const doc = st().current, o = st().object(st().selected)
  if (!doc || !o || o.kind !== 'mannequin') { toast('Select a figure to apply the animation to', 'info'); return }
  const had = (keyframesOf(doc).objects[o.id]?.length ?? 0) > 0 || (doc.tracks?.[o.id]?.length ?? 0) > 0
  const block = { id: newId('blk'), source: { kind: 'template', id: t.id, clip: t.name }, start: st().frame, trim_in: 0, trim_out: null, loops: 1, speed: 1,
    blend_in: had ? 6 : 0, blend_out: 0, in_place: false, foot_lock: true, ground: true, mirror: false, path: false, length: 0 } as MotionBlock
  const probe = { ...doc, tracks: { ...(doc.tracks ?? {}), [o.id]: [...(doc.tracks?.[o.id] ?? []), block] } }
  const keys = await blockKeys(probe, o.id, block.id)
  if (!keys?.length) { toast(`${t.name} was not applied: ${useBlocks.getState().errors[block.id] ?? 'it could not be evaluated'}`, 'error'); return }
  st().addBlock(o.id, { ...block, length: keys[keys.length - 1].frame - keys[0].frame + 1 })
  toast(`${t.name} on ${o.name}: frames ${keys[0].frame}–${keys[keys.length - 1].frame}`, 'success')
}

export async function templateToLibrary(t: AnimationTemplate): Promise<void> {
  try {
    const r = await unwrap(http.POST('/stages/animations/{aid}/library', { params: { path: { aid: t.id } } }))
    useTemplates.setState({ revision: r.revision, items: r.items as unknown as AnimationTemplate[], library: r.library as unknown as AnimationTemplate[] })
    templatesChanged()
    toast(`${t.name} is in your library — every project has it under Mine`, 'success')
  } catch (e) { toast(`Library: ${(e as { detail?: string }).detail ?? e}`, 'error') }
}

export async function removeTemplate(t: AnimationTemplate, from: 'project' | 'library'): Promise<void> {
  if (from === 'project') { await putTemplates(useTemplates.getState().items.filter((x) => x.id !== t.id)); return }
  try {
    const r = await unwrap(http.DELETE('/stages/animations/library/{aid}', { params: { path: { aid: t.id } } }))
    useTemplates.setState({ library: r.library as unknown as AnimationTemplate[] })
    templatesChanged()
  } catch (e) { toast(`Library: ${(e as { detail?: string }).detail ?? e}`, 'error') }
}

/** *Import…* (04 §3.2): a motion file copied into the local motion folder (the OS picker in the app; a path typed in a browser). */
export async function importMotion(refresh: () => Promise<void>): Promise<void> {
  const paths = isTauri() ? await pickFiles('Import a motion file', [{ name: 'Motion files', extensions: ['glb', 'gltf', 'fbx'] }])
    : [await askText({ title: 'Import a motion file', text: 'The path of a .glb, .gltf or .fbx file: it is copied into the local motion folder.', placeholder: 'C:\\motion\\Walk.fbx' })].filter((p): p is string => !!p?.trim())
  for (const path of paths) {
    try { await unwrap(http.POST('/motion/import', { body: { path } })); toast(`${path.split(/[\\/]/).pop()} imported into the local motion folder`, 'success') }
    catch (e) { toast(`Import: ${(e as { detail?: string }).detail ?? e}`, 'error') }
  }
  if (paths.length) await refresh()
}

/** A block's right-click (04 §3.2): speed, loops, blend, mirror, in place, foot lock, the feet on the floor; bake; save; remove. */
export function blockMenu(oid: string, bid: string): MenuItem[] {
  const doc = st().current, b = blockOf(doc, oid, bid), o = doc?.objects.find((x) => x.id === oid)
  if (!doc || !b || !o) return []
  const set = (patch: Partial<MotionBlock>) => () => void editBlock(oid, bid, patch)
  const flag = (label: string, key: 'mirror' | 'in_place' | 'foot_lock' | 'ground'): MenuItem => ({ label, checked: !!b[key], run: set({ [key]: !b[key] } as Partial<MotionBlock>) })
  const hasPath = !!o.path && o.path.length >= 2
  return [
    { heading: `${b.source.clip || 'animation'} · frames ${b.start}–${b.start + Math.max(1, b.length) - 1}` },
    { label: 'Speed', items: [0.5, 0.75, 1, 1.25, 1.5, 2].map((v): MenuItem => ({ label: `×${v}`, checked: b.speed === v, run: set({ speed: v }) })) },
    { label: 'Loops', items: [...[1, 2, 3, 4, 6, 8].map((v): MenuItem => ({ label: `${v}×`, checked: b.loops === v, run: set({ loops: v }) })),
      ...(hasPath ? [{ label: `As far as ${o.name}'s path goes`, checked: b.loops === 0, run: set({ loops: 0, path: true }) } as MenuItem] : [])] },
    { label: 'Blend in', items: [0, 6, 12, 24].map((v): MenuItem => ({ label: v ? `${v} frames` : 'none (a cut)', checked: b.blend_in === v, run: set({ blend_in: v }) })) },
    { sep: true },
    flag('Mirror', 'mirror'), flag('In place', 'in_place'), flag('Foot lock', 'foot_lock'), flag('Feet on the floor', 'ground'),
    ...(hasPath ? [{ label: `Along ${o.name}'s path`, checked: b.path, run: set({ path: !b.path }) } as MenuItem] : []),
    { sep: true },
    { label: 'Bake to keys', run: () => void bakeBlock(oid, bid) },
    { label: 'Save as animation…', run: () => void saveBlockAsAnimation(oid, bid) },
    { sep: true },
    { label: 'Remove the clip', danger: true, run: () => st().removeBlock(oid, bid) },
  ]
}
