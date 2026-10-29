// D121 (proto01_animate 26 §5.5, AW3): the Shot section that heads every Animate level — the stage the shot uses (a picker, not the list of
// every stage) and the stepper: the stage's pipeline in one row, each step's state, a click to the step's level and card. passes (Clay) ·
// frame (Image › From a stage) · clip (Performance › Stage clip) · final (Performance › Final shot) · composition and render (Final). Each
// step's verb is the foot of the level it opens, so the row carries no second primary; it replaces the rig strip of D116 U7 and the passes
// row of AN1 #16. Light: no three.js engine here (the Final level imports it).
import { Hammer, PersonStanding, Send, Users } from 'lucide-react'
import { CommandButton, MenuButton } from '../../frame/CommandButton'
import { markUsed, runCommand, sep, type MenuItem } from '../../frame/commands'
import { Help } from '../../frame/Help'
import { useSession } from '../../store/session'
import type { Job } from '../../api/types'
import { useMakeFor } from '../../store/origin'
import { ForChip } from '../story/ForChip'
import { ForRecipe } from '../story/RecipeSteps'
import { assembling, newestFinal, rendering, useFinals, useFinalsPoll } from './finalShot'
import { st, useStage } from './stageStore'
import { stageSteps, STATE_WORD, type StepInput } from './steps'

const live = (j: Job) => j.status === 'queued' || j.status === 'running'

/** The stepper's input from the stores — the stage's newest final, the session's jobs by their origin. */
function useStepInput(): StepInput | null {
  const current = useStage((s) => s.current)
  const cam = useStage((s) => s.activeCamera())
  const entry = useStage((s) => s.passesEntry())
  const stale = useStage((s) => s.passesStale())
  const shots = useStage((s) => s.shots)
  const guiding = useStage((s) => s.rendering && !!s.rendered)
  const finals = useFinals((s) => s.finals)
  const comps = useFinals((s) => s.compositions)
  const making = useFinals((s) => !!s.making)
  const jobs = useSession((s) => s.jobs)
  useFinalsPoll(current?.id)                                           // the final's and its composition's states, whichever level is open
  if (!current) return null
  const mine = (surface: string) => Object.values(jobs).some((j) => live(j) && j.origin?.suite === 'stage' && j.origin.surface === surface && j.origin.ref === current.id)
  const f = newestFinal(finals, current.id) ?? null
  const made = (l: { kind: string; status: string; frames_done: number }) => (l.kind === 'plate' || l.kind === 'figure' ? l.status === 'done' && l.frames_done === f!.frames : l.status !== 'failed')
  const c = f ? comps[f.id] ?? null : null
  return {
    camera: cam?.name ?? null,
    passes: entry ? { n: Object.keys(entry.assets).length, size: `${entry.size.w}×${entry.size.h}`, stale } : null,
    stills: shots.filter((a) => a.kind !== 'video').length, frameRunning: mine('shot'),
    clips: shots.filter((a) => a.kind === 'video').length, clipRunning: mine('clip') || guiding,
    final: f ? { layers: f.layers.length, done: f.layers.filter(made).length, running: f.layers.some((l) => l.status === 'queued' || l.status === 'running') || assembling(f.id), assembled: !!f.assembled_at } : null,
    making,
    comp: c ? { revision: c.revision, stale: !!c.stale, rendered: c.clip_id ? (c.rendered_revision ?? c.revision) : null, rendering: rendering(f!.id) } : null,
  }
}

/** The stepper: one row of the stage's steps — the state as a dot, a count where there is one, the words in the tooltip (D116). */
export function ShotStepper() {
  const input = useStepInput()
  if (!input) return null
  const steps = stageSteps(input)
  return (
    <div className="shot-stepper" role="list" aria-label="the shot's steps" data-stepper>
      {steps.map((s) => { markUsed(s.cmd); return (
        <button key={s.id} type="button" role="listitem" className={`step s-${s.state}`} data-step={s.id} data-state={s.state} title={`${s.tip} (${STATE_WORD[s.state]})`} onClick={() => runCommand(s.cmd)}>
          <i className="dot" aria-hidden="true" /><span>{s.label}</span>{s.count && <small>{s.count}</small>}
        </button>) })}
      <Help text="The stage's pipeline: the passes of its camera, its frames, its clip, the final shot's layers, their composition, the finished render. A dot is the step's state — hollow not yet, filled done, amber stale, pulsing running, half a final part made. A click opens the step where its verb is (the foot)." />
    </div>
  )
}

/** The stage the shot uses — a picker (the project's stages) with New stage, and what it holds. */
export function StagePicker() {
  const current = useStage((s) => s.current)
  const stages = useStage((s) => s.stages)
  markUsed('stage.new')
  const listed = stages.filter((s) => s.purpose === 'stage')                       // D142: a bench and the line-up are not stages to pick
  return (
    <div className="stage-picker">
      <span className="lbl">stage</span>
      <select aria-label="the stage" value={current?.id ?? ''} onChange={(e) => void st().open(e.target.value || null)}>
        {!current && <option value="">{listed.length ? '— pick a stage —' : '— no stage yet —'}</option>}
        {current && current.purpose !== 'stage' && <option value={current.id}>{current.name}</option>}
        {listed.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
      </select>
      <CommandButton id="stage.new" />
      {current && <span className="hint">{current.objects.length} object{current.objects.length === 1 ? '' : 's'} · {current.cameras.length} cam{current.cameras.length === 1 ? '' : 's'}</span>}
      {!stages.length && <button type="button" className="quiet" onClick={() => runCommand('stage.new')}>New stage…</button>}
    </div>
  )
}

/** D142: Clay opened for a Cast version (*Bench · Mara v1*) or on the line-up (CW5) — what it is and the way back; the line-up's verbs. */
function BenchChip() {
  const cur = useStage((s) => s.current)
  const stages = useStage((s) => s.stages)
  if (!cur || cur.purpose === 'stage') return null
  markUsed('stage.bench.back'); markUsed('stage.lineup.send'); markUsed('stage.lineup.pose')
  if (cur.purpose === 'bench') return (
    <div className="for-chip bench-chip" data-testid="bench-chip" title="Clay opened for a Cast version: its figure (or its prop) follows Cast; what you change here is the bench's own scene">
      <span className="for-what"><Hammer size={14} /> Bench: <b>{cur.name.replace(/^Bench · /, '')}</b></span>
      <CommandButton id="stage.bench.back" text size={14} label="Back to Cast" />
    </div>
  )
  const figures = cur.objects.filter((o) => o.kind !== 'set').length
  return (
    <div className="for-chip bench-chip" data-testid="bench-chip" title="The line-up: side by side at their sizes before 0.5 m marks — a scratch scene, made again each time">
      <span className="for-what"><Users size={14} /> Line-up · <b>{figures}</b></span>
      <MenuButton label="Pose all" text size={14} icon={PersonStanding} items={() => [{ cmd: 'stage.lineup.pose' }, sep, ...['walk', 'sit', 'wave', 'point'].map((p): MenuItem => ({ label: p, run: () => st().poseAll(p) }))]} />
      <MenuButton label="Send to a stage" text size={14} icon={Send} items={() => { const to = stages.filter((s) => s.purpose === 'stage').slice(0, 12)
        return [{ cmd: 'stage.lineup.send' }, ...(to.length ? [sep] : []), ...to.map((s): MenuItem => ({ label: s.name, run: () => void st().sendLineup(s.id) }))] }} />
      <CommandButton id="stage.bench.back" text size={14} label="Back" />
    </div>
  )
}

/** The Shot section of a level: the For chip and the Story shot's recipe, then (when the work is the stage's) the stage and its steps. */
export function ShotHead({ stage = true }: { stage?: boolean }) {
  const forShot = useMakeFor((s) => s.animate)
  return (
    <div className="shot-head">
      <BenchChip /><ForChip maker="animate" /><ForRecipe maker="animate" />
      {stage && <><StagePicker /><ShotStepper /></>}
      {!stage && !forShot && <span className="hint">Not for a Story shot. <Help text="A clip made here stands alone in the Bin. Opened from Story (a shot's Make clip ▸), the shot is named here and its clips come back as its takes." /></span>}
    </div>
  )
}
