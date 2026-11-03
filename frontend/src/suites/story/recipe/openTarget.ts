// RC1 (D96, proto01_animate 28): a recipe graph node opened where it is made — Animate's Graph, the shot page's graph and the Flow's in-place
// graph all open a picked node with this (graph.targetOf says where).
import { goToStory } from '../../../store/origin'
import type { Target } from './graph'
import { navigate } from '../../../frame/router'

/** Open a node's place for a shot version (Animate's Graph, the shot page, the Flow's in-place graph). */
export function openTarget(t: Target, shotId: string, version: string): void {
  switch (t.kind) {
    case 'cast': goToStory({ tab: 'cast', id: t.profileId, version: t.version }); return
    case 'flow': goToStory({ tab: 'flow', id: t.nodeId }); return
    case 'shots': goToStory({ tab: 'shots', id: shotId, version }); return
    case 'clay':
      navigate({ suite: 'stage', tab: t.section })                              // the column's section
      void Promise.all([import('../../stage/stageStore'), import('../../../ui2/clay/clayStore')]).then(async ([m, c]) => {
        if (t.stageId) await c.useClay.getState().openScene(t.stageId, { shot: shotId, version, camera: t.cameraId ?? null })   // C0 (D181): the scene in Clay's layer, ← back to the shot
        const st = m.useStage.getState(); if (t.objectId) st.select(t.objectId); if (t.cameraId) st.setActiveCamera(t.cameraId) })
      return
    case 'performance':
      navigate({ suite: 'animate', tab: 'performance' })
      void import('../../animate/routeStore').then((m) => m.useAnimRoute.getState().set(t.card))
      return
    case 'final': navigate({ suite: 'final', tab: t.section }); return
    case 'image':
      void Promise.all([import('../storyStore'), import('../makeFor')]).then(([st, mf]) => {
        const s = st.useStory.getState().shots.find((x) => x.id === shotId), v = s?.versions.find((x) => x.id === version)
        if (s && v && v.state === 'open') void mf.makeFrameFor(s, v)
        else navigate({ suite: 'generate' })
      })
      return
  }
}

/** C4 (RC1): the shot version an image or a clip belongs to — its frame, its clip or one of its takes (the newest version first), or null. */
export async function shotOfAsset(a: { id: string; kind: string }): Promise<{ shotId: string; version: string } | null> {
  const { http, unwrap } = await import('../../../api/client')
  let ids = [a.id]
  if (a.kind === 'video') {                                                     // a clip's take is its clip id; the tile is its proxy's asset
    const c = (await unwrap(http.GET('/clips'))).items.find((x) => x.asset_id === a.id)
    if (!c) return null
    ids = [c.id]
  }
  for (const s of (await unwrap(http.GET('/story/shots'))).items) {
    for (const v of [...s.versions].reverse()) {
      if (ids.includes(v.frame_asset_id ?? '') || ids.includes(v.clip_id ?? '') || v.takes.some((t) => ids.includes(t.id))) return { shotId: s.id, version: v.id }
    }
  }
  return null
}
