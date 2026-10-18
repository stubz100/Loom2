// D95 (AN1, UX0 #5): Image · Make's *From a stage* — stills from a stage, the stage edited in Animate (its Clay level). Pick a stage and a
// camera here; the form is the stage's own still form (method, image 1 = the pass, the reference deck with the figures' bound slots, the
// prompt, size, count, results — `ShotTab` without the clip, which belongs to Animate). The passes render headless when the stage is not on
// screen (headless.ts). Loaded lazily with the stage's code, so Image's eager bundle carries no three.js.
import { CommandButton } from '../../frame/CommandButton'
import { useSession } from '../../store/session'
import { ShotTab, StageFoot, useStageLoad } from './StageParts'
import { st, useStage } from './stageStore'
import './stage.css'

export function FromStage() {
  useStageLoad()
  const stages = useStage((s) => s.stages)
  const current = useStage((s) => s.current)
  if (!stages.length) return <div className="from-stage"><p className="hint">No stage in this project yet — make one in Animate (its Clay level).</p><CommandButton id="global.suite.stage" text label="Open Animate · Clay" /></div>
  return (
    <div className="from-stage">
      <div className="kv"><span>stage</span>
        <select aria-label="the stage" value={current?.id ?? ''} onChange={(e) => { if (e.target.value) void st().open(e.target.value) }}>
          {!current && <option value="">— pick a stage —</option>}
          {stages.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <CommandButton id="global.suite.stage" label="Edit the stage (Animate · Clay)" />
      </div>
      {current && <div className="kv"><span>camera</span>
        <select aria-label="the camera" value={current.active_camera ?? ''} onChange={(e) => st().setActiveCamera(e.target.value)}>
          {current.cameras.map((c) => <option key={c.id} value={c.id}>{c.name} · {c.focal_mm} mm</option>)}
        </select>
      </div>}
      {current && <ShotTab stillsOnly />}
    </div>
  )
}

/** The foot of Image · Make while its source is a stage: New stage / Render frame ×n. */
export function FromStageFoot() {
  const project = useSession((s) => s.project)
  if (!project?.open) return null
  return <StageFoot />
}

export default FromStage
