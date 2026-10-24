// RC1 (D96, proto01_animate 28): a recipe graph node opened where it is made — Animate's Graph, the shot page's graph and the Flow's in-place
// graph all open a picked node with this (graph.targetOf says where).
import { goToStory } from '../../../store/origin'
import { useSession } from '../../../store/session'
import type { Target } from './graph'

/** Open a node's place for a shot version (Animate's Graph, the shot page, the Flow's in-place graph). */
export function openTarget(t: Target, shotId: string, version: string): void {
  const ses = useSession.getState()
  const rail = (suite: string, tab: string) => void import('../../../frame/suiteRegistry').then((r) => r.setRailTab(suite, tab))
  switch (t.kind) {
    case 'cast': goToStory({ tab: 'cast', id: t.profileId, version: t.version }); return
    case 'flow': goToStory({ tab: 'flow', id: t.nodeId }); return
    case 'shots': goToStory({ tab: 'shots', id: shotId, version }); return
    case 'clay':
      ses.setSuite('stage'); rail('stage', t.section)
      void import('../../stage/stageStore').then(async (m) => {                 // the shot's stage opened first: Clay may show another, or none
        if (t.stageId && m.useStage.getState().current?.id !== t.stageId) await m.useStage.getState().open(t.stageId)
        const st = m.useStage.getState(); if (t.objectId) st.select(t.objectId); if (t.cameraId) st.setActiveCamera(t.cameraId) })
      return
    case 'performance':
      ses.setSuite('animate'); rail('animate', 'performance')
      void import('../../animate/routeStore').then((m) => m.useAnimRoute.getState().set(t.card))
      return
    case 'final': ses.setSuite('final'); rail('final', t.section); return
    case 'image':
      void Promise.all([import('../storyStore'), import('../makeFor')]).then(([st, mf]) => {
        const s = st.useStory.getState().shots.find((x) => x.id === shotId), v = s?.versions.find((x) => x.id === version)
        if (s && v && v.state === 'open') void mf.makeFrameFor(s, v)
        else ses.setSuite('generate')
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
