import { useEffect, useRef } from 'react'
import { useSession } from '../store/session'
import { StageActive, useStageKeep } from './stageKeep'
import { SUITE_DEFS, useSuite } from './suiteRegistry'

/** The active suite's Stage, plus every visited keep-alive Stage kept mounted but hidden (D69). */
export function Stage() {
  const suite = useSuite()
  const mounted = useStageKeep((s) => s.mounted)
  const keepMin = useSession((s) => s.ui.editKeepAliveMin ?? 10)
  const prev = useRef(suite.id)
  useEffect(() => {
    const k = useStageKeep.getState()
    if (suite.keepAlive) k.visit(suite.id)
    if (prev.current !== suite.id && SUITE_DEFS[prev.current]?.keepAlive) k.hide(prev.current)
    prev.current = suite.id
  }, [suite.id, suite.keepAlive])
  useEffect(() => {                                                      // the release policy's clock: hidden longer than the setting
    const t = window.setInterval(() => { useStageKeep.getState().expire(useSession.getState().ui.suite, keepMin) }, 30_000)
    return () => window.clearInterval(t)
  }, [keepMin])
  const kept = suite.keepAlive && !mounted.includes(suite.id) ? [...mounted, suite.id] : mounted   // the first visit mounts at once
  const SuiteStage = suite.Stage
  return (
    <section className="stage">
      {!suite.keepAlive && <SuiteStage key={suite.id} />}
      {kept.map((id) => {
        const def = SUITE_DEFS[id]
        if (!def) return null
        const on = id === suite.id
        return (
          <div key={id} className="stage-keep" hidden={!on}>
            <StageActive.Provider value={on}><def.Stage /></StageActive.Provider>
          </div>
        )
      })}
    </section>
  )
}
