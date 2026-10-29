// U4c (D157, proto01_UI2 04 §2.1): the shot header's scene — its stage as the header reads it (the open stage's when Clay has it, else
// fetched), the cameras and which shot looks through each, the cast standing on it, and the scene menu's two changes. Pure parts:
// shots.test.ts.
import { useEffect, useState } from 'react'
import { http, unwrap } from '../../api/client'
import type { Profile, Shot, StageDoc } from '../../api/types'
import { useSession } from '../../store/session'
import { useStory } from '../../suites/story/storyStore'
import { readiness } from '../world/readiness'
import { routeRows } from './route'
import { flushClay } from './shotsStore'

/** The route's rows, from the Story store's records. */
export function useRouteRows() {
  const flowGraph = useStory((s) => s.flowGraph)
  const flowNodes = useStory((s) => s.flowNodes)
  const shots = useStory((s) => s.shots)
  const finals = useStory((s) => s.boardFinals)
  const cuts = useStory((s) => s.boardCuts)
  const clipsById = useStory((s) => s.clipsById)
  const cards = useStory((s) => s.cards)
  return routeRows({ flowGraph, flowNodes, shots, finals, cuts, clipsById, cards })
}

export interface StageLite {
  id: string; name: string; revision: number; fps: number; range: { start: number; end: number }
  cameras: { id: string; name: string }[]
  objects: { id: string; kind: string; name: string; profile_id: string | null; version: string | null; visible: boolean }[]
}

export const liteOf = (d: Pick<StageDoc, 'id' | 'name' | 'revision' | 'size' | 'range' | 'cameras' | 'objects'>): StageLite => ({
  id: d.id, name: d.name, revision: d.revision, fps: d.size?.fps ?? 24, range: { start: d.range?.start ?? 0, end: d.range?.end ?? 120 },
  cameras: d.cameras.map((c) => ({ id: c.id, name: c.name })),
  objects: d.objects.map((o) => ({ id: o.id, kind: o.kind, name: o.name, profile_id: o.profile_id ?? null, version: (o as { version?: string | null }).version ?? null, visible: o.visible !== false })),
})

/** The shot's stage for the header: live from the stage store while it is the open stage (Clay), else read once (again when the shots move). */
export function useShotStage(stageId: string | null): StageLite | null {
  const [doc, setDoc] = useState<StageLite | null>(null)
  const shots = useStory((s) => s.shots)                                  // a camera copied for a shot comes back with the shots
  useEffect(() => {
    if (!stageId) return
    let live = true, off: (() => void) | undefined
    void import('../../suites/stage/stageStore').then(({ useStage }) => {
      const read = (): boolean => { const c = useStage.getState().current; if (c?.id !== stageId) return false; if (live) setDoc(liteOf(c)); return true }
      if (!read()) void unwrap(http.GET('/stages/{st_id}', { params: { path: { st_id: stageId } } })).then((d) => { if (live) setDoc(liteOf(d)) }).catch(() => undefined)
      off = useStage.subscribe((x, p) => { if (x.current !== p.current) read() })
    })
    return () => { live = false; off?.() }
  }, [stageId, shots])
  return doc && doc.id === stageId ? doc : null
}

/** Each camera of the stage with the shot that looks through it (a shot's current version first), for the camera menu. */
export function cameraUsers(stageId: string, shots: Pick<Shot, 'id' | 'name' | 'current' | 'versions'>[]): Record<string, string> {
  const out: Record<string, string> = {}
  for (const s of shots) {
    const v = s.versions.find((x) => x.id === s.current) ?? s.versions[0]
    if (v?.stage_id === stageId && v.camera_id && !out[v.camera_id]) out[v.camera_id] = s.name
  }
  return out
}

export interface CastMember { id: string; name: string; cls: 'character' | 'prop' | null; profile: string | null; version: string | null; owed: number; line: string }

/** The cast standing on the stage (04 §2.1): its figures and its World props, bound or not, each with what it still lacks for Clay. */
export function castOf(stage: StageLite, profiles: Profile[]): CastMember[] {
  return stage.objects.filter((o) => o.visible && (o.kind === 'mannequin' || (o.kind === 'mesh' && o.profile_id))).map((o) => {
    const p = o.profile_id ? profiles.find((x) => x.id === o.profile_id) : undefined
    const v = p ? p.versions.find((x) => x.id === (o.version ?? p.current)) ?? p.versions[0] : undefined
    const r = p && v ? readiness(p, v, v.hero_asset_id ? 1 : 0) : null                // the hero is a reference too (World's bin)
    return { id: o.id, name: p?.name ?? o.name, cls: p ? (p.cls === 'prop' ? 'prop' : 'character') : null, profile: p?.id ?? null, version: v?.id ?? null,
      owed: r?.owed ?? 0, line: r ? r.line : 'not bound to World' }
  })
}

/** The scene menu (04 §2.1): a new scene (a place's set, else empty) or the same scene as `like` (that shot's camera, copied). */
export async function rescene(scene: 'new' | 'same', opts: { like?: string | null; place_id?: string | null } = {}): Promise<boolean> {
  const st = useStory.getState(), s = st.shot(), v = st.shotVersion()
  if (!s || !v) return false
  if (scene === 'same') await flushClay()
  try {
    const next = await unwrap(http.POST('/story/shots/{sid}/versions/{vid}/scene', { params: { path: { sid: s.id, vid: v.id } }, body: { scene, like: opts.like ?? null, place_id: opts.place_id ?? null } }))
    useStory.setState({ shots: useStory.getState().shots.map((x) => (x.id === next.id ? next : x)) })
    await Promise.all([useStory.getState().loadFlow(), useStory.getState().loadShotDetails()])
    return true
  } catch (e) { useSession.getState().toast(`Scene: ${(e as { detail?: string }).detail ?? e}`, 'error'); return false }
}

/** The shot's range on its scene's timeline (null: the stage's whole range). */
export async function setRange(range: { start: number; end: number } | null): Promise<void> {
  const st = useStory.getState(), s = st.shot(), v = st.shotVersion()
  if (!s || !v) return
  try {
    const next = await unwrap(http.PATCH('/story/shots/{sid}', { params: { path: { sid: s.id } }, body: { revision: s.revision, versions: [{ id: v.id, range }] } as never }))
    useStory.setState({ shots: useStory.getState().shots.map((x) => (x.id === next.id ? next : x)) })
  } catch (e) { useSession.getState().toast(`Range: ${(e as { detail?: string }).detail ?? e}`, 'error') }
}
