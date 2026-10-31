// proto01_UIcast CW6 (04 §3–4; D143): a place's set on its Cast version — *Build the set ▶* (MoGe on the set picture, the fit scaled by the
// camera's height), the author's edits (the kind, the sizes, the parts, the overlay's drags), the bake (stage/setBake.ts in this page, the
// faces uploaded) and *Fill ▶* (the server fills face after face). The set's state for the page's status line.
import { create } from 'zustand'
import { api, http, sha256Hex, unwrap, type ApiError } from '../../api/client'
import type { Job, Profile } from '../../api/types'
import { useSession } from '../../store/session'
import { bakeKey, type SourceCam } from '../stage/setOverlay'
import { setFaces, type PlaceSetDoc } from '../stage/placeSet'
import { sy, useStory } from './storyStore'

type Version = Profile['versions'][number]
export type PlaceSet = NonNullable<Version['place_set']>
export const EYE_HEIGHT_M = 1.6                                                  // D143: the camera's height a fit is scaled by unless the author says
const toast = (text: string, kind: 'error' | 'info' | 'success' = 'error') => useSession.getState().toast(text, kind)
const detail = (e: unknown) => (e as ApiError).detail ?? String(e)
const busy = (j: Job | undefined) => !!j && !['done', 'failed', 'cancelled'].includes(j.status)

/** The picture a place's set is fitted to: its set picture (the empty place), else its hero. */
export const setPicture = (v: Pick<Version, 'anim_ref_asset_id' | 'hero_asset_id'>) => v.anim_ref_asset_id ?? v.hero_asset_id ?? null
/** The set's camera: the one its picture was matched to. */
export const setCamera = (ps: PlaceSet | null | undefined): SourceCam | null => (ps?.sources[0]?.camera as SourceCam | undefined) ?? null
/** The faces were baked for this set and camera (not for an earlier fit or before an edit). */
export const bakedFresh = (ps: PlaceSet) => { const c = setCamera(ps); return !!c && ps.faces.some((f) => f.baked_asset_id) && ps.baked_key === bakeKey(ps as PlaceSetDoc, c) }

const jobsOf = (jobs: Record<string, Job>, surface: string, pid: string, vid: string) => Object.values(jobs)
  .filter((j) => j.origin?.surface === surface && j.origin?.ref === pid && (j.origin?.payload as { version?: string } | null)?.version === vid)
  .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
export const latestFitJob = (jobs: Record<string, Job>, pid: string, vid: string) => jobsOf(jobs, 'set_fit', pid, vid)[0]
export const fillBusy = (jobs: Record<string, Job>, pid: string, vid: string) => jobsOf(jobs, 'set_fill', pid, vid).some(busy)
export const fitBusy = (jobs: Record<string, Job>, pid: string, vid: string) => busy(latestFitJob(jobs, pid, vid))

/** What the set builder says in a few words (D116: a state, a count). */
export function setStatus(v: Version, jobs: Record<string, Job>, pid: string, baking: boolean): { text: string; warn?: boolean } {
  const fit = latestFitJob(jobs, pid, v.id)
  const ps = v.place_set
  if (busy(fit)) return { text: `fitting the set… ${Math.round((fit!.progress ?? 0) * 100)} %` }
  const err = (fit?.result as { set_error?: string } | null)?.set_error
  if (fit?.status === 'done' && err && (!ps || ps.sources[0]?.made_at < fit.created_at)) return { text: `not fitted: ${err}`, warn: true }
  if (fit?.status === 'failed' && !ps) return { text: `the fit failed: ${fit.error ?? 'see the job'}`, warn: true }
  if (!ps) return { text: setPicture(v) ? 'no set yet' : 'no set picture yet' }
  if (baking) return { text: 'baking the faces…' }
  const filling = ps.faces.filter((f) => f.fill_job_id).length
  if (filling || fillBusy(jobs, pid, v.id)) return { text: `filling ${ps.faces.filter((f) => f.filled).length + 1} of ${ps.faces.filter((f) => f.filled || (f.bad ?? 0) >= 0.002).length} faces…` }
  if (!ps.faces.some((f) => f.baked_asset_id)) return { text: 'fitted · not baked yet' }
  if (!bakedFresh(ps)) return { text: 'changed since the bake', warn: true }
  const toFill = ps.faces.filter((f) => !f.filled && (f.bad ?? 0) >= 0.002)
  if (toFill.length) return { text: `${toFill.length} face${toFill.length === 1 ? '' : 's'} to fill · ${Math.round(100 * unseenShare(ps))} % of the set` }
  return { text: ps.faces.some((f) => f.filled) ? 'baked and filled' : 'baked' }
}

/** The share of the set's area the picture did not see well and no Fill has painted yet. */
export function unseenShare(ps: PlaceSet): number {
  const area = Object.fromEntries(setFaces(ps as PlaceSetDoc).map((f) => [f.id, f.w * f.h]))
  let all = 0, bad = 0
  for (const f of ps.faces) { const a = area[f.id] ?? 0; all += a; bad += (f.filled ? 0 : (f.bad ?? 0)) * a }
  return all ? bad / all : 0
}

const current = () => { const p = sy().profile(); const v = sy().version(); return p && v && p.cls === 'place' ? { p, v } : null }
const put = (p: Profile) => useStory.setState({ profiles: useStory.getState().profiles.map((x) => (x.id === p.id ? p : x)) })

export async function buildSet(cameraHeight = EYE_HEIGHT_M): Promise<void> {
  const c = current(); if (!c) return
  try {
    await unwrap(http.POST('/story/profiles/{pid}/versions/{vid}/set/fit', { params: { path: { pid: c.p.id, vid: c.v.id } }, body: { camera_height_m: cameraHeight } }))
    toast(`Fitting ${c.p.name}'s set to its picture — the faces are baked when it lands`, 'info')
  } catch (e) { toast(`Build the set: ${detail(e)}`) }
}

/** The author's edit of the set (the kind, a size, a part, a drag, a face's material): the faces stay until the next bake. */
export async function saveSet(ps: PlaceSet | null): Promise<boolean> {
  const c = current(); if (!c) return false
  try {
    const p = ps === null ? await unwrap(http.DELETE('/story/profiles/{pid}/versions/{vid}/set', { params: { path: { pid: c.p.id, vid: c.v.id } } }))
      : await unwrap(http.PUT('/story/profiles/{pid}/versions/{vid}/set', { params: { path: { pid: c.p.id, vid: c.v.id } }, body: { revision: c.p.revision, place_set: ps } }))
    put(p)
    return true
  } catch (e) {
    if ((e as ApiError).status === 409) { await sy().loadProfiles(); toast('The set changed meanwhile (a Fill landed) — shown as it is now; edit again', 'info') }
    else toast(`The set: ${detail(e)}`)
    return false
  }
}

export const useSetBuilder = create<{ baking: boolean }>(() => ({ baking: false }))
/** D173: the face whose crowd form is open in Build's face rows (one at a time); D174: or its walkers' form. */
export const useCrowdForm = create<{ face: string | null; walkers?: boolean }>(() => ({ face: null }))

/** D173: *Crowd ▶* — people along a face over a stretch of it (metres from the face's left end, as seen from inside): Klein puts them in,
 *  Wan 2.2 loops them; the face plays it in Clay and the plate. */
export async function makeCrowd(face: string, fromM: number, toM: number, words: string): Promise<boolean> {
  const c = current(); if (!c) return false
  try {
    await unwrap(http.POST('/story/profiles/{pid}/versions/{vid}/set/crowd', { params: { path: { pid: c.p.id, vid: c.v.id } }, body: { face, from_m: fromM, to_m: toM, words } }))
    toast(`A crowd along ${c.p.name}'s ${face}, ${fromM}–${toM} m: the picture, then its loop — about 4 min`, 'info')
    return true
  } catch (e) { toast(`Crowd: ${detail(e)}`); return false }
}

/** D174: *Walkers ▶* — walkers cut out of a loop over a stretch of the face, only those walking on the ground line at its depth, laid
 *  over the face and its crowd. Each segment is its own loop. */
export async function makeWalkers(face: string, fromM: number, toM: number, words: string): Promise<boolean> {
  const c = current(); if (!c) return false
  try {
    await unwrap(http.POST('/story/profiles/{pid}/versions/{vid}/set/walkers', { params: { path: { pid: c.p.id, vid: c.v.id } }, body: { face, from_m: fromM, to_m: toM, words } }))
    toast(`Walkers along ${c.p.name}'s ${face}, ${fromM}–${toM} m: the picture, its loop, then the walkers cut out — about 6 min`, 'info')
    return true
  } catch (e) { toast(`Walkers: ${detail(e)}`); return false }
}

/** D174: a walkers' segment removed (a step still running is stopped; its clips stay in the Bin). */
export async function removeWalkers(face: string, id: string): Promise<void> {
  const c = current(); if (!c) return
  try {
    await unwrap(http.DELETE('/story/profiles/{pid}/versions/{vid}/set/walkers/{fid}/{wid}', { params: { path: { pid: c.p.id, vid: c.v.id, fid: face, wid: id } } }))
  } catch (e) { toast(`Remove the walkers: ${detail(e)}`) }
}

/** D173: the face's crowd removed (a step still running is stopped; its clip stays in the Bin). */
export async function removeCrowd(face: string): Promise<void> {
  const c = current(); if (!c) return
  try {
    await unwrap(http.DELETE('/story/profiles/{pid}/versions/{vid}/set/crowd/{fid}', { params: { path: { pid: c.p.id, vid: c.v.id, fid: face } } }))
  } catch (e) { toast(`Remove the crowd: ${detail(e)}`) }
}

/** The noun a face's Fill names when the author gave no material (place_sets.py NOUN). */
const NOUN: Record<string, string> = { floor: 'the floor', ceiling: 'the ceiling', wall: 'a wall', road: "the road's surface", pavement: 'the pavement', facade: "the buildings' fronts",
  end: 'the far end of the street', backdrop: 'the land and the sky in the distance' }
export const faceNoun = (fid: string) => NOUN[fid.split('_')[0]] ?? 'the surface'

const tried = new Set<string>()
/** A fit just landed (a set with its source and no baked face): baked once, here, while the page shows it. */
export function autoBake(pid: string, vid: string, ps: PlaceSet): void {
  const key = `${pid}/${vid}/${ps.sources[0]?.made_at ?? ''}`
  if (!ps.sources.length || ps.faces.some((f) => f.baked_asset_id) || tried.has(key) || useSetBuilder.getState().baking) return
  tried.add(key)
  void bakeSet()
}

/** The picture projected onto every face from its camera, at the kind's texel (D143), uploaded: the faces become the version's. */
export async function bakeSet(): Promise<boolean> {
  const c = current(); const ps = c?.v.place_set; const cam = setCamera(ps)
  if (!c || !ps || !cam || useSetBuilder.getState().baking) return false
  useSetBuilder.setState({ baking: true })
  try {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.src = api.assetUrl(ps.sources[0].asset_id)
    await img.decode()
    const { bakeSet: bake, TEXEL_BY_KIND } = await import('../stage/setBake')
    const doc = ps as PlaceSetDoc
    const faces = await bake(doc, img, cam, TEXEL_BY_KIND[ps.kind])
    const up = async (b: Blob) => { const sha = await sha256Hex(await b.arrayBuffer()); await api.putBlob(sha, b); return sha }
    const body = { key: bakeKey(doc, cam), faces: [] as { id: string; image: string; coverage: string; texel_m: number; seen: number; bad: number }[] }
    for (const f of faces) body.faces.push({ id: f.id, image: await up(f.texture), coverage: await up(f.coverage), texel_m: f.texel_m, seen: f.seen, bad: f.bad })
    put(await unwrap(http.PUT('/story/profiles/{pid}/versions/{vid}/set/bake', { params: { path: { pid: c.p.id, vid: c.v.id } }, body })))
    return true
  } catch (e) { toast(`Bake the set: ${detail(e)}`); return false }
  finally { useSetBuilder.setState({ baking: false }) }
}

/** D143: the faces' Fill, most seen first, each with its material named — about 45 s a face on Klein (E38). */
export async function fillSet(faces: string[] | null = null): Promise<void> {
  const c = current(); if (!c) return
  try {
    const r = await unwrap(http.POST('/story/profiles/{pid}/versions/{vid}/set/fill', { params: { path: { pid: c.p.id, vid: c.v.id } }, body: { faces } }))
    toast(`${r.faces.length} face${r.faces.length === 1 ? '' : 's'} of ${c.p.name}'s set to fill, one after another — about ${Math.max(1, Math.round(r.faces.length * 45 / 60))} min`, 'info')
  } catch (e) { toast(`Fill the set: ${detail(e)}`) }
}
