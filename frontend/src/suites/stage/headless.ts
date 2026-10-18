// D95 (AN1, UX0 #5): the stage's passes without its viewport. Image's *From a stage* makes stills from a stage that is not on screen, so
// the pass and sequence renderers cannot come from the mounted viewport (StageParts' Viewport registers them while it lives). A headless
// engine on a detached canvas — never started, no loop, no pointer — follows the open document and renders the same passes; the viewport,
// when it mounts, puts its own renderers back.
import { StageEngine } from './engine'
import { useStage } from './stageStore'

let engine: StageEngine | null = null

/** Install the headless pass and sequence renderers when no viewport has registered its own. Returns whether renderers are available. */
export function ensureHeadless(): boolean {
  const s = useStage.getState()
  if (s.passRenderer && s.sequenceRenderer) return true
  if (!s.current) return false
  engine ??= new StageEngine(document.createElement('canvas'), { onPick: () => undefined, onTransformed: () => undefined, onPosed: () => undefined })
  const e = engine
  useStage.setState({
    passRenderer: (cam, w, h) => { const doc = useStage.getState().current; if (doc) e.sync(doc); return e.renderPasses(cam, w, h) },
    sequenceRenderer: (fr, w, h, kind, restore, on) => e.renderSequence(fr, w, h, kind, restore, on),
  })
  return true
}
