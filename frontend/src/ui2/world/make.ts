// U3b (D157, proto01_UI2 03 §3): Make's pure parts — the framings per class and an entity version's Make context (makeContext, U1): a
// context never seen is seeded with the entity linked (a character or prop as the subject card, a place as the scene).
import { makeContext, useGenerate, type Tree } from '../../suites/generate/generateStore'
import type { ProfileClass } from '../../suites/story/storyStore'

/** A framing per class (03 §3): the words a picture of the entity needs, not a shot's — the camera and the light are Clay's. */
export const FRAMINGS: Record<ProfileClass, { id: string; label: string; tree: Partial<Tree> }[]> = {
  character: [
    { id: 'portrait', label: 'portrait', tree: { camera: { distance: 'close-up portrait' }, composition: 'head and shoulders' } },
    { id: 'waist', label: 'waist-up', tree: { camera: { distance: 'medium shot' }, composition: 'from the waist up' } },
    { id: 'full', label: 'full body', tree: { camera: { distance: 'full shot' }, composition: 'full body, head to feet in frame' } },
  ],
  prop: [
    { id: 'alone', label: 'on its own', tree: { background: 'a plain light grey studio backdrop', composition: 'the object alone, centred' } },
    { id: 'hand', label: 'in a hand', tree: { composition: 'held in a hand, close' } },
    { id: 'setting', label: 'in its setting', tree: { background: '', composition: 'in its everyday setting' } },
  ],
  place: [
    { id: 'wide', label: 'wide', tree: { camera: { distance: 'wide establishing shot' }, composition: 'the whole place' } },
    { id: 'empty', label: 'empty, eye level', tree: { camera: { distance: 'wide shot', angle: 'eye level' }, composition: 'empty, no people, seen straight on' } },
    { id: 'detail', label: 'a detail', tree: { camera: { distance: 'close-up' }, composition: 'a telling detail of the place' } },
  ],
}

/** D162: a class's reference framing — the words its reference is made with (the server's sentence, `/capabilities.story.references`):
 *  a character's A-pose front and back, a prop's reference view, a place's set picture. With one on, the run is that reference's make. */
export interface RefFraming { id: string; label: string; side: 'front' | 'back' }
export const REF_FRAMINGS: Record<ProfileClass, RefFraming[]> = {
  character: [{ id: 'apose_front', label: 'A-pose front', side: 'front' }, { id: 'apose_back', label: 'A-pose back', side: 'back' }],
  prop: [{ id: 'reference', label: 'reference view', side: 'front' }],
  place: [{ id: 'set_picture', label: 'set picture', side: 'front' }],
}
export type References = Partial<Record<string, Partial<Record<'front' | 'back', string>>>>

/** The tree a reference framing writes: its sentence as the framing words, the camera's distance (a place: wide, at eye level). */
export function refTree(cls: ProfileClass, sentence: string, camera: Tree['camera']): Partial<Tree> {
  return { composition: sentence, camera: { ...camera, ...(cls === 'place' ? { distance: 'wide shot', angle: 'eye level' } : { distance: 'full shot' }) } }
}

/** The framing the words are now: a class framing or a reference framing whose words they are, else none (the author's own words). */
export function activeFraming(cls: ProfileClass, words: string, refs: References | undefined): { id: string; ref: RefFraming | null } | null {
  const w = words.trim()
  if (!w) return null
  const r = REF_FRAMINGS[cls].find((f) => refs?.[cls]?.[f.side]?.trim() === w)
  if (r) return { id: r.id, ref: r }
  const f = FRAMINGS[cls].find((x) => (x.tree.composition ?? '').trim() === w)
  return f ? { id: f.id, ref: null } : null
}

/** The size at 16:9 with about the same pixels (a reference is 16:9), each side a multiple of 16. */
export function to169(width: number, height: number): [number, number] {
  const snap = (x: number) => Math.max(64, Math.round(x / 16) * 16)
  const w = snap(Math.sqrt((width * height * 16) / 9))
  return [w, snap((w * 9) / 16)]
}

/** The context key of an entity version's Make panel. */
export const makeKey = (cls: string, pid: string, vid: string): string => `world/${cls}/${pid}/${vid}`

/** Enter an entity version's Make context; a context never seen is seeded with the entity linked (a subject card, or a place's scene). */
export function enterMake(cls: ProfileClass, pid: string, vid: string): void {
  const key = makeKey(cls, pid, vid)
  const fresh = makeContext.saved(key) === undefined && makeContext.key !== key
  makeContext.enter(key)
  if (!fresh) return
  linkEntity(cls, pid, vid)
  useGenerate.getState().set({ count: Math.min(useGenerate.getState().panel.count, 4) })
}

/** The entity as the panel's subject (a place: its scene) — on entering, and again back in Tree from JSON, which keeps no links (D93 B4). */
export function linkEntity(cls: ProfileClass, pid: string, vid: string): void {
  useGenerate.getState().applyFrame(cls === 'place' ? { text: null, subjects: [], place: pid } : { text: null, subjects: [{ profile_id: pid, version: vid }], place: null })
}
